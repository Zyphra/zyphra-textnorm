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
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying decimal and grouped numbers in Turkish:
    - 3,14 -> üç virgül on dört
    - 0,5 -> sıfır virgül beş
    - 1.234,56 -> bin iki yüz otuz dört virgül elli altı
    - -0,5 -> eksi sıfır virgül beş
    - 1,5 milyon -> bir virgül beş milyon
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        integer_part = cardinal.positive_cardinals

        d1_to_9 = pynini.string_map([
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        d2_to_9 = pynini.string_map([
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        tens_map = pynini.string_map([
            ("1", "on"),
            ("2", "yirmi"),
            ("3", "otuz"),
            ("4", "kırk"),
            ("5", "elli"),
            ("6", "altmış"),
            ("7", "yetmiş"),
            ("8", "seksen"),
            ("9", "doksan"),
        ])
        two_digits = (tens_map + pynutil.delete("0")) | (tens_map + pynutil.insert(" ") + d1_to_9)
        rem_1_to_99 = (pynutil.delete("0") + pynutil.insert(" ") + d1_to_9) | (pynutil.insert(" ") + two_digits)
        hundreds = (
            (pynini.cross("1", "yüz") + (pynutil.delete("00") | rem_1_to_99))
            | (d2_to_9 + pynutil.insert(" yüz") + (pynutil.delete("00") | rem_1_to_99))
        )

        frac_1 = pynini.string_map([
            ("0", "sıfır"),
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        frac_0x = pynini.cross("0", "sıfır ") + frac_1
        frac_2 = frac_0x | two_digits
        frac_3 = (
            (pynini.cross("00", "sıfır sıfır ") + frac_1)
            | (pynini.cross("0", "sıfır ") + two_digits)
            | hundreds
        )
        # More digits: digit-by-digit
        frac_seq = frac_1 + pynini.closure(pynutil.insert(" ") + frac_1, 1)

        fractional = (frac_2 | frac_1 | frac_3 | frac_seq).optimize()
        self.fractional = fractional

        opt_neg = pynini.closure(pynini.cross(pynini.union("-", "−"), "eksi "), 0, 1)

        decimal_comma = (
            opt_neg
            + integer_part
            + pynini.cross(",", " virgül ")
            + fractional
        )

        decimal_dot = (
            opt_neg
            + integer_part
            + pynini.cross(".", " virgül ")
            + fractional
        )

        quantity = pynini.string_map([
            ("milyon", "milyon"),
            ("milyonluk", "milyonluk"),
            ("milyar", "milyar"),
            ("milyarlık", "milyarlık"),
            ("trilyon", "trilyon"),
            ("katrilyon", "katrilyon"),
            ("bin", "bin"),
            ("bilyon", "bilyon"),
            ("biljoner", "biljon"),
        ])
        decimal_with_quantity = (decimal_comma | decimal_dot) + pynutil.delete(" ") + pynutil.insert(" ") + quantity
        cardinal_with_quantity = integer_part + pynutil.delete(" ") + pynutil.insert(" ") + quantity

        all_decimals = (
            decimal_with_quantity
            | cardinal_with_quantity
            | decimal_comma
            | decimal_dot
        ).optimize()
        self.all_decimals = all_decimals

        self.fst = (pynutil.insert('name: "') + convert_space(all_decimals) + pynutil.insert('"')).optimize()
