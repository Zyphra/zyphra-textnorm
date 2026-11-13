# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying cardinals in Thai (th).
    Supports:
    - Native Thai digits (๐-๙) and ASCII digits (0-9)
    - Productive numbers up to trillions
    - Special ten/one forms (11: สิบเอ็ด, 20: ยี่สิบ, 21: ยี่สิบเอ็ด, 101: หนึ่งร้อยเอ็ด, etc.)
    - Comma-separated groups (1,234 -> หนึ่งพันสองร้อยสามสิบสี่)
    - Negative numbers with "-" and "−" (U+2212) -> "ลบ"
    - Leading zeros and serial digit strings (0042 -> ศูนย์ศูนย์สี่สอง)
    - Ranges (5-10, 10–20, 1990–1995 -> ห้าถึงสิบ)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        # Thai native digits to ASCII digits
        thai_to_ascii = pynini.string_map(
            [
                ("๐", "0"),
                ("๑", "1"),
                ("๒", "2"),
                ("๓", "3"),
                ("๔", "4"),
                ("๕", "5"),
                ("๖", "6"),
                ("๗", "7"),
                ("๘", "8"),
                ("๙", "9"),
            ]
        )
        self.digit_map = thai_to_ascii | NEMO_DIGIT
        # Preprocessor to turn Thai digits and grouped commas into plain ASCII digits
        del_comma = pynutil.delete(",")
        digit_or_comma = thai_to_ascii | NEMO_DIGIT | del_comma
        self.prefilter = (thai_to_ascii | NEMO_DIGIT) + pynini.closure(digit_or_comma)

        # Single digits
        zero = pynini.cross("0", "ศูนย์")
        units_data = [
            ("1", "หนึ่ง"),
            ("2", "สอง"),
            ("3", "สาม"),
            ("4", "สี่"),
            ("5", "ห้า"),
            ("6", "หก"),
            ("7", "เจ็ด"),
            ("8", "แปด"),
            ("9", "เก้า"),
        ]
        units = pynini.string_map(units_data)
        units_2_to_9 = pynini.string_map(units_data[1:])
        alt_units = pynini.cross("1", "เอ็ด") | units_2_to_9

        # Tens (10 to 99)
        teens = pynini.cross("10", "สิบ") | (pynutil.delete("1") + pynutil.insert("สิบ") + alt_units)
        twenties = pynini.cross("20", "ยี่สิบ") | (pynutil.delete("2") + pynutil.insert("ยี่สิบ") + alt_units)
        ties = pynini.string_map(
            [
                ("3", "สามสิบ"),
                ("4", "สี่สิบ"),
                ("5", "ห้าสิบ"),
                ("6", "หกสิบ"),
                ("7", "เจ็ดสิบ"),
                ("8", "แปดสิบ"),
                ("9", "เก้าสิบ"),
            ]
        )
        other_tens = (ties + pynutil.delete("0")) | (ties + alt_units)
        tens = teens | twenties | other_tens

        up_to_99 = units | tens

        # Hundreds (100 to 999)
        rem_hundreds = (
            pynutil.delete("00")
            | (pynutil.delete("0") + pynini.cross("1", "เอ็ด"))
            | (pynutil.delete("0") + units_2_to_9)
            | tens
        )
        hundreds = units + pynutil.insert("ร้อย") + rem_hundreds

        up_to_999 = up_to_99 | hundreds

        # Thousands (1,000 to 9,999)
        rem_thousands = (
            pynutil.delete("000")
            | (pynutil.delete("00") + pynini.cross("1", "เอ็ด"))
            | (pynutil.delete("00") + units_2_to_9)
            | (pynutil.delete("0") + tens)
            | hundreds
        )
        thousands = units + pynutil.insert("พัน") + rem_thousands

        up_to_9999 = up_to_999 | thousands

        # Ten-thousands (10,000 to 99,999, หมื่น)
        rem_ten_thousands = (
            pynutil.delete("0000")
            | (pynutil.delete("000") + pynini.cross("1", "เอ็ด"))
            | (pynutil.delete("000") + units_2_to_9)
            | (pynutil.delete("00") + tens)
            | (pynutil.delete("0") + hundreds)
            | thousands
        )
        ten_thousands = units + pynutil.insert("หมื่น") + rem_ten_thousands

        up_to_99999 = up_to_9999 | ten_thousands

        # Hundred-thousands (100,000 to 999,999, แสน)
        rem_hundred_thousands = (
            pynutil.delete("00000")
            | (pynutil.delete("0000") + pynini.cross("1", "เอ็ด"))
            | (pynutil.delete("0000") + units_2_to_9)
            | (pynutil.delete("000") + tens)
            | (pynutil.delete("00") + hundreds)
            | (pynutil.delete("0") + thousands)
            | ten_thousands
        )
        hundred_thousands = units + pynutil.insert("แสน") + rem_hundred_thousands

        up_to_999999 = up_to_99999 | hundred_thousands

        # Millions (1,000,000 to 999,999,999,999, ล้าน)
        rem_millions = (
            pynutil.delete("000000")
            | (pynutil.delete("00000") + pynini.cross("1", "เอ็ด"))
            | (pynutil.delete("00000") + units_2_to_9)
            | (pynutil.delete("0000") + tens)
            | (pynutil.delete("000") + hundreds)
            | (pynutil.delete("00") + thousands)
            | (pynutil.delete("0") + ten_thousands)
            | hundred_thousands
        )
        millions = up_to_999999 + pynutil.insert("ล้าน") + rem_millions

        # Trillions (10^12, ล้านล้าน)
        millions_chunk = (
            (pynutil.delete("00000") + units)
            | (pynutil.delete("0000") + tens)
            | (pynutil.delete("000") + hundreds)
            | (pynutil.delete("00") + thousands)
            | (pynutil.delete("0") + ten_thousands)
            | hundred_thousands
        ) + pynutil.insert("ล้าน") + rem_millions

        rem_trillions = (
            pynutil.delete("000000000000")
            | (pynutil.delete("000000") + rem_millions)
            | millions_chunk
        )
        trillions = up_to_999999 + pynutil.insert("ล้านล้าน") + rem_trillions
        positive_integers = up_to_999999 | millions | trillions
        ascii_cardinal = zero | positive_integers

        # Full cardinal numbers graph composing digit and comma preprocessing
        self.all_positive = (self.prefilter @ positive_integers).optimize()
        self.all_cardinals = (self.prefilter @ ascii_cardinal).optimize()
        self.zero = (self.prefilter @ zero).optimize()

        # Negative numbers: -5, −5 -> ลบห้า
        minus = pynini.cross("-", "ลบ") | pynini.cross("−", "ลบ")
        self.negative_cardinal = (minus + self.all_cardinals).optimize()

        # Leading zeros and digit-by-digit serial strings (0042 -> ศูนย์ศูนย์สี่สอง)
        single_digit = thai_to_ascii | NEMO_DIGIT
        single_digit_words = pynini.string_map([("0", "ศูนย์")] + units_data)
        digit_by_digit = single_digit @ single_digit_words
        leading_zero_prefix = (pynini.union("0", "๐") @ pynini.cross("0", "ศูนย์"))
        self.serial_digits = (leading_zero_prefix + pynini.closure(digit_by_digit, 1)).optimize()

        # Numbers for token emission
        self.number = (self.negative_cardinal | self.all_cardinals | self.serial_digits).optimize()

        # Cardinal ranges: 5-10, 10–20, 1990–1995, 3~5 -> ห้าถึงสิบ
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        dash = pynini.union("-", "–", "—", "~", "〜", "～")
        range_op = opt_sp + pynini.cross(dash, "ถึง") + opt_sp
        self.range_graph = (self.all_positive + range_op + self.all_positive).optimize()

        # Composite cardinal graph (ratio heavily weighted so clock 14:30 wins)
        ratio = pynutil.add_weight(self.all_positive + pynini.cross(":", "ต่อ") + self.all_positive, 2.5)
        cardinal_core = (
            pynutil.add_weight(self.range_graph, 1.05)
            | pynutil.add_weight(self.number, 1.1)
            | ratio
        ).optimize()
        self.fst = (
            pynutil.insert('name: "')
            + convert_space(cardinal_core)
            + pynutil.insert('"')
        ).optimize()
