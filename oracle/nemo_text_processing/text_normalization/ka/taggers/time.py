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
    NEMO_NOT_SPACE,
    GraphFst,
    delete_space,
)
from nemo_text_processing.text_normalization.ka.graph_utils import with_suffix
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time, e.g.
        "15:52" -> time { hours: "თხუთმეტი" minutes: "ორმოცდათორმეტი" }
        "12:30:45" -> time { hours: "თორმეტი" minutes: "ოცდაათი" seconds: "ორმოცდახუთი" }
        "2:30 pm" -> time { hours: "ორი" minutes: "ოცდაათი" period: "დღის" }
        "10:00" -> time { hours: "ათი" }
        "10:00:30" -> time { hours: "ათი" seconds: "ოცდაათი" }
        "14:30 UTC" -> time { hours: "თოთხმეტი" minutes: "ოცდაათი" zone: "UTC" }
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="time", kind="classify")
        hours = pynini.string_file(get_abs_path("data/time/hours.tsv"))
        minutes = pynini.string_file(get_abs_path("data/time/minutes.tsv"))

        hours = ((pynutil.insert("0") + NEMO_DIGIT) | (NEMO_DIGIT ** 2)) @ hours
        hours = hours.optimize()

        hour_cardinal = pynini.compose(
            pynini.project(hours, "input"),
            pynini.cross("00", "ნული")
            | (
                (pynini.closure(pynutil.delete("0"), 0, 1) + (NEMO_DIGIT - "0")) | ((NEMO_DIGIT - "0") + NEMO_DIGIT)
            ) @ cardinal.all_nums_no_tokens,
        ).optimize()
        full_hour = pynutil.delete(":00") + pynini.closure(pynutil.delete(":00"), 0, 1)

        no_zero = pynini.difference(NEMO_DIGIT ** 2, "00")
        graph_hours = pynutil.insert('hours: "') + hours + pynutil.insert('"')
        graph_minutes = pynutil.insert(' minutes: "') + pynini.compose(no_zero, minutes) + pynutil.insert('"')
        graph_minutes_suffixed = (
            pynutil.insert(' minutes: "')
            + pynini.compose(no_zero + pynini.closure(NEMO_NOT_SPACE), with_suffix(minutes))
            + pynutil.insert('"')
        )
        seconds = ((pynutil.delete("0") + NEMO_DIGIT) | ((NEMO_DIGIT - "0") + NEMO_DIGIT)) @ cardinal.all_nums_no_tokens
        graph_seconds = pynutil.insert(' seconds: "') + seconds + pynutil.insert('"')
        hour_alone = pynutil.insert('hours: "') + hour_cardinal + full_hour + pynutil.insert('"')
        hour_alone |= pynutil.insert('hours: "') + with_suffix(hour_cardinal + full_hour) + pynutil.insert('"')

        hm = graph_hours + pynutil.delete(":") + graph_minutes
        hms = hm + pynutil.delete(":") + graph_seconds
        hms |= hm + pynutil.delete(":00")
        final_graph = hm | hms | hour_alone
        final_graph |= graph_hours + pynutil.delete(":") + graph_minutes_suffixed

        graph_seconds_only = pynutil.insert(' seconds: "') + pynini.compose(no_zero, seconds) + pynutil.insert('"')
        final_graph |= graph_hours + pynutil.delete(":00:") + graph_seconds_only

        # 12-hour clock with am / pm
        def hour_set(values):
            return pynini.union(*[pynini.accep(v) for v in values])

        def clock(hour_values, period_word):
            h = pynutil.insert('hours: "') + (hour_set(hour_values) @ hours) + pynutil.insert('"')
            t = h + pynutil.delete(":") + graph_minutes + pynini.closure(pynutil.delete(":") + graph_seconds, 0, 1)
            t |= pynutil.insert('hours: "') + (hour_set(hour_values) @ hour_cardinal) + full_hour + pynutil.insert('"')
            return t, pynutil.insert(f' period: "{period_word}"')

        def hour_strings(nums):
            return [f"{n}" for n in nums] + [f"{n:02d}" for n in nums if n < 10]

        am = pynini.union("am", "AM", "a.m.", "A.M.", "Am")
        pm = pynini.union("pm", "PM", "p.m.", "P.M.", "Pm")
        ampm = pynini.Fst()
        for nums, marker, word in (
            ([12, 1, 2, 3, 4, 5], am, "ღამის"),
            ([6, 7, 8, 9, 10, 11], am, "დილის"),
            ([12, 1, 2, 3, 4, 5], pm, "დღის"),
            ([6, 7, 8, 9, 10, 11], pm, "საღამოს"),
        ):
            t, period = clock(hour_strings(nums), word)
            ampm |= t + delete_space + pynutil.delete(marker) + period
        final_graph |= ampm

        # Timezones: "14:30 UTC", "09:00 GMT", "14:00 UTC+10", "14:00 UTC−10"
        tz_offset = pynini.union("+", "-", "−") + NEMO_DIGIT ** (1, 2)
        tz_name = (
            pynini.union("UTC", "GMT", "EST", "PST", "CET", "EET", "MSK")
            + pynini.closure(tz_offset, 0, 1)
        )
        zone_tag = pynutil.insert(' zone: "') + tz_name + pynutil.insert('"')
        final_graph |= (hm | hour_alone) + delete_space + zone_tag

        self.fst = self.add_tokens(final_graph).optimize()
