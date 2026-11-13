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

from nemo_text_processing.text_normalization.mr.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "बारा"  minutes: "दहा"  seconds: "दहा" } -> बारा वाजून दहा मिनिटे दहा सेकंद
        time { hours: "सात" minutes: "एक" } -> सात वाजून एक मिनिट
        time { hours: "दहा" } -> दहा वाजता
        time { period: "सकाळी" hours: "दहा" } -> सकाळी दहा वाजता

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="verbalize")

        hour = pynutil.delete("hours: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + insert_space
        minute_value = pynini.closure(NEMO_NOT_QUOTE, 1)
        # CLDR mr: {0} मिनिट for one, {0} मिनिटे otherwise
        minute_one = pynini.accep("एक") + pynutil.delete("\"") + pynutil.insert(" मिनिट")
        minute_other = pynini.difference(minute_value, "एक") + pynutil.delete("\"") + pynutil.insert(" मिनिटे")
        minute = pynutil.delete("minutes: \"") + (minute_one | minute_other)
        second = (
            pynutil.delete("seconds: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\"")
            + pynutil.insert(" सेकंद")
        )
        period = pynini.closure(
            pynutil.delete("period: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"") + delete_space + insert_space,
            0,
            1,
        )
        zone = pynini.closure(
            delete_space + insert_space + pynutil.delete("zone: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\""),
            0,
            1,
        )

        insert_vajun = pynutil.insert("वाजून")
        insert_vajta = pynutil.insert("वाजता")

        graph_hms = (
            hour + delete_space + insert_vajun + insert_space + minute + delete_space + insert_space + second
        )
        graph_hm = hour + delete_space + insert_vajun + insert_space + minute
        graph_h = hour + delete_space + insert_vajta

        self.graph = period + (graph_hms | graph_hm | graph_h) + zone
        range_graph = (
            pynutil.delete("start {")
            + delete_space
            + self.graph
            + delete_space
            + pynutil.delete("}")
            + delete_space
            + pynutil.insert(" ते ")
            + pynutil.delete("end {")
            + delete_space
            + self.graph
            + delete_space
            + pynutil.delete("}")
            + delete_space
            + pynutil.delete("preserve_order: true")
        )
        delete_tokens = self.delete_tokens((self.graph | range_graph) + delete_space)
        self.fst = delete_tokens.optimize()
