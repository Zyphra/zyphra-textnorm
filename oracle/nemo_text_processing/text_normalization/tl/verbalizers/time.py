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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_preserve_order,
)
from nemo_text_processing.text_normalization.tl.graph_utils import get_linker_fst


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog time, e.g.
        time { hours: "sampu" minutes: "tatlumpu" } -> ika-sampu at tatlumpung minuto
        time { hours: "walo" zone: "P H T" } -> ika-walo P H T
        time { hours: "sampu" minutes: "tatlumpu" seconds: "labinlima" }
            -> ika-sampu at tatlumpung minuto at labinlimang segundo
        time { range: "ika-siyam hanggang ika-labimpito" } -> ika-siyam hanggang ika-labimpito
        time { hours: "walo" suffix: "ng umaga" } -> ika-walo ng umaga

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="time", kind="verbalize", deterministic=deterministic)
        linker = get_linker_fst()
        val = pynini.closure(NEMO_NOT_QUOTE, 1)

        hours = pynutil.delete('hours: "') + pynutil.insert("ika-") + val + pynutil.delete('"')
        minutes = (
            pynutil.delete(' minutes: "')
            + pynutil.insert(" at ")
            + (val @ linker)
            + pynutil.insert(" minuto")
            + pynutil.delete('"')
        )
        seconds = (
            pynutil.delete(' seconds: "')
            + pynutil.insert(" at ")
            + (val @ linker)
            + pynutil.insert(" segundo")
            + pynutil.delete('"')
        )
        suffix = pynutil.delete(' suffix: "') + pynutil.insert(" ") + val + pynutil.delete('"')
        zone = pynutil.delete(' zone: "') + pynutil.insert(" ") + val + pynutil.delete('"')

        hm_graph = (
            hours
            + pynini.closure(minutes, 0, 1)
            + pynini.closure(seconds, 0, 1)
            + pynini.closure(suffix, 0, 1)
            + pynini.closure(zone, 0, 1)
        )

        range_graph = pynutil.delete('range: "') + val + pynutil.delete('"')

        graph = hm_graph | range_graph
        self.fst = self.delete_tokens(graph + delete_preserve_order).optimize()
