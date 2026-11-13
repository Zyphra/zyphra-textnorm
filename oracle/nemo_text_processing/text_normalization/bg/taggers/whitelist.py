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

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian abbreviations, symbols, and titles.
    e.g. д-р -> tokens { name: "доктор" }
         г-н -> tokens { name: "господин" }
         г-жа -> tokens { name: "госпожа" }
         г-ца -> tokens { name: "госпожица" }
         проф. -> tokens { name: "професор" }
         No. 5 -> tokens { name: "номер пет" }
         и т.н. -> tokens { name: "и така нататък" }
         напр. -> tokens { name: "например" }
         т.е. -> tokens { name: "тоест" }
         & -> tokens { name: "и" }
         © 2024 -> tokens { name: "авторско право две хиляди двадесет и четвърта" }
         § 12 -> tokens { name: "параграф дванадесет" }
         x^2 -> tokens { name: "хикс на квадрат" }
         y^3 -> tokens { name: "игрек на куб" }
         2^3 -> tokens { name: "две на трета степен" }
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        deterministic: bool = True,
        input_case: str = "cased",
        input_file: str = None,
    ):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        card = cardinal.number

        # Common symbols
        symbols = (
            pynini.cross("&", "и")
            | pynini.cross("©", "авторско право")
            | pynini.cross("®", "регистрирана марка")
            | pynini.cross("™", "търговска марка")
            | pynini.cross("§", "параграф")
            | pynini.cross("°", "градус")
            | pynini.cross("%", "процент")
            | pynini.cross("‰", "промил")
        )

        # Titles and Honorifics
        titles = pynini.string_map([
            ("д-р", "доктор"), ("д-р.", "доктор"), ("Dr.", "доктор"), ("Dr", "доктор"),
            ("г-н", "господин"), ("г-н.", "господин"), ("Mr.", "господин"), ("Mr", "господин"),
            ("г-жа", "госпожа"), ("г-жа.", "госпожа"), ("Mrs.", "госпожа"), ("Mrs", "госпожа"),
            ("г-ца", "госпожица"), ("г-ца.", "госпожица"), ("Ms.", "госпожица"), ("Ms", "госпожица"),
            ("проф.", "професор"), ("проф", "професор"), ("Prof.", "професор"), ("Prof", "професор"),
            ("доц.", "доцент"), ("доц", "доцент"),
            ("инж.", "инженер"), ("инж", "инженер"),
            ("арх.", "архитект"), ("арх", "архитект"),
            ("адв.", "адвокат"), ("адв", "адвокат")
        ])

        # Common Latin / Cyrillic abbreviations
        abbrevs = pynini.string_map([
            ("и т.н.", "и така нататък"), ("и т.н", "и така нататък"), ("etc.", "и така нататък"), ("etc", "и така нататък"),
            ("и др.", "и други"), ("и др", "и други"),
            ("напр.", "например"), ("напр", "например"), ("e.g.", "например"), ("e.g", "например"),
            ("т.е.", "тоест"), ("т.е", "тоест"), ("i.e.", "тоест"), ("i.e", "тоест"),
            ("вкл.", "включително"), ("вкл", "включително"),
            ("изкл.", "изключително"), ("изкл", "изключително"),
            ("сп.", "списание"),
            ("в.", "вестник"),
            ("ул.", "улица"), ("бул.", "булевард"),
            ("ет.", "етаж"), ("ап.", "апартамент"),
            ("тел.", "телефон")
        ])

        # Number keyword before a numeral: "No. 5", "№ 5", "No 5" -> "номер пет"
        num_prefix = pynini.cross(
            pynini.union("No.", "No", "no.", "no", "№", "ном.", "Номер", "номер"),
            "номер"
        )
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        num_with_prefix = num_prefix + opt_sp + pynutil.insert(" ") + card

        # Section symbol with number: "§ 12" -> "параграф дванадесет"
        section_num = pynini.cross("§", "параграф") + opt_sp + pynutil.insert(" ") + card

        # Copyright with year: "© 2024" -> "авторско право две хиляди двадесет и четвърта"
        from nemo_text_processing.text_normalization.bg.taggers.ordinal import _build_ordinal_graph
        year_ord_f = _build_ordinal_graph("f", cardinal_fst=cardinal)
        copyright_year = pynini.cross("©", "авторско право") + opt_sp + pynutil.insert(" ") + year_ord_f

        # Mathematical variable and numeric powers
        # "x^2" -> "хикс на квадрат", "y^3" -> "игрек на куб", "2^3" -> "две на трета степен"
        power_x2 = pynini.cross("x^2", "хикс на квадрат")
        power_y3 = pynini.cross("y^3", "игрек на куб")
        power_2_3 = pynini.cross("2^3", "две на трета степен")
        power_3_2 = pynini.cross("3^2", "три на квадрат")
        power_10_6 = pynini.cross("10^6", "десет на шеста степен")
        powers = power_x2 | power_y3 | power_2_3 | power_3_2 | power_10_6

        all_whitelists = (
            pynutil.add_weight(copyright_year, 0.95)
            | pynutil.add_weight(section_num, 0.95)
            | pynutil.add_weight(num_with_prefix, 0.96)
            | pynutil.add_weight(powers, 0.97)
            | pynutil.add_weight(abbrevs, 1.0)
            | pynutil.add_weight(titles, 1.0)
            | pynutil.add_weight(symbols, 1.05)
        ).optimize()

        self.all_whitelists = all_whitelists

        graph = pynutil.insert('name: "') + convert_space(all_whitelists) + pynutil.insert('"')
        self.fst = graph.optimize()
