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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone_token
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_CHAR,
    NEMO_WHITE_SPACE,
    TO_ASCII_DIGIT,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path

KN_PLUS = "ಪ್ಲಸ್"
MOBILE_START_DIGITS = pynini.union("6", "7", "8", "9", "೬", "೭", "೮", "೯").optimize()
ZERO_DIGIT = pynini.union("0", "೦").optimize()

digit_to_word = pynini.compose(TO_ASCII_DIGIT, pynini.string_file(get_abs_path("data/telephone/number.tsv"))).optimize()
credit_context = pynini.string_file(get_abs_path("data/telephone/credit_context.tsv"))
pincode_context = pynini.string_file(get_abs_path("data/telephone/pincode_context.tsv"))

num_token = (digit_to_word + insert_space).optimize()
group_separator = pynini.union(pynutil.delete(" "), pynutil.delete("-"), pynutil.delete(".")).optimize()


def digits(n_min: int, n_max: int = None) -> pynini.Fst:
    return pynini.closure(num_token, n_min, n_max if n_max is not None else n_min).optimize()


def grouped(total_min: int, total_max: int) -> pynini.Fst:
    other = pynini.union(" ", "-", ".")
    shape = pynini.closure(other) + pynini.closure(NEMO_ALL_DIGIT + pynini.closure(other), total_min, total_max)
    reader = pynini.closure(pynini.union(num_token, pynutil.delete(group_separator))).optimize()
    return pynini.compose(shape, reader).optimize()


def _digit_count(n_min: int, n_max: int) -> pynini.Fst:
    other = pynini.union(" ", "-", ".")
    one = pynini.closure(other) + NEMO_ALL_DIGIT
    return (pynini.closure(one, n_min, n_max) + pynini.closure(other)).optimize()


def get_context(keywords: pynini.Fst):
    non_digit_char = pynini.difference(NEMO_CHAR, pynini.union(NEMO_ALL_DIGIT, NEMO_WHITE_SPACE))
    sep = pynini.closure(pynini.union(" ", ":", "-"), 1)
    before = pynini.closure(non_digit_char) + keywords + sep
    after = sep + keywords + pynini.closure(non_digit_char)
    return before.optimize(), after.optimize()


def number_part(graph: pynini.Fst) -> pynini.Fst:
    return pynutil.insert("number_part: \"") + graph + pynutil.insert("\" ")


def generate_international() -> pynini.Fst:
    country_code = (
        pynutil.insert("country_code: \"")
        + pynini.cross("+", KN_PLUS + " ")
        + digits(1, 3)
        + pynutil.insert("\" ")
        + pynini.closure(pynutil.delete(group_separator), 0, 1)
    ).optimize()
    return (country_code + number_part(grouped(6, 12))).optimize()


def generate_mobile() -> pynini.Fst:
    leading_zero = pynini.closure(pynini.compose(ZERO_DIGIT, digit_to_word) + insert_space, 0, 1)
    first = pynini.compose(MOBILE_START_DIGITS, num_token)
    rest9 = digits(9)

    plain = leading_zero + first + rest9

    split = (
        leading_zero
        + first
        + digits(4)
        + group_separator
        + digits(5)
        | leading_zero
        + first
        + digits(2)
        + group_separator
        + digits(3)
        + group_separator
        + digits(4)
    )
    return number_part(plain | split).optimize()


def generate_landline() -> pynini.Fst:
    std = (
        pynini.compose(ZERO_DIGIT, num_token)
        + digits(1, 4)
        | pynutil.delete("(") + pynini.compose(ZERO_DIGIT, num_token) + digits(1, 4) + pynutil.delete(")")
    )
    subscriber = digits(6, 8)
    graph = std + group_separator + subscriber
    return number_part(graph).optimize()


def generate_context(context_keywords: pynini.Fst, n_min: int) -> pynini.Fst:
    context_before, context_after = get_context(context_keywords)
    reader = digit_to_word + pynini.closure(insert_space + digit_to_word, n_min - 1, 18)
    return number_part(context_before + reader | reader + context_after).optimize() + delete_space


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying telephone numbers.
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        international = generate_international()
        mobile = generate_mobile()
        landline = generate_landline()
        credit = generate_context(credit_context, 16)
        pincode = generate_context(pincode_context, 6)

        final = international | pynutil.add_weight(mobile, -0.2) | landline | credit | pincode
        self.final = final.optimize()
        self.fst = (self.add_tokens(self.final) | international_telephone_token(digit_to_word, KN_PLUS)).optimize()
