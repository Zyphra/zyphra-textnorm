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

from nemo_text_processing.text_normalization.pa.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    TO_LOWER,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.pa.utils import get_abs_path


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying serial strings in Punjabi.
    Handles Punjabi-numeric mixtures, complex delimited number chains,
    symbols, and powers. Supports both ASCII (0-9) and Gurmukhi (੦-੯) digits.

        e.g. ਕੋਵਿਡ-19  -> tokens { name: "ਕੋਵਿਡ-ਉੱਨੀ" }
        e.g. 5ਜੀ       -> tokens { name: "ਪੰਜ ਜੀ" }
        e.g. 2^2       -> tokens { name: "ਦੋ ਸਕੇਅਰ" }
        e.g. 2^4       -> tokens { name: "ਦੋ ਦੀ ਘਾਤ ਚਾਰ" }
        e.g. B-60      -> tokens { name: "ਬੀ-ਸੱਠ" }
        e.g. A12       -> tokens { name: "ਏ ਬਾਰਾਂ" }
        e.g. FY2024    -> tokens { name: "ਐੱਫ ਵਾਈ ਦੋ ਸਿਫ਼ਰ ਦੋ ਚਾਰ" }
    """

    def __init__(
        self,
        cardinal: GraphFst,
        deterministic: bool = True,
    ):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)

        digit_graph = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        zero_graph = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))

        punjabi_digits = pynini.project(
            pynini.union(digit_graph, zero_graph),
            "input",
        ).optimize()

        any_digit = pynini.union(NEMO_DIGIT, punjabi_digits).optimize()

        num_graph = cardinal.code_num_graph

        symbols_graph = pynini.string_file(get_abs_path("data/serial/special_symbols.tsv")).optimize()

        punjabi_chars = pynini.string_file(get_abs_path("data/serial/chars.tsv")).optimize()

        letter_graph = pynini.string_file(get_abs_path("data/address/letters.tsv"))
        letter_graph = (letter_graph | pynini.compose(TO_LOWER, letter_graph)).optimize()
        latin_letters = letter_graph + pynini.closure(pynutil.insert(" ") + letter_graph)
        latin_letters = latin_letters.optimize()

        punjabi_word = pynini.closure(punjabi_chars, 2).optimize()

        delimiter = (pynini.accep("-") | pynini.accep("/") | pynini.accep(" ")).optimize()

        alphas = (latin_letters | punjabi_word).optimize()
        segment = (alphas | num_graph | symbols_graph).optimize()

        serial_core = segment + pynini.closure(delimiter + segment, 1)
        serial_core = serial_core.optimize()

        serial_graph = serial_core

        all_alphas = pynini.union(NEMO_ALPHA, punjabi_chars).optimize()

        insert_space_alpha_digit = pynini.cdrewrite(pynutil.insert(" "), all_alphas, any_digit, NEMO_SIGMA)
        insert_space_digit_alpha = pynini.cdrewrite(pynutil.insert(" "), any_digit, all_alphas, NEMO_SIGMA)
        space_inserter = pynini.compose(insert_space_alpha_digit, insert_space_digit_alpha).optimize()

        glued_serial = pynini.compose(space_inserter, serial_core).optimize()
        serial_graph = pynini.union(serial_graph, glued_serial).optimize()

        # Reusable mixed alphanumeric-code graph
        code_join_char = pynini.union(all_alphas, any_digit, pynini.accep("-"), pynini.accep("/"))
        has_letter = pynini.closure(code_join_char) + all_alphas + pynini.closure(code_join_char)
        has_digit = pynini.closure(code_join_char) + any_digit + pynini.closure(code_join_char)
        mixed_code_only = pynini.intersect(
            pynini.intersect(pynini.closure(code_join_char, 1), has_letter), has_digit
        ).optimize()

        self.mixed_alphanum_graph = pynini.compose(mixed_code_only, serial_graph).optimize()

        power_special = pynutil.add_weight(
            pynini.string_file(get_abs_path("data/serial/power_special.tsv")), -1.0
        ).optimize()

        power_generic = pynutil.add_weight(
            (pynutil.delete("^") + pynutil.insert(" ਦੀ ਘਾਤ ") + num_graph), 1.0
        ).optimize()

        power_suffix = pynini.union(power_special, power_generic).optimize()
        power_graph = (num_graph | letter_graph) + power_suffix
        serial_graph = pynini.union(serial_graph, power_graph).optimize()

        serial_graph = pynini.compose(pynini.closure(NEMO_NOT_SPACE, 2), serial_graph).optimize()

        pure_word_slash = pynini.closure(NEMO_ALPHA, 1) + pynini.accep("/") + pynini.closure(NEMO_ALPHA, 1)

        letter_join_char = NEMO_ALPHA | pynini.accep("-") | pynini.accep("/")
        contains_latin_letter = pynini.closure(letter_join_char) + NEMO_ALPHA + pynini.closure(letter_join_char)
        pure_latin_word = pynini.intersect(pynini.closure(letter_join_char, 1), contains_latin_letter).optimize()

        dimension_pattern = (
            pynini.closure(any_digit, 1) + (pynini.accep("x") | pynini.accep("X")) + pynini.closure(any_digit, 1)
        )

        ordinal_suffixes = pynini.project(
            pynini.string_file(get_abs_path("data/ordinal/suffixes.tsv")), "input"
        ).optimize()
        ordinal_exceptions = pynini.project(
            pynini.union(
                pynini.string_file(get_abs_path("data/ordinal/exceptions.tsv")),
                pynini.string_file(get_abs_path("data/date/day_ordinal.tsv")),
            ),
            "input",
        ).optimize()
        classifiers = pynini.project(
            pynini.string_file(get_abs_path("data/numbers/classifiers.tsv")), "input"
        ).optimize()
        ordinal_pattern = (pynini.closure(any_digit, 1) + (ordinal_suffixes | classifiers)) | ordinal_exceptions

        date_year_suffix = pynini.project(
            pynini.string_file(get_abs_path("data/date/year_suffix.tsv")),
            "input",
        ).optimize()
        date_pattern = (
            pynini.closure(any_digit, 1)
            + pynini.closure(pynini.accep("-") + pynini.closure(any_digit, 1), 0)
            + pynini.accep(" ")
            + date_year_suffix
        )
        year_digit_4 = pynini.union("1", "2", "੧", "੨") + any_digit + any_digit + any_digit
        year_range_pattern = year_digit_4 + pynini.union("-", "–") + year_digit_4
        iso_date_pattern = (
            year_digit_4
            + pynini.union("-", "/")
            + pynini.closure(any_digit, 1, 2)
            + pynini.union("-", "/")
            + pynini.closure(any_digit, 1, 2)
        )
        numeric_dmy = (
            pynini.closure(any_digit, 1, 2) + pynini.union("-", "/", ".")
            + pynini.closure(any_digit, 1, 2) + pynini.union("-", "/", ".") + year_digit_4
        )

        units = pynini.project(pynini.string_file(get_abs_path("data/measure/unit.tsv")), "input").optimize()
        num_part = (
            pynini.closure(any_digit, 1)
            + pynini.closure(pynini.accep(",") + pynini.closure(any_digit, 2, 3))
            + pynini.closure(pynini.accep(".") + pynini.closure(any_digit, 1), 0, 1)
        )
        measure_pattern = (
            num_part
            + pynini.closure(pynini.union("-", "–") + num_part, 0, 1)
            + pynini.closure(pynini.accep(" "), 0, 1)
            + units
        )
        exclusions = (
            pure_word_slash
            | pure_latin_word
            | dimension_pattern
            | ordinal_pattern
            | date_pattern
            | year_range_pattern
            | iso_date_pattern
            | numeric_dmy
            | measure_pattern
        )
        accepted_inputs = pynini.difference(NEMO_SIGMA, exclusions).optimize()

        serial_graph = pynini.compose(accepted_inputs, serial_graph).optimize()

        version_component = cardinal.final_graph
        version_dot = pynini.cross(".", " ਡਾਟ ")
        version_graph = (
            (pynini.union("v", "V") @ letter_graph)
            + pynutil.insert(" ")
            + version_component
            + pynini.closure(version_dot + version_component, 1)
        ) | (
            version_component + version_dot + version_component + version_dot + version_component
        )
        serial_graph |= version_graph

        self.graph = serial_graph.optimize()
        graph = pynutil.insert('name: "') + convert_space(self.graph).optimize() + pynutil.insert('"')
        self.fst = graph.optimize()
