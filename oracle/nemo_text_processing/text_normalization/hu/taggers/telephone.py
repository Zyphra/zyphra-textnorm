# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
# Copyright (c) 2023, Jim O'Regan for Språkbanken Tal
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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    NEMO_SPACE,
    GraphFst,
    delete_extra_space,
    insert_space,
)
from nemo_text_processing.text_normalization.hu.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.hu.utils import get_abs_path


class TelephoneFst(GraphFst):
    """
    tel: + (36) 1 441-4000
    Finite state transducer for classifying telephone numbers, e.g.
        + (36) 1 441-4000 -> { number_part: "plusz harminchat egy négyszáznegyvenegy négyezer" }.

    Hungarian numbers are written in the following formats:
        06 1 XXX XXXX
        06 AA XXX-XXX
        06 AA XXX-XXXX (mobile phones)

    See:
        https://en.wikipedia.org/wiki/Telephone_numbers_in_Hungary

    Args:
                deterministic: if True will provide a single transduction option,
                        for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)
        cardinal = CardinalFst(deterministic)
        area_codes = pynini.string_file(get_abs_path("data/telephone/area_codes.tsv")) @ cardinal.graph
        self.area_codes = area_codes
        country_codes = pynini.string_file(get_abs_path("data/telephone/country_codes.tsv")) @ cardinal.graph
        self.country_codes = country_codes.optimize()

        digit = cardinal.digit
        two_digits = cardinal.two_digits_read
        three_digits = cardinal.three_digits_read
        four_digits = cardinal.four_digits_read
        up_to_three_digits = digit | two_digits | three_digits
        up_to_four_digits = up_to_three_digits | four_digits

        separators = pynini.union(NEMO_SPACE, pynini.cross("-", " "))
        area_separators = pynini.union(separators, pynini.cross("/", " "))

        zero = pynini.cross("0", "nulla")
        digit |= zero

        special_numbers = pynini.string_file(get_abs_path("data/telephone/special_numbers.tsv"))
        special_numbers @= cardinal.three_digits_read

        passable = pynini.union(":", ": ", " ")
        prompt_pass = pynini.closure(pynutil.delete(passable) + insert_space, 0, 1)
        telephone_abbr = pynini.string_file(get_abs_path("data/telephone/telephone_abbr.tsv"))
        telephone_abbr = telephone_abbr + prompt_pass
        telephone_prompt = pynini.string_file(get_abs_path("data/telephone/telephone_prompt.tsv"))
        prompt_as_code = pynutil.insert("country_code: \"") + telephone_prompt + pynutil.insert("\"")
        prompt_as_code |= pynutil.insert("country_code: \"") + telephone_abbr + pynutil.insert("\"")
        prompt_as_code |= (
            pynutil.insert("country_code: \"") + telephone_prompt + NEMO_SPACE + telephone_abbr + pynutil.insert("\"")
        )
        prompt_inner = telephone_prompt | telephone_abbr
        prompt_inner |= telephone_prompt + NEMO_SPACE + telephone_abbr

        plus = pynini.cross("+", "plusz ")
        plus |= pynini.cross("00", "nulla nulla ")
        plus = plus + pynini.closure(pynutil.delete(" "), 0, 1)

        known_country = (
            plus
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynini.closure(pynutil.delete("("), 0, 1)
            + country_codes
            + pynini.closure(pynutil.delete(")"), 0, 1)
        )
        known_country_code = pynutil.insert("country_code: \"") + known_country + pynutil.insert("\"")
        known_country_code |= prompt_as_code
        known_country_code |= (
            pynutil.insert("country_code: \"") + prompt_inner + NEMO_SPACE + known_country + pynutil.insert("\"")
        )

        generic_cc = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ cardinal.graph
        any_country = (
            plus
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynini.closure(pynutil.delete("("), 0, 1)
            + (pynutil.add_weight(country_codes, -0.05) | generic_cc)
            + pynini.closure(pynutil.delete(")"), 0, 1)
        )
        country_code = pynutil.insert("country_code: \"") + any_country + pynutil.insert("\"")
        country_code |= prompt_as_code
        country_code |= (
            pynutil.insert("country_code: \"") + prompt_inner + NEMO_SPACE + any_country + pynutil.insert("\"")
        )
        trunk = pynini.cross("06", "nulla hat")
        trunk |= pynutil.delete("(") + trunk + pynutil.delete(")")

        area_part = area_codes + area_separators

        base_number_part = pynini.union(
            three_digits + separators + three_digits,
            three_digits + separators + two_digits + separators + two_digits,
            three_digits + separators + four_digits,
            two_digits + separators + four_digits,
            four_digits + separators + three_digits,
            two_digits + separators + two_digits + separators + three_digits,
        )
        number_part = area_part + base_number_part

        self.number_graph = number_part
        number_part = pynutil.insert("number_part: \"") + self.number_graph + pynutil.insert("\"")
        trunk_number_part = (
            pynutil.insert("number_part: \"") + trunk + separators + self.number_graph + pynutil.insert("\"")
        )
        # numbers outside the Hungarian plan, groups read as typed:
        #   +1 555 123 4567 -> plusz egy ötszázötvenöt százhuszonhárom négyezer-ötszázhatvanhét
        #   (021) 555-1234 -> nulla huszonegy ötszázötvenöt ezerkétszázharmincnégy
        foreign_area = (
            pynini.closure(pynutil.delete("("), 0, 1)
            + (((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ up_to_three_digits)
            + pynini.closure(pynutil.delete(")"), 0, 1)
        )
        foreign_groups = (
            base_number_part
            | (four_digits + separators + four_digits)
            | (up_to_four_digits + pynini.closure(separators + up_to_four_digits, 1, 3))
        )
        foreign_two_group = three_digits + separators + four_digits | four_digits + separators + four_digits
        foreign_number_part = (
            pynutil.insert("number_part: \"")
            + ((foreign_area + separators + foreign_groups) | foreign_two_group)
            + pynutil.insert("\"")
        )
        bracketed_area = (
            pynutil.delete("(")
            + (
                (cardinal.zero_space + (((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ up_to_three_digits))
                | (((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 1, 2)) @ up_to_three_digits)
            )
            + pynutil.delete(")")
        )
        bracketed_number_part = (
            pynutil.insert("number_part: \"")
            + bracketed_area
            + (NEMO_SPACE | pynutil.insert(" "))
            + base_number_part
            + pynutil.insert("\"")
        )
        mellek = NEMO_SPACE + pynutil.delete("mellék")
        extension = pynutil.insert("extension: \"") + up_to_four_digits + pynutil.insert("\"")
        extension = pynini.closure(area_separators + extension + mellek, 0, 1)

        special_numbers = pynutil.insert("number_part: \"") + special_numbers + pynutil.insert("\"")
        graph = pynini.union(
            country_code + separators + number_part,
            country_code + separators + number_part + extension,
            number_part + extension,
            trunk_number_part,
            trunk_number_part + extension,
            known_country_code + number_part,
            known_country_code + trunk_number_part,
            known_country_code + trunk_number_part + extension,
            known_country_code + special_numbers,
            known_country_code + number_part + extension,
            country_code + separators + foreign_number_part,
            bracketed_number_part,
        )
        self.tel_graph = graph.optimize()

        # ip
        ip_prompts = pynini.string_file(get_abs_path("data/telephone/ip_prompt.tsv"))
        ip_graph = up_to_three_digits + (pynini.cross(".", " pont ") + up_to_three_digits) ** 3
        graph |= (
            pynini.closure(
                pynutil.insert("country_code: \"") + ip_prompts + pynutil.insert("\"") + delete_extra_space, 0, 1
            )
            + pynutil.insert("number_part: \"")
            + ip_graph.optimize()
            + pynutil.insert("\"")
        )

        final_graph = self.add_tokens(graph)
        self.fst = final_graph.optimize()
