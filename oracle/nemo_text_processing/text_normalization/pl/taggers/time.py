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
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Polish clock times, e.g.
        "12:30" -> "dwunasta trzydzieści"
        "08:15:30" -> "ósma piętnaście trzydzieści"
        "7:05" -> "siódma zero pięć"
        "00:00" -> "północ"
        "00:30" -> "zero trzydzieści"
        "14:30 UTC" -> "czternasta trzydzieści u t c"
        "09:00 GMT" -> "dziewiąta zero zero g m t"
        "9:00 AM" -> "dziewiąta rano"
        "4:45 p.m." -> "czwarta czterdzieści pięć po południu"
        "9:00-17:00" -> "dziewiąta zero zero do siedemnastej zero zero"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        # Hours mapping (0-23 in feminine ordinal, e.g. 1 -> pierwsza, 14 -> czternasta)
        hours_map = [
            ("0", "zero"),
            ("00", "zero"),
            ("1", "pierwsza"),
            ("01", "pierwsza"),
            ("2", "druga"),
            ("02", "druga"),
            ("3", "trzecia"),
            ("03", "trzecia"),
            ("4", "czwarta"),
            ("04", "czwarta"),
            ("5", "piąta"),
            ("05", "piąta"),
            ("6", "szósta"),
            ("06", "szósta"),
            ("7", "siódma"),
            ("07", "siódma"),
            ("8", "ósma"),
            ("08", "ósma"),
            ("9", "dziewiąta"),
            ("09", "dziewiąta"),
            ("10", "dziesiąta"),
            ("11", "jedenasta"),
            ("12", "dwunasta"),
            ("13", "trzynasta"),
            ("14", "czternasta"),
            ("15", "piętnasta"),
            ("16", "szesnasta"),
            ("17", "siedemnasta"),
            ("18", "osiemnasta"),
            ("19", "dziewiętnasta"),
            ("20", "dwudziesta"),
            ("21", "dwudziesta pierwsza"),
            ("22", "dwudziesta druga"),
            ("23", "dwudziesta trzecia"),
        ]
        hour_fst = pynini.string_map(hours_map)

        # Genitive hours mapping (for time ranges after "do", e.g. 17 -> siedemnastej)
        hours_gen_map = [
            ("0", "zera"),
            ("00", "zera"),
            ("1", "pierwszej"),
            ("01", "pierwszej"),
            ("2", "drugiej"),
            ("02", "drugiej"),
            ("3", "trzeciej"),
            ("03", "trzeciej"),
            ("4", "czwartej"),
            ("04", "czwartej"),
            ("5", "piątej"),
            ("05", "piątej"),
            ("6", "szóstej"),
            ("06", "szóstej"),
            ("7", "siódmej"),
            ("07", "siódmej"),
            ("8", "ósmej"),
            ("08", "ósmej"),
            ("9", "dziewiątej"),
            ("09", "dziewiątej"),
            ("10", "dziesiątej"),
            ("11", "jedenastej"),
            ("12", "dwunastej"),
            ("13", "trzynastej"),
            ("14", "czternastej"),
            ("15", "piętnastej"),
            ("16", "szesnastej"),
            ("17", "siedemnastej"),
            ("18", "osiemnastej"),
            ("19", "dziewiętnastej"),
            ("20", "dwudziestej"),
            ("21", "dwudziestej pierwszej"),
            ("22", "dwudziestej drugiej"),
            ("23", "dwudziestej trzeciej"),
        ]
        hour_gen_fst = pynini.string_map(hours_gen_map)

        # Minutes (00-59)
        zero_digit = pynini.cross("0", "zero ") + cardinal.digit
        min_00 = pynini.cross("00", "zero zero")
        tens_and_units = (NEMO_DIGIT**2) @ cardinal.graph
        min_fst = min_00 | zero_digit | tens_and_units

        # Seconds (00-59)
        sec_fst = min_fst

        # Core time: H:MM or HH:MM
        colon = pynutil.delete(":")
        h_m = hour_fst + colon + pynutil.insert(" ") + min_fst
        h_m_s = hour_fst + colon + pynutil.insert(" ") + min_fst + colon + pynutil.insert(" ") + sec_fst

        # Core time genitive (for ranges after "do")
        h_m_gen = hour_gen_fst + colon + pynutil.insert(" ") + min_fst
        h_m_s_gen = hour_gen_fst + colon + pynutil.insert(" ") + min_fst + colon + pynutil.insert(" ") + sec_fst

        # Midnight
        midnight = pynini.cross("00:00", "północ")

        core_time = midnight | h_m_s | h_m
        core_time_gen = h_m_s_gen | h_m_gen

        # AM / PM indicators
        am_marker = pynini.cross(pynini.union(" AM", " am", " A.M.", " a.m."), " rano")
        pm_marker = pynini.cross(
            pynini.union(" PM", " pm", " P.M.", " p.m."), " po południu"
        )
        opt_ampm = pynini.closure(am_marker | pm_marker, 0, 1)

        # Timezones (UTC, GMT, CET, CEST, etc.)
        tz_words = pynini.string_map(
            [
                ("UTC", "u t c"),
                ("GMT", "g m t"),
                ("CET", "c e t"),
                ("CEST", "c e s t"),
                ("EET", "e e t"),
                ("EEST", "e e s t"),
                ("PST", "p s t"),
                ("PDT", "p d t"),
                ("EST", "e s t"),
                ("EDT", "e d t"),
            ]
        )
        tz_offset = (
            pynini.cross(" ", " ")
            + tz_words
            + pynini.closure(
                (pynini.cross("+", " plus ") | pynini.cross(pynini.union("-", "−"), " minus "))
                + (NEMO_DIGIT** (1, 2) @ cardinal.graph),
                0,
                1,
            )
        )
        opt_tz = pynini.closure(tz_offset, 0, 1)

        time_single = (core_time + opt_ampm + opt_tz).optimize()
        time_single_gen = (core_time_gen + opt_ampm + opt_tz).optimize()

        # Time ranges: "9:00-17:00", "9:00–17:00" -> "dziewiąta zero zero do siedemnastej zero zero"
        dash = pynini.union("-", "–", "—")
        range_to = pynini.cross(dash, " do ")
        time_range = (
            core_time
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + range_to
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + time_single_gen
        )

        self.graph = (time_range | time_single).optimize()
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
