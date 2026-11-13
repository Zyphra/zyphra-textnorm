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

# Number names from Unicode CLDR release-49 (fil locale, Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_CHAR, NEMO_NOT_QUOTE, GraphFst


class OrdinalFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog ordinals (CLDR fil %spellout-ordinal), e.g.
        ordinal { integer: "isa" } -> una
        ordinal { integer: "dalawa" } -> ikalawa
        ordinal { integer: "tatlo" } -> ikatlo
        ordinal { integer: "apat" } -> ikaapat
        ordinal { integer: "sampu" } -> ikasampu

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="ordinal", kind="verbalize", deterministic=deterministic)
        integer = pynutil.delete('integer: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        first = pynini.cross("isa", "una")
        second = pynini.cross("dalawa", "ikalawa")
        third = pynini.cross("tatlo", "ikatlo")
        others = pynutil.insert("ika") + pynini.difference(
            pynini.closure(NEMO_CHAR, 1), pynini.union("isa", "dalawa", "tatlo")
        )

        morphology = (first | second | third | others).optimize()
        self.fst = self.delete_tokens(integer @ morphology).optimize()
