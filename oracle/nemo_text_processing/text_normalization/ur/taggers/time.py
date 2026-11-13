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

from nemo_text_processing.text_normalization.ur.graph_utils import (
    NEMO_SPACE,
    UR_DEDH,
    UR_DHAI,
    UR_PAUNE,
    UR_SADHE,
    UR_SAVA,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ur.utils import get_abs_path, load_labels

TIME_DOUBLE_ZERO = "00"
TIME_FIFTEEN = ":15"
TIME_THIRTY = ":30"
TIME_FORTYFIVE = ":45"

hours_graph = pynini.string_file(get_abs_path("data/time/hours.tsv"))
minutes_graph = pynini.string_file(get_abs_path("data/time/minutes.tsv"))
seconds_graph = pynini.string_file(get_abs_path("data/time/seconds.tsv"))

AM = pynini.union("am", "AM", "a.m.", "A.M.")
PM = pynini.union("pm", "PM", "p.m.", "P.M.")


def day_period(hour: int, pm: bool) -> str:
    """CLDR release-49 ur day periods (dayPeriods.xml): 04-12 صبح, 12-16 دوپہر, 16-18 سہ پہر, 18-20 شام, 20-04 رات."""
    hour24 = hour % 12 + (12 if pm else 0)
    if 4 <= hour24 < 12:
        return "صبح"
    if 12 <= hour24 < 16:
        return "دوپہر"
    if 16 <= hour24 < 18:
        return "سہ پہر"
    if 18 <= hour24 < 20:
        return "شام"
    return "رات"


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time, e.g.
        12:30:30  -> time { hours: "بارہ" minutes: "تیس" seconds: "تیس" }
        1:40  -> time { hours: "ایک" minutes: "چالیس" }
        1:00  -> time { hours: "ایک" }
        10:30 am -> time { hours: "دس" minutes: "تیس" suffix: "صبح" }
        2:15  -> time { morphosyntactic_features: "سوا دو" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="classify")

        delete_colon = pynutil.delete(":")
        cardinal_graph = cardinal.digit | cardinal.teens_and_ties

        self.hours = pynutil.insert("hours: \"") + hours_graph + pynutil.insert("\" ")
        self.minutes = pynutil.insert("minutes: \"") + minutes_graph + pynutil.insert("\" ")
        self.seconds = pynutil.insert("seconds: \"") + seconds_graph + pynutil.insert("\" ")

        # hour minute seconds
        graph_hms = (
            self.hours + delete_colon + insert_space + self.minutes + delete_colon + insert_space + self.seconds
        )

        # hour minute
        graph_hm = self.hours + delete_colon + insert_space + self.minutes

        # hour
        graph_h = self.hours + delete_colon + pynutil.delete(TIME_DOUBLE_ZERO)

        dedh_dhai_graph = pynini.string_map([("1:30", UR_DEDH), ("2:30", UR_DHAI)])

        savva_numbers = cardinal_graph + pynini.cross(TIME_FIFTEEN, "")
        savva_graph = pynutil.insert(UR_SAVA) + pynutil.insert(NEMO_SPACE) + savva_numbers

        sadhe_numbers = cardinal_graph + pynini.cross(TIME_THIRTY, "")
        sadhe_graph = pynutil.insert(UR_SADHE) + pynutil.insert(NEMO_SPACE) + sadhe_numbers

        paune = pynini.string_file(get_abs_path("data/whitelist/paune_mappings.tsv"))
        paune_numbers = paune + pynini.cross(TIME_FORTYFIVE, "")
        paune_graph = pynutil.insert(UR_PAUNE) + pynutil.insert(NEMO_SPACE) + paune_numbers

        graph_dedh_dhai = (
            pynutil.insert("morphosyntactic_features: \"")
            + dedh_dhai_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        graph_savva = (
            pynutil.insert("morphosyntactic_features: \"")
            + savva_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        graph_sadhe = (
            pynutil.insert("morphosyntactic_features: \"")
            + sadhe_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        graph_paune = (
            pynutil.insert("morphosyntactic_features: \"")
            + paune_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        # 12-hour clock with am / pm: the day-period word depends on the hour, so every hour 1-12 is spelled out.
        hour_names = dict(load_labels(get_abs_path("data/time/hours.tsv")))
        after_hour = (
            delete_colon + insert_space + self.minutes + pynini.closure(delete_colon + insert_space + self.seconds, 0, 1)
        ) | pynutil.delete(":" + TIME_DOUBLE_ZERO) | pynutil.insert("")
        ampm_graphs = []
        for hour in range(1, 13):
            hour_input = pynini.union(str(hour), f"{hour:02d}")
            hour_tag = pynini.cross(hour_input, f"hours: \"{hour_names[str(hour)]}\" ")
            for marker, pm in ((AM, False), (PM, True)):
                ampm_graphs.append(
                    pynutil.insert(f'suffix: "{day_period(hour, pm)}" ')
                    + hour_tag
                    + after_hour
                    + pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)
                    + pynutil.delete(marker)
                )
        graph_ampm = pynini.union(*ampm_graphs).optimize()

        base_time = (
            graph_hms
            | pynutil.add_weight(graph_hm, 0.3)
            | pynutil.add_weight(graph_h, 0.3)
            | pynutil.add_weight(graph_dedh_dhai, 0.1)
            | pynutil.add_weight(graph_savva, 0.2)
            | pynutil.add_weight(graph_sadhe, 0.2)
            | pynutil.add_weight(graph_paune, 0.1)
            | graph_ampm
        ).optimize()

        tz_map = pynini.string_map(
            [
                ("UTC", "یو ٹی سی"),
                ("GMT", "جی ایم ٹی"),
                ("PKT", "پی کے ٹی"),
                ("IST", "آئی ایس ٹی"),
                ("EST", "ای ایس ٹی"),
                ("EDT", "ای ڈی ٹی"),
                ("CST", "سی ایس ٹی"),
                ("CDT", "سی ڈی ٹی"),
                ("MST", "ایم ایس ٹی"),
                ("MDT", "ایم ڈی ٹی"),
                ("PST", "پی ایس ٹی"),
                ("PDT", "پی ڈی ٹی"),
                ("CET", "سی ای ٹی"),
                ("CEST", "سی ای ایس ٹی"),
                ("GST", "جی ایس ٹی"),
                ("AST", "اے ایس ٹی"),
            ]
        )
        offset_num = pynini.string_map([(str(i), hour_names[str(i)]) for i in range(1, 13)])
        tz_offset = pynini.closure(
            (pynini.cross("+", " جمع ") | pynini.cross("-", " منفی ")) + offset_num,
            0,
            1,
        )
        zone_component = (
            pynutil.delete(" ")
            + pynutil.insert(' zone: "')
            + tz_map
            + tz_offset
            + pynutil.insert('"')
        )
        graph_tz = (base_time + zone_component).optimize()

        # Time ranges: "9:00-17:00", "09:00–17:00", "9 am - 5 pm"
        from nemo_text_processing.text_normalization.ur.verbalizers.time import TimeFst as TimeVerbalizer

        time_spoken = (self.add_tokens(base_time) @ TimeVerbalizer(cardinal=cardinal).fst).optimize()
        dash = pynini.union("-", "–", " - ", " – ")
        graph_time_range = (
            pynutil.insert('morphosyntactic_features: "')
            + time_spoken
            + pynini.cross(dash, " سے ")
            + time_spoken
            + pynutil.insert('"')
        ).optimize()
        graph_time_range_tz = (graph_time_range + pynini.closure(zone_component, 0, 1)).optimize()

        final_graph = base_time | pynutil.add_weight(graph_tz, -0.05) | pynutil.add_weight(graph_time_range_tz, -0.05)

        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
