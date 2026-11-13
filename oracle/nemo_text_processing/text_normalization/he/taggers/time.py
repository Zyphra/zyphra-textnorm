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
    insert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew clock times.
    e.g. 12:30 -> שתים עשרה שלושים
         10:00 -> עשר
         08:15:30 -> שמונה חמש עשרה ושלושים שניות
         14:30 UTC -> ארבע עשרה שלושים יוטוסי
         9:00-17:00 -> תשע עד שבע עשרה
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        colon = pynutil.delete(":")

        hours_map = [
            ("0", "חצות"),
            ("00", "חצות"),
            ("1", "אחת"),
            ("01", "אחת"),
            ("2", "שתיים"),
            ("02", "שתיים"),
            ("3", "שלוש"),
            ("03", "שלוש"),
            ("4", "ארבע"),
            ("04", "ארבע"),
            ("5", "חמש"),
            ("05", "חמש"),
            ("6", "שש"),
            ("06", "שש"),
            ("7", "שבע"),
            ("07", "שבע"),
            ("8", "שמונה"),
            ("08", "שמונה"),
            ("9", "תשע"),
            ("09", "תשע"),
            ("10", "עשר"),
            ("11", "אחת עשרה"),
            ("12", "שתים עשרה"),
            ("13", "שלוש עשרה"),
            ("14", "ארבע עשרה"),
            ("15", "חמש עשרה"),
            ("16", "שש עשרה"),
            ("17", "שבע עשרה"),
            ("18", "שמונה עשרה"),
            ("19", "תשע עשרה"),
            ("20", "עשרים"),
            ("21", "עשרים ואחת"),
            ("22", "עשרים ושתיים"),
            ("23", "עשרים ושלוש"),
            ("24", "עשרים וארבע"),
        ]
        hours_fst = pynini.string_map(hours_map)
        self.hours_fst = hours_fst

        # Minutes (00-59)
        min_00 = pynutil.delete("00")
        min_01_09 = pynini.cross("0", "אפס ") + cardinal.digit_f
        min_10_59 = cardinal.two_digits_f
        minutes_fst = min_01_09 | min_10_59
        self.minutes_fst = minutes_fst

        # Seconds (00-59)
        sec_fst = (min_01_09 | min_10_59) + pynutil.insert(" שניות")

        # Timezones
        tz_map = [
            ("UTC", " יוטוסי"),
            ("GMT", " ג׳יאמטי"),
            ("EST", " אי אס טי"),
            ("PST", " פי אס טי"),
            ("CET", " סי אי טי"),
            ("IDT", " שעון ישראל"),
            ("IST", " שעון ישראל"),
        ]
        timezones_fst = pynini.string_map(tz_map)

        # Base time: HH:MM
        time_exact_hour = hours_fst + colon + min_00
        time_with_minutes = hours_fst + colon + pynutil.insert(" ") + minutes_fst

        time_hm = time_exact_hour | time_with_minutes
        self.time_hm = time_hm

        # Time with seconds: HH:MM:SS
        time_hms = (
            time_hm
            + colon
            + pynutil.insert(" ו")
            + sec_fst
        )

        time_core = (pynutil.add_weight(time_hms, 0.9) | pynutil.add_weight(time_hm, 1.0)).optimize()

        # Time with timezone
        time_tz = time_core + opt_space + timezones_fst

        # Time ranges: 9:00-17:00, 09:00–17:00
        dash = pynini.union("-", "–", "—", "־")
        time_range = (
            time_hm
            + opt_space
            + pynini.cross(dash, " עד ")
            + opt_space
            + time_hm
        ).optimize()

        all_times = (
            pynutil.add_weight(time_tz, 0.9)
            | pynutil.add_weight(time_range, 0.92)
            | pynutil.add_weight(time_core, 1.0)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_times) + pynutil.insert('"')
        ).optimize()
