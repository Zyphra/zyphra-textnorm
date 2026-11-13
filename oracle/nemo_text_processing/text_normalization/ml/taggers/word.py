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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    MIN_NEG_WEIGHT,
    NEMO_ML_CHAR,
    NEMO_NOT_SPACE,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.ml.taggers.punctuation import PunctuationFst


class WordFst(GraphFst):
    """
    Finite state transducer for classifying Malayalam words.
        e.g. മലയാളം -> tokens { name: "മലയാളം" }
    """

    def __init__(self, punctuation: PunctuationFst, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)

        punct = punctuation.graph
        punct_in = pynini.project(punct, "input")
        symbols_to_exclude = (
            punct_in
            | pynini.union(
                "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
                "൦", "൧", "൨", "൩", "൪", "൫", "൬", "൭", "൮", "൯",
                "$", "€", "£", "¥", "₹", "%", "‰", "°", "℃", "℉",
            )
        ).optimize()

        default_graph = pynini.closure(pynini.difference(NEMO_NOT_SPACE, symbols_to_exclude), 1)
        ml_graph = pynini.closure(pynini.difference(NEMO_ML_CHAR, symbols_to_exclude), 1)

        graph = pynutil.add_weight(ml_graph, MIN_NEG_WEIGHT) | default_graph
        graph = graph + pynini.closure(punct + graph)
        graph = pynini.closure(punct, 0, 1) + graph + pynini.closure(punct, 0, 1)

        # Fallback for any unconsumed token
        fallback = pynutil.add_weight(pynini.closure(NEMO_NOT_SPACE, 1), 100.0)
        graph = graph | fallback

        self.graph = convert_space(graph)
        self.fst = (pynutil.insert("name: \"") + self.graph + pynutil.insert("\"")).optimize()
