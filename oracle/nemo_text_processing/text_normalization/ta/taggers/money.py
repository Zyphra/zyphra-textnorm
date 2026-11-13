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

from collections import defaultdict

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_TA_DIGIT,
    NEMO_TA_NON_ZERO,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path, load_labels

currency_graph = pynini.string_file(get_abs_path("data/money/currency.tsv"))
currency_singular_graph = pynini.string_file(get_abs_path("data/money/currency_singular.tsv"))


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, e.g.
        ₹50 -> money { currency_maj: "ரூபாய்" integer_part: "ஐம்பது" }
        ₹50.50 -> money { currency_maj: "ரூபாய்" integer_part: "ஐம்பது" fractional_part: "ஐம்பது" currency_min: "பைசா" }
        ₹0.50 -> money { currency_maj: "ரூபாய்" integer_part: "பூஜ்யம்" fractional_part: "ஐம்பது" currency_min: "பைசா" }
        $50k -> money { currency_maj: "டாலர்" integer_part: "ஐம்பதாயிரம்" }
        $2.5M -> money { currency_maj: "டாலர்" integer_part: "இரண்டு புள்ளி ஐந்து மில்லியன்" }
        $15/h -> money { currency_maj: "டாலர்" integer_part: "பதினைந்து" morphosyntactic_features: "ஒரு மணிநேரத்திற்கு" }
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.attributive_graph

        deva_to_ascii = pynini.closure(TO_ASCII_DIGIT, 1)

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _any_digit = _ascii_digit | NEMO_TA_DIGIT
        _any_nonzero = _ascii_nonzero | NEMO_TA_NON_ZERO

        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", '"true"') + insert_space,
            0,
            1,
        )

        currency_major = pynutil.insert('currency_maj: "') + currency_graph + pynutil.insert('"')
        currency_major_singular = pynutil.insert('currency_maj: "') + currency_singular_graph + pynutil.insert('"')

        two_digits_fractional_part = _any_digit + _any_digit
        fractional_part = (
            pynutil.insert('fractional_part: "')
            + pynini.compose(deva_to_ascii, cardinal.teens_and_ties | cardinal.digit | cardinal.zero)
            + pynutil.insert('"')
        )
        fractional_part_tens = (
            pynutil.insert('fractional_part: "')
            + pynini.compose(deva_to_ascii, pynini.cross("1", "பத்து"))
            + pynutil.delete(pynini.union("0", "௦"))
            + pynutil.insert('"')
        )

        fraction = pynini.compose(
            two_digits_fractional_part, (fractional_part | fractional_part_tens)
        )

        guarded_decimal_digits = pynutil.insert('fractional_part: "') + cardinal.single_digits_graph + pynutil.insert('"')

        optional_space = pynini.closure(pynutil.delete(" "), 0, 1)

        per_unit_words = pynini.string_map(
            [
                ("/h", "மணிக்கு"),
                ("/hr", "மணிக்கு"),
                ("/hour", "மணிக்கு"),
                ("/kg", "ஒரு கிலோவிற்கு"),
                ("/day", "ஒரு நாளைக்கு"),
                ("/month", "ஒரு மாதத்திற்கு"),
                ("/year", "ஒரு வருடத்திற்கு"),
                ("/yr", "ஒரு ஆண்டிற்கு"),
                ("/m", "ஒரு மீட்டருக்கு"),
                ("/km", "ஒரு கிலோமீட்டருக்கு"),
            ]
        )
        optional_per_unit = pynini.closure(
            optional_space
            + pynutil.insert(' morphosyntactic_features: "')
            + per_unit_words
            + pynutil.insert('"'),
            0,
            1,
        )

        currency_major = currency_major + optional_space
        currency_major_singular = currency_major_singular + optional_space
        currency_suffix = optional_space + insert_space + currency_major
        currency_suffix_singular = optional_space + insert_space + currency_major_singular

        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')
        integer_one = (
            pynutil.insert('integer_part: "')
            + pynini.compose(pynini.union("1", "௧"), cardinal_graph)
            + pynutil.insert('"')
        )

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynutil.delete(pynini.union("0", "௦")) + pynutil.delete(pynini.union("0", "௦")),
            0,
            1,
        )
        integer_final = integer + optional_delete_fractional_zeros

        # Shorthand notation: $50k, €50k, $2.5M
        shorthand_k_words = (
            (pynini.compose(pynini.closure(_any_digit, 1, 3), deva_to_ascii) + pynutil.delete(pynini.union("k", "K")) + pynutil.insert("000"))
            @ cardinal_graph
        )
        shorthand_scale_int = (
            pynini.compose(pynini.closure(_any_digit, 1, 3), deva_to_ascii @ cardinal_graph)
            + (
                pynutil.delete(pynini.union("m", "M")) + pynutil.insert(" மில்லியன்")
                | pynutil.delete(pynini.union("b", "B")) + pynutil.insert(" பில்லியன்")
                | pynutil.delete(pynini.union("t", "T")) + pynutil.insert(" ட்ரில்லியன்")
            )
        )
        shorthand_scale_dec = (
            pynini.compose(pynini.closure(_any_digit, 1, 3), deva_to_ascii @ cardinal_graph)
            + pynini.cross(".", " புள்ளி ")
            + pynini.compose(pynini.closure(_any_digit, 1, 3), deva_to_ascii @ cardinal.single_digits_graph)
            + (
                pynutil.delete(pynini.union("m", "M")) + pynutil.insert(" மில்லியன்")
                | pynutil.delete(pynini.union("b", "B")) + pynutil.insert(" பில்லியன்")
                | pynutil.delete(pynini.union("t", "T")) + pynutil.insert(" ட்ரில்லியன்")
            )
        )
        shorthand_words = (shorthand_k_words | shorthand_scale_dec | shorthand_scale_int).optimize()
        shorthand_integer = pynutil.insert('integer_part: "') + shorthand_words + pynutil.insert('"')
        graph_shorthand_prefix = (
            optional_graph_negative + currency_major + insert_space + shorthand_integer + optional_per_unit
        )
        graph_shorthand_suffix = (
            optional_graph_negative + shorthand_integer + currency_suffix + optional_per_unit
        )

        # Currency ranges: ₹10-₹20, $10-$20
        short_num = cardinal.final_graph | (
            cardinal.final_graph
            + pynini.cross(".", " புள்ளி ")
            + pynini.compose(pynini.closure(_any_digit, 1, 2), deva_to_ascii @ cardinal.single_digits_graph)
        )
        range_amt = (short_num | shorthand_words).optimize()
        range_dash = pynini.cross(pynini.union("-", "–", " - ", " – "), " முதல் ")
        maj_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        prefix_maj_labels = maj_labels
        by_maj_prefix = defaultdict(list)
        for sym, maj in prefix_maj_labels:
            by_maj_prefix[maj].append(sym)
        same_sym_ranges = []
        for maj, syms in by_maj_prefix.items():
            sym_u = pynini.union(*syms)
            same_sym_ranges.append(
                pynutil.insert(f'currency_maj: "{maj}" integer_part: "')
                + pynutil.delete(sym_u)
                + optional_space
                + range_amt
                + range_dash
                + pynini.closure(pynutil.delete(sym_u) + optional_space, 0, 1)
                + range_amt
                + pynutil.insert('"')
                + optional_per_unit
            )
        graph_range_prefix = pynini.union(*same_sym_ranges)
        graph_range_suffix = (
            pynutil.insert('integer_part: "')
            + range_amt
            + range_dash
            + range_amt
            + pynutil.insert('"')
            + currency_suffix
            + optional_per_unit
        )

        graph_decimal_path = (
            optional_graph_negative
            + currency_major
            + insert_space
            + integer_final
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + optional_per_unit
        )
        graph_suffix_decimal = (
            optional_graph_negative
            + integer_final
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + currency_suffix
            + optional_per_unit
        )

        graph_major_only_singular = (
            optional_graph_negative
            + currency_major_singular
            + insert_space
            + integer_one
            + optional_delete_fractional_zeros
            + optional_per_unit
        )
        graph_suffix_only_singular = (
            optional_graph_negative
            + integer_one
            + optional_delete_fractional_zeros
            + currency_suffix_singular
            + optional_per_unit
        )

        graph_major_only = (
            optional_graph_negative
            + currency_major
            + insert_space
            + integer
            + optional_delete_fractional_zeros
            + optional_per_unit
        )
        graph_suffix_only = (
            optional_graph_negative
            + integer
            + optional_delete_fractional_zeros
            + currency_suffix
            + optional_per_unit
        )

        maj_singular_labels = load_labels(get_abs_path("data/money/currency_singular.tsv"))
        prefix_maj_singular_labels = maj_singular_labels
        maj_to_min = dict(load_labels(get_abs_path("data/money/major_minor_currencies.tsv")))

        def _build_major_and_minor(pref_labels, suf_labels, int_graph):
            by_pair_pref = defaultdict(list)
            for sym, maj in pref_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_pair_pref[(maj, min_name)].append(sym)
            by_pair_suf = defaultdict(list)
            for sym, maj in suf_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_pair_suf[(maj, min_name)].append(sym)

            amount = (int_graph + pynini.cross(".", " ") + fraction).optimize()
            graphs = []
            for (maj, min_name), syms in by_pair_pref.items():
                sym_union = pynini.union(*syms)
                curr_maj = pynutil.insert(f'currency_maj: "{maj}"') + pynutil.delete(sym_union) + optional_space
                curr_min = pynutil.insert(f'currency_min: "{min_name}"')
                graphs.append(
                    optional_graph_negative
                    + curr_maj
                    + insert_space
                    + amount
                    + insert_space
                    + curr_min
                    + optional_per_unit
                )
            for (maj, min_name), syms in by_pair_suf.items():
                sym_union = pynini.union(*syms)
                graphs.append(
                    optional_graph_negative
                    + amount
                    + optional_space
                    + pynutil.insert(f' currency_maj: "{maj}" currency_min: "{min_name}"')
                    + pynutil.delete(sym_union)
                    + optional_per_unit
                )
            return pynini.union(*graphs)

        graph_major_and_minor = _build_major_and_minor(prefix_maj_labels, maj_labels, integer)
        graph_major_and_minor_singular = _build_major_and_minor(
            prefix_maj_singular_labels, maj_singular_labels, integer_one
        )

        graph_currencies = (
            pynutil.add_weight(
                graph_major_only_singular | graph_suffix_only_singular | graph_major_and_minor_singular, -0.002
            )
            | pynutil.add_weight(graph_major_and_minor, -0.001)
            | pynutil.add_weight(graph_decimal_path | graph_suffix_decimal, 0.001)
            | pynutil.add_weight(graph_shorthand_prefix | graph_shorthand_suffix, -0.002)
            | pynutil.add_weight(graph_range_prefix | graph_range_suffix, -0.002)
            | graph_major_only
            | graph_suffix_only
        )

        graph = graph_currencies.optimize()
        self.fst = self.add_tokens(graph)
