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

from nemo_text_processing.text_normalization.mr.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.mr.utils import get_abs_path

MR_DOUBLE_ZERO = pynini.union("००", "00")

hours_graph = pynini.string_file(get_abs_path("data/time/hours.tsv"))
minutes_graph = pynini.string_file(get_abs_path("data/time/minutes.tsv"))
seconds_graph = pynini.string_file(get_abs_path("data/time/seconds.tsv"))

_TIME_ZONES = [
    ("UTC", "यू टी सी"),
    ("GMT", "जी एम टी"),
    ("IST", "आय एस टी"),
    ("EST", "ई एस टी"),
    ("EDT", "ई डी टी"),
    ("CST", "सी एस टी"),
    ("CDT", "सी डी टी"),
    ("MST", "एम एस टी"),
    ("MDT", "एम डी टी"),
    ("PST", "पी एस टी"),
    ("PDT", "पी डी टी"),
    ("CET", "सी ई टी"),
    ("CEST", "सी ई एस टी"),
    ("BST", "बी एस टी"),
    ("JST", "जे एस टी"),
    ("KST", "के एस टी"),
    ("AEST", "ए ई एस टी"),
]

# Day-period words for 12-hour input, by hour, following the CLDR release-49 mr day periods
# (04-06 पहाट, 06-12 सकाळ, 12-16 दुपार, 16-21 संध्याकाळ, 21-04 रात्र), in their locative form.
_AM_PERIODS = {12: "रात्री", 1: "रात्री", 2: "रात्री", 3: "रात्री", 4: "पहाटे", 5: "पहाटे"}
_PM_PERIODS = {12: "दुपारी", 1: "दुपारी", 2: "दुपारी", 3: "दुपारी", 9: "रात्री", 10: "रात्री", 11: "रात्री"}
_DEVA = "०१२३४५६७८९"

def _hour_forms(h: int):
    forms = {str(h), "".join(_DEVA[int(c)] for c in str(h))}
    if h < 10:
        forms |= {f"0{h}", f"०{_DEVA[h]}"}
    return forms


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time, e.g.
        १२:३०:३०  -> time { hours: "बारा" minutes: "तीस" seconds: "तीस" }
        १:४०  -> time { hours: "एक" minutes: "चाळीस" }
        १:००  -> time { hours: "एक" }
        7:30 pm -> time { period: "संध्याकाळी" hours: "सात" minutes: "तीस" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="classify")

        delete_colon = pynutil.delete(":")

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
        graph_h = self.hours + delete_colon + pynutil.delete(MR_DOUBLE_ZERO)

        clock = graph_hms | pynutil.add_weight(graph_hm, 0.3) | pynutil.add_weight(graph_h, 0.3)

        # 12-hour clock with am/pm: the day-period word is chosen by the hour
        am = pynini.union("am", "AM", "a.m.", "A.M.", "a.m", "A.M")
        pm = pynini.union("pm", "PM", "p.m.", "P.M.", "p.m", "P.M")
        delete_marker_space = pynini.closure(pynutil.delete(" "), 0, 1)
        twelve_hour = []
        for marker, periods, default in ((am, _AM_PERIODS, "सकाळी"), (pm, _PM_PERIODS, "संध्याकाळी")):
            for h in range(1, 13):
                hour_input = pynini.union(*_hour_forms(h))
                rest = pynini.accep(":") + pynini.closure(pynini.union(*":0123456789०१२३४५६७८९"), 1)
                restricted = pynini.compose(hour_input + rest, clock)
                twelve_hour.append(
                    pynutil.insert(f"period: \"{periods.get(h, default)}\" ")
                    + restricted
                    + delete_marker_space
                    + pynutil.delete(marker)
                )
        graph_12h = pynini.union(*twelve_hour)

        base_time = clock | pynutil.add_weight(graph_12h, -0.1)
        self.fst_no_zone = self.add_tokens(base_time).optimize()

        zone_map = pynini.string_map(_TIME_ZONES).optimize()
        optional_zone = pynini.closure(
            pynutil.delete(" ") + pynutil.insert('zone: "') + zone_map + pynutil.insert('" '),
            0,
            1,
        )
        time_with_zone = base_time + optional_zone
        range_separator = (
            delete_marker_space
            + pynini.cross(pynini.union("-", "–"), "")
            + delete_marker_space
        )
        time_range = (
            pynutil.insert("start { ")
            + time_with_zone
            + pynutil.insert("} ")
            + range_separator
            + pynutil.insert("end { ")
            + time_with_zone
            + pynutil.insert("} preserve_order: true")
        )
        final_graph = time_with_zone | pynutil.add_weight(time_range, -0.01)

        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
