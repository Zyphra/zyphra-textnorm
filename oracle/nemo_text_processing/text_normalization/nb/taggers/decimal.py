# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål decimals and percentages.
    e.g. 3,14 -> tre komma en fire (or tre komma fjorten)
         0,5 -> null komma fem
         99.9% -> nittini komma ni prosent
         10-15% -> ti til femten prosent
         ±10% -> pluss minus ti prosent
         5‰ -> fem promille
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        integer_part = cardinal.cardinal
        decimal_sep = pynini.cross(",", " komma ") | pynini.cross(".", " komma ")

        single_digit = pynini.string_map(
            [
                ("0", "null"),
                ("1", "en"),
                ("2", "to"),
                ("3", "tre"),
                ("4", "fire"),
                ("5", "fem"),
                ("6", "seks"),
                ("7", "sju"),
                ("8", "åtte"),
                ("9", "ni"),
            ]
        )
        # Fraction read either as compound cardinal or digit-by-digit
        fractional_digits = pynini.closure(single_digit + pynutil.insert(" "), 1) + single_digit
        fraction_part = cardinal.cardinal | fractional_digits | single_digit

        # Decimal number
        decimal_num = integer_part + decimal_sep + fraction_part

        # Negative decimal
        neg_sign = pynini.cross("-", "minus ") | pynini.cross("−", "minus ")
        neg_decimal = neg_sign + decimal_num

        self.decimal_num = (neg_decimal | decimal_num).optimize()

        # Percent and Permille
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        pct = pynini.cross("%", " prosent")
        permille = pynini.cross("‰", " promille")
        pct_unit = pct | permille

        plus_minus = pynini.cross("±", "pluss minus ")
        opt_pm = pynini.closure(plus_minus, 0, 1)

        percent_single = (
            opt_pm
            + (self.decimal_num | cardinal.cardinal)
            + opt_space
            + pct_unit
        )

        # Percent range (e.g. 10-15%)
        dash = (
            pynini.cross("-", " til ")
            | pynini.cross("–", " til ")
            | pynini.cross("—", " til ")
        )
        percent_range = (
            (self.decimal_num | cardinal.cardinal)
            + opt_space
            + dash
            + opt_space
            + (self.decimal_num | cardinal.cardinal)
            + opt_space
            + pct_unit
        )

        all_decimals = (
            percent_range
            | percent_single
            | self.decimal_num
        )

        self.graph = all_decimals.optimize()
        self.fst = self.graph
