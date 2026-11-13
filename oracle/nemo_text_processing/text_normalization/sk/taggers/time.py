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
    GraphFst,
)
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Slovak clock times, e.g.
        02:00 -> dve hodiny
        12:00 -> dvanásť hodín
        13:05 -> trinásť hodín päť minút
        14:30 -> štrnásť tridsať
        12:30:45 -> dvanásť hodín tridsať minút štyridsaťpäť sekúnd
        08:15:30 -> osem hodín pätnásť minút tridsať sekúnd
        14:30 UTC -> štrnásť tridsať UTC
        9:00-17:00 -> deväť nula nula až sedemnásť nula nula
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        hours_map = {
            0: "nula",
            1: "jedna",
            2: "dve",
            3: "tri",
            4: "štyri",
            5: "päť",
            6: "šesť",
            7: "sedem",
            8: "osem",
            9: "deväť",
            10: "desať",
            11: "jedenásť",
            12: "dvanásť",
            13: "trinásť",
            14: "štrnásť",
            15: "pätnásť",
            16: "šestnásť",
            17: "sedemnásť",
            18: "osemnásť",
            19: "devätnásť",
            20: "dvadsať",
            21: "dvadsaťjeden",
            22: "dvadsaťdva",
            23: "dvadsaťtri",
        }

        hours_hod_map = {
            1: "jedna hodina",
            2: "dve hodiny",
            3: "tri hodiny",
            4: "štyri hodiny",
            0: "nula hodín",
        }
        for h in range(5, 24):
            hours_hod_map[h] = f"{hours_map[h]} hodín"

        def min_str(m):
            if m == 0:
                return "nula"
            units = {
                1: "jeden",
                2: "dva",
                3: "tri",
                4: "štyri",
                5: "päť",
                6: "šesť",
                7: "sedem",
                8: "osem",
                9: "deväť",
            }
            teens = {
                10: "desať",
                11: "jedenásť",
                12: "dvanásť",
                13: "trinásť",
                14: "štrnásť",
                15: "pätnásť",
                16: "šestnásť",
                17: "sedemnásť",
                18: "osemnásť",
                19: "devätnásť",
            }
            tens = {20: "dvadsať", 30: "tridsať", 40: "štyridsať", 50: "päťdesiat"}
            if m < 10:
                return units[m]
            if m < 20:
                return teens[m]
            t = (m // 10) * 10
            u = m % 10
            return tens[t] if u == 0 else tens[t] + units[u]

        mins_min_map = {
            0: "",
            1: "jedna minúta",
            2: "dve minúty",
            3: "tri minúty",
            4: "štyri minúty",
        }
        for m in range(5, 60):
            mins_min_map[m] = f"{min_str(m)} minút"

        # 1. Exact hours: 02:00, 12:00
        pairs_exact = []
        for h in range(24):
            pairs_exact.append((f"{h:02d}:00", hours_hod_map[h]))
            pairs_exact.append((f"{h}:00", hours_hod_map[h]))

        # 2. Hours and minutes: 13:05, 14:30, 05:45, 09:59, 08:07
        pairs_hm = []
        for h in range(24):
            for m in range(1, 60):
                spoken = f"{hours_hod_map[h]} {mins_min_map[m]}"
                pairs_hm.append((f"{h:02d}:{m:02d}", spoken))
                pairs_hm.append((f"{h}:{m:02d}", spoken))

        hour_graph = pynini.string_map([
            (written, spoken)
            for h, spoken in hours_hod_map.items()
            for written in {str(h), f"{h:02d}"}
        ])
        minute_graph = pynini.string_map([
            (f"{m:02d}", mins_min_map[m] if m else "nula minút")
            for m in range(60)
        ])
        second_graph = pynini.string_map([
            (f"{s:02d}", "jedna sekunda" if s == 1 else "dve sekundy" if s == 2
             else f"{min_str(s)} sekundy" if s in (3, 4) else f"{min_str(s)} sekúnd")
            for s in range(60)
        ])
        hms = hour_graph + pynini.cross(":", " ") + minute_graph + pynini.cross(":", " ") + second_graph
        timezone = pynini.union("UTC", "GMT", "CET", "CEST", "EET")

        # 5. Time ranges: 9:00-17:00, 9:00–17:00
        time_dash = pynini.cross(pynini.union("-", "–"), " až ")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        base_time = pynini.string_map(pairs_exact + pairs_hm) | hms
        base_time += pynini.closure(pynini.accep(" ") + timezone, 0, 1)
        time_range = base_time + opt_sp + time_dash + opt_sp + base_time

        all_time = pynutil.add_weight(time_range, 0.05) | pynutil.add_weight(base_time, 0.08)
        self.fst = all_time.optimize()
