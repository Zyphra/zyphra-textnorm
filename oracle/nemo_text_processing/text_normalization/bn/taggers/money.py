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

from nemo_text_processing.text_normalization.bn.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.bn.utils import get_abs_path, load_labels

currency_graph = pynini.string_file(get_abs_path("data/money/currency.tsv"))
quantities_graph = pynini.string_file(get_abs_path("data/numbers/quantities.tsv"))


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, suppletive aware, e.g.
        ৳৫০ -> money { currency_maj: "টাকা" integer_part: "পঞ্চাশ" }
        ৳৫০.৫০ -> money { currency_maj: "টাকা" integer_part: "পঞ্চাশ" fractional_part: "পঞ্চাশ" currency_min: "পয়সা" }
        ৳০.৫০ -> money { currency_maj: "টাকা" integer_part: "শূন্য" fractional_part: "পঞ্চাশ" currency_min: "পয়সা" }
        ৫০৳ / Tk 50 -> money { currency_maj: "টাকা" integer_part: "পঞ্চাশ" }

    Bengali currency names are invariant (১ টাকা, ৫ টাকা), so there is no singular table.

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.final_graph

        _bn_to_ascii = pynini.union(*[pynini.cross(b, a) for b, a in zip("০১২৩৪৫৬৭৮৯", "0123456789")])
        bn_to_ascii = pynini.closure(_bn_to_ascii | pynini.union(*"0123456789"), 1)

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _bn_nonzero = pynini.union(*"১২৩৪৫৬৭৮৯")
        _any_digit = _ascii_digit | pynini.union(*"০১২৩৪৫৬৭৮৯")
        _any_nonzero = _ascii_nonzero | _bn_nonzero

        sign_prefix = (
            pynini.cross(pynini.union("-", "−"), '"true"')
            | (pynini.cross("~", '"approx"') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", '"pm"') + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + sign_prefix + insert_space,
            0,
            1,
        )

        # The symbol may be followed by a space or a period (Tk. 500, Rs. 500)
        delete_symbol_sep = pynini.closure(pynutil.delete(pynini.union(" ", ". ", ".")), 0, 1)
        currency_major = pynutil.insert('currency_maj: "') + currency_graph + pynutil.insert('"') + delete_symbol_sep

        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')

        strip_trailing_zeros = pynini.closure(_ascii_digit) + _ascii_nonzero + pynini.closure(pynutil.delete("0"))
        canonicalise = (
            (pynutil.delete("0") + _ascii_nonzero)
            | (_ascii_nonzero + pynutil.insert("0"))
            | (_ascii_nonzero + _ascii_digit)
        )
        two_digits_fractional_part = bn_to_ascii @ strip_trailing_zeros @ canonicalise

        fraction = (
            pynutil.insert('fractional_part: "') + (two_digits_fractional_part @ cardinal_graph) + pynutil.insert('"')
        )

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynini.closure(pynutil.delete("0") | pynutil.delete("০"), 1),
            0,
            1,
        )

        has_3plus_sig_digits = _any_digit + _any_digit + _any_nonzero + pynini.closure(_any_digit)
        single_digit = _any_digit @ cardinal.single_digits_graph
        decimal_digits = (
            pynutil.insert('fractional_part: "')
            + single_digit
            + pynini.closure(insert_space + single_digit)
            + pynutil.insert('"')
        )
        guarded_decimal_digits = has_3plus_sig_digits @ decimal_digits

        # Per-unit money suffix, e.g. $15/h -> পনেরো ডলার প্রতি ঘণ্টা, €20/kg -> কুড়ি ইউরো প্রতি কিলোগ্রাম
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        per_unit_map = pynini.string_map(
            [
                ("h", "প্রতি ঘণ্টা"),
                ("hr", "প্রতি ঘণ্টা"),
                ("s", "প্রতি সেকেন্ড"),
                ("sec", "প্রতি সেকেন্ড"),
                ("min", "প্রতি মিনিট"),
                ("d", "প্রতিদিন"),
                ("day", "প্রতিদিন"),
                ("wk", "প্রতি সপ্তাহ"),
                ("mo", "প্রতি মাস"),
                ("month", "প্রতি মাস"),
                ("yr", "প্রতি বছর"),
                ("year", "প্রতি বছর"),
                ("kg", "প্রতি কিলোগ্রাম"),
                ("g", "প্রতি গ্রাম"),
                ("lb", "প্রতি পাউন্ড"),
                ("oz", "প্রতি আউন্স"),
                ("t", "প্রতি টন"),
                ("l", "প্রতি লিটার"),
                ("L", "প্রতি লিটার"),
                ("gal", "প্রতি গ্যালন"),
                ("m", "প্রতি মিটার"),
                ("km", "প্রতি কিলোমিটার"),
                ("ft", "প্রতি ফুট"),
                ("m²", "প্রতি বর্গ মিটার"),
                ("m2", "প্রতি বর্গ মিটার"),
                ("ft²", "প্রতি বর্গ ফুট"),
                ("ft2", "প্রতি বর্গ ফুট"),
                ("ac", "প্রতি একর"),
                ("kWh", "প্রতি কিলোওয়াট ঘন্টা"),
            ]
        )
        per_unit = (
            opt_sp
            + pynutil.delete("/")
            + opt_sp
            + pynutil.insert(' morphosyntactic_features: "')
            + per_unit_map
            + pynutil.insert('"')
        ).optimize()
        opt_per_unit = pynini.closure(per_unit, 0, 1)

        graph_decimal_path = (
            optional_graph_negative
            + currency_major
            + insert_space
            + pynutil.insert('integer_part: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + opt_per_unit
        ).optimize()

        graph_major_only = (
            optional_graph_negative
            + currency_major
            + insert_space
            + integer
            + optional_delete_fractional_zeros
            + opt_per_unit
        ).optimize()

        maj_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        maj_to_min = dict(load_labels(get_abs_path("data/money/major_minor_currencies.tsv")))

        def _build_major_and_minor(sym_maj_labels, int_graph, trailing: bool = False):
            by_min = {}
            for sym, maj in sym_maj_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_min.setdefault(min_name, []).append((sym, maj))
            branches = []
            for min_name, pairs in by_min.items():
                curr_maj_map = pynini.string_map(pairs)
                curr_min = pynutil.insert(f'currency_min: "{min_name}"')
                if trailing:
                    curr_maj = (
                        pynini.closure(pynutil.delete(" "), 0, 1)
                        + pynutil.insert(' currency_maj: "')
                        + curr_maj_map
                        + pynutil.insert('"')
                    )
                    g = (
                        optional_graph_negative
                        + int_graph
                        + pynini.cross(".", " ")
                        + fraction
                        + insert_space
                        + curr_min
                        + curr_maj
                        + opt_per_unit
                    ).optimize()
                else:
                    curr_maj = (
                        pynutil.insert('currency_maj: "')
                        + curr_maj_map
                        + pynutil.insert('"')
                        + delete_symbol_sep
                    )
                    g = (
                        optional_graph_negative
                        + curr_maj
                        + insert_space
                        + int_graph
                        + pynini.cross(".", " ")
                        + fraction
                        + insert_space
                        + curr_min
                        + opt_per_unit
                    ).optimize()
                branches.append(g)
            return pynini.union(*branches).optimize()

        graph_major_and_minor = _build_major_and_minor(maj_labels, integer, trailing=False)
        graph_suffix_major_and_minor = _build_major_and_minor(maj_labels, integer, trailing=True)

        # CLDR bn places the symbol after the amount (৫০৳, ৫০ ৳, 500 USD); read the same way
        currency_suffix = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' currency_maj: "')
            + currency_graph
            + pynutil.insert('"')
        )
        graph_suffix_symbol = (
            optional_graph_negative + integer + optional_delete_fractional_zeros + currency_suffix + opt_per_unit
        ).optimize()
        graph_suffix_decimal_path = (
            optional_graph_negative
            + pynutil.insert('integer_part: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + currency_suffix
            + opt_per_unit
        ).optimize()

        # Money with scale/quantity word, e.g. ৳২.৫ কোটি -> দুই দশমিক পাঁচ কোটি টাকা, $5 মিলিয়ন -> পাঁচ মিলিয়ন ডলার
        # Also shorthand magnitude suffixes: $50k, €50k, $2.5M, $1.2B, $5T (glued or spaced, prefix or suffix currency)
        qty_num = cardinal_graph | (
            cardinal_graph + pynini.cross(".", " দশমিক ") + single_digit + pynini.closure(insert_space + single_digit)
        )
        mag_shorthand = pynini.string_map(
            [
                ("k", "হাজার"),
                ("K", "হাজার"),
                ("M", "মিলিয়ন"),
                ("B", "বিলিয়ন"),
                ("T", "ট্রিলিয়ন"),
            ]
        )
        qty_suffix = (pynini.accep(" ") + quantities_graph) | (opt_sp + pynutil.insert(" ") + mag_shorthand)
        qty_integer_field = pynutil.insert('integer_part: "') + qty_num + qty_suffix + pynutil.insert('"')

        graph_money_quantity = (
            (optional_graph_negative + currency_major + insert_space + qty_integer_field + opt_per_unit)
            | (optional_graph_negative + qty_integer_field + currency_suffix + opt_per_unit)
        ).optimize()

        # Money ranges with trailing currency: "10-20 $", "10–20 €", "৫০-১০০ টাকা"
        range_dash = opt_sp + pynini.cross(pynini.union("-", "–", "—"), " থেকে ") + opt_sp
        range_int_field = (
            pynutil.insert('integer_part: "')
            + qty_num
            + range_dash
            + qty_num
            + pynutil.insert('"')
        )
        graph_money_range_single_curr = (
            (currency_major + insert_space + range_int_field)
            | (range_int_field + currency_suffix)
        ).optimize()

        positive_curr_only = (
            pynutil.add_weight(
                currency_major + insert_space + pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"') + pynini.cross(".", " ") + guarded_decimal_digits,
                -0.0005,
            )
            | (currency_major + insert_space + integer + optional_delete_fractional_zeros)
            | (currency_major + insert_space + qty_integer_field)
        )
        self.positive_fst = self.add_tokens(
            positive_curr_only | _build_major_and_minor(maj_labels, integer, trailing=False)
        ).optimize()

        graph_currencies = (
            pynutil.add_weight(graph_decimal_path, -0.0005)
            | pynutil.add_weight(graph_suffix_decimal_path, -0.0005)
            | graph_major_only
            | graph_major_and_minor
            | graph_suffix_symbol
            | graph_suffix_major_and_minor
            | pynutil.add_weight(graph_money_quantity, -0.01)
            | pynutil.add_weight(graph_money_range_single_curr, -0.01)
        )

        graph = graph_currencies.optimize()
        self.fst = self.add_tokens(graph)
        # Each endpoint keeps its currency and minor-unit reading.
        repeated_currency_range = (
            self.positive_fst
            + opt_sp
            + pynutil.delete(pynini.union("-", "–", "—"))
            + opt_sp
            + pynutil.insert(' } tokens { name: "থেকে" } tokens { ')
            + self.positive_fst
        )
        self.fst = (self.fst | pynutil.add_weight(repeated_currency_range, -0.01)).optimize()
