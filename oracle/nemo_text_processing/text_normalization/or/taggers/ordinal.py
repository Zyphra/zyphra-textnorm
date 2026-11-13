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
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGITS,
    convert_space,
)
from .cardinal import CardinalFst, ODIA_CARDINALS_0_TO_99

ORDINALS_1_TO_10 = {
    "1": "ପ୍ରଥମ",
    "2": "ଦ୍ୱିତୀୟ",
    "3": "ତୃତୀୟ",
    "4": "ଚତୁର୍ଥ",
    "5": "ପଞ୍ଚମ",
    "6": "ଷଷ୍ଠ",
    "7": "ସପ୍ତମ",
    "8": "ଅଷ୍ଟମ",
    "9": "ନବମ",
    "10": "ଦଶମ",
}


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying ordinals in Odia:
        ୧ମ or 1st -> tokens { name: "ପ୍ରଥମ" }
        ୨ୟ or 2nd -> tokens { name: "ଦ୍ୱିତୀୟ" }
        ୩ୟ or 3rd -> tokens { name: "ତୃତୀୟ" }
        ୪ର୍ଥ or 4th -> tokens { name: "ଚତୁର୍ଥ" }
        ୫ମ or 5th -> tokens { name: "ପଞ୍ଚମ" }
        ୬ଷ୍ଠ or 6th -> tokens { name: "ଷଷ୍ଠ" }
        ୧୧ତମ or 11th -> tokens { name: "ଏଗାରତମ" }
        ୨୧ତମ or 21st -> tokens { name: "ଏକୋଇଶତମ" }
        ୧୦୦ତମ or 100th -> tokens { name: "ଶହେତମ" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        self.cardinal = cardinal

        # 1-10 with native suffixes
        ord_1_to_10_pairs = [
            # 1
            ("1ମ", "ପ୍ରଥମ"), ("୧ମ", "ପ୍ରଥମ"), ("1st", "ପ୍ରଥମ"), ("୧st", "ପ୍ରଥମ"),
            # 2
            ("2ୟ", "ଦ୍ୱିତୀୟ"), ("୨ୟ", "ଦ୍ୱିତୀୟ"), ("2nd", "ଦ୍ୱିତୀୟ"), ("୨nd", "ଦ୍ୱିତୀୟ"),
            # 3
            ("3ୟ", "ତୃତୀୟ"), ("୩ୟ", "ତୃତୀୟ"), ("3rd", "ତୃତୀୟ"), ("୩rd", "ତୃତୀୟ"),
            # 4
            ("4ର୍ଥ", "ଚତୁର୍ଥ"), ("୪ର୍ଥ", "ଚତୁର୍ଥ"), ("4th", "ଚତୁର୍ଥ"), ("୪th", "ଚତୁର୍ଥ"),
            # 5
            ("5ମ", "ପଞ୍ଚମ"), ("୫ମ", "ପଞ୍ଚମ"), ("5th", "ପଞ୍ଚମ"), ("୫th", "ପଞ୍ଚମ"),
            # 6
            ("6ଷ୍ଠ", "ଷଷ୍ଠ"), ("୬ଷ୍ଠ", "ଷଷ୍ଠ"), ("6th", "ଷଷ୍ଠ"), ("୬th", "ଷଷ୍ଠ"),
            # 7
            ("7ମ", "ସପ୍ତମ"), ("୭ମ", "ସପ୍ତମ"), ("7th", "ସପ୍ତମ"), ("୭th", "ସପ୍ତମ"),
            # 8
            ("8ମ", "ଅଷ୍ଟମ"), ("୮ମ", "ଅଷ୍ଟମ"), ("8th", "ଅଷ୍ଟମ"), ("୮th", "ଅଷ୍ଟମ"),
            # 9
            ("9ମ", "ନବମ"), ("୯ମ", "ନବମ"), ("9th", "ନବମ"), ("୯th", "ନବମ"),
            # 10
            ("10ମ", "ଦଶମ"), ("୧୦ମ", "ଦଶମ"), ("10th", "ଦଶମ"), ("୧୦th", "ଦଶମ"),
        ]
        ord_1_to_10 = pynini.string_map(ord_1_to_10_pairs).optimize()

        # Generic ordinals: <cardinal> + "ତମ" or English suffixes (th, st, nd, rd)
        # e.g. ୧୧ତମ -> ଏଗାରତମ, ୨୧ତମ -> ଏକୋଇଶତମ, ୧୦୦ତମ -> ଶହେତମ
        ord_suffix = pynini.cross("ତମ", "ତମ") | pynini.cross("th", "ତମ") | pynini.cross("st", "ତମ") | pynini.cross("nd", "ତମ") | pynini.cross("rd", "ତମ")

        card_part = (NORMALIZE_DIGITS @ cardinal.cardinal_numbers).optimize()
        generic_ordinal = (card_part + ord_suffix).optimize()

        all_ordinals = (ord_1_to_10 | generic_ordinal).optimize()
        self.ordinal_numbers = all_ordinals

        graph = pynutil.insert('name: "') + convert_space(all_ordinals) + pynutil.insert('"')
        self.fst = graph.optimize()
