# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.mr.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_NON_ZERO,
    GraphFst,
)
from nemo_text_processing.text_normalization.mr.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.mr.utils import get_abs_path, load_labels


def va_number_inputs() -> 'pynini.FstLike':
    """
    Digit strings (ASCII and Devanagari) whose CLDR mr ordinal is cardinal + "वा" (11-18, 50, 79-88);
    every other number above ten takes cardinal + "ावा".
    """
    deva = "०१२३४५६७८९"
    numbers = [row[0] for row in load_labels(get_abs_path("data/ordinal/va_numbers.tsv"))]
    return pynini.union(*numbers, *["".join(deva[int(c)] for c in n) for n in numbers]).optimize()


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Marathi ordinals (CLDR %spellout-ordinal), e.g.
        १ला -> ordinal { integer: "पहिला" }
        5वी -> ordinal { integer: "पाचवी" }
        11वा -> ordinal { integer: "अकरावा" }
        21वे -> ordinal { integer: "एकवीसावे" }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        suffixes = pynini.string_file(get_abs_path("data/ordinal/suffixes.tsv"))
        exceptions = pynini.string_file(get_abs_path("data/ordinal/exceptions.tsv"))

        # Limit cardinal graph to thousands range for faster compilation
        limited_cardinal_graph = (
            cardinal.teens_and_ties
            | cardinal.graph_hundreds
            | cardinal.graph_thousands
            | cardinal.graph_ten_thousands
        ).optimize()

        delete_sep = pynutil.delete(",")
        two_digits = NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        three_digits = NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        strip_commas = (
            pynini.closure(NEMO_ALL_DIGIT, 1, 2) + delete_sep + three_digits
            | pynini.closure(NEMO_ALL_DIGIT, 1, 2) + delete_sep + two_digits + delete_sep + three_digits
        ).optimize()
        limited_with_commas = (
            limited_cardinal_graph
            | pynini.compose(strip_commas, limited_cardinal_graph | cardinal.graph_lakhs | cardinal.graph_ten_lakhs)
        ).optimize()

        above_ten = NEMO_ALL_NON_ZERO + pynini.closure(NEMO_ALL_DIGIT | pynini.accep(","), 1)
        va_inputs = va_number_inputs()
        aava_inputs = pynini.difference(above_ten, va_inputs).optimize()

        graph_va = pynini.compose(va_inputs, limited_cardinal_graph) + suffixes
        graph_aava = pynini.compose(aava_inputs, limited_with_commas) + pynutil.insert("ा") + suffixes

        graph = pynini.union(pynutil.add_weight(exceptions, -0.1), graph_va, graph_aava)

        self.graph = graph.optimize()

        final_graph = pynutil.insert("integer: \"") + self.graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
