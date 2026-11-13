# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time expressions in Thai (th).
    Supports:
    - 08:15:30 -> แปดนาฬิกาสิบห้านาทีสามสิบวินาที
    - 14:30 -> สิบสี่นาฬิกาสามสิบนาที
    - 00:00 -> ศูนย์นาฬิกา
    - 00:30 -> ศูนย์นาฬิกาสามสิบนาที
    - 9:00 AM -> เก้านาฬิกา
    - 4:45 PM / 4:45 p.m. -> สิบหกนาฬิกาสี่สิบห้านาที
    - 14:30 UTC -> สิบสี่นาฬิกาสามสิบนาที ยูทีซี
    - Time ranges: 9:00-17:00 -> เก้านาฬิกาถึงสิบเจ็ดนาฬิกา
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        thai_to_ascii = pynini.string_map(
            [
                ("๐", "0"),
                ("๑", "1"),
                ("๒", "2"),
                ("๓", "3"),
                ("๔", "4"),
                ("๕", "5"),
                ("๖", "6"),
                ("๗", "7"),
                ("๘", "8"),
                ("๙", "9"),
            ]
        )
        single_digit = thai_to_ascii | NEMO_DIGIT

        # Hours (0-23)
        h_0_to_23 = (single_digit | (single_digit + single_digit)) @ (
            (pynutil.delete("0") + cardinal.all_positive)
            | pynini.cross("00", "ศูนย์")
            | pynini.cross("0", "ศูนย์")
            | cardinal.all_cardinals
        )

        # Minutes (0-59)
        m_nonzero = (single_digit + single_digit) @ (
            (pynutil.delete("0") + cardinal.all_positive) | cardinal.all_positive
        )
        m_zero = pynini.cross("00", "")

        # Seconds (0-59)
        s_nonzero = (single_digit + single_digit) @ (
            (pynutil.delete("0") + cardinal.all_positive) | cardinal.all_positive
        )
        s_zero = pynini.cross("00", "")

        # Time with seconds: 08:15:30, 08:15:00
        hms = (
            h_0_to_23
            + pynutil.insert("นาฬิกา")
            + pynutil.delete(":")
            + (
                (m_nonzero + pynutil.insert("นาที") + pynutil.delete(":") + (
                    (s_nonzero + pynutil.insert("วินาที")) | s_zero
                ))
                | (m_zero + pynutil.delete(":") + (
                    (s_nonzero + pynutil.insert("วินาที")) | s_zero
                ))
            )
        ).optimize()

        # Time without seconds: 14:30, 00:00, 09:00
        hm = (
            h_0_to_23
            + pynutil.insert("นาฬิกา")
            + pynutil.delete(":")
            + ((m_nonzero + pynutil.insert("นาที")) | m_zero)
        ).optimize()

        # 12-hour AM / PM
        pm_hours_map = pynini.string_map(
            [
                ("1", "สิบสาม"),
                ("01", "สิบสาม"),
                ("2", "สิบสี่"),
                ("02", "สิบสี่"),
                ("3", "สิบห้า"),
                ("03", "สิบห้า"),
                ("4", "สิบหก"),
                ("04", "สิบหก"),
                ("5", "สิบเจ็ด"),
                ("05", "สิบเจ็ด"),
                ("6", "สิบแปด"),
                ("06", "สิบแปด"),
                ("7", "สิบเก้า"),
                ("07", "สิบเก้า"),
                ("8", "ยี่สิบ"),
                ("08", "ยี่สิบ"),
                ("9", "ยี่สิบเอ็ด"),
                ("09", "ยี่สิบเอ็ด"),
                ("10", "ยี่สิบสอง"),
                ("11", "ยี่สิบสาม"),
                ("12", "สิบสอง"),
            ]
        )
        am_suffix = pynini.union(" AM", " am", " A.M.", " a.m.", "AM", "am")
        pm_suffix = pynini.union(" PM", " pm", " P.M.", " p.m.", "PM", "pm")

        hm_am = (
            h_0_to_23
            + pynutil.insert("นาฬิกา")
            + pynutil.delete(":")
            + ((m_nonzero + pynutil.insert("นาที")) | m_zero)
            + pynutil.delete(am_suffix)
        ).optimize()

        hm_pm = (
            pm_hours_map
            + pynutil.insert("นาฬิกา")
            + pynutil.delete(":")
            + ((m_nonzero + pynutil.insert("นาที")) | m_zero)
            + pynutil.delete(pm_suffix)
        ).optimize()

        # Timezones: 14:30 UTC, 09:00 GMT
        tz_map = pynini.string_map(
            [
                (" UTC", " ยูทีซี"),
                (" GMT", " จีเอ็มที"),
                (" EST", " อีเอสที"),
                (" PST", " พีเอสที"),
                (" ICT", " ไอซีที"),
            ]
        )
        time_with_tz = ((hms | hm) + tz_map).optimize()

        # Single clock times
        single_time = (time_with_tz | hms | hm_am | hm_pm | hm).optimize()

        # Time ranges: 9:00-17:00, 09:00–17:00 -> เก้านาฬิกาถึงสิบเจ็ดนาฬิกา
        dash = pynini.union("-", "–", "—")
        range_op = opt_sp + pynini.cross(dash, "ถึง") + opt_sp
        time_range = (single_time + range_op + single_time).optimize()

        all_times = (
            pynutil.add_weight(time_range, 1.02)
            | pynutil.add_weight(time_with_tz, 1.03)
            | pynutil.add_weight(hms, 1.04)
            | pynutil.add_weight(hm_am, 1.04)
            | pynutil.add_weight(hm_pm, 1.04)
            | pynutil.add_weight(hm, 1.05)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_times)
            + pynutil.insert('"')
        ).optimize()
