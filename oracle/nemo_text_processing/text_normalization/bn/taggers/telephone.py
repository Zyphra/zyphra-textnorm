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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.bn.graph_utils import (
    NEMO_ALL_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.bn.utils import get_abs_path

digit_to_word = pynini.string_file(get_abs_path("data/telephone/number.tsv"))
digits = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
zero = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))

# Reusable optimized graph for any digit token
num_token = pynini.union(digit_to_word, digits, zero).optimize()


def digit_run(min_len: int, max_len: int) -> pynini.Fst:
    """A run of min_len..max_len digits read one by one."""
    return (num_token + pynini.closure(insert_space + num_token, min_len - 1, max_len - 1)).optimize()


def grouped(total_min: int, total_max: int, first_min: int = 2) -> pynini.Fst:
    """Digit groups (2+ digits each, the first first_min+) separated by a space, hyphen or period, total_min..total_max
    digits."""
    separator = pynini.union(" ", "-", ".")
    group = pynini.closure(NEMO_ALL_DIGIT, 2)
    shape = pynini.closure(NEMO_ALL_DIGIT, first_min) + pynini.closure(separator + group)
    any_separators = pynini.closure(separator)
    counted = pynini.closure(any_separators + NEMO_ALL_DIGIT, total_min, total_max) + any_separators
    allowed = pynini.intersect(shape, counted)
    reader = num_token + pynini.closure((pynini.cross(separator, " ") | insert_space) + num_token)
    return pynini.compose(allowed, reader).optimize()


class TelephoneFst(GraphFst):
    """
    Finite state transducer for tagging telephone numbers, read digit by digit, e.g.
        ০১৭১২৩৪৫৬৭৮ -> telephone { number_part: "শূন্য এক সাত এক দুই তিন চার পাঁচ ছয় সাত আট" }
        +৮৮০ ১৭১২-৩৪৫৬৭৮ -> telephone { country_code: "প্লাস আট আট শূন্য" number_part: "এক সাত এক দুই তিন চার পাঁচ ছয় সাত আট" }
        (০২) ৯৮৭৬৫৪৩ -> telephone { number_part: "শূন্য দুই নয় আট সাত ছয় পাঁচ চার তিন" }
    """

    def __init__(self):
        super().__init__(name="telephone", kind="classify")

        zero_digit = pynini.union("0", "০")

        country_code = (
            pynutil.insert("country_code: \"")
            + pynini.cross("+", "প্লাস")
            + insert_space
            + digit_run(1, 3)
            + pynutil.insert("\" ")
            + pynini.closure(pynutil.delete(pynini.union(" ", "-")), 0, 1)
        )

        # after a country code the area code may be a single digit: +971 4 123 4567
        number_part_with_country = pynutil.insert("number_part: \"") + grouped(6, 12, 1) + pynutil.insert("\"")

        # National numbers start with 0: mobile 01XXXXXXXXX (11 digits), landline 0X..., written with optional groups
        national = pynini.compose(zero_digit + pynini.closure(NEMO_ALL_DIGIT | pynini.union(" ", "-", ".")), grouped(9, 11))
        number_part_national = pynutil.insert("number_part: \"") + national + pynutil.insert("\"")

        # Area code in brackets: (০২) ৯৮৭৬৫৪৩
        bracketed = (
            pynutil.insert("number_part: \"")
            + pynutil.delete("(")
            + pynini.compose(zero_digit + pynini.closure(NEMO_ALL_DIGIT, 1, 4), digit_run(2, 5))
            + pynutil.delete(")")
            + pynini.cross(pynini.closure(pynini.union(" ", "-"), 0, 1), " ")
            + grouped(5, 8)
            + pynutil.insert("\"")
        )

        graph = (
            (country_code + number_part_with_country)
            | number_part_national
            | bracketed
        )

        self.final = graph.optimize()
        self.fst = self.add_tokens(self.final)
