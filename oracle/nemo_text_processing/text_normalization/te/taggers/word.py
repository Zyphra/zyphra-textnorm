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
    MIN_NEG_WEIGHT,
    NEMO_NOT_SPACE,
    NEMO_TE_CHAR,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.te.taggers.punctuation import PunctuationFst


class WordFst(GraphFst):
    """
    Finite state transducer for classifying Telugu words.
        e.g. బంగారం -> tokens { name: "బంగారం" }

    Args:
        punctuation: PunctuationFst
        deterministic: if True will provide a single transduction option,
            for False multiple transductions are generated (used for audio-based normalization)
    """

    def __init__(self, punctuation: PunctuationFst, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)
        # Include punctuation in the graph
        punct = punctuation.graph
        punct_in = pynini.project(punct, "input")
        symbols_to_exclude = (
            pynini.union(
                "$",
                "¢",
                "€",
                "₩",
                "£",
                "¥",
                "₹",
                "₨",
                "₦",
                "৳",
                "₽",
                "₫",
                "₱",
                "฿",
                "₵",
                "₪",
                "₺",
                "₴",
                "₸",
                "₼",
                "₾",
                "֏",
                "#",
                "%",
                "‰",
                "~",
                "±",
                "&",
                "©",
                "®",
                "™",
                "§",
                "¶",
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
                "⅐",
                "⅛",
                "⅜",
                "⅝",
                "⅞",
                "⅑",
                "⅒",
            )
            | punct_in
        ).optimize()
        default_graph = pynini.closure(pynini.difference(NEMO_NOT_SPACE, symbols_to_exclude), 1)

        graph = pynini.closure(pynini.difference(NEMO_TE_CHAR, symbols_to_exclude), 1)
        graph = pynutil.add_weight(graph, MIN_NEG_WEIGHT) | default_graph

        # Ensure no spaces around punctuation (at least 1 segment so bare punct cannot match word_graph)
        graph = graph + pynini.closure(punct + graph)

        # Punctuation written against a word stays inside the word token, so the verbalized text keeps the
        # original spacing ("(సరే)", "ఎందుకు?!"); there is no post-processing pass that would re-attach it.
        graph = pynini.closure(punct, 0, 1) + graph + pynini.closure(punct, 0, 1)

        # Fallback for any residual non-space token containing unconsumed symbols so ClassifyFst never fails
        fallback = pynutil.add_weight(pynini.closure(NEMO_NOT_SPACE, 1), 100.0)
        graph = graph | fallback

        self.graph = convert_space(graph)
        self.fst = (pynutil.insert("name: \"") + self.graph + pynutil.insert("\"")).optimize()
