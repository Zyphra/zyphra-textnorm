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

from nemo_text_processing.text_normalization.gu.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.gu.utils import get_abs_path

GU_DOUBLE_ZERO = pynini.union("૦૦", "00")

hours_graph = pynini.string_file(get_abs_path("data/time/hours.tsv"))
minutes_graph = pynini.string_file(get_abs_path("data/time/minutes.tsv"))
seconds_graph = pynini.string_file(get_abs_path("data/time/seconds.tsv"))

_TIME_ZONES = [
    ("UTC", "યુ ટી સી"),
    ("GMT", "જી એમ ટી"),
    ("IST", "આઇ એસ ટી"),
    ("EST", "ઈ એસ ટી"),
    ("EDT", "ઈ ડી ટી"),
    ("CST", "સી એસ ટી"),
    ("CDT", "સી ડી ટી"),
    ("MST", "એમ એસ ટી"),
    ("MDT", "એમ ડી ટી"),
    ("PST", "પી એસ ટી"),
    ("PDT", "પી ડી ટી"),
    ("CET", "સી ઈ ટી"),
    ("CEST", "સી ઈ એસ ટી"),
    ("BST", "બી એસ ટી"),
    ("JST", "જે એસ ટી"),
    ("KST", "કે એસ ટી"),
    ("AEST", "એ ઈ એસ ટી"),
]

# Day-period words for 12-hour input following CLDR release-49 gu day periods
# (04-12 સવારે, 12-16 બપોરે, 16-20 સાંજે, 20-04 રાત્રે)
_AM_PERIODS = {12: "રાત્રે", 1: "રાત્રે", 2: "રાત્રે", 3: "રાત્રે", 4: "સવારે", 5: "સવારે"}
_PM_PERIODS = {12: "બપોરે", 1: "બપોરે", 2: "બપોરે", 3: "બપોરે", 8: "રાત્રે", 9: "રાત્રે", 10: "રાત્રે", 11: "રાત્રે"}
_GU_DIGITS = "૦૧૨૩૪૫૬૭૮૯"


def _hour_forms(h: int):
    forms = {str(h), "".join(_GU_DIGITS[int(c)] for c in str(h))}
    if h < 10:
        forms.add(f"0{h}")
        forms.add(f"૦{_GU_DIGITS[h]}")
    return forms


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time in Gujarati, e.g.
        ૧૨:૩૦:૩૦  -> time { hours: "બાર" minutes: "ત્રીસ" seconds: "ત્રીસ" }
        ૧:૪૦  -> time { hours: "એક" minutes: "ચાલીસ" }
        ૧:૦૦  -> time { hours: "એક" }
        7:30 pm -> time { period: "સાંજે" hours: "સાત" minutes: "ત્રીસ" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="classify")

        delete_colon = pynutil.delete(":")

        self.hours = pynutil.insert('hours: "') + hours_graph + pynutil.insert('" ')
        self.minutes = pynutil.insert('minutes: "') + minutes_graph + pynutil.insert('" ')
        self.seconds = pynutil.insert('seconds: "') + seconds_graph + pynutil.insert('" ')

        # hour minute seconds
        graph_hms = (
            self.hours + delete_colon + insert_space + self.minutes + delete_colon + insert_space + self.seconds
        )

        # hour minute
        graph_hm = self.hours + delete_colon + insert_space + self.minutes

        # hour
        graph_h = self.hours + delete_colon + pynutil.delete(GU_DOUBLE_ZERO)

        clock = graph_hms | pynutil.add_weight(graph_hm, 0.3) | pynutil.add_weight(graph_h, 0.3)

        # 12-hour clock with am/pm
        am = pynini.union("am", "AM", "a.m.", "A.M.", "a.m", "A.M")
        pm = pynini.union("pm", "PM", "p.m.", "P.M.", "p.m", "P.M")
        delete_marker_space = pynini.closure(pynutil.delete(" "), 0, 1)
        twelve_hour = []
        for marker, periods, default in ((am, _AM_PERIODS, "સવારે"), (pm, _PM_PERIODS, "સાંજે")):
            for h in range(1, 13):
                hour_input = pynini.union(*_hour_forms(h))
                rest = pynini.accep(":") + pynini.closure(pynini.union(*":0123456789૦૧૨૩૪૫૬૭૮૯"), 1)
                restricted = pynini.compose(hour_input + rest, clock)
                twelve_hour.append(
                    pynutil.insert(f'period: "{periods.get(h, default)}" ')
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
