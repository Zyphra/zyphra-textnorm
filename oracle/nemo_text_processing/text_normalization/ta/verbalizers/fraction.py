# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing fraction. Tamil names the denominator first,
    in the locative (-இல், e.g. "ஏழில் மூன்று" = 3/7), e.g.
        fraction { numerator: "மூன்று" denominator: "ஏழு" } -> ஏழில் மூன்று
        fraction { integer_part: "இரண்டு" numerator: "மூன்று" denominator: "ஏழு" } -> இரண்டு மற்றும் ஏழில் மூன்று
        fraction { morphosyntactic_features: "முக்கால்" } -> முக்கால்

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)

        optional_sign = pynini.closure(pynini.cross("negative: \"true\"", MINUS) + delete_space, 0, 1)

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        ends_in_u = NEMO_SIGMA + "ு"
        ends_in_m = NEMO_SIGMA + "ம்"
        other = pynini.difference(pynini.difference(NEMO_SIGMA, ends_in_u), ends_in_m)

        locative = (
            pynini.compose(ends_in_u, NEMO_SIGMA + pynini.cross("ு", "ில்"))
            | pynini.compose(ends_in_m, NEMO_SIGMA + pynini.cross("ம்", "த்தில்"))
            | (other + pynutil.insert("இல்"))
        ).optimize()

        integer = field("integer_part")
        numerator = field("numerator")
        denominator = pynini.compose(field("denominator"), locative)

        self.graph = optional_sign + (
            (
                pynini.closure(integer + delete_space + pynutil.insert(" "), 0, 1)
                + denominator
                + delete_space
                + pynutil.insert(" ")
                + numerator
            )
            | field("morphosyntactic_features")
        )

        delete_tokens = self.delete_tokens(self.graph + delete_space)
        self.fst = delete_tokens.optimize()
