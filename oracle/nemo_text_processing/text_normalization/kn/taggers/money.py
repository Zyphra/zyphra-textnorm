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

from collections import defaultdict

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_KN_DIGIT,
    NEMO_KN_NON_ZERO,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path, load_labels

currency_graph = pynini.string_file(get_abs_path("data/money/currency.tsv"))
currency_singular_graph = pynini.string_file(get_abs_path("data/money/currency_singular.tsv"))


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, suppletive aware, e.g.
        ₹50 -> money { currency_maj: "ರೂಪಾಯಿ" integer_part: "ಐವತ್ತು" }
        ₹50.50 -> money { currency_maj: "ರೂಪಾಯಿ" integer_part: "ಐವತ್ತು" fractional_part: "ಐವತ್ತು" currency_min: "ಪೈಸೆ" }
        ₹0.50 -> money { currency_maj: "ರೂಪಾಯಿ" integer_part: "ಸೊನ್ನೆ" fractional_part: "ಐವತ್ತು" currency_min: "ಪೈಸೆ" }
        $50k -> money { currency_maj: "ಡಾಲರ್" integer_part: "ಐವತ್ತು ಸಾವಿರ" }
        $2.5M -> money { currency_maj: "ಡಾಲರ್" integer_part: "ಎರಡು ದಶಮಾಂಶ ಐದು ಮಿಲಿಯನ್" }
        $15/h -> money { currency_maj: "ಡಾಲರ್" integer_part: "ಹದಿನೈದು" morphosyntactic_features: "ಗಂಟೆಗೆ" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.attributive_graph

        deva_to_ascii = pynini.closure(TO_ASCII_DIGIT, 1)

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _any_digit = _ascii_digit | NEMO_KN_DIGIT
        _any_nonzero = _ascii_nonzero | NEMO_KN_NON_ZERO

        minus_sym = pynini.union("-", "−")
        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(minus_sym, '"true"') + insert_space,
            0,
            1,
        )

        optional_space = pynini.closure(pynutil.delete(" "), 0, 1)

        prefix_usd_plural = pynini.string_map([("USD", "ಯುಎಸ್ ಡಾಲರ್"), ("US$", "ಯುಎಸ್ ಡಾಲರ್")])
        prefix_usd_singular = pynini.string_map([("USD", "ಯುಎಸ್ ಡಾಲರ್"), ("US$", "ಯುಎಸ್ ಡಾಲರ್")])
        non_usd_in = pynini.difference(pynini.project(currency_graph, "input"), pynini.union("USD", "US$"))
        prefix_currency_graph = pynini.compose(non_usd_in, currency_graph) | prefix_usd_plural
        prefix_currency_singular_graph = pynini.compose(non_usd_in, currency_singular_graph) | prefix_usd_singular

        currency_major = pynutil.insert('currency_maj: "') + prefix_currency_graph + pynutil.insert('" ') + optional_space
        currency_major_singular = (
            pynutil.insert('currency_maj: "') + prefix_currency_singular_graph + pynutil.insert('" ') + optional_space
        )
        currency_suffix = optional_space + pynutil.insert(' currency_maj: "') + currency_graph + pynutil.insert('"')
        currency_suffix_singular = (
            optional_space + pynutil.insert(' currency_maj: "') + currency_singular_graph + pynutil.insert('"')
        )
        one = pynini.union("1", "೧")
        integer_one = pynutil.insert('integer_part: "') + (one @ cardinal_graph) + pynutil.insert('"')
        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')

        strip_trailing_zeros = pynini.closure(_ascii_digit) + _ascii_nonzero + pynini.closure(pynutil.delete("0"))
        canonicalise = (
            (pynutil.delete("0") + _ascii_nonzero)
            | (_ascii_nonzero + pynutil.insert("0"))
            | (_ascii_nonzero + _ascii_digit)
        )
        two_digits_fractional_part = deva_to_ascii @ strip_trailing_zeros @ canonicalise

        fraction = (
            pynutil.insert('fractional_part: "') + (two_digits_fractional_part @ cardinal_graph) + pynutil.insert('"')
        ).optimize()

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynini.closure(pynutil.delete("0") | pynutil.delete("೦"), 1),
            0,
            1,
        )

        has_3plus_sig_digits = _any_digit**2 + pynini.closure(_any_digit) + _any_nonzero + pynini.closure(_any_digit)
        single_digit = _any_digit @ cardinal.single_digits_graph
        decimal_digits = (
            pynutil.insert('fractional_part: "')
            + single_digit
            + pynini.closure(insert_space + single_digit)
            + pynutil.insert('"')
        )
        guarded_decimal_digits = (has_3plus_sig_digits @ decimal_digits).optimize()

        integer_final = pynutil.insert('integer_part: "') + cardinal.final_graph + pynutil.insert('"')

        per_unit_map = pynini.string_map(
            [
                ("h", "ಗಂಟೆಗೆ"),
                ("hr", "ಗಂಟೆಗೆ"),
                ("s", "ಸೆಕೆಂಡಿಗೆ"),
                ("sec", "ಸೆಕೆಂಡಿಗೆ"),
                ("min", "ನಿಮಿಷಕ್ಕೆ"),
                ("d", "ದಿನಕ್ಕೆ"),
                ("day", "ದಿನಕ್ಕೆ"),
                ("m", "ತಿಂಗಳಿಗೆ"),
                ("mo", "ತಿಂಗಳಿಗೆ"),
                ("month", "ತಿಂಗಳಿಗೆ"),
                ("y", "ವರ್ಷಕ್ಕೆ"),
                ("yr", "ವರ್ಷಕ್ಕೆ"),
                ("year", "ವರ್ಷಕ್ಕೆ"),
                ("kg", "ಕಿಲೋಗ್ರಾಂಗೆ"),
                ("g", "ಗ್ರಾಂಗೆ"),
                ("l", "ಲೀಟರ್‌ಗೆ"),
                ("km", "ಕಿಲೋಮೀಟರ್‌ಗೆ"),
            ]
        )
        per_unit_suffix = (
            optional_space
            + pynutil.delete("/")
            + optional_space
            + pynutil.insert(' morphosyntactic_features: "')
            + per_unit_map
            + pynutil.insert('"')
        )
        optional_per_unit = pynini.closure(per_unit_suffix, 0, 1)

        mult_k = pynini.cross(pynini.union("k", "K"), " ಸಾವಿರ")
        mult_m = pynini.cross(pynini.union("m", "M"), " ಮಿಲಿಯನ್")
        mult_b = pynini.cross(pynini.union("b", "B"), " ಬಿಲಿಯನ್")
        mult_t = pynini.cross(pynini.union("t", "T"), " ಟ್ರಿಲಿಯನ್")
        mult_suffix = mult_k | mult_m | mult_b | mult_t

        num_int_for_mult = pynini.closure(_any_digit, 1, 4) @ cardinal_graph
        graph_mult_int = (
            currency_major
            + pynutil.insert('integer_part: "')
            + num_int_for_mult
            + mult_suffix
            + pynutil.insert('"')
            + optional_per_unit
        )

        num_dec_for_mult = (
            pynini.closure(_any_digit, 1, 3) @ cardinal_graph
            + pynutil.delete(".")
            + pynutil.insert(" ದಶಮಾಂಶ ")
            + (_any_digit @ cardinal.single_digits_graph)
            + pynini.closure(pynutil.insert(" ") + (_any_digit @ cardinal.single_digits_graph))
        )
        graph_mult_dec = (
            currency_major
            + pynutil.insert('integer_part: "')
            + num_dec_for_mult
            + mult_suffix
            + pynutil.insert('"')
            + optional_per_unit
        )
        graph_mult = graph_mult_int | graph_mult_dec

        # Suffix-only currencies: "25¢"
        cents_graph = pynini.string_map([("¢", "ಸೆಂಟ್"), ("c", "ಸೆಂಟ್")])
        cents_only = (
            pynutil.insert('integer_part: "ಸೊನ್ನೆ" fractional_part: "')
            + (pynini.closure(_any_digit, 1, 2) @ cardinal_graph)
            + pynutil.insert('" currency_maj: "ಡಾಲರ್" currency_min: "')
            + optional_space
            + cents_graph
            + pynutil.insert('"')
        )

        # Mapping from major currency to minor currency
        mapping = load_labels(get_abs_path("data/money/major_minor_currencies.tsv"))
        mapping_dict = defaultdict(list)
        for row in mapping:
            mapping_dict[row[0]].append(row[1])

        maj_min_graphs = []
        for maj, mins in mapping_dict.items():
            min_cross = pynini.union(*mins)
            c_maj = pynutil.delete(maj)
            c_min = pynutil.insert(min_cross)

            p_maj = pynutil.insert(f'currency_maj: "{maj}" ')
            p_min = pynutil.insert(' currency_min: "') + c_min + pynutil.insert('"')

            # Regular integer + 2-digit minor currency
            g1 = (
                p_maj
                + (
                    (prefix_currency_singular_graph @ c_maj) + optional_space + integer_one
                    | (prefix_currency_graph @ c_maj) + optional_space + integer
                )
                + pynutil.delete(".")
                + insert_space
                + fraction
                + p_min
                + optional_per_unit
            )

            # Zero integer + minor currency: "₹0.50" -> integer_part: "ಸೊನ್ನೆ" fractional_part: "ಐವತ್ತು"
            zero_int = pynutil.insert('integer_part: "ಸೊನ್ನೆ"')
            g_zero = (
                p_maj
                + (prefix_currency_graph @ c_maj)
                + optional_space
                + (pynutil.delete("0") | pynutil.delete("೦"))
                + pynutil.delete(".")
                + zero_int
                + insert_space
                + fraction
                + p_min
                + optional_per_unit
            )

            g_suf = (
                (
                    integer_one + pynutil.delete(".") + insert_space + fraction + optional_space + (currency_singular_graph @ c_maj)
                    | integer + pynutil.delete(".") + insert_space + fraction + optional_space + (currency_graph @ c_maj)
                )
                + pynutil.insert(f' currency_maj: "{maj}"')
                + p_min
                + optional_per_unit
            )
            maj_min_graphs.extend([g1, g_zero, g_suf])

        graph_major_minor = pynini.union(*maj_min_graphs)

        # Money with 3+ decimal digits (foreign exchange, cryptocurrency): "$0.0001"
        graph_decimal = (
            currency_major
            + integer_final
            + pynutil.delete(".")
            + insert_space
            + guarded_decimal_digits
            + optional_per_unit
        )
        # Currency ranges: $10-$20, ₹10-₹20, $10-$20/h, $10.5-$20.5, €10k–€20k, $1,000-$2,000
        short_num = cardinal.final_graph | (
            cardinal.final_graph
            + pynini.cross(".", " ದಶಮಾಂಶ ")
            + pynini.compose(pynini.closure(_any_digit, 1, 2), deva_to_ascii @ cardinal.single_digits_graph)
        )
        range_amt = (short_num | (num_int_for_mult + mult_suffix) | (num_dec_for_mult + mult_suffix)).optimize()
        range_dash = pynini.cross(pynini.union("-", "–", " - ", " – "), " ರಿಂದ ")
        maj_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        by_maj_prefix = defaultdict(list)
        for sym, maj in maj_labels:
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

        # Integer only money
        graph_integer_prefix = (
            currency_major_singular + integer_one + optional_delete_fractional_zeros + optional_per_unit
            | currency_major + integer + optional_delete_fractional_zeros + optional_per_unit
        )
        graph_integer_suffix = (
            integer_one + optional_delete_fractional_zeros + currency_suffix_singular + optional_per_unit
            | integer + optional_delete_fractional_zeros + currency_suffix + optional_per_unit
        )
        graph_isolated = (
            graph_mult
            | cents_only
            | pynutil.add_weight(graph_range_prefix | graph_range_suffix, -0.002)
            | pynutil.add_weight(graph_major_minor, -0.001)
            | pynutil.add_weight(graph_decimal, 0.001)
            | graph_integer_prefix
            | graph_integer_suffix
        )
        graph = optional_graph_negative + graph_isolated

        self.positive_fst = pynutil.insert("money { ") + graph_isolated + pynutil.insert(" }")
        self.fst = self.add_tokens(graph)
