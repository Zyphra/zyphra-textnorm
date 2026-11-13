# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.kn.graph_utils import (
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path

hours_graph = pynini.string_file(get_abs_path("data/time/hours.tsv"))
minutes_graph = pynini.string_file(get_abs_path("data/time/minutes.tsv"))
seconds_graph = pynini.string_file(get_abs_path("data/time/seconds.tsv"))

# CLDR kn day periods (morning1 ಬೆಳಗ್ಗೆ, afternoon1 ಮಧ್ಯಾಹ್ನ, evening1 ಸಂಜೆ, night1 ರಾತ್ರಿ)
MORNING = "ಬೆಳಗ್ಗೆ"
AFTERNOON = "ಮಧ್ಯಾಹ್ನ"
EVENING = "ಸಂಜೆ"
NIGHT = "ರಾತ್ರಿ"


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time (ASCII or Kannada digits), e.g.
        12:30:30 -> time { hours: "ಹನ್ನೆರಡು" minutes: "ಮೂವತ್ತು" seconds: "ಮೂವತ್ತು" }
        1:40 -> time { hours: "ಒಂದು" minutes: "ನಲವತ್ತು" }
        1:00 -> time { hours: "ಒಂದು" }
        7:30 pm -> time { day_period: "ಸಂಜೆ" hours: "ಏಳು" minutes: "ಮೂವತ್ತು" }
        14:30 UTC -> time { hours: "ಹದಿನಾಲ್ಕು" minutes: "ಮೂವತ್ತು" zone: "ಯು ಟಿ ಸಿ" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="classify")

        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        hours_mapped = pynini.compose(to_ascii, hours_graph)
        minutes_mapped = pynini.compose(to_ascii, minutes_graph)
        seconds_mapped = pynini.compose(to_ascii, seconds_graph)

        # Day period tag
        am_trigger = pynini.union("am", "AM", "a.m.", "A.M.", "ಬೆಳಗ್ಗೆ")
        pm_trigger = pynini.union("pm", "PM", "p.m.", "P.M.", "ಮಧ್ಯಾಹ್ನ", "ಸಂಜೆ", "ರಾತ್ರಿ")

        # Map trigger to standard Kannada period
        am_tag = pynutil.insert("day_period: \"") + pynini.cross(am_trigger, MORNING) + pynutil.insert("\" ")
        pm_tag = pynutil.insert("day_period: \"") + (
            pynini.cross(pynini.union("pm", "PM", "p.m.", "P.M."), EVENING)
            | pynini.cross("ಮಧ್ಯಾಹ್ನ", AFTERNOON)
            | pynini.cross("ಸಂಜೆ", EVENING)
            | pynini.cross("ರಾತ್ರಿ", NIGHT)
        ) + pynutil.insert("\" ")

        day_period = am_tag | pm_tag

        # Time zone
        zone_map = pynini.string_map(
            [
                ("UTC", "ಯು ಟಿ ಸಿ"),
                ("GMT", "ಜಿ ಎಮ್ ಟಿ"),
                ("IST", "ಐ ಎಸ್ ಟಿ"),
                ("PST", "ಪಿ ಎಸ್ ಟಿ"),
                ("EST", "ಇ ಎಸ್ ಟಿ"),
            ]
        )
        zone = pynutil.insert("zone: \"") + zone_map + pynutil.insert("\"")
        opt_zone = pynini.closure(pynutil.delete(" ") + insert_space + zone, 0, 1)

        colon = pynutil.delete(":")

        h = pynutil.insert("hours: \"") + hours_mapped + pynutil.insert("\"")
        m = pynutil.insert("minutes: \"") + minutes_mapped + pynutil.insert("\"")
        s = pynutil.insert("seconds: \"") + seconds_mapped + pynutil.insert("\"")

        # 00 minutes: 1:00 -> hours: "ಒಂದು"
        m_zero = pynutil.delete("00") | pynutil.delete("೦೦")

        hms = h + colon + insert_space + m + colon + insert_space + s
        hm = h + colon + insert_space + m
        h_exact = h + colon + m_zero

        am = pynini.union("am", "AM", "a.m.", "A.M.", "Am")
        pm = pynini.union("pm", "PM", "p.m.", "P.M.", "Pm")

        def hours_12(ascii_hours):
            return pynini.compose(pynini.union(*ascii_hours), hours_mapped)

        twelve_hour_cases = [
            (am, ["4", "5", "6", "7", "8", "9", "10", "11", "04", "05", "06", "07", "08", "09"], MORNING),
            (am, ["12", "1", "2", "3", "01", "02", "03"], NIGHT),
            (pm, ["12", "1", "2", "3", "01", "02", "03"], AFTERNOON),
            (pm, ["4", "5", "6", "7", "8", "04", "05", "06", "07", "08"], EVENING),
            (pm, ["9", "10", "11", "09"], NIGHT),
        ]
        graph_12 = None
        for marker, hour_list, period in twelve_hour_cases:
            h_c = pynutil.insert('hours: "') + hours_12(hour_list) + pynutil.insert('"')
            body = (
                h_c + colon + insert_space + m
                | h_c + colon + m_zero
                | h_c
            )
            g = (
                pynutil.insert(f'day_period: "{period}" ')
                + body
                + opt_space
                + pynutil.delete(marker)
                + opt_zone
            )
            graph_12 = g if graph_12 is None else graph_12 | g

        range_dash = pynini.cross(pynini.union("-", "–", " - ", " – "), " ರಿಂದ ")
        time_range = (
            pynutil.insert('hours: "')
            + hours_mapped
            + colon + m_zero
            + pynutil.insert(" ಗಂಟೆ")
            + range_dash
            + hours_mapped
            + colon + m_zero
            + pynutil.insert('"')
        )

        plain_time = (hms | hm | h_exact) + opt_zone
        final_graph = (pynutil.add_weight(graph_12, -0.1) | time_range | plain_time).optimize()
        self.fst = self.add_tokens(final_graph)
