# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing fraction. Kannada names the denominator first, in the locative
    ("ಏಳರಲ್ಲಿ ಮೂರು" = 3/7), e.g.
        fraction { numerator: "ಮೂರು" denominator: "ಏಳು" } -> ಏಳರಲ್ಲಿ ಮೂರು
        fraction { integer_part: "ಐದು" numerator: "ಎರಡು" denominator: "ಮೂರು" } -> ಐದು ಮತ್ತು ಮೂರರಲ್ಲಿ ಎರಡು
        fraction { morphosyntactic_features: "ಮುಕ್ಕಾಲು" } -> ಮುಕ್ಕಾಲು
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)

        optional_sign = pynini.closure(pynini.cross("negative: \"true\"", MINUS) + delete_space, 0, 1)

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        # locative of the denominator: words ending in ು take ರಲ್ಲಿ (ಏಳು -> ಏಳರಲ್ಲಿ, ಮೂರು -> ಮೂರರಲ್ಲಿ),
        # ಸಾವಿರ -> ಸಾವಿರದಲ್ಲಿ, other endings take ರಲ್ಲಿ
        u_final = NEMO_SIGMA + "ು"
        locative = pynini.union(
            pynini.compose(u_final, NEMO_SIGMA + pynini.cross("ು", "ರಲ್ಲಿ")),
            pynini.cross("ಸಾವಿರ", "ಸಾವಿರದಲ್ಲಿ"),
            pynini.compose(pynini.difference(NEMO_SIGMA, u_final), NEMO_SIGMA + pynutil.insert("ರಲ್ಲಿ")),
        ).optimize()

        integer = field("integer_part")
        numerator = field("numerator")
        denominator = pynini.compose(field("denominator"), locative)

        self.graph = optional_sign + (
            (
                pynini.closure(integer + delete_space + pynutil.insert(" ಮತ್ತು "), 0, 1)
                + denominator
                + delete_space
                + pynutil.insert(" ")
                + numerator
            )
            | field("morphosyntactic_features")
        )

        delete_tokens = self.delete_tokens(self.graph + delete_space)
        self.fst = delete_tokens.optimize()
