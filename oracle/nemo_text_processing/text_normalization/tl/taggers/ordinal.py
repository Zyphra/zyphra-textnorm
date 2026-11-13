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
    Finite state transducer for classifying Tagalog ordinals (CLDR fil %digits-ordinal "ika=#,##0="), e.g.
        "ika-3" -> ordinal { integer: "tatlo" }
        "ika-1" -> ordinal { integer: "isa" }
        "ika-21" -> ordinal { integer: "dalawampu't isa" }
        "1st" -> ordinal { integer: "isa" }
        "2nd" -> ordinal { integer: "dalawa" }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)
        prefix = pynutil.delete(pynini.union("ika-", "ika", "Ika-", "Ika", "pang-", "Pang-"))
        graph_prefix = prefix + pynutil.insert('integer: "') + cardinal.graph_with_sep + pynutil.insert('"')

        # English-borrowed suffixes (1st, 2nd, 3rd, 4th, 21st...)
        suffix = pynutil.delete(pynini.union("st", "nd", "rd", "th", "ST", "ND", "RD", "TH"))
        graph_suffix = pynutil.insert('integer: "') + (cardinal.graph_with_sep + suffix) + pynutil.insert('"')

        graph = graph_prefix | graph_suffix
        self.fst = self.add_tokens(graph).optimize()
