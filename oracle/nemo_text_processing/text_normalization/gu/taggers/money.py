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

from nemo_text_processing.text_normalization.gu.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.gu.utils import get_abs_path, load_labels

delete_optional_space = pynini.closure(pynutil.delete(" "), 0, 1)
currency_raw = pynini.string_file(get_abs_path("data/money/currency.tsv"))
currency_singular_raw = pynini.string_file(get_abs_path("data/money/currency_singular.tsv"))
currency_graph = currency_raw + delete_optional_space
currency_singular_graph = currency_singular_raw + delete_optional_space
quantities = pynini.string_file(get_abs_path("data/numbers/thousands.tsv"))
intl_shorthand = pynini.string_map(
    [
        ("k", "હજાર"),
        ("K", "હજાર"),
        ("M", "દસ લાખ"),
        ("m", "દસ લાખ"),
        ("B", "અબજ"),
        ("bn", "અબજ"),
        ("T", "ખરબ"),
    ]
)

_PER_UNITS = [
    ("/કલાક", "પ્રતિ કલાક"),
    ("/h", "પ્રતિ કલાક"),
    ("/hr", "પ્રતિ કલાક"),
    ("/મિનિટ", "પ્રતિ મિનિટ"),
    ("/min", "પ્રતિ મિનિટ"),
    ("/સેકન્ડ", "પ્રતિ સેકન્ડ"),
    ("/s", "પ્રતિ સેકન્ડ"),
    ("/દિવસ", "પ્રતિ દિવસ"),
    ("/d", "પ્રતિ દિવસ"),
    ("/અઠવાડિયું", "પ્રતિ અઠવાડિયું"),
    ("/wk", "પ્રતિ અઠવાડિયું"),
    ("/મહિનો", "પ્રતિ મહિનો"),
    ("/mo", "પ્રતિ મહિનો"),
    ("/વર્ષ", "પ્રતિ વર્ષ"),
    ("/yr", "પ્રતિ વર્ષ"),
    ("/kg", "પ્રતિ કિલોગ્રામ"),
    ("/કિગ્રા", "પ્રતિ કિલોગ્રામ"),
    ("/g", "પ્રતિ ગ્રામ"),
    ("/t", "પ્રતિ ટન"),
    ("/l", "પ્રતિ લિટર"),
    ("/L", "પ્રતિ લિટર"),
    ("/ml", "પ્રતિ મિલિલિટર"),
    ("/mL", "પ્રતિ મિલિલિટર"),
    ("/m", "પ્રતિ મીટર"),
    ("/km", "પ્રતિ કિલોમીટર"),
    ("/m²", "પ્રતિ ચોરસ મીટર"),
    ("/m2", "પ્રતિ ચોરસ મીટર"),
    ("/m³", "પ્રતિ ઘન મીટર"),
    ("/m3", "પ્રતિ ઘન મીટર"),
    ("/ft²", "પ્રતિ ચોરસ ફૂટ"),
    ("/ac", "પ્રતિ એકર"),
    ("/kWh", "પ્રતિ કિલોવૉટ કલાક"),
]


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money in Gujarati, e.g.
        ₹૫૦ -> money { currency_maj: "રૂપિયા" integer_part: "પચાસ" }
        ₹૫૦.૫૦ -> money { currency_maj: "રૂપિયા" integer_part: "પચાસ" fractional_part: "પચાસ" currency_min: "પૈસા" }
        ₹૦.૫૦ -> money { currency_maj: "રૂપિયા" integer_part: "શૂન્ય" fractional_part: "પચાસ" currency_min: "પૈસા" }

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.final_graph

        _ascii_to_gu_digit = pynini.string_map([(str(i), "૦૧૨૩૪૫૬૭૮૯"[i]) for i in range(10)])
        _gu_to_ascii = pynini.invert(_ascii_to_gu_digit)
        gu_to_ascii = pynini.closure(_gu_to_ascii | pynini.union(*"0123456789"), 1)

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _gu_nonzero = pynini.union(*"૧૨૩૪૫૬૭૮૯")
        _any_digit = _ascii_digit | pynini.union(*"૦૧૨૩૪૫૬૭૮૯")
        _any_nonzero = _ascii_nonzero | _gu_nonzero

        optional_graph_negative = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true"') + insert_space)
            | (pynini.cross("~", 'negative: "આશરે"') + delete_optional_space + insert_space)
            | (pynini.cross("±", 'negative: "વત્તા કે ઓછા"') + delete_optional_space + insert_space),
            0,
            1,
        )
        currency_major = pynutil.insert('currency_maj: "') + currency_graph + pynutil.insert('"')
        currency_major_singular = pynutil.insert('currency_maj: "') + currency_singular_graph + pynutil.insert('"')

        one = pynini.union("1", "૧")
        integer_one = pynutil.insert('integer_part: "') + (one @ cardinal_graph) + pynutil.insert('"')
        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')

        strip_trailing_zeros = pynini.closure(_ascii_digit) + _ascii_nonzero + pynini.closure(pynutil.delete("0"))
        canonicalise = (
            (pynutil.delete("0") + _ascii_nonzero)
            | (_ascii_nonzero + pynutil.insert("0"))
            | (_ascii_nonzero + _ascii_digit)
        )
        two_digits_fractional_part = gu_to_ascii @ strip_trailing_zeros @ canonicalise

        fraction = (
            pynutil.insert('fractional_part: "') + (two_digits_fractional_part @ cardinal_graph) + pynutil.insert('"')
        )

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynini.closure(pynutil.delete("0") | pynutil.delete("૦"), 1),
            0,
            1,
        )

        has_3plus_sig_digits = _any_digit + _any_digit + pynini.closure(_any_digit) + _any_nonzero + pynini.closure(_any_digit)
        single_digit = _any_digit @ cardinal.single_digits_graph
        decimal_digits = (
            pynutil.insert('fractional_part: "')
            + single_digit
            + pynini.closure(insert_space + single_digit)
            + pynutil.insert('"')
        )
        guarded_decimal_digits = has_3plus_sig_digits @ decimal_digits

        graph_decimal_path = (
            currency_major
            + insert_space
            + pynutil.insert('integer_part: "')
            + cardinal_graph
            + pynutil.insert('"')
            + pynini.cross(".", " ")
            + guarded_decimal_digits
        ).optimize()

        graph_major_only_singular = (
            currency_major_singular + insert_space + integer_one + optional_delete_fractional_zeros
        ).optimize()

        graph_major_only = (currency_major + insert_space + integer + optional_delete_fractional_zeros).optimize()

        range_sep = delete_optional_space + pynini.cross(pynini.union("-", "–", "—"), " થી ") + delete_optional_space
        range_amount = (
            cardinal_graph
            + pynini.closure(
                pynini.cross(".", " દશાંશ ") + single_digit + pynini.closure(insert_space + single_digit),
                0,
                1,
            )
        ).optimize()
        range_integer = (
            pynutil.insert('integer_part: "')
            + range_amount
            + range_sep
            + range_amount
            + pynutil.insert('"')
        ).optimize()
        graph_range_leading = (currency_major + insert_space + range_integer).optimize()

        all_quantities = (quantities | intl_shorthand).optimize()
        quantity_part = delete_optional_space + insert_space + all_quantities
        decimal_with_quantity = (
            cardinal.graph_without_leading_zeros
            + pynini.cross(".", " દશાંશ ")
            + single_digit
            + pynini.closure(insert_space + single_digit)
            + quantity_part
        )
        cardinal_with_quantity = cardinal.graph_without_leading_zeros + quantity_part
        graph_quantity_money = (
            currency_major
            + insert_space
            + pynutil.insert('integer_part: "')
            + (decimal_with_quantity | cardinal_with_quantity)
            + pynutil.insert('"')
        ).optimize()

        maj_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        maj_singular_labels = load_labels(get_abs_path("data/money/currency_singular.tsv"))
        maj_to_min = dict(load_labels(get_abs_path("data/money/major_minor_currencies.tsv")))

        symbols_by_major = {}
        for symbol, major in maj_labels:
            symbols_by_major.setdefault(major, []).append(symbol)
        repeated_currency_ranges = []
        for major, symbols in symbols_by_major.items():
            repeated_currency_ranges.append(
                pynutil.insert('currency_maj: "')
                + pynini.string_map([(symbol, major) for symbol in symbols])
                + delete_optional_space
                + pynutil.insert('" integer_part: "')
                + range_amount
                + range_sep
                + pynutil.delete(pynini.union(*symbols))
                + delete_optional_space
                + range_amount
                + pynutil.insert('"')
            )
        graph_repeated_range = pynini.union(*repeated_currency_ranges).optimize()

        def _build_major_and_minor(sym_maj_labels, int_graph):
            by_min = {}
            for sym, maj in sym_maj_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_min.setdefault(min_name, []).append((sym, maj))
            parts = []
            for min_name, pairs in by_min.items():
                curr_maj = (
                    pynutil.insert('currency_maj: "')
                    + pynini.string_map(pairs)
                    + delete_optional_space
                    + pynutil.insert('"')
                )
                curr_min = pynutil.insert(f'currency_min: "{min_name}"')
                parts.append(
                    (
                        curr_maj
                        + insert_space
                        + int_graph
                        + pynini.cross(".", " ")
                        + fraction
                        + insert_space
                        + curr_min
                    ).optimize()
                )
            return pynini.union(*parts).optimize()

        graph_major_and_minor = _build_major_and_minor(maj_labels, integer)
        graph_major_and_minor_singular = _build_major_and_minor(maj_singular_labels, integer_one)

        currency_suffix = (
            delete_optional_space + pynutil.insert(' currency_maj: "') + currency_raw + pynutil.insert('"')
        )
        currency_suffix_singular = (
            delete_optional_space + pynutil.insert(' currency_maj: "') + currency_singular_raw + pynutil.insert('"')
        )
        graph_suffix_only = (integer + optional_delete_fractional_zeros + currency_suffix).optimize()
        graph_suffix_only_singular = (
            integer_one + optional_delete_fractional_zeros + currency_suffix_singular
        ).optimize()
        graph_suffix_range = (range_integer + currency_suffix).optimize()
        graph_suffix_quantity = (
            pynutil.insert('integer_part: "')
            + (decimal_with_quantity | cardinal_with_quantity)
            + pynutil.insert('"')
            + currency_suffix
        ).optimize()
        graph_suffix_decimal = (
            integer + pynini.cross(".", " ") + guarded_decimal_digits + currency_suffix
        ).optimize()

        def _build_suffix_major_and_minor(sym_maj_labels, int_graph):
            by_min = {}
            for sym, maj in sym_maj_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_min.setdefault(min_name, []).append((sym, maj))
            parts = []
            for min_name, pairs in by_min.items():
                curr_suffix = (
                    delete_optional_space
                    + pynutil.insert(' currency_maj: "')
                    + pynini.string_map(pairs)
                    + pynutil.insert(f'" currency_min: "{min_name}"')
                )
                parts.append((int_graph + pynini.cross(".", " ") + fraction + curr_suffix).optimize())
            return pynini.union(*parts).optimize()

        graph_suffix_major_and_minor = _build_suffix_major_and_minor(maj_labels, integer)
        graph_suffix_major_and_minor_singular = _build_suffix_major_and_minor(maj_singular_labels, integer_one)

        per_unit = (
            delete_optional_space
            + pynutil.insert(' morphosyntactic_features: "')
            + pynini.string_map(_PER_UNITS).optimize()
            + pynutil.insert('"')
        )
        optional_per = pynini.closure(per_unit, 0, 1)

        pos_currencies = (
            pynutil.add_weight(
                graph_major_only_singular
                | graph_major_and_minor_singular
                | graph_suffix_only_singular
                | graph_suffix_major_and_minor_singular,
                -0.001,
            )
            | pynutil.add_weight(
                graph_decimal_path
                | graph_suffix_decimal
                | graph_quantity_money
                | graph_suffix_quantity
                | graph_range_leading
                | graph_suffix_range
                | graph_repeated_range,
                -0.0005,
            )
            | graph_major_only
            | graph_major_and_minor
            | graph_suffix_only
            | graph_suffix_major_and_minor
        ) + optional_per

        self.positive_fst = self.add_tokens(pos_currencies).optimize()
        graph = (optional_graph_negative + pos_currencies).optimize()
        self.fst = self.add_tokens(graph).optimize()
