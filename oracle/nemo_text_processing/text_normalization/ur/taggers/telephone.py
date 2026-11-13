# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ur.graph_utils import (
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SPACE,
    NEMO_WHITE_SPACE,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ur.utils import get_abs_path

ZERO_DIGIT = pynini.accep("0")
# Pakistani mobile numbers are 03xx-xxxxxxx: the digit after the trunk zero is 3.
MOBILE_START_DIGITS = pynini.accep("3")
LANDLINE_START_DIGITS = pynini.union("2", "3", "4", "5", "6", "7", "8", "9").optimize()

delete_zero = pynutil.delete(ZERO_DIGIT)
delete_zero_optional = pynini.closure(delete_zero, 0, 1)
insert_shunya = pynutil.insert('صفر') + insert_space

# Load the number mappings from the TSV file
digit_to_word = pynini.string_file(get_abs_path("data/telephone/number.tsv"))
digits = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
zero = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))
mobile_context = pynini.string_file(get_abs_path("data/telephone/mobile_context.tsv"))
landline_context = pynini.string_file(get_abs_path("data/telephone/landline_context.tsv"))
credit_context = pynini.string_file(get_abs_path("data/telephone/credit_context.tsv"))
pincode_context = pynini.string_file(get_abs_path("data/telephone/pincode_context.tsv"))

# Reusable optimized graph for any digit token
num_token = pynini.union(digit_to_word, digits, zero).optimize()


def generate_mobile(context_keywords: pynini.Fst) -> pynini.Fst:
    context_before, context_after = get_context(context_keywords)

    # Filter cardinals to only include allowed digits
    mobile_start_digit = pynini.union(MOBILE_START_DIGITS @ digits, MOBILE_START_DIGITS @ digit_to_word)

    country_code_digits = pynini.closure(num_token + insert_space, 1, 3)
    country_code = (
        pynutil.insert("country_code: \"")
        + context_before
        + pynini.cross("+", "پلس")
        + insert_space
        + country_code_digits
        + pynutil.insert("\" ")
        + pynini.closure(delete_space, 0, 1)
    )

    extension_optional = pynini.closure(
        pynutil.insert("extension: \"")
        + pynini.closure(num_token + insert_space, 1, 3)
        + context_after
        + pynutil.insert("\" ")
        + delete_space,
        0,
        1,
    )

    # 3xx followed by seven digits, optionally grouped as "3xx-xxxxxxx", "3xx xxxxxxx" or "3xx.xxxxxxx"
    group_separator = pynini.closure(pynutil.delete(pynini.union("-", " ", ".")), 0, 1)
    number_part = (
        mobile_start_digit
        + insert_space
        + pynini.closure(num_token + insert_space, 2, 2)
        + group_separator
        + pynini.closure(num_token + insert_space, 7)
    )

    number_without_country = (
        pynutil.insert("number_part: \"")
        + context_before
        + delete_zero_optional
        + insert_shunya
        + number_part
        + context_after
        + pynutil.insert("\" ")
        + delete_space
    )

    number_with_country = (
        country_code
        + pynutil.insert("number_part: \"")
        + number_part
        + context_after
        + pynutil.insert("\" ")
        + delete_space
    )

    return (pynini.union(number_with_country, number_without_country) + extension_optional).optimize()


def get_landline(std_length: int, context_keywords: pynini.Fst) -> pynini.Fst:
    context_before, context_after = get_context(context_keywords)

    # Filter cardinals to only include allowed digits
    landline_start_digit = pynini.union(LANDLINE_START_DIGITS @ digits, LANDLINE_START_DIGITS @ digit_to_word)

    std_code_graph = (
        delete_zero_optional + insert_shunya + pynini.closure(num_token + insert_space, std_length, std_length)
    )

    # Pakistani local numbers have seven or eight digits after the area code.
    landline_digit_count = 9 - std_length
    landline_graph = (
        landline_start_digit
        + insert_space
        + pynini.closure(num_token + insert_space, landline_digit_count, landline_digit_count + 1)
    )

    separator_optional = pynini.closure(pynini.union(pynini.cross("-", ""), pynini.cross(".", "")), 0, 1)

    std_code_in_brackets = (
        delete_zero_optional
        + delete_space
        + pynutil.delete("(")
        + pynini.closure(delete_space, 0, 1)
        + std_code_graph
        + pynini.closure(delete_space, 0, 1)
        + pynutil.delete(")")
    )

    std_part = pynini.union(std_code_graph, std_code_in_brackets)

    return (
        pynutil.insert("number_part: \"")
        + context_before
        + std_part
        + separator_optional
        + delete_space
        + landline_graph
        + context_after
        + pynutil.insert("\" ")
    ).optimize()


def generate_landline(context_keywords: pynini.Fst) -> pynini.Fst:
    graph = (
        get_landline(2, context_keywords)
        | get_landline(3, context_keywords)
        | get_landline(4, context_keywords)
        | get_landline(5, context_keywords)
        | get_landline(6, context_keywords)
        | get_landline(7, context_keywords)
    )

    return graph.optimize()


def get_context(keywords: pynini.Fst):

    all_digits = NEMO_DIGIT

    non_digit_char = pynini.difference(NEMO_CHAR, pynini.union(all_digits, NEMO_WHITE_SPACE))
    word = pynini.closure(non_digit_char, 1) + pynini.accep(NEMO_SPACE)

    window = pynini.closure(word, 0, 5)

    before = pynini.closure(keywords + pynini.accep(NEMO_SPACE) + window, 0, 1)

    after = pynini.closure(pynutil.delete(NEMO_SPACE) + window + keywords, 0, 1)

    return before.optimize(), after.optimize()


def generate_credit(context_keywords: pynini.Fst) -> pynini.Fst:
    context_before, context_after = get_context(context_keywords)
    return (
        pynutil.insert("number_part: \"")
        + context_before
        + pynini.closure(num_token + insert_space, 4)
        + context_after
        + pynutil.insert("\" ")
        + delete_space
    ).optimize()


def generate_pincode(context_keywords: pynini.Fst) -> pynini.Fst:
    context_before, context_after = get_context(context_keywords)
    return (
        pynutil.insert("number_part: \"")
        + context_before
        + pynini.closure(num_token + insert_space, 6)
        + context_after
        + pynutil.insert("\" ")
        + delete_space
    ).optimize()


def generate_international() -> pynini.Fst:
    """
    "+<country code> <groups>" with any grouping (space, "-" or "."), read digit by digit, e.g.
        +1 555 123 4567 -> country_code: "پلس ایک" number_part: "پانچ پانچ پانچ ایک دو تین چار پانچ چھ سات"
    """
    separator = pynini.union(NEMO_SPACE, "-", ".")
    reader = num_token + pynini.closure(pynini.closure(pynutil.delete(separator), 0, 1) + insert_space + num_token)
    country_code = (
        pynutil.insert("country_code: \"")
        + pynini.cross("+", "پلس")
        + insert_space
        + (pynini.closure(NEMO_DIGIT, 1, 3) @ reader)
        + pynutil.insert("\" ")
        + pynini.closure(pynutil.delete(pynini.union(NEMO_SPACE, "-")), 0, 1)
    )
    group = pynini.closure(NEMO_DIGIT, 1)
    number = pynini.intersect(
        group + pynini.closure(separator + group),
        pynini.closure(pynini.closure(separator, 0, 1) + NEMO_DIGIT, 6, 12),
    )
    return (country_code + pynutil.insert("number_part: \"") + (number @ reader) + pynutil.insert("\" ")).optimize()


class TelephoneFst(GraphFst):
    """
    Finite state transducer for tagging telephone numbers, e.g.
        03001234567 -> telephone { number_part: "صفر تین صفر صفر ایک دو تین چار پانچ چھ سات" }
        +92 3001234567 -> telephone { country_code: "پلس نو دو", number_part: "تین صفر صفر ایک دو تین چار پانچ چھ سات" }
        042-35761234 -> telephone { number_part: "صفر چار دو تین پانچ سات چھ ایک دو تین چار" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization
    """

    def __init__(self):
        super().__init__(name="telephone", kind="classify")

        mobile_number = generate_mobile(mobile_context)
        landline = generate_landline(landline_context)
        credit_card = generate_credit(credit_context)
        pincode = generate_pincode(pincode_context)
        international = generate_international()

        graph = (
            pynutil.add_weight(mobile_number, 0.7)
            | pynutil.add_weight(landline, 0.8)
            | pynutil.add_weight(credit_card, 0.9)
            | pynutil.add_weight(pincode, 1)
            | pynutil.add_weight(international, 1)
        )

        self.final = graph.optimize()
        self.fst = self.add_tokens(self.final)
