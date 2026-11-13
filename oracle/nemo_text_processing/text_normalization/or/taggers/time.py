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

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGITS,
    convert_space,
)
from .cardinal import CardinalFst, ODIA_CARDINALS_0_TO_99

TIMEZONES = [
    ("UTC", "ୟୁ ଟି ସି"),
    ("GMT", "ଜି ଏମ୍ ଟି"),
    ("IST", "ଆଇ ଏସ୍ ଟି"),
    ("EST", "ଇ ଏସ୍ ଟି"),
    ("PST", "ପି ଏସ୍ ଟି"),
    ("CST", "ସି ଏସ୍ ଟି"),
]


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying clock times in Odia:
        ୧୨:୩୦ -> tokens { name: "ବାରଟା ତିରିଶ" }
        08:15:30 -> tokens { name: "ଆଠଟା ପନ୍ଦର ମିନିଟ୍ ତିରିଶ ସେକେଣ୍ଡ" }
        14:30 UTC -> tokens { name: "ଚଉଦଟା ତିରିଶ ୟୁ ଟି ସି" }
        9:00-17:00 -> tokens { name: "ନଅଟା ରୁ ସତରଟା" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        self.cardinal = cardinal

        # Hours (0 to 23) + "ଟା"
        hour_pairs = []
        for h in range(24):
            w = ODIA_CARDINALS_0_TO_99[h] + "ଟା"
            hour_pairs.append((str(h), w))
            hour_pairs.append((f"{h:02d}", w))
        hour_map = pynini.string_map(hour_pairs)
        hour_graph = (NORMALIZE_DIGITS @ hour_map).optimize()

        # Minutes (0 to 59)
        min_pairs = [("00", ""), ("୦୦", "")]
        for m in range(1, 60):
            w = ODIA_CARDINALS_0_TO_99[m]
            min_pairs.append((str(m), w))
            min_pairs.append((f"{m:02d}", w))
        min_map = pynini.string_map(min_pairs)
        min_graph = (NORMALIZE_DIGITS @ min_map).optimize()

        # Minutes with "ମିନିଟ୍" suffix (used when seconds are present)
        min_sec_pairs = [("00", "")]
        for m in range(1, 60):
            w = ODIA_CARDINALS_0_TO_99[m] + " ମିନିଟ୍"
            min_sec_pairs.append((str(m), w))
            min_sec_pairs.append((f"{m:02d}", w))
        min_sec_map = pynini.string_map(min_sec_pairs)
        min_sec_graph = (NORMALIZE_DIGITS @ min_sec_map).optimize()

        # Seconds (0 to 59) with "ସେକେଣ୍ଡ"
        sec_pairs = [("00", "")]
        for s in range(1, 60):
            w = ODIA_CARDINALS_0_TO_99[s] + " ସେକେଣ୍ଡ"
            sec_pairs.append((str(s), w))
            sec_pairs.append((f"{s:02d}", w))
        sec_map = pynini.string_map(sec_pairs)
        sec_graph = (NORMALIZE_DIGITS @ sec_map).optimize()

        # Timezones
        tz_graph = pynini.string_map(TIMEZONES).optimize()
        opt_tz = pynini.closure(pynini.accep(" ") + tz_graph, 0, 1)

        # 1. HH:MM (e.g. 12:30 -> ବାରଟା ତିରିଶ, 9:00 -> ନଅଟା)
        # Note: if min is "00", it produces empty string, so "9:00" -> "ନଅଟା"
        # If min is not "00", e.g. "12:30" -> "ବାରଟା ତିରିଶ"
        # We handle "00" cleanly
        min_nonzero = pynini.string_map([(f"{m:02d}", f" {ODIA_CARDINALS_0_TO_99[m]}") for m in range(1, 60)] + [(str(m), f" {ODIA_CARDINALS_0_TO_99[m]}") for m in range(1, 10)])
        min_nonzero_graph = (NORMALIZE_DIGITS @ min_nonzero).optimize()
        del_00 = pynutil.delete("00") | pynutil.delete("୦୦")

        hm_graph = (
            hour_graph + pynutil.delete(":") + (del_00 | min_nonzero_graph) + opt_tz
        ).optimize()

        # 2. HH:MM:SS (e.g. 08:15:30 -> ଆଠଟା ପନ୍ଦର ମିନିଟ୍ ତିରିଶ ସେକେଣ୍ଡ)
        hms_graph = (
            hour_graph
            + pynutil.delete(":")
            + pynutil.insert(" ")
            + min_sec_graph
            + pynutil.delete(":")
            + pynutil.insert(" ")
            + sec_graph
            + opt_tz
        ).optimize()

        # 3. Time ranges: 9:00-17:00, 09:00–17:00
        dash = pynini.union("-", "–", "—", " to ")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        time_range = (
            hm_graph + opt_sp + pynutil.delete(dash) + pynutil.insert(" ରୁ ") + opt_sp + hm_graph
        ).optimize()

        all_times = (hms_graph | time_range | hm_graph).optimize()
        self.time_graph = all_times

        graph = pynutil.insert('name: "') + convert_space(all_times) + pynutil.insert('"')
        self.fst = graph.optimize()
