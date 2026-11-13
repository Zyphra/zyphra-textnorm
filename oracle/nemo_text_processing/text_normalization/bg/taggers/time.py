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

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian clock times.
    e.g. 08:15 -> tokens { name: "осем и петнадесет" }
         08:15:30 -> tokens { name: "осем часа, петнадесет минути и тридесет секунди" }
         14:30 -> tokens { name: "четиринадесет и тридесет" }
         14:30 UTC -> tokens { name: "четиринадесет и тридесет UTC" }
         9:00 AM -> tokens { name: "девет сутринта" }
         4:45 p.m. -> tokens { name: "четири и четиридесет и пет следобед" }
         9:00-17:00 -> tokens { name: "девет до седемнадесет" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        hours_map = pynini.string_map([
            ("0", "нула"), ("00", "нула"),
            ("1", "един"), ("01", "един"),
            ("2", "два"), ("02", "два"),
            ("3", "три"), ("03", "три"),
            ("4", "четири"), ("04", "четири"),
            ("5", "пет"), ("05", "пет"),
            ("6", "шест"), ("06", "шест"),
            ("7", "седем"), ("07", "седем"),
            ("8", "осем"), ("08", "осем"),
            ("9", "девет"), ("09", "девет"),
            ("10", "десет"),
            ("11", "единадесет"),
            ("12", "дванадесет"),
            ("13", "тринадесет"),
            ("14", "четиринадесет"),
            ("15", "петнадесет"),
            ("16", "шестнадесет"),
            ("17", "седемнадесет"),
            ("18", "осемнадесет"),
            ("19", "деветнадесет"),
            ("20", "двадесет"),
            ("21", "двадесет и един"),
            ("22", "двадесет и два"),
            ("23", "двадесет и три")
        ])

        # Minutes mapping
        card_f = cardinal.cardinal_f
        min_00 = pynutil.delete("00")
        min_01 = pynini.cross("01", "една")
        min_units = pynutil.delete("0") + pynini.string_map([
            ("1", "една"), ("2", "две"), ("3", "три"), ("4", "четири"), ("5", "пет"),
            ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
        ])
        min_teens_tens = (pynini.union(*"12345") + pynini.union(*"0123456789")) @ card_f

        minutes = min_01 | min_units | min_teens_tens

        # Colon separator
        colon = pynutil.delete(":")

        # Exact hours: "00:00" -> "нула часа", "9:00" -> "девет"
        time_exact_zero = pynini.cross(pynini.union("00:00", "0:00"), "нула часа")
        time_exact_other = hours_map + colon + min_00

        # Hours and minutes: "08:15", "14:30", "7:05"
        time_hm = hours_map + colon + pynutil.insert(" и ") + minutes

        # Hours, minutes, and seconds: "08:15:30"
        # "08:15:30" -> "осем часа, петнадесет минути и тридесет секунди"
        time_hms = (
            hours_map
            + pynutil.insert(" часа, ")
            + colon
            + minutes
            + pynutil.insert(" минути и ")
            + colon
            + minutes
            + pynutil.insert(" секунди")
        )

        # AM / PM indicators
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        am_ind = pynini.cross(pynini.union("AM", "A.M.", "am", "a.m."), "сутринта")
        pm_ind = pynini.cross(pynini.union("PM", "P.M.", "pm", "p.m."), "следобед")
        ampm = am_ind | pm_ind

        time_ampm = (time_exact_other | time_hm) + opt_sp + pynutil.insert(" ") + ampm

        # Timezones: "14:30 UTC", "09:00 GMT"
        tz_ind = pynini.union("UTC", "GMT", "EET", "EEST", "CET", "CEST")
        time_tz = (time_exact_other | time_hm) + pynutil.delete(" ") + pynutil.insert(" ") + tz_ind

        # Time ranges: "9:00-17:00", "09:00–17:00"
        dash = pynini.cross(pynini.union("-", "–", "—"), " до ")
        time_range = (
            (time_exact_other | time_hm)
            + opt_sp
            + dash
            + opt_sp
            + (time_exact_other | time_hm)
        ).optimize()

        all_times = (
            pynutil.add_weight(time_range, 0.95)
            | pynutil.add_weight(time_hms, 0.96)
            | pynutil.add_weight(time_ampm, 0.97)
            | pynutil.add_weight(time_tz, 0.98)
            | pynutil.add_weight(time_exact_zero, 0.99)
            | pynutil.add_weight(time_hm, 1.0)
            | pynutil.add_weight(time_exact_other, 1.05)
        ).optimize()

        self.all_times = all_times

        graph = pynutil.insert('name: "') + convert_space(all_times) + pynutil.insert('"')
        self.fst = graph.optimize()
