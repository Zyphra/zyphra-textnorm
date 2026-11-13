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

from nemo_text_processing.text_normalization.ar.graph_utils import GraphFst
from nemo_text_processing.text_normalization.ar.utils import get_abs_path, load_labels


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time. Hours are read with the feminine ordinal MSA uses after الساعة
    (data/time/hours.tsv: الواحدة ... الثانية عشرة); minutes and seconds agree with دقيقة / ثانية
    (data/time/minutes.tsv, seconds.tsv). In HH:MM, ":15" is والربع, ":30" والنصف and ":45" إلا ربعًا with the
    next hour. A "ص" / "م" (or am / pm) suffix after hours 1-12 gives صباحًا / مساءً. Without a suffix the input is
    24-hour: 13-23 are read on the 12-hour clock followed by مساءً, 0 as الثانية عشرة ليلًا, 1-12 without a period, e.g.
        "10:30" -> time { hours: "العاشرة" minutes: "والنصف" preserve_order: true }
        "8:45 م" -> time { hours: "التاسعة" minutes: "إلا ربعًا" suffix: "مساءً" preserve_order: true }
        "14:05:09" -> time { hours: "الثانية" minutes: "وخمس دقائق" seconds: "وتسع ثوان" suffix: "مساءً" preserve_order: true }
        "14:30 UTC" -> time { hours: "الثانية" minutes: "والنصف" suffix: "مساءً" zone: "بالتوقيت العالمي المنسق" preserve_order: true }
    """

    def __init__(self):
        super().__init__(name="time", kind="classify")
        hour_words = dict(load_labels(get_abs_path("data/time/hours.tsv")))
        minute_words = dict(load_labels(get_abs_path("data/time/minutes.tsv")))
        second_words = dict(load_labels(get_abs_path("data/time/seconds.tsv")))

        def hour_inputs(h):
            return sorted({str(h), f"{h:02d}"})

        def period_24(h):
            return "مساءً" if h >= 13 else ("ليلًا" if h == 0 else None)

        def suffix_field(period):
            return f' suffix: "{period}"' if period else ""

        order = pynutil.insert(" preserve_order: true")

        # Factored HH:MM (00:00..23:59) with special :15 / :30 / :45 readings
        non_45_entries = [("00", ""), ("15", ' minutes: "والربع"'), ("30", ' minutes: "والنصف"')]
        for m in range(1, 60):
            if m not in (15, 30, 45):
                non_45_entries.append((f"{m:02d}", f' minutes: "{minute_words[f"{m:02d}"]}"'))
        non_45_mins = pynini.string_map(non_45_entries).optimize()
        quarter_to = pynutil.delete(":45") + pynutil.insert(' minutes: "إلا ربعًا"')

        hm_24_graph = None
        for period in [None, "مساءً", "ليلًا"]:
            hrs_same = pynini.string_map(
                [(hi, f'hours: "{hour_words[str(h % 12 or 12)]}"') for h in range(24) if period_24(h) == period for hi in hour_inputs(h)]
            )
            hrs_45 = pynini.string_map(
                [
                    (hi, f'hours: "{hour_words[str((h % 12 or 12) % 12 + 1)]}"')
                    for h in range(24)
                    if period_24(h) == period
                    for hi in hour_inputs(h)
                ]
            )
            g = ((hrs_same + pynutil.delete(":") + non_45_mins) | (hrs_45 + quarter_to)) + pynutil.insert(
                suffix_field(period)
            )
            hm_24_graph = g if hm_24_graph is None else hm_24_graph | g
        hm_24_graph = hm_24_graph.optimize()

        hrs_12_same = pynini.string_map([(hi, f'hours: "{hour_words[str(h)]}"') for h in range(1, 13) for hi in hour_inputs(h)])
        hrs_12_45 = pynini.string_map(
            [(hi, f'hours: "{hour_words[str(h % 12 + 1)]}"') for h in range(1, 13) for hi in hour_inputs(h)]
        )
        hm_12_core = ((hrs_12_same + pynutil.delete(":") + non_45_mins) | (hrs_12_45 + quarter_to)).optimize()

        # HH:MM:SS, 24-hour, plain minutes and seconds
        hms = []
        for h in range(24):
            for hi in hour_inputs(h):
                hms.append((hi, f'hours: "{hour_words[str(h % 12 or 12)]}"', period_24(h)))
        minutes = pynini.string_map([("00", "")] + [(k, f' minutes: "{v}"') for k, v in minute_words.items()])
        seconds = pynini.string_map([("00", "")] + [(k, f' seconds: "{v}"') for k, v in second_words.items()])
        graph_hms = None
        for period in [None, "مساءً", "ليلًا"]:
            hours = pynini.string_map([(hi, tags) for hi, tags, p in hms if p == period])
            g = (
                hours
                + pynutil.delete(":")
                + minutes
                + pynutil.delete(":")
                + seconds
                + pynutil.insert(suffix_field(period))
            )
            graph_hms = g if graph_hms is None else graph_hms | g

        suffix = pynini.cross("ص", "صباحًا") | pynini.cross("م", "مساءً")
        suffix |= pynini.union(*[pynini.cross(x, "صباحًا") for x in ["am", "AM", "a.m."]])
        suffix |= pynini.union(*[pynini.cross(x, "مساءً") for x in ["pm", "PM", "p.m."]])
        graph_12 = (
            hm_12_core
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' suffix: "')
            + suffix
            + pynutil.insert('"')
        )

        tz_map = pynini.string_map(
            [
                ("UTC", "بالتوقيت العالمي المنسق"),
                ("GMT", "بتوقيت غرينتش"),
                ("EST", "بتوقيت شرق أمريكا"),
                ("EDT", "بالتوقيت الصيفي لشرق أمريكا"),
                ("CST", "بتوقيت وسط أمريكا"),
                ("CDT", "بالتوقيت الصيفي لوسط أمريكا"),
                ("MST", "بتوقيت الجبال"),
                ("MDT", "بالتوقيت الصيفي للجبال"),
                ("PST", "بتوقيت المحيط الهادئ"),
                ("PDT", "بالتوقيت الصيفي للمحيط الهادئ"),
                ("CET", "بتوقيت وسط أوروبا"),
                ("CEST", "بالتوقيت الصيفي لوسط أوروبا"),
                ("AST", "بالتوقيت العربي"),
                ("GST", "بتوقيت الخليج"),
            ]
        )
        offset_num = pynini.string_map(
            [
                ("1", "واحد"),
                ("2", "اثنين"),
                ("3", "ثلاثة"),
                ("4", "أربعة"),
                ("5", "خمسة"),
                ("6", "ستة"),
                ("7", "سبعة"),
                ("8", "ثمانية"),
                ("9", "تسعة"),
                ("10", "عشرة"),
                ("11", "أحد عشر"),
                ("12", "اثني عشر"),
            ]
        )
        tz_offset = pynini.closure(
            (pynini.cross("+", " زائد ") | pynini.cross("-", " ناقص ")) + offset_num,
            0,
            1,
        )
        opt_zone = pynini.closure(
            pynutil.delete(" ") + pynutil.insert(' zone: "') + tz_map + tz_offset + pynutil.insert('"'),
            0,
            1,
        )

        hm_core = (hm_24_graph | pynutil.add_weight(graph_12, -0.1)).optimize()
        self.hm_fst = self.add_tokens((hm_core + opt_zone + order).optimize()).optimize()

        graph = (hm_core | graph_hms) + opt_zone
        self.graph = (graph + order).optimize()
        self.fst = self.add_tokens(self.graph).optimize()
