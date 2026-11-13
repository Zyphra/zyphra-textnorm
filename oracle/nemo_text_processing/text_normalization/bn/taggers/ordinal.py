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

from nemo_text_processing.text_normalization.bn.graph_utils import GraphFst
from nemo_text_processing.text_normalization.bn.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.bn.utils import get_abs_path


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Bengali ordinals (CLDR %digits-ordinal / %spellout-ordinal), e.g.
        ১ম -> ordinal { integer: "প্রথম" }
        2য় -> ordinal { integer: "দ্বিতীয়" }
        ১১তম -> ordinal { integer: "এগারোতম" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        # 1-10 have their own words (প্রথম ... দশম); 11 and up are <cardinal>তম
        suffixes_fst = pynini.string_file(get_abs_path("data/ordinal/suffixes.tsv"))
        exceptions = pynini.string_file(get_abs_path("data/ordinal/exceptions.tsv"))

        # Limit cardinal graph to thousands range for faster compilation
        limited_cardinal_graph = (
            cardinal.teens_and_ties
            | cardinal.graph_hundreds
            | cardinal.graph_thousands
            | cardinal.graph_ten_thousands
        ).optimize()

        # English-style suffixes (21st, 102nd) are read as the Bengali ordinal <cardinal>তম
        english_suffixes = pynini.cross(pynini.union("st", "nd", "rd", "th"), "তম")
        graph = limited_cardinal_graph + (suffixes_fst | pynutil.add_weight(english_suffixes, -0.1))
        exceptions = pynutil.add_weight(exceptions, -0.1)
        # Calendar-day ordinals: ১লা -> পয়লা, ২১শে -> একুশে
        day_ordinal = pynini.string_file(get_abs_path("data/date/day_ordinal.tsv"))
        graph = pynini.union(exceptions, pynutil.add_weight(day_ordinal, -0.1), graph)

        self.graph = graph.optimize()

        final_graph = pynutil.insert("integer: \"") + graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
