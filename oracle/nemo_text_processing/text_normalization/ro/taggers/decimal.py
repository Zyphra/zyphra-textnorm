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
)
from nemo_text_processing.text_normalization.ro.graph_utils import (
    RO_DASH,
    decimal_separator,
    to_name_token,
)
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Romanian decimals, e.g.
        "33,32" -> tokens { name: "treizeci și trei virgulă treizeci și doi" }
        "0,05" -> tokens { name: "zero virgulă zero cinci" }
        "-0,25" -> tokens { name: "minus zero virgulă douăzeci și cinci" }
        "3.5" -> tokens { name: "trei virgulă cinci" }
        "12,5%" -> tokens { name: "douăsprezece virgulă cinci la sută" }
        "99.9%" -> tokens { name: "nouăzeci și nouă virgulă nouă la sută" }
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        integer_part = cardinal.cardinal_numbers
        # For feminine integer parts (e.g. 12,5% -> douăsprezece virgulă cinci la sută)
        integer_part_fem = cardinal.cardinal_numbers_fem

        # Decimal separator to spoken "virgulă"
        sep = pynutil.delete(decimal_separator) + pynutil.insert(" virgulă ")

        # Fractional part:
        # 1 digit: "5" -> "cinci"
        frac_1 = cardinal.digit

        # 2 digits:
        # "05" -> "zero cinci"
        # "32" -> "treizeci și doi"
        frac_2_zero = pynutil.insert("zero ") + pynutil.delete("0") + cardinal.digit
        frac_2_non_zero = cardinal.cardinal_numbers
        frac_2 = frac_2_zero | frac_2_non_zero

        # 3 digits:
        # "005" -> "zero zero cinci"
        # "025" -> "zero douăzeci și cinci"
        # "125" -> "o sută douăzeci și cinci"
        frac_3_two_zero = pynutil.insert("zero zero ") + pynutil.delete("00") + cardinal.digit
        frac_3_one_zero = pynutil.insert("zero ") + pynutil.delete("0") + frac_2_non_zero
        frac_3_non_zero = cardinal.cardinal_numbers
        frac_3 = frac_3_two_zero | frac_3_one_zero | frac_3_non_zero

        # 4+ digits: digit by digit (serial digits)
        frac_long = pynini.closure(NEMO_DIGIT, 4) @ cardinal.serial_digits

        fractional_part = (
            (NEMO_DIGIT @ frac_1)
            | (NEMO_DIGIT**2 @ frac_2)
            | (NEMO_DIGIT**3 @ frac_3)
            | frac_long
        ).optimize()

        # Core decimal: 33,32 -> treizeci și trei virgulă treizeci și doi
        decimal_core = integer_part + sep + fractional_part

        # Negative decimal: -0,25 -> minus zero virgulă douăzeci și cinci
        minus_prefix = pynutil.delete(pynini.union("-", "−")) + pynutil.insert("minus ")
        decimal_neg = minus_prefix + decimal_core

        # Percent with decimals: 12,5% -> douăsprezece virgulă cinci la sută
        # In Romanian, 12,5% often uses feminine for 12 (douăsprezece) or masculine (doisprezece)
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        pct_suffix = opt_space + pynutil.delete("%") + pynutil.insert(" la sută")
        permille_suffix = opt_space + pynutil.delete("‰") + pynutil.insert(" la mie")

        decimal_percent = (
            pynini.closure(minus_prefix, 0, 1)
            + (integer_part_fem | integer_part)
            + sep
            + fractional_part
            + (pct_suffix | permille_suffix)
        )

        decimal_graph = (decimal_percent | decimal_neg | decimal_core).optimize()
        grouped_integer = pynini.union(*[
            (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynini.accep(separator) + NEMO_DIGIT ** 3, 1)
            for separator in (".", ",", " ", "\u00a0")
        ])
        grouped_input = pynini.closure(pynini.union("-", "−"), 0, 1) + grouped_integer
        grouped_input += pynini.closure(
            pynini.project(pct_suffix | permille_suffix, "input"), 0, 1
        )
        decimal_inputs = pynini.difference(
            pynini.project(decimal_graph, "input"), grouped_input.optimize()
        )
        self.decimal_no_tokens = (decimal_inputs @ decimal_graph).optimize()

        self.fst = to_name_token(self.decimal_no_tokens)
