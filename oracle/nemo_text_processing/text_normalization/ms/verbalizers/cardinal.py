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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_NOT_QUOTE, GraphFst


class CardinalFst(GraphFst):
    """
    Finite state transducer for verbalizing Malay cardinals, e.g.
        cardinal { negative: "true" integer: "dua belas" } -> negatif dua belas
        cardinal { negative: "sekitar" integer: "lima puluh" } -> sekitar lima puluh
        cardinal { negative: "lebih kurang" integer: "lima" } -> lebih kurang lima

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="verbalize", deterministic=deterministic)
        prefix_sign = (
            pynini.cross('negative: "true" ', "negatif ")
            | pynini.cross('negative: "sekitar" ', "sekitar ")
            | pynini.cross('negative: "lebih kurang" ', "lebih kurang ")
            | pynini.cross('negative: "kurang lebih" ', "kurang lebih ")
            | pynini.cross('negative: "kira-kira" ', "kira-kira ")
        )
        self.optional_sign = pynini.closure(prefix_sign, 0, 1)
        self.numbers = pynutil.delete('integer: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        self.fst = self.delete_tokens(self.optional_sign + self.numbers).optimize()
