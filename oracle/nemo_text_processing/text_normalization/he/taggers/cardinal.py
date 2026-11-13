# Copyright (c) 2026 Zyphra, Inc.
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
    GraphFst,
    convert_space,
    delete_space,
    insert_space,
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew cardinals.
    Abstract numbers in Hebrew are feminine by default (0-9: אפס, אחת, שתיים, שלוש...).
    Masculine forms (אחד, שניים, שלושה...) are provided for counted masculine nouns, dates, etc.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        # 0. Digits Feminine (default)
        digit_f = pynini.string_map([
            ("0", "אפס"),
            ("1", "אחת"),
            ("2", "שתיים"),
            ("3", "שלוש"),
            ("4", "ארבע"),
            ("5", "חמש"),
            ("6", "שש"),
            ("7", "שבע"),
            ("8", "שמונה"),
            ("9", "תשע"),
        ])
        self.digit_f = digit_f

        # Digits Masculine
        digit_m = pynini.string_map([
            ("0", "אפס"),
            ("1", "אחד"),
            ("2", "שניים"),
            ("3", "שלושה"),
            ("4", "ארבעה"),
            ("5", "חמישה"),
            ("6", "שישה"),
            ("7", "שבעה"),
            ("8", "שמונה"),
            ("9", "תשעה"),
        ])
        self.digit_m = digit_m

        # Counted / construct masculine (for 1, 2 before nouns)
        counted_m = pynini.string_map([
            ("1", "אחד"),
            ("2", "שני"),
            ("3", "שלושה"),
            ("4", "ארבעה"),
            ("5", "חמישה"),
            ("6", "שישה"),
            ("7", "שבעה"),
            ("8", "שמונה"),
            ("9", "תשעה"),
        ])
        self.counted_m = counted_m

        unit_non_zero_f = pynini.string_map([
            ("1", "אחת"),
            ("2", "שתיים"),
            ("3", "שלוש"),
            ("4", "ארבע"),
            ("5", "חמש"),
            ("6", "שש"),
            ("7", "שבע"),
            ("8", "שמונה"),
            ("9", "תשע"),
        ])
        self.unit_non_zero_f = unit_non_zero_f

        unit_non_zero_m = pynini.string_map([
            ("1", "אחד"),
            ("2", "שניים"),
            ("3", "שלושה"),
            ("4", "ארבעה"),
            ("5", "חמישה"),
            ("6", "שישה"),
            ("7", "שבעה"),
            ("8", "שמונה"),
            ("9", "תשעה"),
        ])
        self.unit_non_zero_m = unit_non_zero_m

        # 1. Teens 10-19
        teens_f = pynini.string_map([
            ("10", "עשר"),
            ("11", "אחת עשרה"),
            ("12", "שתים עשרה"),
            ("13", "שלוש עשרה"),
            ("14", "ארבע עשרה"),
            ("15", "חמש עשרה"),
            ("16", "שש עשרה"),
            ("17", "שבע עשרה"),
            ("18", "שמונה עשרה"),
            ("19", "תשע עשרה"),
        ])
        self.teens_f = teens_f

        teens_m = pynini.string_map([
            ("10", "עשרה"),
            ("11", "אחד עשר"),
            ("12", "שנים עשר"),
            ("13", "שלושה עשר"),
            ("14", "ארבעה עשר"),
            ("15", "חמישה עשר"),
            ("16", "שישה עשר"),
            ("17", "שבעה עשר"),
            ("18", "שמונה עשר"),
            ("19", "תשעה עשר"),
        ])
        self.teens_m = teens_m

        # 2. Tens 20-90
        tens = pynini.string_map([
            ("2", "עשרים"),
            ("3", "שלושים"),
            ("4", "ארבעים"),
            ("5", "חמישים"),
            ("6", "שישים"),
            ("7", "שבעים"),
            ("8", "שמונים"),
            ("9", "תשעים"),
        ])
        tens_exact = tens + pynutil.delete("0")
        self.tens_exact = tens_exact

        # 21-99
        compound_tens_f = tens + pynutil.insert(" ו") + unit_non_zero_f
        compound_tens_m = tens + pynutil.insert(" ו") + unit_non_zero_m

        self.two_digits_f = (teens_f | tens_exact | compound_tens_f).optimize()
        self.two_digits_m = (teens_m | tens_exact | compound_tens_m).optimize()

        # 1-99
        num_1_99_f = (unit_non_zero_f | self.two_digits_f).optimize()
        num_1_99_m = (unit_non_zero_m | self.two_digits_m).optimize()
        self.num_1_99_f = num_1_99_f
        self.num_1_99_m = num_1_99_m

        # 3. Hundreds 100-900
        hundreds_exact = pynini.string_map([
            ("100", "מאה"),
            ("200", "מאתיים"),
            ("300", "שלוש מאות"),
            ("400", "ארבע מאות"),
            ("500", "חמש מאות"),
            ("600", "שש מאות"),
            ("700", "שבע מאות"),
            ("800", "שמונה מאות"),
            ("900", "תשע מאות"),
        ])
        hundreds_prefix = pynini.string_map([
            ("1", "מאה"),
            ("2", "מאתיים"),
            ("3", "שלוש מאות"),
            ("4", "ארבע מאות"),
            ("5", "חמש מאות"),
            ("6", "שש מאות"),
            ("7", "שבע מאות"),
            ("8", "שמונה מאות"),
            ("9", "תשע מאות"),
        ])

        # Hundreds + 1..99
        hundreds_comp_f = hundreds_prefix + (
            (pynutil.delete("0") + pynutil.insert(" ו") + unit_non_zero_f)
            | (pynutil.insert(" ו") + teens_f)
            | (pynutil.insert(" ו") + tens_exact)
            | (pynutil.insert(" ו") + compound_tens_f)
            | pynutil.add_weight(pynutil.insert(" ") + self.two_digits_f, 0.5)
        )
        hundreds_comp_m = hundreds_prefix + (
            (pynutil.delete("0") + pynutil.insert(" ו") + unit_non_zero_m)
            | (pynutil.insert(" ו") + teens_m)
            | (pynutil.insert(" ו") + tens_exact)
            | (pynutil.insert(" ו") + compound_tens_m)
            | pynutil.add_weight(pynutil.insert(" ") + self.two_digits_m, 0.5)
        )

        num_100_999_f = (hundreds_exact | hundreds_comp_f).optimize()
        num_100_999_m = (hundreds_exact | hundreds_comp_m).optimize()

        num_1_999_f = (num_1_99_f | num_100_999_f).optimize()
        num_1_999_m = (num_1_99_m | num_100_999_m).optimize()
        self.num_1_999_f = num_1_999_f
        self.num_1_999_m = num_1_999_m

        # Leading zeroes deleted for 1-999
        pad_0_f = pynini.closure(pynutil.delete("0"), 1, 2) + num_1_999_f
        pad_0_m = pynini.closure(pynutil.delete("0"), 1, 2) + num_1_999_m
        num_1_999_f_padded = (num_1_999_f | pad_0_f).optimize()
        num_1_999_m_padded = (num_1_999_m | pad_0_m).optimize()

        # 4. Thousands 1,000 - 999,999
        thousands_spec = pynini.string_map([
            ("1", "אלף"),
            ("2", "אלפיים"),
            ("3", "שלושת אלפים"),
            ("4", "ארבעת אלפים"),
            ("5", "חמשת אלפים"),
            ("6", "ששת אלפים"),
            ("7", "שבעת אלפים"),
            ("8", "שמונת אלפים"),
            ("9", "תשעת אלפים"),
            ("10", "עשרת אלפים"),
        ])
        thousands_over_10 = (
            (pynini.difference(NEMO_DIGIT ** 2, "10") @ teens_m)
            | tens_exact
            | compound_tens_m
            | num_100_999_m
        ) + pynutil.insert(" אלף")

        thousands_prefix = (thousands_spec | thousands_over_10).optimize()

        thousands_exact = thousands_prefix + pynutil.delete("000")
        thousands_comp_f = thousands_prefix + (
            (pynutil.delete("00") + pynutil.insert(" ו") + unit_non_zero_f)
            | (pynutil.delete("0") + pynutil.insert(" ו") + teens_f)
            | (pynutil.delete("0") + pynutil.insert(" ו") + tens_exact)
            | (pynutil.delete("0") + pynutil.insert(" ") + compound_tens_f)
            | (pynutil.insert(" ו") + hundreds_exact)
            | (pynutil.insert(" ") + num_100_999_f)
        )
        thousands_comp_m = thousands_prefix + (
            (pynutil.delete("00") + pynutil.insert(" ו") + unit_non_zero_m)
            | (pynutil.delete("0") + pynutil.insert(" ו") + teens_m)
            | (pynutil.delete("0") + pynutil.insert(" ו") + tens_exact)
            | (pynutil.delete("0") + pynutil.insert(" ") + compound_tens_m)
            | (pynutil.insert(" ו") + hundreds_exact)
            | (pynutil.insert(" ") + num_100_999_m)
        )

        num_1k_999k_f = (thousands_exact | thousands_comp_f).optimize()
        num_1k_999k_m = (thousands_exact | thousands_comp_m).optimize()

        num_1_999k_f = (num_1_999_f | num_1k_999k_f).optimize()
        num_1_999k_m = (num_1_999_m | num_1k_999k_m).optimize()

        # 5. Millions 1,000,000 - 999,999,999
        millions_prefix = (
            pynini.cross("1", "מיליון")
            | pynini.cross("2", "שני מיליון")
            | (((pynini.difference(pynini.project(num_1_999_m, "input"), pynini.union("1", "2").optimize()).optimize() @ num_1_999_m)) + pynutil.insert(" מיליון"))
        ).optimize()

        millions_exact = millions_prefix + pynutil.delete("000000")
        millions_comp_f = millions_prefix + (
            (pynutil.delete("00000") + pynutil.insert(" ו") + unit_non_zero_f)
            | (pynutil.delete("0000") + pynutil.insert(" ו") + teens_f)
            | (pynutil.delete("0000") + pynutil.insert(" ו") + tens_exact)
            | (pynutil.delete("0000") + pynutil.insert(" ") + compound_tens_f)
            | (pynutil.delete("000") + pynutil.insert(" ") + num_100_999_f)
            | (pynini.closure(pynutil.delete("0"), 0, 2) + pynutil.insert(" ") + num_1k_999k_f)
        )
        millions_comp_m = millions_prefix + (
            (pynutil.delete("00000") + pynutil.insert(" ו") + unit_non_zero_m)
            | (pynutil.delete("0000") + pynutil.insert(" ו") + teens_m)
            | (pynutil.delete("0000") + pynutil.insert(" ו") + tens_exact)
            | (pynutil.delete("0000") + pynutil.insert(" ") + compound_tens_m)
            | (pynutil.delete("000") + pynutil.insert(" ") + num_100_999_m)
            | (pynini.closure(pynutil.delete("0"), 0, 2) + pynutil.insert(" ") + num_1k_999k_m)
        )

        num_1m_999m_f = (millions_exact | millions_comp_f).optimize()
        num_1m_999m_m = (millions_exact | millions_comp_m).optimize()

        num_1_999m_f = (num_1_999k_f | num_1m_999m_f).optimize()
        num_1_999m_m = (num_1_999k_m | num_1m_999m_m).optimize()

        # 6. Billions 1,000,000,000 - 999,999,999,999
        billions_prefix = (
            pynini.cross("1", "מיליארד")
            | pynini.cross("2", "שני מיליארד")
            | (((pynini.difference(pynini.project(num_1_999_m, "input"), pynini.union("1", "2").optimize()).optimize() @ num_1_999_m)) + pynutil.insert(" מיליארד"))
        ).optimize()

        billions_exact = billions_prefix + pynutil.delete("000000000")
        billions_comp_f = billions_prefix + (
            (pynutil.delete("00000000") + pynutil.insert(" ו") + unit_non_zero_f)
            | (pynutil.delete("0000000") + pynutil.insert(" ו") + teens_f)
            | (pynutil.delete("0000000") + pynutil.insert(" ו") + tens_exact)
            | (pynutil.delete("0000000") + pynutil.insert(" ") + compound_tens_f)
            | (pynutil.delete("000000") + pynutil.insert(" ") + num_100_999_f)
            | (pynini.closure(pynutil.delete("0"), 0, 5) + pynutil.insert(" ") + num_1k_999k_f)
            | (pynini.closure(pynutil.delete("0"), 0, 2) + pynutil.insert(" ") + num_1m_999m_f)
        )
        billions_comp_m = billions_prefix + (
            (pynutil.delete("00000000") + pynutil.insert(" ו") + unit_non_zero_m)
            | (pynutil.delete("0000000") + pynutil.insert(" ו") + teens_m)
            | (pynutil.delete("0000000") + pynutil.insert(" ו") + tens_exact)
            | (pynutil.delete("0000000") + pynutil.insert(" ") + compound_tens_m)
            | (pynutil.delete("000000") + pynutil.insert(" ") + num_100_999_m)
            | (pynini.closure(pynutil.delete("0"), 0, 5) + pynutil.insert(" ") + num_1k_999k_m)
            | (pynini.closure(pynutil.delete("0"), 0, 2) + pynutil.insert(" ") + num_1m_999m_m)
        )

        num_1b_999b_f = (billions_exact | billions_comp_f).optimize()
        num_1b_999b_m = (billions_exact | billions_comp_m).optimize()

        cardinal_f = (pynini.cross("0", "אפס") | num_1_999m_f | num_1b_999b_f).optimize()
        cardinal_m = (pynini.cross("0", "אפס") | num_1_999m_m | num_1b_999b_m).optimize()

        self.cardinal_f = cardinal_f
        self.cardinal_m = cardinal_m

        # Comma thousands grouping (e.g. 1,000, 1,000,000, 1,234)
        comma = pynutil.delete(",")
        num_with_commas = (
            pynini.closure(NEMO_DIGIT, 1, 3)
            + comma
            + pynini.closure(NEMO_DIGIT**3 + comma)
            + NEMO_DIGIT**3
        )
        grouped_cardinal_f = (num_with_commas @ cardinal_f).optimize()
        grouped_cardinal_m = (num_with_commas @ cardinal_m).optimize()

        self.grouped_cardinal_f = grouped_cardinal_f
        self.grouped_cardinal_m = grouped_cardinal_m

        # Leading zeroes (e.g. 007 -> אפס אפס שבע, 01 -> אפס אחת)
        leading_zero_digits = (
            pynini.cross("0", "אפס")
            + pynini.closure(insert_space + pynini.cross("0", "אפס"))
            + insert_space
            + digit_f
            + pynini.closure(insert_space + digit_f)
        ).optimize()
        self.leading_zero_digits = leading_zero_digits

        # Base numbers
        base_num_f = (grouped_cardinal_f | cardinal_f | leading_zero_digits).optimize()
        base_num_m = (grouped_cardinal_m | cardinal_m).optimize()
        self.base_num_f = base_num_f
        self.base_num_m = base_num_m

        # Negative numbers (-12, −7)
        neg_sign = pynini.cross("-", "מינוס ") | pynini.cross("−", "מינוס ")
        negative_num = (neg_sign + base_num_f).optimize()
        self.negative_num = negative_num

        # Numeric ranges: 5-10, 5–10, 2020-2024 -> חמש עד עשר
        dash = pynini.union("-", "–", "—", "־")
        num_range = (base_num_f + pynini.cross(dash, " עד ") + base_num_f).optimize()
        self.num_range = num_range

        # Digit list: 1,2,3 -> אחת, שתיים, שלוש
        digit_list = (
            base_num_f
            + pynini.cross(",", ", ")
            + base_num_f
            + pynini.closure(pynini.cross(",", ", ") + base_num_f)
        ).optimize()
        self.digit_list = digit_list

        all_nums = (
            pynutil.add_weight(negative_num, 0.9)
            | pynutil.add_weight(num_range, 0.95)
            | pynutil.add_weight(digit_list, 1.2)
            | pynutil.add_weight(base_num_f, 1.0)
        ).optimize()
        all_nums |= pynutil.add_weight(self.base_num_f + pynini.cross(":", " ל") + self.base_num_f, 2.0)
        self.all_nums = all_nums

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_nums) + pynutil.insert('"')
        ).optimize()
