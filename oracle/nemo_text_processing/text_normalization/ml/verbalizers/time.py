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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "പത്ത്" minutes: "മുപ്പത്" } -> പത്ത് മുപ്പത്
        time { hours: "ഏഴ്" } -> ഏഴ് മണി
        time { hours: "ഒരു" } -> ഒരു മണി
        time { day_period: "വൈകുന്നേരം" hours: "ഏഴ്" minutes: "മുപ്പത്" } -> വൈകുന്നേരം ഏഴ് മുപ്പത്
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="time", kind="verbalize", deterministic=deterministic)

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        hour = field("hours")
        minute = field("minutes")
        second = field("seconds")

        day_period = pynini.closure(field("day_period") + delete_space + insert_space, 0, 1)
        zone = pynini.closure(delete_space + insert_space + field("zone"), 0, 1)

        # 1:00 is ഒരു മണി, others <hour> മണി
        one_hour = pynutil.delete('hours: "ഒരു"') | pynutil.delete('hours: "ഒന്ന്"')
        other_hour = (
            pynutil.delete('hours: "')
            + (pynini.closure(NEMO_NOT_QUOTE, 1) - pynini.union("ഒരു", "ഒന്ന്"))
            + pynutil.delete('"')
        )
        hour_exact = (one_hour + pynutil.insert("ഒരു മണി")) | (other_hour + pynutil.insert(" മണി"))
        graph_hms = hour + delete_space + insert_space + minute + delete_space + insert_space + second
        graph_hm = hour + delete_space + insert_space + minute
        graph_h = hour_exact

        graph = day_period + (graph_hms | graph_hm | graph_h) + zone + delete_space
        self.fst = self.delete_tokens(graph).optimize()
