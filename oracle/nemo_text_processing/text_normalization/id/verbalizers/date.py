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
    Finite state transducer for verbalizing dates in day month year order, plus standalone decade/era expressions, e.g.
        date { day: "tujuh belas" month: "Agustus" year: "seribu sembilan ratus empat puluh lima" }
            -> tujuh belas Agustus seribu sembilan ratus empat puluh lima
        date { year: "dua ribu dua puluhan" } -> dua ribu dua puluhan

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
        graph = day + space + month + pynini.closure(space + year, 0, 1)
        graph |= month + space + year
        graph |= year
        self.fst = self.delete_tokens(graph).optimize()
