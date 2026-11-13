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
    NEMO_CHAR,
    NEMO_SPACE,
    NEMO_WHITE_SPACE,
    TO_ASCII_DIGIT,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path

TE_PLUS = "ప్లస్"
MOBILE_START_DIGITS = pynini.union("6", "7", "8", "9", "౬", "౭", "౮", "౯").optimize()
ZERO_DIGIT = pynini.union("0", "౦").optimize()

digit_to_word = pynini.compose(TO_ASCII_DIGIT, pynini.string_file(get_abs_path("data/telephone/number.tsv"))).optimize()
credit_context = pynini.string_file(get_abs_path("data/telephone/credit_context.tsv"))
pincode_context = pynini.string_file(get_abs_path("data/telephone/pincode_context.tsv"))

# one digit read as a word, followed by a space
num_token = (digit_to_word + insert_space).optimize()
group_separator = pynini.union(pynutil.delete(" "), pynutil.delete("-"), pynutil.delete(".")).optimize()


def digits(n_min: int, n_max: int = None) -> pynini.Fst:
    """n_min..n_max digits read one by one, each followed by a space."""
    return pynini.closure(num_token, n_min, n_max if n_max is not None else n_min).optimize()


def grouped(total_min: int, total_max: int) -> pynini.Fst:
    """total_min..total_max digits, groups optionally separated by one space/-/. each."""
    sep = pynini.closure(pynini.union(" ", "-", "."), 0, 1)
    shape = NEMO_ALL_DIGIT + pynini.closure(sep + NEMO_ALL_DIGIT)
    shape = pynini.intersect(shape, _digit_count(total_min, total_max)).optimize()
    reader = pynini.closure(num_token | group_separator, 1)
    return pynini.compose(shape, reader).optimize()


def _digit_count(n_min: int, n_max: int) -> pynini.Fst:
    other = pynini.union(" ", "-", ".")
    one = pynini.closure(other) + NEMO_ALL_DIGIT
    return (pynini.closure(one, n_min, n_max) + pynini.closure(other)).optimize()


def get_context(keywords: pynini.Fst):
    non_digit_char = pynini.difference(NEMO_CHAR, pynini.union(NEMO_ALL_DIGIT, NEMO_WHITE_SPACE))
    word = pynini.closure(non_digit_char, 1) + pynini.accep(NEMO_SPACE)
    window = pynini.closure(word, 0, 5)
    before = pynini.closure(keywords + pynini.accep(NEMO_SPACE) + window, 0, 1)
    after = pynini.closure(pynutil.delete(NEMO_SPACE) + window + keywords, 0, 1)
    return before.optimize(), after.optimize()


def number_part(graph: pynini.Fst) -> pynini.Fst:
    return pynutil.insert("number_part: \"") + graph + pynutil.insert("\" ")


def generate_international() -> pynini.Fst:
    """+<country code> followed by 6-12 digits, optionally grouped: +91 98480 22338 -> ప్లస్ తొమ్మిది ఒకటి ..."""
    country_code = (
        pynutil.insert("country_code: \"")
        + pynini.cross("+", TE_PLUS)
        + insert_space
        + digits(1, 3)
        + pynutil.insert("\" ")
        + pynini.closure(pynutil.delete(pynini.union(" ", "-")), 0, 1)
    )
    return (country_code + number_part(grouped(6, 12))).optimize()


def generate_mobile() -> pynini.Fst:
    """Ten-digit Indian mobile numbers starting with 6-9, optionally with a leading 0 or grouped 5+5 / 3-3-4."""
    start = pynini.compose(MOBILE_START_DIGITS, digit_to_word) + insert_space
    leading_zero = pynini.closure(pynini.compose(ZERO_DIGIT, digit_to_word) + insert_space, 0, 1)
    plain = leading_zero + start + digits(9)
    split = pynini.compose(
        MOBILE_START_DIGITS + NEMO_ALL_DIGIT**4 + pynini.union(" ", "-") + NEMO_ALL_DIGIT**5,
        start + digits(4) + group_separator + digits(5),
    ) | pynini.compose(
        MOBILE_START_DIGITS + NEMO_ALL_DIGIT**2 + pynini.union(" ", "-") + NEMO_ALL_DIGIT**3 + pynini.union(" ", "-") + NEMO_ALL_DIGIT**4,
        start + digits(2) + group_separator + digits(3) + group_separator + digits(4),
    )
    return number_part(plain | split).optimize()


def generate_landline() -> pynini.Fst:
    """STD code starting with 0 (2-5 digits after it, optionally bracketed) + 6-8 digit subscriber number."""
    std = pynini.compose(ZERO_DIGIT, digit_to_word) + insert_space + digits(2, 5)
    std_in_brackets = pynutil.delete("(") + std + pynutil.delete(")") + pynini.closure(pynutil.delete(" "), 0, 1)
    std_sep = std + pynini.closure(group_separator, 0, 1)
    subscriber = digits(6, 8)
    graph = pynini.compose(
        pynini.intersect(_digit_count(10, 12), ZERO_DIGIT + pynini.closure(NEMO_ALL_DIGIT, 1) + pynini.closure(pynini.union(" ", "-", ".") + NEMO_ALL_DIGIT + pynini.closure(NEMO_ALL_DIGIT), 0, 1))
        | pynini.accep("(") + _digit_count(3, 6) + pynini.accep(")") + pynini.closure(" ", 0, 1) + _digit_count(6, 8),
        (std_sep | std_in_brackets) + subscriber,
    )
    return number_part(graph).optimize()


def generate_context(context_keywords: pynini.Fst, n_min: int) -> pynini.Fst:
    context_before, context_after = get_context(context_keywords)
    return number_part(context_before + digits(n_min, 19) + context_after).optimize() + delete_space


class TelephoneFst(GraphFst):
    """
    Finite state transducer for tagging telephone numbers (digits read one by one), e.g.
        9848022338 -> telephone { number_part: "తొమ్మిది ఎనిమిది నాలుగు ఎనిమిది సున్నా రెండు రెండు మూడు మూడు ఎనిమిది" }
        +91 98480 22338 -> telephone { country_code: "ప్లస్ తొమ్మిది ఒకటి" number_part: "తొమ్మిది ఎనిమిది ..." }
        040-23456789 -> telephone { number_part: "సున్నా నాలుగు సున్నా రెండు మూడు ..." }
    """

    def __init__(self):
        super().__init__(name="telephone", kind="classify")

        graph = (
            pynutil.add_weight(generate_international(), 0.7)
            # a bare ten-digit number starting with 6-9 is an Indian mobile number, not an amount
            | pynutil.add_weight(generate_mobile(), -0.2)
            | pynutil.add_weight(generate_landline(), 0.8)
            | pynutil.add_weight(generate_context(credit_context, 4), 0.9)
            | pynutil.add_weight(generate_context(pincode_context, 6), 1)
        )

        self.final = graph.optimize()
        self.fst = self.add_tokens(self.final)
