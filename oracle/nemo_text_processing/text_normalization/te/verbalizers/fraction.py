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

from nemo_text_processing.text_normalization.te.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing fraction. Telugu names the denominator first, in the locative
    ("నాలుగింటిలో మూడు" = 3/4), e.g.
        fraction { numerator: "మూడు" denominator: "ఏడు" } -> ఏడింటిలో మూడు
        fraction { integer_part: "రెండు" numerator: "మూడు" denominator: "ఏడు" } -> రెండు మరియు ఏడింటిలో మూడు
        fraction { morphosyntactic_features: "ముప్పావు" } -> ముప్పావు

    The tagger emits numerator before denominator without preserve_order; this verbalizer accepts only the
    denominator-first order, which the normalizer's field permutation supplies.

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)

        optional_sign = pynini.closure(pynini.cross("negative: \"true\"", MINUS) + delete_space, 0, 1)

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        # locative of the last number word: ...ు / ...ి -> ...ింటిలో (ఏడు -> ఏడింటిలో, ఎనిమిది -> ఎనిమిదింటిలో),
        # any other ending takes లో (ఇరవై -> ఇరవైలో, వంద -> వందలో)
        vowel_sign_final = NEMO_SIGMA + pynini.union("ు", "ి")
        locative = pynini.union(
            pynini.compose(vowel_sign_final, NEMO_SIGMA + pynini.cross(pynini.union("ు", "ి"), "ింటిలో")),
            pynini.compose(pynini.difference(NEMO_SIGMA, vowel_sign_final), NEMO_SIGMA + pynutil.insert("లో")),
        ).optimize()

        integer = field("integer_part")
        numerator = field("numerator")
        denominator = pynini.compose(field("denominator"), locative)

        self.graph = optional_sign + (
            (
                pynini.closure(integer + delete_space + pynutil.insert(" మరియు "), 0, 1)
                + denominator
                + delete_space
                + pynutil.insert(" ")
                + numerator
            )
            | field("morphosyntactic_features")
        )

        delete_tokens = self.delete_tokens(self.graph + delete_space)
        self.fst = delete_tokens.optimize()
