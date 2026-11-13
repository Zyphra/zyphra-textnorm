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
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    delete_space,
    insert_space,
)


def _build_number_graph(gender: str = "masculine") -> pynini.Fst:
    """
    Constructs Norwegian Bokmål cardinal transduction from digits to words.
    gender: 'masculine' (uses 'en') or 'neuter' (uses 'ett').
    """
    one_word = "ett" if gender == "neuter" else "en"

    unit = pynini.string_map(
        [
            ("1", one_word),
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
    unit_no_one = pynini.string_map(
        [
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
    teens = pynini.string_map(
        [
            ("10", "ti"),
            ("11", "elleve"),
            ("12", "tolv"),
            ("13", "tretten"),
            ("14", "fjorten"),
            ("15", "femten"),
            ("16", "seksten"),
            ("17", "sytten"),
            ("18", "atten"),
            ("19", "nitten"),
        ]
    )
    ties = pynini.string_map(
        [
            ("2", "tjue"),
            ("3", "tretti"),
            ("4", "førti"),
            ("5", "femti"),
            ("6", "seksti"),
            ("7", "sytti"),
            ("8", "åtti"),
            ("9", "nitti"),
        ]
    )

    compound_tens = ties + unit
    exact_ties = ties + pynutil.delete("0")
    tens = teens | exact_ties | compound_tens
    two_digits_non_zero = tens | (pynutil.delete("0") + unit)

    digits_1_99 = unit | tens

    # Hundreds (exact 3 digits: 100-999)
    hundre_exact = (
        pynini.cross("100", "hundre")
        | pynutil.add_weight(pynini.cross("100", "ett hundre"), 0.1)
        | (unit_no_one + pynutil.delete("00") + pynutil.insert(" hundre"))
    )

    hundre_rem = (
        (pynutil.delete("1") | pynutil.add_weight(pynini.cross("1", "ett "), 0.1))
        + pynutil.insert("hundre og ")
        + two_digits_non_zero
    ) | (unit_no_one + pynutil.insert(" hundre og ") + two_digits_non_zero)

    digits_1_999 = digits_1_99 | hundre_exact | hundre_rem

    prefix_3d_no_one = hundre_exact | hundre_rem | tens | unit_no_one

    # 3-digit padded (001-999)
    pad_3d_small = (pynutil.delete("0") + tens) | (pynutil.delete("00") + unit)
    pad_3d_hundreds = hundre_exact | hundre_rem
    pad_3d = pad_3d_small | pad_3d_hundreds

    # Thousands (1,000 - 999,999)
    tusen_head = (
        pynini.cross("1", "tusen")
        | pynutil.add_weight(pynini.cross("1", "ett tusen"), 0.1)
        | (prefix_3d_no_one + pynutil.insert(" tusen"))
    )

    tusen_exact = tusen_head + pynutil.delete("000")
    tusen_rem_small = tusen_head + pynutil.insert(" og ") + pad_3d_small
    tusen_rem_hundreds = tusen_head + pynutil.insert(" ") + pad_3d_hundreds
    thousands_block = tusen_exact | tusen_rem_small | tusen_rem_hundreds

    digits_1_999999 = digits_1_999 | thousands_block

    # Padded thousands (exact 3 digits: 000-999) used inside millions and higher
    pad_thousands_non_zero = (
        (pynutil.delete("00") + (pynini.cross("1", "ett tusen") | pynutil.add_weight(pynini.cross("1", "tusen"), 0.1)))
        | (pynutil.delete("00") + unit_no_one + pynutil.insert(" tusen"))
        | (pynutil.delete("0") + tens + pynutil.insert(" tusen"))
        | ((hundre_exact | hundre_rem) + pynutil.insert(" tusen"))
    )

    # 6-digit tail (exact 6 digits: 000000 - 999999)
    tail_6d_exact_zero = pynutil.delete("000000")
    tail_6d_no_thousands_small = pynutil.delete("000") + pynutil.insert(" og ") + pad_3d_small
    tail_6d_no_thousands_hundreds = pynutil.delete("000") + pynutil.insert(" ") + pad_3d_hundreds
    tail_6d_has_thousands_exact = pynutil.insert(" ") + pad_thousands_non_zero + pynutil.delete("000")
    tail_6d_has_thousands_small = pynutil.insert(" ") + pad_thousands_non_zero + pynutil.insert(" og ") + pad_3d_small
    tail_6d_has_thousands_hundreds = pynutil.insert(" ") + pad_thousands_non_zero + pynutil.insert(" ") + pad_3d_hundreds

    tail_6d_non_zero = (
        tail_6d_no_thousands_small
        | tail_6d_no_thousands_hundreds
        | tail_6d_has_thousands_exact
        | tail_6d_has_thousands_small
        | tail_6d_has_thousands_hundreds
    )

    # Millions (1,000,000 - 999,999,999)
    million_head = (
        pynini.cross("1", "en million")
        | (prefix_3d_no_one + pynutil.insert(" millioner"))
    )
    million_exact = million_head + tail_6d_exact_zero
    million_rem = million_head + tail_6d_non_zero
    millions_block = million_exact | million_rem

    digits_1_999999999 = digits_1_999999 | millions_block

    # Padded millions (exact 3 digits: 000-999) used inside billions
    pad_millions_non_zero = (
        (pynutil.delete("00") + pynini.cross("1", "én million"))
        | (pynutil.delete("00") + unit_no_one + pynutil.insert(" millioner"))
        | (pynutil.delete("0") + tens + pynutil.insert(" millioner"))
        | ((hundre_exact | hundre_rem) + pynutil.insert(" millioner"))
    )

    # 9-digit tail (exact 9 digits)
    tail_9d_exact_zero = pynutil.delete("000000000")
    tail_9d_no_millions = pynutil.delete("000") + tail_6d_non_zero
    tail_9d_has_millions = pynutil.insert(" ") + pad_millions_non_zero + (tail_6d_exact_zero | tail_6d_non_zero)
    tail_9d_non_zero = tail_9d_no_millions | tail_9d_has_millions

    # Billions (1,000,000,000 - 999,999,999,999)
    milliard_head = (
        pynini.cross("1", "en milliard")
        | (prefix_3d_no_one + pynutil.insert(" milliarder"))
    )
    milliard_exact = milliard_head + tail_9d_exact_zero
    milliard_rem = milliard_head + tail_9d_non_zero
    milliards_block = milliard_exact | milliard_rem

    # Padded milliards (exact 3 digits: 000-999)
    pad_milliards_non_zero = (
        (pynutil.delete("00") + pynini.cross("1", "én milliard"))
        | (pynutil.delete("00") + unit_no_one + pynutil.insert(" milliarder"))
        | (pynutil.delete("0") + tens + pynutil.insert(" milliarder"))
        | ((hundre_exact | hundre_rem) + pynutil.insert(" milliarder"))
    )

    # 12-digit tail
    tail_12d_exact_zero = pynutil.delete("000000000000")
    tail_12d_no_milliards = pynutil.delete("000") + tail_9d_non_zero
    tail_12d_has_milliards = pynutil.insert(" ") + pad_milliards_non_zero + (tail_9d_exact_zero | tail_9d_non_zero)
    tail_12d_non_zero = tail_12d_no_milliards | tail_12d_has_milliards

    # Trillions (1,000,000,000,000 - 999,999,999,999,999)
    billion_head = (
        pynini.cross("1", "en billion")
        | (prefix_3d_no_one + pynutil.insert(" billioner"))
    )
    billion_exact = billion_head + tail_12d_exact_zero
    billion_rem = billion_head + tail_12d_non_zero
    billions_block = billion_exact | billion_rem

    full_graph = (
        digits_1_999999999
        | milliards_block
        | billions_block
    )

    three_digits = NEMO_DIGIT ** 3
    end_or_sep = pynini.union(".", " ", "[EOS]")
    del_dot = pynini.cdrewrite(pynutil.delete("."), "", three_digits + end_or_sep, NEMO_SIGMA)
    del_space = pynini.cdrewrite(pynutil.delete(" "), "", three_digits + end_or_sep, NEMO_SIGMA)
    cleaned_input = (del_dot @ del_space).optimize()
    cardinal_with_sep = (cleaned_input @ full_graph).optimize()

    return (full_graph | cardinal_with_sep).optimize()


class CardinalFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål cardinals.
    e.g. 1000 -> tusen
         123 -> hundre og tjuetre
         -5 -> minus fem
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        zero = pynini.cross("0", "null")
        cardinal_masc = _build_number_graph("masculine")
        cardinal_neut = _build_number_graph("neuter")

        self.cardinal_masculine = (zero | cardinal_masc).optimize()
        self.cardinal_neuter = (zero | cardinal_neut).optimize()
        self.cardinal = self.cardinal_masculine

        # Digit by digit (identifiers / leading zeros like 007, 01)
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
        leading_zero = pynini.cross("0", "null") + pynini.closure(
            pynutil.insert(" ") + single_digit, 1
        )
        self.leading_zero = leading_zero.optimize()

        # Negative numbers (-5, −5)
        neg_sign = pynini.cross("-", "minus ") | pynini.cross("−", "minus ")
        negative = neg_sign + self.cardinal

        # Ranges (5-10, 5–10)
        dash = (
            pynini.cross("-", " til ")
            | pynini.cross("–", " til ")
            | pynini.cross("—", " til ")
        )
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        number_range = self.cardinal + opt_space + dash + opt_space + self.cardinal
        neg_range = negative + opt_space + dash + opt_space + self.cardinal

        all_cardinals = (
            self.cardinal
            | negative
            | leading_zero
            | number_range
            | neg_range
        )

        self.graph = all_cardinals.optimize()
        self.fst = (self.graph | self.cardinal + pynini.cross(":", " til ") + self.cardinal).optimize()
