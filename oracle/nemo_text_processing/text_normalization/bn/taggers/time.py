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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.bn.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.bn.utils import get_abs_path, load_labels

BN_DOUBLE_ZERO = pynini.union("০০", "00")
_TO_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

hours_graph = pynini.string_file(get_abs_path("data/time/hours.tsv"))
minutes_graph = pynini.string_file(get_abs_path("data/time/minutes.tsv"))
seconds_graph = pynini.string_file(get_abs_path("data/time/seconds.tsv"))

AM = pynini.union("am", "AM", "a.m.", "A.M.", "এএম")
PM = pynini.union("pm", "PM", "p.m.", "P.M.", "পিএম")

TIMEZONES = pynini.string_map(
    [
        ("UTC", "ইউ টি সি"),
        ("GMT", "জি এম টি"),
        ("BST", "বি এস টি"),
        ("IST", "আই এস টি"),
        ("EST", "ই এস টি"),
        ("EDT", "ই ডি টি"),
        ("CST", "সি এস টি"),
        ("CDT", "সি ডি টি"),
        ("MST", "এম এস টি"),
        ("MDT", "এম ডি টি"),
        ("PST", "পি এস টি"),
        ("PDT", "পি ডি টি"),
        ("CET", "সি ই টি"),
        ("CEST", "সি ই এস টি"),
        ("JST", "জে এস টি"),
        ("KST", "কে এস টি"),
    ]
)


def day_period(hour24: int) -> str:
    """CLDR release-49 dayPeriodRules for bn (format abbreviated names)."""
    if 4 <= hour24 < 6:
        return "ভোর"
    if 6 <= hour24 < 12:
        return "সকাল"
    if 12 <= hour24 < 16:
        return "দুপুর"
    if 16 <= hour24 < 18:
        return "বিকাল"
    if 18 <= hour24 < 20:
        return "সন্ধ্যা"
    return "রাত"


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time, e.g.
        ১২:৩০:৩০ -> time { hours: "বারো" minutes: "ত্রিশ" seconds: "ত্রিশ" }
        ১:৪০ -> time { hours: "এক" minutes: "চল্লিশ" }
        ১:০০ -> time { hours: "এক" }
        ৪:১৫ pm -> time { suffix: "বিকাল" hours: "চার" minutes: "পনেরো" }
        9:00-17:00 -> time { morphosyntactic_features: "নয়টা থেকে সতেরোটা" }
        14:30 UTC -> time { hours: "চৌদ্দ" minutes: "ত্রিশ" zone: "ইউ টি সি" }

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
            graph_hs = hour + delete_colon + pynutil.delete(BN_DOUBLE_ZERO) + delete_colon + insert_space + self.seconds
            graph_hm0 = hour + delete_colon + insert_space + self.minutes + delete_colon + pynutil.delete(BN_DOUBLE_ZERO)
            graph_h00 = hour + delete_colon + pynutil.delete(BN_DOUBLE_ZERO) + delete_colon + pynutil.delete(BN_DOUBLE_ZERO)
            graph_hm = hour + delete_colon + insert_space + self.minutes
            graph_h = hour + delete_colon + pynutil.delete(BN_DOUBLE_ZERO)
            return (
                graph_hms
                | pynutil.add_weight(graph_hs, 0.1)
                | pynutil.add_weight(graph_hm0, 0.1)
                | pynutil.add_weight(graph_h00, 0.1)
                | pynutil.add_weight(graph_hm, 0.3)
                | pynutil.add_weight(graph_h, 0.3)
            )

        graph_24h = after_hour(self.hours)

        # 12-hour clock with am/pm: the day period (CLDR bn dayPeriodRules) is chosen by the 24-hour value.
        hour_labels = dict(load_labels(get_abs_path("data/time/hours.tsv")))
        delete_marker_space = pynini.closure(pynutil.delete(" "), 0, 1)
        graph_12h = []
        for hour12 in range(1, 13):
            written = pynini.union(*[k for k in hour_labels if k.lstrip("0০") and int(k.translate(_TO_ASCII)) == hour12])
            hour = pynutil.insert("hours: \"") + pynini.cross(written, hour_labels[str(hour12)]) + pynutil.insert("\" ")
            for marker, offset in ((AM, 0), (PM, 12)):
                hour24 = hour12 % 12 + offset
                period = pynutil.insert("suffix: \"" + day_period(hour24) + "\" ")
                graph_12h.append(period + after_hour(hour) + delete_marker_space + pynutil.delete(marker))

        opt_zone = pynini.closure(
            pynutil.delete(" ") + pynutil.insert('zone: "') + TIMEZONES + pynutil.insert('" '),
            0,
            1,
        )

        # Time ranges: "9:00-17:00", "09:00–17:00", "9:30-17:45", "১০:০০-১২:০০"
        plain_hm = (
            hours_graph
            + pynutil.insert("টা")
            + delete_colon
            + (
                pynutil.delete(BN_DOUBLE_ZERO)
                | (pynutil.insert(" ") + minutes_graph + pynutil.insert(" মিনিট"))
            )
        ).optimize()
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        range_sep = opt_sp + pynini.cross(pynini.union("-", "–"), " থেকে ") + opt_sp
        graph_time_range = (
            pynutil.insert('morphosyntactic_features: "')
            + plain_hm
            + range_sep
            + plain_hm
            + pynutil.insert('" ')
        ).optimize()

        final_graph = (
            (graph_24h + opt_zone)
            | pynutil.add_weight(pynini.union(*graph_12h) + opt_zone, -0.01)
            | pynutil.add_weight(graph_time_range + opt_zone, -0.05)
        )

        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
