# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path

hours_graph = pynini.string_file(get_abs_path("data/time/hours.tsv"))
minutes_graph = pynini.string_file(get_abs_path("data/time/minutes.tsv"))
seconds_graph = pynini.string_file(get_abs_path("data/time/seconds.tsv"))

# CLDR ml day periods
MORNING = "രാവിലെ"
AFTERNOON = "ഉച്ചയ്ക്ക്"
EVENING = "വൈകുന്നേരം"
NIGHT = "രാത്രി"


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time, e.g.
        10:30 -> time { hours: "പത്ത്" minutes: "മുപ്പത്" }
        7:00 -> time { hours: "ഏഴ്" }
        1:00 -> time { hours: "ഒരു" }
        7:30 pm -> time { day_period: "വൈകുന്നേരം" hours: "ഏഴ്" minutes: "മുപ്പത്" }
        8 am -> time { day_period: "രാവിലെ" hours: "എട്ട്" }
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="classify")

        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()
        delete_colon = pynutil.delete(":")

        hours = pynini.compose(to_ascii, hours_graph).optimize()
        two_digit = pynini.closure(TO_ASCII_DIGIT, 2, 2).optimize()
        minutes = pynini.compose(two_digit, minutes_graph).optimize()
        seconds = pynini.compose(to_ascii, seconds_graph).optimize()
        double_zero = pynini.compose(to_ascii, pynini.accep("00")).optimize()

        self.hours = pynutil.insert("hours: \"") + hours + pynutil.insert("\" ")
        self.minutes = pynutil.insert("minutes: \"") + minutes + pynutil.insert("\" ")
        self.seconds = pynutil.insert("seconds: \"") + seconds + pynutil.insert("\" ")

        tz_map = pynini.string_map(
            [
                ("UTC", "യു ടി സി"),
                ("GMT", "ജി എം ടി"),
                ("IST", "ഐ എസ് ടി"),
                ("EST", "ഇ എസ് ടി"),
                ("EDT", "ഇ ഡി ടി"),
                ("CST", "സി എസ് ടി"),
                ("CDT", "സി ഡി ടി"),
                ("PST", "പി എസ് ടി"),
                ("PDT", "പി ഡി ടി"),
                ("CET", "സി ഇ ടി"),
                ("BST", "ബി എസ് ടി"),
            ]
        )
        optional_zone = pynini.closure(
            pynutil.delete(" ") + pynutil.insert("zone: \"") + tz_map + pynutil.insert("\" "), 0, 1
        )

        graph_hms = (
            self.hours
            + delete_colon
            + insert_space
            + self.minutes
            + delete_colon
            + insert_space
            + self.seconds
            + optional_zone
        )
        graph_hm = self.hours + delete_colon + insert_space + self.minutes + optional_zone
        graph_h = self.hours + delete_colon + pynutil.delete(double_zero) + optional_zone
        graph_24 = graph_hms | pynutil.add_weight(graph_hm, 0.3) | pynutil.add_weight(graph_h, 0.2)

        # 12-hour clock with am/pm
        def hours_12(ascii_hours):
            return pynini.compose(pynini.union(*ascii_hours), hours_graph)

        am = pynini.union("am", "AM", "a.m.", "A.M.", "Am")
        pm = pynini.union("pm", "PM", "p.m.", "P.M.", "Pm")
        twelve_hour_cases = [
            (am, ["6", "7", "8", "9", "10", "11", "06", "07", "08", "09"], MORNING),
            (am, ["12", "1", "2", "3", "4", "5", "01", "02", "03", "04", "05"], NIGHT),
            (pm, ["12", "1", "2", "3", "01", "02", "03"], AFTERNOON),
            (pm, ["4", "5", "6", "7", "04", "05", "06", "07"], EVENING),
            (pm, ["8", "9", "10", "11", "08", "09"], NIGHT),
        ]
        graph_12 = None
        for marker, hour_list, period in twelve_hour_cases:
            h = pynutil.insert("hours: \"") + hours_12(hour_list) + pynutil.insert("\" ")
            body = (
                h + delete_colon + insert_space + self.minutes
                | h + delete_colon + pynutil.delete("00")
                | h
            )
            g = (
                pynutil.insert(f"day_period: \"{period}\" ")
                + body
                + pynini.closure(pynutil.delete(" "), 0, 1)
                + pynutil.delete(marker)
                + optional_zone
            )
            graph_12 = g if graph_12 is None else graph_12 | g

        final_graph = graph_24 | pynutil.add_weight(graph_12, -0.1)
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
