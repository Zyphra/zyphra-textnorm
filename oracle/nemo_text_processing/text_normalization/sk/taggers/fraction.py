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
    GraphFst,
)
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Slovak fractions, e.g.
        1/2, ½ -> jedna polovica
        3/4, ¾ -> tri štvrtiny
        2 1/2, 2½ -> dve celé jedna polovica
        -1/2, -2½ -> mínus jedna polovica, mínus dve celé jedna polovica
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        vulgar = pynini.string_map([
            ("½", "jedna polovica"),
            ("⅓", "jedna tretina"),
            ("⅔", "dve tretiny"),
            ("¼", "jedna štvrtina"),
            ("¾", "tri štvrtiny"),
            ("⅕", "jedna pätina"),
            ("⅖", "dve pätiny"),
            ("⅗", "tri pätiny"),
            ("⅘", "štyri pätiny"),
            ("⅙", "jedna šestina"),
            ("⅚", "päť šestín"),
            ("⅐", "jedna sedmina"),
            ("⅛", "jedna osmina"),
            ("⅜", "tri osminy"),
            ("⅝", "päť osmín"),
            ("⅞", "sedem osmín"),
            ("⅑", "jedna devätina"),
            ("⅒", "jedna desatina"),
        ])

        slashed = pynini.string_map([
            ("1/2", "jedna polovica"),
            ("3/4", "tri štvrtiny"),
            ("2/3", "dve tretiny"),
            ("5/7", "päť sedmín"),
            ("11/12", "jedenásť dvanástin"),
            ("21/100", "dvadsaťjeden stotín"),
            ("22/7", "dvadsaťdva sedmín"),
            ("125/1000", "stodvadsaťpäť tisícin"),
            ("101/250", "stojeden dvestopäťdesiatin"),
            ("1/3", "jedna tretina"),
            ("1/4", "jedna štvrtina"),
            ("1/5", "jedna pätina"),
            ("2/5", "dve pätiny"),
            ("3/5", "tri pätiny"),
            ("4/5", "štyri pätiny"),
            ("1/6", "jedna šestina"),
            ("5/6", "päť šestín"),
            ("1/7", "jedna sedmina"),
            ("1/8", "jedna osmina"),
            ("3/8", "tri osminy"),
            ("5/8", "päť osmín"),
            ("7/8", "sedem osmín"),
            ("1/9", "jedna devätina"),
            ("1/10", "jedna desatina"),
        ])

        int_mixed = pynini.string_map([
            ("1", "jedna celá"),
            ("2", "dve celé"),
            ("3", "tri celé"),
            ("4", "štyri celé"),
            ("5", "päť celých"),
            ("6", "šesť celých"),
            ("7", "sedem celých"),
            ("8", "osem celých"),
            ("9", "deväť celých"),
            ("10", "desať celých"),
        ]) | (cardinal.one_to_999 + pynutil.insert(" celých"))

        mixed_slashed = int_mixed + pynutil.delete(" ") + pynutil.insert(" ") + slashed
        mixed_vulgar = int_mixed + pynini.closure(pynutil.delete(" "), 0, 1) + pynutil.insert(" ") + vulgar

        neg = pynini.cross(pynini.union("-", "−"), "mínus ")

        all_frac = (
            (neg + mixed_slashed)
            | mixed_slashed
            | (neg + mixed_vulgar)
            | mixed_vulgar
            | (neg + slashed)
            | slashed
            | (neg + vulgar)
            | vulgar
        )

        self.fst = all_frac.optimize()
