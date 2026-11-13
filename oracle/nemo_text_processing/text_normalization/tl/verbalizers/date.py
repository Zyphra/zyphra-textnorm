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


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog dates, e.g.
        date { day: "labimpito" month: "Agosto" year: "isang libo siyam na raan apatnapu't lima" }
            -> labimpito ng Agosto isang libo siyam na raan apatnapu't lima
        date { day: "una" month: "Mayo" year: "dalawang libo dalawampu't tatlo" }
            -> una ng Mayo dalawang libo dalawampu't tatlo
        date { year: "mga taong dalawang libo dalawampu" }
            -> mga taong dalawang libo dalawampu
        date { year: "limang daan bago si Kristo" }
            -> limang daan bago si Kristo

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="date", kind="verbalize", deterministic=deterministic)
        day = pynutil.delete('day: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        month = pynutil.delete('month: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        year = pynutil.delete('year: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        space = pynini.accep(" ")

        # Day + ng + Month + [Year]
        graph = day + pynutil.delete(" ") + pynutil.insert(" ng ") + month + pynini.closure(space + year, 0, 1)
        # Month + Year
        graph |= month + space + year
        # Year only (decades, eras)
        graph |= year

        self.fst = self.delete_tokens(graph).optimize()
