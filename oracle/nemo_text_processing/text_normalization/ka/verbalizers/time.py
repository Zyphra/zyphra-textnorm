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
    delete_space,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time in Georgian, e.g.
        time { hours: "ათი" } -> ათი
        time { hours: "თოთხმეტი" minutes: "ოცი" } -> თოთხმეტი და ოცი
        time { hours: "რვა" minutes: "თხუთმეტი" seconds: "ოცდაათი" } -> რვა და თხუთმეტი და ოცდაათი წამი
        time { period: "დღის" hours: "ორი" } -> დღის ორი
        time { hours: "თოთხმეტი" minutes: "ოცდაათი" zone: "UTC" } -> თოთხმეტი და ოცდაათი UTC
    """

    def __init__(self):
        super().__init__(name="time", kind="verbalize")

        def field(name):
            return pynutil.delete(f'{name}: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        period = field("period") + delete_space + pynutil.insert(" ")
        hours = field("hours")
        minutes = delete_space + pynutil.insert(" და ") + field("minutes")
        seconds = delete_space + pynutil.insert(" და ") + field("seconds") + pynutil.insert(" წამი")
        zone = delete_space + pynutil.insert(" ") + field("zone")

        time_body = (
            hours
            + pynini.closure(minutes, 0, 1)
            + pynini.closure(seconds, 0, 1)
            + pynini.closure(zone, 0, 1)
        )

        graph = pynini.closure(period, 0, 1) + time_body + delete_preserve_order
        self.numbers = graph.optimize()
        self.fst = self.delete_tokens(graph).optimize()
