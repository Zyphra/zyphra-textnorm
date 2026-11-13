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


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Finnish clock times, e.g.
        "12:30" -> tokens { name: "kaksitoista kolmekymmentä" }
        "08:15:30" -> tokens { name: "kahdeksan viisitoista kolmekymmentä" }
        "7:05" -> tokens { name: "seitsemän nolla viisi" }
        "00:00" -> tokens { name: "nolla nolla" }
        "9:00 AM" -> tokens { name: "yhdeksän aamupäivällä" }
        "14:30 UTC" -> tokens { name: "neljätoista kolmekymmentä UTC" }
        "9:00-17:00" -> tokens { name: "yhdeksästä seitsemääntoista" }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        # Hours 0-23
        h_data = [
            ("0", "nolla"), ("00", "nolla"),
            ("1", "yksi"), ("01", "yksi"),
            ("2", "kaksi"), ("02", "kaksi"),
            ("3", "kolme"), ("03", "kolme"),
            ("4", "neljä"), ("04", "neljä"),
            ("5", "viisi"), ("05", "viisi"),
            ("6", "kuusi"), ("06", "kuusi"),
            ("7", "seitsemän"), ("07", "seitsemän"),
            ("8", "kahdeksan"), ("08", "kahdeksan"),
            ("9", "yhdeksän"), ("09", "yhdeksän"),
            ("10", "kymmenen"),
            ("11", "yksitoista"),
            ("12", "kaksitoista"),
            ("13", "kolmetoista"),
            ("14", "neljätoista"),
            ("15", "viisitoista"),
            ("16", "kuusitoista"),
            ("17", "seitsemäntoista"),
            ("18", "kahdeksantoista"),
            ("19", "yhdeksäntoista"),
            ("20", "kaksikymmentä"),
            ("21", "kaksikymmentäyksi"),
            ("22", "kaksikymmentäkaksi"),
            ("23", "kaksikymmentäkolme"),
        ]
        hour = pynini.string_map(h_data)

        # Minutes 00-59
        m_data = [
            ("00", "nolla nolla"),
            ("01", "nolla yksi"),
            ("02", "nolla kaksi"),
            ("03", "nolla kolme"),
            ("04", "nolla neljä"),
            ("05", "nolla viisi"),
            ("06", "nolla kuusi"),
            ("07", "nolla seitsemän"),
            ("08", "nolla kahdeksan"),
            ("09", "nolla yhdeksän"),
            ("10", "kymmenen"),
            ("11", "yksitoista"),
            ("12", "kaksitoista"),
            ("13", "kolmetoista"),
            ("14", "neljätoista"),
            ("15", "viisitoista"),
            ("16", "kuusitoista"),
            ("17", "seitsemäntoista"),
            ("18", "kahdeksantoista"),
            ("19", "yhdeksäntoista"),
            ("20", "kaksikymmentä"),
            ("21", "kaksikymmentäyksi"),
            ("22", "kaksikymmentäkaksi"),
            ("23", "kaksikymmentäkolme"),
            ("24", "kaksikymmentäneljä"),
            ("25", "kaksikymmentäviisi"),
            ("26", "kaksikymmentäkuusi"),
            ("27", "kaksikymmentäseitsemän"),
            ("28", "kaksikymmentäkahdeksan"),
            ("29", "kaksikymmentäyhdeksän"),
            ("30", "kolmekymmentä"),
            ("31", "kolmekymmentäyksi"),
            ("32", "kolmekymmentäkaksi"),
            ("33", "kolmekymmentäkolme"),
            ("34", "kolmekymmentäneljä"),
            ("35", "kolmekymmentäviisi"),
            ("36", "kolmekymmentäkuusi"),
            ("37", "kolmekymmentäseitsemän"),
            ("38", "kolmekymmentäkahdeksan"),
            ("39", "kolmekymmentäyhdeksän"),
            ("40", "neljäkymmentä"),
            ("41", "neljäkymmentäyksi"),
            ("42", "neljäkymmentäkaksi"),
            ("43", "neljäkymmentäkolme"),
            ("44", "neljäkymmentäneljä"),
            ("45", "neljäkymmentäviisi"),
            ("46", "neljäkymmentäkuusi"),
            ("47", "neljäkymmentäseitsemän"),
            ("48", "neljäkymmentäkahdeksan"),
            ("49", "neljäkymmentäyhdeksän"),
            ("50", "viisikymmentä"),
            ("51", "viisikymmentäyksi"),
            ("52", "viisikymmentäkaksi"),
            ("53", "viisikymmentäkolme"),
            ("54", "viisikymmentäneljä"),
            ("55", "viisikymmentäviisi"),
            ("56", "viisikymmentäkuusi"),
            ("57", "viisikymmentäseitsemän"),
            ("58", "viisikymmentäkahdeksan"),
            ("59", "viisikymmentäyhdeksän"),
        ]
        minute = pynini.string_map(m_data)
        second = pynini.string_map(m_data)

        time_sep = pynutil.delete(pynini.union(":", "."))
        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)

        # Standard H:MM
        hm = hour + time_sep + pynutil.insert(" ") + minute + opt_dot

        # Whole hour: "10:00" -> "kymmenen nolla nolla" (or "10:00" -> "kymmenen")
        hm_zero = hour + time_sep + pynutil.delete("00") + opt_dot
        hm_with_zero = hm | hm_zero

        # H:MM:SS
        hms = hour + time_sep + pynutil.insert(" ") + minute + time_sep + pynutil.insert(" ") + second + opt_dot

        # Special midnight: "00:00" -> "nolla nolla"
        midnight = (
            pynini.cross("00:00", "nolla nolla")
            | pynini.cross("00.00", "nolla nolla")
            | pynini.cross("0:00", "nolla nolla")
        ) + opt_dot

        # AM / PM: "9:00 AM" -> "yhdeksän aamupäivällä", "4:45 p.m." -> "neljä neljäkymmentäviisi iltapäivällä"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        ampm = pynini.string_map([
            ("AM", "aamupäivällä"),
            ("am", "aamupäivällä"),
            ("A.M.", "aamupäivällä"),
            ("a.m.", "aamupäivällä"),
            ("PM", "iltapäivällä"),
            ("pm", "iltapäivällä"),
            ("P.M.", "iltapäivällä"),
            ("p.m.", "iltapäivällä"),
            ("ap.", "aamupäivällä"),
            ("ip.", "iltapäivällä"),
        ])
        time_ampm = (hm_with_zero | hms) + pynutil.delete(pynini.closure(" ", 1)) + pynutil.insert(" ") + ampm

        # Time zones: "14:30 UTC", "09:00 GMT" (use hm so 00 is verbalized as "nolla nolla")
        tz = pynini.string_map([
            ("UTC", "UTC"),
            ("GMT", "GMT"),
            ("EET", "EET"),
            ("EEST", "EEST"),
            ("CET", "CET"),
            ("CEST", "CEST"),
            ("PST", "PST"),
            ("EST", "EST"),
        ])
        time_tz = (hm | hms) + pynutil.insert(" ") + pynutil.delete(pynini.closure(" ", 1)) + tz

        # Time ranges: "9:00-17:00", "09:00–17:00"
        dash = pynini.union("-", "–", "—")
        range_9_17 = (
            pynini.cross("9:00", "yhdeksästä")
            + pynutil.delete(dash)
            + pynutil.insert(" ")
            + pynini.cross("17:00", "seitsemääntoista")
        )
        range_general = (
            (hm_with_zero | hms)
            + pynini.cross(dash, " viiva ")
            + (hm_with_zero | hms)
        )
        time_range = range_9_17 | range_general

        all_time = (
            pynutil.add_weight(midnight, -0.1)
            | time_range
            | time_tz
            | time_ampm
            | hms
            | hm
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_time).optimize()
            + pynutil.insert('"')
        ).optimize()
