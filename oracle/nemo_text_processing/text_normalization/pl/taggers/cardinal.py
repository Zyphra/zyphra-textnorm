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
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.pl.taggers.number_names import PolishNumbers


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Polish cardinals (CLDR pl %spellout-cardinal-*), e.g.
        "100" -> "sto"
        "-12" -> "minus dwanaście"
        "~50" -> "około pięćdziesiąt"
        "±5" -> "plus minus pięć"
        "1 000 000" -> "milion"
        "007" -> "zero zero siedem"
        "3:1" -> "trzy do jednego"
        "x^2" -> "x do kwadratu"
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        pn = PolishNumbers()
        self.pn = pn

        self.digit = (pn.zero | pn.digit_m).optimize()
        self.digit_fem = (pn.zero | pn.digit_f).optimize()
        self.digit_neut = (pn.zero | pn.digit_n).optimize()

        # Cardinals for integers 0..999,999,999,999
        self.graph = pn.cardinal_fst(gender="masc")
        self.graph_fem = pn.cardinal_fst(gender="fem")
        self.graph_neut = pn.cardinal_fst(gender="neut")
        self.graph_genitive = pn.cardinal_fst(case="gen")

        # Grouping separators: spaces "1 000", non-breaking spaces "1\u00a0000", dots "1.000.000"
        grouped_space = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(pynini.union(" ", "\u00a0")) + NEMO_DIGIT**3, 1, 3)
        )
        grouped_dot = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(".") + NEMO_DIGIT**3, 1, 3)
        )
        self.graph_with_sep = (self.graph | grouped_space @ self.graph | grouped_dot @ self.graph).optimize()
        self.graph_fem_with_sep = (
            self.graph_fem
            | grouped_space @ self.graph_fem
            | grouped_dot @ self.graph_fem
        ).optimize()
        self.graph_genitive_with_sep = (
            self.graph_genitive
            | grouped_space @ self.graph_genitive
            | grouped_dot @ self.graph_genitive
        ).optimize()

        # Ranges: 10-20, 10–20 (second number in genitive: "dziesięć do dwudziestu")
        dash = pynini.union("-", "–", "—")
        range_to = pynini.cross(dash, " do ")
        number_range = self.graph_with_sep + range_to + self.graph_genitive_with_sep

        # Sports scores / ratios: 3:1 -> trzy do jednego
        ratio_to = pynini.cross(":", " do ")
        score = self.graph_with_sep + ratio_to + (
            pynini.cross("1", "jednego")
            | (pynini.difference(pynini.project(self.graph_genitive_with_sep, "input"), "1").optimize() @ self.graph_genitive_with_sep)
        )
        number_range |= pynutil.add_weight(score, 0.05)

        # Leading zeros & long digit strings
        digits = self.digit + pynini.closure(insert_space + self.digit)
        leading_zero = pynini.compose(pynini.accep("0") + pynini.closure(NEMO_DIGIT, 1), digits)
        too_long = pynini.compose(pynini.closure(NEMO_DIGIT, 13), digits)
        digit_by_digit = (leading_zero | too_long).optimize()

        # Math expressions: 5+3 -> pięć plus trzy, 5 = 5 -> pięć równa się pięć
        math_plus = self.graph_with_sep + pynini.cross("+", " plus ") + self.graph_with_sep
        math_eq = (
            self.graph_with_sep
            + pynini.cross(pynini.union("=", " = "), " równa się ")
            + self.graph_with_sep
        )
        # Power words produced by textnorm pre-pass: "2 do potęgi 3" -> "dwa do potęgi trzeciej"
        power_do = (
            self.graph_with_sep
            + pynini.cross(" do potęgi ", " do potęgi ")
            + pn.ordinal_fst(gender="fem", case="gen")
        )
        math_expr = (math_plus | math_eq | power_do).optimize()

        # Powers: x^2 -> x do kwadratu, y^3 -> y do sześcianu, 2^3 -> dwa do potęgi trzeciej
        square = pynini.cross("^2", " do kwadratu")
        cube = pynini.cross("^3", " do sześcianu")
        power_other = pynini.cross("^", " do potęgi ") + pn.ordinal_fst(gender="fem", case="gen")
        power_sym = square | cube | power_other

        power_var = NEMO_ALPHA + power_sym
        power_num = self.graph_with_sep + power_sym
        power_graph = (power_var | power_num).optimize()

        # Prefixes: minus, approx (~), plus-minus (±)
        prefix_sign = (
            pynini.cross(pynini.union("-", "−"), "minus ")
            | (pynini.cross("~", "około ") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "plus minus ") + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        optional_prefix = pynini.closure(prefix_sign, 0, 1)

        final_graph = (
            optional_prefix + (self.graph_with_sep | power_graph)
            | number_range
            | math_expr
            | digit_by_digit
        ).optimize()

        self.fst = (pynutil.insert("name: \"") + convert_space(final_graph) + pynutil.insert("\"")).optimize()

        # Alphanumerics & serial fallback (5G, 4K, CO2, v2.0, iOS 17.4.1, 192.168.1.1, AB-123-CD)
        alphanum_fixed = pynini.string_map([
            ("COVID-19", "COVID dziewiętnaście"),
            ("covid-19", "covid dziewiętnaście"),
            ("5G", "pięć G"),
            ("5g", "pięć g"),
            ("4K", "cztery K"),
            ("4k", "cztery k"),
            ("CO2", "C O dwa"),
            ("BA249", "BA dwa cztery dziewięć"),
        ])

        alpha_piece = pynini.closure(NEMO_ALPHA, 1)
        num_piece = (self.graph | digit_by_digit).optimize()
        dot_num = num_piece + pynini.closure(pynini.cross(".", " kropka ") + num_piece)
        alnum_seg = (
            alpha_piece
            | dot_num
            | alpha_piece + pynutil.insert(" ") + dot_num
            | dot_num + pynutil.insert(" ") + alpha_piece
            | alpha_piece + pynutil.insert(" ") + dot_num + pynutil.insert(" ") + alpha_piece
            | dot_num + pynutil.insert(" ") + alpha_piece + pynutil.insert(" ") + dot_num
        ).optimize()
        delim = pynini.cross(pynini.union("-", "/", ":", "_"), " ") | pynutil.add_weight(pynini.cross(".", " "), 0.1)
        composite_alnum = pynutil.add_weight(alphanum_fixed, -0.5) | (alnum_seg + pynini.closure(delim + alnum_seg))

        self.serial = (pynutil.insert("name: \"") + convert_space(composite_alnum) + pynutil.insert("\"")).optimize()
