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

from nemo_text_processing.text_normalization.ur.graph_utils import (
    MIN_NEG_WEIGHT,
    NEMO_NOT_SPACE,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.ur.taggers.punctuation import PunctuationFst


class WordFst(GraphFst):
    """
    Finite state transducer for classifying Urdu words.
        e.g. کتاب -> tokens { name: "کتاب" }

    Args:
        punctuation: PunctuationFst
        deterministic: if True will provide a single transduction option,
            for False multiple transductions are generated (used for audio-based normalization)
    """

    def __init__(self, punctuation: PunctuationFst, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)

        # Arabic-script letters and marks used in Urdu (no digits, no punctuation such as ، ؛ ؟ ۔)
        URDU_CHAR = pynini.union(
            *[chr(i) for i in range(0x0621, 0x064A + 1)],  # Arabic letters
            *[chr(i) for i in range(0x064B, 0x065F + 1)],  # harakat and other marks
            chr(0x0670),  # superscript alef
            *[chr(i) for i in range(0x0671, 0x06D3 + 1)],  # extended letters (ٹ پ چ ڈ ڑ ژ ک گ ں ھ ہ ی ے ...)
        ).optimize()

        # Include punctuation in the graph
        punct = punctuation.graph
        symbols_to_exclude = (
            pynini.union("$", "€", "₩", "£", "¥", "₹", "₨", "₽", "₺", "₪", "₴", "₫", "৳", "₦", "₱", "฿", "֏", "¢", "#", "%", "~", "≈", "±", "©", "®", "™", "§")
            | punct.project("input")
        ).optimize()
        default_graph = pynini.closure(pynini.difference(NEMO_NOT_SPACE, symbols_to_exclude), 1)
        graph = pynini.closure(pynini.difference(URDU_CHAR, symbols_to_exclude), 1)
        graph = pynutil.add_weight(graph, MIN_NEG_WEIGHT) | default_graph

        # Ensure no spaces around punctuation
        graph = pynini.closure(graph + pynini.closure(punct + graph, 0, 1))

        # Quotes and brackets stay attached to the word they wrap ("اچھا" stays "اچھا", not " اچھا "): the ur
        # package has no post-processor to re-attach them.
        open_marks = pynini.union('"', "'", "(", "«", "“", "‘")
        close_marks = pynini.union('"', "'", ")", "»", "”", "’")
        graph = pynini.closure(open_marks, 0, 1) + graph + pynini.closure(close_marks, 0, 1)

        self.graph = convert_space(graph)
        self.fst = (pynutil.insert("name: \"") + self.graph + pynutil.insert("\"")).optimize()
