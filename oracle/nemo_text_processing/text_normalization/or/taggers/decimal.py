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

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGIT,
    convert_space,
)
from .cardinal import CardinalFst, SINGLE_DIGITS


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying decimal numbers in Odia:
        ୩.୧୪ -> tokens { name: "ତିନି ଦଶମିକ ଏକ ଚାରି" }
        -୨.୫ -> tokens { name: "ଋଣ ଦୁଇ ଦଶମିକ ପାଞ୍ଚ" }
        ୧.୫ କୋଟି -> tokens { name: "ଏକ ଦଶମିକ ପାଞ୍ଚ କୋଟି" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        self.cardinal = cardinal

        # Fractional digits read one by one:
        single_digit_word = pynini.string_map([(k, v) for k, v in SINGLE_DIGITS.items()])
        single_frac_digit = (NORMALIZE_DIGIT @ single_digit_word).optimize()
        fractional_digits = (
            single_frac_digit + pynini.closure(pynutil.insert(" ") + single_frac_digit)
        ).optimize()

        decimal_sep = pynini.cross(".", " ଦଶମିକ ") | pynini.cross(",", " ଦଶମିକ ")

        # Standard decimal: integer_part + decimal_sep + fractional_digits
        # Integer part can be positive or negative
        int_part = cardinal.cardinal_numbers
        neg_prefix = pynini.cross("-", "ଋଣ ") | pynini.cross("−", "ଋଣ ")
        int_with_neg = (pynini.closure(neg_prefix, 0, 1) + int_part).optimize()

        base_decimal = (int_with_neg + decimal_sep + fractional_digits).optimize()

        # Decimal starting with separator (e.g. .5 -> ଶୂନ୍ୟ ଦଶମିକ ପାଞ୍ଚ)
        lead_sep = pynini.cross(".", "ଶୂନ୍ୟ ଦଶମିକ ") | pynini.cross(",", "ଶୂନ୍ୟ ଦଶମିକ ")
        lead_decimal = (lead_sep + fractional_digits).optimize()
        neg_lead_decimal = (neg_prefix + lead_decimal).optimize()

        # Scale suffixes:
        # ୧.୫ କୋଟି, ୨ ଲକ୍ଷ, ୩.୨ ହଜାର, ୫ ମିଲିଅନ୍
        scale_words = pynini.union(
            pynini.cross("କୋଟି", "କୋଟି"),
            pynini.cross("ଲକ୍ଷ", "ଲକ୍ଷ"),
            pynini.cross("ହଜାର", "ହଜାର"),
            pynini.cross("ମିଲିଅନ୍", "ମିଲିଅନ୍"),
            pynini.cross("ମିଲିୟନ", "ମିଲିଅନ୍"),
            pynini.cross("ବିଲିଅନ୍", "ବିଲିଅନ୍"),
            pynini.cross("ବିଲିୟନ", "ବିଲିଅନ୍"),
            pynini.cross("k", "ହଜାର"),
            pynini.cross("K", "ହଜାର"),
            pynini.cross("M", "ମିଲିଅନ୍"),
            pynini.cross("B", "ବିଲିଅନ୍"),
        )
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        scale_suffix = opt_space + pynutil.insert(" ") + scale_words

        decimal_with_scale = (
            (base_decimal | int_with_neg) + scale_suffix
        ).optimize()

        # Approximate (~) and Plus-Minus (±)
        approx_prefix = pynini.cross("~", "ପ୍ରାୟ ")
        pm_prefix = pynini.cross("±", "ପ୍ଲସ୍ ମାଇନସ୍ ")

        all_decimals = (
            base_decimal
            | lead_decimal
            | neg_lead_decimal
            | decimal_with_scale
            | (approx_prefix + (base_decimal | decimal_with_scale))
            | (pm_prefix + (base_decimal | decimal_with_scale))
        ).optimize()
        decimal_inputs = pynini.difference(pynini.project(all_decimals, "input"), cardinal.grouped_numbers)
        all_decimals = (decimal_inputs @ all_decimals).optimize()

        self.decimal_numbers = all_decimals

        graph = pynutil.insert('name: "') + convert_space(all_decimals) + pynutil.insert('"')
        self.fst = graph.optimize()
