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
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_ALL_DIGIT,
    NEMO_OR_DIGIT,
    NORMALIZE_DIGIT,
    convert_space,
    insert_space,
    delete_space,
)

ODIA_CARDINALS_0_TO_99 = {
    0: "ଶୂନ୍ୟ", 1: "ଏକ", 2: "ଦୁଇ", 3: "ତିନି", 4: "ଚାରି", 5: "ପାଞ୍ଚ", 6: "ଛଅ", 7: "ସାତ", 8: "ଆଠ", 9: "ନଅ", 10: "ଦଶ",
    11: "ଏଗାର", 12: "ବାର", 13: "ତେର", 14: "ଚଉଦ", 15: "ପନ୍ଦର", 16: "ଷୋଳ", 17: "ସତର", 18: "ଅଠର", 19: "ଊଣେଇଶ", 20: "କୋଡ଼ିଏ",
    21: "ଏକୋଇଶ", 22: "ବାଇଶ", 23: "ତେଇଶ", 24: "ଚଉବିଶ", 25: "ପଚିଶ", 26: "ଛବିଶ", 27: "ସତାଇଶ", 28: "ଅଠାଇଶ", 29: "ଊଣାତିରିଶ", 30: "ତିରିଶ",
    31: "ଏକତିରିଶ", 32: "ବତିଶ", 33: "ତେତିଶ", 34: "ଚଉତିରିଶ", 35: "ପଞ୍ଚତିରିଶ", 36: "ଛତିଶ", 37: "ସତତିରିଶ", 38: "ଅଠତିରିଶ", 39: "ଊଣଚାଳିଶ", 40: "ଚାଳିଶ",
    41: "ଏକଚାଳିଶ", 42: "ବୟାଳିଶ", 43: "ତେତାଳିଶ", 44: "ଚଉରାଳିଶ", 45: "ପଞ୍ଚଚାଳିଶ", 46: "ଛେଚାଳିଶ", 47: "ସତଚାଳିଶ", 48: "ଅଠଚାଳିଶ", 49: "ଊଣପଚାଶ", 50: "ପଚାଶ",
    51: "ଏକାବନ", 52: "ବାବନ", 53: "ତେପନ", 54: "ଚଉବନ", 55: "ପଞ୍ଚାବନ", 56: "ଛପନ", 57: "ସତାବନ", 58: "ଅଠାବନ", 59: "ଊଣଷାଠିଏ", 60: "ଷାଠିଏ",
    61: "ଏକଷଠି", 62: "ବାଷଠି", 63: "ତେଷଠି", 64: "ଚଉଷଠି", 65: "ପଞ୍ଚଷଠି", 66: "ଛଅଷଠି", 67: "ସତଷଠି", 68: "ଅଠଷଠି", 69: "ଊଣସତୁରୀ", 70: "ସତୁରୀ",
    71: "ଏକସତୁରୀ", 72: "ବାସତୁରୀ", 73: "ତେସତୁରୀ", 74: "ଚଉସତୁରୀ", 75: "ପଞ୍ଚସତୁରୀ", 76: "ଛଅସତୁରୀ", 77: "ସତସତୁରୀ", 78: "ଅଠସତୁରୀ", 79: "ଊଣାଶୀ", 80: "ଅଶୀ",
    81: "ଏକାଶୀ", 82: "ବୟାଶୀ", 83: "ତେରାଶୀ", 84: "ଚଉରାଶୀ", 85: "ପଞ୍ଚାଶୀ", 86: "ଛିଆଶୀ", 87: "ସତାଶୀ", 88: "ଅଠାଶୀ", 89: "ଊଣାନବେ", 90: "ନବେ",
    91: "ଏକାନବେ", 92: "ବୟାନବେ", 93: "ତେରାନବେ", 94: "ଚଉରାନବେ", 95: "ପଞ୍ଚାନବେ", 96: "ଛିଆନବେ", 97: "ସତାନବେ", 98: "ଅଠାନବେ", 99: "ନିଆଁନବେ",
}

SINGLE_DIGITS = {str(i): ODIA_CARDINALS_0_TO_99[i] for i in range(10)}


def _build_core_cardinals():
    digit_map = pynini.string_map([(str(i), ODIA_CARDINALS_0_TO_99[i]) for i in range(1, 10)])
    zero_map = pynini.string_map([("0", "ଶୂନ୍ୟ")])
    teens_ties_map = pynini.string_map([(str(i), ODIA_CARDINALS_0_TO_99[i]) for i in range(10, 100)])

    num_1_99 = digit_map | teens_ties_map

    del_zero = pynutil.delete("0")
    ins_sp = pynutil.insert(" ")

    # Hundreds: 100 to 999
    # 100 -> ଶହେ
    h_100 = pynini.cross("100", "ଶହେ")
    # 101 to 109 -> ଏକ ଶହ <1-9>
    h_101_109 = pynutil.delete("1") + del_zero + pynutil.insert("ଏକ ଶହ ") + digit_map
    # 110 to 199 -> ଏକ ଶହ <10-99>
    h_110_199 = pynutil.delete("1") + pynutil.insert("ଏକ ଶହ ") + teens_ties_map

    # 200 to 900
    h_d00 = digit_map + pynutil.delete("00") + pynutil.insert(" ଶହ")
    # 201 to 909
    h_d0d = digit_map + pynutil.insert(" ଶହ ") + del_zero + digit_map
    # 210 to 999
    h_dtens = digit_map + pynutil.insert(" ଶହ ") + teens_ties_map

    hundreds = h_100 | h_101_109 | h_110_199 | h_d00 | h_d0d | h_dtens
    num_1_999 = (num_1_99 | hundreds).optimize()

    # Each scale consumes an exact-width remainder. Variable-width lower groups
    # would allow an ordinary lakh value to take a much larger crore path.
    lower = num_1_999
    for width, scale in ((3, "ହଜାର"), (5, "ଲକ୍ଷ"), (7, "କୋଟି"), (9, "ଅରବ"), (11, "ଖରବ")):
        remainder = pynutil.delete("0" * width)
        for zeros in range(width):
            significant = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, width - zeros - 1, width - zeros - 1)
            remainder |= pynutil.delete("0" * zeros) + ins_sp + (significant @ lower)
        scaled = num_1_99 + pynutil.insert(" " + scale) + remainder
        lower = (lower | scaled).optimize()
    all_pos = (zero_map | lower).optimize()
    return all_pos, zero_map, digit_map, num_1_99, num_1_999


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying cardinals in Odia:
        -୨୩ -> tokens { name: "ଋଣ ତେଇଶ" }
        ~୫୦ -> tokens { name: "ପ୍ରାୟ ପଚାଶ" }
        ±୫ -> tokens { name: "ପ୍ଲସ୍ ମାଇନସ୍ ପାଞ୍ଚ" }
        ୨ଟି -> tokens { name: "ଦୁଇଟି" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        all_pos, zero_map, digit_map, num_1_99, num_1_999 = _build_core_cardinals()

        self.zero = zero_map
        self.digit = digit_map
        self.num_1_99 = num_1_99
        self.num_1_999 = num_1_999

        # Accept complete Western or Indian digit groups, never arbitrary
        # punctuation deletion that changes a decimal into an integer.
        digit = NEMO_ALL_DIGIT
        nonzero = pynini.difference(digit, pynini.union("0", "୦"))
        separator = pynutil.delete(pynini.union(",", " "))
        western = nonzero + pynini.closure(digit, 0, 2) + pynini.closure(separator + digit**3, 1)
        indian = nonzero + pynini.closure(digit, 0, 1) + pynini.closure(separator + digit**2) + separator + digit**3
        self.grouped_numbers = pynini.project(western | indian, "input").optimize()
        normalized = pynini.closure(NORMALIZE_DIGIT, 1)
        cardinal_core = ((normalized | ((western | indian) @ normalized)) @ all_pos).optimize()
        self.cardinal_numbers = cardinal_core

        # Single-digit serial reading (e.g. "୦୭୩" -> "ଶୂନ୍ୟ ସାତ ତିନି")
        single_digit_word = pynini.string_map([(k, v) for k, v in SINGLE_DIGITS.items()])
        single_digit_trans = (NORMALIZE_DIGIT @ single_digit_word).optimize()
        self.single_digits = (
            single_digit_trans + pynini.closure(pynutil.insert(" ") + single_digit_trans)
        ).optimize()

        # Leading-zero numbers: read digit-by-digit
        leading_zero = pynini.union("0", "୦")
        leading_zero_graph = leading_zero + pynini.closure(NEMO_ALL_DIGIT, 1)
        self.leading_zeros = (leading_zero_graph @ self.single_digits).optimize()

        # Classifier suffixes in Odia:
        # ୨ଟି -> ଦୁଇଟି, ୩ଟି -> ତିନିଟି, ୫ଟି -> ପାଞ୍ଚଟି, ୨ଟା -> ଦୁଇଟା, ୩ଜଣ -> ତିନି ଜଣ, ୨ଖଣ୍ଡ -> ଦୁଇ ଖଣ୍ଡ
        classifier_glued = pynini.union(
            pynini.cross("ଟି", "ଟି"),
            pynini.cross("ଟା", "ଟା"),
            pynini.cross("ଜଣ", " ଜଣ"),
            pynini.cross("ଖଣ୍ଡ", " ଖଣ୍ଡ"),
        )
        classified_numbers = (cardinal_core + classifier_glued).optimize()

        # Negative numbers
        neg_prefix = pynini.cross("-", "ଋଣ ") | pynini.cross("−", "ଋଣ ")
        neg_cardinal = (neg_prefix + cardinal_core).optimize()

        # Approximate (~) and Plus-Minus (±)
        approx_prefix = pynini.cross("~", "ପ୍ରାୟ ")
        pm_prefix = pynini.cross("±", "ପ୍ଲସ୍ ମାଇନସ୍ ")

        approx_cardinal = (approx_prefix + (cardinal_core | classified_numbers)).optimize()
        pm_cardinal = (pm_prefix + (cardinal_core | classified_numbers)).optimize()
        number_range = (
            cardinal_core + pynini.cross(pynini.union("-", "–", "—"), " ରୁ ") + cardinal_core
        )

        # Complete cardinal graph
        all_cardinals = (
            pynutil.add_weight(self.leading_zeros, -0.05)
            | pynutil.add_weight(cardinal_core, 0.0)
            | pynutil.add_weight(classified_numbers, -0.1)
            | pynutil.add_weight(neg_cardinal, -0.1)
            | pynutil.add_weight(approx_cardinal, -0.1)
            | number_range
            | pynutil.add_weight(pm_cardinal, -0.1)
        ).optimize()

        self.all_nums_no_tokens = all_cardinals

        graph = pynutil.insert('name: "') + convert_space(all_cardinals) + pynutil.insert('"')
        self.fst = graph.optimize()
