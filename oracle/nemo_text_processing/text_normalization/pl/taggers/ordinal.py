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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst, convert_space
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Polish ordinals, e.g.
        "1." -> "pierwszy"
        "2." -> "drugi"
        "3." -> "trzeci"
        "1-szy" -> "pierwszy"
        "2-gi" -> "drugi"
        "3-ci" -> "trzeci"
        "4-ty" -> "czwarty"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        pn = cardinal.pn
        self.pn = pn

        ord_m = pn.ordinal_fst(gender="masc")
        ord_f = pn.ordinal_fst(gender="fem")

        # Ordinal with period: "3." -> "trzeci"
        dot_ord = ord_m + pynutil.delete(".")

        # Ordinal suffixes (masculine and feminine)
        suff_m = (
            pynini.cross("-szy", "")
            | pynini.cross("-gi", "")
            | pynini.cross("-ci", "")
            | pynini.cross("-ty", "")
            | pynini.cross("-my", "")
        )
        suff_f = (
            pynini.cross("-sza", "")
            | pynini.cross("-ga", "")
            | pynini.cross("-cia", "")
            | pynini.cross("-ta", "")
            | pynini.cross("-ma", "")
        )

        num_1_4 = pynini.closure(NEMO_DIGIT, 1, 4)
        suffixed_m = (num_1_4 + suff_m) @ ord_m
        suffixed_f = (num_1_4 + suff_f) @ ord_f

        self.graph = (dot_ord | suffixed_m | suffixed_f).optimize()
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
