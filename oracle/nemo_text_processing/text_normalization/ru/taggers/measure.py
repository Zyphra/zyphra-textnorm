# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst
from nemo_text_processing.text_normalization.ru.alphabet import RU_ALPHA
from nemo_text_processing.text_normalization.ru.taggers.ordinal import SUFFIXES
from nemo_text_processing.text_normalization.ru.taggers.units import (
    MARK,
    UNIT_SPACE,
    agreement,
    attach,
    form_map,
    load_units,
    per_unit,
    quantity_nouns,
)

_MINUS_OR_PM = pynini.closure(
    pynini.cross("-", "минус ")
    | (pynini.cross("±", "плюс-минус ") + pynini.closure(pynutil.delete(" "), 0, 1))
    | (pynini.cross("~", "приблизительно ") + pynini.closure(pynutil.delete(" "), 0, 1)),
    0,
    1,
)

_GENITIVE_PREPS = pynini.union(
    "около",
    "Около",
    "более",
    "Более",
    "менее",
    "Менее",
    "больше",
    "Больше",
    "меньше",
    "Меньше",
    "свыше",
    "Свыше",
    "порядка",
    "Порядка",
    "до",
    "До",
    "от",
    "От",
).optimize()


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure, e.g.
        "2 кг" -> measure { cardinal { integer: "два килограмма" } }
        "1 т" -> "одна тонна", "3,2 л" -> "три целых две десятых литра", "3 км/ч" -> "три километра в час",
        "~10 km" -> "около десяти километров", "±10%" -> "плюс-минус десять процентов"
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        units = load_units()
        rate = per_unit(units)
        optional_rate = pynini.closure(rate, 0, 1)
        quantities = quantity_nouns()
        unit_agreement = agreement(units, UNIT_SPACE, optional_rate)

        # Prevent 4-digit decades "1990s" / "2020s" and 2-digit "'90s" / "90s" from matching glued "s" (seconds)!
        decade_4d = pynini.union("18", "19", "20") + NEMO_DIGIT + "0"
        not_decade_marked = pynini.compose(
            pynini.difference(pynini.project(cardinal.marked, "input"), decade_4d), cardinal.marked
        ).optimize()
        units_no_s = [u for u in units if u.written != "s"]
        units_only_s = [u for u in units if u.written == "s"]
        spaced_only = (pynutil.delete(pynini.union(" ", "\u00a0")) + pynutil.insert(" ")).optimize()

        # "5 кг", "5 км/ч"; for unit "s", allow spaced for any number, or glued only for non-decade numbers
        integer = cardinal.counted(units_no_s, UNIT_SPACE, optional_rate)
        if units_only_s:
            integer |= cardinal.counted(units_only_s, spaced_only, optional_rate)
            integer |= cardinal.counted(units_only_s, pynutil.insert(" "), optional_rate, number=not_decade_marked)
        # "5 млн км" / "5млн км" -> "пять миллионов километров"
        integer |= cardinal.counted(quantities, UNIT_SPACE, UNIT_SPACE + form_map(units, "many", optional_rate))

        decimal_number = decimal.integer_part + pynini.cross(",", " ") + decimal.graph_fractional
        point_number = (
            pynini.compose(pynini.closure(pynini.union(*"0123456789"), 1, 3), decimal.integer_part)
            + pynini.cross(".", " ")
            + decimal.graph_fractional
        )
        self.decimal_number = decimal_number
        self.point_number = point_number
        # "3,2 л" -> "... литра"; "3,2 млн л" -> "... миллиона литров"
        gen_mark = pynutil.insert(MARK["gen"])
        fractional = attach((decimal_number | point_number) + gen_mark, unit_agreement)
        fractional |= (
            decimal_number
            + UNIT_SPACE
            + form_map(quantities, "gen")
            + UNIT_SPACE
            + form_map(units, "many", optional_rate)
        )

        # "~10 km" -> "около десяти километров", "около 10 км" -> "около десяти километров"
        approx_prefix = (pynini.cross("~", "около ") + pynini.closure(pynutil.delete(" "), 0, 1)) | (
            _GENITIVE_PREPS + pynini.accep(" ")
        )
        approx_integer_unit = approx_prefix + attach(
            cardinal.genitive_marked, agreement(units, UNIT_SPACE, optional_rate, tail_only=True)
        )

        # "10-15%" / "5–10 кг" -> "от десяти до пятнадцати процентов" / "от пяти до десяти килограмм"
        range_unit = (
            pynutil.insert("от ")
            + cardinal.range_genitive
            + pynini.cross(pynini.union("-", "–"), " до ")
            + attach(cardinal.range_genitive_marked, agreement(units, UNIT_SPACE, optional_rate, tail_only=True))
        )
        # "1/кг" -> "один на килограмм"
        per = cardinal.numbers['masc'] + rate
        self.measure = (
            (_MINUS_OR_PM + (integer | fractional | per))
            | pynutil.add_weight(approx_integer_unit, -0.05)
            | range_unit
        ).optimize()

        alpha = pynini.closure(RU_ALPHA, 1)
        # "9мешок", "4,2-килограммовый" -> number and the word as written; "6-й", "4-х" are ordinals / genitives
        not_suffix = pynini.difference(
            alpha, pynini.union(*SUFFIXES, "х", "ая", "ья", *(q.written for q in quantities))
        ).optimize()
        number_dash_alpha = (
            (cardinal.cardinal_numbers_default | decimal_number)
            + pynini.closure(pynutil.delete("-"), 0, 1)
            + pynutil.insert(" ")
            + not_suffix
        )
        # "тест-8", "тест-1,02"
        alpha_dash_number = alpha + pynini.cross(pynini.closure("-", 0, 1), " ") + (
            cardinal.cardinal_numbers_nominative | decimal_number
        )

        graph = self.measure | pynutil.add_weight(number_dash_alpha | alpha_dash_number, 0.1)
        self.fst = self.add_tokens(
            pynutil.insert("cardinal { integer: \"") + graph.optimize() + pynutil.insert("\" }")
        ).optimize()
