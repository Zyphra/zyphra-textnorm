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
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.pl.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.pl.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.pl.utils import get_abs_path, load_labels


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Polish measurements and units, e.g.
        "50 kg" -> "pięćdziesiąt kilogramów"
        "50kg" -> "pięćdziesiąt kilogramów"
        "100m" -> "sto metrów"
        "1,5km" -> "jeden przecinek pięć kilometra"
        "37°C" -> "trzydzieści siedem stopni Celsjusza"
        "-15°C" -> "minus piętnaście stopni Celsjusza"
        "120km/h" -> "sto dwadzieścia kilometrów na godzinę"
        "10 Gbps" -> "dziesięć gigabitów na sekundę"
        "5000 mAh" -> "pięć tysięcy miliamperogodzin"
        "50 kWh" -> "pięćdziesiąt kilowatogodzin"
        "1013 hPa" -> "tysiąc trzynaście hektopaskali"
        "60 dB" -> "sześćdziesiąt decybeli"
        "100 Ω" -> "sto omów"
        "50 µg" -> "pięćdziesiąt mikrogramów"
        "10 µm" -> "dziesięć mikrometrów"
        "100 m²" -> "sto metrów kwadratowych"
        "5 m³" -> "pięć metrów sześciennych"
        "~10 km" -> "około dziesięć kilometrów"
        "5-10 kg" -> "pięć do dziesięciu kilogramów"
    """

    def __init__(
        self,
        cardinal: CardinalFst,
        decimal: DecimalFst,
        fraction: FractionFst,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        pn = cardinal.pn
        card_m = cardinal.graph_with_sep
        card_f = cardinal.graph_fem_with_sep
        card_gen = cardinal.graph_genitive_with_sep
        units_data = load_labels(get_abs_path("data/measure/measurements.tsv"))

        not_one = pynini.difference(NEMO_DIGIT, "1")
        ending_one = pynini.accep("1")
        ending_few_digit = pynini.union("2", "3", "4")
        any_num_char = NEMO_DIGIT | pynini.union(" ", "\u00a0", ".")
        num_prefix = pynini.closure(any_num_char)
        ending_few = (num_prefix + not_one + ending_few_digit) | ending_few_digit
        ending_many = pynini.difference(pynini.project(card_m, "input"), ending_one | ending_few).optimize()

        prefix_sign = (
            pynini.cross(pynini.union("-", "−"), "minus ")
            | (pynini.cross("~", "około ") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "plus minus ") + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        opt_prefix = pynini.closure(prefix_sign, 0, 1)

        feminine_units = {"s", "sek.", "sek", "min", "min.", "h", "godz.", "godz", "t", "mi", "oz", "ha", "kcal", "cal", "atm", "mAh", "Ah", "kWh", "Wh", "MWh"}

        dash = pynini.union("-", "–", "—")
        range_to = pynini.cross(dash, " do ")

        all_unit_graphs = []
        positive_unit_graphs = []
        range_unit_graphs = []

        for row in units_data:
            if not row or len(row) < 4:
                continue
            sym, u_one, u_few, u_many = row[:4]

            is_fem = sym in feminine_units
            c_graph = card_f if is_fem else card_m

            # Kelvin 'K' requires a preceding space so '4K' resolution is handled by serial
            opt_sp = pynutil.delete(" ") if sym == "K" else pynini.closure(pynutil.delete(" "), 0, 1)
            del_sym = pynutil.delete(sym)

            # Whole numbers
            q_one = (ending_one @ c_graph) + opt_sp + del_sym + pynutil.insert(" " + u_one)
            q_few = (ending_few @ c_graph) + opt_sp + del_sym + pynutil.insert(" " + u_few)
            q_many = (ending_many @ c_graph) + opt_sp + del_sym + pynutil.insert(" " + u_many)
            int_q = q_one | q_few | q_many

            # Decimal numbers (e.g. 1,5 km -> jeden przecinek pięć kilometrów)
            dec_q = decimal.graph + opt_sp + del_sym + pynutil.insert(" " + u_many)

            # Fractions (e.g. 1/2 kg -> pół kilograma, 2 1/2 kg -> dwa i pół kilograma)
            half_q = (
                fraction.graph
                + opt_sp
                + del_sym
                + pynutil.insert(" " + u_many)
            )

            unit_pos = int_q | dec_q | half_q
            positive_unit_graphs.append(unit_pos)
            all_unit_graphs.append(opt_prefix + unit_pos)

            # Unit range: "5-10 kg" -> "pięć do dziesięciu kilogramów"
            r_sp = pynini.closure(pynutil.delete(" "), 0, 1)
            range_unit = card_m + range_to + card_gen + r_sp + del_sym + pynutil.insert(" " + u_many)
            range_unit_od = pynutil.insert("od ") + card_m + range_to + card_gen + r_sp + del_sym + pynutil.insert(" " + u_many)
            range_unit_graphs.append(range_unit | range_unit_od)

        combined_units = pynini.union(*all_unit_graphs)
        self.positive_fst = pynini.union(*positive_unit_graphs).optimize()
        unit_ranges = pynini.union(*range_unit_graphs)

        self.graph = (unit_ranges | combined_units).optimize()
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
