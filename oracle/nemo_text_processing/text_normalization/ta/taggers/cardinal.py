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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_ZERO,
    NEMO_DIGIT,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path

# CLDR ta %spellout-numbering and sandhi
HUNDRED = "நூறு"
HUNDREDS_COMB = "நூற்று"
THOUSAND_ONE = "ஆயிரம்"
THOUSANDS_COMB = "ஆயிரத்து"
LAKH_ONE = "ஒரு லட்சம்"
LAKHS_COMB = "லட்சத்து"
CRORE_ONE = "ஒரு கோடி"
CRORES_COMB = "கோடியே"
ARAB = "அரபம்"
KHARAB = "கரபம்"

# Prefixes for 2..99 from CLDR %%spellout-prefix
_PREFIX_MAP = {
    1: "ஒன்ற", 2: "இரண்ட", 3: "மூன்ற", 4: "நான்க", 5: "ஐந்த",
    6: "ஆற", 7: "ஏழ", 8: "எட்ட", 9: "ஒன்பத", 10: "பத்த",
    11: "பதினொன்ற", 12: "பன்னிரண்ட", 13: "பதின்மூன்ற", 14: "பதினான்க",
    15: "பதினைந்த", 16: "பதினாற", 17: "பதினேழ", 18: "பதினெட்ட", 19: "பத்தொன்பத",
}
for tens_val, tens_name in [(20, "இருப"), (30, "முப்ப"), (40, "நாற்ப"), (50, "ஐம்ப"),
                            (60, "அறுப"), (70, "எழுப"), (80, "எண்ப")]:
    _PREFIX_MAP[tens_val] = tens_name + "த"
    for unit_val in range(1, 10):
        _PREFIX_MAP[tens_val + unit_val] = tens_name + "த்து " + _PREFIX_MAP[unit_val]
_PREFIX_MAP[90] = "தொண்ணூற"
for unit_val in range(1, 10):
    _PREFIX_MAP[90 + unit_val] = "தொண்ணூற்று " + _PREFIX_MAP[unit_val]


def _rest(lower: 'pynini.FstLike', exact: 'pynini.FstLike') -> 'pynini.FstLike':
    """Non-zero k-digit string that may start with zeros: a zero is dropped and the rest read as k-1 digits."""
    return (pynutil.delete("0") + lower | exact).optimize()


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Tamil cardinals (ASCII and Tamil digits), e.g.
        -23 -> cardinal { negative: "true" integer: "இருபத்து மூன்று" }
        201 -> cardinal { integer: "இருநூற்று ஒன்று" }
        1,00,000 -> cardinal { integer: "ஒரு லட்சம்" }

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

        # Hundreds (100 - 999)
        hundreds_exact = {
            100: "நூறு",
            200: "இருநூறு",
            300: "முந்நூறு",
            400: "நானூறு",
            500: "ஐநூறு",
            600: "அறுநூறு",
            700: "எழுநூறு",
            800: "எண்நூறு",
            900: "தொள்ளாயிரம்",
        }
        hundreds_comb = {
            1: "நூற்று ",
            2: "இருநூற்று ",
            3: "முந்நூற்று ",
            4: "நானூற்று ",
            5: "ஐநூற்று ",
            6: "அறுநூற்று ",
            7: "எழுநூற்று ",
            8: "எண்நூற்று ",
            9: "தொள்ளாயிரத்து ",
        }

        h_exact_list = [pynini.cross(str(h), word) for h, word in hundreds_exact.items()]
        h_comb_list = [pynutil.delete(str(d)) + pynutil.insert(prefix) + r2 for d, prefix in hundreds_comb.items()]

        e3 = pynini.union(*h_exact_list, *h_comb_list).optimize()
        r3 = _rest(r2, e3)

        # Thousands (1,000 - 99,999) using CLDR prefix combining rules
        th_exact_1_list = [(str(i), _PREFIX_MAP[i] + "ாயிரம்") for i in range(2, 10)]
        th_comb_1_list = [(str(i), _PREFIX_MAP[i] + "ாயிரத்து ") for i in range(2, 10)]
        th_exact_2_list = [(str(i), _PREFIX_MAP[i] + "ாயிரம்") for i in range(10, 100)]
        th_comb_2_list = [(str(i), _PREFIX_MAP[i] + "ாயிரத்து ") for i in range(10, 100)]

        th_exact_1 = pynini.string_map(th_exact_1_list).optimize()
        th_comb_1 = pynini.string_map(th_comb_1_list).optimize()
        th_exact_2 = pynini.string_map(th_exact_2_list).optimize()
        th_comb_2 = pynini.string_map(th_comb_2_list).optimize()

        e4 = (
            pynini.cross("1000", THOUSAND_ONE)
            | pynutil.delete("1") + pynutil.insert(THOUSANDS_COMB + " ") + r3
            | th_exact_1 + pynutil.delete("000")
            | th_comb_1 + r3
        ).optimize()

        e5 = (
            th_exact_2 + pynutil.delete("000")
            | th_comb_2 + r3
        ).optimize()

        r4 = _rest(r3, e4)
        r5 = _rest(r4, e5)

        # Lakhs (1,00,000 - 99,99,999)
        def magnitude(head_exact, head_comb, zeros: int, rest):
            return (head_exact + pynutil.delete("0" * zeros) | head_comb + rest).optimize()

        head_l_1_exact = pynini.cross("1", LAKH_ONE)
        head_l_1_comb = pynutil.delete("1") + pynutil.insert("ஒரு " + LAKHS_COMB + " ")
        head_l_2_exact = d2_9 + pynutil.insert(" லட்சம்")
        head_l_2_comb = d2_9 + pynutil.insert(" லட்சத்து ")
        head_l_ties_exact = e2 + pynutil.insert(" லட்சம்")
        head_l_ties_comb = e2 + pynutil.insert(" லட்சத்து ")

        e6 = (magnitude(head_l_1_exact, head_l_1_comb, 5, r5) | magnitude(head_l_2_exact, head_l_2_comb, 5, r5)).optimize()
        e7 = magnitude(head_l_ties_exact, head_l_ties_comb, 5, r5)
        r6 = _rest(r5, e6)
        r7 = _rest(r6, e7)

        # Crores (1,00,00,000 - 99,99,99,999)
        head_c_1_exact = pynini.cross("1", CRORE_ONE)
        head_c_1_comb = pynutil.delete("1") + pynutil.insert(CRORE_ONE + "யே ")
        head_c_2_exact = d2_9 + pynutil.insert(" கோடி")
        head_c_2_comb = d2_9 + pynutil.insert(" கோடியே ")
        head_c_ties_exact = e2 + pynutil.insert(" கோடி")
        head_c_ties_comb = e2 + pynutil.insert(" கோடியே ")

        e8 = (magnitude(head_c_1_exact, head_c_1_comb, 7, r7) | magnitude(head_c_2_exact, head_c_2_comb, 7, r7)).optimize()
        e9 = magnitude(head_c_ties_exact, head_c_ties_comb, 7, r7)
        r8 = _rest(r7, e8)
        r9 = _rest(r8, e9)

        # Arab (1,00,00,00,000 - 99,99,99,99,999)
        head_a_1 = pynini.cross("1", "ஒரு " + ARAB)
        head_a_1_comb = pynutil.delete("1") + pynutil.insert("ஒரு " + ARAB + "த்து ")
        head_a_2 = d2_9 + pynutil.insert(" " + ARAB)
        head_a_2_comb = d2_9 + pynutil.insert(" " + ARAB + "த்து ")
        head_a_ties = e2 + pynutil.insert(" " + ARAB)
        head_a_ties_comb = e2 + pynutil.insert(" " + ARAB + "த்து ")

        e10 = (magnitude(head_a_1, head_a_1_comb, 9, r9) | magnitude(head_a_2, head_a_2_comb, 9, r9)).optimize()
        e11 = magnitude(head_a_ties, head_a_ties_comb, 9, r9)
        r10 = _rest(r9, e10)
        r11 = _rest(r10, e11)

        # Kharab (1,00,00,00,00,000)
        up_to_7_without_one = pynini.union(d2_9, e2, e3, e4, e5, e6, e7).optimize()
        head_k = pynini.cross("1", "ஒரு " + KHARAB) | up_to_7_without_one + pynutil.insert(" " + KHARAB)
        e12_18 = (head_k + (pynutil.delete("0" * 11) | insert_space + r11)).optimize()

        ascii_graph = pynini.union(
            pynini.cross("0", "பூஜ்யம்"), d1, e2, e3, e4, e5, e6, e7, e8, e9, e10, e11, e12_18
        ).optimize()

        def accept_ta_digits(graph):
            return pynini.compose(to_ascii, graph).optimize()

        self.digit = digit
        self.zero = zero
        self.teens_and_ties = accept_ta_digits(e2)
        self.graph_hundreds = accept_ta_digits(e3)
        self.graph_thousands = accept_ta_digits(e4 | e5)
        # 1-999 without leading zeros, used by time, date, ordinal and serial graphs
        self.up_to_999 = accept_ta_digits(d1 | e2 | e3)
        # ASCII building blocks for ordinal builder
        self.ascii_d2_9 = d2_9
        self.ascii_e2 = e2

        # Digit-by-digit reading, e.g. "007" -> "பூஜ்யம் பூஜ்யம் ஏழு"
        single_digit_graph = accept_ta_digits(digit | zero)
        self.single_digits_graph = (single_digit_graph + pynini.closure(insert_space + single_digit_graph)).optimize()

        graph_without_leading_zeros = accept_ta_digits(ascii_graph)
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

        # Attributive form for a number directly before a counted noun (money, measure units):
        # 1 -> ஒரு (1 rupee = ஒரு ரூபாய், 1 kg = ஒரு கிலோகிராம், 21 rupees = இருபத்து ஒரு ரூபாய்),
        # 11 -> பதினொரு (11 rupees = பதினொரு ரூபாய்).
        attributive = pynini.cdrewrite(
            pynini.cross("ஒன்று", "ஒரு"), pynini.union("[BOS]", " "), "[EOS]", NEMO_SIGMA
        ) @ pynini.cdrewrite(
            pynini.cross("பதினொன்று", "பதினொரு"), pynini.union("[BOS]", " "), "[EOS]", NEMO_SIGMA
        )
        self.attributive_graph = pynini.compose(self.final_graph, attributive).optimize()
        final_graph = optional_minus_graph + pynutil.insert("integer: \"") + self.final_graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
