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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.da.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Danish measurements and units.
    Handles:
      - Units: SI, computing, speed, temperature, time, power, electrical, etc.
      - Agreement: "1 m" -> "en meter", "2 m" -> "to meter", "1 kg" -> "et kilogram", "1 °C" -> "en grad celsius"
      - Glued inputs: "50kg", "100m", "250ml", "37°C", "-15°C", "120km/h", "64GB", "2,4GHz"
      - Decimals with units: "3,5 mm", "1,5km", "99,9%"
      - Percent and permille: "5%", "50%", "10-15%", "5‰"
      - Negative values: "-12kg", "-15°C", "-5 °C"
      - Measure ranges: "5-10 kg" -> "fem til ti kilogram", "10-15%" -> "ti til femten procent"
    """

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Unit tuples: (symbol, singular, plural, gender: 'c' (en) or 'n' (et))
        units = [
            # Length
            ("kilometer", "kilometer", "kilometer", "c"),
            ("km", "kilometer", "kilometer", "c"),
            ("meter", "meter", "meter", "c"),
            ("m", "meter", "meter", "c"),
            ("centimeter", "centimeter", "centimeter", "c"),
            ("cm", "centimeter", "centimeter", "c"),
            ("millimeter", "millimeter", "millimeter", "c"),
            ("mm", "millimeter", "millimeter", "c"),
            ("mikrometer", "mikrometer", "mikrometer", "c"),
            ("µm", "mikrometer", "mikrometer", "c"),
            ("μm", "mikrometer", "mikrometer", "c"),
            # Mass
            ("kilogram", "kilogram", "kilogram", "n"),
            ("kg", "kilogram", "kilogram", "n"),
            ("kilo", "kilo", "kilo", "n"),
            ("gram", "gram", "gram", "n"),
            ("g", "gram", "gram", "n"),
            ("milligram", "milligram", "milligram", "n"),
            ("mg", "milligram", "milligram", "n"),
            ("mikrogram", "mikrogram", "mikrogram", "n"),
            ("µg", "mikrogram", "mikrogram", "n"),
            ("μg", "mikrogram", "mikrogram", "n"),
            ("ton", "ton", "ton", "n"),
            ("t", "ton", "ton", "n"),
            # Volume
            ("liter", "liter", "liter", "c"),
            ("l", "liter", "liter", "c"),
            ("deciliter", "deciliter", "deciliter", "c"),
            ("dl", "deciliter", "deciliter", "c"),
            ("milliliter", "milliliter", "milliliter", "c"),
            ("ml", "milliliter", "milliliter", "c"),
            # Speed
            ("km/t", "kilometer i timen", "kilometer i timen", "c"),
            ("km/h", "kilometer i timen", "kilometer i timen", "c"),
            ("m/s", "meter i sekundet", "meter i sekundet", "c"),
            # Temperature
            ("°C", "grad celsius", "grader celsius", "c"),
            ("°F", "grad fahrenheit", "grader fahrenheit", "c"),
            ("°", "grad", "grader", "c"),
            ("K", "kelvin", "kelvin", "c"),
            ("grader", "grad", "grader", "c"),
            # Time
            ("sekunder", "sekund", "sekunder", "n"),
            ("sekund", "sekund", "sekunder", "n"),
            ("sek", "sekund", "sekunder", "n"),
            ("s", "sekund", "sekunder", "n"),
            ("minutter", "minut", "minutter", "n"),
            ("minut", "minut", "minutter", "n"),
            ("min", "minut", "minutter", "n"),
            ("timer", "time", "timer", "c"),
            ("time", "time", "timer", "c"),
            ("tim", "time", "timer", "c"),
            ("h", "time", "timer", "c"),
            ("dage", "dag", "dage", "c"),
            ("dag", "dag", "dage", "c"),
            ("år", "år", "år", "n"),
            # Data & Network
            ("Gbps", "gigabit i sekundet", "gigabit i sekundet", "c"),
            ("Mbps", "megabit i sekundet", "megabit i sekundet", "c"),
            ("kbps", "kilobit i sekundet", "kilobit i sekundet", "c"),
            ("bps", "bit i sekundet", "bit i sekundet", "c"),
            ("GB", "gigabyte", "gigabyte", "c"),
            ("MB", "megabyte", "megabyte", "c"),
            ("kB", "kilobyte", "kilobyte", "c"),
            ("KB", "kilobyte", "kilobyte", "c"),
            ("TB", "terabyte", "terabyte", "c"),
            ("B", "byte", "byte", "c"),
            # Frequency
            ("GHz", "gigahertz", "gigahertz", "c"),
            ("MHz", "megahertz", "megahertz", "c"),
            ("kHz", "kilohertz", "kilohertz", "c"),
            ("Hz", "hertz", "hertz", "c"),
            # Power / Energy / Electrical
            ("mAh", "milliamperetime", "milliamperetimer", "c"),
            ("Ah", "amperetime", "amperetimer", "c"),
            ("kWh", "kilowatt-time", "kilowatt-timer", "c"),
            ("Wh", "watt-time", "watt-timer", "c"),
            ("hPa", "hektopascal", "hektopascal", "c"),
            ("Pa", "pascal", "pascal", "c"),
            ("bar", "bar", "bar", "c"),
            ("kcal", "kilokalori", "kilokalorier", "c"),
            ("cal", "kalori", "kalorier", "c"),
            ("J", "joule", "joule", "c"),
            ("kJ", "kilojoule", "kilojoule", "c"),
            ("dB", "decibel", "decibel", "c"),
            ("Ω", "ohm", "ohm", "c"),
            ("Ω", "ohm", "ohm", "c"),
            ("W", "watt", "watt", "c"),
            ("kW", "kilowatt", "kilowatt", "c"),
            ("MW", "megawatt", "megawatt", "c"),
            # Area & Volume superscripts
            ("m²", "kvadratmeter", "kvadratmeter", "c"),
            ("km²", "kvadratkilometer", "kvadratkilometer", "c"),
            ("cm²", "kvadratcentimeter", "kvadratcentimeter", "c"),
            ("mm²", "kvadratmillimeter", "kvadratmillimeter", "c"),
            ("m³", "kubikmeter", "kubikmeter", "c"),
            ("cm³", "kubikcentimeter", "kubikcentimeter", "c"),
            # Percent & Permille
            ("%", "procent", "procent", "c"),
            ("‰", "promille", "promille", "c"),
            ("pct.", "procent", "procent", "c"),
            ("pct", "procent", "procent", "c"),
        ]

        # Negative sign: "-" or "−" -> "minus "
        minus_sign = pynini.cross(pynini.union("-", "−"), "minus ")
        optional_minus = pynini.closure(minus_sign, 0, 1)

        # Approximate ("~") and plus-minus ("±")
        approx_sign = pynini.cross("~", "cirka ")
        plus_minus_sign = pynini.cross("±", "plus-minus ")
        opt_prefix = pynini.closure(minus_sign | approx_sign | plus_minus_sign, 0, 1)

        unit_graphs = []

        num_int = (
            pynutil.add_weight(cardinal.integer_with_et, -0.01)
            | cardinal.integer_common
        )
        not_one_digits = pynini.difference(pynini.closure(NEMO_DIGIT, 1), "1")
        multi_num_int = (not_one_digits @ num_int).optimize()
        for sym, sing, plur, gen in units:
            one_word = "en" if gen == "c" else "et"

            # 1 + singular unit: e.g. "1 kg" -> "et kilogram", "1 m" -> "en meter"
            one_graph = pynini.cross("1", f"{one_word} {sing}")

            # > 1 integer + plural unit: e.g. "2 kg" -> "to kilogram", "50 kg" -> "halvtreds kilogram"
            # Support "et hundrede" / "et tusind" for 100/1000 with units (e.g. 100m -> et hundrede meter)
            multi_graph = multi_num_int + pynutil.insert(f" {plur}")

            int_unit = (one_graph | multi_graph) + opt_sp + pynutil.delete(sym)

            # Decimal + unit: e.g. "3,5 mm" -> "tre komma fem millimeter", "1,5km" -> "en komma fem kilometer"
            dec_unit = decimal.core_decimal + opt_sp + pynutil.insert(f" {plur}") + opt_sp + pynutil.delete(sym)

            unit_graphs.append(int_unit | dec_unit)

        core_measure = pynini.union(*unit_graphs)

        # Measure range: "5-10 kg" -> "fem til ti kilogram", "5–10 kg", "10-15%" -> "ti til femten procent"
        range_dash = pynini.cross(pynini.union("-", "–", "—"), " til ")
        measure_range = (
            cardinal.integer_common
            + opt_sp
            + range_dash
            + opt_sp
            + core_measure
        )
        measure_range_repeated = (
            core_measure
            + opt_sp
            + range_dash
            + opt_sp
            + core_measure
        )

        all_measures = opt_prefix + (
            measure_range_repeated
            | measure_range
            | core_measure
        )

        all_measures = pynutil.add_weight(all_measures, -0.05)

        self.graph = all_measures.optimize()

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
