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
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    NEMO_SIGMA,
)


def _build_ordinal_tables(gender="m"):
    """
    Builds Bulgarian ordinal tables for masculine ('m'), feminine ('f'), or neuter ('n').
    """
    if gender == "m":
        u_ord = [
            ("1", "първи"), ("2", "втори"), ("3", "трети"), ("4", "четвърти"), ("5", "пети"),
            ("6", "шести"), ("7", "седми"), ("8", "осми"), ("9", "девети")
        ]
        teens_ord = [
            ("10", "десети"), ("11", "единадесети"), ("12", "дванадесети"), ("13", "тринадесети"),
            ("14", "четиринадесети"), ("15", "петнадесети"), ("16", "шестнадесети"),
            ("17", "седемнадесети"), ("18", "осемнадесети"), ("19", "деветнадесети")
        ]
        tens_ord = [
            ("20", "двадесети"), ("30", "тридесети"), ("40", "четиридесети"), ("50", "петдесети"),
            ("60", "шестдесети"), ("70", "седемдесети"), ("80", "осемдесети"), ("90", "деветдесети")
        ]
        hundreds_ord = [
            ("100", "стотен"), ("200", "двестотен"), ("300", "тристотен"), ("400", "четиристотен"),
            ("500", "петстотен"), ("600", "шестстотен"), ("700", "седемстотен"),
            ("800", "осемстотен"), ("900", "деветстотен")
        ]
        thousand_ord = "хиляден"
    elif gender == "f":
        u_ord = [
            ("1", "първа"), ("2", "втора"), ("3", "трета"), ("4", "четвърта"), ("5", "пета"),
            ("6", "шеста"), ("7", "седма"), ("8", "осма"), ("9", "девета")
        ]
        teens_ord = [
            ("10", "десета"), ("11", "единадесета"), ("12", "дванадесета"), ("13", "тринадесета"),
            ("14", "четиринадесета"), ("15", "петнадесета"), ("16", "шестнадесета"),
            ("17", "седемнадесета"), ("18", "осемнадесета"), ("19", "деветнадесета")
        ]
        tens_ord = [
            ("20", "двадесета"), ("30", "тридесета"), ("40", "четиридесета"), ("50", "петдесета"),
            ("60", "шестдесета"), ("70", "седемдесета"), ("80", "осемдесета"), ("90", "деветдесета")
        ]
        hundreds_ord = [
            ("100", "стотна"), ("200", "двестотна"), ("300", "тристотна"), ("400", "четиристотна"),
            ("500", "петстотна"), ("600", "шестстотна"), ("700", "седемстотна"),
            ("800", "осемстотна"), ("900", "деветстотна")
        ]
        thousand_ord = "хилядна"
    else:  # neuter
        u_ord = [
            ("1", "първо"), ("2", "второ"), ("3", "трето"), ("4", "четвърто"), ("5", "пето"),
            ("6", "шесто"), ("7", "седмо"), ("8", "осмо"), ("9", "девето")
        ]
        teens_ord = [
            ("10", "десето"), ("11", "единадесето"), ("12", "дванадесето"), ("13", "тринадесето"),
            ("14", "четиринадесето"), ("15", "петнадесето"), ("16", "шестнадесето"),
            ("17", "седемнадесето"), ("18", "осемнадесето"), ("19", "деветнадесето")
        ]
        tens_ord = [
            ("20", "двадесето"), ("30", "тридесето"), ("40", "четиридесето"), ("50", "петдесето"),
            ("60", "шестдесето"), ("70", "седемдесето"), ("80", "осемдесето"), ("90", "деветдесето")
        ]
        hundreds_ord = [
            ("100", "стотно"), ("200", "двестотно"), ("300", "тристотно"), ("400", "четиристотно"),
            ("500", "петстотно"), ("600", "шестстотно"), ("700", "седемстотно"),
            ("800", "осемстотно"), ("900", "деветстотно")
        ]
        thousand_ord = "хилядно"

    return u_ord, teens_ord, tens_ord, hundreds_ord, thousand_ord


def _build_ordinal_graph(gender="m", cardinal_fst=None):
    """
    Builds an ordinal transducer that converts numeric digits to Bulgarian ordinal words.
    In Bulgarian, only the LAST component of a compound number inflects as an ordinal!
    e.g. 21 -> двадесет и първи
         125 -> сто двадесет и пети
    """
    u_ord, teens_ord, tens_ord, hundreds_ord, thousand_ord = _build_ordinal_tables(gender)

    ord_units = pynini.string_map(u_ord)
    ord_teens = pynini.string_map(teens_ord)
    ord_tens = pynini.string_map(tens_ord)
    ord_hundreds = pynini.string_map(hundreds_ord)

    tens_prefix = pynini.string_map([
        ("2", "двадесет"), ("3", "тридесет"), ("4", "четиридесет"), ("5", "петдесет"),
        ("6", "шестдесет"), ("7", "седемдесет"), ("8", "осемдесет"), ("9", "деветдесет")
    ])
    compound_tens = tens_prefix + pynutil.insert(" и ") + ord_units

    hundreds_prefix = pynini.string_map([
        ("1", "сто"), ("2", "двеста"), ("3", "триста"), ("4", "четиристотин"),
        ("5", "петстотин"), ("6", "шестстотин"), ("7", "седемстотин"),
        ("8", "осемстотин"), ("9", "деветстотин")
    ])

    h_and_u = hundreds_prefix + pynutil.delete("0") + pynutil.insert(" и ") + ord_units
    h_and_t = hundreds_prefix + pynutil.insert(" и ") + ord_teens
    h_and_te = hundreds_prefix + pynutil.insert(" и ") + ord_tens
    h_comp = hundreds_prefix + pynutil.insert(" ") + compound_tens

    sub1000 = (
        ord_units
        | ord_teens
        | ord_tens
        | compound_tens
        | ord_hundreds
        | h_and_u
        | h_and_t
        | h_and_te
        | h_comp
    ).optimize()

    # Thousands ordinals:
    # 1000 -> хиляден
    # 2000 -> две хиляден
    # 2026 -> две хиляди двадесет и шести
    # 1990 -> хиляда деветстотин и деветдесети
    th_1000 = pynini.cross("1000", thousand_ord)

    # 1001-1999:
    th_1_prefix = pynini.cross("1", "хиляда")
    # Remainder 3 digits:
    rem_and_u = pynutil.delete("00") + pynutil.insert(" и ") + ord_units
    rem_and_t = pynutil.delete("0") + pynutil.insert(" и ") + ord_teens
    rem_and_te = pynutil.delete("0") + pynutil.insert(" и ") + ord_tens
    rem_comp = pynutil.delete("0") + pynutil.insert(" ") + compound_tens
    rem_and_hex = pynutil.insert(" и ") + ord_hundreds
    rem_h_rest = pynutil.insert(" ") + (h_and_u | h_and_t | h_and_te | h_comp)
    rem3_ord = (rem_and_u | rem_and_t | rem_and_te | rem_comp | rem_and_hex | rem_h_rest).optimize()

    th_1_rest = th_1_prefix + rem3_ord

    # 2000-9999:
    units_f_2plus = pynini.string_map([
        ("2", "две"), ("3", "три"), ("4", "четири"), ("5", "пет"),
        ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
    ])
    th_2_prefix = units_f_2plus + pynutil.insert(" хиляди")
    th_2_exact = units_f_2plus + pynutil.delete("000") + pynutil.insert(f" {thousand_ord}")
    th_2_rest = th_2_prefix + rem3_ord

    all_ord = (sub1000 | th_1000 | th_1_rest | th_2_exact | th_2_rest).optimize()
    return all_ord


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian ordinals,
    including suffixed forms, decade terms, and contextual Roman numerals.
    e.g. 1-ви -> tokens { name: "първи" }
         1-ва -> tokens { name: "първа" }
         1-во -> tokens { name: "първо" }
         21-ви -> tokens { name: "двадесет и първи" }
         1990-те -> tokens { name: "деветдесетте години" }
         XXI век -> tokens { name: "двадесет и първи век" }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        ord_m = _build_ordinal_graph("m")
        ord_f = _build_ordinal_graph("f")
        ord_n = _build_ordinal_graph("n")

        # Hyphenated and glued suffixes
        opt_dash = pynini.closure(pynutil.delete("-"), 0, 1)

        # Masculine: -ви, -ри, -ти, -ми, -тен, -ен
        suf_m = opt_dash + pynutil.delete(pynini.union("ви", "ри", "ти", "ми", "тен", "ен"))
        ord_m_suffixed = ord_m + suf_m

        # Feminine: -ва, -ра, -та, -ма, -тна, -на
        suf_f = opt_dash + pynutil.delete(pynini.union("ва", "ра", "та", "ма", "тна", "на"))
        ord_f_suffixed = ord_f + suf_f

        # Neuter: -во, -ро, -то, -мо, -тно, -но
        suf_n = opt_dash + pynutil.delete(pynini.union("во", "ро", "то", "мо", "тно", "но"))
        ord_n_suffixed = ord_n + suf_n

        # Decades: "1990-те", "2020-те", "90-те", "2020s", "1990s"
        dec_90 = pynini.cross(pynini.union("90-те", "1990-те", "1990-те години", "1990s", "1990's"), "деветдесетте години")
        dec_20 = pynini.cross(pynini.union("2020-те", "2020-те години", "2020s", "2020's"), "двадесетте години на двадесет и първи век")
        dec_80 = pynini.cross(pynini.union("80-те", "1980-те", "1980s"), "осемдесетте години")
        dec_70 = pynini.cross(pynini.union("70-те", "1970-те", "1970s"), "седемдесетте години")
        dec_60 = pynini.cross(pynini.union("60-те", "1960-те", "1960s"), "шестдесетте години")
        decades = (dec_90 | dec_20 | dec_80 | dec_70 | dec_60).optimize()

        # Dot ordinals: "1.", "2.", "21." -> masculine ordinal
        dot_ord = ord_m + pynutil.delete(".")

        # Roman numerals with context
        # Roman mapping
        roman_map_m = pynini.string_map([
            ("I", "първи"), ("II", "втори"), ("III", "трети"), ("IV", "четвърти"),
            ("V", "пети"), ("VI", "шести"), ("VII", "седми"), ("VIII", "осми"),
            ("IX", "девети"), ("X", "десети"), ("XI", "единадесети"), ("XII", "дванадесети"),
            ("XIII", "тринадесети"), ("XIV", "четиринадесети"), ("XV", "петнадесети"),
            ("XVI", "шестнадесети"), ("XVII", "седемнадесети"), ("XVIII", "осемнадесети"),
            ("XIX", "деветнадесети"), ("XX", "двадесети"), ("XXI", "двадесет и първи"),
            ("XXII", "двадесет и втори")
        ])

        roman_map_f = pynini.string_map([
            ("I", "първа"), ("II", "втора"), ("III", "трета"), ("IV", "четвърта"),
            ("V", "пета"), ("VI", "шеста"), ("VII", "седма"), ("VIII", "осма"),
            ("IX", "девета"), ("X", "десета"), ("XI", "единадесета"), ("XII", "дванадесета"),
            ("XIII", "тринадесета"), ("XIV", "четиринадесета"), ("XV", "петнадесета"),
            ("XVI", "шестнадесета"), ("XVII", "седемнадесета"), ("XVIII", "осемнадесета"),
            ("XIX", "деветнадесета"), ("XX", "двадесета"), ("XXI", "двадесет и първа"),
            ("XXII", "двадесет и втора")
        ])

        # Contextual triggers:
        # Chapter / Part / Volume / Century / Monarchs:
        # "Глава IV" -> "глава четвърта", "глава IV" -> "глава четвърта"
        chap = (
            pynini.union("Глава", "глава")
            + pynutil.insert(" ")
            + pynutil.delete(" ")
            + roman_map_f
        )
        part = (
            pynini.union("Част", "част")
            + pynutil.insert(" ")
            + pynutil.delete(" ")
            + roman_map_f
        )
        vol = (
            pynini.union("Том", "том")
            + pynutil.insert(" ")
            + pynutil.delete(" ")
            + roman_map_m
        )
        century = (
            roman_map_m
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + pynini.union("век", "в.")
        )
        monarch = (
            pynini.union(
                "Симеон", "Борис", "Петър", "Иван Асен", "Калоян", "Самуил",
                "Александър", "Николай", "Хенри", "Луи", "Елизабет"
            )
            + pynutil.insert(" ")
            + pynutil.delete(" ")
            + roman_map_m
        )

        # Safety controls: preserve non-numeric acronyms
        controls = (
            pynini.cross("XL", "X L")
            | pynini.cross("MIX", "M I X")
            | pynini.cross("CD", "C D")
        )

        roman_context = (chap | part | vol | century | monarch | controls).optimize()

        self.all_ordinals = (
            pynutil.add_weight(decades, 1.0)
            | pynutil.add_weight(roman_context, 1.02)
            | pynutil.add_weight(ord_m_suffixed, 1.05)
            | pynutil.add_weight(ord_f_suffixed, 1.05)
            | pynutil.add_weight(ord_n_suffixed, 1.05)
            | pynutil.add_weight(dot_ord, 1.1)
        ).optimize()

        graph = pynutil.insert('name: "') + convert_space(self.all_ordinals) + pynutil.insert('"')
        self.fst = graph.optimize()
