# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.cs.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.cs.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_SIGMA,
    GraphFst,
)


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Czech units of measurement,
    temperatures, speeds, rates, computing/scientific units, and measure ranges.
    """

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        other_number = pynini.difference(
            pynini.project(cardinal.positive_numbers, "input"), pynini.union("1", "2", "3", "4")
        ) @ cardinal.positive_numbers
        feminine_other = other_number @ pynini.cdrewrite(
            pynini.string_map([("jeden", "jedna"), ("dva", "dvě")]),
            pynini.union("[BOS]", " "), "[EOS]", NEMO_SIGMA,
        )

        # Helper for unit agreement:
        # 1 -> singular
        # 2, 3, 4 -> few
        # 5+ -> other (plural genitive)
        # decimals -> genitive singular or plural
        def build_unit_fst(unit_syms, sing, few, other, is_fem=False):
            sym = pynutil.delete(pynini.union(*unit_syms))
            n1 = pynini.cross("1", "jedna" if is_fem else "jeden") + opt_sp + pynutil.insert(f" {sing}") + sym
            ending_few_digits = pynini.string_map([
                ("2", "dvě" if is_fem else "dva"),
                ("3", "tři"),
                ("4", "čtyři"),
            ])
            n_few = (
                ending_few_digits
                + opt_sp
                + pynutil.insert(f" {few}")
                + sym
            )
            n_other = (feminine_other if is_fem else other_number) + opt_sp + pynutil.insert(f" {other}") + sym
            genitive = few if is_fem else sing + "u"
            n_dec = decimal.decimal_numbers + opt_sp + pynutil.insert(f" {genitive}") + sym
            return (pynutil.add_weight(n1, -0.01) | pynutil.add_weight(n_few, -0.01) | n_other | n_dec).optimize()

        # Length
        km = build_unit_fst(["km", "kilometr", "kilometry", "kilometrů"], "kilometr", "kilometry", "kilometrů")
        m = build_unit_fst(["m", "metr", "metry", "metrů"], "metr", "metry", "metrů")
        cm = build_unit_fst(["cm", "centimetr", "centimetry", "centimetrů"], "centimetr", "centimetry", "centimetrů")
        mm = build_unit_fst(["mm", "milimetr", "milimetry", "milimetrů"], "milimetr", "milimetry", "milimetrů")
        um = build_unit_fst(["µm", "μm"], "mikrometr", "mikrometry", "mikrometrů")

        # Mass
        kg = build_unit_fst(["kg", "kilogram", "kilogramy", "kilogramů", "kilo", "kila", "kil"], "kilogram", "kilogramy", "kilogramů")
        g = build_unit_fst(["g", "gram", "gramy", "gramů"], "gram", "gramy", "gramů")
        mg = build_unit_fst(["mg", "miligram", "miligramy", "miligramů"], "miligram", "miligramy", "miligramů")
        ug = build_unit_fst(["µg", "μg"], "mikrogram", "mikrogramy", "mikrogramů")
        t = build_unit_fst(["t", "tuna", "tuny", "tun"], "tuna", "tuny", "tun", is_fem=True)

        # Volume
        l = build_unit_fst(["l", "litr", "litry", "litrů"], "litr", "litry", "litrů")
        ml = build_unit_fst(["ml", "mililitr", "mililitry", "mililitrů"], "mililitr", "mililitry", "mililitrů")
        dl = build_unit_fst(["dl", "decilitr", "decilitry", "decilitrů"], "decilitr", "decilitry", "decilitrů")
        cl = build_unit_fst(["cl", "centilitr", "centilitry", "centilitrů"], "centilitr", "centilitry", "centilitrů")

        # Area & Volume
        m2 = (
            (cardinal.cardinal_numbers | decimal.decimal_numbers)
            + opt_sp
            + pynutil.insert(" metrů čtverečních")
            + pynutil.delete("m²")
        ).optimize()
        m3 = (
            (cardinal.cardinal_numbers | decimal.decimal_numbers)
            + opt_sp
            + pynutil.insert(" metrů krychlových")
            + pynutil.delete("m³")
        ).optimize()

        # Speed
        kmh = (
            (cardinal.cardinal_numbers | decimal.decimal_numbers)
            + opt_sp
            + pynutil.insert(" kilometrů za hodinu")
            + pynutil.delete(pynini.union("km/h", "km/hod"))
        ).optimize()
        ms = (
            (cardinal.cardinal_numbers | decimal.decimal_numbers)
            + opt_sp
            + pynutil.insert(" metrů za sekundu")
            + pynutil.delete(pynini.union("m/s", "m/sec"))
        ).optimize()

        # Temperature
        celsius_sym = pynutil.delete(pynini.union("°C", "℃", "st. C"))
        deg_1 = pynini.cross("1", "jeden stupeň Celsia") + opt_sp + celsius_sym
        deg_few = pynini.string_map([
            ("2", "dva"),
            ("3", "tři"),
            ("4", "čtyři"),
        ]) + opt_sp + pynutil.insert(" stupně Celsia") + celsius_sym
        deg_other = other_number + opt_sp + pynutil.insert(" stupňů Celsia") + celsius_sym
        deg_dec = decimal.decimal_numbers + opt_sp + pynutil.insert(" stupňů Celsia") + celsius_sym
        celsius = (deg_1 | deg_few | deg_other | deg_dec).optimize()

        # Bare degrees
        deg_sym = pynutil.delete("°")
        deg_bare_1 = pynini.cross("1", "jeden stupeň") + opt_sp + deg_sym
        deg_bare_few = pynini.string_map([
            ("2", "dva"),
            ("3", "tři"),
            ("4", "čtyři"),
        ]) + opt_sp + pynutil.insert(" stupně") + deg_sym
        deg_bare_other = other_number + opt_sp + pynutil.insert(" stupňů") + deg_sym
        bare_degrees = (deg_bare_1 | deg_bare_few | deg_bare_other).optimize()

        # Computing & Electrical & Scientific
        gbps = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" gigabitů za sekundu") + pynutil.delete("Gbps")
        mbps = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" megabitů za sekundu") + pynutil.delete("Mbps")
        mah = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" miliampérhodin") + pynutil.delete("mAh")
        kwh = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" kilowatthodin") + pynutil.delete("kWh")
        hpa = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" hektopascalů") + pynutil.delete("hPa")
        kcal = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" kilokalorií") + pynutil.delete("kcal")
        db = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" decibelů") + pynutil.delete("dB")
        ohm = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" ohmů") + pynutil.delete(pynini.union("Ω", "Ω"))
        gb = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" gigabajtů") + pynutil.delete("GB")
        ghz = (cardinal.cardinal_numbers | decimal.decimal_numbers) + opt_sp + pynutil.insert(" gigahertz") + pynutil.delete("GHz")

        scientific = (
            gbps | mbps | mah | kwh | hpa | kcal | db | ohm | gb | ghz
        ).optimize()

        measure_core = (
            celsius
            | bare_degrees
            | kmh
            | ms
            | m2
            | m3
            | scientific
            | km
            | m
            | cm
            | mm
            | um
            | kg
            | g
            | mg
            | ug
            | t
            | l
            | ml
            | dl
            | cl
        ).optimize()

        # Negatives: e.g. "-15°C", "-5 °C", "-12kg"
        neg_sym = pynini.cross("-", "mínus ") | pynini.cross("−", "mínus ")
        neg_measure = (neg_sym + measure_core).optimize()

        # Ranges: "5-10 kg", "5–10 kg", "5-10 km"
        dash = pynini.cross("-", " až ") | pynini.cross("–", " až ") | pynini.cross("—", " až ")
        measure_range = (
            (cardinal.cardinal_numbers | decimal.decimal_numbers)
            + opt_sp
            + dash
            + opt_sp
            + measure_core
        ).optimize()

        self.fst = (
            measure_range
            | neg_measure
            | measure_core
        ).optimize()
