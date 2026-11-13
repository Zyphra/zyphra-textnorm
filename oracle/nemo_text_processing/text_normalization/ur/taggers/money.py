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

from nemo_text_processing.text_normalization.ur.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.ur.utils import get_abs_path, load_labels

_PER_UNIT_MAP = [
    ("h", "فی گھنٹہ"),
    ("hr", "فی گھنٹہ"),
    ("hrs", "فی گھنٹہ"),
    ("hour", "فی گھنٹہ"),
    ("min", "فی منٹ"),
    ("s", "فی سیکنڈ"),
    ("sec", "فی سیکنڈ"),
    ("d", "فی دن"),
    ("day", "فی دن"),
    ("wk", "فی ہفتہ"),
    ("week", "فی ہفتہ"),
    ("mo", "فی مہینہ"),
    ("month", "فی مہینہ"),
    ("yr", "فی سال"),
    ("y", "فی سال"),
    ("year", "فی سال"),
    ("kg", "فی کلو گرام"),
    ("g", "فی گرام"),
    ("mg", "فی ملی گرام"),
    ("t", "فی ٹن"),
    ("lb", "فی پونڈ"),
    ("oz", "فی اونس"),
    ("L", "فی لیٹر"),
    ("l", "فی لیٹر"),
    ("mL", "فی ملی لیٹر"),
    ("ml", "فی ملی لیٹر"),
    ("m", "فی میٹر"),
    ("km", "فی کلومیٹر"),
    ("m²", "فی مربع میٹر"),
    ("m2", "فی مربع میٹر"),
    ("m³", "فی کیوبک میٹر"),
    ("m3", "فی کیوبک میٹر"),
    ("kWh", "فی کلو واٹ آور"),
    ("unit", "فی یونٹ"),
]
# A currency symbol or code may be followed by one space ("Rs 500", "PKR 1,200").
_optional_space = pynini.closure(pynutil.delete(" "), 0, 1)
_raw_currency = pynini.string_file(get_abs_path("data/money/currency.tsv"))
_raw_currency_singular = pynini.string_file(get_abs_path("data/money/currency_singular.tsv"))
currency_graph = _raw_currency + _optional_space
currency_singular_graph = _raw_currency_singular + _optional_space
_trailing_currency_major = _optional_space + pynutil.insert('currency_maj: "') + _raw_currency + pynutil.insert('"')
_trailing_currency_major_singular = (
    _optional_space + pynutil.insert('currency_maj: "') + _raw_currency_singular + pynutil.insert('"')
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, suppletive aware, e.g.
        ₨50 -> money { currency_maj: "روپے" integer_part: "پچاس" }
        Rs 50.50 -> money { currency_maj: "روپے" integer_part: "پچاس" fractional_part: "پچاس" currency_min: "پیسے" }
        ₨0.50 -> { money { currency_maj: "روپے" integer_part: "صفر" fractional_part: "پچاس" currency_min: "پیسے" }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.final_graph

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _any_digit = _ascii_digit
        _any_nonzero = _ascii_nonzero

        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", '"true"') + insert_space,
            0,
            1,
        )

        currency_major = pynutil.insert('currency_maj: "') + currency_graph + pynutil.insert('"')
        currency_major_singular = pynutil.insert('currency_maj: "') + currency_singular_graph + pynutil.insert('"')

        one = pynini.accep("1")
        integer_one = pynutil.insert('integer_part: "') + (one @ cardinal_graph) + pynutil.insert('"')
        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')

        strip_trailing_zeros = pynini.closure(_ascii_digit) + _ascii_nonzero + pynini.closure(pynutil.delete("0"))
        canonicalise = (
            (pynutil.delete("0") + _ascii_nonzero)
            | (_ascii_nonzero + pynutil.insert("0"))
            | (_ascii_nonzero + _ascii_digit)
        )
        two_digits_fractional_part = strip_trailing_zeros @ canonicalise

        fraction = (
            pynutil.insert('fractional_part: "') + (two_digits_fractional_part @ cardinal_graph) + pynutil.insert('"')
        )

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynini.closure(pynutil.delete("0"), 1),
            0,
            1,
        )

        # Use decimal digits whenever a nonzero digit occurs beyond the
        # currency's two-place minor amount, including values such as 0.0001.
        has_3plus_sig_digits = _any_digit**2 + pynini.closure(_any_digit) + _any_nonzero + pynini.closure(_any_digit)
        single_digit = _any_digit @ cardinal.single_digits_graph
        decimal_digits = (
            pynutil.insert('fractional_part: "')
            + single_digit
            + pynini.closure(insert_space + single_digit)
            + pynutil.insert('"')
        )
        guarded_decimal_digits = has_3plus_sig_digits @ decimal_digits

        graph_decimal_path = (
            optional_graph_negative
            + currency_major
            + insert_space
            + pynutil.insert('integer_part: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynini.cross(".", " ")
            + guarded_decimal_digits
        ).optimize()

        graph_major_only_singular = (
            optional_graph_negative
            + currency_major_singular
            + insert_space
            + integer_one
            + optional_delete_fractional_zeros
        ).optimize()

        graph_major_only = (
            optional_graph_negative + currency_major + insert_space + integer + optional_delete_fractional_zeros
        ).optimize()

        maj_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        maj_singular_labels = load_labels(get_abs_path("data/money/currency_singular.tsv"))
        maj_to_min = dict(load_labels(get_abs_path("data/money/major_minor_currencies.tsv")))

        def _build_major_and_minor(sym_maj_labels, int_graph):
            by_pair = defaultdict(list)
            for sym, maj in sym_maj_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_pair[(maj, min_name)].append(sym)

            amount = (int_graph + pynini.cross(".", " ") + fraction).optimize()
            graphs = []
            for (maj, min_name), syms in by_pair.items():
                sym_union = pynini.union(*syms)
                curr_maj = pynutil.insert(f'currency_maj: "{maj}"') + pynutil.delete(sym_union) + _optional_space
                curr_min = pynutil.insert(f'currency_min: "{min_name}"')
                graphs.append(optional_graph_negative + curr_maj + insert_space + amount + insert_space + curr_min)
                graphs.append(
                    optional_graph_negative
                    + amount
                    + _optional_space
                    + pynutil.insert(f' currency_maj: "{maj}" currency_min: "{min_name}"')
                    + pynutil.delete(sym_union)
                )
            return pynini.union(*graphs).optimize()

        graph_trailing_major_only_singular = (
            optional_graph_negative
            + integer_one
            + optional_delete_fractional_zeros
            + insert_space
            + _trailing_currency_major_singular
        ).optimize()

        graph_trailing_major_only = (
            optional_graph_negative
            + integer
            + optional_delete_fractional_zeros
            + insert_space
            + _trailing_currency_major
        ).optimize()

        graph_trailing_decimal_path = (
            optional_graph_negative
            + pynutil.insert('integer_part: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + insert_space
            + _trailing_currency_major
        ).optimize()

        # Magnitude shorthand: "$50k", "€50k", "$2.5M", "$1.2B"
        mag_map = pynini.string_map(
            [
                ("k", "ہزار"),
                ("K", "ہزار"),
                ("M", "ملین"),
                ("m", "ملین"),
                ("B", "ارب"),
                ("b", "ارب"),
                ("T", "ٹریلین"),
            ]
        )
        short_num = cardinal_graph | (
            cardinal_graph + pynini.cross(".", " اعشاریہ ") + single_digit + pynini.closure(insert_space + single_digit)
        )
        shorthand_int = (
            pynutil.insert('integer_part: "')
            + short_num
            + _optional_space
            + insert_space
            + mag_map
            + pynutil.insert('"')
        ).optimize()
        graph_shorthand_lead = (optional_graph_negative + currency_major + insert_space + shorthand_int).optimize()
        graph_shorthand_trail = (
            optional_graph_negative + shorthand_int + insert_space + _trailing_currency_major
        ).optimize()

        graph_major_and_minor = _build_major_and_minor(maj_labels, integer)
        graph_major_and_minor_singular = _build_major_and_minor(maj_singular_labels, integer_one)

        base_currencies = (
            pynutil.add_weight(
                graph_major_only_singular | graph_trailing_major_only_singular | graph_major_and_minor_singular, -0.001
            )
            | pynutil.add_weight(graph_decimal_path | graph_trailing_decimal_path, -0.0005)
            | pynutil.add_weight(graph_shorthand_lead | graph_shorthand_trail, -0.0005)
            | graph_major_only
            | graph_trailing_major_only
            | graph_major_and_minor
        ).optimize()

        per_unit_graph = (
            _optional_space
            + pynutil.delete("/")
            + _optional_space
            + pynutil.insert(' morphosyntactic_features: "')
            + pynini.string_map(_PER_UNIT_MAP)
            + pynutil.insert('"')
        ).optimize()

        # Money ranges: "$10-$20", "$10–$20", "$10-20", "10-20 €", "10-20 USD"
        dash = pynini.union("-", "–", " - ", " – ")
        range_amt = (
            short_num + pynini.closure(_optional_space + insert_space + mag_map, 0, 1)
        ).optimize()

        by_maj = defaultdict(list)
        sign_by_maj = defaultdict(list)
        for sym, maj in maj_labels:
            by_maj[maj].append(sym)
            if not sym.isalpha():
                sign_by_maj[maj].append(sym)

        # Both endpoints must name the same currency; never silently discard
        # the first currency in a mixed-currency expression.
        both_pre_range = pynini.union(
            *[
                pynutil.delete(pynini.union(*syms) + pynini.closure(" ", 0, 1))
                + pynutil.insert('integer_part: "')
                + range_amt
                + pynini.cross(dash, " سے ")
                + pynutil.delete(pynini.union(*syms) + pynini.closure(" ", 0, 1))
                + range_amt
                + pynutil.insert(f'" currency_maj: "{maj}"')
                for maj, syms in by_maj.items()
            ]
        ).optimize()

        left_pre_branches = [
            pynutil.delete(pynini.union(*syms) + pynini.closure(" ", 0, 1))
            + pynutil.insert('integer_part: "')
            + range_amt
            + pynini.cross(dash, " سے ")
            + range_amt
            + pynutil.insert(f'" currency_maj: "{maj}"')
            for maj, syms in sign_by_maj.items()
        ]
        left_pre_range = pynini.union(*left_pre_branches).optimize()

        suf_range = (
            pynutil.insert('integer_part: "')
            + range_amt
            + pynini.cross(dash, " سے ")
            + range_amt
            + pynutil.insert('" ')
            + _trailing_currency_major
        ).optimize()

        money_range_graph = pynutil.add_weight(both_pre_range | left_pre_range | suf_range, -0.01).optimize()

        money_amount = (base_currencies | money_range_graph).optimize()
        graph = (
            money_amount
            | pynutil.add_weight(money_amount + per_unit_graph, -0.01)
        ).optimize()
        self.fst = self.add_tokens(graph)
