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

from nemo_text_processing.text_normalization.pa.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.pa.utils import get_abs_path, load_labels

PA_DOUBLE_ZERO = pynini.union("੦੦", "00")
_TO_ASCII = str.maketrans("੦੧੨੩੪੫੬੭੮੯", "0123456789")

hours_graph = pynini.string_file(get_abs_path("data/time/hours.tsv"))
minutes_graph = pynini.string_file(get_abs_path("data/time/minutes.tsv"))
seconds_graph = pynini.string_file(get_abs_path("data/time/seconds.tsv"))

AM = pynini.union("am", "AM", "a.m.", "A.M.", "ਏਐਮ")
PM = pynini.union("pm", "PM", "p.m.", "P.M.", "ਪੀਐਮ")

TIMEZONES = pynini.string_map(
    [
        ("UTC", "ਯੂ ਟੀ ਸੀ"),
        ("GMT", "ਜੀ ਐਮ ਟੀ"),
        ("IST", "ਆਈ ਐਸ ਟੀ"),
        ("EST", "ਈ ਐਸ ਟੀ"),
        ("EDT", "ਈ ਡੀ ਟੀ"),
        ("CST", "ਸੀ ਐਸ ਟੀ"),
        ("CDT", "ਸੀ ਡੀ ਟੀ"),
        ("MST", "ਐਮ ਐਸ ਟੀ"),
        ("MDT", "ਐਮ ਡੀ ਟੀ"),
        ("PST", "ਪੀ ਐਸ ਟੀ"),
        ("PDT", "ਪੀ ਡੀ ਟੀ"),
        ("CET", "ਸੀ ਈ ਟੀ"),
        ("CEST", "ਸੀ ਈ ਐਸ ਟੀ"),
        ("JST", "ਜੇ ਐਸ ਟੀ"),
        ("KST", "ਕੇ ਐਸ ਟੀ"),
    ]
)


def day_period(hour24: int) -> str:
    """CLDR release-49 dayPeriodRules for pa."""
    if hour24 == 0:
        return "ਅੱਧੀ ਰਾਤ"
    if 4 <= hour24 < 12:
        return "ਸਵੇਰੇ"
    if 12 <= hour24 < 16:
        return "ਦੁਪਹਿਰੇ"
    if 16 <= hour24 < 21:
        return "ਸ਼ਾਮੀਂ"
    return "ਰਾਤੀਂ"


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time in Punjabi, e.g.
        ੧੨:੩੦:੩੦ -> time { hours: "ਬਾਰਾਂ" minutes: "ਤੀਹ" seconds: "ਤੀਹ" }
        ੧:੪੦ -> time { hours: "ਇੱਕ" minutes: "ਚਾਲੀ" }
        ੧:੦੦ -> time { hours: "ਇੱਕ" }
        ੪:੧੫ pm -> time { suffix: "ਸ਼ਾਮੀਂ" hours: "ਚਾਰ" minutes: "ਪੰਦਰਾਂ" }
        9:00-17:00 -> time { morphosyntactic_features: "ਨੌਂ ਵਜੇ ਤੋਂ ਸਤਾਰਾਂ ਵਜੇ" }
        14:30 UTC -> time { hours: "ਚੌਦਾਂ" minutes: "ਤੀਹ" zone: "ਯੂ ਟੀ ਸੀ" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="classify")

        delete_colon = pynutil.delete(":")

        self.hours = pynutil.insert("hours: \"") + hours_graph + pynutil.insert("\" ")
        self.minutes = pynutil.insert("minutes: \"") + minutes_graph + pynutil.insert("\" ")
        self.seconds = pynutil.insert("seconds: \"") + seconds_graph + pynutil.insert("\" ")

        def after_hour(hour):
            graph_hms = hour + delete_colon + insert_space + self.minutes + delete_colon + insert_space + self.seconds
            graph_hs = hour + delete_colon + pynutil.delete(PA_DOUBLE_ZERO) + delete_colon + insert_space + self.seconds
            graph_hm0 = hour + delete_colon + insert_space + self.minutes + delete_colon + pynutil.delete(PA_DOUBLE_ZERO)
            graph_h00 = hour + delete_colon + pynutil.delete(PA_DOUBLE_ZERO) + delete_colon + pynutil.delete(PA_DOUBLE_ZERO)
            graph_hm = hour + delete_colon + insert_space + self.minutes
            graph_h = hour + delete_colon + pynutil.delete(PA_DOUBLE_ZERO)
            return (
                graph_hms
                | pynutil.add_weight(graph_hs, 0.1)
                | pynutil.add_weight(graph_hm0, 0.1)
                | pynutil.add_weight(graph_h00, 0.1)
                | pynutil.add_weight(graph_hm, 0.3)
                | pynutil.add_weight(graph_h, 0.3)
            )

        graph_24h = after_hour(self.hours)

        # 12-hour clock with am/pm: the day period (CLDR pa dayPeriodRules) is chosen by the 24-hour value.
        hour_labels = dict(load_labels(get_abs_path("data/time/hours.tsv")))
        delete_marker_space = pynini.closure(pynutil.delete(" "), 0, 1)
        graph_12h = []
        for hour12 in range(1, 13):
            written = pynini.union(*[k for k in hour_labels if k.lstrip("0੦") and int(k.translate(_TO_ASCII)) == hour12])
            hour = pynutil.insert("hours: \"") + pynini.cross(written, hour_labels[str(hour12)]) + pynutil.insert("\" ")
            for marker, offset in ((AM, 0), (PM, 12)):
                hour24 = (hour12 % 12) + offset
                period = pynutil.insert("suffix: \"" + day_period(hour24) + "\" ")
                graph_12h.append(period + after_hour(hour) + delete_marker_space + pynutil.delete(marker))

        opt_zone = pynini.closure(
            pynutil.delete(" ") + pynutil.insert('zone: "') + TIMEZONES + pynutil.insert('" '),
            0,
            1,
        )

        time_range_dash = pynini.closure(pynutil.delete(" "), 0, 1) + pynutil.delete(pynini.union("-", "–", "—")) + pynini.closure(pynutil.delete(" "), 0, 1)

        # Time range like 9:00-17:00
        time_endpoint = (
            hours_graph + delete_colon + pynutil.delete(PA_DOUBLE_ZERO) + pynutil.insert(" ਵਜੇ")
            | hours_graph + delete_colon + pynutil.insert(" ਵੱਜ ਕੇ ") + minutes_graph + pynutil.insert(" ਮਿੰਟ")
        )
        time_range = (
            pynutil.insert('morphosyntactic_features: "')
            + (
                time_endpoint
                + time_range_dash
                + pynutil.insert(' ਤੋਂ ')
                + time_endpoint
            )
            + pynutil.insert('"')
        )

        graph_time = pynini.union(graph_24h, *graph_12h)
        final_graph = (graph_time + opt_zone) | time_range

        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph)
