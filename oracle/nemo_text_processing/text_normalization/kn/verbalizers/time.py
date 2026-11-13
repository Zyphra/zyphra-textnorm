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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "ಹನ್ನೆರಡು" minutes: "ಹತ್ತು" seconds: "ಹತ್ತು" } -> ಹನ್ನೆರಡು ಗಂಟೆ ಹತ್ತು ನಿಮಿಷ ಹತ್ತು ಸೆಕೆಂಡ್
        time { hours: "ಒಂದು" } -> ಒಂದು ಗಂಟೆ
        time { hours: "ಏಳು" minutes: "ನಲವತ್ತು" } -> ಏಳು ಗಂಟೆ ನಲವತ್ತು ನಿಮಿಷ
        time { hours: "ಹತ್ತು" } -> ಹತ್ತು ಗಂಟೆ
        time { day_period: "ಸಂಜೆ" hours: "ಏಳು" minutes: "ಮೂವತ್ತು" } -> ಸಂಜೆ ಏಳು ಗಂಟೆ ಮೂವತ್ತು ನಿಮಿಷ

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
        day_period = pynini.closure(field("day_period") + delete_space + insert_space, 0, 1)
        zone = pynini.closure(delete_space + insert_space + field("zone"), 0, 1)

        hours_combining = hour + pynutil.insert(" ಗಂಟೆ")
        hours_exact = hour + pynutil.insert(" ಗಂಟೆ")
        minutes_combining = minute + pynutil.insert(" ನಿಮಿಷ")
        minutes_final = minute + pynutil.insert(" ನಿಮಿಷ")
        seconds_final = second + pynutil.insert(" ಸೆಕೆಂಡ್")

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
