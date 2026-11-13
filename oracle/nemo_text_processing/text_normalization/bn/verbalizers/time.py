# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.bn.graph_utils import NEMO_NOT_QUOTE, GraphFst, delete_space, insert_space


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "বারো"  minutes: "দশ"  seconds: "দশ" } -> বারোটা দশ মিনিট দশ সেকেন্ড
        time { hours: "সাত" minutes: "চল্লিশ" } -> সাতটা চল্লিশ মিনিট
        time { hours: "দশ" } -> দশটা
        time { suffix: "সকাল" hours: "দশ" } -> সকাল দশটা
        time { hours: "চৌদ্দ" minutes: "ত্রিশ" zone: "ইউ টি সি" } -> চৌদ্দটা ত্রিশ মিনিট ইউ টি সি

    The hour is the plain cardinal with the classifier টা glued to it (দশ + টা -> দশটা).

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

        insert_minute = pynutil.insert("মিনিট")
        insert_second = pynutil.insert("সেকেন্ড")
        insert_ta = pynutil.insert("টা")
        period = pynini.closure(
            pynutil.delete("suffix: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + delete_space
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
            + insert_ta
            + delete_space
            + insert_space
            + minute
            + delete_space
            + insert_minute
            + insert_space
            + second
            + delete_space
            + insert_second
        )

        # hour minute
        graph_hm = hour + insert_ta + delete_space + insert_space + minute + delete_space + insert_minute

        # hour:00:second
        graph_hs = (
            hour
            + insert_ta
            + delete_space
            + insert_space
            + second
            + delete_space
            + insert_second
        )

        # hour
        graph_h = hour + insert_ta

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
