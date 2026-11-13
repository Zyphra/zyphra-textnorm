# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål clock times.
    e.g. 10:00 -> ti
         14:30 -> fjorten tretti
         12.30 -> tolv tretti
         kl. 10 -> klokken ti
         12:30:45 -> tolv tretti førtifem
         08:05 -> åtte null fem
         14:30 UTC -> fjorten tretti u t c
         14:00 UTC+10 -> fjorten u t c pluss ti
         9:00-17:00 -> ni til sytten
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        card_masc = cardinal.cardinal_masculine

        # Hours 0-23
        hours_map = [
            (str(h), pynini.shortestpath(str(h) @ card_masc).string()) for h in range(24)
        ]
        # Also with leading zero "00"-"09"
        for h in range(10):
            hours_map.append((f"0{h}", pynini.shortestpath(str(h) @ card_masc).string()))
        hours = pynini.string_map(hours_map)

        # Minutes 00-59
        minutes_map = [
            ("00", ""),  # 10:00 -> ti
        ]
        for m in range(1, 10):
            minutes_map.append((f"0{m}", f"null {pynini.shortestpath(str(m) @ card_masc).string()}"))
        for m in range(10, 60):
            minutes_map.append((str(m), pynini.shortestpath(str(m) @ card_masc).string()))
        minutes = pynini.string_map(minutes_map)

        # Seconds 00-59
        seconds_map = []
        for s in range(10):
            seconds_map.append((f"0{s}", f"null {pynini.shortestpath(str(s) @ card_masc).string()}"))
        for s in range(10, 60):
            seconds_map.append((str(s), pynini.shortestpath(str(s) @ card_masc).string()))
        seconds = pynini.string_map(seconds_map)

        time_sep = pynutil.delete(":") | pynutil.delete(".")

        # H:MM or H.MM
        # When minutes are "00": "10:00" -> "ti"
        h_00 = hours + time_sep + pynutil.delete("00")
        # When minutes are non-zero: "14:30" -> "fjorten tretti", "08:05" -> "åtte null fem"
        non_zero_mins = pynini.difference(pynini.closure(NEMO_DIGIT, 2), pynini.accep("00")) @ minutes
        h_mm = hours + time_sep + pynutil.insert(" ") + non_zero_mins

        h_mm_all = h_00 | h_mm

        # H:MM:SS
        h_mm_ss = (
            hours
            + time_sep
            + pynutil.insert(" ")
            + (minutes | pynini.cross("00", "null null"))
            + time_sep
            + pynutil.insert(" ")
            + seconds
        )

        base_time = h_mm_ss | h_mm_all

        # Prefix "kl." or "Kl." or "klokken"
        kl_prefix = (
            pynini.cross("kl. ", "klokken ")
            | pynini.cross("Kl. ", "klokken ")
            | pynini.cross("kl ", "klokken ")
            | pynini.cross("Kl ", "klokken ")
            | pynini.cross("klokken ", "klokken ")
        )
        # Also bare hour with kl. prefix: "kl. 10" -> "klokken ti"
        kl_hour = kl_prefix + hours
        kl_time = kl_prefix + base_time

        # Time suffixes: am, pm, f.m., e.m.
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        am = opt_space + (
            pynini.cross("am", " formiddag")
            | pynini.cross("AM", " formiddag")
            | pynini.cross("a.m.", " formiddag")
            | pynini.cross("f.m.", " formiddag")
        )
        pm = opt_space + (
            pynini.cross("pm", " ettermiddag")
            | pynini.cross("PM", " ettermiddag")
            | pynini.cross("p.m.", " ettermiddag")
            | pynini.cross("e.m.", " ettermiddag")
        )
        ampm = am | pm

        time_ampm = (base_time | hours) + ampm

        # Timezones: UTC, GMT, CET, EST, PST
        tz_map = [
            ("UTC", "u t c"),
            ("GMT", "g m t"),
            ("CET", "c e t"),
            ("EST", "e s t"),
            ("PST", "p s t"),
            ("cet", "c e t"),
            ("est", "e s t"),
        ]
        tz = (opt_space + pynutil.insert(" ") + pynini.string_map(tz_map)).optimize()

        # Timezone offsets: UTC+10 -> "u t c pluss ti", UTC−10 -> "u t c minus ti"
        sign = pynini.cross("+", " pluss ") | pynini.cross("-", " minus ") | pynini.cross("−", " minus ")
        tz_offset = (
            tz
            + sign
            + card_masc
        )

        time_with_tz = (
            (base_time | time_ampm | kl_time)
            + (tz_offset | tz)
        )

        single_time = (
            time_with_tz
            | time_ampm
            | kl_time
            | kl_hour
            | base_time
        )

        # Time ranges: 9:00-17:00, 09:00–17:00
        dash = (
            pynini.cross("-", " til ")
            | pynini.cross("–", " til ")
            | pynini.cross("—", " til ")
        )
        time_range = (
            base_time
            + opt_space
            + dash
            + opt_space
            + base_time
        )

        all_times = (
            time_range
            | single_time
        )

        self.graph = all_times.optimize()
        self.fst = self.graph
