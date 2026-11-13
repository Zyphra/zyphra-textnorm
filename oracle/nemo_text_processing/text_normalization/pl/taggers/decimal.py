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
    insert_space,
)
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Polish decimals and percentages, e.g.
        "2,5" -> "dwa przecinek pięć"
        "3.14" -> "trzy przecinek czternaście"
        "0,05" -> "zero przecinek zero pięć"
        "-0,25" -> "minus zero przecinek dwadzieścia pięć"
        "12,5%" -> "dwanaście przecinek pięć procent"
        "99.9%" -> "dziewięćdziesiąt dziewięć przecinek dziewięć procent"
        "-5%" -> "minus pięć procent"
        "5‰" -> "pięć promili"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        digits = cardinal.digit + pynini.closure(insert_space + cardinal.digit)
        leading_zero_frac = pynini.compose(pynini.accep("0") + pynini.closure(NEMO_DIGIT, 1), digits)
        normal_frac = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ cardinal.graph
        long_frac = pynini.compose(pynini.closure(NEMO_DIGIT, 4), digits)

        frac_part = (leading_zero_frac | normal_frac | long_frac).optimize()

        # Decimal separator: comma (standard) or dot (fallback with penalty, no dot thousands grouping)
        sep_comma = pynini.cross(",", " przecinek ")
        sep_dot = pynutil.add_weight(pynini.cross(".", " przecinek "), 0.2)

        grouped_space = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(pynini.union(" ", "\u00a0")) + NEMO_DIGIT**3, 1, 3)
        )
        integer_dot = (cardinal.graph | grouped_space @ cardinal.graph).optimize()
        integer_comma = cardinal.graph_with_sep

        decimal_core = (
            integer_comma + sep_comma + frac_part
            | integer_dot + sep_dot + frac_part
        ).optimize()

        prefix_sign = (
            pynini.cross(pynini.union("-", "−"), "minus ")
            | (pynini.cross("~", "około ") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "plus minus ") + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        opt_prefix = pynini.closure(prefix_sign, 0, 1)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        pct = pynini.cross("%", " procent")
        permille = pynini.cross("‰", " promili")
        pct_or_permille = opt_sp + (pct | permille)

        decimal_num = opt_prefix + decimal_core
        decimal_pct = opt_prefix + decimal_core + pct_or_permille
        integer_pct = opt_prefix + integer_comma + pct_or_permille

        # Percentage ranges: 10-15%, 10%-15% (second number in genitive)
        dash = pynini.union("-", "–", "—")
        range_to = pynini.cross(dash, " do ")
        integer_gen = cardinal.graph_genitive_with_sep

        pct_range = (
            integer_comma + range_to + integer_gen + pct
            | integer_comma + pct + range_to + integer_gen + pct
            | decimal_core + range_to + decimal_core + pct
        )

        self.graph = (decimal_pct | integer_pct | pct_range | decimal_num).optimize()
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
