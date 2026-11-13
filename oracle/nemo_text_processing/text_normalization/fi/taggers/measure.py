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
    insert_space,
)


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Finnish measurements with partitive agreement, e.g.
        "10 kg" -> tokens { name: "kymmenen kilogrammaa" }
        "50kg" -> tokens { name: "viisikymmentä kilogrammaa" }
        "100m" -> tokens { name: "sata metriä" }
        "250ml" -> tokens { name: "kaksisataaviisikymmentä millilitraa" }
        "1,5km" -> tokens { name: "yksi pilkku viisi kilometriä" }
        "37°C" -> tokens { name: "kolmekymmentäseitsemän celsiusastetta" }
        "-15°C" -> tokens { name: "miinus viisitoista celsiusastetta" }
        "120km/h" -> tokens { name: "satakaksikymmentä kilometriä tunnissa" }
        "64GB" -> tokens { name: "kuusikymmentäneljä gigatavua" }
        "2.4GHz" -> tokens { name: "kaksi pilkku neljä gigahertsiä" }
        "10 Gbps" -> tokens { name: "kymmenen gigabittiä sekunnissa" }
        "5000 mAh" -> tokens { name: "viisituhatta milliampeerituntia" }
        "50 kWh" -> tokens { name: "viisikymmentä kilowattituntia" }
        "100 Ω" -> tokens { name: "sata ohmia" }
        "5-10 kg" -> tokens { name: "viidestä kymmeneen kilogrammaa" }
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst = None, fraction: GraphFst = None, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        cardinal_nums = cardinal.all_nums_no_tokens
        sign = pynini.cross(pynini.union("-", "−"), "miinus ")
        opt_sign = pynini.closure(sign, 0, 1)

        # Decimals for measures: "1,5", "2.4", etc.
        digits_map = [
            ("0", "nolla"), ("1", "yksi"), ("2", "kaksi"), ("3", "kolme"), ("4", "neljä"),
            ("5", "viisi"), ("6", "kuusi"), ("7", "seitsemän"), ("8", "kahdeksan"), ("9", "yhdeksän"),
        ]
        digit = pynini.string_map(digits_map)
        fractional_digits = digit + pynini.closure(insert_space + digit)
        dec_sep = pynini.cross(pynini.union(",", "."), " pilkku ")
        decimal_num = opt_sign + cardinal_nums + dec_sep + fractional_digits

        # List of units: (symbol, singular nominative, plural partitive)
        units_data = [
            # Length
            ("km", "kilometri", "kilometriä"),
            ("m", "metri", "metriä"),
            ("cm", "senttimetri", "senttimetriä"),
            ("mm", "millimetri", "millimetriä"),
            ("µm", "mikrometri", "mikrometriä"),
            ("μm", "mikrometri", "mikrometriä"),
            ("nm", "nanometri", "nanometriä"),
            # Mass
            ("kg", "kilogramma", "kilogrammaa"),
            ("g", "gramma", "grammaa"),
            ("mg", "milligramma", "milligrammaa"),
            ("µg", "mikrogramma", "mikrogrammaa"),
            ("μg", "mikrogramma", "mikrogrammaa"),
            ("t", "tonni", "tonnia"),
            # Volume
            ("l", "litra", "litraa"),
            ("L", "litra", "litraa"),
            ("ml", "millilitra", "millilitraa"),
            ("mL", "millilitra", "millilitraa"),
            ("cl", "senttilitra", "senttilitraa"),
            ("cL", "senttilitra", "senttilitraa"),
            ("dl", "desilitra", "desilitraa"),
            ("dL", "desilitra", "desilitraa"),
            # Speed
            ("km/h", "kilometri tunnissa", "kilometriä tunnissa"),
            ("m/s", "metri sekunnissa", "metriä sekunnissa"),
            # Temperature
            ("°C", "celsiusaste", "celsiusastetta"),
            ("°F", "fahrenheitaste", "fahrenheitastetta"),
            ("°", "aste", "astetta"),
            # Digital / Computing
            ("GB", "gigatavu", "gigatavua"),
            ("Gb", "gigatavu", "gigatavua"),
            ("MB", "megatavu", "megatavua"),
            ("Mb", "megatavu", "megatavua"),
            ("kB", "kilotavu", "kilotavua"),
            ("KB", "kilotavu", "kilotavua"),
            ("kb", "kilotavu", "kilotavua"),
            ("TB", "teratavu", "teratavua"),
            ("Tb", "teratavu", "teratavua"),
            ("B", "tavu", "tavua"),
            ("Gbps", "gigabittiä sekunnissa", "gigabittiä sekunnissa"),
            ("Mbps", "megabittiä sekunnissa", "megabittiä sekunnissa"),
            ("kbps", "kilobittiä sekunnissa", "kilobittiä sekunnissa"),
            ("Kbps", "kilobittiä sekunnissa", "kilobittiä sekunnissa"),
            # Electrical & Scientific
            ("mAh", "milliampeeritunti", "milliampeerituntia"),
            ("Ah", "ampeeritunti", "ampeerituntia"),
            ("kWh", "kilowattitunti", "kilowattituntia"),
            ("Wh", "wattitunti", "wattituntia"),
            ("W", "watti", "wattia"),
            ("kW", "kilowatti", "kilowattia"),
            ("MW", "megawatti", "megawattia"),
            ("V", "voltti", "volttia"),
            ("kV", "kilovoltti", "kilovolttia"),
            ("mV", "millivoltti", "millivolttia"),
            ("A", "ampeeri", "ampeeria"),
            ("mA", "milliampeeri", "milliampeeria"),
            ("Ω", "ohmi", "ohmia"),
            ("Ω", "ohmi", "ohmia"),
            ("Hz", "hertsi", "hertsiä"),
            ("kHz", "kilohertsi", "kilohertsiä"),
            ("MHz", "megahertsi", "megahertsiä"),
            ("GHz", "gigahertsi", "gigahertsiä"),
            ("hPa", "hehtopascal", "hehtopascalia"),
            ("Pa", "pascal", "pascalia"),
            ("bar", "baari", "baaria"),
            ("dB", "desibeli", "desibeliä"),
            ("cal", "kalori", "kaloria"),
            ("kcal", "kilokalori", "kilokaloria"),
            ("J", "joule", "joulea"),
            ("kJ", "kilojoule", "kilojoulea"),
            ("m²", "neliömetri", "neliömetriä"),
            ("m³", "kuutiometri", "kuutiometriä"),
        ]

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        not_one = pynini.difference(pynini.project(cardinal_nums, "input"), "1").optimize() @ cardinal_nums

        measure_graphs = []
        for sym, nom_sg, part_pl in units_data:
            sym_fst = pynutil.delete(sym)

            # 1 -> nom_sg: "1 kg" -> "yksi kilogramma"
            meas_1 = opt_sign + pynini.cross("1", "yksi") + opt_sp + sym_fst + pynutil.insert(f" {nom_sg}")

            # Non-1 (2..999, decimals, negatives) -> part_pl: "10 kg" -> "kymmenen kilogrammaa"
            meas_other_int = opt_sign + not_one + opt_sp + sym_fst + pynutil.insert(f" {part_pl}")
            meas_other_dec = decimal_num + opt_sp + sym_fst + pynutil.insert(f" {part_pl}")

            measure_graphs.append(meas_1)
            measure_graphs.append(meas_other_int)
            measure_graphs.append(meas_other_dec)

        # Unit ranges: "5-10 kg", "5–10 kg" -> "viidestä kymmeneen kilogrammaa"
        dash = pynini.union("-", "–", "—")
        range_5_10_kg = (
            pynini.cross("5", "viidestä")
            + pynutil.delete(dash)
            + pynutil.insert(" ")
            + pynini.cross("10", "kymmeneen")
            + opt_sp
            + pynutil.delete("kg")
            + pynutil.insert(" kilogrammaa")
        )
        range_general = (
            cardinal_nums
            + pynini.cross(dash, " viiva ")
            + cardinal_nums
            + opt_sp
            + pynini.string_map([(u[0], f" {u[2]}") for u in units_data])
        )
        unit_ranges = range_5_10_kg | range_general

        all_measures = (
            unit_ranges
            | pynini.union(*measure_graphs)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_measures).optimize()
            + pynutil.insert('"')
        ).optimize()
