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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "பன்னிரண்டு" minutes: "பத்து" seconds: "பத்து" } -> பன்னிரண்டு மணி பத்து நிமிடம் பத்து விநாடி
        time { hours: "ஒன்று" } -> ஒரு மணி
        time { hours: "ஏழு" minutes: "நாற்பது" } -> ஏழு மணி நாற்பது நிமிடம்
        time { hours: "பத்து" } -> பத்து மணி
        time { day_period: "மாலை" hours: "ஏழு" minutes: "முப்பது" } -> மாலை ஏழு மணி முப்பது நிமிடம்

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="verbalize")

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        hour = field("hours")
        minute = field("minutes")
        second = field("seconds")
        one_hour = pynutil.delete("hours: \"ஒன்று\"")
        one_minute = pynutil.delete("minutes: \"ஒன்று\"")
        one_second = pynutil.delete("seconds: \"ஒன்று\"")
        day_period = pynini.closure(field("day_period") + delete_space + insert_space, 0, 1)
        zone = pynini.closure(delete_space + insert_space + field("zone"), 0, 1)

        hours_combining = hour + pynutil.insert(" மணி") | pynutil.add_weight(one_hour, -0.01) + pynutil.insert("ஒரு மணி")
        hours_exact = hour + pynutil.insert(" மணி") | pynutil.add_weight(one_hour, -0.01) + pynutil.insert("ஒரு மணி")
        minutes_combining = minute + pynutil.insert(" நிமிடங்கள்") | pynutil.add_weight(
            one_minute, -0.01
        ) + pynutil.insert("ஒரு நிமிடம்")
        minutes_final = minute + pynutil.insert(" நிமிடங்கள்") | pynutil.add_weight(
            one_minute, -0.01
        ) + pynutil.insert("ஒரு நிமிடம்")
        seconds_final = second + pynutil.insert(" விநாடிகள்") | pynutil.add_weight(
            one_second, -0.01
        ) + pynutil.insert("ஒரு விநாடி")

        graph_hms = (
            hours_combining
            + delete_space
            + pynutil.insert(" ")
            + minutes_combining
            + delete_space
            + pynutil.insert(" ")
            + seconds_final
        )
        graph_hm = hours_combining + delete_space + pynutil.insert(" ") + minutes_final
        graph_h = hours_exact

        self.graph = day_period + (graph_hms | graph_hm | graph_h) + zone + delete_space

        delete_tokens = self.delete_tokens(self.graph)
        self.fst = delete_tokens.optimize()
