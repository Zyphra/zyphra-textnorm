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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fractions in Thai (th).
    Supports:
    - Unicode vulgar fractions: ½, ¼, ¾, ⅓, ⅔, ⅕, ⅖, ⅗, ⅘, ⅙, ⅚, ⅛, ⅜, ⅝, ⅞, ⅐, ⅑, ⅒
    - Written fractions: 1/2 -> เศษหนึ่งส่วนสอง
    - Mixed fractions: 2½, 2 1/2 -> สองเศษหนึ่งส่วนสอง
    - Negative fractions: -½ -> ลบเศษหนึ่งส่วนสอง, -2½ -> ลบสองเศษหนึ่งส่วนสอง
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        vulgar_fractions = pynini.string_map(
            [
                ("½", "เศษหนึ่งส่วนสอง"),
                ("¼", "เศษหนึ่งส่วนสี่"),
                ("¾", "เศษสามส่วนสี่"),
                ("⅓", "เศษหนึ่งส่วนสาม"),
                ("⅔", "เศษสองส่วนสาม"),
                ("⅕", "เศษหนึ่งส่วนห้า"),
                ("⅖", "เศษสองส่วนห้า"),
                ("⅗", "เศษสามส่วนห้า"),
                ("⅘", "เศษสี่ส่วนห้า"),
                ("⅙", "เศษหนึ่งส่วนหก"),
                ("⅚", "เศษห้าส่วนหก"),
                ("⅛", "เศษหนึ่งส่วนแปด"),
                ("⅜", "เศษสามส่วนแปด"),
                ("⅝", "เศษห้าส่วนแปด"),
                ("⅞", "เศษเจ็ดส่วนแปด"),
                ("⅐", "เศษหนึ่งส่วนเจ็ด"),
                ("⅑", "เศษหนึ่งส่วนเก้า"),
                ("⅒", "เศษหนึ่งส่วนสิบ"),
            ]
        )

        # Slashed fractions: 1/2 -> เศษหนึ่งส่วนสอง
        slash_fraction = (
            pynutil.insert("เศษ")
            + cardinal.all_positive
            + pynini.cross("/", "ส่วน")
            + cardinal.all_positive
        ).optimize()

        pure_fraction = (vulgar_fractions | slash_fraction).optimize()

        # Mixed fractions: 2½, 2 1/2, 3 3/4 -> สองเศษหนึ่งส่วนสอง
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        mixed_vulgar = cardinal.all_positive + opt_sp + vulgar_fractions
        mixed_slash = (
            cardinal.all_positive
            + pynutil.delete(" ")
            + pynutil.insert("เศษ")
            + cardinal.all_positive
            + pynini.cross("/", "ส่วน")
            + cardinal.all_positive
        )
        mixed_fraction = (mixed_vulgar | mixed_slash).optimize()

        all_positive_fractions = (mixed_fraction | pure_fraction).optimize()

        # Negative fractions: -½, −2½ -> ลบเศษหนึ่งส่วนสอง, ลบสองเศษหนึ่งส่วนสอง
        minus = pynini.cross("-", "ลบ") | pynini.cross("−", "ลบ")
        all_fractions = (minus + all_positive_fractions) | all_positive_fractions

        self.fraction_numbers = all_fractions.optimize()
        self.fst = (
            pynutil.insert('name: "')
            + convert_space(self.fraction_numbers)
            + pynutil.insert('"')
        ).optimize()
