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
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.he.taggers.decimal import DecimalFst


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew measurements and units.
    Handles length, area, volume, mass, speed, computing, electrical, temperature,
    glued units (50kg, 100m, 250ml, 1.5km, 120km/h, 64GB, 2.4GHz, 37°C),
    and measure ranges (5–10 kg).
    """

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        # ----------------- Unit Name Mappings -----------------
        unit_map = [
            # Length
            ("km", " קילומטר"),
            ("ק\"מ", " קילומטר"),
            ("ק״מ", " קילומטר"),
            ("m", " מטר"),
            ("מטר", " מטר"),
            ("cm", " סנטימטר"),
            ("ס\"מ", " סנטימטר"),
            ("ס״מ", " סנטימטר"),
            ("mm", " מילימטר"),
            ("מ\"מ", " מילימטר"),
            ("מ״מ", " מילימטר"),
            ("µm", " מיקרומטר"),
            ("μm", " מיקרומטר"),
            # Area & Volume superscripts
            ("km²", " קילומטר רבוע"),
            ("קמ\"ר", " קילומטר רבוע"),
            ("קמ״ר", " קילומטר רבוע"),
            ("m²", " מטר רבוע"),
            ("מ\"ר", " מטר רבוע"),
            ("מ״ר", " מטר רבוע"),
            ("cm²", " סנטימטר רבוע"),
            ("סמ\"ר", " סנטימטר רבוע"),
            ("סמ״ר", " סנטימטר רבוע"),
            ("mm²", " מילימטר רבוע"),
            ("m³", " מטר מעוקב"),
            ("מ\"ק", " מטר מעוקב"),
            ("מ״ק", " מטר מעוקב"),
            ("cm³", " סנטימטר מעוקב"),
            ("סמ\"ק", " סנטימטר מעוקב"),
            ("סמ״ק", " סנטימטר מעוקב"),
            # Volume
            ("ml", " מיליליטר"),
            ("mL", " מיליליטר"),
            ("מ\"ל", " מיליליטר"),
            ("מ״ל", " מיליליטר"),
            ("l", " ליטר"),
            ("L", " ליטר"),
            ("ליטר", " ליטר"),
            # Mass
            ("kg", " קילוגרם"),
            ("ק\"ג", " קילוגרם"),
            ("ק״ג", " קילוגרם"),
            ("g", " גרם"),
            ("גרם", " גרם"),
            ("mg", " מיליגרם"),
            ("מ\"ג", " מיליגרם"),
            ("מ״ג", " מיליגרם"),
            ("µg", " מיקרוגרם"),
            ("μg", " מיקרוגרם"),
            ("t", " טון"),
            ("טון", " טון"),
            # Speed
            ("km/h", " קילומטר לשעה"),
            ("קמ\"ש", " קילומטר לשעה"),
            ("קמ״ש", " קילומטר לשעה"),
            ("mph", " מיל לשעה"),
            # Time
            ("s", " שניות"),
            ("sec", " שניות"),
            ("שנ'", " שניות"),
            ("min", " דקות"),
            ("דק'", " דקות"),
            ("h", " שעות"),
            ("hr", " שעות"),
            ("ש'", " שעות"),
            # Computing / Data
            ("GB", " גיגהבייט"),
            ("ג\"ב", " גיגהבייט"),
            ("ג״ב", " גיגהבייט"),
            ("MB", " מגהבייט"),
            ("מ\"ב", " מגהבייט"),
            ("מ״ב", " מגהבייט"),
            ("KB", " קילובייט"),
            ("ק\"ב", " קילובייט"),
            ("ק״ב", " קילובייט"),
            ("TB", " טרבייט"),
            ("ט\"ב", " טרבייט"),
            ("ט״ב", " טרבייט"),
            ("B", " בייט"),
            # Network rates
            ("Gbps", " גיגהביט לשנייה"),
            ("Mbps", " מגהביט לשנייה"),
            ("kbps", " קילוביט לשנייה"),
            # Electrical / Physics / Scientific
            ("kWh", " קילוואט שעה"),
            ("Wh", " וואט שעה"),
            ("mAh", " מיליאמפר שעה"),
            ("Ah", " אמפר שעה"),
            ("kW", " קילוואט"),
            ("W", " וואט"),
            ("V", " וולט"),
            ("A", " אמפר"),
            ("GHz", " גיגההרץ"),
            ("MHz", " מגההרץ"),
            ("kHz", " קילוהרץ"),
            ("Hz", " הרץ"),
            ("hPa", " הקטופסקל"),
            ("kcal", " קילו קלוריות"),
            ("dB", " דציבל"),
            ("Ω", " אוהם"),
            ("Ω", " אוהם"),
            # Temperature
            ("°C", " מעלות צלזיוס"),
            ("℃", " מעלות צלזיוס"),
            ("°F", " מעלות פרנהייט"),
            ("℉", " מעלות פרנהייט"),
            ("°", " מעלות"),
        ]

        units_fst = pynini.string_map(unit_map)
        self.units_fst = units_fst

        # Numbers before units:
        # 1 kg -> קילוגרם אחד or אחד קילוגרם
        # 2 kg -> שני קילוגרמים or שני קילוגרם
        # 3-10 kg -> שלושה..עשרה קילוגרמים or קילוגרם
        # 50kg -> חמישים קילוגרם
        # 1.5km -> אחת נקודה חמש קילומטר
        num_m = cardinal.base_num_m
        num_f = cardinal.base_num_f
        num_dec = decimal.decimal_num

        # Negative numbers before units (e.g. -5 °C, -15°C)
        neg = pynini.cross("-", "מינוס ") | pynini.cross("−", "מינוס ")
        opt_neg = pynini.closure(neg, 0, 1)

        num_for_measure = (
            opt_neg
            + (
                pynutil.add_weight(num_dec, 0.9)
                | pynutil.add_weight(num_m, 0.95)
                | pynutil.add_weight(num_f, 1.05)
            )
        ).optimize()

        # Plural forms for 3-10 km, kg, km/h
        num_3_10_m = (
            pynini.union("3", "4", "5", "6", "7", "8", "9", "10") @ num_m
        )
        plural_km_kg = (
            pynini.cross(pynini.union("km", "ק\"מ", "ק״מ"), " קילומטרים")
            | pynini.cross(pynini.union("km/h", "קמ\"ש", "קמ״ש"), " קילומטרים לשעה")
            | pynini.cross(pynini.union("kg", "ק\"ג", "ק״ג"), " קילוגרמים")
        )
        measure_3_10_plural = num_3_10_m + opt_space + plural_km_kg
        measure_3_10_plural_range = (
            num_3_10_m
            + opt_space
            + pynini.cross(pynini.union("-", "–", "—", "־"), " עד ")
            + opt_space
            + num_3_10_m
            + opt_space
            + plural_km_kg
        )

        # Temperature units use feminine numerals
        temp_units = pynini.union("°C", "℃", "°F", "℉", "°") @ units_fst
        temp_expr = opt_neg + num_f + opt_space + temp_units

        # Measurement: <number> + opt_space + <unit>
        measure_expr = num_for_measure + opt_space + units_fst

        # Measure ranges: 5–10 kg, 5-10 kg -> חמישה עד עשרה קילוגרמים
        dash = pynini.union("-", "–", "—", "־")
        measure_range = (
            num_for_measure
            + opt_space
            + pynini.cross(dash, " עד ")
            + opt_space
            + num_for_measure
            + opt_space
            + units_fst
        ).optimize()

        all_measures = (
            pynutil.add_weight(measure_3_10_plural_range, 0.82)
            | pynutil.add_weight(measure_3_10_plural, 0.85)
            | pynutil.add_weight(temp_expr, 0.87)
            | pynutil.add_weight(measure_range, 0.89)
            | pynutil.add_weight(measure_expr, 0.90)
        ).optimize()
        self.fst = (
            pynutil.insert('name: "') + convert_space(all_measures) + pynutil.insert('"')
        ).optimize()
