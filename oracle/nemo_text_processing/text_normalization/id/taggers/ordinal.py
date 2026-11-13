# Copyright (c) 2026 Zyphra, Inc.
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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Indonesian ordinals (CLDR id %digits-ordinal "ke-#"), e.g.
        "ke-3" -> ordinal { integer: "tiga" }
        "ke21" -> ordinal { integer: "dua puluh satu" }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)
        prefix = pynutil.delete(pynini.union("ke-", "ke", "Ke-", "Ke"))
        graph = prefix + pynutil.insert("integer: \"") + cardinal.graph_with_sep + pynutil.insert("\"")
        self.fst = self.add_tokens(graph).optimize()
