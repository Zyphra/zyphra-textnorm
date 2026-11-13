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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.tr.taggers.decimal import DecimalFst


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measurements in Turkish:
    - 50 kg / 50kg -> elli kilogram
    - 100 m / 100m -> yüz metre
    - 250 ml / 250ml -> iki yüz elli mililitre
    - 1,5 km / 1,5km -> bir virgül beş kilometre
    - 37°C -> otuz yedi derece
    - -15°C -> eksi on beş derece
    - 120 km/h / 120km/h -> yüz yirmi kilometre bölü saat
    - 64 GB / 64GB -> altmış dört gigabayt
    - 2,4 GHz / 2,4GHz -> iki virgül dört gigahertz
    - 5–10 kg -> beş ila on kilogram
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        decimal: DecimalFst = None,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)

        unit_map = pynini.string_map([
            # Length
            ("km", "kilometre"),
            ("km.", "kilometre"),
            ("m", "metre"),
            ("m.", "metre"),
            ("cm", "santimetre"),
            ("cm.", "santimetre"),
            ("mm", "milimetre"),
            ("mm.", "milimetre"),
            ("µm", "mikrometre"),
            ("um", "mikrometre"),
            ("nm", "nanometre"),
            # Weight
            ("kg", "kilogram"),
            ("kg.", "kilogram"),
            ("g", "gram"),
            ("g.", "gram"),
            ("gr", "gram"),
            ("gr.", "gram"),
            ("mg", "miligram"),
            ("mg.", "miligram"),
            ("µg", "mikrogram"),
            ("ug", "mikrogram"),
            ("t", "ton"),
            # Volume
            ("l", "litre"),
            ("L", "litre"),
            ("lt", "litre"),
            ("lt.", "litre"),
            ("ml", "mililitre"),
            ("mL", "mililitre"),
            ("cl", "santilitre"),
            ("cL", "santilitre"),
            ("dl", "desilitre"),
            ("dL", "desilitre"),
            # Speed
            ("km/h", "kilometre bölü saat"),
            ("km/s", "kilometre bölü saat"),
            ("kmh", "kilometre bölü saat"),
            ("m/s", "metre bölü saniye"),
            ("mph", "mil bölü saat"),
            # Area & volume
            ("m²", "metrekare"),
            ("m2", "metrekare"),
            ("m³", "metreküp"),
            ("m3", "metreküp"),
            ("cm²", "santimetrekare"),
            ("cm2", "santimetrekare"),
            ("cm³", "santimetreküp"),
            ("cm3", "santimetreküp"),
            ("km²", "kilometrekare"),
            ("km2", "kilometrekare"),
            ("mm²", "milimetrekare"),
            ("mm2", "milimetrekare"),
            # Temperature & angles
            ("°C", "derece"),
            ("℃", "derece"),
            ("°F", "derece fahrenheit"),
            ("℉", "derece fahrenheit"),
            ("°", "derece"),
            # Computing & data
            ("B", "bayt"),
            ("KB", "kilobayt"),
            ("kB", "kilobayt"),
            ("Kb", "kilobit"),
            ("MB", "megabayt"),
            ("Mb", "megabit"),
            ("GB", "gigabayt"),
            ("Gb", "gigabit"),
            ("TB", "terabayt"),
            ("Tb", "terabit"),
            ("PB", "petabayt"),
            ("kbps", "kilobit bölü saniye"),
            ("Kbps", "kilobit bölü saniye"),
            ("Mbps", "megabit bölü saniye"),
            ("Gbps", "gigabit bölü saniye"),
            # Electrical & Physics
            ("Hz", "hertz"),
            ("kHz", "kilohertz"),
            ("MHz", "megahertz"),
            ("GHz", "gigahertz"),
            ("W", "vat"),
            ("kW", "kilovat"),
            ("MW", "megavat"),
            ("GW", "gigavat"),
            ("kWh", "kilovatsaat"),
            ("kwh", "kilovatsaat"),
            ("V", "volt"),
            ("kV", "kilovolt"),
            ("mV", "milivolt"),
            ("A", "amper"),
            ("mA", "miliamper"),
            ("mAh", "miliamper saat"),
            ("Ah", "amper saat"),
            ("hPa", "hektopaskal"),
            ("Pa", "paskal"),
            ("bar", "bar"),
            ("kcal", "kilokalori"),
            ("cal", "kalori"),
            ("kJ", "kilojul"),
            ("J", "jul"),
            ("dB", "desibel"),
            ("Ω", "ohm"),
            ("ohm", "ohm"),
        ])

        opt_neg = pynini.closure(pynini.cross(pynini.union("-", "−"), "eksi "), 0, 1)
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        num_graph = decimal.all_decimals | (opt_neg + cardinal.positive_cardinals)

        # 1. Number + unit (spaced or glued)
        # Glued units must not match inside ordinary words (handled by token boundaries)
        num_unit = (
            num_graph
            + opt_sp
            + pynutil.insert(" ")
            + unit_map
        )

        # 2. Measure range: 5-10 kg, 5–10 kg
        dash = pynini.union("-", "–", "—")
        measure_range = (
            num_graph
            + opt_sp
            + pynini.cross(dash, " ila ")
            + opt_sp
            + num_graph
            + opt_sp
            + pynutil.insert(" ")
            + unit_map
        )

        all_measures = (measure_range | num_unit).optimize()
        self.all_measures = all_measures

        self.fst = (pynutil.insert('name: "') + convert_space(all_measures) + pynutil.insert('"')).optimize()
