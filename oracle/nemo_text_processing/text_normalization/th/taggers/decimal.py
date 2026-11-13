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
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying decimals in Thai (th).
    Supports:
    - 3.14 -> สามจุดหนึ่งสี่
    - 0.05 -> ศูนย์จุดศูนย์ห้า
    - 12.50 -> สิบสองจุดห้าศูนย์
    - -12.50 / −12.50 -> ลบสิบสองจุดห้าศูนย์
    - Grouped decimals: 1,234.56 -> หนึ่งพันสองร้อยสามสิบสี่จุดห้าหก
    - Native Thai digits: ๓.๑๔ -> สามจุดหนึ่งสี่
    - Decimal ranges: 3.5-4.5 -> สามจุดห้าถึงสี่จุดห้า
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

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
        single_digit = thai_to_ascii | NEMO_DIGIT
        single_digit_words = pynini.string_map(
            [
                ("0", "ศูนย์"),
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
        )
        fractional_digits = pynini.closure(single_digit @ single_digit_words, 1)

        dot = pynini.cross(".", "จุด")
        integer_part = cardinal.all_cardinals

        positive_decimal = (integer_part + dot + fractional_digits).optimize()

        minus = pynini.cross("-", "ลบ") | pynini.cross("−", "ลบ")
        negative_decimal = (minus + positive_decimal).optimize()

        self.decimal_numbers = (negative_decimal | positive_decimal).optimize()
        self.positive_decimal = positive_decimal

        # Decimal ranges: 3.5-4.5 -> สามจุดห้าถึงสี่จุดห้า
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        dash = pynini.union("-", "–", "—", "~", "〜", "～")
        range_op = opt_sp + pynini.cross(dash, "ถึง") + opt_sp
        self.range = (positive_decimal + range_op + positive_decimal).optimize()

        graph = pynutil.add_weight(self.range, 1.05) | pynutil.add_weight(self.decimal_numbers, 1.1)
        self.fst = (
            pynutil.insert('name: "')
            + convert_space(graph)
            + pynutil.insert('"')
        ).optimize()
