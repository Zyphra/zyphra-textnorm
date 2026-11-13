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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tl.utils import get_abs_path


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Tagalog time, e.g.
        "10:30" -> time { hours: "sampu" minutes: "tatlumpu" preserve_order: true }
        "08:00 PHT" -> time { hours: "walo" zone: "P H T" preserve_order: true }
        "10:30:15" -> time { hours: "sampu" minutes: "tatlumpu" seconds: "labinlima" preserve_order: true }
        "9:00-17:00" -> time { range: "ika-siyam hanggang ika-labimpito" preserve_order: true }
        "8:00 am" -> time { hours: "walo" suffix: "ng umaga" preserve_order: true }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)
        number = cardinal.graph
        optional_zero = pynini.closure(pynutil.delete("0"), 0, 1)
        hour_digits = pynini.union(*[str(x) for x in range(0, 25)])
        hour_padded = (optional_zero + hour_digits) @ number
        minute = (pynutil.delete("0") + (NEMO_DIGIT - "0") | pynini.union(*[str(x) for x in range(10, 60)])) @ number

        hours = pynutil.insert('hours: "') + hour_padded + pynutil.insert('"')
        minutes = pynutil.insert(' minutes: "') + minute + pynutil.insert('"')
        seconds = pynutil.insert(' seconds: "') + minute + pynutil.insert('"')
        separator_colon = pynutil.delete(":")
        separator_dot = pynutil.delete(".")

        hm_colon = hours + separator_colon + (pynutil.delete("00") | minutes)
        hm_dot = hours + separator_dot + (pynutil.delete("00") | minutes)
        hms = hours + separator_colon + (pynutil.delete("00") | minutes) + separator_colon + seconds

        # Time ranges: "9:00-17:00", "09:00–17:00"
        plain_hour = pynutil.insert("ika-") + hour_padded
        plain_hm = plain_hour + separator_colon + (pynutil.delete("00") | (pynutil.insert(" at ") + minute + pynutil.insert(" minuto")))
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        range_sep = opt_sp + pynini.cross(pynini.union("-", "–"), " hanggang ") + opt_sp
        hm_range = pynutil.insert('range: "') + plain_hm + range_sep + plain_hm + pynutil.insert('"')
        zone = pynini.closure(
            pynini.accep(" ")
            + pynutil.insert('zone: "')
            + convert_space(pynini.string_file(get_abs_path("data/time/time_zone.tsv")))
            + pynutil.insert('"'),
            0,
            1,
        )

        am_pm = pynini.string_map(
            [
                ("am", "ng umaga"),
                ("a.m.", "ng umaga"),
                ("AM", "ng umaga"),
                ("A.M.", "ng umaga"),
                ("pm", "ng hapon"),
                ("p.m.", "ng hapon"),
                ("PM", "ng hapon"),
                ("P.M.", "ng hapon"),
                ("n.u.", "ng umaga"),
                ("n.h.", "ng hapon"),
                ("n.g.", "ng gabi"),
            ]
        )
        suffix = pynini.closure(
            pynini.accep(" ") + pynutil.insert('suffix: "') + am_pm + pynutil.insert('"'), 0, 1
        )
        suffix_req = pynini.accep(" ") + pynutil.insert('suffix: "') + am_pm + pynutil.insert('"')
        zone_req = (
            pynini.accep(" ")
            + pynutil.insert('zone: "')
            + convert_space(pynini.string_file(get_abs_path("data/time/time_zone.tsv")))
            + pynutil.insert('"')
        )

        prefix = pynutil.delete(pynini.union("oras ", "Oras ", "ika-", "Ika-"))

        # Colon time can have optional prefix and optional suffix/zone
        colon_time = pynini.closure(prefix, 0, 1) + (hm_colon | hms) + suffix + zone
        # Dot time MUST have explicit prefix, OR explicit suffix, OR explicit zone
        dot_time = (
            (prefix + hm_dot + suffix + zone)
            | (hm_dot + suffix_req + zone)
            | (hm_dot + zone_req)
        )

        graph = colon_time | dot_time
        graph |= hm_range
        graph += pynutil.insert(" preserve_order: true")
        self.fst = self.add_tokens(graph).optimize()
