# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.gu.graph_utils import (
    ASTERISK,
    COMMA,
    DECIMAL_25,
    DECIMAL_75,
    GU_ADHI,
    GU_BY,
    GU_DODH,
    GU_PERIOD,
    GU_PONA,
    GU_SADA,
    GU_SAVVA,
    HYPHEN,
    LOWERCASE_X,
    MIN_NEG_WEIGHT,
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_GU_DIGIT,
    NEMO_NOT_SPACE,
    NEMO_SPACE,
    NEMO_WHITE_SPACE,
    ONE_POINT_FIVE,
    PERIOD,
    POINT_FIVE,
    SLASH,
    TWO_POINT_FIVE,
    UPPERCASE_X,
    GraphFst,
    capitalized_input_graph,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.gu.utils import get_abs_path

digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
zero = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))
telephone_number = pynini.string_file(get_abs_path("data/telephone/number.tsv"))
states_map = pynini.string_file(get_abs_path("data/address/states.tsv"))
cities_map = pynini.string_file(get_abs_path("data/address/cities.tsv"))
special_characters_map = pynini.string_file(get_abs_path("data/address/special_characters.tsv"))
letters_map = pynini.string_file(get_abs_path("data/address/letters.tsv"))
context_map = pynini.string_file(get_abs_path("data/address/context.tsv"))


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure in Gujarati, e.g.
        -૧૨kg -> measure { cardinal { negative: "true" integer: "બાર" } units: "કિલોગ્રામ" }
        -૧૨.૨kg -> measure { decimal { negative: "true" integer_part: "બાર" fractional_part: "બે" } units: "કિલોગ્રામ" }
        અમદાવાદ ૩૮૦૦૦૧ -> measure { units: "address" cardinal { integer: "અમદાવાદ ત્રણ આઠ શૂન્ય શૂન્ય શૂન્ય એક" } preserve_order: true }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
    """

    def get_structured_address_graph(self, cardinal: GraphFst, ordinal: GraphFst, input_case: str):
        state_city_names = pynini.union(states_map, cities_map).optimize()
        num_token = (digit | zero | telephone_number).optimize()
        pincode = (num_token + pynini.closure(insert_space + num_token, 5, 5)).optimize()
        trailing_sep = pynini.closure(pynutil.delete(COMMA), 0, 1) + delete_space

        graph_city_pincode = (
            state_city_names
            + trailing_sep
            + insert_space
            + pincode
        )

        graph = (
            pynutil.insert('units: "address" cardinal { integer: "')
            + graph_city_pincode
            + pynutil.insert('" } preserve_order: true')
        )
        return pynutil.add_weight(graph, 1.0).optimize()

    def get_address_graph(self, cardinal: GraphFst, ordinal: GraphFst, serial: GraphFst, input_case: str):
        ordinal_graph = ordinal.graph
        char_to_word = (digit | zero | special_characters_map | telephone_number).optimize()
        letter_to_word = capitalized_input_graph(letters_map)
        address_keywords = pynini.project(
            capitalized_input_graph(context_map),
            "input",
        ).optimize()

        single_digit = pynini.union(NEMO_DIGIT, NEMO_GU_DIGIT).optimize()
        special_chars = pynini.union(HYPHEN, SLASH).optimize()
        single_letter = pynini.project(letter_to_word, "input").optimize()
        convertible_char = pynini.union(single_digit, special_chars, single_letter)
        non_space_char = pynini.difference(
            NEMO_CHAR, pynini.union(NEMO_WHITE_SPACE, convertible_char, pynini.accep(COMMA))
        ).optimize()

        comma_processor = delete_space + pynini.accep(COMMA)
        ordinal_processor = insert_space + ordinal_graph
        latin_word = single_letter + pynini.closure(single_letter, 1)
        english_word_processor = insert_space + latin_word
        letter_processor = insert_space + pynini.compose(single_letter, letter_to_word)
        special_char_processor = insert_space + pynini.compose(special_chars, char_to_word)
        other_word_processor = insert_space + pynini.closure(non_space_char, 1)

        code_processor = insert_space + serial.mixed_alphanum_graph
        number_run = pynini.compose(pynini.closure(single_digit, 1), cardinal.code_num_graph).optimize()
        number_run_processor = insert_space + number_run

        token_processor = (
            pynini.accep(NEMO_SPACE)
            | comma_processor
            | special_char_processor
            | code_processor
            | pynutil.add_weight(ordinal_processor, MIN_NEG_WEIGHT)
            | pynutil.add_weight(number_run_processor, 0.5)
            | letter_processor
            | english_word_processor
            | pynutil.add_weight(other_word_processor, 0.1)
        ).optimize()

        full_string_processor = pynini.closure(token_processor, 1).optimize()

        word_boundary = pynini.union(
            NEMO_WHITE_SPACE, pynini.accep(COMMA), pynini.accep(GU_PERIOD), pynini.accep(PERIOD)
        ).optimize()
        non_boundary_char = pynini.difference(NEMO_CHAR, word_boundary)
        word = pynini.closure(non_boundary_char, 1).optimize()
        word_with_boundary = word + pynini.closure(word_boundary)
        window = pynini.closure(word_with_boundary, 0, 5).optimize()
        boundary = pynini.closure(word_boundary, 1).optimize()
        input_pattern = pynini.union(
            address_keywords + boundary + window,
            window + boundary + address_keywords + pynini.closure(boundary + window, 0, 1),
        ).optimize()
        address_graph = pynini.compose(input_pattern, full_string_processor).optimize()
        address_graph = (
            address_graph @ pynini.cdrewrite(pynutil.delete(NEMO_SPACE), "[BOS]", "", pynini.closure(NEMO_CHAR))
        ).optimize()
        graph = (
            pynutil.insert('units: "address" cardinal { integer: "')
            + address_graph
            + pynutil.insert('" } preserve_order: true')
        )
        return graph.optimize()

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, ordinal: GraphFst, serial: GraphFst, input_case: str):
        super().__init__(name="measure", kind="classify")

        cardinal_graph = (
            cardinal.zero
            | cardinal.digit
            | cardinal.teens_and_ties
            | cardinal.graph_hundreds
            | cardinal.graph_thousands
            | cardinal.graph_ten_thousands
            | cardinal.graph_lakhs
            | cardinal.graph_ten_lakhs
        )
        point = pynutil.delete(".")
        decimal_integers = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')
        decimal_graph = decimal_integers + point + insert_space + decimal.graph_fractional
        unit_graph = pynini.string_file(get_abs_path("data/measure/unit.tsv"))

        year_informal = pynini.string_map([("yr", "વર્ષ")])
        year_formal = pynini.string_file(get_abs_path("data/measure/unit_year_formal.tsv"))

        unit_inputs_except_yr = pynini.difference(pynini.project(unit_graph, "input"), pynini.accep("yr"))
        unit_graph_no_year = pynini.compose(unit_inputs_except_yr, unit_graph)

        quarterly_units_map = pynini.string_file(get_abs_path("data/measure/quarterly_units_map.tsv"))
        quarterly_units_list = pynini.string_file(get_abs_path("data/measure/quarterly_units_list.tsv"))
        quarterly_units_graph = pynini.union(quarterly_units_map, quarterly_units_list)

        delete_opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        optional_graph_negative = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true"') + insert_space)
            | (pynini.cross("~", 'negative: "આશરે"') + delete_opt_sp + insert_space)
            | (pynini.cross("±", 'negative: "વત્તા કે ઓછા"') + delete_opt_sp + insert_space),
            0,
            1,
        )

        unit = (
            pynutil.insert(NEMO_SPACE)
            + pynutil.insert('units: "')
            + unit_graph_no_year
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )
        units = (
            pynutil.insert(NEMO_SPACE)
            + pynutil.insert('units: "')
            + quarterly_units_graph
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )

        unit_year_informal = (
            pynutil.insert(NEMO_SPACE)
            + pynutil.insert('units: "')
            + year_informal
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )
        unit_year_formal = (
            pynutil.insert(NEMO_SPACE)
            + pynutil.insert('units: "')
            + year_formal
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )

        cardinal_large = cardinal.graph_without_leading_zeros
        cardinal_small = cardinal.zero | cardinal.digit | cardinal.teens_and_ties | cardinal.graph_hundreds

        symbol_graph = pynini.string_map(
            [
                (LOWERCASE_X, GU_BY),
                (UPPERCASE_X, GU_BY),
                (ASTERISK, GU_BY),
            ]
        )

        graph_decimal = (
            pynutil.insert("decimal { ")
            + optional_graph_negative
            + decimal_graph
            + pynutil.insert(" }")
            + delete_space
            + unit
        )

        dedh_dhai = pynini.union(
            pynini.cross(ONE_POINT_FIVE, GU_DODH),
            pynini.cross(TWO_POINT_FIVE, GU_ADHI),
        )
        dedh_dhai_graph = pynutil.insert('integer: "') + dedh_dhai + pynutil.insert('"')

        savva_numbers = cardinal_graph + pynini.cross(DECIMAL_25, "")
        savva_graph = (
            pynutil.insert('integer: "')
            + pynutil.insert(GU_SAVVA)
            + pynutil.insert(NEMO_SPACE)
            + savva_numbers
            + pynutil.insert('"')
        )

        sadhe_numbers = cardinal_graph + pynini.cross(POINT_FIVE, "")
        sadhe_graph = (
            pynutil.insert('integer: "')
            + pynutil.insert(GU_SADA)
            + pynutil.insert(NEMO_SPACE)
            + sadhe_numbers
            + pynutil.insert('"')
        )

        paune = pynini.string_file(get_abs_path("data/whitelist/paune_mappings.tsv"))
        paune_numbers = paune + pynini.cross(DECIMAL_75, "")
        paune_graph = (
            pynutil.insert('integer: "')
            + pynutil.insert(GU_PONA)
            + pynutil.insert(NEMO_SPACE)
            + paune_numbers
            + pynutil.insert('"')
        )

        graph_dedh_dhai = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + dedh_dhai_graph
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("}")
            + delete_space
            + units
        )

        graph_savva = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + savva_graph
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("}")
            + delete_space
            + units
        )

        graph_sadhe = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + sadhe_graph
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("}")
            + delete_space
            + units
        )

        graph_paune = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + paune_graph
            + pynutil.insert(" }")
            + delete_space
            + units
        )

        range_sep = pynini.cross(pynini.union("-", "–", "—", " - ", " – ", " — "), " થી ")
        range_cardinal = cardinal_graph + range_sep + cardinal_graph
        range_decimal_val = cardinal_graph + pynini.cross(".", " દશાંશ ") + decimal.graph
        range_num = (
            range_cardinal
            | (range_decimal_val + range_sep + range_decimal_val)
            | (cardinal_graph + range_sep + range_decimal_val)
            | (range_decimal_val + range_sep + cardinal_graph)
        ).optimize()

        graph_cardinal = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert('integer: "')
            + (cardinal_graph | range_num)
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("}")
            + delete_space
            + unit
        )

        graph_cardinal_year_formal = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert('integer: "')
            + cardinal_large
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("}")
            + delete_space
            + unit_year_formal
        )

        graph_cardinal_year_informal = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert('integer: "')
            + cardinal_small
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("}")
            + delete_space
            + unit_year_informal
        )

        graph_decimal_year_formal = (
            pynutil.insert("decimal { ")
            + optional_graph_negative
            + decimal_graph
            + pynutil.insert(" }")
            + delete_space
            + unit_year_formal
        )

        graph_exceptions = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert('integer: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynutil.insert(" }")
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert('units: "')
            + symbol_graph
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("} }")
            + insert_space
            + pynutil.insert("tokens { cardinal { ")
            + optional_graph_negative
            + pynutil.insert('integer: "')
            + cardinal_graph
            + pynutil.insert('"')
        )

        address_graph = self.get_address_graph(cardinal, ordinal, serial, input_case)
        structured_address_graph = self.get_structured_address_graph(cardinal, ordinal, input_case)

        any_d = NEMO_DIGIT | NEMO_GU_DIGIT
        zero_d = pynini.union("0", "૦")
        nonzero_d = pynini.difference(any_d, zero_d)
        glued_decade = (
            (pynini.union("1", "2", "૧", "૨") + any_d + any_d + zero_d + "s")
            | (nonzero_d + zero_d + "s")
        ).optimize()
        not_glued_decade = pynini.difference(pynini.closure(NEMO_CHAR), glued_decade).optimize()

        measure_body = pynini.compose(
            not_glued_decade,
            pynutil.add_weight(graph_decimal, -0.05)
            | pynutil.add_weight(graph_decimal_year_formal, -0.05)
            | pynutil.add_weight(graph_cardinal, -0.05)
            | pynutil.add_weight(graph_cardinal_year_formal, -0.05)
            | pynutil.add_weight(graph_cardinal_year_informal, -0.1)
            | pynutil.add_weight(graph_exceptions, 0.1)
            | pynutil.add_weight(graph_dedh_dhai, -0.2)
            | pynutil.add_weight(graph_savva, -0.1)
            | pynutil.add_weight(graph_sadhe, -0.1)
            | pynutil.add_weight(graph_paune, -0.5),
        ).optimize()

        graph = measure_body | address_graph | structured_address_graph
        self.graph = graph.optimize()

        final_graph = self.add_tokens(self.graph)
        self.fst = final_graph
