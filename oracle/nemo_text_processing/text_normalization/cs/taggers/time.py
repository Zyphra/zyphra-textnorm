# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.cs.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Czech clock times, timezones,
    and time ranges.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        # Hours: 0..23
        hours_map = [
            ("0", "nula"),
            ("00", "nula"),
            ("1", "jedna"),
            ("01", "jedna"),
            ("2", "dvě"),
            ("02", "dvě"),
            ("3", "tři"),
            ("03", "tři"),
            ("4", "čtyři"),
            ("04", "čtyři"),
            ("5", "pět"),
            ("05", "pět"),
            ("6", "šest"),
            ("06", "šest"),
            ("7", "sedm"),
            ("07", "sedm"),
            ("8", "osm"),
            ("08", "osm"),
            ("9", "devět"),
            ("09", "devět"),
            ("10", "deset"),
            ("11", "jedenáct"),
            ("12", "dvanáct"),
            ("13", "třináct"),
            ("14", "čtrnáct"),
            ("15", "patnáct"),
            ("16", "šestnáct"),
            ("17", "sedmnáct"),
            ("18", "osmnáct"),
            ("19", "devatenáct"),
            ("20", "dvacet"),
            ("21", "dvacet jedna"),
            ("22", "dvacet dva"),
            ("23", "dvacet tři"),
        ]
        hour = pynini.string_map(hours_map)

        # Minutes / Seconds: 00..59
        min_sec_map = [
            ("00", "nula nula"),
            ("01", "nula jedna"),
            ("02", "nula dvě"),
            ("03", "nula tři"),
            ("04", "nula čtyři"),
            ("05", "nula pět"),
            ("06", "nula šest"),
            ("07", "nula sedm"),
            ("08", "nula osm"),
            ("09", "nula devět"),
            ("0", "nula"),
            ("1", "jedna"),
            ("2", "dvě"),
            ("3", "tři"),
            ("4", "čtyři"),
            ("5", "pět"),
            ("6", "šest"),
            ("7", "sedm"),
            ("8", "osm"),
            ("9", "devět"),
            ("10", "deset"),
            ("11", "jedenáct"),
            ("12", "dvanáct"),
            ("13", "třináct"),
            ("14", "čtrnáct"),
            ("15", "patnáct"),
            ("16", "šestnáct"),
            ("17", "sedmnáct"),
            ("18", "osmnáct"),
            ("19", "devatenáct"),
            ("20", "dvacet"),
            ("21", "dvacet jedna"),
            ("22", "dvacet dva"),
            ("23", "dvacet tři"),
            ("24", "dvacet čtyři"),
            ("25", "dvacet pět"),
            ("26", "dvacet šest"),
            ("27", "dvacet sedm"),
            ("28", "dvacet osm"),
            ("29", "dvacet devět"),
            ("30", "třicet"),
            ("31", "třicet jedna"),
            ("32", "třicet dva"),
            ("33", "třicet tři"),
            ("34", "třicet čtyři"),
            ("35", "třicet pět"),
            ("36", "třicet šest"),
            ("37", "třicet sedm"),
            ("38", "třicet osm"),
            ("39", "třicet devět"),
            ("40", "čtyřicet"),
            ("41", "čtyřicet jedna"),
            ("42", "čtyřicet dva"),
            ("43", "čtyřicet tři"),
            ("44", "čtyřicet čtyři"),
            ("45", "čtyřicet pět"),
            ("46", "čtyřicet šest"),
            ("47", "čtyřicet sedm"),
            ("48", "čtyřicet osm"),
            ("49", "čtyřicet devět"),
            ("50", "padesát"),
            ("51", "padesát jedna"),
            ("52", "padesát dva"),
            ("53", "padesát tři"),
            ("54", "padesát čtyři"),
            ("55", "padesát pět"),
            ("56", "padesát šest"),
            ("57", "padesát sedm"),
            ("58", "padesát osm"),
            ("59", "padesát devět"),
        ]
        minute = pynini.string_map(min_sec_map)
        second = minute

        # Colon separator between hours and minutes
        colon = pynutil.delete(":")

        # Midnight special cases
        midnight = pynini.cross("00:00", "půlnoc") | pynini.cross("0:00", "půlnoc")

        # Standard H:MM or HH:MM
        time_hm = (hour + colon + pynutil.insert(" ") + minute).optimize()

        # With seconds H:MM:SS or HH:MM:SS
        time_hms = (
            hour + colon + pynutil.insert(" ") + minute + colon + pynutil.insert(" ") + second
        ).optimize()

        # AM / PM indicators
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        ampm = pynini.string_map([
            ("AM", "dopoledne"),
            ("A.M.", "dopoledne"),
            ("am", "dopoledne"),
            ("a.m.", "dopoledne"),
            ("dop.", "dopoledne"),
            ("dop", "dopoledne"),
            ("PM", "odpoledne"),
            ("P.M.", "odpoledne"),
            ("pm", "odpoledne"),
            ("p.m.", "odpoledne"),
            ("odp.", "odpoledne"),
            ("odp", "odpoledne"),
            ("e.m.", "odpoledne"),
            ("e.m", "odpoledne"),
            ("fm", "dopoledne"),
            ("f.m.", "dopoledne"),
        ])

        time_core = (midnight | time_hms | time_hm).optimize()

        time_with_ampm = (
            time_core + opt_sp + pynutil.insert(" ") + ampm
        ).optimize()

        # Timezones: UTC, GMT, CET, CEST, EST, PST, etc.
        tz_map = [
            ("UTC", "U T C"),
            ("GMT", "G M T"),
            ("CET", "C E T"),
            ("CEST", "C E S T"),
            ("EST", "E S T"),
            ("EDT", "E D T"),
            ("PST", "P S T"),
            ("PDT", "P D T"),
            ("SEČ", "středoevropského času"),
            ("SELČ", "středoevropského letního času"),
        ]
        tz = pynini.string_map(tz_map)

        # Timezone offsets: "UTC+10", "UTC-10", "UTC+2", "UTC−10"
        offset_sign = pynini.cross("+", "plus ") | pynini.cross("-", "mínus ") | pynini.cross("−", "mínus ")
        tz_offset = (
            tz
            + opt_sp
            + pynutil.insert(" ")
            + offset_sign
            + cardinal.n1_999
        ).optimize()

        time_with_tz = (
            (time_with_ampm | time_core)
            + opt_sp
            + pynutil.insert(" ")
            + (tz_offset | tz)
        ).optimize()

        # Time ranges: "9:00-17:00", "09:00–17:00", "9:30-18:15"
        dash = pynini.cross("-", " až ") | pynini.cross("–", " až ") | pynini.cross("—", " až ")
        time_range = (
            time_core + opt_sp + dash + opt_sp + time_core
        ).optimize()

        self.fst = (
            midnight
            | time_with_tz
            | time_with_ampm
            | time_range
            | time_hms
            | time_hm
        ).optimize()
