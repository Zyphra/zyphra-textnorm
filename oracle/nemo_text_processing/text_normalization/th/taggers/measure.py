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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.th.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.th.taggers.fraction import FractionFst


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measurement units, percents, temperatures,
    and approximations in Thai (th).
    Supports:
    - SI units: 5 km -> ห้ากิโลเมตร, 3.5 km -> สามจุดห้ากิโลเมตร, 5 kg -> ห้ากิโลกรัม
    - Unspaced spans: 5km -> ห้ากิโลเมตร, 5kg -> ห้ากิโลกรัม, 100กม. -> หนึ่งร้อยกิโลเมตร
    - Computing / Electrical / Scientific: 10 Gbps, 100 Mbps, 5000 mAh, 50 kWh, 1013 hPa, 250 kcal, 60 dB, 100 Ω, 50 µg, 10 µm, 100 m², 5 m³
    - Temperatures: 37°C / 37 ℃ -> สามสิบเจ็ดองศาเซลเซียส, -15°C -> ลบสิบห้าองศาเซลเซียส, 30 °F -> สามสิบองศาฟาเรนไฮต์
    - Percents: 50% -> ห้าสิบเปอร์เซ็นต์, 5‰ -> ห้าเปอร์มิล
    - Prefix modifiers: ~50 -> ประมาณห้าสิบ, ~10 km -> ประมาณสิบกิโลเมตร, ±5 -> บวกลบห้า, ±10% -> บวกลบสิบเปอร์เซ็นต์
    - Measure ranges: 5–10 kg -> ห้าถึงสิบกิโลกรัม, 10–15% -> สิบถึงสิบห้าเปอร์เซ็นต์
    """

    def __init__(
        self,
        cardinal: CardinalFst,
        decimal: DecimalFst,
        fraction: FractionFst,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Measure units mapping
        units_map = pynini.string_map(
            [
                # Length
                ("km", "กิโลเมตร"),
                ("กม.", "กิโลเมตร"),
                ("กม", "กิโลเมตร"),
                ("m", "เมตร"),
                ("ม.", "เมตร"),
                ("ม", "เมตร"),
                ("cm", "เซนติเมตร"),
                ("ซม.", "เซนติเมตร"),
                ("ซม", "เซนติเมตร"),
                ("mm", "มิลลิเมตร"),
                ("มม.", "มิลลิเมตร"),
                ("มม", "มิลลิเมตร"),
                ("µm", "ไมโครเมตร"),
                ("μm", "ไมโครเมตร"),
                ("mi", "ไมล์"),
                # Mass
                ("kg", "กิโลกรัม"),
                ("กก.", "กิโลกรัม"),
                ("กก", "กิโลกรัม"),
                ("g", "กรัม"),
                ("mg", "มิลลิกรัม"),
                ("µg", "ไมโครกรัม"),
                ("μg", "ไมโครกรัม"),
                # Volume
                ("L", "ลิตร"),
                ("l", "ลิตร"),
                ("mL", "มิลลิลิตร"),
                ("ml", "มิลลิลิตร"),
                # Time
                ("s", "วินาที"),
                ("sec", "วินาที"),
                ("ms", "มิลลิวินาที"),
                ("min", "นาที"),
                ("h", "ชั่วโมง"),
                ("hr", "ชั่วโมง"),
                ("ชม.", "ชั่วโมง"),
                ("ชม", "ชั่วโมง"),
                # Speed / Rate
                ("km/h", "กิโลเมตรต่อชั่วโมง"),
                ("km/hr", "กิโลเมตรต่อชั่วโมง"),
                ("m/s", "เมตรต่อวินาที"),
                ("mph", "ไมล์ต่อชั่วโมง"),
                # Area / Volume
                ("m²", "ตารางเมตร"),
                ("m2", "ตารางเมตร"),
                ("cm²", "ตารางเซนติเมตร"),
                ("cm2", "ตารางเซนติเมตร"),
                ("km²", "ตารางกิโลเมตร"),
                ("km2", "ตารางกิโลเมตร"),
                ("m³", "ลูกบาศก์เมตร"),
                ("m3", "ลูกบาศก์เมตร"),
                ("cm³", "ลูกบาศก์เซนติเมตร"),
                ("cm3", "ลูกบาศก์เซนติเมตร"),
                # Temperature
                ("°C", "องศาเซลเซียส"),
                ("℃", "องศาเซลเซียส"),
                ("°F", "องศาฟาเรนไฮต์"),
                ("K", "เคลวิน"),
                # Scientific & Electrical & Computing
                ("Gbps", "กิกะบิตต่อวินาที"),
                ("Mbps", "เมกะบิตต่อวินาที"),
                ("kbps", "กิโลบิตต่อวินาที"),
                ("mAh", "มิลลิแอมแปร์ชั่วโมง"),
                ("kWh", "กิโลวัตต์ชั่วโมง"),
                ("hPa", "เฮกโตปาสกาล"),
                ("kcal", "กิโลแคลอรี"),
                ("dB", "เดซิเบล"),
                ("Ω", "โอห์ม"),
                ("Ω", "โอห์ม"),
                ("Hz", "เฮิรตซ์"),
                ("kHz", "กิโลเฮิรตซ์"),
                ("MHz", "เมกะเฮิรตซ์"),
                ("GHz", "กิกะเฮิรตซ์"),
                ("W", "วัตต์"),
                ("kW", "กิโลวัตต์"),
                ("MW", "เมกะวัตต์"),
                ("V", "โวลต์"),
                ("mV", "มิลลิโวลต์"),
                ("A", "แอมแปร์"),
                ("mA", "มิลลิแอมแปร์"),
                ("KB", "กิโลไบต์"),
                ("kB", "กิโลไบต์"),
                ("MB", "เมกะไบต์"),
                ("GB", "กิกะไบต์"),
                ("TB", "เทระไบต์"),
                # Percent & Permille
                ("%", "เปอร์เซ็นต์"),
                ("‰", "เปอร์มิล"),
            ]
        )

        num = pynutil.add_weight(decimal.decimal_numbers, 1.0) | pynutil.add_weight(cardinal.number, 1.1)

        # Standard measure: 5 km, 3.5 km, 5km, 50%
        single_measure = (num + opt_sp + units_map).optimize()

        # Fractions with units: ½ L -> ครึ่งลิตร / เศษหนึ่งส่วนสองลิตร
        frac_measure = (fraction.fraction_numbers + opt_sp + units_map).optimize()

        # Prefix modifiers: ~50 -> ประมาณห้าสิบ, ~10 km -> ประมาณสิบกิโลเมตร, ±5 -> บวกลบห้า, ±10% -> บวกลบสิบเปอร์เซ็นต์
        approx_sym = pynini.cross("~", "ประมาณ")
        plus_minus_sym = pynini.cross("±", "บวกลบ")
        prefix_modifier = approx_sym | plus_minus_sym

        prefixed_measure = (
            prefix_modifier
            + opt_sp
            + (single_measure | num)
        ).optimize()

        # Measure ranges: 5–10 kg -> ห้าถึงสิบกิโลกรัม, 10–15% -> สิบถึงสิบห้าเปอร์เซ็นต์
        dash = pynini.union("-", "–", "—", "~", "〜", "～")
        range_op = opt_sp + pynini.cross(dash, "ถึง") + opt_sp
        measure_range = (
            num
            + range_op
            + num
            + opt_sp
            + units_map
        ).optimize()

        # Repeated unit measure range: 5 kg - 10 kg
        repeated_measure_range = (
            single_measure
            + range_op
            + single_measure
        ).optimize()

        all_measure = (
            pynutil.add_weight(measure_range, -1.5)
            | pynutil.add_weight(repeated_measure_range, 1.03)
            | pynutil.add_weight(prefixed_measure, 1.04)
            | pynutil.add_weight(frac_measure, 1.05)
            | pynutil.add_weight(single_measure, 1.06)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_measure)
            + pynutil.insert('"')
        ).optimize()
