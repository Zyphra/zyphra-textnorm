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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_NON_ZERO,
    NEMO_ALL_ZERO,
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_ML_CHAR,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path

# Combining and exact magnitude forms per CLDR ml %spellout-cardinal:
HUNDRED = "നൂറ്"
HUNDRED_COMBINING = "നൂറ്റി "
THOUSAND_ONE = "ആയിരം"
THOUSAND_COMBINING = "ആയിരത്തി "
LAKH_ONE = "ഒരു ലക്ഷം"
LAKH_COMBINING = "ഒരു ലക്ഷത്തി "
LAKHS = "ലക്ഷം"
LAKHS_COMBINING = "ലക്ഷത്തി "
CRORE_ONE = "ഒരു കോടി"
CRORE_COMBINING = "ഒരു കോടി "
CRORES = "കോടി"
CRORES_COMBINING = "കോടി "
ARAB_ONE = "ഒരു അറബ്"
ARAB = "അറബ്"
KHARAB_ONE = "ഒരു ഖറബ്"
KHARAB = "ഖറബ്"


def _rest(lower: 'pynini.FstLike', exact: 'pynini.FstLike') -> 'pynini.FstLike':
    """Non-zero k-digit string that may start with zeros: zero dropped and rest read as k-1 digits."""
    return (pynutil.delete("0") + lower | exact).optimize()


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Malayalam cardinals (ASCII and Malayalam digits), e.g.
        -45 -> cardinal { negative: "true" integer: "നാൽപ്പത്തിയഞ്ച്" }
        201 -> cardinal { integer: "ഇരുനൂറ്റി ഒന്ന്" }
        1,00,000 -> cardinal { integer: "ഒരു ലക്ഷം" }

    Args:
        deterministic: if True will provide a single transduction option
    """

    def __init__(self, deterministic: bool = True):
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

        hundred_exact = pynini.string_map([
            ("1", "നൂറ്"),
            ("2", "ഇരുനൂറ്"),
            ("3", "മുന്നൂറ്"),
            ("4", "നാന്നൂറ്"),
            ("5", "അഞ്ഞൂറ്"),
            ("6", "അറുന്നൂറ്"),
            ("7", "എഴുന്നൂറ്"),
            ("8", "എണ്ണൂറ്"),
            ("9", "തൊള്ളായിരം"),
        ])

        hundred_combining = pynini.string_map([
            ("1", "നൂറ്റി "),
            ("2", "ഇരുനൂറ്റി "),
            ("3", "മുന്നൂറ്റി "),
            ("4", "നാന്നൂറ്റി "),
            ("5", "അഞ്ഞൂറ്റി "),
            ("6", "അറുന്നൂറ്റി "),
            ("7", "എഴുന്നൂറ്റി "),
            ("8", "എണ്ണൂറ്റി "),
            ("9", "തൊള്ളായിരത്തി "),
        ])

        e3 = (
            hundred_exact + pynutil.delete("00")
            | hundred_combining + r2
        ).optimize()
        r3 = _rest(r2, e3)

        # 4 digits: 1,000 to 9,999
        th_1_exact = pynini.cross("1000", THOUSAND_ONE)
        th_1_comb = pynutil.delete("1") + pynutil.insert(THOUSAND_COMBINING) + r3

        th_digit_exact = pynini.string_map([
            ("2", "രണ്ടായിരം"),
            ("3", "മൂന്നായിരം"),
            ("4", "നാലായിരം"),
            ("5", "അഞ്ചായിരം"),
            ("6", "ആറായിരം"),
            ("7", "ഏഴായിരം"),
            ("8", "എട്ടായിരം"),
            ("9", "ഒൻപതിനായിരം"),
        ])

        th_digit_comb = pynini.string_map([
            ("2", "രണ്ടായിരത്തി "),
            ("3", "മൂന്നായിരത്തി "),
            ("4", "നാലായിരത്തി "),
            ("5", "അഞ്ചായിരത്തി "),
            ("6", "ആറായിരത്തി "),
            ("7", "ഏഴായിരത്തി "),
            ("8", "എട്ടായിരത്തി "),
            ("9", "ഒൻപതിനായിരത്തി "),
        ])

        e4 = (
            th_1_exact
            | th_1_comb
            | th_digit_exact + pynutil.delete("000")
            | th_digit_comb + r3
        ).optimize()
        r4 = _rest(r3, e4)

        # 5 digits: 10,000 to 99,999
        head_th_2_exact = e2 + pynutil.insert(" ആയിരം")
        head_th_2_comb = e2 + pynutil.insert(" ആയിരത്തി ")
        e5 = (
            head_th_2_exact + pynutil.delete("000")
            | head_th_2_comb + r3
        ).optimize()
        r5 = _rest(r4, e5)

        # 6 digits: 1,00,000 to 9,99,999 (Lakhs)
        head_l_1 = (
            pynini.cross("1", LAKH_ONE) + pynutil.delete("00000")
            | pynutil.delete("1") + pynutil.insert(LAKH_COMBINING) + r5
        )
        head_l_single = (
            d2_9 + pynutil.insert(" " + LAKHS) + pynutil.delete("00000")
            | d2_9 + pynutil.insert(" " + LAKHS_COMBINING) + r5
        )
        e6 = (head_l_1 | head_l_single).optimize()
        r6 = _rest(r5, e6)

        # 7 digits: 10,00,000 to 99,99,999
        head_l_double = (
            e2 + pynutil.insert(" " + LAKHS) + pynutil.delete("00000")
            | e2 + pynutil.insert(" " + LAKHS_COMBINING) + r5
        )
        e7 = head_l_double.optimize()
        r7 = _rest(r6, e7)

        # 8 digits: 1,00,00,000 to 9,99,99,999 (Crores)
        head_c_1 = (
            pynini.cross("1", CRORE_ONE) + pynutil.delete("0000000")
            | pynutil.delete("1") + pynutil.insert(CRORE_COMBINING) + r7
        )
        head_c_single = (
            d2_9 + pynutil.insert(" " + CRORES) + pynutil.delete("0000000")
            | d2_9 + pynutil.insert(" " + CRORES_COMBINING) + r7
        )
        e8 = (head_c_1 | head_c_single).optimize()
        r8 = _rest(r7, e8)

        # 9 digits: 10,00,00,000 to 99,99,99,999
        head_c_double = (
            e2 + pynutil.insert(" " + CRORES) + pynutil.delete("0000000")
            | e2 + pynutil.insert(" " + CRORES_COMBINING) + r7
        )
        e9 = head_c_double.optimize()
        r9 = _rest(r8, e9)

        # 10 digits: 1,00,00,00,000 to 9,99,99,99,999 (Arab)
        head_a_1 = (
            pynini.cross("1", ARAB_ONE) + pynutil.delete("000000000")
            | pynutil.delete("1") + pynutil.insert("ഒരു അറബ് ") + r9
        )
        head_a_single = (
            d2_9 + pynutil.insert(" " + ARAB) + pynutil.delete("000000000")
            | d2_9 + pynutil.insert(" " + ARAB + " ") + r9
        )
        e10 = (head_a_1 | head_a_single).optimize()
        r10 = _rest(r9, e10)

        # 11 digits: 10,00,00,00,000 to 99,99,99,99,999
        head_a_double = (
            e2 + pynutil.insert(" " + ARAB) + pynutil.delete("000000000")
            | e2 + pynutil.insert(" " + ARAB + " ") + r9
        )
        e11 = head_a_double.optimize()
        r11 = _rest(r10, e11)

        # Kharab (10^11 and beyond)
        up_to_7_without_one = pynini.union(d2_9, e2, e3, e4, e5, e6, e7).optimize()
        head_k = (
            pynini.cross("1", KHARAB_ONE) + pynutil.delete("0" * 11)
            | pynutil.delete("1") + pynutil.insert("ഒരു ഖറബ് ") + r11
            | up_to_7_without_one + pynutil.insert(" " + KHARAB) + pynutil.delete("0" * 11)
            | up_to_7_without_one + pynutil.insert(" " + KHARAB + " ") + r11
        )
        e12_18 = head_k.optimize()

        ascii_graph = pynini.union(
            pynini.cross("0", "പൂജ്യം"), d1, e2, e3, e4, e5, e6, e7, e8, e9, e10, e11, e12_18
        ).optimize()

        def accept_ml_digits(graph):
            return pynini.compose(to_ascii, graph).optimize()

        self.digit = digit
        self.zero = zero
        self.teens_and_ties = accept_ml_digits(e2)
        self.graph_hundreds = accept_ml_digits(e3)
        self.graph_thousands = accept_ml_digits(e4 | e5)
        self.up_to_999 = accept_ml_digits(d1 | e2 | e3)
        self.ascii_d2_9 = d2_9
        self.ascii_e2 = e2

        # Digit-by-digit reading, e.g. "007" -> "പൂജ്യം പൂജ്യം ഏഴ്"
        single_digit_graph = digit | zero
        self.single_digits_graph = (single_digit_graph + pynini.closure(insert_space + single_digit_graph)).optimize()

        graph_without_leading_zeros = accept_ml_digits(ascii_graph)
        self.graph_without_leading_zeros = graph_without_leading_zeros

        cardinal_with_leading_zeros = pynini.compose(
            NEMO_ALL_ZERO + pynini.closure(NEMO_ALL_DIGIT, 1), self.single_digits_graph
        )
        cardinal_with_leading_zeros = pynutil.add_weight(cardinal_with_leading_zeros, 0.5)

        # Digit-group separators: Indian (1,00,000) and western (100,000) grouping
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

        # Support ASCII '-' and Unicode '−' (U+2212)
        minus_char = pynini.union("-", "−")
        optional_minus_graph = pynini.closure(pynutil.insert("negative: ") + pynini.cross(minus_char, "\"true\" "), 0, 1)

        # Attributive form for counted nouns (money, units): 1 -> ഒരു (₹1 -> ഒരു രൂപ, 1 kg -> ഒരു കിലോഗ്രാം)
        attributive = pynini.cdrewrite(
            pynini.cross("ഒന്ന്", "ഒരു"),
            pynini.union("[BOS]", " "),
            "[EOS]",
            NEMO_SIGMA,
        )
        self.attributive_graph = pynini.compose(final_graph, attributive).optimize()

        # Serial codes: 1-3 digit groups read as cardinal, 4+ digits read digit-by-digit
        any_digit = pynini.union(NEMO_DIGIT, NEMO_ALL_DIGIT).optimize()
        digitwise_4plus = pynini.compose(any_digit**4 + pynini.closure(any_digit), self.single_digits_graph).optimize()
        self.code_num_graph = (single_digit_graph | self.up_to_999 | digitwise_4plus).optimize()

        # Ranges: 5-10, 2020-2024 -> 5 മുതൽ 10 വരെ
        dash = pynini.union("-", "–", "—")
        range_graph = (
            final_graph
            + pynini.cross(dash, " മുതൽ ")
            + final_graph
            + pynutil.insert(" വരെ")
        ).optimize()
        self.range_graph = range_graph

        self.final_graph = final_graph.optimize()
        graph_with_integer = optional_minus_graph + pynutil.insert("integer: \"") + self.final_graph + pynutil.insert("\"")
        self.fst = self.add_tokens(graph_with_integer).optimize()

        # Serial / alphanum graph (e.g. B-60, A12, COVID-19, FY2024)
        alpha_chunk = pynini.closure(NEMO_ALPHA | NEMO_ML_CHAR, 1)
        sep_chars = pynini.union("-", "_", "/")
        spaced = (
            pynini.cdrewrite(pynutil.insert(" "), alpha_chunk, any_digit, NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.insert(" "), any_digit, alpha_chunk, NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross(sep_chars, " "), "", "", NEMO_SIGMA)
        )
        piece = alpha_chunk | self.code_num_graph
        pieces = piece + pynini.closure(pynini.accep(" ") + piece)
        alphanum = pynini.compose(spaced, pieces).optimize()
        self.serial = self.add_tokens(pynutil.insert('integer: "') + alphanum + pynutil.insert('"')).optimize()
