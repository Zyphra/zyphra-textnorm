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
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Czech decimal numbers, percentages,
    permilles, fractions, and mixed numbers.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        # Decimal point/comma
        # Integer part handling:
        # Whole-part agreement: one, two-to-four, and all other values.
        int_0 = pynini.cross("0", "nula celých ")
        int_1 = pynini.cross("1", "jedna celá ")
        int_few = pynini.string_map([
            ("2", "dvě celé "),
            ("3", "tři celé "),
            ("4", "čtyři celé "),
        ])
        other_input = pynini.difference(
            pynini.project(cardinal.positive_numbers, "input"),
            pynini.union("0", "1", "2", "3", "4").optimize(),
        ).optimize()
        int_other = (other_input @ cardinal.positive_numbers) + pynutil.insert(" celých ")
        int_part_spoken = (int_0 | int_1 | int_few | int_other).optimize()

        # Pure ungrouped integer part for dot-decimal fallback (prevents 1.000.000 -> 1.000 . 000)
        other_pure_input = pynini.difference(
            pynini.project(cardinal.n1_999, "input"),
            pynini.union("0", "1", "2", "3", "4").optimize(),
        ).optimize()
        int_pure_other = (other_pure_input @ cardinal.n1_999) + pynutil.insert(" celých ")
        int_pure_spoken = (int_0 | int_1 | int_few | int_pure_other).optimize()

        # Fractional part:
        # 1-digit: "5" -> "pět"
        # 2-digit: "05" -> "nula pět", "14" -> "čtrnáct", "50" -> "padesát"
        # multi-digit: digit sequence or number
        frac_digits = cardinal.digits
        frac_two = (
            (pynini.cross("0", "nula ") + frac_digits)
            | (cardinal.n1_999)
            | (pynini.closure(frac_digits + pynutil.insert(" "), 1) + frac_digits)
        )
        frac_multi = pynini.closure(frac_digits + pynutil.insert(" "), 1) + frac_digits
        frac_part_spoken = (frac_two | frac_multi | frac_digits).optimize()

        decimal_core = (
            (int_part_spoken + pynutil.delete(",") + frac_part_spoken)
            | (int_pure_spoken + pynutil.add_weight(pynutil.delete("."), 0.1) + frac_part_spoken)
        ).optimize()

        neg_sym = pynini.cross("-", "mínus ") | pynini.cross("−", "mínus ")
        neg_decimal = (neg_sym + decimal_core).optimize()

        self.decimal_numbers = (decimal_core | neg_decimal).optimize()

        # Percentages:
        # 1% -> "jedno procento"
        # 2..4% -> "dvě/tři/čtyři procenta"
        # 5+% -> "... procent"
        pct_sym = pynutil.delete("%")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        pct_one = pynini.cross("1", "jedno procento")
        pct_few = pynini.string_map([
            ("2", "dvě"),
            ("3", "tři"),
            ("4", "čtyři"),
        ]) + pynutil.insert(" procenta")
        pct_other = (
            pynini.difference(pynini.project(cardinal.positive_numbers, "input"), pynini.union("1", "2", "3", "4"))
            @ cardinal.positive_numbers
        ) + pynutil.insert(" procent")
        pct_dec = self.decimal_numbers + pynutil.insert(" procent")

        pct_val = (pct_one | pct_few | pct_other | pct_dec).optimize()
        pct_single = (pct_val + opt_sp + pct_sym).optimize()
        neg_pct = (neg_sym + pct_single).optimize()
        pm_pct = (
            (pynini.cross("±", "plus mínus ") | pynini.cross("+/-", "plus mínus "))
            + opt_sp
            + pct_single
        ).optimize()

        # Percent range: "10-15%" / "10–15%" -> "deset až patnáct procent"
        dash = pynini.cross("-", " až ") | pynini.cross("–", " až ") | pynini.cross("—", " až ")
        pct_range = (
            (cardinal.cardinal_numbers | self.decimal_numbers)
            + opt_sp
            + dash
            + opt_sp
            + pct_single
        ).optimize()

        self.percentages = (pct_single | neg_pct | pm_pct | pct_range).optimize()

        # Permille: "5‰" -> "pět promile"
        permille_sym = pynutil.delete("‰")
        self.permille = (
            (cardinal.cardinal_numbers | self.decimal_numbers)
            + opt_sp
            + pynutil.insert(" promile")
            + permille_sym
        ).optimize()

        # Fractions:
        # Common vulgar fractions
        vulgar_fractions = pynini.string_map([
            ("½", "jedna polovina"),
            ("⅓", "jedna třetina"),
            ("⅔", "dvě třetiny"),
            ("¼", "jedna čtvrtina"),
            ("¾", "tři čtvrtiny"),
            ("⅕", "jedna pětina"),
            ("⅖", "dvě pětiny"),
            ("⅗", "tři pětiny"),
            ("⅘", "čtyři pětiny"),
            ("⅙", "jedna šestina"),
            ("⅚", "pět šestin"),
            ("⅛", "jedna osmina"),
            ("⅜", "tři osminy"),
            ("⅝", "pět osmin"),
            ("⅞", "sedm osmin"),
            ("⅐", "jedna sedmina"),
            ("⅑", "jedna devítina"),
            ("⅒", "jedna desetina"),
        ])

        # Slash fractions: "1/2", "3/4", "5/8", etc.
        slash_fractions_map = [
            ("1/2", "jedna polovina"),
            ("1/3", "jedna třetina"),
            ("2/3", "dvě třetiny"),
            ("1/4", "jedna čtvrtina"),
            ("3/4", "tři čtvrtiny"),
            ("1/5", "jedna pětina"),
            ("2/5", "dvě pětiny"),
            ("3/5", "tři pětiny"),
            ("4/5", "čtyři pětiny"),
            ("1/6", "jedna šestina"),
            ("5/6", "pět šestin"),
            ("1/7", "jedna sedmina"),
            ("1/8", "jedna osmina"),
            ("3/8", "tři osminy"),
            ("5/8", "pět osmin"),
            ("7/8", "sedm osmin"),
            ("1/9", "jedna devítina"),
            ("1/10", "jedna desetina"),
            ("11/12", "jedenáct dvanáctin"),
            ("21/100", "dvacet jedna setin"),
            ("22/7", "dvacet dvě sedmin"),
            ("125/1000", "sto dvacet pět tisícin"),
            ("101/250", "sto jedna dvě stě padesátin"),
        ]
        slash_fractions = pynini.string_map(slash_fractions_map)

        all_pure_fractions = (vulgar_fractions | slash_fractions).optimize()
        neg_fractions = (neg_sym + all_pure_fractions).optimize()

        # Mixed fractions:
        # "2 1/2" -> "dvě a jedna polovina" (or "dvě celé jedna polovina")
        # "1 1/3" -> "jedna a jedna třetina"
        # "2½" -> "dvě a jedna polovina"
        # "-2½" -> "mínus dvě a jedna polovina"
        # "-3 3/4" -> "mínus tři a tři čtvrtiny"
        sp_or_none = pynini.closure(pynutil.delete(" "), 0, 1)

        mixed_join = pynutil.insert(" a ") | pynutil.insert(" celé ")

        mixed_pos = (
            cardinal.n1_999_fem
            + sp_or_none
            + mixed_join
            + all_pure_fractions
        ).optimize()
        mixed_neg = (neg_sym + mixed_pos).optimize()

        self.fractions = (
            all_pure_fractions
            | neg_fractions
            | mixed_pos
            | mixed_neg
        ).optimize()

        self.fst = (
            self.percentages
            | self.permille
            | self.fractions
            | self.decimal_numbers
        ).optimize()
