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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ur.graph_utils import NEMO_NOT_QUOTE, GraphFst, delete_space, insert_space


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "بارہ"  minutes: "دس"  seconds: "دس" } -> بارہ بج کر دس منٹ دس سیکنڈ
        time { hours: "سات" minutes: "چالیس" } -> سات بج کر چالیس منٹ
        time { hours: "دس" } -> دس بجے
        time { suffix: "صبح" hours: "دس" } -> صبح دس بجے

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="verbalize")

        hour = pynutil.delete("hours: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + insert_space

        minute = (
            pynutil.delete("minutes: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + insert_space
        )

        second = (
            pynutil.delete("seconds: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + insert_space
        )

        insert_minute = pynutil.insert("منٹ")
        insert_second = pynutil.insert("سیکنڈ")
        insert_bajkar = pynutil.insert("بج کر")
        insert_baje = pynutil.insert("بجے")

        # hour minute second
        graph_hms = (
            hour
            + delete_space
            + insert_bajkar
            + insert_space
            + minute
            + delete_space
            + insert_minute
            + insert_space
            + second
            + delete_space
            + insert_second
        )

        graph_quarter = (
            pynutil.delete("morphosyntactic_features: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        )

        # hour minute
        graph_hm = hour + delete_space + insert_bajkar + insert_space + minute + delete_space + insert_minute

        # hour
        graph_h = hour + delete_space + insert_baje

        # Day period (am / pm input) is spoken before the time: "صبح دس بجے".
        day_period = (
            pynutil.delete("suffix: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + delete_space
        )
        optional_zone = pynini.closure(
            delete_space
            + insert_space
            + pynutil.delete("zone: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\""),
            0,
            1,
        )
        clock = graph_hms | graph_hm | graph_h
        core = clock | graph_quarter | (day_period + insert_space + clock)
        self.graph = core + optional_zone

        final_graph = self.graph

        delete_tokens = self.delete_tokens(final_graph)
        self.fst = delete_tokens.optimize()
