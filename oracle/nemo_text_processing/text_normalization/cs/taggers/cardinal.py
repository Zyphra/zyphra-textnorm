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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Czech cardinal numbers.
    Handles numbers from 0 to 999,999,999,999, grouped numbers, leading zeros,
    negatives, ranges, and decades.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        digits_map = [
            ("0", "nula"),
            ("1", "jedna"),
            ("2", "dva"),
            ("3", "tři"),
            ("4", "čtyři"),
            ("5", "pět"),
            ("6", "šest"),
            ("7", "sedm"),
            ("8", "osm"),
            ("9", "devět"),
        ]
        self.digits = pynini.string_map(digits_map)
        digits_no_zero = pynini.string_map(digits_map[1:])

        digits_fem = pynini.string_map([
            ("1", "jedna"),
            ("2", "dvě"),
            ("3", "tři"),
            ("4", "čtyři"),
            ("5", "pět"),
            ("6", "šest"),
            ("7", "sedm"),
            ("8", "osm"),
            ("9", "devět"),
        ])
        digits_masc = pynini.string_map([
            ("1", "jeden"),
            ("2", "dva"),
            ("3", "tři"),
            ("4", "čtyři"),
            ("5", "pět"),
            ("6", "šest"),
            ("7", "sedm"),
            ("8", "osm"),
            ("9", "devět"),
        ])
        digits_neut = pynini.string_map([
            ("1", "jedno"),
            ("2", "dvě"),
            ("3", "tři"),
            ("4", "čtyři"),
            ("5", "pět"),
            ("6", "šest"),
            ("7", "sedm"),
            ("8", "osm"),
            ("9", "devět"),
        ])

        teens_map = [
            ("10", "deset"),
            ("11", "jedenáct"),
            ("12", "dvanáct"),
            ("13", "třináct"),
            ("14", "čtrnáct"),
            ("15", "patnáct"),
            ("16", "šestnáct"),
            ("17", "sedmnáct"),
            ("18", "osmnáct"),
            ("19", "devatenáct"),
        ]
        teens = pynini.string_map(teens_map)

        tens_map = [
            ("2", "dvacet"),
            ("3", "třicet"),
            ("4", "čtyřicet"),
            ("5", "padesát"),
            ("6", "šedesát"),
            ("7", "sedmdesát"),
            ("8", "osmdesát"),
            ("9", "devadesát"),
        ]
        tens = pynini.string_map(tens_map)
        tens_with_unit = (tens + pynutil.delete("0")) | (tens + pynutil.insert(" ") + digits_no_zero)
        tens_with_unit_fem = (tens + pynutil.delete("0")) | (tens + pynutil.insert(" ") + digits_fem)
        tens_with_unit_masc = (tens + pynutil.delete("0")) | (tens + pynutil.insert(" ") + digits_masc)
        tens_with_unit_neut = (tens + pynutil.delete("0")) | (tens + pynutil.insert(" ") + digits_neut)

        hundreds_map = [
            ("1", "sto"),
            ("2", "dvě stě"),
            ("3", "tři sta"),
            ("4", "čtyři sta"),
            ("5", "pět set"),
            ("6", "šest set"),
            ("7", "sedm set"),
            ("8", "osm set"),
            ("9", "devět set"),
        ]
        hundreds = pynini.string_map(hundreds_map)

        del_zeros_2 = pynutil.delete("00")
        del_zeros_1 = pynutil.delete("0")

        def make_1_to_999(u_graph, tu_graph):
            h_full = (
                (hundreds + del_zeros_2)
                | (hundreds + del_zeros_1 + pynutil.insert(" ") + u_graph)
                | (hundreds + pynutil.insert(" ") + (teens | tu_graph))
            )
            return (u_graph | teens | tu_graph | h_full).optimize()

        self.n1_999 = make_1_to_999(digits_no_zero, tens_with_unit)
        self.n1_999_fem = make_1_to_999(digits_fem, tens_with_unit_fem)
        self.n1_999_masc = make_1_to_999(digits_masc, tens_with_unit_masc)
        self.n1_999_neut = make_1_to_999(digits_neut, tens_with_unit_neut)

        card_0_to_999 = (
            self.digits
            | teens
            | tens_with_unit
            | (hundreds + del_zeros_2)
            | (hundreds + del_zeros_1 + pynutil.insert(" ") + digits_no_zero)
            | (hundreds + pynutil.insert(" ") + (teens | tens_with_unit))
        ).optimize()

        # Thousands: 1 000 to 999 999
        th_one = pynini.cross("1", "tisíc")
        th_few = pynini.string_map([("2", "dva tisíce"), ("3", "tři tisíce"), ("4", "čtyři tisíce")])
        th_other_units = pynini.string_map([
            ("5", "pět"), ("6", "šest"), ("7", "sedm"), ("8", "osm"), ("9", "devět")
        ]) + pynutil.insert(" tisíc")
        th_teens = teens + pynutil.insert(" tisíc")
        th_tens = tens_with_unit + pynutil.insert(" tisíc")
        th_hundreds = (
            (hundreds + del_zeros_2 + pynutil.insert(" tisíc"))
            | (hundreds + del_zeros_1 + pynutil.insert(" ") + (th_one | th_few | th_other_units))
            | (hundreds + pynutil.insert(" ") + (th_teens | th_tens))
        )
        thousands_prefix = (th_one | th_few | th_other_units | th_teens | th_tens | th_hundreds).optimize()

        rem_3 = (
            (del_zeros_2 + del_zeros_1)
            | (del_zeros_2 + pynutil.insert(" ") + digits_no_zero)
            | (del_zeros_1 + pynutil.insert(" ") + (teens | tens_with_unit))
            | (pynutil.insert(" ") + (
                (hundreds + del_zeros_2)
                | (hundreds + del_zeros_1 + pynutil.insert(" ") + digits_no_zero)
                | (hundreds + pynutil.insert(" ") + (teens | tens_with_unit))
            ))
        )

        card_thousands = (thousands_prefix + (NEMO_DIGIT ** 3 @ rem_3)).optimize()

        # Millions: 1 000 000 to 999 999 999
        m_one = pynini.cross("1", "jeden milion") | pynutil.add_weight(pynini.cross("1", "milion"), 0.1)
        m_few = pynini.string_map([("2", "dva miliony"), ("3", "tři miliony"), ("4", "čtyři miliony")])
        m_other_units = pynini.string_map([
            ("5", "pět"), ("6", "šest"), ("7", "sedm"), ("8", "osm"), ("9", "devět")
        ]) + pynutil.insert(" milionů")
        m_teens = teens + pynutil.insert(" milionů")
        m_tens = tens_with_unit + pynutil.insert(" milionů")
        m_hundreds = (
            (hundreds + del_zeros_2 + pynutil.insert(" milionů"))
            | (hundreds + del_zeros_1 + pynutil.insert(" ") + (m_one | m_few | m_other_units))
            | (hundreds + pynutil.insert(" ") + (m_teens | m_tens))
        )
        millions_prefix = (m_one | m_few | m_other_units | m_teens | m_tens | m_hundreds).optimize()

        lower_six = pynini.closure(pynutil.delete("0")) + (card_thousands | self.n1_999)
        rem_6 = pynutil.delete("000000") | pynutil.insert(" ") + (NEMO_DIGIT ** 6 @ lower_six)
        card_millions = (millions_prefix + rem_6).optimize()

        # Billions (miliarda): 1 000 000 000 to 999 999 999 999
        b_one = pynini.cross("1", "jedna miliarda") | pynutil.add_weight(pynini.cross("1", "miliarda"), 0.1)
        b_few = pynini.string_map([("2", "dvě miliardy"), ("3", "tři miliardy"), ("4", "čtyři miliardy")])
        b_other_units = pynini.string_map([
            ("5", "pět"), ("6", "šest"), ("7", "sedm"), ("8", "osm"), ("9", "devět")
        ]) + pynutil.insert(" miliard")
        b_teens = teens + pynutil.insert(" miliard")
        b_tens = tens_with_unit + pynutil.insert(" miliard")
        b_hundreds = (
            (hundreds + del_zeros_2 + pynutil.insert(" miliard"))
            | (hundreds + del_zeros_1 + pynutil.insert(" ") + (b_one | b_few | b_other_units))
            | (hundreds + pynutil.insert(" ") + (b_teens | b_tens))
        )
        billions_prefix = (b_one | b_few | b_other_units | b_teens | b_tens | b_hundreds).optimize()

        lower_nine = pynini.closure(pynutil.delete("0")) + (card_millions | card_thousands | self.n1_999)
        rem_9 = pynutil.delete("000000000") | pynutil.insert(" ") + (NEMO_DIGIT ** 9 @ lower_nine)
        card_billions = (billions_prefix + rem_9).optimize()

        # Trillions: 1 000 000 000 000
        tr_one = pynini.cross("1", "jeden bilion")
        tr_few = pynini.string_map([("2", "dva biliony"), ("3", "tři biliony"), ("4", "čtyři biliony")])
        tr_other = pynini.string_map([
            ("5", "pět"), ("6", "šest"), ("7", "sedm"), ("8", "osm"), ("9", "devět")
        ]) + pynutil.insert(" bilionů")
        trillions_prefix = (tr_one | tr_few | tr_other).optimize()
        card_trillions = (trillions_prefix + del_zeros_2 ** 6).optimize()

        pure_cardinal = (
            card_0_to_999
            | card_thousands
            | card_millions
            | card_billions
            | card_trillions
        ).optimize()

        # Handle numbers with spaces or dots as thousands grouping
        # e.g. "1 000 000", "1.000.000", "2 300", "1 234 567"
        strip_separators = (
            (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(pynini.union(" ", ".", "\u00a0", "\u202f")) + NEMO_DIGIT ** 3, 1)
        )
        grouped_cardinal = pynini.compose(strip_separators, pure_cardinal).optimize()

        # Leading zero and digit-by-digit identifiers
        # "007" -> "nula nula sedm", "0042" -> "nula nula čtyřicet dva" or "nula nula čtyři dva"
        digit_seq = pynini.closure(self.digits + pynutil.insert(" "), 1) + self.digits
        leading_zeros = (
            pynini.closure(pynini.cross("0", "nula "), 1)
            + (pure_cardinal | digit_seq)
        ).optimize()

        all_positive = (grouped_cardinal | pure_cardinal | leading_zeros).optimize()

        # Negatives
        neg_sym = pynini.cross("-", "mínus ") | pynini.cross("−", "mínus ")
        negative_cardinal = (neg_sym + all_positive).optimize()

        # Cardinal ranges: "10-20", "10–20", "5-10", "1990–1995"
        dash = pynini.cross("-", " až ") | pynini.cross("–", " až ") | pynini.cross("—", " až ")
        opt_s = pynini.closure(pynutil.delete(" "), 0, 1)
        cardinal_range = (
            all_positive + opt_s + dash + opt_s + all_positive
        ).optimize()

        # Negative range: "-5-10" / "-5–10" -> "mínus pět až deset"
        neg_cardinal_range = (
            neg_sym + all_positive + opt_s + dash + opt_s + all_positive
        ).optimize()

        # Decades: "2020s" -> "dvacátá léta", "1990s" -> "devadesátá léta", "90. léta" -> "devadesátá léta"
        decades_map = [
            ("2020s", "dvacátá léta"),
            ("2010s", "desátá léta"),
            ("2000s", "nultá léta"),
            ("1990s", "devadesátá léta"),
            ("1980s", "osmdesátá léta"),
            ("1970s", "sedmdesátá léta"),
            ("1960s", "šedesátá léta"),
            ("1950s", "padesátá léta"),
            ("1940s", "čtyřicátá léta"),
            ("1930s", "třicátá léta"),
            ("1920s", "dvacátá léta"),
            ("90. léta", "devadesátá léta"),
            ("90.léta", "devadesátá léta"),
            ("80. léta", "osmdesátá léta"),
            ("80.léta", "osmdesátá léta"),
            ("70. léta", "sedmdesátá léta"),
            ("70.léta", "sedmdesátá léta"),
            ("60. léta", "šedesátá léta"),
            ("60.léta", "šedesátá léta"),
            ("1990-léta", "devadesátá léta"),
        ]
        decades = pynini.string_map(decades_map)
        self.positive_numbers = all_positive

        self.cardinal_numbers = (all_positive | negative_cardinal).optimize()
        self.range_graph = (cardinal_range | neg_cardinal_range).optimize()

        self.fst = (
            self.cardinal_numbers
            | self.range_graph
            | decades
        ).optimize()
