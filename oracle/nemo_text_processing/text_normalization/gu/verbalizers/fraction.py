# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.gu.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing fraction in Gujarati, e.g.
        fraction { integer_part: "તેવીસ" numerator: "ચાર" denominator: "છ" } -> તેવીસ પૂર્ણાંક ચાર ના છેદમાં છ
        fraction { numerator: "ચાર" denominator: "છ" } -> ચાર ના છેદમાં છ
        fraction { morphosyntactic_features: "દોઢ" } -> દોઢ

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transductions are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)

        optional_sign = pynini.cross('negative: "true"', MINUS) | (
            pynutil.delete('negative: "')
            + pynini.difference(pynini.closure(NEMO_NOT_QUOTE, 1), "true")
            + pynutil.delete('"')
            + pynutil.insert(" ")
        )
        optional_sign = pynini.closure(optional_sign + delete_space, 0, 1)

        integer = pynutil.delete("integer_part: \"") + pynini.closure(NEMO_NOT_QUOTE) + pynutil.delete("\" ")
        numerator = pynutil.delete("numerator: \"") + pynini.closure(NEMO_NOT_QUOTE) + pynutil.delete("\" ")
        denominator = pynutil.delete("denominator: \"") + pynini.closure(NEMO_NOT_QUOTE) + pynutil.delete("\"")
        insert_na_chedma = pynutil.insert(" ના છેદમાં ")
        insert_purnank = pynutil.insert(" પૂર્ણાંક ")
        graph_quarter = (
            pynutil.delete("morphosyntactic_features: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        )

        fraction_default = numerator + insert_na_chedma + denominator

        self.graph = optional_sign + (
            pynini.closure(integer + insert_purnank, 0, 1) + fraction_default
            | graph_quarter
        )

        delete_tokens = self.delete_tokens(self.graph)
        self.fst = delete_tokens.optimize()
