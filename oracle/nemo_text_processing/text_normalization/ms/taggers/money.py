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

# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst, convert_space
from nemo_text_processing.text_normalization.ms.taggers.decimal import quantities
from nemo_text_processing.text_normalization.ms.utils import get_abs_path, load_labels

_PER_UNITS = [
    ("/jam", "per jam"),
    ("/j", "per jam"),
    ("/h", "per jam"),
    ("/hr", "per jam"),
    ("/minit", "per minit"),
    ("/min", "per minit"),
    ("/mnt", "per minit"),
    ("/menit", "per minit"),
    ("/saat", "per saat"),
    ("/s", "per saat"),
    ("/sec", "per saat"),
    ("/detik", "per saat"),
    ("/hari", "per hari"),
    ("/d", "per hari"),
    ("/minggu", "per minggu"),
    ("/wk", "per minggu"),
    ("/bulan", "per bulan"),
    ("/bln", "per bulan"),
    ("/mo", "per bulan"),
    ("/tahun", "per tahun"),
    ("/thn", "per tahun"),
    ("/yr", "per tahun"),
    ("/kg", "per kilogram"),
    ("/g", "per gram"),
    ("/gr", "per gram"),
    ("/t", "per tan"),
    ("/ton", "per tan"),
    ("/tan", "per tan"),
    ("/l", "per liter"),
    ("/L", "per liter"),
    ("/ml", "per mililiter"),
    ("/mL", "per mililiter"),
    ("/m", "per meter"),
    ("/km", "per kilometer"),
    ("/m²", "per meter persegi"),
    ("/m2", "per meter persegi"),
    ("/m³", "per meter padu"),
    ("/m3", "per meter padu"),
    ("/kWh", "per kilowatt-jam"),
    ("/orang", "per orang"),
    ("/malam", "per malam"),
    ("/unit", "per unit"),
]


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Malay money; the currency is written before or after the amount and spoken after it, e.g.
        "RM15,000" -> money { currency_maj: "ringgit" integer_part: "lima belas ribu" }
        "RM 1.5 juta" -> money { currency_maj: "ringgit" integer_part: "satu" fractional_part: "lima" quantity: "juta" }
        "RM15.50" -> money { currency_maj: "ringgit" integer_part: "lima belas" fractional_part: "lima puluh" currency_min: "sen" }
        "$2.50" -> money { currency_maj: "dolar" integer_part: "dua" fractional_part: "lima puluh" currency_min: "sen" }
        "100 USD" -> money { integer_part: "seratus" currency_maj: "dolar Amerika" }
        "$50k" -> money { currency_maj: "dolar" integer_part: "lima puluh" quantity: "ribu" }
        "-12.50 €" -> money { negative: "negatif" integer_part: "dua belas" fractional_part: "lima puluh" currency_min: "sen" currency_maj: "euro" }
        "$15/h" -> money { currency_maj: "dolar" integer_part: "lima belas" morphosyntactic_features: "per jam" }
        "10-20 €" -> money { integer_part: "sepuluh hingga dua puluh" currency_maj: "euro" }
    The verbalizer reads "[<prefix>] <amount> <currency> [<minor> sen] [<per_unit>]".

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
        codes = convert_space(pynini.string_map([x for x in currency_labels if x[0].isalpha()]))
        symbols = convert_space(pynini.string_map([x for x in currency_labels if not x[0].isalpha()]))

        rm_labels = [x for x in currency_labels if x[0] in {"RM", "RM.", "MYR"}]
        non_rm_labels = [x for x in currency_labels if x[0] not in {"RM", "RM.", "MYR"}]
        rm_currency = convert_space(pynini.string_map(rm_labels))
        non_rm_currency = convert_space(pynini.string_map(non_rm_labels))
        non_rm_codes = convert_space(pynini.string_map([x for x in non_rm_labels if x[0].isalpha()]))
        non_rm_symbols = convert_space(pynini.string_map([x for x in non_rm_labels if not x[0].isalpha()]))

        quantity_words = quantities | pynini.string_file(get_abs_path("data/money/quantity_abbr.tsv"))
        intl_shorthand = pynini.string_map(
            [("k", "ribu"), ("K", "ribu"), ("M", "juta"), ("B", "bilion"), ("T", "trilion")]
        )

        integer = pynutil.insert('integer_part: "') + cardinal.graph_with_sep + pynutil.insert('"')
        integer_plain = pynutil.insert('integer_part: "') + cardinal.graph + pynutil.insert('"')
        # "RM5,000.00" / "RM5.000,-" / "RM5000.00"
        optional_zero_cents = pynini.closure(
            pynutil.delete(pynini.union(".", ",")) + pynutil.delete(pynini.union("-", "00")),
            0,
            1,
        )
        fractional_digits = (
            pynutil.delete(pynini.union(".", ","))
            + pynutil.insert(' fractional_part: "')
            + decimal.graph_fractional_digits
            + pynutil.insert('"')
        )
        not_two_digits = pynini.difference(pynini.closure(NEMO_DIGIT, 1), NEMO_DIGIT**2)
        quantity = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' quantity: "')
            + quantity_words
            + pynutil.insert('"')
        )
        intl_quantity = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' quantity: "')
            + (quantities | intl_shorthand)
            + pynutil.insert('"')
        )
        two_digit_minor = (NEMO_DIGIT**2 - "00") @ (pynini.closure(pynutil.delete("0"), 0, 1) + cardinal.graph)
        minor = (
            pynutil.delete(pynini.union(".", ","))
            + pynutil.insert(' fractional_part: "')
            + two_digit_minor
            + pynutil.insert('" currency_min: "sen"')
        )

        # Shared range amount ("10-20 €", "RM10-20 juta", "$10–20")
        range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " hingga ")
        short_dec = (
            cardinal.graph_with_sep + pynini.cross(pynini.union(".", ","), " perpuluhan ") + decimal.graph_fractional_digits
        )
        quant_suffix = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(" ")
            + (quantities | intl_shorthand | pynini.string_file(get_abs_path("data/money/quantity_abbr.tsv")))
        )
        range_endpoint = (cardinal.graph_with_sep | short_dec) + pynini.closure(quant_suffix, 0, 1)
        range_amount = (
            pynutil.insert('integer_part: "')
            + range_endpoint
            + range_sep
            + range_endpoint
            + pynutil.insert('"')
        )

        base_amount = (
            pynutil.add_weight(integer + optional_zero_cents, -0.01)
            | integer + ((pynini.union(".", ",") + not_two_digits) @ fractional_digits)
            | ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT | "." | ",")) @ integer + minor
            | pynutil.add_weight(range_amount, -0.01)
        )
        rm_amount = (
            base_amount
            | integer + pynini.closure(fractional_digits, 0, 1) + quantity
            | integer_plain + fractional_digits + quantity
        )
        intl_amount = (
            base_amount
            | integer + pynini.closure(fractional_digits, 0, 1) + intl_quantity
            | integer_plain + fractional_digits + intl_quantity
        )
        minor_only = (
            pynutil.delete(pynini.union("0,", "0."))
            + pynutil.insert('fractional_part: "')
            + two_digit_minor
            + pynutil.insert('" currency_min: "sen"')
        )

        space = pynini.closure(pynutil.delete(pynini.union(" ", "\u00a0", "\u202f")), 0, 1)
        req_space = pynutil.delete(pynini.union(" ", "\u00a0", "\u202f"))

        rm_maj = pynutil.insert('currency_maj: "') + rm_currency + pynutil.insert('" ')
        non_rm_maj = pynutil.insert('currency_maj: "') + non_rm_currency + pynutil.insert('" ')

        # Do not consume "¢" in minor_only ("25¢" uses currency_maj: "sen")
        currency_no_cent = convert_space(pynini.string_map([x for x in currency_labels if x[0] != "¢"]))
        currency_input = pynini.project(currency_no_cent, "input")
        symbols_no_cent = convert_space(
            pynini.string_map([x for x in currency_labels if not x[0].isalpha() and x[0] != "¢"])
        )
        symbols_input = pynini.project(symbols_no_cent, "input")
        codes_input = pynini.project(codes, "input")

        leading = (
            rm_maj + space + rm_amount
            | non_rm_maj + space + intl_amount
            | pynutil.delete(currency_input) + space + minor_only
        )

        trailing_rm_maj = req_space + pynutil.insert(' currency_maj: "') + convert_space(pynini.accep("MYR") @ currency) + pynutil.insert('"')
        trailing_non_rm_maj = (
            space + pynutil.insert(' currency_maj: "') + non_rm_symbols + pynutil.insert('"')
            | req_space + pynutil.insert(' currency_maj: "') + non_rm_codes + pynutil.insert('"')
        )
        trailing_minor = minor_only + (
            space + pynutil.delete(symbols_input) | req_space + pynutil.delete(codes_input)
        )
        trailing = pynutil.add_weight(
            rm_amount + trailing_rm_maj | intl_amount + trailing_non_rm_maj | trailing_minor,
            0.01,
        )

        per_unit = (
            space
            + pynutil.insert(' morphosyntactic_features: "')
            + convert_space(pynini.string_map(_PER_UNITS).optimize())
            + pynutil.insert('"')
        )
        optional_per = pynini.closure(per_unit, 0, 1)

        pos_body = (leading | trailing) + optional_per
        self.positive_fst = self.add_tokens(pos_body).optimize()

        optional_prefix = pynini.closure(
            pynini.cross(pynini.union("-", "−"), 'negative: "negatif" ')
            | (pynini.cross("~", 'negative: "sekitar" ') + space)
            | (pynini.cross("±", 'negative: "lebih kurang" ') + space),
            0,
            1,
        )
        graph = optional_prefix + pos_body
        self.fst = self.add_tokens(graph).optimize()
