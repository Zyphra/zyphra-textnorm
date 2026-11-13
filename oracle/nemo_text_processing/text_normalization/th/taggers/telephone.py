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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone_token
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying telephone numbers in Thai (th).
    Supports:
    - 081-234-5678 -> ศูนย์แปดหนึ่ง สองสามสี่ ห้าหกเจ็ดแปด
    - 02-123-4567 -> ศูนย์สอง หนึ่งสองสาม สี่ห้าหกเจ็ด
    - +66 2 123 4567 -> บวกหกสิบหก สอง หนึ่งสองสาม สี่ห้าหกเจ็ด
    - 138-1234-5678 -> หนึ่งสามแปด หนึ่งสองสามสี่ ห้าหกเจ็ดแปด
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

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
        digit_words = pynini.string_map(
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
        digit = single_digit @ digit_words
        sep = pynini.cross("-", " ") | pynini.cross(" ", " ")

        # 3-3-4 pattern: 081-234-5678 or 081 234 5678
        p_3_3_4 = digit**3 + sep + digit**3 + sep + digit**4

        # 2-3-4 pattern: 02-123-4567 or 02 123 4567
        p_2_3_4 = digit**2 + sep + digit**3 + sep + digit**4

        # 3-4-4 pattern: 138-1234-5678
        p_3_4_4 = digit**3 + sep + digit**4 + sep + digit**4

        # 3-8 pattern: 010-12345678
        p_3_8 = digit**3 + sep + digit**8

        # International prefix: +66 2 123 4567 or +66 81 234 5678
        intl_prefix = pynini.cross("+", "บวก") + (digit**2 @ (cardinal.all_cardinals)) + sep
        intl_phone = intl_prefix + (p_2_3_4 | p_3_3_4 | (digit**1 + sep + digit**3 + sep + digit**4))

        all_phone = (intl_phone | p_3_3_4 | p_2_3_4 | p_3_4_4 | p_3_8).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_phone)
            + pynutil.insert('"')
        ).optimize()
        self.fst = (self.fst | international_telephone_token(digit, "บวก")).optimize()
