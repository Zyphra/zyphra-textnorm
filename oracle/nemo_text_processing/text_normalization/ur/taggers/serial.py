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

from nemo_text_processing.text_normalization.ur.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    TO_LOWER,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.ur.utils import get_abs_path


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying serial strings in Urdu.
    Handles Urdu-numeric mixtures, complex delimited number chains,
    symbols, and powers. Digits are ASCII (the wrapper converts Arabic-Indic digits).

        e.g. کووڈ-19  -> tokens { name: "کووڈ-انیس" }
        e.g. 5جی       -> tokens { name: "پانچ جی" }
        e.g. 2^2       -> tokens { name: "دو کا مربع" }
        e.g. 2^4       -> tokens { name: "دو کی طاقت چار" }
        e.g. 1-800-555 -> tokens { name: "ایک-آٹھ سو-پانچ سو پچپن" }
        e.g. B-60      -> tokens { name: "بی-ساٹھ" }
        e.g. A12       -> tokens { name: "اے بارہ" }
        e.g. FY2024    -> tokens { name: "ایف وائی دو صفر دو چار" }
    """

    def __init__(
        self,
        cardinal: GraphFst,
        deterministic: bool = True,
    ):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)

        digit_graph = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        zero_graph = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))

        urdu_digits = pynini.project(
            pynini.union(digit_graph, zero_graph),
            "input",
        ).optimize()

        any_digit = pynini.union(NEMO_DIGIT, urdu_digits).optimize()

        # Fetch centralized 1-3 vs 4+ digit logic from cardinal
        num_graph = cardinal.code_num_graph

        symbols_graph = pynini.string_file(get_abs_path("data/serial/special_symbols.tsv")).optimize()

        urdu_chars = pynini.string_file(get_abs_path("data/serial/chars.tsv")).optimize()

        letter_graph = pynini.string_file(get_abs_path("data/address/letters.tsv"))
        letter_graph = (letter_graph | pynini.compose(TO_LOWER, letter_graph)).optimize()
        latin_letters = letter_graph + pynini.closure(pynutil.insert(" ") + letter_graph)
        latin_letters = latin_letters.optimize()

        urdu_word = pynini.closure(urdu_chars, 2).optimize()

        delimiter = (pynini.accep("-") | pynini.accep("/") | pynini.accep(" ")).optimize()

        alphas = (latin_letters | urdu_word).optimize()
        segment = (alphas | num_graph | symbols_graph).optimize()

        serial_core = segment + pynini.closure(delimiter + segment, 1)
        serial_core = serial_core.optimize()

        serial_graph = serial_core

        all_alphas = pynini.union(NEMO_ALPHA, urdu_chars).optimize()

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

        neg_num_graph = pynini.cross("-", "منفی ") + num_graph
        power_generic = pynutil.add_weight(
            (pynutil.delete("^") + pynutil.insert(" کی طاقت ") + (num_graph | neg_num_graph)), 1.0
        ).optimize()

        power_suffix = pynini.union(power_special, power_generic).optimize()
        var_base = (num_graph | letter_graph).optimize()
        power_graph = var_base + power_suffix

        # Dotted software version numbers: "v2.0", "17.4.1", "v1.2.3"
        ver_seg = num_graph | (zero_graph + pynini.closure(pynutil.insert(" ") + (digit_graph | zero_graph), 1))
        v_prefix_ver = (
            pynini.cross(pynini.union("v", "V"), "وی ")
            + ver_seg
            + pynini.closure(pynini.cross(".", " اعشاریہ ") + ver_seg, 1, 4)
        ).optimize()
        multi_dot_ver = (ver_seg + pynini.closure(pynini.cross(".", " اعشاریہ ") + ver_seg, 2, 4)).optimize()

        serial_graph = pynini.union(serial_graph, power_graph, v_prefix_ver, multi_dot_ver).optimize()
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
        date_suffixes = pynini.project(
            pynini.string_file(get_abs_path("data/date/suffixes.tsv")),
            "input",
        ).optimize()
        date_pattern = (
            pynini.closure(any_digit, 1)
            + pynini.closure(pynini.accep("-") + pynini.closure(any_digit, 1), 0)
            + pynini.accep(" ")
            + pynini.union(date_year_suffix, date_suffixes)
        )

        # DD/MM/YYYY and DD.MM.YYYY belong to the date tagger.
        numeric_date = pynini.union(
            *[
                pynini.closure(any_digit, 1, 2) + sep + pynini.closure(any_digit, 1, 2) + sep + any_digit**4
                for sep in ("/", ".", "-")
            ]
        )

        # A number glued to a measure unit ("5kg", "2.5km") belongs to the measure tagger.
        unit_inputs = pynini.project(pynini.string_file(get_abs_path("data/measure/unit.tsv")), "input")
        num_part = (
            pynini.closure(any_digit, 1)
            + pynini.closure(pynini.accep(",") + pynini.closure(any_digit, 2, 3))
            + pynini.closure(pynini.accep(".") + pynini.closure(any_digit, 1), 0, 1)
        )
        number_unit = (
            num_part
            + pynini.closure(pynini.union("-", "–") + num_part, 0, 1)
            + pynini.closure(pynini.accep(" "), 0, 1)
            + unit_inputs
        )

        # A currency symbol/code glued or spaced with a number ("USD100", "CA$50", "$50k", "$15/h") belongs to money.
        currency_inputs = pynini.project(pynini.string_file(get_abs_path("data/money/currency.tsv")), "input")
        money_mag = pynini.closure(pynini.union("k", "K", "M", "m", "B", "b", "T"), 0, 1)
        money_per = pynini.closure(pynini.accep("/") + pynini.closure(NEMO_ALPHA | pynini.union("²", "³"), 1), 0, 1)
        money_pattern = (
            pynini.closure("-", 0, 1)
            + (
                (currency_inputs + pynini.closure(" ", 0, 1) + num_part + money_mag + money_per)
                | (num_part + money_mag + pynini.closure(" ", 0, 1) + currency_inputs + money_per)
            )
        )

        # International decades ("1990s", "2020s") belong to date.
        decade_pattern = pynini.union("1", "2") + (any_digit**2) + "0" + pynini.union("s", "'s", "’s")

        # Trunk-prefixed phone numbers ("0300-1234567", "0423-5761234") belong to the telephone tagger.
        phone_number = pynini.accep("0") + any_digit**3 + pynini.accep("-") + pynini.closure(any_digit, 7, 8)

        # IPv4 addresses ("192.168.1.1") belong to electronic.
        ipv4_pattern = (
            pynini.closure(any_digit, 1, 3)
            + "."
            + pynini.closure(any_digit, 1, 3)
            + "."
            + pynini.closure(any_digit, 1, 3)
            + "."
            + pynini.closure(any_digit, 1, 3)
        )

        exclusions = (
            pure_word_slash
            | pure_latin_word
            | dimension_pattern
            | ordinal_pattern
            | date_pattern
            | numeric_date
            | number_unit
            | money_pattern
            | decade_pattern
            | phone_number
            | ipv4_pattern
        )
        accepted_inputs = pynini.difference(NEMO_SIGMA, exclusions).optimize()
        serial_graph = pynini.compose(accepted_inputs, serial_graph).optimize()

        self.graph = serial_graph.optimize()
        graph = pynutil.insert('name: "') + convert_space(self.graph).optimize() + pynutil.insert('"')
        self.fst = graph.optimize()
