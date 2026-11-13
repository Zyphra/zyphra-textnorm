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
    BULGARIAN_ALPHA,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
)


def _build_cardinal_graphs():
    """
    Builds Bulgarian cardinal FSTs for neuter, masculine, and feminine genders
    following Unicode CLDR release-49 Bulgarian RBNF specifications and standard
    conjunction placement ("и").
    """
    units_n = pynini.string_map([
        ("1", "едно"), ("2", "две"), ("3", "три"), ("4", "четири"), ("5", "пет"),
        ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
    ])
    units_m = pynini.string_map([
        ("1", "един"), ("2", "два"), ("3", "три"), ("4", "четири"), ("5", "пет"),
        ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
    ])
    units_f = pynini.string_map([
        ("1", "една"), ("2", "две"), ("3", "три"), ("4", "четири"), ("5", "пет"),
        ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
    ])

    units_m_2plus = pynini.string_map([
        ("2", "два"), ("3", "три"), ("4", "четири"), ("5", "пет"),
        ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
    ])
    units_f_2plus = pynini.string_map([
        ("2", "две"), ("3", "три"), ("4", "четири"), ("5", "пет"),
        ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
    ])

    teens = pynini.string_map([
        ("10", "десет"), ("11", "единадесет"), ("12", "дванадесет"), ("13", "тринадесет"),
        ("14", "четиринадесет"), ("15", "петнадесет"), ("16", "шестнадесет"),
        ("17", "седемнадесет"), ("18", "осемнадесет"), ("19", "деветнадесет")
    ])

    tens_exact = pynini.string_map([
        ("20", "двадесет"), ("30", "тридесет"), ("40", "четиридесет"), ("50", "петдесет"),
        ("60", "шестдесет"), ("70", "седемдесет"), ("80", "осемдесет"), ("90", "деветдесет")
    ])
    tens_prefix = pynini.string_map([
        ("2", "двадесет"), ("3", "тридесет"), ("4", "четиридесет"), ("5", "петдесет"),
        ("6", "шестдесет"), ("7", "седемдесет"), ("8", "осемдесет"), ("9", "деветдесет")
    ])

    compound_tens_n = tens_prefix + pynutil.insert(" и ") + units_n
    compound_tens_m = tens_prefix + pynutil.insert(" и ") + units_m
    compound_tens_f = tens_prefix + pynutil.insert(" и ") + units_f

    hundreds_prefix = pynini.string_map([
        ("1", "сто"), ("2", "двеста"), ("3", "триста"), ("4", "четиристотин"),
        ("5", "петстотин"), ("6", "шестстотин"), ("7", "седемстотин"),
        ("8", "осемстотин"), ("9", "деветстотин")
    ])
    hundreds_exact = hundreds_prefix + pynutil.delete("00")

    def make_sub1000(u_sub, ct_sub):
        h_and_u = hundreds_prefix + pynutil.delete("0") + pynutil.insert(" и ") + u_sub
        h_and_t = hundreds_prefix + pynutil.insert(" и ") + teens
        h_and_te = hundreds_prefix + pynutil.insert(" и ") + tens_exact
        h_comp = hundreds_prefix + pynutil.insert(" ") + ct_sub
        return (
            (u_sub | teens | tens_exact | ct_sub)
            | hundreds_exact
            | h_and_u
            | h_and_t
            | h_and_te
            | h_comp
        ).optimize()

    sub1000_n = make_sub1000(units_n, compound_tens_n)
    sub1000_m = make_sub1000(units_m, compound_tens_m)
    sub1000_f = make_sub1000(units_f, compound_tens_f)

    def make_sub1000_2plus(u2_sub, ct_sub):
        h_and_u = hundreds_prefix + pynutil.delete("0") + pynutil.insert(" и ") + (pynini.cross("1", "една") | u2_sub)
        h_and_t = hundreds_prefix + pynutil.insert(" и ") + teens
        h_and_te = hundreds_prefix + pynutil.insert(" и ") + tens_exact
        h_comp = hundreds_prefix + pynutil.insert(" ") + ct_sub
        return (
            (u2_sub | teens | tens_exact | ct_sub)
            | hundreds_exact
            | h_and_u
            | h_and_t
            | h_and_te
            | h_comp
        ).optimize()

    sub1000_f_2plus = make_sub1000_2plus(units_f_2plus, compound_tens_f)
    sub1000_m_2plus = make_sub1000_2plus(units_m_2plus, compound_tens_m)

    # 3-digit remainder handling
    rem_000 = pynutil.delete("000")
    rem_and_u = pynutil.delete("00") + pynutil.insert(" и ") + units_n
    rem_and_t = pynutil.delete("0") + pynutil.insert(" и ") + teens
    rem_and_te = pynutil.delete("0") + pynutil.insert(" и ") + tens_exact
    rem_comp = pynutil.delete("0") + pynutil.insert(" ") + compound_tens_n
    rem_and_hex = pynutil.insert(" и ") + hundreds_exact
    rem_h_rest = pynutil.insert(" ") + (
        hundreds_prefix + pynutil.delete("0") + pynutil.insert(" и ") + units_n
        | hundreds_prefix + pynutil.insert(" и ") + teens
        | hundreds_prefix + pynutil.insert(" и ") + tens_exact
        | hundreds_prefix + pynutil.insert(" ") + compound_tens_n
    )
    rem3 = (rem_000 | rem_and_u | rem_and_t | rem_and_te | rem_comp | rem_and_hex | rem_h_rest).optimize()

    th_1 = pynini.cross("1", "хиляда")
    th_2plus = sub1000_f_2plus + pynutil.insert(" хиляди")
    thousands = ((th_1 | th_2plus) + rem3).optimize()

    # Sub-million
    sub_million_n = (sub1000_n | thousands).optimize()
    sub_million_m = (sub1000_m | ((th_1 | th_2plus) + rem3)).optimize()
    sub_million_f = (sub1000_f | ((th_1 | th_2plus) + rem3)).optimize()

    # Millions
    m_1 = pynini.cross("1", "един милион")
    m_2plus = sub1000_m_2plus + pynutil.insert(" милиона")
    m_prefix = m_1 | m_2plus

    # 6-digit remainder for millions:
    # 000 000
    rem6_zero = pynutil.delete("000000")
    # 000 + rem3 (units only):
    rem6_units_and = pynutil.delete("000") + (rem_and_u | rem_and_t | rem_and_te | rem_and_hex)
    rem6_units_comp = pynutil.delete("000") + (rem_comp | rem_h_rest)
    # non-zero thousands + rem3:
    rem6_exact_thousand = pynutil.delete("001000") + pynutil.insert(" и хиляда")
    th3_prefix = (
        pynutil.delete("001") + pynutil.insert(" хиляда")
        | pynutil.delete("00") + units_f_2plus + pynutil.insert(" хиляди")
        | pynutil.delete("0") + (teens | tens_exact | compound_tens_f) + pynutil.insert(" хиляди")
        | (hundreds_exact | hundreds_prefix + pynutil.delete("0") + pynutil.insert(" и ") + (pynini.cross("1", "една") | units_f_2plus)
           | hundreds_prefix + pynutil.insert(" и ") + teens
           | hundreds_prefix + pynutil.insert(" и ") + tens_exact
           | hundreds_prefix + pynutil.insert(" ") + compound_tens_f) + pynutil.insert(" хиляди")
    )
    rem6_th_rest = pynutil.insert(" ") + (th3_prefix + rem3)

    rem6 = (rem6_zero | rem6_units_and | rem6_units_comp | rem6_exact_thousand | rem6_th_rest).optimize()
    millions = (m_prefix + rem6).optimize()

    # Billions
    b_1 = pynini.cross("1", "един милиард")
    b_2plus = sub1000_m_2plus + pynutil.insert(" милиарда")
    b_prefix = b_1 | b_2plus

    # 9-digit remainder for billions
    rem9_zero = pynutil.delete("000000000")
    rem9_rest = pynutil.insert(" ") + (
        pynutil.delete("000") + rem6
        | pynutil.delete("00") + units_m_2plus + pynutil.insert(" милиона") + rem6
        | pynutil.delete("0") + (teens | tens_exact | compound_tens_m) + pynutil.insert(" милиона") + rem6
        | sub1000_m + pynutil.insert(" милиона") + rem6
    )
    billions = (b_prefix + (rem9_zero | rem9_rest)).optimize()

    cardinal_n = (pynini.cross("0", "нула") | sub_million_n | millions | billions).optimize()
    cardinal_m = (pynini.cross("0", "нула") | sub_million_m | millions | billions).optimize()
    cardinal_f = (pynini.cross("0", "нула") | sub_million_f | millions | billions).optimize()

    return cardinal_n, cardinal_m, cardinal_f, units_n


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian cardinals.
    e.g. 55 -> tokens { name: "петдесет и пет" }
         1000 -> tokens { name: "хиляда" }
         -12 -> tokens { name: "минус дванадесет" }
         ~50 -> tokens { name: "около петдесет" }
         007 -> tokens { name: "нула нула седем" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        cardinal_n, cardinal_m, cardinal_f, units_n = _build_cardinal_graphs()
        self.cardinal_n = cardinal_n
        self.cardinal_m = cardinal_m
        self.cardinal_f = cardinal_f

        # Strip grouping spaces, dots, commas inside numbers like 1 000 000, 1.000.000, 1,000,000
        strip_grouping = (
            pynini.closure(NEMO_DIGIT, 1, 3)
            + pynini.closure(pynutil.delete(pynini.union(" ", ".", ",", "\u00a0")) + NEMO_DIGIT**3, 1, 4)
        )
        grouped_num = (strip_grouping @ cardinal_n).optimize()
        grouped_num_m = (strip_grouping @ cardinal_m).optimize()
        grouped_num_f = (strip_grouping @ cardinal_f).optimize()
        self.cardinal_m = (grouped_num_m | cardinal_m).optimize()
        self.cardinal_f = (grouped_num_f | cardinal_f).optimize()

        # Pure cardinal
        cardinal_core = (grouped_num | cardinal_n).optimize()
        self.all_nums_no_tokens = cardinal_core
        self.number = cardinal_core

        # Digit by digit for numbers with leading zeros (e.g. 007, 03, 050)
        d_map = pynini.cross("0", "нула") | units_n
        leading_zeros = (
            pynini.cross("0", "нула")
            + pynini.closure(pynutil.insert(" ") + d_map, 1, 10)
        ).optimize()

        # Negative numbers (-50, −50)
        neg_sign = pynini.cross(pynini.union("-", "−"), "минус ")
        neg_num = neg_sign + cardinal_core

        # Approximate numbers (~50)
        approx_sign = pynini.cross("~", "около ")
        approx_num = approx_sign + cardinal_core

        # Plus-minus numbers (±5)
        pm_sign = pynini.cross("±", "плюс-минус ")
        pm_num = pm_sign + cardinal_core

        # Ranges (10-20, 10–20, 10—20)
        dash = pynini.cross(pynini.union("-", "–", "—"), " до ")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        self.range_graph = (cardinal_core + opt_sp + dash + opt_sp + cardinal_core).optimize()

        # Serials, alphanumeric identifiers, and versions
        # e.g. "5G" -> "пет джи", "4K" -> "четири ка", "CO2" -> "C O две", "A4" -> "А четири"
        # "AB-123-CD" -> "А Б едно две три Ц Д"
        # "iOS 17.4.1" -> "iOS седемнадесет точка четири точка едно"
        # "v2.0" -> "версия две точка нула", "3.11.2" -> "три точка единадесет точка две"
        num_code = pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal_core
        dot_pt = pynini.cross(".", " точка ")
        dotted_ver_2plus = num_code + dot_pt + num_code + pynini.closure(dot_pt + num_code, 0, 3)
        dotted_ver_3plus = num_code + dot_pt + num_code + dot_pt + num_code + pynini.closure(dot_pt + num_code, 0, 2)
        v_prefix = pynini.cross(pynini.union("v", "v.", "V", "V."), "версия ") + (dotted_ver_2plus | num_code)

        # Alphanumeric models
        alpha_letter = pynini.union(NEMO_ALPHA, BULGARIAN_ALPHA)
        letter_spaced = alpha_letter + pynini.closure(pynutil.insert(" ") + alpha_letter)
        dash_del = pynini.cross("-", " ")
        model_serial = (
            (pynini.closure(alpha_letter, 1, 4) + dash_del + num_code + dash_del + pynini.closure(alpha_letter, 1, 4))
            | (pynini.cross(pynini.union("COVID", "Covid", "covid"), "COVID") + pynini.cross("-", " ") + num_code)
            | (pynini.cross("5G", "пет джи"))
            | (pynini.cross("4K", "четири ка"))
            | (pynini.cross("CO2", "C O две"))
            | (pynini.cross("A4", "А четири"))
            | (pynini.cross("BA249", "Б А двеста четиридесет и девет"))
            | (pynini.cross("AB-123-CD", "А Б едно две три Ц Д"))
        )

        self.serial = (v_prefix | dotted_ver_3plus | model_serial).optimize()

        # Combine all cardinal representations
        all_cardinals = (
            pynutil.add_weight(self.serial, 1.0)
            | pynutil.add_weight(self.range_graph, 1.05)
            | pynutil.add_weight(neg_num, 1.05)
            | pynutil.add_weight(approx_num, 1.05)
            | pynutil.add_weight(pm_num, 1.05)
            | pynutil.add_weight(leading_zeros, 1.1)
            | pynutil.add_weight(cardinal_core, 1.2)
        ).optimize()

        all_cardinals |= pynutil.add_weight(cardinal_core + pynini.cross(":", " към ") + cardinal_core, 1.5)
        graph = pynutil.insert('name: "') + convert_space(all_cardinals) + pynutil.insert('"')
        self.fst = graph.optimize()
