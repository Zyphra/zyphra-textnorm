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

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian contextual Roman numerals.
    e.g. Глава IV -> tokens { name: "глава четвърта" }
         Част II -> tokens { name: "част втора" }
         Том I -> tokens { name: "том първи" }
         XXI век -> tokens { name: "двадесет и първи век" }
         Симеон I -> tokens { name: "Симеон първи" }
         Борис III -> tokens { name: "Борис трети" }
         XL -> tokens { name: "X L" }
         MIX -> tokens { name: "M I X" }
         CD -> tokens { name: "C D" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_m = pynini.string_map([
            ("I", "първи"), ("II", "втори"), ("III", "трети"), ("IV", "четвърти"),
            ("V", "пети"), ("VI", "шести"), ("VII", "седми"), ("VIII", "осми"),
            ("IX", "девети"), ("X", "десети"), ("XI", "единадесети"), ("XII", "дванадесети"),
            ("XIII", "тринадесети"), ("XIV", "четиринадесети"), ("XV", "петнадесети"),
            ("XVI", "шестнадесети"), ("XVII", "седемнадесети"), ("XVIII", "осемнадесети"),
            ("XIX", "деветнадесети"), ("XX", "двадесети"), ("XXI", "двадесет и първи"),
            ("XXII", "двадесет и втори")
        ])

        roman_f = pynini.string_map([
            ("I", "първа"), ("II", "втора"), ("III", "трета"), ("IV", "четвърта"),
            ("V", "пета"), ("VI", "шеста"), ("VII", "седма"), ("VIII", "осма"),
            ("IX", "девета"), ("X", "десета"), ("XI", "единадесета"), ("XII", "дванадесета"),
            ("XIII", "тринадесета"), ("XIV", "четиринадесета"), ("XV", "петнадесета"),
            ("XVI", "шестнадесета"), ("XVII", "седемнадесета"), ("XVIII", "осемнадесета"),
            ("XIX", "деветнадесета"), ("XX", "двадесета"), ("XXI", "двадесет и първа"),
            ("XXII", "двадесет и втора")
        ])

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        chap = (
            pynini.union("Глава", "глава")
            + pynutil.insert(" ")
            + opt_sp
            + roman_f
        )
        part = (
            pynini.union("Част", "част")
            + pynutil.insert(" ")
            + opt_sp
            + roman_f
        )
        vol = (
            pynini.union("Том", "том")
            + pynutil.insert(" ")
            + opt_sp
            + roman_m
        )
        century = (
            roman_m
            + opt_sp
            + pynutil.insert(" ")
            + pynini.union("век", "в.")
        )
        monarch = (
            pynini.union(
                "Симеон", "Борис", "Петър", "Иван Асен", "Калоян", "Самуил",
                "Александър", "Николай", "Хенри", "Луи", "Елизабет"
            )
            + pynutil.insert(" ")
            + opt_sp
            + roman_m
        )

        controls = (
            pynini.cross("XL", "X L")
            | pynini.cross("MIX", "M I X")
            | pynini.cross("CD", "C D")
        )

        all_romans = (chap | part | vol | century | monarch | controls).optimize()
        self.all_romans = all_romans

        graph = pynutil.insert('name: "') + convert_space(all_romans) + pynutil.insert('"')
        self.fst = graph.optimize()
