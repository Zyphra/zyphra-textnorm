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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_NOT_QUOTE, GraphFst, delete_preserve_order


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing Malay time, e.g.
        time { hours: "sepuluh" minutes: "tiga puluh" } -> pukul sepuluh tiga puluh minit
        time { hours: "lapan" zone: "M Y T" } -> pukul lapan M Y T
        time { prefix: "jam" hours: "tujuh" } -> jam tujuh
        time { hours: "sepuluh" minutes: "tiga puluh" seconds: "lima belas" }
            -> pukul sepuluh tiga puluh minit lima belas saat

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="time", kind="verbalize", deterministic=deterministic)
        prefix = pynutil.delete("prefix: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\" ") | pynutil.insert("pukul")
        hours = pynutil.delete("hours: \"") + pynutil.insert(" ") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        minutes = (
            pynutil.delete(" minutes: \"") + pynutil.insert(" ") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + pynutil.insert(" minit")
        )
        seconds = pynutil.delete(" seconds: \"") + pynutil.insert(" ") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + pynutil.insert(" saat")
        zone = pynutil.delete(" zone: \"") + pynutil.insert(" ") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        graph = (
            prefix
            + hours
            + pynini.closure(minutes, 0, 1)
            + pynini.closure(seconds, 0, 1)
            + pynini.closure(zone, 0, 1)
        )
        self.fst = self.delete_tokens(graph + delete_preserve_order).optimize()
