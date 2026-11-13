# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

import re

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.hu.graph_utils import ensure_space
from nemo_text_processing.text_normalization.hu.utils import (
    get_abs_path,
    inflect_abbreviation,
    load_labels,
    naive_inflector,
)

maj_singular = pynini.string_file(get_abs_path("data/money/currency.tsv"))
per_units = pynini.string_file(get_abs_path("data/money/per_unit.tsv"))


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, e.g.
        "€1" -> money { currency_maj: "euró" integer_part: "egy"}
        "€1,000" -> money { currency_maj: "euró" integer_part: "egy" }
        "€1,001" -> money { currency_maj: "euró" integer_part: "egy" fractional_part: "egy"}
        "£1,4" -> money { integer_part: "egy" currency_maj: "font" fractional_part: "negyven" preserve_order: true}
               -> money { integer_part: "egy" currency_maj: "font" fractional_part: "negyven" currency_min: "penny" preserve_order: true}
        "£0,01" -> money { fractional_part: "egy" currency_min: "penny" preserve_order: true}
        "£0,01 million" -> money { currency_maj: "font" integer_part: "nulla" fractional_part: "egy század" quantity: "millió"}

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)
        # an amount of exactly one magnitude is counted: 1 000 000 Ft -> egymillió forint
        cardinal_graph = (cardinal.graph @ cardinal.counted).optimize()
        graph_decimal_final = decimal.final_graph_wo_negative
        dot_to_comma = pynini.cdrewrite(pynini.cross(".", ","), "", "", NEMO_SIGMA)
        dot_decimal_simple = (
            pynini.closure(NEMO_DIGIT, 1) + "." + (pynini.closure(NEMO_DIGIT, 1) - NEMO_DIGIT**3)
        ) @ dot_to_comma
        decimal_comma_or_dot = (
            graph_decimal_final
            | ((dot_decimal_simple + pynini.closure(" " + pynini.closure(NEMO_ALPHA, 1), 0, 1)) @ graph_decimal_final)
        ).optimize()

        maj_singular_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        min_singular_labels = load_labels(get_abs_path("data/money/currency_minor.tsv"))
        maj_dict = dict(maj_singular_labels)
        maj_singular_graph = convert_space(maj_singular).optimize()

        letters = pynini.string_file(get_abs_path("data/money/alphabet.tsv"))
        if not deterministic:
            letters |= pynini.cross("W", "vé")
            letters |= pynini.cross("W", "kettős vé")
        read_letters = letters + pynini.closure(insert_space + letters)
        self.read_letters = read_letters

        graph_maj_singular = (pynutil.insert("currency_maj: \"") + maj_singular_graph + pynutil.insert("\"")).optimize()

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(pynini.union(",", ".")) + pynini.closure(pynutil.delete("0"), 1), 0, 1
        )

        # only for decimals where third decimal after comma/dot is non-zero or with quantity
        decimal_delete_last_zeros = (
            pynini.closure(NEMO_DIGIT, 1)
            + pynini.cross(pynini.union(",", "."), ",")
            + pynini.closure(NEMO_DIGIT, 2)
            + (NEMO_DIGIT - "0")
            + pynini.closure(pynutil.delete("0"))
        )
        decimal_with_quantity = (
            pynini.closure(NEMO_DIGIT, 1)
            + pynini.closure(pynini.cross(pynini.union(",", "."), ",") + pynini.closure(NEMO_DIGIT, 1), 0, 1)
            + " "
            + pynini.closure(NEMO_ALPHA, 1)
        )
        decimal_part = ((decimal_delete_last_zeros | decimal_with_quantity) @ graph_decimal_final).optimize()
        optional_space = pynini.closure(pynutil.delete(" "), 0, 1)
        graph_decimal = graph_maj_singular + optional_space + insert_space + decimal_part

        graph_integer = (pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")).optimize()
        graph_range = (pynutil.insert("integer_part: \"") + cardinal.range + pynutil.insert("\"")).optimize()

        # Shorthand magnitudes: k/K -> ezer, M -> millió, B -> milliárd
        k_suffix = optional_space + pynutil.delete(pynini.union("k", "K"))
        cardinal_k = (
            pynini.cross("1", "ezer")
            | (((pynini.closure(NEMO_DIGIT, 1) - "1") - "0") @ cardinal.graph) + pynutil.insert("ezer")
        ).optimize()
        graph_k_int = (pynutil.insert("integer_part: \"") + cardinal_k + k_suffix + pynutil.insert("\"")).optimize()

        mag_shorthand = pynini.string_map([("k", "ezer"), ("K", "ezer"), ("M", "millió"), ("B", "milliárd")])
        dec_base_comma_or_dot = (
            (pynini.closure(NEMO_DIGIT, 1) + pynini.cross(pynini.union(",", "."), ",") + pynini.closure(NEMO_DIGIT, 1))
            @ (decimal.graph_integer + pynutil.delete(",") + insert_space + decimal.graph_fractional)
        ).optimize()
        graph_mag_dec = (
            dec_base_comma_or_dot
            + optional_space
            + pynutil.insert(" quantity: \"")
            + mag_shorthand
            + pynutil.insert("\"")
        ).optimize()
        int_mb_shorthand = pynini.string_map([("M", "millió"), ("B", "milliárd")])
        graph_mb_int = (
            pynutil.insert("integer_part: \"")
            + (
                (pynini.cross("1", "egy") + optional_space + int_mb_shorthand)
                | ((((pynini.closure(NEMO_DIGIT, 1) - "1") - "0") @ cardinal.graph) + optional_space + int_mb_shorthand)
            )
            + pynutil.insert("\"")
        ).optimize()
        shorthand_amount = (graph_k_int | graph_mb_int | graph_mag_dec).optimize()

        graph_integer_only = graph_maj_singular + optional_space + insert_space + (graph_integer | graph_range)
        graph_shorthand_leading = graph_maj_singular + optional_space + insert_space + shorthand_amount

        graph = (
            (graph_integer_only + optional_delete_fractional_zeros)
            | graph_decimal
            | graph_shorthand_leading
        )

        # remove trailing zeros of non zero number in the first 2 digits and fill up to 2 digits
        two_digits_fractional_part = (
            pynini.closure(NEMO_DIGIT) + (NEMO_DIGIT - "0") + pynini.closure(pynutil.delete("0"))
        ) @ (
            (pynutil.delete("0") + (NEMO_DIGIT - "0"))
            | ((NEMO_DIGIT - "0") + pynutil.insert("0"))
            | ((NEMO_DIGIT - "0") + NEMO_DIGIT)
        )

        graph_fractional = (
            pynutil.insert("fractional_part: \"")
            + (two_digits_fractional_part @ pynini.closure(NEMO_DIGIT, 1, 2) @ cardinal.two_digit_non_zero)
            + pynutil.insert("\"")
        ).optimize()
        non_zero_integer = ((pynini.closure(NEMO_DIGIT, 1) - "0") @ graph_integer).optimize()
        preserve_order = pynutil.insert(" preserve_order: true")

        trailing_maj_dict = {}
        trailing_maj_forms = []

        for curr_symbol, cur_word in maj_singular_labels:
            trailing_maj_dict[curr_symbol] = cur_word
            trailing_maj_dict[cur_word] = cur_word
            for ikey, ival in naive_inflector(curr_symbol, cur_word):
                trailing_maj_dict[ikey] = ival
                trailing_maj_dict[ival] = ival
            if re.match("^[A-Z]{3}$", curr_symbol):
                letter_pairs = list(inflect_abbreviation(curr_symbol, cur_word))
                for ikey, ival in letter_pairs:
                    trailing_maj_dict[ikey] = ival
                if not deterministic:
                    letter_expansion = pynini.string_map(letter_pairs)
                    expanded = curr_symbol @ read_letters
                    get_endings = pynini.project(letter_expansion, "input")
                    letter_endings = get_endings @ (
                        pynini.cdrewrite(pynini.cross(f"{curr_symbol}-", expanded), "[BOS]", "", NEMO_SIGMA)
                    )
                    trailing_maj_forms.append(letter_endings | pynini.project(letter_endings, "output"))

        trailing_maj_fst = convert_space(pynini.string_map(list(trailing_maj_dict.items())))
        if trailing_maj_forms:
            trailing_maj_fst |= convert_space(pynini.union(*trailing_maj_forms))
        graph_maj_final = (
            pynutil.insert("currency_maj: \"") + trailing_maj_fst.optimize() + pynutil.insert("\"")
        ).optimize()

        # Zero-loop factored major+minor decimal currencies
        lead_maj_min_map = convert_space(
            pynini.string_map(
                [(s, f'currency_maj: "{maj_dict[s]}" currency_min: "{mn}" ') for s, mn in min_singular_labels if s in maj_dict]
            )
        ) | pynini.cdrewrite(pynini.cross("\u00a0", " "), "", "", NEMO_SIGMA)
        lead_maj_min_map = pynini.string_map(
            [
                (s, f'currency_maj: "{maj_dict[s].replace(" ", "\u00a0")}" currency_min: "{mn.replace(" ", "\u00a0")}" ')
                for s, mn in min_singular_labels
                if s in maj_dict
            ]
        ).optimize()
        lead_min_only_map = pynini.string_map(
            [(s, f'currency_min: "{mn.replace(" ", "\u00a0")}" ') for s, mn in min_singular_labels]
        ).optimize()
        trail_maj_min_map = pynini.string_map(
            [
                (s, f' currency_maj: "{maj_dict[s].replace(" ", "\u00a0")}" currency_min: "{mn.replace(" ", "\u00a0")}"')
                for s, mn in min_singular_labels
                if s in maj_dict
            ]
        ).optimize()
        trail_min_only_map = pynini.string_map(
            [(s, f' currency_min: "{mn.replace(" ", "\u00a0")}"') for s, mn in min_singular_labels]
        ).optimize()

        dec_sep = pynini.cross(pynini.union(",", "."), " ")
        zero_dec_prefix = pynutil.delete(pynini.union("0,", "0."))

        lead_minor = (lead_maj_min_map + optional_space + non_zero_integer + dec_sep + graph_fractional) | (
            lead_min_only_map + optional_space + zero_dec_prefix + graph_fractional
        )
        trail_minor = pynutil.add_weight(
            (non_zero_integer + dec_sep + graph_fractional + optional_space + trail_maj_min_map)
            | (zero_dec_prefix + graph_fractional + optional_space + trail_min_only_map + preserve_order),
            -0.0001,
        )
        decimal_graph_with_minor = (lead_minor | trail_minor).optimize()

        graph |= (
            (decimal_comma_or_dot | ((graph_integer | graph_range) + optional_delete_fractional_zeros) | shorthand_amount)
            + ensure_space
            + graph_maj_final
            + preserve_order
        )

        # Trailing cent symbol: "25¢" -> "huszonöt cent"
        cent_graph = (
            pynutil.insert("fractional_part: \"")
            + cardinal_graph
            + pynutil.insert("\" currency_min: \"cent\" preserve_order: true")
            + optional_space
            + pynutil.delete("¢")
        )

        # Factored money ranges with repeated symbol: "$10-$20", "€10–€20"
        from_num = ((pynini.closure(NEMO_DIGIT, 1) @ cardinal_graph) @ cardinal.from_suffix).optimize()
        to_num = ((pynini.closure(NEMO_DIGIT, 1) @ cardinal_graph) @ cardinal.to_suffix).optimize()
        range_dash = pynini.cross(pynini.union("-", "–", "—"), " ")
        sym_only_labels = [(s, w) for s, w in maj_singular_labels if not s.isalpha()]
        sym_range_list = []
        for s, w in sym_only_labels:
            lead = pynutil.insert(f'currency_maj: "{w.replace(" ", "\u00a0")}" integer_part: "') + pynutil.delete(s)
            r = (
                lead
                + optional_space
                + from_num
                + range_dash
                + pynutil.delete(s)
                + optional_space
                + to_num
                + pynutil.insert('"')
            )
            sym_range_list.append(r)
        same_sym_range = pynini.union(*sym_range_list).optimize() if sym_range_list else pynini.Fst()

        pos_graph = (graph | decimal_graph_with_minor | cent_graph | same_sym_range).optimize()

        graph_per_units = (
            pynutil.insert(" morphosyntactic_features: \"") + convert_space(per_units) + pynutil.insert("\"")
        ).optimize()

        optional_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), "\"true\" ") + optional_space, 0, 1
        )

        final_graph = optional_negative + pos_graph + pynini.closure(graph_per_units, 0, 1)
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
