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
    MIN_NEG_WEIGHT,
    NEMO_KN_CHAR,
    NEMO_NOT_SPACE,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.kn.taggers.punctuation import PunctuationFst


class WordFst(GraphFst):
    """
    Finite state transducer for classifying Kannada words.
        e.g. ಪುಸ್ತಕ -> tokens { name: "ಪುಸ್ತಕ" }

    Args:
        punctuation: PunctuationFst
        deterministic: if True will provide a single transduction option,
            for False multiple transductions are generated (used for audio-based normalization)
    """

    def __init__(self, punctuation: PunctuationFst, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)
        punct = punctuation.graph
        punct_in = pynini.project(punct, "input")
        symbols_to_exclude = (
            punct_in
            | pynini.union(
                "₹",
                "$",
                "€",
                "£",
                "¥",
                "%",
                "‰",
                "°",
                "&",
                "~",
                "±",
                "@",
                "#",
                "§",
                "¶",
                "©",
                "®",
                "™",
                "^",
                "²",
                "³",
                "½",
                "¼",
                "¾",
                "⅓",
                "⅔",
                "⅕",
                "⅖",
                "⅗",
                "⅘",
                "⅙",
                "⅚",
                "⅛",
                "⅜",
                "⅝",
                "⅞",
            )
        ).optimize()
        default_graph = pynini.closure(pynini.difference(NEMO_NOT_SPACE, symbols_to_exclude), 1)

        graph = pynini.closure(pynini.difference(NEMO_KN_CHAR, symbols_to_exclude), 1)
        graph = pynutil.add_weight(graph, MIN_NEG_WEIGHT) | default_graph

        graph = graph + pynini.closure(punct + graph)
        graph = pynini.closure(punct, 0, 1) + graph + pynini.closure(punct, 0, 1)

        fallback = pynutil.add_weight(pynini.closure(NEMO_NOT_SPACE, 1), 100.0)
        graph = graph | fallback

        self.graph = convert_space(graph)
        self.fst = (pynutil.insert("name: \"") + self.graph + pynutil.insert("\"")).optimize()
