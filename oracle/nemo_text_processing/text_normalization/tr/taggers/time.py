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
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for clock times in Turkish:
    - 08:30 -> sekiz otuz
    - 14:15 -> on dört on beş
    - 12:00 -> on iki
    - 08:15:30 -> sekiz on beş otuz
    - saat 14:00 -> saat on dört
    - 14:30 UTC -> on dört otuz u t c
    - 09:00-17:00 -> dokuz ila on yedi
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        d1_to_9 = pynini.string_map([
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        tens_map = pynini.string_map([
            ("1", "on"),
            ("2", "yirmi"),
            ("3", "otuz"),
            ("4", "kırk"),
            ("5", "elli"),
        ])
        two_digits = (tens_map + pynutil.delete("0")) | (tens_map + pynutil.insert(" ") + d1_to_9)

        # Hours: 0 to 23
        hours_00 = pynini.cross("00", "sıfır sıfır") | pynini.cross("0", "sıfır")
        hours_1_9 = (pynini.closure(pynutil.delete("0"), 0, 1) + d1_to_9)
        hours_10_19 = pynini.cross("10", "on") | (pynini.cross("1", "on ") + d1_to_9)
        hours_20_23 = (
            pynini.cross("20", "yirmi")
            | pynini.cross("21", "yirmi bir")
            | pynini.cross("22", "yirmi iki")
            | pynini.cross("23", "yirmi üç")
        )
        hours = (hours_10_19 | hours_20_23 | hours_1_9 | hours_00).optimize()

        # Minutes: 00 to 59
        min_00 = pynini.cross("00", "sıfır sıfır")
        min_0x = pynini.cross("0", "sıfır ") + d1_to_9
        minutes_all = (min_00 | min_0x | two_digits).optimize()

        # Seconds: 00 to 59
        seconds_all = minutes_all

        # 1. HH:MM
        # When minutes are "00": "12:00" can be "on iki" or "on iki sıfır sıfır"
        hh_mm_exact_zero = hours + pynutil.delete(":") + pynutil.delete("00")
        hh_mm_with_min = hours + pynutil.delete(":") + pynutil.insert(" ") + (min_0x | two_digits)
        hh_mm_full = hh_mm_exact_zero | hh_mm_with_min

        # 2. HH:MM:SS
        hh_mm_ss = (
            hours
            + pynutil.delete(":")
            + pynutil.insert(" ")
            + minutes_all
            + pynutil.delete(":")
            + pynutil.insert(" ")
            + seconds_all
        )

        # 3. Timezones & AM/PM suffixes
        tz_words = pynini.string_map([
            ("UTC", "u t c"),
            ("GMT", "g m t"),
            ("CET", "c e t"),
            ("EET", "e e t"),
            ("EST", "e s t"),
            ("PST", "p s t"),
            ("TSİ", "t s i"),
            ("e.m. est", "e s t"),
            ("e.m. cet", "c e t"),
            ("e.m.", "öğleden sonra"),
            ("ö.s.", "öğleden sonra"),
            ("ö.ö.", "öğleden önce"),
        ])
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        time_base = (hh_mm_ss | hh_mm_full).optimize()

        time_with_tz = time_base + pynutil.delete(" ") + pynutil.insert(" ") + tz_words

        # 4. "saat" prefix: saat 12, saat 14:00, saat 14:30
        saat_prefix = (
            pynini.cross("saat ", "saat ")
            | pynini.cross("Saat ", "saat ")
            | pynini.cross("kl. ", "saat ")
        )
        time_with_saat = saat_prefix + (time_with_tz | time_base | hours)

        # 5. Time ranges: 09:00-17:00, 9:00–17:00, 9:30-18:15
        dash = pynini.union("-", "–", "—")
        time_range = (
            time_base
            + opt_sp
            + pynini.cross(dash, " ila ")
            + opt_sp
            + time_base
        )

        all_times = (
            time_range
            | time_with_saat
            | time_with_tz
            | time_base
        ).optimize()
        self.all_times = all_times

        self.fst = (pynutil.insert('name: "') + convert_space(all_times) + pynutil.insert('"')).optimize()
