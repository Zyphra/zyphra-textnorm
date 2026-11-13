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


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Roman numerals in contextual positions for Thai (th).
    Supports:
    - Chapter IV -> บทที่สี่
    - Part II -> ภาคที่สอง
    - Louis XIV -> หลุยส์ที่สิบสี่
    - Elizabeth II -> เอลิซาเบธที่สอง
    - Rama IX -> รัชกาลที่เก้า
    - century XXI / Century XXI / ศตวรรษที่ XXI -> ศตวรรษที่ยี่สิบเอ็ด
    Safety controls:
    - Isolated labels like XL, MIX, CD, Section C are NOT converted.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_to_words = pynini.string_map(
            [
                ("I", "หนึ่ง"),
                ("II", "สอง"),
                ("III", "สาม"),
                ("IV", "สี่"),
                ("V", "ห้า"),
                ("VI", "หก"),
                ("VII", "เจ็ด"),
                ("VIII", "แปด"),
                ("IX", "เก้า"),
                ("X", "สิบ"),
                ("XI", "สิบเอ็ด"),
                ("XII", "สิบสอง"),
                ("XIII", "สิบสาม"),
                ("XIV", "สิบสี่"),
                ("XV", "สิบห้า"),
                ("XVI", "สิบหก"),
                ("XVII", "สิบเจ็ด"),
                ("XVIII", "สิบแปด"),
                ("XIX", "สิบเก้า"),
                ("XX", "ยี่สิบ"),
                ("XXI", "ยี่สิบเอ็ด"),
                ("XXII", "ยี่สิบสอง"),
            ]
        )

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Chapter / Part / Volume
        chapter = (
            pynini.cross("Chapter ", "บทที่")
            | pynini.cross("chapter ", "บทที่")
            | pynini.cross("Chapter", "บทที่")
            | pynini.cross("chapter", "บทที่")
            | pynini.cross("บทที่ ", "บทที่")
            | pynini.cross("บทที่", "บทที่")
        )
        part = (
            pynini.cross("Part ", "ภาคที่")
            | pynini.cross("part ", "ภาคที่")
            | pynini.cross("Part", "ภาคที่")
            | pynini.cross("part", "ภาคที่")
            | pynini.cross("ภาคที่ ", "ภาคที่")
            | pynini.cross("ภาคที่", "ภาคที่")
        )
        volume = (
            pynini.cross("Vol. ", "เล่มที่")
            | pynini.cross("vol. ", "เล่มที่")
            | pynini.cross("Vol.", "เล่มที่")
            | pynini.cross("vol.", "เล่มที่")
            | pynini.cross("เล่มที่ ", "เล่มที่")
            | pynini.cross("เล่มที่", "เล่มที่")
        )
        # Monarchs
        monarch = (
            pynini.cross("Louis ", "หลุยส์ที่")
            | pynini.cross("Elizabeth ", "เอลิซาเบธที่")
            | pynini.cross("Rama ", "รัชกาลที่")
            | pynini.cross("Henry ", "เฮนรีที่")
            | pynini.cross("George ", "จอร์จที่")
            | pynini.cross("Charles ", "ชาร์ลส์ที่")
            | pynini.cross("รัชกาลที่ ", "รัชกาลที่")
            | pynini.cross("รัชกาลที่", "รัชกาลที่")
        )

        # Century
        century = (
            pynini.cross("century ", "ศตวรรษที่")
            | pynini.cross("Century ", "ศตวรรษที่")
            | pynini.cross("ศตวรรษที่ ", "ศตวรรษที่")
            | pynini.cross("ศตวรรษที่", "ศตวรรษที่")
        )

        contextual_prefixes = chapter | part | volume | monarch | century
        graph = (contextual_prefixes + opt_sp + roman_to_words).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(graph)
            + pynutil.insert('"')
        ).optimize()
