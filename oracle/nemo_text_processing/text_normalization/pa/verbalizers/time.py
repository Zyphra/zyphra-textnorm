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

from nemo_text_processing.text_normalization.pa.graph_utils import NEMO_NOT_QUOTE, GraphFst, delete_space, insert_space


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time in Punjabi, e.g.
        time { hours: "ਬਾਰਾਂ"  minutes: "ਦਸ"  seconds: "ਦਸ" } -> ਬਾਰਾਂ ਵੱਜ ਕੇ ਦਸ ਮਿੰਟ ਦਸ ਸਕਿੰਟ
        time { hours: "ਸੱਤ" minutes: "ਚਾਲੀ" } -> ਸੱਤ ਵੱਜ ਕੇ ਚਾਲੀ ਮਿੰਟ
        time { hours: "ਦਸ" } -> ਦਸ ਵਜੇ
        time { suffix: "ਸਵੇਰੇ" hours: "ਦਸ" } -> ਸਵੇਰੇ ਦਸ ਵਜੇ
        time { hours: "ਚੌਦਾਂ" minutes: "ਤੀਹ" zone: "ਯੂ ਟੀ ਸੀ" } -> ਚੌਦਾਂ ਵੱਜ ਕੇ ਤੀਹ ਮਿੰਟ ਯੂ ਟੀ ਸੀ

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="verbalize")

        hour = pynutil.delete("hours: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        minute = (
            pynutil.delete("minutes: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + insert_space
        )

        second = (
            pynutil.delete("seconds: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + insert_space
        )

        insert_vajj_ke = pynutil.insert(" ਵੱਜ ਕੇ ")
        insert_vaje = pynutil.insert(" ਵਜੇ")
        insert_minute = pynutil.insert("ਮਿੰਟ")
        insert_second = pynutil.insert("ਸਕਿੰਟ")

        period = pynini.closure(
            pynutil.delete("suffix: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\"")
            + delete_space
            + insert_space,
            0,
            1,
        )

        zone = pynini.closure(
            delete_space
            + insert_space
            + pynutil.delete("zone: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\""),
            0,
            1,
        )

        # hour minute second
        graph_hms = (
            hour
            + insert_vajj_ke
            + delete_space
            + minute
            + delete_space
            + insert_minute
            + insert_space
            + second
            + delete_space
            + insert_second
        )

        # hour minute
        graph_hm = hour + insert_vajj_ke + delete_space + minute + delete_space + insert_minute

        # hour:00:second
        graph_hs = hour + insert_vajj_ke + delete_space + second + delete_space + insert_second

        # hour alone
        graph_h = hour + insert_vaje

        # pre-formatted time range
        graph_range = (
            pynutil.delete("morphosyntactic_features: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\"")
        )

        self.graph = (period + (graph_hms | graph_hm | graph_hs | graph_h) + zone) | (graph_range + zone)

        final_graph = self.graph
        delete_tokens = self.delete_tokens(final_graph)
        self.fst = delete_tokens.optimize()
