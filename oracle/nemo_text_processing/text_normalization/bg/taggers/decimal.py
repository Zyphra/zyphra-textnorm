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


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian decimals.
    Follows Unicode CLDR bg RBNF: 'x.x: << цяло и >>;'
    e.g. 0,5 -> tokens { name: "нула цяло и пет" }
         3.5 -> tokens { name: "три цяло и пет" }
         0,05 -> tokens { name: "нула цяло и нула пет" }
         -2,5 -> tokens { name: "минус две цяло и пет" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        card = cardinal.number

        # Integer part
        int_part = card

        # Separator: comma (Bulgarian standard) or dot
        sep = pynini.cross(pynini.union(",", "."), " цяло и ")

        # Fractional part: single or multiple digits
        d_map = pynini.string_map([
            ("0", "нула"), ("1", "едно"), ("2", "две"), ("3", "три"), ("4", "четири"),
            ("5", "пет"), ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
        ])
        lead_zeros = pynini.cross("0", "нула") + pynini.closure(pynutil.insert(" ") + d_map, 1, 5)
        frac_part = lead_zeros | card

        pos_decimal = int_part + sep + frac_part

        # Negative decimals
        neg_sign = pynini.cross(pynini.union("-", "−"), "минус ")
        neg_decimal = neg_sign + pos_decimal

        all_decimals = (neg_decimal | pos_decimal).optimize()
        self.all_decimals = all_decimals

        graph = pynutil.insert('name: "') + convert_space(all_decimals) + pynutil.insert('"')
        self.fst = graph.optimize()
