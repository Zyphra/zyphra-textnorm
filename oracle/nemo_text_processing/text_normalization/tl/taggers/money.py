# Copyright (c) 2026 Zyphra, Inc.
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

# Number names from Unicode CLDR release-49 (fil locale, Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tl.taggers.decimal import quantities
from nemo_text_processing.text_normalization.tl.utils import get_abs_path, load_labels

_PER_UNITS = [
    ("/oras", "bawat oras"),
    ("/h", "bawat oras"),
    ("/hr", "bawat oras"),
    ("/minuto", "bawat minuto"),
    ("/min", "bawat minuto"),
    ("/segundo", "bawat segundo"),
    ("/s", "bawat segundo"),
    ("/araw", "bawat araw"),
    ("/d", "bawat araw"),
    ("/linggo", "bawat linggo"),
    ("/wk", "bawat linggo"),
    ("/buwan", "bawat buwan"),
    ("/mo", "bawat buwan"),
    ("/taon", "bawat taon"),
    ("/yr", "bawat taon"),
    ("/kilo", "bawat kilo"),
    ("/kg", "bawat kilo"),
    ("/gramo", "bawat gramo"),
    ("/g", "bawat gramo"),
    ("/litro", "bawat litro"),
    ("/l", "bawat litro"),
    ("/L", "bawat litro"),
    ("/metro", "bawat metro"),
    ("/m", "bawat metro"),
    ("/kilometro", "bawat kilometro"),
    ("/km", "bawat kilometro"),
    ("/tao", "bawat tao"),
    ("/unit", "bawat yunit"),
]


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Tagalog money; currency is written before or after the amount, e.g.
        "₱15,000" -> money { integer_part: "labinlimang libo" currency_maj: "piso" }
        "₱1.50" -> money { integer_part: "isa" currency_maj: "piso" fractional_part: "limampu" currency_min: "sentimo" }
        "$2.50" -> money { integer_part: "dalawa" currency_maj: "dolyar" fractional_part: "limampu" currency_min: "sentimo" }
        "100 USD" -> money { integer_part: "isang daan" currency_maj: "dolyar ng US" }
        "$50k" -> money { integer_part: "limampu" quantity: "libo" currency_maj: "dolyar" }
        "-₱12.50" -> money { negative: "minus" integer_part: "labindalawa" currency_maj: "piso" fractional_part: "limampu" currency_min: "sentimo" }
        "$15/h" -> money { integer_part: "labinlima" currency_maj: "dolyar" morphosyntactic_features: "bawat oras" }
        "10-20 €" -> money { integer_part: "sampu hanggang dalawampu" currency_maj: "euro" }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)
        currency_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        currency = convert_space(pynini.string_map(currency_labels))

        quantity_words = quantities | pynini.string_file(get_abs_path("data/money/quantity_abbr.tsv"))
        intl_shorthand = pynini.string_map([("k", "libo"), ("K", "libo"), ("M", "milyon"), ("B", "bilyon")])

        integer = pynutil.insert('integer_part: "') + cardinal.graph_with_sep + pynutil.insert('"')
        integer_plain = pynutil.insert('integer_part: "') + cardinal.graph + pynutil.insert('"')

        # Optional zero cents: ".00" or ",00"
        optional_zero_cents = pynini.closure(
            pynutil.delete(pynini.union(".", ",")) + (pynutil.delete("-") | pynini.closure(pynutil.delete("0"), 1)), 0, 1
        )

        fractional_digits = (
            pynutil.delete(pynini.union(".", ","))
            + pynutil.insert(' fractional_part: "')
            + decimal.graph_fractional_digits
            + pynutil.insert('"')
        )

        quantity = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' quantity: "')
            + quantity_words
            + pynutil.insert('"')
        )
        intl_quantity = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' quantity: "')
            + (quantities | intl_shorthand | pynini.cross("T", "trilyon"))
            + pynutil.insert('"')
        )

        two_digit_minor = (NEMO_DIGIT**2 - "00") @ (pynini.closure(pynutil.delete("0"), 0, 1) + cardinal.graph)
        minor = (
            pynutil.delete(pynini.union(".", ","))
            + pynutil.insert(' fractional_part: "')
            + two_digit_minor
            + pynutil.insert('" currency_min: "sentimo"')
        )

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        per_unit = (
            pynutil.insert(' morphosyntactic_features: "')
            + pynini.string_map(_PER_UNITS)
            + pynutil.insert('"')
        )
        optional_per = pynini.closure(opt_space + per_unit, 0, 1)

        # 1. Symbol/Code + amount (e.g. ₱15,000, $2.50, US$50, ₱50k)
        # Parse symbol first, but emit in canonical order: integer + currency_maj + [fractional + currency_min]
        curr_maj_tag = pynutil.insert(' currency_maj: "') + currency + pynutil.insert('"')

        prefix_shorthand = (
            pynutil.delete(currency)
            + opt_space
            + (integer_plain + intl_quantity | integer + fractional_digits + quantity)
            + curr_maj_tag
        )
        # For major-minor, match curr, integer, minor
        # To avoid permutation in Pynini, currency can map to a temporary tag or we parse each currency:
        prefix_cases = []
        for sym, word in currency_labels:
            sym_fst = pynutil.delete(sym) + opt_space
            maj_field = pynutil.insert(f' currency_maj: "{word}"')
            maj_min = sym_fst + integer + maj_field + minor
            maj_only = sym_fst + integer + optional_zero_cents + maj_field
            short_int = sym_fst + integer_plain + intl_quantity + maj_field
            short_dec = sym_fst + integer + fractional_digits + quantity + maj_field
            prefix_cases.extend([maj_min, maj_only, short_int, short_dec])

        prefix_amount = pynini.union(*prefix_cases) + optional_per

        # 2. Amount + Symbol/Code (e.g. 100 USD, 20 €, 99.95 €, 10-20 €)
        curr_suffix = opt_space + curr_maj_tag
        suffix_shorthand = (integer_plain + intl_quantity | integer + fractional_digits + quantity) + curr_suffix
        suffix_major_minor = integer + minor + curr_suffix
        suffix_major_only = integer + optional_zero_cents + curr_suffix
        range_dash = pynini.cross(pynini.union("-", "–"), " hanggang ")
        money_range = (
            pynutil.insert('integer_part: "')
            + cardinal.graph_with_sep
            + range_dash
            + cardinal.graph_with_sep
            + pynutil.insert('"')
            + curr_suffix
        )
        suffix_amount = (suffix_shorthand | suffix_major_minor | suffix_major_only | money_range) + optional_per

        # 3. Cents only (e.g. 25¢, $0.99, ₱0.99, 0.99 €)
        cents_sym = pynini.cross("¢", "sentimo")
        cent_unit = pynutil.insert('currency_min: "') + cents_sym + pynutil.insert('"')
        cents_direct = pynutil.insert('fractional_part: "') + cardinal.graph + pynutil.insert('" ') + cent_unit
        cents_from_zero = (
            pynutil.delete(pynini.union("₱", "$", "US$", "€", "£"))
            + opt_space
            + pynutil.delete("0")
            + minor
        )
        cents_from_zero_post = (
            pynutil.delete("0")
            + minor
            + opt_space
            + pynutil.delete(pynini.union("€", "$", "USD", "EUR", "PHP"))
        )
        cents_amount = (cents_direct | cents_from_zero | cents_from_zero_post) + optional_per

        graph = prefix_amount | suffix_amount | cents_amount

        # Wrapped in parentheses: e.g. "(50 €)"
        graph |= pynutil.delete("(") + (prefix_amount | suffix_amount) + pynutil.delete(")")

        # Negative money (-$12.50, -₱100)
        optional_prefix = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"minus" '), 0, 1
        )
        self.positive_fst = graph.optimize()
        self.fst = self.add_tokens(optional_prefix + graph).optimize()
