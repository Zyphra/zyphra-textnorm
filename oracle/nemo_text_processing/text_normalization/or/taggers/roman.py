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

from ..graph_utils import (
    GraphFst,
    convert_space,
)
from .cardinal import ODIA_CARDINALS_0_TO_99

ROMAN_TO_INT = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
    "XXI": 21, "XXII": 22, "XXIII": 23, "XXIV": 24, "XXV": 25, "XXVI": 26, "XXVII": 27, "XXVIII": 28, "XXIX": 29, "XXX": 30,
    "XL": 40, "L": 50, "LX": 60, "LXX": 70, "LXXX": 80, "XC": 90, "C": 100,
}

ROMAN_MAP = [
    (k, ODIA_CARDINALS_0_TO_99[v]) for k, v in ROMAN_TO_INT.items() if v in ODIA_CARDINALS_0_TO_99
]


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying contextual Roman numerals in Odia:
        ଅଧ୍ୟାୟ IV -> tokens { name: "ଅଧ୍ୟାୟ ଚାରି" }
        ଭାଗ II -> tokens { name: "ଭାଗ ଦୁଇ" }
        Louis XIV -> tokens { name: "Louis ଚଉଦ" }
        XXI ଶତାବ୍ଦୀ -> tokens { name: "ଏକୋଇଶ ଶତାବ୍ଦୀ" }
        XL -> XL (untouched)
        MIX -> MIX (untouched)
        CD -> CD (untouched)
    """

    def __init__(self, cardinal=None, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_numeral = pynini.string_map(ROMAN_MAP).optimize()

        prefix_keys = pynini.union(
            "ଅଧ୍ୟାୟ", "ଭାଗ", "ଖଣ୍ଡ", "ପର୍ବ", "ଶ୍ରେଣୀ", "ଧାରା", "ଅନୁଚ୍ଛେଦ", "ପରିଚ୍ଛେଦ",
            "Chapter", "Part", "Volume", "Section", "Act", "Scene",
            "ଲୁଇ", "Louis", "ହେନରୀ", "Henry", "ଏଡୱାର୍ଡ", "Edward", "ଜର୍ଜ", "George",
            "ଚାର୍ଲ୍ସ", "Charles", "ଏଲିଜାବେଥ", "Elizabeth", "ପୋପ୍", "Pope",
        )

        suffix_keys = pynini.union(
            "ଶତାବ୍ଦୀ", "ଶତାବ୍ଦୀର", "Century", "ଭାଗ", "ଅଧ୍ୟାୟ",
        )

        sep = pynini.union(" ", "-")

        # 1. Prefix key + Roman numeral: e.g. ଅଧ୍ୟାୟ IV -> ଅଧ୍ୟାୟ ଚାରି, Chapter IV -> Chapter ଚାରି
        pre_roman = (
            prefix_keys + sep + roman_numeral
        ).optimize()

        # 2. Roman numeral + suffix key: e.g. XXI ଶତାବ୍ଦୀ -> ଏକୋଇଶ ଶତାବ୍ଦୀ
        suf_roman = (
            roman_numeral + sep + suffix_keys
        ).optimize()

        all_roman = (pre_roman | suf_roman).optimize()
        self.roman_graph = all_roman

        graph = pynutil.insert('name: "') + convert_space(all_roman) + pynutil.insert('"')
        self.fst = graph.optimize()
