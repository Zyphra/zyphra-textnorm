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

from nemo_text_processing.text_normalization.mr.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_ZERO,
    NEMO_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.mr.utils import get_abs_path


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying cardinals, e.g.
        -२३ -> cardinal { negative: "true"  integer: "तेवीस" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True, lm: bool = False):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        zero = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))
        # Load both Devanagari and ASCII number mappings
        teens_ties_hi = pynini.string_file(get_abs_path("data/numbers/teens_and_ties.tsv"))
        teens_ties_en = pynini.string_file(get_abs_path("data/numbers/teens_and_ties_en.tsv"))
        teens_ties = pynini.union(teens_ties_hi, teens_ties_en)
        teens_and_ties = pynutil.add_weight(teens_ties, -0.1)

        self.digit = digit
        self.zero = zero
        self.teens_and_ties = teens_and_ties

        # Single digit graph for digit-by-digit reading
        # e.g., "०७३" -> "शून्य सात तीन"
        single_digit_graph = digit | zero
        self.single_digits_graph = single_digit_graph + pynini.closure(insert_space + single_digit_graph)

        def create_graph_suffix(digit_graph, suffix, zeros_counts):
            zero = pynutil.add_weight(pynutil.delete(NEMO_ALL_ZERO), -0.1)
            if zeros_counts == 0:
                return digit_graph + suffix

            return digit_graph + (zero**zeros_counts) + suffix

        def create_larger_number_graph(digit_graph, suffix, zeros_counts, sub_graph):
            insert_space = pynutil.insert(" ")
            zero = pynutil.add_weight(pynutil.delete(NEMO_ALL_ZERO), -0.1)
            if zeros_counts == 0:
                return digit_graph + suffix + insert_space + sub_graph

            return digit_graph + suffix + (zero**zeros_counts) + insert_space + sub_graph

        # Hundreds per CLDR mr %spellout-cardinal: 100 शंभर, 101-199 एकशे >>, 200 दोनशे[ >>] ... 900 नऊशे[ >>]
        hundreds_prefix = pynini.string_file(get_abs_path("data/numbers/hundreds_prefix.tsv"))
        one = pynini.union("1", "१")
        delete_zero = pynutil.add_weight(pynutil.delete(NEMO_ALL_ZERO), -0.1)
        graph_hundreds = pynini.cross(one + NEMO_ALL_ZERO + NEMO_ALL_ZERO, "शंभर")
        nonone_prefix = pynini.compose(pynini.difference(NEMO_ALL_DIGIT, one), hundreds_prefix)
        graph_hundreds |= nonone_prefix + (delete_zero**2)
        graph_hundreds |= hundreds_prefix + delete_zero + insert_space + digit
        graph_hundreds |= hundreds_prefix + insert_space + teens_ties
        graph_hundreds = graph_hundreds.optimize()
        self.graph_hundreds = graph_hundreds

        # Thousands and Ten thousands graph
        suffix_thousands = pynutil.insert(" हजार")
        graph_thousands = create_graph_suffix(digit, suffix_thousands, 3)
        graph_thousands |= create_larger_number_graph(digit, suffix_thousands, 2, digit)
        graph_thousands |= create_larger_number_graph(digit, suffix_thousands, 1, teens_ties)
        graph_thousands |= create_larger_number_graph(digit, suffix_thousands, 0, graph_hundreds)
        graph_thousands.optimize()
        self.graph_thousands = graph_thousands

        graph_ten_thousands = create_graph_suffix(teens_and_ties, suffix_thousands, 3)
        graph_ten_thousands |= create_larger_number_graph(teens_and_ties, suffix_thousands, 2, digit)
        graph_ten_thousands |= create_larger_number_graph(teens_and_ties, suffix_thousands, 1, teens_ties)
        graph_ten_thousands |= create_larger_number_graph(teens_and_ties, suffix_thousands, 0, graph_hundreds)
        graph_ten_thousands.optimize()
        self.graph_ten_thousands = graph_ten_thousands

        # Lakhs graph and ten lakhs graph
        suffix_lakhs = pynutil.insert(" लाख")
        graph_lakhs = create_graph_suffix(digit, suffix_lakhs, 5)
        graph_lakhs |= create_larger_number_graph(digit, suffix_lakhs, 4, digit)
        graph_lakhs |= create_larger_number_graph(digit, suffix_lakhs, 3, teens_ties)
        graph_lakhs |= create_larger_number_graph(digit, suffix_lakhs, 2, graph_hundreds)
        graph_lakhs |= create_larger_number_graph(digit, suffix_lakhs, 1, graph_thousands)
        graph_lakhs |= create_larger_number_graph(digit, suffix_lakhs, 0, graph_ten_thousands)
        graph_lakhs.optimize()
        self.graph_lakhs = graph_lakhs

        graph_ten_lakhs = create_graph_suffix(teens_and_ties, suffix_lakhs, 5)
        graph_ten_lakhs |= create_larger_number_graph(teens_and_ties, suffix_lakhs, 4, digit)
        graph_ten_lakhs |= create_larger_number_graph(teens_and_ties, suffix_lakhs, 3, teens_ties)
        graph_ten_lakhs |= create_larger_number_graph(teens_and_ties, suffix_lakhs, 2, graph_hundreds)
        graph_ten_lakhs |= create_larger_number_graph(teens_and_ties, suffix_lakhs, 1, graph_thousands)
        graph_ten_lakhs |= create_larger_number_graph(teens_and_ties, suffix_lakhs, 0, graph_ten_thousands)
        graph_ten_lakhs.optimize()
        self.graph_ten_lakhs = graph_ten_lakhs

        # Crores graph ten crores graph
        suffix_crores = pynutil.insert(" कोटी")
        graph_crores = create_graph_suffix(digit, suffix_crores, 7)
        graph_crores |= create_larger_number_graph(digit, suffix_crores, 6, digit)
        graph_crores |= create_larger_number_graph(digit, suffix_crores, 5, teens_ties)
        graph_crores |= create_larger_number_graph(digit, suffix_crores, 4, graph_hundreds)
        graph_crores |= create_larger_number_graph(digit, suffix_crores, 3, graph_thousands)
        graph_crores |= create_larger_number_graph(digit, suffix_crores, 2, graph_ten_thousands)
        graph_crores |= create_larger_number_graph(digit, suffix_crores, 1, graph_lakhs)
        graph_crores |= create_larger_number_graph(digit, suffix_crores, 0, graph_ten_lakhs)
        graph_crores.optimize()

        graph_ten_crores = create_graph_suffix(teens_and_ties, suffix_crores, 7)
        graph_ten_crores |= create_larger_number_graph(teens_and_ties, suffix_crores, 6, digit)
        graph_ten_crores |= create_larger_number_graph(teens_and_ties, suffix_crores, 5, teens_ties)
        graph_ten_crores |= create_larger_number_graph(teens_and_ties, suffix_crores, 4, graph_hundreds)
        graph_ten_crores |= create_larger_number_graph(teens_and_ties, suffix_crores, 3, graph_thousands)
        graph_ten_crores |= create_larger_number_graph(teens_and_ties, suffix_crores, 2, graph_ten_thousands)
        graph_ten_crores |= create_larger_number_graph(teens_and_ties, suffix_crores, 1, graph_lakhs)
        graph_ten_crores |= create_larger_number_graph(teens_and_ties, suffix_crores, 0, graph_ten_lakhs)
        graph_ten_crores.optimize()

        # Arabs graph and ten arabs graph
        suffix_arabs = pynutil.insert(" अब्ज")
        graph_arabs = create_graph_suffix(digit, suffix_arabs, 9)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 8, digit)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 7, teens_ties)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 6, graph_hundreds)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 5, graph_thousands)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 4, graph_ten_thousands)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 3, graph_lakhs)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 2, graph_ten_lakhs)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 1, graph_crores)
        graph_arabs |= create_larger_number_graph(digit, suffix_arabs, 0, graph_ten_crores)
        graph_arabs.optimize()

        graph_ten_arabs = create_graph_suffix(teens_and_ties, suffix_arabs, 9)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 8, digit)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 7, teens_ties)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 6, graph_hundreds)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 5, graph_thousands)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 4, graph_ten_thousands)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 3, graph_lakhs)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 2, graph_ten_lakhs)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 1, graph_crores)
        graph_ten_arabs |= create_larger_number_graph(teens_and_ties, suffix_arabs, 0, graph_ten_crores)
        graph_ten_arabs.optimize()

        # Kharabs graph and ten kharabs graph
        suffix_kharabs = pynutil.insert(" खर्व")
        graph_kharabs = create_graph_suffix(digit, suffix_kharabs, 11)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 10, digit)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 9, teens_ties)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 8, graph_hundreds)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 7, graph_thousands)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 6, graph_ten_thousands)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 5, graph_lakhs)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 4, graph_ten_lakhs)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 3, graph_crores)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 2, graph_ten_crores)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 1, graph_arabs)
        graph_kharabs |= create_larger_number_graph(digit, suffix_kharabs, 0, graph_ten_arabs)
        graph_kharabs.optimize()

        graph_ten_kharabs = create_graph_suffix(teens_and_ties, suffix_kharabs, 11)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 10, digit)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 9, teens_ties)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 8, graph_hundreds)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 7, graph_thousands)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 6, graph_ten_thousands)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 5, graph_lakhs)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 4, graph_ten_lakhs)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 3, graph_crores)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 2, graph_ten_crores)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 1, graph_arabs)
        graph_ten_kharabs |= create_larger_number_graph(teens_and_ties, suffix_kharabs, 0, graph_ten_arabs)
        graph_ten_kharabs.optimize()

        # Only match exactly 2 digits to avoid interfering with telephone numbers, decimals, etc.
        # e.g., "०५" -> "शून्य पाच"
        single_digit = digit | zero
        graph_leading_zero = zero + insert_space + single_digit
        graph_leading_zero = pynutil.add_weight(graph_leading_zero, 0.5)

        graph_without_leading_zeros = (
            digit
            | zero
            | teens_and_ties
            | graph_hundreds
            | graph_thousands
            | graph_ten_thousands
            | graph_lakhs
            | graph_ten_lakhs
            | graph_crores
            | graph_ten_crores
            | graph_arabs
            | graph_ten_arabs
            | graph_kharabs
            | graph_ten_kharabs
        )
        self.graph_without_leading_zeros = graph_without_leading_zeros.optimize()

        # Handle numbers with leading zeros by reading digit-by-digit
        # e.g., ASCII "073" -> "शून्य सात तीन", Devanagari "००५" -> "शून्य शून्य पाच"
        cardinal_with_leading_zeros = pynini.compose(
            NEMO_ALL_ZERO + pynini.closure(NEMO_ALL_DIGIT), self.single_digits_graph
        )
        cardinal_with_leading_zeros = pynutil.add_weight(cardinal_with_leading_zeros, 0.5)

        # Handle large numbers written with digit-group separators.
        delete_separator = pynutil.delete(",")
        two_digits = NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        three_digits = NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        # Indian grouping: 1-2 leading digits, groups of 2, final group of 3.
        indian_grouping = (
            pynini.closure(NEMO_ALL_DIGIT, 1, 2)
            + pynini.closure(delete_separator + two_digits)
            + delete_separator
            + three_digits
        )
        # International grouping: 1-3 leading digits, one or more groups of 3.
        western_grouping = pynini.closure(NEMO_ALL_DIGIT, 1, 3) + pynini.closure(delete_separator + three_digits, 1)
        strip_separators = (indian_grouping | western_grouping).optimize()
        cardinal_with_separators = pynini.compose(strip_separators, graph_without_leading_zeros).optimize()

        # Full graph including leading zeros - for standalone cardinal matching
        final_graph = graph_without_leading_zeros | cardinal_with_leading_zeros | cardinal_with_separators

        delete_opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        optional_minus_graph = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true" '))
            | (pynini.cross("~", 'negative: "सुमारे" ') + delete_opt_sp)
            | (pynini.cross("±", 'negative: "अधिक किंवा उणे" ') + delete_opt_sp),
            0,
            1,
        )
        # --- Centralized logic for Address & Serial classes ---
        # 1-3 digit groups read as cardinals, 4+ digits read digit-by-digit
        limited_cardinal_graph = (self.digit | self.zero | self.teens_and_ties | self.graph_hundreds).optimize()

        any_digit = pynini.union(
            NEMO_DIGIT,
            pynini.project(
                pynini.union(
                    pynini.string_file(get_abs_path("data/numbers/digit.tsv")),
                    pynini.string_file(get_abs_path("data/numbers/zero.tsv")),
                ),
                "input",
            ),
        ).optimize()

        digitwise_4plus = pynini.compose(any_digit**4 + pynini.closure(any_digit), self.single_digits_graph).optimize()

        self.code_num_graph = (limited_cardinal_graph | digitwise_4plus).optimize()

        # En-dash ranges ("10–20", "1995–2005") read with "ते"
        endash_range = (
            self.graph_without_leading_zeros
            + delete_opt_sp
            + pynini.cross("–", " ते ")
            + delete_opt_sp
            + self.graph_without_leading_zeros
        ).optimize()

        self.final_graph = final_graph.optimize()
        final_graph = (
            optional_minus_graph + pynutil.insert('integer: "') + self.final_graph + pynutil.insert('"')
            | pynutil.insert('integer: "') + endash_range + pynutil.insert('"')
        )
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph
