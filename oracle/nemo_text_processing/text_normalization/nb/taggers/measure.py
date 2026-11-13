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
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)
from nemo_text_processing.text_normalization.nb.taggers.decimal import (
    DecimalFst,
)
from nemo_text_processing.text_normalization.nb.taggers.fraction import (
    FractionFst,
)


class MeasureFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål measurements.
    e.g. 2.5 kg -> to komma fem kilogram
         1 kg -> ett kilogram
         1 l -> en liter
         1 ss -> en spiseskje
         2 ss -> to spiseskjeer
         1 stk -> ett stykk
         5 stk -> fem stykker
         -1.5 °C -> minus en komma fem celsiusgrader
         10 Gbps -> ti gigabit per sekund
         5000 mAh -> femtusen milliamperetimer
         50 kWh -> femti kilowattimer
         100 Ω -> hundre ohm
         1/2 kg -> ett halvt kilogram
         5-10 kg -> fem til ti kilogram
         ~10 km -> omtrent ti kilometer
    """

    def __init__(
        self,
        cardinal: CardinalFst,
        decimal: DecimalFst,
        fraction: FractionFst,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        digits = pynini.closure(NEMO_DIGIT, 1)
        not_one = pynini.difference(digits, pynini.accep("1"))
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        # -------------------------------------------------------------
        # Neuter units (using "ett" for 1: ett gram, ett kilogram, ett tonn)
        # -------------------------------------------------------------
        neuter_units_map = [
            ("kg", "kilogram"),
            ("kilo", "kilo"),
            ("g", "gram"),
            ("mg", "milligram"),
            ("µg", "mikrogram"),
            ("μg", "mikrogram"),
            ("t", "tonn"),
        ]
        neuter_units = pynini.string_map(neuter_units_map)

        neuter_card_one = pynini.cross("1", "ett")
        neuter_card_many = not_one @ cardinal.cardinal_neuter
        neuter_card = neuter_card_one | neuter_card_many

        neuter_fraction = (
            pynini.cross("1/2", "ett halvt")
            | pynini.cross("½", "ett halvt")
            | pynini.cross("-1/2", "minus ett halvt")
            | pynini.cross("-½", "minus ett halvt")
            | (cardinal.cardinal_masculine + opt_space + pynutil.insert(" ") + pynini.cross("1/2", "og ett halvt"))
            | (cardinal.cardinal_masculine + opt_space + pynutil.insert(" ") + pynini.cross("½", "og ett halvt"))
        )

        neuter_num = (
            decimal.decimal_num
            | neuter_fraction
            | neuter_card
        )

        neuter_measure = neuter_num + opt_space + pynutil.insert(" ") + neuter_units

        # -------------------------------------------------------------
        # Common / Masculine / Invariable units
        # -------------------------------------------------------------
        invariable_units_map = [
            # Length
            ("km", "kilometer"),
            ("m", "meter"),
            ("cm", "centimeter"),
            ("mm", "millimeter"),
            ("µm", "mikrometer"),
            ("μm", "mikrometer"),
            # Volume
            ("l", "liter"),
            ("L", "liter"),
            ("dl", "desiliter"),
            ("cl", "centiliter"),
            ("ml", "milliliter"),
            ("mL", "milliliter"),
            # Area and volume powers
            ("m²", "kvadratmeter"),
            ("km²", "kvadratkilometer"),
            ("cm²", "kvadratcentimeter"),
            ("m³", "kubikkmeter"),
            ("cm³", "kubikkcentimeter"),
            # Speed / Rate
            ("km/t", "kilometer i timen"),
            ("km/h", "kilometer i timen"),
            ("m/s", "meter per sekund"),
            # Computing & Scientific
            ("Gbps", "gigabit per sekund"),
            ("Mbps", "megabit per sekund"),
            ("kbps", "kilobit per sekund"),
            ("bps", "bit per sekund"),
            ("GB", "gigabyte"),
            ("MB", "megabyte"),
            ("kB", "kilobyte"),
            ("KB", "kilobyte"),
            ("TB", "terabyte"),
            ("B", "byte"),
            ("W", "watt"),
            ("kW", "kilowatt"),
            ("MW", "megawatt"),
            ("GW", "gigawatt"),
            ("V", "volt"),
            ("kV", "kilovolt"),
            ("mV", "millivolt"),
            ("A", "ampere"),
            ("mA", "milliampere"),
            ("Hz", "hertz"),
            ("kHz", "kilohertz"),
            ("MHz", "megahertz"),
            ("GHz", "gigahertz"),
            ("hPa", "hektopascal"),
            ("Pa", "pascal"),
            ("bar", "bar"),
            ("dB", "desibel"),
            ("Ω", "ohm"),
            ("Ω", "ohm"),
            # Temperature
            ("°C", "celsiusgrader"),
            ("°F", "grader fahrenheit"),
        ]
        invariable_units = pynini.string_map(invariable_units_map)

        # Inflecting common units:
        inflect_sing_map = [
            ("ss", "spiseskje"),
            ("ts", "teskje"),
            ("tsk", "teskje"),
            ("kcal", "kilokalori"),
            ("cal", "kalori"),
            ("kWh", "kilowattime"),
            ("Wh", "wattime"),
            ("mAh", "milliamperetime"),
            ("Ah", "amperetime"),
            ("°", "grad"),
        ]
        inflect_plur_map = [
            ("ss", "spiseskjeer"),
            ("ts", "teskjeer"),
            ("tsk", "teskjeer"),
            ("kcal", "kilokalorier"),
            ("cal", "kalorier"),
            ("kWh", "kilowattimer"),
            ("Wh", "wattimer"),
            ("mAh", "milliamperetimer"),
            ("Ah", "amperetimer"),
            ("°", "grader"),
        ]
        inflect_sing_units = pynini.string_map(inflect_sing_map)
        inflect_plur_units = pynini.string_map(inflect_plur_map)

        # "stk" / "stk." (neuter: 1 stk -> ett stykk, 5 stk -> fem stykker)
        stk_sing = pynini.cross("stk.", "stykk") | pynini.cross("stk", "stykk")
        stk_plur = pynini.cross("stk.", "stykker") | pynini.cross("stk", "stykker")

        stk_measure = (
            (pynini.cross("1", "ett") + opt_space + pynutil.insert(" ") + stk_sing)
            | (not_one @ cardinal.cardinal_masculine + opt_space + pynutil.insert(" ") + stk_plur)
            | (decimal.decimal_num + opt_space + pynutil.insert(" ") + stk_plur)
        )

        common_card_one = pynini.cross("1", "en")
        common_card_many = not_one @ cardinal.cardinal_masculine
        common_card = common_card_one | common_card_many

        common_num = (
            decimal.decimal_num
            | fraction.fst
            | common_card
        )

        invariable_measure = common_num + opt_space + pynutil.insert(" ") + invariable_units

        inflecting_sing_measure = common_card_one + opt_space + pynutil.insert(" ") + inflect_sing_units
        inflecting_plur_measure = (
            common_card_many
            | decimal.decimal_num
            | fraction.fst
        ) + opt_space + pynutil.insert(" ") + inflect_plur_units
        inflecting_measure = inflecting_sing_measure | inflecting_plur_measure

        # Special casing for temperature: "20 °C" -> "grader celsius", "-1.5 °C" -> "minus en komma fem celsiusgrader"
        temp_unit = pynini.cross("°C", "grader celsius") | pynini.cross("°C", "celsiusgrader")
        temp_measure = common_num + opt_space + pynutil.insert(" ") + temp_unit

        single_measure = (
            neuter_measure
            | invariable_measure
            | inflecting_measure
            | stk_measure
            | temp_measure
        )

        # Approximate prefix: "~10 km", "~50"
        approx = (
            pynini.cross("~", "omtrent ")
            | pynini.cross("ca.", "cirka ")
            | pynini.cross("ca. ", "cirka ")
        )
        approx_measure = approx + single_measure

        # Measure ranges: 5-10 kg, 5–10 kg, 1,5-2,5 kg
        dash = (
            pynini.cross("-", " til ")
            | pynini.cross("–", " til ")
            | pynini.cross("—", " til ")
        )
        measure_range = (
            (common_num | neuter_num)
            + opt_space
            + dash
            + opt_space
            + single_measure
        )

        all_measures = (
            approx_measure
            | measure_range
            | single_measure
        )

        self.graph = all_measures.optimize()
        self.fst = self.graph
