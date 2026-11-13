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

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "పన్నెండు" minutes: "పది" seconds: "పది" } -> పన్నెండు గంటల పది నిమిషాల పది సెకన్లు
        time { hours: "ఒకటి" } -> ఒంటి గంట
        time { hours: "ఏడు" minutes: "నలభై" } -> ఏడు గంటల నలభై నిమిషాలు
        time { hours: "పది" } -> పది గంటలు
        time { day_period: "సాయంత్రం" hours: "ఏడు" minutes: "ముప్పై" } -> సాయంత్రం ఏడు గంటల ముప్పై నిమిషాలు

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
        one_hour = pynutil.delete("hours: \"ఒకటి\"")
        one_minute = pynutil.delete("minutes: \"ఒకటి\"")
        one_second = pynutil.delete("seconds: \"ఒకటి\"")
        day_period = pynini.closure(field("day_period") + delete_space + insert_space, 0, 1)
        zone = pynini.closure(delete_space + insert_space + field("zone"), 0, 1)

        # 1 o'clock is ఒంటి గంట; one minute / second take the singular (ఒక నిమిషం, ఒక సెకను)
        hours_combining = hour + pynutil.insert(" గంటల") | pynutil.add_weight(one_hour, -0.01) + pynutil.insert("ఒంటి గంట")
        hours_exact = hour + pynutil.insert(" గంటలు") | pynutil.add_weight(one_hour, -0.01) + pynutil.insert("ఒంటి గంట")
        minutes_combining = minute + pynutil.insert(" నిమిషాల") | pynutil.add_weight(
            one_minute, -0.01
        ) + pynutil.insert("ఒక నిమిషం")
        minutes_final = minute + pynutil.insert(" నిమిషాలు") | pynutil.add_weight(
            one_minute, -0.01
        ) + pynutil.insert("ఒక నిమిషం")
        seconds_final = second + pynutil.insert(" సెకన్లు") | pynutil.add_weight(
            one_second, -0.01
        ) + pynutil.insert("ఒక సెకను")

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
