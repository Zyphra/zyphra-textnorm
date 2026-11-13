# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Dutch time expressions.
    Handles:
    - Standard clock times: 12:30 -> twaalf uur dertig, 10:00 -> tien uur, 7:05 -> zeven uur vijf
    - Midnight: 00:00 -> nul uur, 00:30 -> nul uur dertig
    - Times with seconds: 08:15:30 -> acht uur vijftien en dertig seconden
    - AM / PM: 9:00 AM -> negen uur 's ochtends, 4:45 p.m. -> vier uur vijfundertig 's middags
    - Timezones: 14:30 UTC -> veertien uur dertig u t c
    - Timezone offsets: 14:00 UTC+10 -> veertien uur u t c plus tien
    - Time ranges: 9:00-17:00 -> negen uur tot zeventien uur
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        dash = pynini.union("-", "–", "—")

        # Hours: 0 to 23
        hours_map = [
            ("0", "nul"),
            ("00", "nul"),
            ("1", "een"),
            ("01", "een"),
            ("2", "twee"),
            ("02", "twee"),
            ("3", "drie"),
            ("03", "drie"),
            ("4", "vier"),
            ("04", "vier"),
            ("5", "vijf"),
            ("05", "vijf"),
            ("6", "zes"),
            ("06", "zes"),
            ("7", "zeven"),
            ("07", "zeven"),
            ("8", "acht"),
            ("08", "acht"),
            ("9", "negen"),
            ("09", "negen"),
            ("10", "tien"),
            ("11", "elf"),
            ("12", "twaalf"),
            ("13", "dertien"),
            ("14", "veertien"),
            ("15", "vijftien"),
            ("16", "zestien"),
            ("17", "zeventien"),
            ("18", "achttien"),
            ("19", "negentien"),
            ("20", "twintig"),
            ("21", "eenentwintig"),
            ("22", "tweeëntwintig"),
            ("23", "drieëntwintig"),
        ]
        hour_fst = pynini.string_map(hours_map).optimize()

        # Minutes: 00 to 59
        # 00 -> "" (just "tien uur")
        # 01-09 -> "nul een" or "vijf"
        # 10-59 -> cardinal word
        min_00 = pynutil.delete("00")
        min_0x = pynini.cross("0", "nul ") + cardinal.digit
        min_0x |= pynutil.delete("0") + cardinal.digit
        min_xx = cardinal.nums_1_to_99
        minute_fst = min_00 | min_0x | min_xx

        # Seconds: 00 to 59
        sec_fst = (
            pynutil.insert(" en ")
            + (
                pynini.cross("0", "nul ") + cardinal.digit
                | cardinal.nums_0_to_99
            )
            + pynutil.insert(" seconden")
        )

        # Base HH:MM:
        # If min_00: "uur"
        # If not min_00: "uur " + minutes
        time_hm = (
            hour_fst
            + pynutil.delete(":")
            + (
                min_00 + pynutil.insert(" uur")
                | (pynutil.insert(" uur ") + (min_0x | min_xx))
            )
        )

        # Base HH:MM:SS:
        time_hms = (
            hour_fst
            + pynutil.delete(":")
            + (
                min_00 + pynutil.insert(" uur nul")
                | (pynutil.insert(" uur ") + (min_0x | min_xx))
            )
            + pynutil.delete(":")
            + sec_fst
        )

        # AM / PM indicators
        am_pat = pynini.union("AM", "A.M.", "am", "a.m.")
        pm_pat = pynini.union("PM", "P.M.", "pm", "p.m.")
        am_fst = pynini.cross(am_pat, " 's ochtends")
        pm_fst = pynini.cross(pm_pat, " 's middags")

        time_ampm = (
            (time_hm | time_hms)
            + opt_space
            + (am_fst | pm_fst)
        )

        # Timezones: UTC, GMT, CET, CEST
        tz_map = pynini.string_map(
            [
                ("UTC", " u t c"),
                ("GMT", " g m t"),
                ("CET", " c e t"),
                ("CEST", " c e s t"),
            ]
        )
        # Offsets: UTC+10, UTC-10, UTC−10
        offset_sign = pynini.cross("+", " plus ") | pynini.cross("-", " min ") | pynini.cross("−", " min ")
        tz_offset = (
            tz_map
            + offset_sign
            + cardinal.nums_1_to_99
        )
        time_tz = (
            (time_hm | time_hms | time_ampm)
            + opt_space
            + (tz_offset | tz_map)
        )

        # Time ranges: 9:00-17:00, 09:00–17:00
        time_range = (
            (
                time_hm
                + delete_space
                + pynini.cross(dash, " tot ")
                + delete_space
                + (time_hm | hour_fst + pynutil.insert(" uur"))
            )
            | (
                hour_fst
                + pynutil.insert(" uur")
                + delete_space
                + pynini.cross(dash, " tot ")
                + delete_space
                + time_hm
            )
        )

        self.spoken_time = (
            pynutil.add_weight(time_tz, 0.94)
            | pynutil.add_weight(time_ampm, 0.95)
            | pynutil.add_weight(time_range, 0.96)
            | pynutil.add_weight(time_hms, 0.97)
            | pynutil.add_weight(time_hm, 1.0)
        ).optimize()

        self.fst = wrap_name(self.spoken_time)
