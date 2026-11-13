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

from nemo_text_processing.text_normalization.pa.graph_utils import GraphFst
from nemo_text_processing.text_normalization.pa.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.pa.utils import get_abs_path


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Punjabi ordinals (CLDR %digits-ordinal / %spellout-ordinal), e.g.
        ੧ਲਾ -> ordinal { integer: "ਪਹਿਲਾ" }
        2ਜਾ -> ordinal { integer: "ਦੂਜਾ" }
        ੫ਵਾਂ -> ordinal { integer: "ਪੰਜਵਾਂ" }
        10th -> ordinal { integer: "ਦਸਵਾਂ" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        suffixes_fst = pynini.string_file(get_abs_path("data/ordinal/suffixes.tsv"))
        exceptions = pynini.string_file(get_abs_path("data/ordinal/exceptions.tsv"))

        limited_cardinal_graph = (
            cardinal.teens_and_ties
            | cardinal.graph_hundreds
            | cardinal.graph_thousands
            | cardinal.graph_ten_thousands
        ).optimize()

        english_suffixes = pynini.cross(pynini.union("st", "nd", "rd", "th"), "ਵਾਂ")
        graph = limited_cardinal_graph + (suffixes_fst | pynutil.add_weight(english_suffixes, -0.1))
        bare_digits = pynini.closure(pynini.union(*"0123456789੦੧੨੩੪੫੬੭੮੯"), 1)
        ordinal_stems = bare_digits @ exceptions
        marked_ordinal = ordinal_stems + pynutil.delete(pynini.union("ਵਾਂ", "ਵਾ", "st", "nd", "rd", "th"))
        marked_exceptions = pynini.difference(pynini.project(exceptions, "input"), bare_digits) @ exceptions
        graph = (
            graph
            | pynutil.add_weight(marked_ordinal, -0.2)
            | pynutil.add_weight(marked_exceptions, -0.3)
        )

        self.graph = graph.optimize()

        final_graph = pynutil.insert("integer: \"") + graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
