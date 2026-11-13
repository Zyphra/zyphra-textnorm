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
)
from nemo_text_processing.text_normalization.ro.graph_utils import (
    RO_DASH,
    to_name_token,
)
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Romanian clock times, e.g.
        "12:30" -> tokens { name: "douăsprezece și jumătate" }
        "7:05" -> tokens { name: "șapte și cinci" }
        "00:00" -> tokens { name: "miezul nopții" }
        "00:30" -> tokens { name: "zero și treizeci de minute" }
        "08:15:30" -> tokens { name: "opt și cincisprezece minute și treizeci de secunde" }
        "14:30 UTC" -> tokens { name: "paisprezece și treizeci U T C" }
        "14:30 GMT-4:30" -> tokens { name: "paisprezece și treizeci G M T minus patru și treizeci" }
        "09:00 GMT" -> tokens { name: "nouă fix G M T" }
        "9 am" -> tokens { name: "nouă dimineața" }
        "2:30 pm" -> tokens { name: "două și jumătate după-amiaza" }
        "8:15 pm" -> tokens { name: "opt și un sfert seara" }
        "9:00-17:00" -> tokens { name: "nouă la șaptesprezece" }
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        # Hours mapping
        hours_map = pynini.string_map([
            ("0", "zero"), ("00", "zero"),
            ("1", "unu"), ("01", "unu"),
            ("2", "două"), ("02", "două"),
            ("3", "trei"), ("03", "trei"),
            ("4", "patru"), ("04", "patru"),
            ("5", "cinci"), ("05", "cinci"),
            ("6", "șase"), ("06", "șase"),
            ("7", "șapte"), ("07", "șapte"),
            ("8", "opt"), ("08", "opt"),
            ("9", "nouă"), ("09", "nouă"),
            ("10", "zece"),
            ("11", "unsprezece"),
            ("12", "douăsprezece"),
            ("13", "treisprezece"),
            ("14", "paisprezece"),
            ("15", "cincisprezece"),
            ("16", "șaisprezece"),
            ("17", "șaptesprezece"),
            ("18", "optsprezece"),
            ("19", "nouăsprezece"),
            ("20", "douăzeci"),
            ("21", "douăzeci și unu"),
            ("22", "douăzeci și două"),
            ("23", "douăzeci și trei"),
        ])

        # Exact special hour: 00:00 -> miezul nopții
        midnight = pynini.cross("00:00", "miezul nopții")

        # Minutes mapping
        # 30 -> "și jumătate", 15 -> "și un sfert" or "și cincisprezece"
        minutes_map = pynini.string_map([
            ("00", ""),
            ("01", " și un minut"),
            ("02", " și două minute"),
            ("03", " și trei minute"),
            ("04", " și patru minute"),
            ("05", " și cinci"),
            ("10", " și zece"),
            ("15", " și cincisprezece"),
            ("20", " și douăzeci de minute"),
            ("25", " și douăzeci și cinci de minute"),
            ("30", " și treizeci de minute"),
            ("35", " și treizeci și cinci de minute"),
            ("40", " și patruzeci de minute"),
            ("45", " și patruzeci și cinci de minute"),
            ("50", " și cincizeci de minute"),
            ("55", " și cincizeci și cinci de minute"),
        ])

        # Natural colloquial half / quarter forms
        minutes_colloquial = pynini.string_map([
            ("15", " și un sfert"),
            ("30", " și jumătate"),
            ("05", " și cinci"),
        ])

        # General minute
        gen_minute = pynutil.insert(" și ") + cardinal.cardinal_numbers + pynutil.insert(" de minute")

        valid_minutes = pynini.union("0", "1", "2", "3", "4", "5") + NEMO_DIGIT
        minute_part = valid_minutes @ (minutes_colloquial | minutes_map | gen_minute)

        # Seconds part
        sec_30 = pynini.cross(":30", " și treizeci de secunde")
        sec_15 = pynini.cross(":15", " și cincisprezece secunde")
        sec_00 = pynutil.delete(":00")
        minute_number = valid_minutes @ cardinal.cardinal_numbers
        sec_gen = pynutil.delete(":") + pynutil.insert(" și ") + minute_number + pynutil.insert(" de secunde")
        sec_part = sec_00 | sec_30 | sec_15 | sec_gen

        # Core time: 12:30 -> douăsprezece și jumătate
        time_core = (hours_map + pynutil.delete(":") + minute_part).optimize()

        # Core time with seconds: 08:15:30 -> opt și cincisprezece minute și treizeci de secunde
        # For 08:15:30 we prefer explicit "minute" before "secunde"
        h_part = hours_map
        m_part_for_sec = pynutil.delete(":") + pynutil.insert(" și ") + minute_number + pynutil.insert(" minute")
        time_with_sec = (h_part + m_part_for_sec + sec_part).optimize()

        # Day periods: am / pm
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        am_suffix = opt_space + pynutil.delete(pynini.union("am", "a.m.", "AM", "A.M.")) + pynutil.insert(" dimineața")
        pm_afternoon = opt_space + pynutil.delete(pynini.union("pm", "p.m.", "PM", "P.M.")) + pynutil.insert(" după-amiaza")
        pm_evening = opt_space + pynutil.delete(pynini.union("pm", "p.m.", "PM", "P.M.")) + pynutil.insert(" seara")

        # 9 am -> nouă dimineața
        bare_hour_am = hours_map + am_suffix
        bare_hour_pm = hours_map + (pm_evening | pm_afternoon)

        # 2:30 pm -> două și jumătate după-amiaza
        # 8:15 pm -> opt și un sfert seara
        time_am_pm = (
            (hours_map + pynutil.delete(":") + minute_part + (pm_evening | pm_afternoon | am_suffix))
            | bare_hour_am
            | bare_hour_pm
        ).optimize()

        # Timezones: UTC, GMT
        tz_word = pynini.string_map([
            ("UTC", "U T C"),
            ("GMT", "G M T"),
            ("CET", "C E T"),
            ("EET", "E E T"),
        ])
        # 09:00 GMT -> nouă fix G M T
        whole_hour_fix = hours_map + pynutil.delete(":00") + pynutil.insert(" fix")

        # Timezone offsets: GMT-4:30 -> G M T minus patru și treizeci
        offset_minus = pynutil.delete(pynini.union("-", "−")) + pynutil.insert(" minus ")
        offset_plus = pynutil.delete("+") + pynutil.insert(" plus ")
        offset_time = hours_map + pynutil.delete(":") + pynutil.insert(" și ") + minute_number
        tz_offset = tz_word + (offset_minus | offset_plus) + (offset_time | cardinal.cardinal_numbers)

        # 14:30 UTC -> paisprezece și treizeci U T C
        # 14:30 GMT-4:30 -> paisprezece și treizeci G M T minus patru și treizeci
        time_with_tz = (
            (hours_map + pynutil.delete(":") + (pynutil.insert(" și ") + minute_number) | whole_hour_fix | time_core)
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + (tz_offset | tz_word)
        ).optimize()

        # Time range: 9:00-17:00 -> nouă la șaptesprezece
        simple_time = (
            hours_map + pynutil.delete(":00")
            | (hours_map + pynutil.delete(":") + minute_part)
        )
        time_range = (
            simple_time
            + opt_space
            + pynini.cross(RO_DASH, " la ")
            + opt_space
            + simple_time
        ).optimize()

        composite = (
            midnight
            | time_range
            | time_with_tz
            | time_with_sec
            | time_am_pm
            | time_core
        ).optimize()

        self.fst = to_name_token(composite)
