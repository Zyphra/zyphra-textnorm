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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.gu.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_NON_ZERO,
    GraphFst,
)
from nemo_text_processing.text_normalization.gu.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.gu.utils import get_abs_path


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Gujarati ordinals (CLDR %spellout-ordinal), e.g.
        ૧લો -> ordinal { integer: "પહેલો" }
        5મી -> ordinal { integer: "પાંચમી" }
        10મો -> ordinal { integer: "દસમો" }
        21મું -> ordinal { integer: "એકવીસમું" }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transductions are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        suffixes = pynini.string_file(get_abs_path("data/ordinal/suffixes.tsv"))
        exceptions = pynini.string_file(get_abs_path("data/ordinal/exceptions.tsv"))

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

        # In Gujarati (CLDR 7: =%spellout-cardinal=મો; etc.), numbers 7+ append suffix directly
        graph_regular = limited_with_commas + suffixes

        graph = pynini.union(pynutil.add_weight(exceptions, -0.1), graph_regular)
        self.graph = graph.optimize()

        final_graph = pynutil.insert('integer: "') + self.graph + pynutil.insert('"')
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
