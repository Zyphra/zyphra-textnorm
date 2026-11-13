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
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.pa.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.pa.utils import get_abs_path, load_labels

currency_graph = pynini.string_file(get_abs_path("data/money/currency.tsv"))
quantities_graph = pynini.string_file(get_abs_path("data/numbers/quantities.tsv"))


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money in Punjabi, e.g.
        ₹੫੦ -> money { currency_maj: "ਰੁਪਏ" integer_part: "ਪੰਜਾਹ" }
        ₹੫੦.੫੦ -> money { currency_maj: "ਰੁਪਏ" integer_part: "ਪੰਜਾਹ" fractional_part: "ਪੰਜਾਹ" currency_min: "ਪੈਸੇ" }
        ₹੦.੫੦ -> money { currency_maj: "ਰੁਪਏ" integer_part: "ਸਿਫ਼ਰ" fractional_part: "ਪੰਜਾਹ" currency_min: "ਪੈਸੇ" }
        ੫੦੦₹ / Rs 50 -> money { currency_maj: "ਰੁਪਏ" integer_part: "ਪੰਜਾਹ" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.final_graph

        _pa_to_ascii = pynini.union(*[pynini.cross(b, a) for b, a in zip("੦੧੨੩੪੫੬੭੮੯", "0123456789")])
        pa_to_ascii = pynini.closure(_pa_to_ascii | pynini.union(*"0123456789"), 1)

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _pa_nonzero = pynini.union(*"੧੨੩੪੫੬੭੮੯")
        _any_digit = _ascii_digit | pynini.union(*"੦੧੨੩੪੫੬੭੮੯")
        _any_nonzero = _ascii_nonzero | _pa_nonzero

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

        delete_symbol_sep = pynini.closure(pynutil.delete(pynini.union(" ", ". ", ".")), 0, 1)
        currency_major = pynutil.insert('currency_maj: "') + currency_graph + pynutil.insert('"') + delete_symbol_sep

        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')

        # Singular 1 agreement: 1 -> ਰੁਪਇਆ
        one_num = pynini.union("1", "੧")
        one_currency_major = pynini.string_map([
            ("₹", "ਰੁਪਇਆ"), ("ਰੁ.", "ਰੁਪਇਆ"), ("ਰੁ", "ਰੁਪਇਆ"), ("Rs.", "ਰੁਪਇਆ"), ("Rs", "ਰੁਪਇਆ"), ("INR", "ਰੁਪਇਆ"),
        ])
        one_major = pynutil.insert('currency_maj: "') + one_currency_major + pynutil.insert('"') + delete_symbol_sep
        integer_one = pynutil.insert('integer_part: "') + (one_num @ cardinal_graph) + pynutil.insert('"')
        graph_major_one = one_major + insert_space + integer_one

        strip_trailing_zeros = pynini.closure(_ascii_digit) + _ascii_nonzero + pynini.closure(pynutil.delete("0"))
        canonicalise = (
            (pynutil.delete("0") + _ascii_nonzero)
            | (_ascii_nonzero + pynutil.insert("0"))
            | (_ascii_nonzero + _ascii_digit)
        )
        two_digits_fractional_part = pa_to_ascii @ strip_trailing_zeros @ canonicalise

        fraction = (
            pynutil.insert('fractional_part: "') + (two_digits_fractional_part @ cardinal_graph) + pynutil.insert('"')
        )

        graph_decimal_digits = pynutil.insert('fractional_part: "') + (cardinal.single_digits_graph) + pynutil.insert('"')
        guarded_decimal_digits = pynini.compose(
            pynini.closure(_any_digit),
            graph_decimal_digits,
        )

        maj_labels = load_labels(get_abs_path("data/money/major_minor_currencies.tsv"))

        def _build_major_and_minor(maj_labels, int_graph, trailing=False):
            components = []
            for major, minor in maj_labels:
                matching_symbols = []
                with open(get_abs_path("data/money/currency.tsv"), "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split("\t")
                        if len(parts) == 2 and parts[1] == major:
                            matching_symbols.append(parts[0])

                if not matching_symbols:
                    continue

                symbols = pynini.union(*matching_symbols)
                maj_tag = pynutil.insert(f'currency_maj: "{major}"')
                min_tag = pynutil.insert(f'currency_min: "{minor}"')

                if trailing:
                    c = (
                        int_graph
                        + pynutil.delete(pynini.union(".", ","))
                        + insert_space
                        + fraction
                        + insert_space
                        + pynutil.delete(symbols)
                        + maj_tag
                        + insert_space
                        + min_tag
                    )
                else:
                    c = (
                        pynutil.delete(symbols)
                        + delete_symbol_sep
                        + maj_tag
                        + insert_space
                        + int_graph
                        + pynutil.delete(pynini.union(".", ","))
                        + insert_space
                        + fraction
                        + insert_space
                        + min_tag
                    )
                components.append(c)
            return pynini.union(*components)

        graph_major_and_minor = _build_major_and_minor(maj_labels, integer, trailing=False)

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(pynini.union(".", ",")) + pynutil.delete(pynini.closure(pynini.union("0", "੦"), 1)),
            0,
            1,
        )

        graph_major_only = pynutil.add_weight(graph_major_one, -0.001) | (currency_major + insert_space + integer + optional_delete_fractional_zeros)

        # Quantity numbers: 2.5 ਲੱਖ ਰੁਪਏ, ₹2.5 ਲੱਖ
        qty_num = (
            cardinal_graph
            | (cardinal_graph + pynini.cross(".", " ਦਸ਼ਮਲਵ ") + cardinal.single_digits_graph)
        )
        qty_integer_field = (
            pynutil.insert('integer_part: "')
            + qty_num
            + pynini.closure(pynutil.delete(" ")) + insert_space
            + quantities_graph
            + pynutil.insert('"')
        )
        graph_money_quantity = (
            (currency_major + insert_space + qty_integer_field)
            | (qty_integer_field + pynini.closure(pynutil.delete(" ")) + insert_space + currency_major)
        )

        # Suffix currency symbol: 500₹
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        currency_suffix = opt_space + pynutil.insert(' currency_maj: "') + currency_graph + pynutil.insert('"')
        graph_suffix_symbol = integer + optional_delete_fractional_zeros + currency_suffix
        graph_suffix_major_and_minor = _build_major_and_minor(maj_labels, integer, trailing=True)

        graph_decimal_path = (
            currency_major
            + insert_space
            + pynutil.insert('integer_part: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynini.cross(".", " ")
            + guarded_decimal_digits
        )
        graph_suffix_decimal_path = (
            pynutil.insert('integer_part: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + currency_suffix
        )

        graph_currencies = (
            pynutil.add_weight(graph_decimal_path, -0.0005)
            | pynutil.add_weight(graph_suffix_decimal_path, -0.0005)
            | graph_major_only
            | graph_major_and_minor
            | graph_suffix_symbol
            | graph_suffix_major_and_minor
            | pynutil.add_weight(graph_money_quantity, -0.01)
        )

        per_unit = pynini.closure(
            opt_space + pynutil.delete("/") + pynutil.insert(' morphosyntactic_features: "')
            + pynini.string_map([("kg", "ਪ੍ਰਤੀ ਕਿਲੋਗ੍ਰਾਮ"), ("h", "ਪ੍ਰਤੀ ਘੰਟਾ"), ("hr", "ਪ੍ਰਤੀ ਘੰਟਾ")])
            + pynutil.insert('"'), 0, 1,
        )
        graph = optional_graph_negative + graph_currencies.optimize() + per_unit
        self.fst = self.add_tokens(graph)

        # Repeated / mixed currency range: $10-€20 -> ਦਸ ਡਾਲਰ ਤੋਂ ਵੀਹ ਯੂਰੋ
        repeated_currency_range = (
            self.fst
            + opt_space
            + pynutil.delete(pynini.union("-", "–", "—"))
            + opt_space
            + pynutil.insert(' } tokens { name: "ਤੋਂ" } tokens { ')
            + self.fst
        )
        self.fst = (self.fst | pynutil.add_weight(repeated_currency_range, -0.01)).optimize()
