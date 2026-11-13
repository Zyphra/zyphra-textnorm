# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import (
    GraphFst,
)
from nemo_text_processing.text_normalization.el.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Greek clock times and time ranges:
        "14:30" -> δεκατέσσερις και τριάντα
        "08:15:30" -> οκτώ και δεκαπέντε και τριάντα δευτερόλεπτα
        "00:00" -> μεσάνυχτα
        "00:30" -> μηδέν και τριάντα
        "7:05" -> επτά και πέντε
        "10:00 π.μ." -> δέκα π.μ.
        "2:30 μ.μ." -> δύο και τριάντα μ.μ.
        "14:30 UTC" -> δεκατέσσερις και τριάντα UTC
        "9:00-17:00" -> εννέα έως δεκαεπτά
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        # Hours: in Greek, hours are feminine (η ώρα)
        # 1: μία, 3: τρεις, 4: τέσσερις, 13: δεκατρείς, 14: δεκατέσσερις, 21: είκοσι μία, 23: είκοσι τρεις
        hours_map = [
            ("00", "μηδέν"), ("0", "μηδέν"),
            ("01", "μία"), ("1", "μία"),
            ("02", "δύο"), ("2", "δύο"),
            ("03", "τρεις"), ("3", "τρεις"),
            ("04", "τέσσερις"), ("4", "τέσσερις"),
            ("05", "πέντε"), ("5", "πέντε"),
            ("06", "έξι"), ("6", "έξι"),
            ("07", "επτά"), ("7", "επτά"),
            ("08", "οκτώ"), ("8", "οκτώ"),
            ("09", "εννέα"), ("9", "εννέα"),
            ("10", "δέκα"),
            ("11", "έντεκα"),
            ("12", "δώδεκα"),
            ("13", "δεκατρείς"),
            ("14", "δεκατέσσερις"),
            ("15", "δεκαπέντε"),
            ("16", "δεκαέξι"),
            ("17", "δεκαεπτά"),
            ("18", "δεκαοκτώ"),
            ("19", "δεκαεννέα"),
            ("20", "είκοσι"),
            ("21", "είκοσι μία"),
            ("22", "είκοσι δύο"),
            ("23", "είκοσι τρεις"),
        ]
        hour_graph = pynini.string_map(hours_map)

        # Minutes:
        min_units = {
            "00": "", "01": "και ένα", "02": "και δύο", "03": "και τρία", "04": "και τέσσερα",
            "05": "και πέντε", "06": "και έξι", "07": "και επτά", "08": "και οκτώ", "09": "και εννέα",
            "10": "και δέκα", "11": "και έντεκα", "12": "και δώδεκα", "13": "και δεκατρία",
            "14": "και δεκατέσσερα", "15": "και δεκαπέντε", "16": "και δεκαέξι", "17": "και δεκαεπτά",
            "18": "και δεκαοκτώ", "19": "και δεκαεννέα",
        }
        min_tens = {2: "είκοσι", 3: "τριάντα", 4: "σαράντα", 5: "πενήντα"}
        min_u = {0: "", 1: "ένα", 2: "δύο", 3: "τρία", 4: "τέσσερα", 5: "πέντε", 6: "έξι", 7: "επτά", 8: "οκτώ", 9: "εννέα"}

        min_map = []
        for k, v in min_units.items():
            min_map.append((k, v))
        for t in range(2, 6):
            for u in range(10):
                k = f"{t}{u}"
                spk = min_tens[t] + (" " + min_u[u] if u > 0 else "")
                min_map.append((k, "και " + spk))

        # Filter out leading space when minute is 00
        min_pairs = []
        for k, v in min_map:
            if k == "00":
                min_pairs.append((k, ""))
            else:
                min_pairs.append((k, " " + v))
        min_graph = pynini.string_map(min_pairs)

        del_colon = pynutil.delete(":")

        # Special: "00:00" -> "μεσάνυχτα"
        midnight = pynini.cross("00:00", "μεσάνυχτα") | pynini.cross("0:00", "μεσάνυχτα")

        # Standard HH:MM
        hm_time = hour_graph + del_colon + min_graph

        # With seconds: HH:MM:SS (e.g. 08:15:30 -> οκτώ και δεκαπέντε και τριάντα δευτερόλεπτα)
        sec_pairs = []
        for k, v in min_map:
            if k != "00":
                sec_pairs.append((k, " " + v + " δευτερόλεπτα"))
            else:
                sec_pairs.append((k, ""))
        sec_graph = pynini.string_map(sec_pairs)

        hms_time = hour_graph + del_colon + min_graph + del_colon + sec_graph

        # AM / PM suffixes:
        am_pm = pynini.string_map(
            [
                ("π.μ.", "π.μ."),
                ("π.μ", "π.μ."),
                ("πμ", "π.μ."),
                ("μ.μ.", "μ.μ."),
                ("μ.μ", "μ.μ."),
                ("μμ", "μ.μ."),
                ("AM", "π.μ."),
                ("PM", "μ.μ."),
                ("am", "π.μ."),
                ("pm", "μ.μ."),
            ]
        )
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        time_ampm = (hm_time | hms_time) + opt_space + pynutil.insert(" ") + am_pm

        # Timezones: "14:30 UTC", "09:00 GMT"
        timezones = pynini.string_map(
            [
                ("UTC", "UTC"),
                ("GMT", "GMT"),
                ("EET", "EET"),
                ("EEST", "EEST"),
                ("CET", "CET"),
                ("CEST", "CEST"),
            ]
        )
        time_tz = (hm_time | hms_time) + pynutil.delete(" ") + pynutil.insert(" ") + timezones

        # Time ranges: "9:00-17:00", "09:00–17:00", "9:00 - 17:00"
        range_dash = pynini.cross(pynini.union("-", "–", "—", " - ", " – ", " — "), " έως ")
        time_range = hm_time + range_dash + hm_time

        all_times = (
            midnight
            | time_range
            | time_tz
            | time_ampm
            | hms_time
            | hm_time
        ).optimize()

        self.hm_time = hm_time
        self.all_times = all_times
        self.fst = all_times
