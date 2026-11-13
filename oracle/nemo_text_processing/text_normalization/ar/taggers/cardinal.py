# Copyright (c) 2023, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.ar.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    flop_digits,
    insert_and,
    insert_space,
)
from nemo_text_processing.text_normalization.ar.utils import get_abs_path


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying cardinals, e.g.
        "9837" ->  cardinal { integer: "تسعة اَلاف وثمان مئة وسبعة وثلاثون" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self):

        super().__init__(name="cardinal", kind="classify")
        # zero
        graph_zero = pynini.string_file(get_abs_path("data/number/zero.tsv"))

        # cardinals data files
        graph_digit = pynini.string_file(get_abs_path("data/number/digit.tsv"))
        digit_100 = pynini.string_file(get_abs_path("data/number/digit_100.tsv"))
        digit_1000 = pynini.string_file(get_abs_path("data/number/digit_1000.tsv"))
        teens = pynini.string_file(get_abs_path("data/number/teens.tsv"))
        tens = pynini.string_file(get_abs_path("data/number/tens.tsv"))

        # Grammar for cardinals 10_20_30 etc
        tens_zero = tens + pynutil.delete("0")

        # Creating flops for two digit cardinals 34->43
        reverse_digits = pynini.string_file(get_abs_path("data/number/flops.tsv"))

        # Grammar for two digitcardinals
        graph_flops = flop_digits @ reverse_digits
        graph_tens_plus1 = graph_digit + insert_space + insert_and + tens
        graph_tens_plus = graph_flops @ graph_tens_plus1
        graph_all = graph_digit | teens | tens_zero | graph_tens_plus
        graph_two_digits = teens | tens_zero | graph_tens_plus

        # Grammar for cardinals hundreds
        one_hundred = pynini.cross("1", "مئة")
        hundreds_zero = digit_100 + insert_space + pynutil.insert("مئة") + pynutil.delete("00", weight=0.001)
        hundreds_plus = (
            digit_100 + insert_space + pynutil.insert("مئة") + insert_space + insert_and + graph_two_digits
            | digit_100
            + insert_space
            + pynutil.insert("مئة")
            + pynutil.delete("0")
            + insert_space
            + insert_and
            + graph_digit
        )
        two_hundreds = pynini.cross("2", "مئتان")
        graph_one_hundred = one_hundred + pynutil.delete("00", weight=0.001)
        graph_one_hundred_plus = (
            one_hundred + insert_space + insert_and + graph_two_digits
            | one_hundred + pynutil.delete("0") + insert_space + insert_and + graph_digit
        )
        graph_two_hundreds = (
            (two_hundreds + pynutil.delete("00", weight=0.001))
            | two_hundreds + insert_space + insert_and + graph_two_digits
            | two_hundreds + pynutil.delete("0") + insert_space + insert_and + graph_digit
        )

        graph_all_one_hundred = graph_one_hundred | graph_one_hundred_plus

        graph_all_hundreds = graph_all_one_hundred | graph_two_hundreds | hundreds_zero | hundreds_plus

        # Grammar for thousands
        one_thousand = pynini.cross("1", "ألف")
        thousands_zero = digit_1000 + insert_space + pynutil.insert("اَلاف") + pynutil.delete("000", weight=0.001)
        thousands_plus = (
            digit_1000 + insert_space + pynutil.insert("اَلاف") + insert_space + insert_and + graph_all_hundreds
        )
        thousands_skip_hundreds = (
            digit_1000
            + insert_space
            + pynutil.insert("اَلاف")
            + pynutil.delete("0")
            + insert_space
            + insert_and
            + graph_two_digits
            | digit_1000
            + insert_space
            + pynutil.insert("اَلاف")
            + pynutil.delete("00")
            + insert_space
            + insert_and
            + graph_digit
        )
        two_thousands = pynini.cross("2", "ألفان")
        graph_one_thousand = one_thousand + pynutil.delete("000", weight=0.001)
        graph_one_thousand_plus = (
            one_thousand + insert_space + insert_and + graph_all_hundreds
            | one_thousand + pynutil.delete("0") + insert_space + insert_and + graph_two_digits
            | one_thousand + pynutil.delete("00") + insert_space + insert_and + graph_digit
        )
        graph_two_thousands = two_thousands + pynutil.delete("000", weight=0.001)
        graph_two_thousands_plus = (
            two_thousands + insert_space + insert_and + graph_all_hundreds
            | two_thousands + pynutil.delete("0") + insert_space + insert_and + graph_two_digits
            | two_thousands + pynutil.delete("00") + insert_space + insert_and + graph_digit
        )

        graph_all_one_thousand = graph_one_thousand | graph_one_thousand_plus
        graph_all_two_thousands = graph_two_thousands | graph_two_thousands_plus

        graph_all_thousands = (
            graph_all_one_thousand
            | graph_two_thousands
            | thousands_zero
            | thousands_plus
            | thousands_skip_hundreds
            | graph_all_two_thousands
        )

        graph = graph_all | graph_all_hundreds | graph_all_thousands | graph_zero

        # 10,000 - 999,999,999,999: thousands, millions and billions, joined with "و" like the hundreds above.
        # Magnitude words follow CLDR %spellout-cardinal-masculine: 1 مليون, 2 مليونان, 3-10 <n> ملايين,
        # 11+ <n> مليون (same for ألف/اَلاف and مليار/مليارات); a count of exactly 200 takes the construct form مئتا.
        three_digits = (
            pynutil.delete("00") + graph_digit | pynutil.delete("0") + graph_two_digits | graph_all_hundreds
        )
        three_to_nine = pynini.union(*"3456789")
        special_counts = pynini.union("001", "002", "010", "200", *[f"00{d}" for d in "3456789"])

        def magnitude(singular: str, dual: str, plural: str):
            return (
                pynini.cross("001", singular)
                | pynini.cross("002", dual)
                | pynutil.delete("00") + (three_to_nine @ graph_digit) + insert_space + pynutil.insert(plural)
                | pynini.cross("010", "عشرة") + insert_space + pynutil.insert(plural)
                | pynini.cross("200", "مئتا") + insert_space + pynutil.insert(singular)
                | (pynini.difference(NEMO_DIGIT**3, special_counts) @ three_digits)
                + insert_space
                + pynutil.insert(singular)
            )

        rest_and = insert_space + insert_and
        up_to_six = pynutil.delete("000") + three_digits | magnitude("ألف", "ألفان", "اَلاف") + (
            pynutil.delete("000") | rest_and + three_digits
        )
        up_to_nine = pynutil.delete("000") + up_to_six | magnitude("مليون", "مليونان", "ملايين") + (
            pynutil.delete("000000") | rest_and + up_to_six
        )
        up_to_twelve = pynutil.delete("000") + up_to_nine | magnitude("مليار", "ملياران", "مليارات") + (
            pynutil.delete("000000000") | rest_and + up_to_nine
        )
        pad_to_twelve = pynini.union(
            *[
                pynutil.insert("0" * (12 - length)) + (NEMO_DIGIT - "0") + NEMO_DIGIT ** (length - 1)
                for length in range(5, 13)
            ]
        )
        graph_large = (pad_to_twelve @ up_to_twelve).optimize()

        # Comma-grouped integers: "1,000" (a lone group of zeros cannot be a decimal) or two or more groups.
        # "12,345" stays a decimal as upstream; the small bonus makes "1,000" a cardinal rather than "1 and 0/1000".
        group = pynutil.delete(",") + NEMO_DIGIT**3
        lead_group = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)
        graph_grouped = (
            (lead_group + pynutil.delete(",") + pynini.accep("000")) | (lead_group + group + pynini.closure(group, 1, 2))
        ) @ (graph | graph_large)
        graph_grouped = pynutil.add_weight(graph_grouped, -0.01)

        self.cardinal_numbers = (graph | graph_large | graph_grouped).optimize()

        #  remove leading zeros
        leading_zeros = pynini.closure(pynini.cross("0", ""))
        self.cardinal_numbers_with_leading_zeros = (leading_zeros + graph | graph_large | graph_grouped).optimize()

        self.optional_minus_graph = pynini.closure(
            pynutil.insert('negative: "true" ')
            + pynutil.delete(pynini.union("-", "−") + pynini.closure(" ", 0, 1)),
            0,
            1,
        )

        final_graph = (
            self.optional_minus_graph
            + pynutil.insert('integer: "')
            + self.cardinal_numbers_with_leading_zeros
            + pynutil.insert('"')
        )

        final_graph = self.add_tokens(final_graph)  # inserts the cardinal tag

        self.fst = final_graph
