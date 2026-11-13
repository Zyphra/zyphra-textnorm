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


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian fractions.
    e.g. ½ -> tokens { name: "една втора" }
         3/4 -> tokens { name: "три четвърти" }
         2 1/2 -> tokens { name: "две и една втора" }
         -2½ -> tokens { name: "минус две и една втора" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        card_n = cardinal.cardinal_n
        card_f = cardinal.cardinal_f

        # Unicode vulgar fractions
        vulgar_map = pynini.string_map([
            ("½", "една втора"), ("⅓", "една трета"), ("⅔", "две трети"),
            ("¼", "една четвърт"), ("¾", "три четвърти"), ("⅕", "една пета"),
            ("⅖", "две пети"), ("⅗", "три пети"), ("⅘", "четири пети"),
            ("⅙", "една шеста"), ("⅚", "пет шести"), ("⅛", "една осма"),
            ("⅜", "три осми"), ("⅝", "пет осми"), ("⅞", "седем осми"),
            ("⅐", "една седма"), ("⅑", "една девета"), ("⅒", "една десета")
        ])

        # Slash fractions: numerator / denominator
        # Denominators when numerator is 1 (singular feminine ordinal):
        den_one = pynini.string_map([
            ("2", "втора"), ("3", "трета"), ("4", "четвърт"), ("5", "пета"),
            ("6", "шеста"), ("7", "седма"), ("8", "осма"), ("9", "девета"),
            ("10", "десета"), ("12", "дванадесета"), ("100", "стотна"),
            ("1000", "хилядна"), ("250", "двеста и петдесета")
        ])

        # Denominators when numerator is > 1 (plural feminine ordinal):
        den_other = pynini.string_map([
            ("2", "втори"), ("3", "трети"), ("4", "четвърти"), ("5", "пети"),
            ("6", "шести"), ("7", "седми"), ("8", "осми"), ("9", "девети"),
            ("10", "десети"), ("12", "дванадесети"), ("100", "стотни"),
            ("1000", "хилядни"), ("250", "двеста и петдесети")
        ])

        num_one = pynini.cross("1", "една")
        slash = pynutil.delete("/") + pynutil.insert(" ")

        slash_frac_one = num_one + slash + den_one
        num_other = (pynini.difference(pynini.project(card_f, "input"), "1") @ card_f).optimize()
        slash_frac_other = num_other + slash + den_other

        simple_fraction = (vulgar_map | pynutil.add_weight(slash_frac_one, -0.01) | slash_frac_other).optimize()

        # Mixed fractions: e.g. "2 1/2", "2½", "1 1/3" -> "две и една втора"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        req_sp = pynutil.delete(" ")
        mixed_vulgar = card_n + opt_sp + pynutil.insert(" и ") + vulgar_map
        mixed_slash = card_n + req_sp + pynutil.insert(" и ") + (slash_frac_one | slash_frac_other)
        mixed_fraction = (mixed_vulgar | mixed_slash).optimize()

        # Negative fractions: "-2½", "-1/2", "−¾"
        neg_sign = pynini.cross(pynini.union("-", "−"), "минус ")
        neg_fraction = neg_sign + (mixed_fraction | simple_fraction)

        all_fractions = (neg_fraction | mixed_fraction | simple_fraction).optimize()
        self.all_fractions = all_fractions

        graph = pynutil.insert('name: "') + convert_space(all_fractions) + pynutil.insert('"')
        self.fst = graph.optimize()
