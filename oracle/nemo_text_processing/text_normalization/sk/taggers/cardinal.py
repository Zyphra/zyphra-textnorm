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
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Slovak cardinal numbers, e.g.
        0 -> nula
        254 -> dvesto päťdesiatštyri
        -50 -> mínus päťdesiat
        1 000 000 -> jeden milión
        2 300 -> dvetisíc tristo
        2000003 -> dva milióny tri
        ~50 -> približne päťdesiat
        ±5 -> plus-mínus päť
        1,2,3 -> jeden, dva, tri
        5-10 -> päť až desať
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        # 0. Basic digits
        zero = pynini.cross("0", "nula")

        digit = pynini.string_map([
            ("1", "jeden"),
            ("2", "dva"),
            ("3", "tri"),
            ("4", "štyri"),
            ("5", "päť"),
            ("6", "šesť"),
            ("7", "sedem"),
            ("8", "osem"),
            ("9", "deväť"),
        ])

        digit_fem = pynini.string_map([
            ("1", "jedna"),
            ("2", "dve"),
            ("3", "tri"),
            ("4", "štyri"),
            ("5", "päť"),
            ("6", "šesť"),
            ("7", "sedem"),
            ("8", "osem"),
            ("9", "deväť"),
        ])

        digit_neut = pynini.string_map([
            ("1", "jedno"),
            ("2", "dve"),
            ("3", "tri"),
            ("4", "štyri"),
            ("5", "päť"),
            ("6", "šesť"),
            ("7", "sedem"),
            ("8", "osem"),
            ("9", "deväť"),
        ])

        self.digit = digit
        self.digit_fem = digit_fem
        self.digit_neut = digit_neut
        self.zero = zero

        # Teens 10..19
        teens = pynini.string_map([
            ("10", "desať"),
            ("11", "jedenásť"),
            ("12", "dvanásť"),
            ("13", "trinásť"),
            ("14", "štrnásť"),
            ("15", "pätnásť"),
            ("16", "šestnásť"),
            ("17", "sedemnásť"),
            ("18", "osemnásť"),
            ("19", "devätnásť"),
        ])
        self.teens = teens

        # Tens exact 20, 30, ..., 90
        tens_exact = pynini.string_map([
            ("20", "dvadsať"),
            ("30", "tridsať"),
            ("40", "štyridsať"),
            ("50", "päťdesiat"),
            ("60", "šesťdesiat"),
            ("70", "sedemdesiat"),
            ("80", "osemdesiat"),
            ("90", "deväťdesiat"),
        ])

        tens_stem = pynini.string_map([
            ("2", "dvadsať"),
            ("3", "tridsať"),
            ("4", "štyridsať"),
            ("5", "päťdesiat"),
            ("6", "šesťdesiat"),
            ("7", "sedemdesiat"),
            ("8", "osemdesiat"),
            ("9", "deväťdesiat"),
        ])
        self.tens_stem = tens_stem

        # Compound numbers 21..99
        tens_compound = tens_stem + digit
        two_digits = teens | tens_exact | tens_compound
        self.two_digits = two_digits

        one_to_99 = digit | two_digits
        self.one_to_99 = one_to_99

        # Hundreds 100..900
        hundreds_exact = pynini.string_map([
            ("100", "sto"),
            ("200", "dvesto"),
            ("300", "tristo"),
            ("400", "štyristo"),
            ("500", "päťsto"),
            ("600", "šesťsto"),
            ("700", "sedemsto"),
            ("800", "osemsto"),
            ("900", "deväťsto"),
        ])

        hundreds_stem = pynini.string_map([
            ("1", "sto"),
            ("2", "dvesto"),
            ("3", "tristo"),
            ("4", "štyristo"),
            ("5", "päťsto"),
            ("6", "šesťsto"),
            ("7", "sedemsto"),
            ("8", "osemsto"),
            ("9", "deväťsto"),
        ])
        self.hundreds_stem = hundreds_stem

        three_digits = hundreds_exact | (
            hundreds_stem + pynutil.insert(" ") + (pynutil.delete("0") + digit | two_digits)
        )
        self.three_digits = three_digits

        one_to_999 = one_to_99 | three_digits
        self.one_to_999 = one_to_999

        rem_999 = (pynutil.delete("00") + digit) | (pynutil.delete("0") + two_digits) | three_digits
        self.rem_999 = rem_999

        # Thousands 1 000 .. 999 999
        th_1 = pynini.cross("1", "tisíc")
        th_2 = pynini.cross("2", "dvetisíc")
        th_3 = pynini.cross("3", "tritisíc")
        th_4 = pynini.cross("4", "štyritisíc")
        th_other_units = (pynini.union("5", "6", "7", "8", "9") @ digit) + pynutil.insert("tisíc")
        th_teens = teens + pynutil.insert("tisíc")
        th_tens_exact = tens_exact + pynutil.insert("tisíc")
        th_tens_compound = tens_stem + digit + pynutil.insert(" tisíc")
        th_two_digits = th_teens | th_tens_exact | th_tens_compound
        th_hundreds_exact = hundreds_exact + pynutil.insert(" tisíc")
        th_hundreds = (
            hundreds_stem + pynutil.insert(" ") + (pynutil.delete("0") + digit | two_digits)
        ) + pynutil.insert(" tisíc")

        th_prefix = (
            th_1
            | th_2
            | th_3
            | th_4
            | th_other_units
            | th_two_digits
            | th_hundreds_exact
            | th_hundreds
        )

        thousands = (th_prefix + pynutil.delete("000")) | (th_prefix + pynutil.insert(" ") + rem_999)
        self.thousands = thousands

        one_to_999k = one_to_999 | thousands
        self.one_to_999k = one_to_999k

        # Millions 1 000 000 .. 999 999 999
        mil_1 = pynini.cross("1", "jeden milión")
        mil_few = (pynini.union("2", "3", "4") @ digit) + pynutil.insert(" milióny")
        mil_other = ((pynini.union("5", "6", "7", "8", "9") @ digit) | two_digits | three_digits) + pynutil.insert(
            " miliónov"
        )
        mil_prefix = mil_1 | mil_few | mil_other

        th_1d = th_1 | th_2 | th_3 | th_4 | th_other_units
        thousands_triad = (
            (pynutil.delete("00") + th_1d)
            | (pynutil.delete("0") + th_two_digits)
            | th_hundreds_exact
            | th_hundreds
        )

        rem_6 = (
            pynutil.delete("000000")
            | (pynutil.delete("000") + pynutil.insert(" ") + rem_999)
            | (pynutil.insert(" ") + thousands_triad + pynutil.delete("000"))
            | (pynutil.insert(" ") + thousands_triad + pynutil.insert(" ") + rem_999)
        )
        millions = mil_prefix + rem_6
        self.millions = millions

        one_to_999m = one_to_999k | millions

        # Billions (miliarda) 1 000 000 000 .. 999 999 999 999
        bil_1 = pynini.cross("1", "jedna miliarda")
        bil_few = (pynini.union("2", "3", "4") @ digit_fem) + pynutil.insert(" miliardy")
        bil_other = ((pynini.union("5", "6", "7", "8", "9") @ digit) | two_digits | three_digits) + pynutil.insert(
            " miliárd"
        )
        bil_prefix = bil_1 | bil_few | bil_other

        mil_1d = mil_1 | mil_few | ((pynini.union("5", "6", "7", "8", "9") @ digit) + pynutil.insert(" miliónov"))
        millions_triad = (
            (pynutil.delete("00") + mil_1d)
            | (pynutil.delete("0") + two_digits + pynutil.insert(" miliónov"))
            | (three_digits + pynutil.insert(" miliónov"))
        )
        rem_6_nonzero = (
            (pynutil.delete("000") + pynutil.insert(" ") + rem_999)
            | (pynutil.insert(" ") + thousands_triad + pynutil.delete("000"))
            | (pynutil.insert(" ") + thousands_triad + pynutil.insert(" ") + rem_999)
        )
        rem_9 = (
            pynutil.delete("000000000")
            | (pynutil.delete("000") + rem_6_nonzero)
            | (pynutil.insert(" ") + millions_triad + pynutil.delete("000000"))
            | (pynutil.insert(" ") + millions_triad + rem_6_nonzero)
        )
        billions = bil_prefix + rem_9

        all_positive = zero | one_to_999m | billions
        self.all_positive = all_positive

        # Grouped digits support (e.g. 1 000 000, 2 300, 21 000, 1.000.000)
        del_sep = pynutil.delete(pynini.union(" ", "\u00a0", "\u202f", "."))
        grouped_digits = (
            pynini.closure(NEMO_DIGIT, 1, 3) + pynini.closure(del_sep + pynini.closure(NEMO_DIGIT, 3, 3), 1)
        )
        grouped_cardinal = (grouped_digits @ all_positive).optimize()

        # Leading zeroes (e.g. 03 -> tri, 050 -> päťdesiat)
        leading_zeros_to_num = pynini.closure(pynutil.delete("0"), 1) + (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT)
        leading_zeros_graph = (leading_zeros_to_num @ all_positive).optimize()

        # Negative numbers (e.g. -50, −50, -050)
        neg_prefix = pynini.cross(pynini.union("-", "−"), "mínus ")
        neg_graph = neg_prefix + (all_positive | grouped_cardinal | leading_zeros_graph)

        plain_cardinal = all_positive | grouped_cardinal | leading_zeros_graph | neg_graph
        self.plain_cardinal = plain_cardinal.optimize()

        # Number lists: 1,2,3 -> jeden, dva, tri
        comma_sep = pynini.cross(",", ", ") | pynini.cross(", ", ", ")
        cardinal_list = (
            plain_cardinal + pynini.closure(comma_sep + plain_cardinal, 1)
        )

        # Number ranges: 5-10, 5–10, 10–20 -> päť až desať, desať až dvadsať
        dash_range = pynini.cross(pynini.union("-", "–", "—"), " až ")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        cardinal_range = plain_cardinal + opt_sp + dash_range + opt_sp + plain_cardinal

        # Approximations and plus-minus: ~50 -> približne päťdesiat, ±5 -> plus-mínus päť
        approx = pynini.cross("~", "približne ") + plain_cardinal
        plus_minus = pynini.cross("±", "plus-mínus ") + plain_cardinal

        # Serials and alphanumeric identifiers:
        # e.g. 2-b-34 -> dva b tridsaťštyri
        # 30kod -> tridsať kod
        # test-8 -> test osem
        # COVID-19 -> COVID devätnásť
        # A4 -> A štyri
        # BA249 -> B A dva štyri deväť
        sp_unit = pynutil.insert(" ")
        native_letters = "áäčďéíĺľňóôŕšťúýž"
        alpha_char = pynini.closure(NEMO_ALPHA | pynini.union(*(native_letters + native_letters.upper())), 1)
        serial_dash = (
            (plain_cardinal + pynini.cross("-", " ") + alpha_char + pynini.cross("-", " ") + plain_cardinal)
            | (plain_cardinal + sp_unit + alpha_char)
            | (alpha_char + pynini.cross("-", " ") + plain_cardinal)
        )

        final_graph = (
            pynutil.add_weight(approx, 1.05)
            | pynutil.add_weight(plus_minus, 1.05)
            | pynutil.add_weight(cardinal_range, 1.08)
            | pynutil.add_weight(cardinal_list, 1.09)
            | pynutil.add_weight(serial_dash, 1.15)
            | pynutil.add_weight(plain_cardinal, 1.1)
        )

        self.fst = (final_graph | all_positive + pynini.cross(":", " dvojbodka ") + all_positive).optimize()
