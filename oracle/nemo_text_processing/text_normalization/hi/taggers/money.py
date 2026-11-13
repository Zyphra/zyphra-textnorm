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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.hi.graph_utils import (
    MINUS,
    NEMO_SPACE,
    GraphFst,
    convert_space,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.hi.utils import get_abs_path, load_labels

currency_graph = pynini.string_file(get_abs_path("data/money/currency.tsv"))
currency_singular_graph = pynini.string_file(get_abs_path("data/money/currency_singular.tsv"))
quantities_graph = pynini.project(pynini.string_file(get_abs_path("data/numbers/thousands.tsv")), "output")

class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, suppletive aware, e.g.
        ₹५० -> money { currency_maj: "रुपए" integer_part: "पचास" }
        ₹५०.५० -> money { currency_maj: "रुपए" integer_part: "पचास" fractional_part: "पचास" currency_min: "पैसे" }
        ₹०.५० -> { money { currency_maj: "रुपए" integer_part: "शून्य" fractional_part: "पचास" currency_min: "पैसे" }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.final_graph

        _en_to_hi_digit = pynini.string_file(get_abs_path("data/ordinal/en_to_hi_digit.tsv"))
        _deva_to_ascii = pynini.invert(_en_to_hi_digit)
        deva_to_ascii = pynini.closure(_deva_to_ascii | pynini.union(*"0123456789"), 1)

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _deva_nonzero = pynini.union(*"१२३४५६७८९")
        _any_digit = _ascii_digit | pynini.union(*"०१२३४५६७८९")
        _any_nonzero = _ascii_nonzero | _deva_nonzero

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ")
            + (
                pynini.cross(pynini.union("-", "−"), '"true"')
                | pynini.cross(pynini.union("~", "≈") + opt_sp, '"approx"')
                | pynini.cross(pynini.accep("±") + opt_sp, '"plus_minus"')
            )
            + insert_space,
            0,
            1,
        )

        currency_major = pynutil.insert('currency_maj: "') + currency_graph + pynutil.insert('"')
        currency_major_singular = pynutil.insert('currency_maj: "') + currency_singular_graph + pynutil.insert('"')

        one = pynini.union("1", "१")
        integer_one = pynutil.insert('integer_part: "') + (one @ cardinal_graph) + pynutil.insert('"')
        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')
        cardinal_minor_limit = pynini.compose(pynini.closure(_any_digit | pynini.accep(","), 1, 13), cardinal_graph).optimize()
        integer_for_minor = pynutil.insert('integer_part: "') + cardinal_minor_limit + pynutil.insert('"')

        strip_trailing_zeros = pynini.closure(_ascii_digit) + _ascii_nonzero + pynini.closure(pynutil.delete("0"))
        canonicalise = (
            (pynutil.delete("0") + _ascii_nonzero)
            | (_ascii_nonzero + pynutil.insert("0"))
            | (_ascii_nonzero + _ascii_digit)
        )
        two_digits_fractional_part = deva_to_ascii @ strip_trailing_zeros @ canonicalise

        fraction = (
            pynutil.insert('fractional_part: "') + (two_digits_fractional_part @ cardinal_graph) + pynutil.insert('"')
        )

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynini.closure(pynutil.delete("0") | pynutil.delete("०"), 1),
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

        # opt_sp defined above

        graph_decimal_path = (
            optional_graph_negative
            + currency_major
            + opt_sp
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
            + opt_sp
            + insert_space
            + integer_one
            + optional_delete_fractional_zeros
        ).optimize()

        graph_major_only = (
            optional_graph_negative
            + currency_major
            + opt_sp
            + insert_space
            + integer
            + optional_delete_fractional_zeros
        ).optimize()

        iso_plural = pynini.string_map(
            [
                ("INR", "रुपए"),
                ("Rs", "रुपए"),
                ("Rs.", "रुपए"),
                ("USD", "अमेरिकी डॉलर"),
                ("EUR", "यूरो"),
                ("GBP", "ब्रिटिश पाउंड"),
                ("JPY", "जापानी येन"),
                ("CNY", "चीनी युआन"),
                ("AUD", "ऑस्ट्रेलियाई डॉलर"),
                ("CAD", "कनाडाई डॉलर"),
                ("SGD", "सिंगापुर डॉलर"),
                ("CHF", "स्विस फ़्रैंक"),
                ("RUB", "रूसी रूबल"),
                ("AED", "दिरहम"),
                ("SAR", "रियाल"),
                ("KRW", "वॉन"),
                ("TRY", "लीरा"),
                ("BDT", "टका"),
                ("NGN", "नाइरा"),
                ("PKR", "पाकिस्तानी रुपए"),
            ]
        )
        iso_singular = pynini.string_map(
            [
                ("INR", "रुपया"),
                ("Rs", "रुपया"),
                ("Rs.", "रुपया"),
                ("USD", "अमेरिकी डॉलर"),
                ("EUR", "यूरो"),
                ("GBP", "ब्रिटिश पाउंड"),
                ("JPY", "जापानी येन"),
                ("CNY", "चीनी युआन"),
                ("AUD", "ऑस्ट्रेलियाई डॉलर"),
                ("CAD", "कनाडाई डॉलर"),
                ("SGD", "सिंगापुर डॉलर"),
                ("CHF", "स्विस फ़्रैंक"),
                ("RUB", "रूसी रूबल"),
                ("AED", "दिरहम"),
                ("SAR", "रियाल"),
                ("KRW", "वॉन"),
                ("TRY", "लीरा"),
                ("BDT", "टका"),
                ("NGN", "नाइरा"),
                ("PKR", "पाकिस्तानी रुपया"),
            ]
        )

        extra_iso_labels = [
            ("NZD", "न्यूज़ीलैंड डॉलर"),
            ("HKD", "हांगकांग डॉलर"),
            ("TWD", "नया ताइवान डॉलर"),
            ("BRL", "ब्राज़ीलियाई रियाल"),
            ("MXN", "मेक्सिकन पेसो"),
            ("ILS", "शेकेल"),
            ("UAH", "ह्रिव्निया"),
            ("VND", "डोंग"),
            ("PHP", "पेसो"),
            ("THB", "बात"),
            ("AMD", "द्राम"),
            ("GHS", "सेडी"),
        ]
        extra_iso = pynini.string_map(extra_iso_labels)
        iso_plural |= extra_iso
        iso_singular |= extra_iso

        iso_curr_maj = pynutil.insert('currency_maj: "') + iso_plural + pynutil.insert('"')
        iso_curr_maj_sg = pynutil.insert('currency_maj: "') + iso_singular + pynutil.insert('"')

        graph_iso_leading = (
            optional_graph_negative
            + iso_curr_maj
            + opt_sp
            + insert_space
            + integer
            + optional_delete_fractional_zeros
        ) | pynutil.add_weight(
            optional_graph_negative
            + iso_curr_maj_sg
            + opt_sp
            + insert_space
            + integer_one
            + optional_delete_fractional_zeros,
            -0.001,
        )

        trailing_curr = currency_graph | iso_plural
        trailing_curr_sg = currency_singular_graph | iso_singular
        trailing_maj = pynutil.insert('currency_maj: "') + trailing_curr + pynutil.insert('"')
        trailing_maj_sg = pynutil.insert('currency_maj: "') + trailing_curr_sg + pynutil.insert('"')

        graph_trailing = (
            optional_graph_negative
            + integer
            + optional_delete_fractional_zeros
            + opt_sp
            + insert_space
            + trailing_maj
            + pynutil.insert(" preserve_order: true")
        ) | pynutil.add_weight(
            optional_graph_negative
            + integer_one
            + optional_delete_fractional_zeros
            + opt_sp
            + insert_space
            + trailing_maj_sg
            + pynutil.insert(" preserve_order: true"),
            -0.001,
        )

        # Money with Indian scale word, e.g. ₹2.5 करोड़ -> दो दशमलव पाँच करोड़ रुपए, ₹5 करोड़ -> पाँच करोड़ रुपए
        qty_num = cardinal_graph | (cardinal_graph + pynini.cross(".", " दशमलव ") + single_digit + pynini.closure(insert_space + single_digit))
        graph_money_quantity = (
            optional_graph_negative
            + (currency_major | (iso_curr_maj + opt_sp))
            + opt_sp
            + insert_space
            + pynutil.insert('integer_part: "')
            + qty_num
            + pynini.accep(" ")
            + quantities_graph
            + pynutil.insert('"')
        ).optimize()

        range_dash = opt_sp + pynini.cross(pynini.union("-", "–", "—"), " से ") + opt_sp
        range_int_field = (
            pynutil.insert('integer_part: "')
            + convert_space(qty_num + range_dash + qty_num)
            + pynutil.insert('"')
        )
        graph_money_range_single_curr = (
            (optional_graph_negative + (currency_major | iso_curr_maj) + opt_sp + insert_space + range_int_field)
            | (optional_graph_negative + range_int_field + opt_sp + insert_space + trailing_maj + pynutil.insert(" preserve_order: true"))
        ).optimize()

        maj_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        maj_singular_labels = load_labels(get_abs_path("data/money/currency_singular.tsv"))
        iso_pl_labels = [
            ("INR", "रुपए"),
            ("Rs", "रुपए"),
            ("Rs.", "रुपए"),
            ("USD", "अमेरिकी डॉलर"),
            ("EUR", "यूरो"),
            ("GBP", "ब्रिटिश पाउंड"),
            ("JPY", "जापानी येन"),
            ("CNY", "चीनी युआन"),
            ("AUD", "ऑस्ट्रेलियाई डॉलर"),
            ("CAD", "कनाडाई डॉलर"),
            ("SGD", "सिंगापुर डॉलर"),
            ("CHF", "स्विस फ़्रैंक"),
            ("RUB", "रूबल"),
            ("AED", "दिरहम"),
            ("SAR", "रियाल"),
            ("KRW", "वॉन"),
            ("TRY", "लीरा"),
            ("BDT", "टका"),
            ("NGN", "नाइरा"),
        ]
        iso_sg_labels = [
            ("INR", "रुपया"),
            ("Rs", "रुपया"),
            ("Rs.", "रुपया"),
            ("USD", "अमेरिकी डॉलर"),
            ("EUR", "यूरो"),
            ("GBP", "ब्रिटिश पाउंड"),
            ("JPY", "जापानी येन"),
            ("CNY", "चीनी युआन"),
            ("AUD", "ऑस्ट्रेलियाई डॉलर"),
            ("CAD", "कनाडाई डॉलर"),
            ("SGD", "सिंगापुर डॉलर"),
            ("CHF", "स्विस फ़्रैंक"),
            ("RUB", "रूबल"),
            ("AED", "दिरहम"),
            ("SAR", "रियाल"),
            ("KRW", "वॉन"),
            ("TRY", "लीरा"),
            ("BDT", "टका"),
            ("NGN", "नाइरा"),
        ]
        iso_pl_labels += extra_iso_labels
        iso_sg_labels += extra_iso_labels
        maj_to_min = dict(load_labels(get_abs_path("data/money/major_minor_currencies.tsv")))

        def _build_major_and_minor(sym_maj_labels, int_graph, trailing: bool = False):
            by_min = {}
            for sym, maj in sym_maj_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_min.setdefault(min_name, []).append((sym, maj))
            branches = []
            for min_name, pairs in by_min.items():
                curr_maj = pynutil.insert('currency_maj: "') + pynini.string_map(pairs) + pynutil.insert('"')
                curr_min = pynutil.insert(f'currency_min: "{min_name}"')
                if trailing:
                    g = (
                        optional_graph_negative
                        + int_graph
                        + pynini.cross(".", " ")
                        + fraction
                        + opt_sp
                        + insert_space
                        + curr_maj
                        + insert_space
                        + curr_min
                        + pynutil.insert(" preserve_order: true")
                    ).optimize()
                else:
                    g = (
                        optional_graph_negative
                        + curr_maj
                        + opt_sp
                        + insert_space
                        + int_graph
                        + pynini.cross(".", " ")
                        + fraction
                        + insert_space
                        + curr_min
                    ).optimize()
                branches.append(g)
            return pynini.union(*branches).optimize()

        graph_major_and_minor = _build_major_and_minor(maj_labels + iso_pl_labels, integer_for_minor)
        graph_major_and_minor_singular = _build_major_and_minor(maj_singular_labels + iso_sg_labels, integer_one)
        graph_trailing_major_minor = _build_major_and_minor(maj_labels + iso_pl_labels, integer_for_minor, trailing=True) | pynutil.add_weight(
            _build_major_and_minor(maj_singular_labels + iso_sg_labels, integer_one, trailing=True), -0.001
        )
        graph_currencies = (
            pynutil.add_weight(graph_major_only_singular | graph_major_and_minor_singular, -0.001)
            | pynutil.add_weight(graph_decimal_path, -0.0005)
            | pynutil.add_weight(graph_money_quantity, -0.01)
            | pynutil.add_weight(graph_money_range_single_curr, -0.01)
            | graph_major_only
            | graph_major_and_minor
            | pynutil.add_weight(graph_iso_leading, -0.01)
            | pynutil.add_weight(graph_trailing, 0.01)
            | pynutil.add_weight(graph_trailing_major_minor, 0.01)
        )

        # Scale abbreviations belong to the amount, not to a following serial.
        scale = pynini.string_map(
            [("k", " हज़ार"), ("K", " हज़ार"), ("m", " मिलियन"), ("M", " मिलियन"),
             ("b", " अरब"), ("B", " अरब")]
        )
        scaled_integer = pynutil.insert('integer_part: "') + qty_num + scale + pynutil.insert('"')
        graph_scaled = optional_graph_negative + (
            (currency_major | iso_curr_maj) + opt_sp + insert_space + scaled_integer
            | scaled_integer + opt_sp + insert_space + trailing_maj + pynutil.insert(" preserve_order: true")
        )
        graph_currencies |= pynutil.add_weight(graph_scaled, -0.02)

        # Per-unit prices retain the currency and use the native denominator.
        per_unit = (
            pynutil.delete("/")
            + pynutil.insert(' per_unit: "')
            + pynini.string_map(
                [("h", "प्रति घंटा"), ("hr", "प्रति घंटा"), ("kg", "प्रति किलोग्राम"),
                 ("g", "प्रति ग्राम"), ("km", "प्रति किलोमीटर"), ("m", "प्रति मीटर"),
                 ("L", "प्रति लीटर"), ("l", "प्रति लीटर"), ("min", "प्रति मिनट")]
            )
            + pynutil.insert('"')
        )
        graph = graph_currencies + pynini.closure(per_unit, 0, 1)

        # Each endpoint is independently denominated; no raw dash survives.
        spoken_prices = []
        for symbol, name in maj_labels + iso_pl_labels:
            spoken_prices.append(
                pynutil.delete(symbol) + opt_sp + qty_num + pynutil.insert(" " + name)
                | qty_num + opt_sp + pynini.cross(symbol, " " + name)
            )
        spoken_price = pynini.union(*spoken_prices).optimize()
        range_dash = opt_sp + pynini.cross(pynini.union("-", "–", "—"), " से ") + opt_sp
        money_range = (
            pynutil.insert('name: "')
            + convert_space(spoken_price + range_dash + spoken_price)
            + pynutil.insert('"')
        )
        self.fst = (self.add_tokens(graph) | money_range).optimize()
