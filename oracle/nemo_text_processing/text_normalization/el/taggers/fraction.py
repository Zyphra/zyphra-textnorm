# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import (
    MINUS,
    GraphFst,
)
from nemo_text_processing.text_normalization.el.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.el.taggers.ordinal import _build_ordinal_maps


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Greek fractions:
        "½" -> ένα δεύτερο
        "⅓" -> ένα τρίτο
        "⅔" -> δύο τρίτα
        "¼" -> ένα τέταρτο
        "¾" -> τρία τέταρτα
        "1/2" -> ένα δεύτερο
        "3/4" -> τρία τέταρτα
        "5/8" -> πέντε όγδοα
        "2½" -> δύο και ένα δεύτερο
        "3 1/4" -> τρία και ένα τέταρτο
        "-1/2" -> μείον ένα δεύτερο
        "-2½" -> μείον δύο και ένα δεύτερο
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        pure_cardinal = cardinal.pure_cardinal

        # Unicode vulgar fractions
        vulgar_pairs = [
            ("½", "ένα δεύτερο"),
            ("⅓", "ένα τρίτο"),
            ("⅔", "δύο τρίτα"),
            ("¼", "ένα τέταρτο"),
            ("¾", "τρία τέταρτα"),
            ("⅕", "ένα πέμπτο"),
            ("⅖", "δύο πέμπτα"),
            ("⅗", "τρία πέμπτα"),
            ("⅘", "τέσσερα πέμπτα"),
            ("⅙", "ένα έκτο"),
            ("⅚", "πέντε έκτα"),
            ("⅛", "ένα όγδοο"),
            ("⅜", "τρία όγδοα"),
            ("⅝", "πέντε όγδοα"),
            ("⅞", "επτά όγδοα"),
            ("⅐", "ένα έβδομο"),
            ("⅑", "ένα ένατο"),
            ("⅒", "ένα δέκατο"),
        ]
        vulgar_graph = pynini.string_map(vulgar_pairs)

        # Denominator singular (when numerator is "1")
        ord_maps = _build_ordinal_maps()
        # Neuter singular ordinals (2..100)
        den_sing_pairs = [p for p in ord_maps["o"] if p[0] != "1"]
        # Special case: 2 -> δεύτερο (already in den_sing_pairs)
        den_sing = pynini.string_map(den_sing_pairs)

        # Denominator plural (when numerator > 1)
        den_pl_pairs = [p for p in ord_maps["a"] if p[0] != "1"]
        # For 2: "2" -> "δεύτερα"
        den_pl = pynini.string_map(den_pl_pairs)

        slash = pynutil.delete("/")

        # 1 / <den_sing> -> "ένα <den_sing>"
        frac_one = pynini.cross("1", "ένα") + slash + pynutil.insert(" ") + den_sing

        # <num != 1> / <den_pl> -> "<num> <den_pl>"
        # Exclude "1" from pure_cardinal for the numerator
        num_gt1 = pynini.difference(pynini.project(pure_cardinal, "input"), "1").optimize() @ pure_cardinal
        frac_other = num_gt1 + slash + pynutil.insert(" ") + den_pl

        # Fallback for arbitrary higher denominators: "N προς D"
        frac_pro = pure_cardinal + pynini.cross("/", " προς ") + pure_cardinal

        slash_graph = frac_one | frac_other | pynutil.add_weight(frac_pro, 0.5)

        base_fractions = vulgar_graph | slash_graph

        # Mixed fractions: "2½", "3 1/4"
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        mixed_fractions = pure_cardinal + opt_space + pynutil.insert(" και ") + base_fractions

        # Negative fractions: "-1/2", "-2½", "−¾"
        neg_prefix = pynini.cross(MINUS, "μείον ")
        neg_fractions = neg_prefix + (base_fractions | mixed_fractions)

        all_fractions = (
            base_fractions
            | mixed_fractions
            | neg_fractions
        ).optimize()

        self.vulgar_graph = vulgar_graph
        self.slash_graph = slash_graph
        self.all_fractions = all_fractions
        self.fst = all_fractions
