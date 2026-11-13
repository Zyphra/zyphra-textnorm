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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_KN_CHAR,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    TO_LOWER,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying serial strings in Kannada text.
    Handles letter-number mixtures, delimited number chains, symbols and powers.
    Supports both ASCII (0-9) and Kannada (೦-೯) digits.

        e.g. ಕೋವಿಡ್-19  -> tokens { name: "ಕೋವಿಡ್-ಹತ್ತೊಂಬತ್ತು" }
        e.g. 5ಜಿ       -> tokens { name: "ಐದು ಜಿ" }
        e.g. 2^3       -> tokens { name: "ಎರಡು ಟು ದಿ ಪವರ್ ಮೂರು" }
        e.g. x^2       -> tokens { name: "ಎಕ್ಸ್ ವರ್ಗ" }
        e.g. B-60      -> tokens { name: "ಬಿ-ಅರವತ್ತು" }
        e.g. A12       -> tokens { name: "ಎ ಹನ್ನೆರಡು" }
        e.g. FY2024    -> tokens { name: "ಎಫ್ ವೈ ಎರಡು ಸೊನ್ನೆ ಎರಡು ನಾಲ್ಕು" }
    """

    def __init__(
        self,
        cardinal: GraphFst,
        deterministic: bool = True,
    ):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)

        digit_graph = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        zero_graph = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))

        kn_digits = pynini.project(
            pynini.union(digit_graph, zero_graph),
            "input",
        ).optimize()

        any_digit = pynini.union(NEMO_DIGIT, kn_digits).optimize()

        # Fetch centralized 1-3 vs 4+ digit logic from cardinal
        num_graph = cardinal.code_num_graph

        symbols_graph = pynini.string_file(get_abs_path("data/serial/special_symbols.tsv")).optimize()

        kn_chars = pynini.string_file(get_abs_path("data/serial/chars.tsv")).optimize()

        letter_graph = pynini.string_file(get_abs_path("data/address/letters.tsv"))
        letter_graph = (letter_graph | pynini.compose(TO_LOWER, letter_graph)).optimize()
        latin_letters = letter_graph + pynini.closure(pynutil.insert(" ") + letter_graph)
        latin_letters = latin_letters.optimize()

        kn_word = pynini.closure(NEMO_KN_CHAR, 1).optimize()

        delimiter = (pynini.accep("-") | pynini.accep("/") | pynini.accep(" ")).optimize()

        alphas = (latin_letters | kn_word).optimize()
        segment = (alphas | num_graph | symbols_graph).optimize()

        serial_core = segment + pynini.closure(delimiter + segment, 1)
        serial_core = serial_core.optimize()

        serial_graph = serial_core

        all_alphas = pynini.union(NEMO_ALPHA, NEMO_KN_CHAR, pynini.project(kn_chars, "input")).optimize()

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

        # Power reading
        power_exp = pynini.closure(pynini.cross(pynini.union("-", "−"), "ಋಣ "), 0, 1) + (num_graph | letter_graph)
        power_suffix = pynutil.add_weight(
            pynutil.delete("^") + pynutil.insert(" ಟು ದಿ ಪವರ್ ") + power_exp, 1.0
        ).optimize()
        numeric_power = num_graph + power_suffix
        variable_power = latin_letters + (
            pynutil.add_weight(
                pynini.cross("^2", " ವರ್ಗ") | pynini.cross("^3", " ಘನ"), -0.01
            )
            | pynini.cross("^", " ರ ") + power_exp + pynutil.insert(" ಘಾತ")
        )
        serial_graph = pynini.union(serial_graph, numeric_power, variable_power).optimize()

        # Dotted multi-part version numbers: "17.4.1", "v1.2.3", "3.11.2"
        ver_part = cardinal.graph_without_leading_zeros
        version_core = ver_part + pynini.closure(pynini.cross(".", " ಡಾಟ್ ") + ver_part, 2)
        version_prefixed = (
            pynini.compose(pynini.union("v", "V"), letter_graph)
            + pynutil.insert(" ")
            + ver_part
            + pynini.closure(pynini.cross(".", " ಡಾಟ್ ") + ver_part, 1)
        )
        version_graph = pynutil.add_weight((version_core | version_prefixed).optimize(), -0.05)
        serial_graph = pynini.union(serial_graph, version_graph).optimize()

        serial_graph = pynini.compose(pynini.closure(NEMO_NOT_SPACE, 2), serial_graph).optimize()

        pure_word_slash = pynini.closure(NEMO_ALPHA, 1) + pynini.accep("/") + pynini.closure(NEMO_ALPHA, 1)

        letter_join_char = NEMO_ALPHA | pynini.accep("-") | pynini.accep("/")
        contains_latin_letter = pynini.closure(letter_join_char) + NEMO_ALPHA + pynini.closure(letter_join_char)
        pure_latin_word = pynini.intersect(pynini.closure(letter_join_char, 1), contains_latin_letter).optimize()

        dimension_pattern = (
            pynini.closure(any_digit, 1) + (pynini.accep("x") | pynini.accep("X")) + pynini.closure(any_digit, 1)
        )

        ordinal_suffixes = pynini.project(
            pynini.string_file(get_abs_path("data/ordinal/suffixes.tsv")),
            "input",
        ).optimize()
        ordinal_pattern = pynini.closure(any_digit, 1) + ordinal_suffixes

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
        measure_units = pynini.project(
            pynini.union(
                pynini.string_file(get_abs_path("data/measure/unit_other.tsv")),
                pynini.string_file(get_abs_path("data/measure/unit_prefixed_other.tsv")),
            ),
            "input",
        ).optimize()
        measure_pattern = (
            pynini.closure(any_digit, 1)
            + pynini.closure((pynini.accep("-") | pynini.accep("–")) + pynini.closure(any_digit, 1), 0, 1)
            + pynini.closure(pynini.accep(" "), 0, 1)
            + measure_units
        )

        # Exclude 4-digit decades (1990s, 2020s, 1990ರ) and currency codes/symbols
        decade_pattern = (
            pynini.union("1", "2", "೧", "೨")
            + any_digit**2
            + pynini.union("0", "೦")
            + pynini.union("s", "ರ", "ರಲ್ಲಿ")
        )
        currency_syms = pynini.project(
            pynini.string_file(get_abs_path("data/money/currency.tsv")),
            "input",
        ).optimize()
        money_glued_pattern = (
            currency_syms + pynini.closure(any_digit, 1)
            | pynini.closure(any_digit, 1) + currency_syms
        )
        ipv4_pattern = (
            pynini.closure(NEMO_DIGIT, 1, 3)
            + ("." + pynini.closure(NEMO_DIGIT, 1, 3)) ** 3
        )
        date_dot_pattern = (
            pynini.closure(any_digit, 1, 2)
            + "."
            + pynini.closure(any_digit, 1, 2)
            + "."
            + any_digit**4
        )

        exclusions = (
            pure_word_slash
            | pure_latin_word
            | dimension_pattern
            | ordinal_pattern
            | date_pattern
            | measure_pattern
            | decade_pattern
            | money_glued_pattern
            | ipv4_pattern
            | date_dot_pattern
        )
        accepted_inputs = pynini.difference(NEMO_SIGMA, exclusions).optimize()

        serial_graph = pynini.compose(accepted_inputs, serial_graph).optimize()

        self.graph = serial_graph.optimize()
        graph = pynutil.insert('name: "') + convert_space(self.graph).optimize() + pynutil.insert('"')
        self.fst = graph.optimize()
