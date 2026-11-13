# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_ZERO,
    NEMO_DIGIT,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path

# CLDR kn %spellout-cardinal: exact multiple and combining form of each magnitude differ
HUNDRED = "ನೂರು"
HUNDREDS_EXACT = {
    "1": "ನೂರು",
    "2": "ಇನ್ನೂರು",
    "3": "ಮುನ್ನೂರು",
    "4": "ನಾನೂರು",
    "5": "ಐನೂರು",
    "6": "ಆರುನೂರು",
    "7": "ಏಳುನೂರು",
    "8": "ಎಂಟುನೂರು",
    "9": "ಒಂಬೈನೂರು",
}
HUNDREDS_COMB = {
    "1": "ನೂರ",
    "2": "ಇನ್ನೂರ",
    "3": "ಮುನ್ನೂರ",
    "4": "ನಾನೂರ",
    "5": "ಐನೂರ",
    "6": "ಆರುನೂರ",
    "7": "ಏಳುನೂರ",
    "8": "ಎಂಟುನೂರ",
    "9": "ಒಂಬೈನೂರ",
}

THOUSAND_ONE = "ಸಾವಿರ"
THOUSAND_ONE_COMB = "ಒಂದು ಸಾವಿರದ"
THOUSANDS = "ಸಾವಿರ"
THOUSANDS_COMB = "ಸಾವಿರದ"

LAKH_ONE = "ಒಂದು ಲಕ್ಷ"
LAKH_ONE_COMB = "ಒಂದು ಲಕ್ಷದ"
LAKHS = "ಲಕ್ಷ"
LAKHS_COMB = "ಲಕ್ಷದ"

CRORE_ONE = "ಒಂದು ಕೋಟಿ"
CRORE_ONE_COMB = "ಒಂದು ಕೋಟಿಯ"
CRORES = "ಕೋಟಿ"
CRORES_COMB = "ಕೋಟಿಯ"

ARAB = "ಅರಬ್"
KHARAB = "ಖರಬ್"


def _rest(lower: 'pynini.FstLike', exact: 'pynini.FstLike') -> 'pynini.FstLike':
    """Non-zero k-digit string that may start with zeros: a zero is dropped and the rest read as k-1 digits."""
    return (pynutil.delete("0") + lower | exact).optimize()


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Kannada cardinals (ASCII and Kannada digits), e.g.
        -23 -> cardinal { negative: "true" integer: "ಇಪ್ಪತ್ತಮೂರು" }
        201 -> cardinal { integer: "ಇನ್ನೂರ ಒಂದು" }
        1,00,000 -> cardinal { integer: "ಒಂದು ಲಕ್ಷ" }

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

        hundreds_exact_graph = pynini.union(*[pynini.cross(k + "00", v) for k, v in HUNDREDS_EXACT.items()]).optimize()
        hundreds_comb_graph = pynini.union(*[pynini.cross(k, v + " ") for k, v in HUNDREDS_COMB.items()]).optimize()
        e3 = (hundreds_exact_graph | (hundreds_comb_graph + r2)).optimize()
        r3 = _rest(r2, e3)

        # Thousands: 1,000 - 99,999
        # Exact 1000: ಒಂದು ಸಾವಿರ or ಸಾವಿರ
        th_1_exact = pynini.cross("1000", "ಒಂದು ಸಾವಿರ") | pynutil.add_weight(pynini.cross("1000", "ಸಾವಿರ"), 0.1)
        th_1_comb = pynini.cross("1", "ಒಂದು ಸಾವಿರದ ") + r3
        th_1 = (th_1_exact | th_1_comb).optimize()

        th_2_9_exact = d2_9 + pynini.cross("000", " ಸಾವಿರ")
        th_2_9_comb = d2_9 + pynutil.insert(" ಸಾವಿರದ ") + r3
        th_2_9 = (th_2_9_exact | th_2_9_comb).optimize()

        e4 = (th_1 | th_2_9).optimize()

        th_10_99_exact = e2 + pynini.cross("000", " ಸಾವಿರ")
        th_10_99_comb = e2 + pynutil.insert(" ಸಾವಿರದ ") + r3
        e5 = (th_10_99_exact | th_10_99_comb).optimize()

        r4 = _rest(r3, e4)
        r5 = _rest(r4, e5)

        # Lakhs: 1,00,000 - 99,99,999
        l_1_exact = pynini.cross("100000", "ಒಂದು ಲಕ್ಷ")
        l_1_comb = pynini.cross("1", "ಒಂದು ಲಕ್ಷದ ") + r5
        l_1 = (l_1_exact | l_1_comb).optimize()

        l_2_9_exact = d2_9 + pynini.cross("00000", " ಲಕ್ಷ")
        l_2_9_comb = d2_9 + pynutil.insert(" ಲಕ್ಷದ ") + r5
        l_2_9 = (l_2_9_exact | l_2_9_comb).optimize()

        e6 = (l_1 | l_2_9).optimize()

        l_10_99_exact = e2 + pynini.cross("00000", " ಲಕ್ಷ")
        l_10_99_comb = e2 + pynutil.insert(" ಲಕ್ಷದ ") + r5
        e7 = (l_10_99_exact | l_10_99_comb).optimize()

        r6 = _rest(r5, e6)
        r7 = _rest(r6, e7)

        # Crores: 1,00,00,000 - 99,99,99,999
        c_1_exact = pynini.cross("10000000", "ಒಂದು ಕೋಟಿ")
        c_1_comb = pynini.cross("1", "ಒಂದು ಕೋಟಿಯ ") + r7
        c_1 = (c_1_exact | c_1_comb).optimize()

        c_2_9_exact = d2_9 + pynini.cross("0000000", " ಕೋಟಿ")
        c_2_9_comb = d2_9 + pynutil.insert(" ಕೋಟಿಯ ") + r7
        c_2_9 = (c_2_9_exact | c_2_9_comb).optimize()

        e8 = (c_1 | c_2_9).optimize()

        c_10_99_exact = e2 + pynini.cross("0000000", " ಕೋಟಿ")
        c_10_99_comb = e2 + pynutil.insert(" ಕೋಟಿಯ ") + r7
        e9 = (c_10_99_exact | c_10_99_comb).optimize()

        r8 = _rest(r7, e8)
        r9 = _rest(r8, e9)

        # Arabs (10^9) and Kharabs (10^11)
        head_a_1 = pynini.cross("1", "ಒಂದು " + ARAB) | d2_9 + pynutil.insert(" " + ARAB)
        head_a_2 = e2 + pynutil.insert(" " + ARAB)
        e10 = (head_a_1 + (pynutil.delete("0" * 9) | insert_space + r9)).optimize()
        e11 = (head_a_2 + (pynutil.delete("0" * 9) | insert_space + r9)).optimize()
        r10 = _rest(r9, e10)
        r11 = _rest(r10, e11)

        up_to_7_without_one = pynini.union(d2_9, e2, e3, e4, e5, e6, e7).optimize()
        head_k = pynini.cross("1", "ಒಂದು " + KHARAB) | up_to_7_without_one + pynutil.insert(" " + KHARAB)
        e12_18 = (head_k + (pynutil.delete("0" * 11) | insert_space + r11)).optimize()

        ascii_graph = pynini.union(
            pynini.cross("0", "ಸೊನ್ನೆ"), d1, e2, e3, e4, e5, e6, e7, e8, e9, e10, e11, e12_18
        ).optimize()

        def accept_kn_digits(graph):
            return pynini.compose(to_ascii, graph).optimize()

        self.digit = digit
        self.zero = zero
        self.teens_and_ties = accept_kn_digits(e2)
        self.graph_hundreds = accept_kn_digits(e3)
        self.graph_thousands = accept_kn_digits(e4 | e5)
        # 1-999 without leading zeros, used by time, date, ordinal and serial graphs
        self.up_to_999 = accept_kn_digits(d1 | e2 | e3)
        # ASCII building blocks for ordinal builder
        self.ascii_d2_9 = d2_9
        self.ascii_e2 = e2

        # Digit-by-digit reading, e.g. "007" -> "ಸೊನ್ನೆ ಸೊನ್ನೆ ಏಳು"
        single_digit_graph = accept_kn_digits(digit | zero)
        self.single_digits_graph = (single_digit_graph + pynini.closure(insert_space + single_digit_graph)).optimize()

        graph_without_leading_zeros = accept_kn_digits(ascii_graph)
        self.graph_without_leading_zeros = graph_without_leading_zeros

        cardinal_with_leading_zeros = pynini.compose(
            NEMO_ALL_ZERO + pynini.closure(NEMO_ALL_DIGIT, 1), self.single_digits_graph
        )
        cardinal_with_leading_zeros = pynutil.add_weight(cardinal_with_leading_zeros, 0.5)

        # Digit-group separators: Indian (1,00,000) and Western (100,000) grouping.
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

        # Support negative sign: "-" and "−" (U+2212)
        minus_sym = pynini.union("-", "−")
        optional_minus_graph = pynini.closure(pynutil.insert("negative: ") + pynini.cross(minus_sym, "\"true\" "), 0, 1)

        # Serial codes: 1-3 digit groups read as cardinals, 4+ digits read digit-by-digit
        any_digit = pynini.union(NEMO_DIGIT, NEMO_ALL_DIGIT).optimize()
        digitwise_4plus = pynini.compose(any_digit**4 + pynini.closure(any_digit), self.single_digits_graph).optimize()
        self.code_num_graph = (single_digit_graph | self.up_to_999 | digitwise_4plus).optimize()

        self.final_graph = final_graph.optimize()
        self.attributive_graph = self.final_graph

        tagged_graph = optional_minus_graph + pynutil.insert("integer: \"") + self.final_graph + pynutil.insert("\"")
        tagged_graph = self.add_tokens(tagged_graph)
        self.fst = tagged_graph.optimize()
