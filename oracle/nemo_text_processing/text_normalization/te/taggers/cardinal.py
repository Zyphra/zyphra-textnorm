# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_ZERO,
    NEMO_DIGIT,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path

# CLDR te %spellout-cardinal: the exact multiple and the combining form of each magnitude differ
# (200 రెండు వందలు / 201 రెండు వందల ఒకటి, 1000 వెయ్యి / 2000 రెండు వేల, 100000 ఒక లక్ష / 200000 రెండు లక్షల).
HUNDRED = "వంద"
HUNDRED_COMBINING_ONE = "నూట"
HUNDREDS_EXACT = "వందలు"
HUNDREDS = "వందల"
THOUSAND_ONE = "వెయ్యి"
THOUSANDS = "వేల"
LAKH_ONE = "ఒక లక్ష"
LAKHS = "లక్షల"
CRORE_ONE = "ఒక కోటి"
CRORES = "కోట్ల"
ARAB = "అరబ్"
KHARAB = "ఖరబ్"


def _rest(lower: 'pynini.FstLike', exact: 'pynini.FstLike') -> 'pynini.FstLike':
    """Non-zero k-digit string that may start with zeros: a zero is dropped and the rest read as k-1 digits."""
    return (pynutil.delete("0") + lower | exact).optimize()


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Telugu cardinals (ASCII and Telugu digits), e.g.
        -23 -> cardinal { negative: "true" integer: "ఇరవై మూడు" }
        201 -> cardinal { integer: "రెండు వందల ఒకటి" }
        1,00,000 -> cardinal { integer: "ఒక లక్ష" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True, lm: bool = False):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        zero = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))
        teens_ties = pynini.string_file(get_abs_path("data/numbers/teens_and_ties.tsv"))
        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()

        # ASCII-only building blocks
        d1 = pynini.compose(pynini.union(*"123456789"), digit).optimize()
        d2_9 = pynini.compose(pynini.union(*"23456789"), digit).optimize()
        e2 = teens_ties
        r2 = _rest(d1, e2)

        e3 = (
            pynini.cross("100", HUNDRED)
            | pynutil.delete("1") + pynutil.insert(HUNDRED_COMBINING_ONE + " ") + r2
            | d2_9 + (pynini.cross("00", " " + HUNDREDS_EXACT) | pynutil.insert(" " + HUNDREDS + " ") + r2)
        ).optimize()
        r3 = _rest(r2, e3)

        def magnitude(head, zeros: int, rest):
            return (head + (pynutil.delete("0" * zeros) | insert_space + rest)).optimize()

        head_th_1 = pynini.cross("1", THOUSAND_ONE) | d2_9 + pynutil.insert(" " + THOUSANDS)
        head_th_2 = e2 + pynutil.insert(" " + THOUSANDS)
        e4 = magnitude(head_th_1, 3, r3)
        e5 = magnitude(head_th_2, 3, r3)
        r4 = _rest(r3, e4)
        r5 = _rest(r4, e5)

        head_l_1 = pynini.cross("1", LAKH_ONE) | d2_9 + pynutil.insert(" " + LAKHS)
        head_l_2 = e2 + pynutil.insert(" " + LAKHS)
        e6 = magnitude(head_l_1, 5, r5)
        e7 = magnitude(head_l_2, 5, r5)
        r6 = _rest(r5, e6)
        r7 = _rest(r6, e7)

        head_c_1 = pynini.cross("1", CRORE_ONE) | d2_9 + pynutil.insert(" " + CRORES)
        head_c_2 = e2 + pynutil.insert(" " + CRORES)
        e8 = magnitude(head_c_1, 7, r7)
        e9 = magnitude(head_c_2, 7, r7)
        r8 = _rest(r7, e8)
        r9 = _rest(r8, e9)

        head_a_1 = pynini.cross("1", ARAB) | d2_9 + pynutil.insert(" " + ARAB)
        head_a_2 = e2 + pynutil.insert(" " + ARAB)
        e10 = magnitude(head_a_1, 9, r9)
        e11 = magnitude(head_a_2, 9, r9)
        r10 = _rest(r9, e10)
        r11 = _rest(r10, e11)

        # ఖరబ్ is the largest named magnitude; CLDR reads its multiplier (up to 7 digits) as a full cardinal.
        up_to_7_without_one = pynini.union(d2_9, e2, e3, e4, e5, e6, e7).optimize()
        head_k = pynini.cross("1", KHARAB) | up_to_7_without_one + pynutil.insert(" " + KHARAB)
        e12_18 = magnitude(head_k, 11, r11)

        ascii_graph = pynini.union(
            pynini.cross("0", "సున్నా"), d1, e2, e3, e4, e5, e6, e7, e8, e9, e10, e11, e12_18
        ).optimize()

        def accept_te_digits(graph):
            return pynini.compose(to_ascii, graph).optimize()

        self.digit = digit
        self.zero = zero
        self.teens_and_ties = accept_te_digits(e2)
        self.graph_hundreds = accept_te_digits(e3)
        self.graph_thousands = accept_te_digits(e4 | e5)
        # 1-999 without leading zeros, used by time, date, ordinal and serial graphs
        self.up_to_999 = accept_te_digits(d1 | e2 | e3)
        # ASCII building blocks for the ordinal builder
        self.ascii_d2_9 = d2_9
        self.ascii_e2 = e2

        # Digit-by-digit reading, e.g. "073" -> "సున్నా ఏడు మూడు"
        single_digit_graph = digit | zero
        self.single_digits_graph = (single_digit_graph + pynini.closure(insert_space + single_digit_graph)).optimize()

        graph_without_leading_zeros = accept_te_digits(ascii_graph)
        self.graph_without_leading_zeros = graph_without_leading_zeros

        cardinal_with_leading_zeros = pynini.compose(
            NEMO_ALL_ZERO + pynini.closure(NEMO_ALL_DIGIT, 1), self.single_digits_graph
        )
        cardinal_with_leading_zeros = pynutil.add_weight(cardinal_with_leading_zeros, 0.5)

        # Digit-group separators: Indian (1,00,000) and international (100,000) grouping.
        delete_separator = pynutil.delete(",")
        two_digits = NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        three_digits = NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        indian_grouping = (
            pynini.closure(NEMO_ALL_DIGIT, 1, 2)
            + pynini.closure(delete_separator + two_digits)
            + delete_separator
            + three_digits
        )
        western_grouping = pynini.closure(NEMO_ALL_DIGIT, 1, 3) + pynini.closure(delete_separator + three_digits, 1)
        strip_separators = (indian_grouping | western_grouping).optimize()
        cardinal_with_separators = pynini.compose(strip_separators, graph_without_leading_zeros).optimize()

        final_graph = graph_without_leading_zeros | cardinal_with_leading_zeros | cardinal_with_separators

        optional_minus_graph = pynini.closure(pynutil.insert("negative: ") + pynini.cross("-", "\"true\" "), 0, 1)

        # Serial codes: 1-3 digit groups read as cardinals, 4+ digits read digit-by-digit
        any_digit = pynini.union(NEMO_DIGIT, NEMO_ALL_DIGIT).optimize()
        digitwise_4plus = pynini.compose(any_digit**4 + pynini.closure(any_digit), self.single_digits_graph).optimize()
        self.code_num_graph = (single_digit_graph | self.up_to_999 | digitwise_4plus).optimize()

        self.final_graph = final_graph.optimize()

        # Attributive form for a number directly before a counted noun (money, measure units): the exact multiple
        # of a hundred takes the combining form and a final ఒకటి becomes ఒక (500 -> ఐదు వందల రూపాయలు, 1 -> ఒక కిలోగ్రాము).
        attributive = pynini.cdrewrite(
            pynini.cross(HUNDREDS_EXACT, HUNDREDS), "", "[EOS]", NEMO_SIGMA
        ) @ pynini.cdrewrite(pynini.cross("ఒకటి", "ఒక"), pynini.union("[BOS]", " "), "[EOS]", NEMO_SIGMA)
        self.attributive_graph = pynini.compose(self.final_graph, attributive).optimize()
        final_graph = optional_minus_graph + pynutil.insert("integer: \"") + self.final_graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
