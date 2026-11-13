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

from unicodedata import category

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.gu.graph_utils import (
    MIN_NEG_WEIGHT,
    NEMO_NOT_SPACE,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.gu.taggers.punctuation import PunctuationFst


class WordFst(GraphFst):
    """
    Finite state transducer for classifying Gujarati words.
        e.g. ઘર -> tokens { name: "ઘર" }
    """

    def __init__(self, punctuation: PunctuationFst, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)

        # Define Gujarati characters and symbols
        GUJARATI_CHAR = pynini.union(
            *[chr(i) for i in range(0x0A81, 0x0AFF + 1) if category(chr(i)) != "Cn"]
        ).optimize()

        punct = punctuation.graph
        non_word_symbols = pynini.union(
            "$", "€", "₩", "£", "¥", "₹", "₨", "₦", "৳", "֏", "₽", "₫",
            "₺", "₪", "₴", "₱", "฿", "¢",
            "#", "%", "‰", "°", "℃", "℉", "Ω", "Ω", "²", "³",
            "±", "©", "§", "®", "™",
            "½", "¼", "¾", "⅓", "⅔", "⅕", "⅖", "⅗", "⅘", "⅙", "⅚", "⅛", "⅜", "⅝", "⅞", "⅐", "⅑", "⅒",
        )
        default_graph = pynini.closure(
            pynini.difference(NEMO_NOT_SPACE, punct.project("input") | non_word_symbols), 1
        )
        symbols_to_exclude = (non_word_symbols | punct).optimize()

        graph = pynini.closure(pynini.difference(GUJARATI_CHAR, symbols_to_exclude), 1)
        graph = pynutil.add_weight(graph, MIN_NEG_WEIGHT) | default_graph

        graph = pynini.closure(graph + pynini.closure(punct + graph, 0, 1))

        self.graph = convert_space(graph)
        self.fst = (pynutil.insert('name: "') + self.graph + pynutil.insert('"')).optimize()
