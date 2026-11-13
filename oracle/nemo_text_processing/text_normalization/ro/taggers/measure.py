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
)
from nemo_text_processing.text_normalization.ro.graph_utils import (
    RO_DASH,
    decimal_separator,
    to_name_token,
)
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.ro.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.ro.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.ro.taggers.money import _build_counted_phrase


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Romanian measurements, e.g.
        "1 m" -> tokens { name: "un metru" }
        "2 metri" -> tokens { name: "doi metri" }
        "20 m" -> tokens { name: "douăzeci de metri" }
        "50kg" -> tokens { name: "cincizeci de kilograme" }
        "100m" -> tokens { name: "o sută de metri" }
        "250ml" -> tokens { name: "două sute cincizeci de mililitri" }
        "1,5km" -> tokens { name: "unu virgulă cinci kilometri" }
        "37°C" -> tokens { name: "treizeci și șapte de grade celsius" }
        "-15°C" -> tokens { name: "minus cincisprezece grade celsius" }
        "120km/h" -> tokens { name: "o sută douăzeci de kilometri pe oră" }
        "64GB" -> tokens { name: "șaizeci și patru de gigabyți" }
        "2,4GHz" -> tokens { name: "două virgulă patru gigahertz" }
        "10 Gbps" -> tokens { name: "zece gigabiți pe secundă" }
        "5000 mAh" -> tokens { name: "cinci mii de miliamperi-oră" }
        "100 Ω" -> tokens { name: "o sută de ohmi" }
        "10-15%" -> tokens { name: "zece până la cincisprezece la sută" }
        "5-10 kg" -> tokens { name: "cinci până la zece kilograme" }
        "1/2 kg" -> tokens { name: "o jumătate de kilogram" }
        "2 1/2 kg" -> tokens { name: "două kilograme și jumătate" }
        "~10 km" -> tokens { name: "aproximativ zece kilometri" }
    """

    def __init__(
        self,
        cardinal: CardinalFst,
        decimal: DecimalFst,
        fraction: FractionFst,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        minus_prefix = pynutil.delete(pynini.union("-", "−")) + pynutil.insert("minus ")
        approx_prefix = pynutil.delete("~") + pynutil.insert("aproximativ ")

        # Unit definitions: (symbols_fst, singular, plural, gender)
        unit_defs = [
            # Weight
            (pynini.union("kg", "KG", "kilograme", "kilogram"), "kilogram", "kilograme", "neut"),
            (pynini.union("g", "G", "grame", "gram"), "gram", "grame", "neut"),
            (pynini.union("mg", "MG", "miligrame", "miligram"), "miligram", "miligrame", "neut"),
            (pynini.union("µg", "μg", "ug", "micrograme"), "microgram", "micrograme", "neut"),
            (pynini.union("t", "tone", "tonă"), "tonă", "tone", "fem"),
            # Length
            (pynini.union("km", "KM", "kilometri", "kilometru"), "kilometru", "kilometri", "masc"),
            (pynini.union("m", "metri", "metru"), "metru", "metri", "masc"),
            (pynini.union("cm", "CM", "centimetri", "centimetru"), "centimetru", "centimetri", "masc"),
            (pynini.union("mm", "MM", "milimetri", "milimetru"), "milimetru", "milimetri", "masc"),
            (pynini.union("µm", "μm", "um", "micrometri"), "micrometru", "micrometri", "masc"),
            # Area & Volume
            (pynini.union("m²", "mp", "metri pătrați"), "metru pătrat", "metri pătrați", "masc"),
            (pynini.union("km²", "kmp", "kilometri pătrați"), "kilometru pătrat", "kilometri pătrați", "masc"),
            (pynini.union("m³", "mc", "metri cubi"), "metru cub", "metri cubi", "masc"),
            # Liquid
            (pynini.union("l", "L", "litri", "litru"), "litru", "litri", "masc"),
            (pynini.union("ml", "mL", "ML", "mililitri", "mililitru"), "mililitru", "mililitri", "masc"),
            # Temperature
            (pynini.union("°C", "℃", "grade Celsius", "grade celsius"), "grad celsius", "grade celsius", "neut"),
            (pynini.union("°F", "℉", "grade Fahrenheit", "grade fahrenheit"), "grad fahrenheit", "grade fahrenheit", "neut"),
            (pynini.union("°", "grade", "grad"), "grad", "grade", "neut"),
            # Speed
            (pynini.union("km/h", "kmh", "km/oră"), "kilometru pe oră", "kilometri pe oră", "masc"),
            (pynini.union("m/s", "ms"), "metru pe secundă", "metri pe secundă", "masc"),
            # Computing & Data
            (pynini.union("GB", "gb", "gigabytes", "gigabyți"), "gigabyte", "gigabyți", "masc"),
            (pynini.union("MB", "mb", "megabytes", "megabyți"), "megabyte", "megabyți", "masc"),
            (pynini.union("KB", "kb", "kilobytes", "kilobyți"), "kilobyte", "kilobyți", "masc"),
            (pynini.union("TB", "tb", "terabytes", "terabyți"), "terabyte", "terabyți", "masc"),
            (pynini.union("B", "bytes", "byți"), "byte", "byți", "masc"),
            (pynini.union("bit", "biți"), "bit", "biți", "masc"),
            (pynini.union("Gbps", "gbps"), "gigabit pe secundă", "gigabiți pe secundă", "masc"),
            (pynini.union("Mbps", "mbps"), "megabit pe secundă", "megabiți pe secundă", "masc"),
            (pynini.union("kbps", "Kbps"), "kilobit pe secundă", "kilobiți pe secundă", "masc"),
            # Frequency
            (pynini.union("GHz", "ghz"), "gigahertz", "gigahertz", "neut"),
            (pynini.union("MHz", "mhz"), "megahertz", "megahertz", "neut"),
            (pynini.union("kHz", "khz"), "kilohertz", "kilohertz", "neut"),
            (pynini.union("Hz", "hz"), "hertz", "hertz", "neut"),
            # Electrical & Scientific
            (pynini.union("kWh", "kwh"), "kilowatt-oră", "kilowați-oră", "masc"),
            (pynini.union("mAh", "mah"), "miliamper-oră", "miliamperi-oră", "masc"),
            (pynini.union("hPa", "hpa"), "hectopascal", "hectopascali", "masc"),
            (pynini.union("kcal", "calorii"), "kilocalorie", "kilocalorii", "fem"),
            (pynini.union("dB", "db"), "decibel", "decibeli", "masc"),
            (pynini.union("Ω", "Ω", "ohmi"), "ohm", "ohmi", "masc"),
            (pynini.union("W", "wați", "watt"), "watt", "wați", "masc"),
            (pynini.union("kW", "kilowați"), "kilowatt", "kilowați", "masc"),
            (pynini.union("V", "volți"), "volt", "volți", "masc"),
            (pynini.union("A", "amperi"), "amper", "amperi", "masc"),
            # Time duration
            (pynini.union("h", "ore", "oră"), "oră", "ore", "fem"),
            (pynini.union("min", "minute", "minut"), "minut", "minute", "neut"),
            (pynini.union("s", "sec", "secunde", "secundă"), "secundă", "secunde", "fem"),
            (pynini.union("zile", "zi"), "zi", "zile", "fem"),
            (pynini.union("luni", "lună"), "lună", "luni", "fem"),
            (pynini.union("ani", "an"), "an", "ani", "masc"),
        ]

        # Decimal numbers helper
        dec_trans = (
            cardinal.cardinal_numbers
            + pynutil.delete(decimal_separator)
            + pynutil.insert(" virgulă ")
            + cardinal.digit
        )

        all_unit_rules = []
        range_rules = []

        for sym_fst, sing, plur, gender in unit_defs:
            counted = _build_counted_phrase(cardinal, sing, plur, gender=gender)

            # Integer measurement: "50 kg", "50kg"
            int_meas = (counted + opt_space + pynutil.delete(sym_fst)).optimize()

            # Decimal measurement: "1,5 km", "1.5km"
            dec_meas = (
                dec_trans
                + opt_space
                + pynutil.delete(sym_fst)
                + pynutil.insert(" " + plur)
            ).optimize()

            # Negative measurement: "-15°C"
            unit_rule = (
                pynini.closure(minus_prefix, 0, 1)
                + pynini.closure(approx_prefix, 0, 1)
                + (dec_meas | int_meas)
            ).optimize()
            all_unit_rules.append(unit_rule)

            # Range of measures: 5-10 kg -> cinci până la zece kilograme
            num_range_words = cardinal.cardinal_numbers
            dash = pynini.cross(RO_DASH, " până la ")
            meas_range = (
                num_range_words
                + opt_space
                + dash
                + opt_space
                + int_meas
            ).optimize()
            range_rules.append(meas_range)

        # Percent rules:
        # 10% -> zece la sută
        # 10-15% -> zece până la cincisprezece la sută
        # ±10% -> plus-minus zece la sută
        # -5% -> minus cinci la sută
        pct_sym = pynutil.delete("%") + pynutil.insert(" la sută")
        permille_sym = pynutil.delete("‰") + pynutil.insert(" la mie")

        plus_minus_prefix = pynutil.delete("±") + pynutil.insert("plus-minus ")

        pct_single = (
            pynini.closure(plus_minus_prefix | minus_prefix, 0, 1)
            + cardinal.cardinal_numbers
            + opt_space
            + (pct_sym | permille_sym)
        ).optimize()

        # Decimal percent: 12,5% -> douăsprezece virgulă cinci la sută
        pct_dec = (
            pynini.closure(plus_minus_prefix | minus_prefix, 0, 1)
            + (cardinal.cardinal_numbers_fem | cardinal.cardinal_numbers)
            + pynutil.delete(decimal_separator)
            + pynutil.insert(" virgulă ")
            + cardinal.digit
            + opt_space
            + (pct_sym | permille_sym)
        ).optimize()

        pct_range = (
            cardinal.cardinal_numbers
            + opt_space
            + pynini.cross(RO_DASH, " până la ")
            + opt_space
            + cardinal.cardinal_numbers
            + opt_space
            + (pct_sym | permille_sym)
        ).optimize()

        # Fractions with units:
        # 1/2 kg -> o jumătate de kilogram
        # 2 1/2 kg -> două kilograme și jumătate
        half_kg = (
            pynini.cross("1/2", "o jumătate de")
            | pynini.cross("½", "o jumătate de")
        ) + opt_space + pynutil.delete(pynini.union("kg", "kilogram")) + pynutil.insert(" kilogram")

        half_hour = (
            pynini.cross("1/2", "o jumătate de")
            | pynini.cross("½", "o jumătate de")
        ) + opt_space + pynutil.delete(pynini.union("h", "oră")) + pynutil.insert(" oră")

        mixed_kg = (
            pynini.cross("2 1/2", "două kilograme și jumătate")
            | pynini.cross("2½", "două kilograme și jumătate")
        ) + opt_space + pynutil.delete(pynini.union("kg", "kilogram", "kilograme"))

        composite = (
            pynini.union(*range_rules)
            | pct_range
            | pct_dec
            | pct_single
            | half_kg
            | half_hour
            | mixed_kg
            | pynini.union(*all_unit_rules)
        ).optimize()

        self.fst = to_name_token(composite)
