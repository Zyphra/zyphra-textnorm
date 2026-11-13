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
from nemo_text_processing.text_normalization.id.taggers.decimal import quantities
from nemo_text_processing.text_normalization.id.utils import get_abs_path, load_labels

_PER_UNITS = [
    ("/jam", "per jam"),
    ("/j", "per jam"),
    ("/h", "per jam"),
    ("/hr", "per jam"),
    ("/menit", "per menit"),
    ("/mnt", "per menit"),
    ("/min", "per menit"),
    ("/detik", "per detik"),
    ("/dtk", "per detik"),
    ("/s", "per detik"),
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
    ("/t", "per ton"),
    ("/ton", "per ton"),
    ("/l", "per liter"),
    ("/L", "per liter"),
    ("/ml", "per mililiter"),
    ("/mL", "per mililiter"),
    ("/m", "per meter"),
    ("/km", "per kilometer"),
    ("/m²", "per meter persegi"),
    ("/m2", "per meter persegi"),
    ("/m³", "per meter kubik"),
    ("/m3", "per meter kubik"),
    ("/kWh", "per kilowatt-jam"),
    ("/orang", "per orang"),
    ("/malam", "per malam"),
    ("/unit", "per unit"),
]


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money; the currency is written before or after the amount and spoken after it, e.g.
        "Rp15.000" -> money { currency_maj: "rupiah" integer_part: "lima belas ribu" }
        "Rp 1,5 juta" -> money { currency_maj: "rupiah" integer_part: "satu" fractional_part: "lima" quantity: "juta" }
        "$2,50" -> money { currency_maj: "dolar" integer_part: "dua" fractional_part: "lima puluh" currency_min: "sen" }
        "100 USD" -> money { integer_part: "seratus" currency_maj: "dolar Amerika" }
        "$50k" -> money { currency_maj: "dolar" integer_part: "lima puluh" quantity: "ribu" }
        "-12,50 €" -> money { negative: "negatif" integer_part: "dua belas" fractional_part: "lima puluh" currency_min: "sen" currency_maj: "euro" }
        "$15/h" -> money { currency_maj: "dolar" integer_part: "lima belas" morphosyntactic_features: "per jam" }
        "10-20 €" -> money { integer_part: "sepuluh sampai dua puluh" currency_maj: "euro" }
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

        rp_labels = [x for x in currency_labels if x[0] in {"Rp", "Rp.", "IDR"}]
        non_rp_labels = [x for x in currency_labels if x[0] not in {"Rp", "Rp.", "IDR"}]
        rp_currency = convert_space(pynini.string_map(rp_labels))
        non_rp_currency = convert_space(pynini.string_map(non_rp_labels))
        non_rp_codes = convert_space(pynini.string_map([x for x in non_rp_labels if x[0].isalpha()]))
        non_rp_symbols = convert_space(pynini.string_map([x for x in non_rp_labels if not x[0].isalpha()]))

        quantity_words = quantities | pynini.string_file(get_abs_path("data/money/quantity_abbr.tsv"))
        intl_shorthand = pynini.string_map([("k", "ribu"), ("K", "ribu"), ("M", "juta"), ("B", "miliar")])

        integer = pynutil.insert('integer_part: "') + cardinal.graph_with_sep + pynutil.insert('"')
        integer_plain = pynutil.insert('integer_part: "') + cardinal.graph + pynutil.insert('"')
        # "Rp5.000,-" / "Rp5.000,00"
        optional_zero_cents = pynini.closure(
            pynutil.delete(",") + (pynutil.delete("-") | pynini.closure(pynutil.delete("0"), 1)), 0, 1
        )
        fractional_digits = (
            pynutil.delete(",")
            + pynutil.insert(' fractional_part: "')
            + decimal.graph_fractional_digits
            + pynutil.insert('"')
        )
        dot_fractional_digits = pynutil.add_weight(
            pynutil.delete(".")
            + pynutil.insert(' fractional_part: "')
            + pynini.difference(pynini.closure(NEMO_DIGIT, 1), NEMO_DIGIT**3) @ decimal.graph_fractional_digits
            + pynutil.insert('"'),
            0.05,
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
            + (quantities | intl_shorthand | pynini.cross("T", "triliun"))
            + pynutil.insert('"')
        )
        two_digit_minor = (NEMO_DIGIT**2 - "00") @ (pynini.closure(pynutil.delete("0"), 0, 1) + cardinal.graph)
        minor = (
            pynutil.delete(",")
            + pynutil.insert(' fractional_part: "')
            + two_digit_minor
            + pynutil.insert('" currency_min: "sen"')
        )
        dot_minor = pynutil.add_weight(
            pynutil.delete(".")
            + pynutil.insert(' fractional_part: "')
            + two_digit_minor
            + pynutil.insert('" currency_min: "sen"'),
            0.05,
        )

        # Shared range amount ("10-20 €", "Rp10.000-20.000", "$10–20")
        range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " sampai ")
        short_dec = (
            cardinal.graph_with_sep + pynini.cross(",", " koma ") + decimal.graph_fractional_digits
            | cardinal.graph + pynini.cross(".", " koma ") + (pynini.difference(pynini.closure(NEMO_DIGIT, 1), NEMO_DIGIT**3) @ decimal.graph_fractional_digits)
        )
        quant_suffix = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(" ")
            + (quantities | intl_shorthand | pynini.cross("T", "triliun") | pynini.string_file(get_abs_path("data/money/quantity_abbr.tsv")))
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
            integer + optional_zero_cents
            | integer + ((pynini.accep(",") + not_two_digits) @ fractional_digits)
            | integer_plain + ((pynini.accep(".") + not_two_digits) @ dot_fractional_digits)
            | ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT | ".")) @ integer + minor
            | pynutil.add_weight(((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT)) @ integer + dot_minor, 0.05)
            | pynutil.add_weight(range_amount, -0.01)
        )
        rp_amount = (
            base_amount
            | integer + pynini.closure(fractional_digits, 0, 1) + quantity
            | integer_plain + dot_fractional_digits + quantity
        )
        intl_amount = (
            base_amount
            | integer + pynini.closure(fractional_digits, 0, 1) + intl_quantity
            | integer_plain + dot_fractional_digits + intl_quantity
        )
        minor_only = (
            pynutil.delete(pynini.union("0,", "0."))
            + pynutil.insert('fractional_part: "')
            + two_digit_minor
            + pynutil.insert('" currency_min: "sen"')
        )

        space = pynini.closure(pynutil.delete(pynini.union(" ", "\u00a0", "\u202f")), 0, 1)
        req_space = pynutil.delete(pynini.union(" ", "\u00a0", "\u202f"))

        rp_maj = pynutil.insert('currency_maj: "') + rp_currency + pynutil.insert('" ')
        non_rp_maj = pynutil.insert('currency_maj: "') + non_rp_currency + pynutil.insert('" ')

        # Do not consume "¢" in minor_only ("0,25 ¢" is rare; "25¢" uses currency_maj: "sen")
        currency_no_cent = convert_space(pynini.string_map([x for x in currency_labels if x[0] != "¢"]))
        currency_input = pynini.project(currency_no_cent, "input")
        symbols_no_cent = convert_space(
            pynini.string_map([x for x in currency_labels if not x[0].isalpha() and x[0] != "¢"])
        )
        symbols_input = pynini.project(symbols_no_cent, "input")
        codes_input = pynini.project(codes, "input")

        leading = (
            rp_maj + space + rp_amount
            | non_rp_maj + space + intl_amount
            | pynutil.delete(currency_input) + space + minor_only
        )

        trailing_rp_maj = req_space + pynutil.insert(' currency_maj: "') + convert_space(pynini.accep("IDR") @ currency) + pynutil.insert('"')
        trailing_non_rp_maj = (
            space + pynutil.insert(' currency_maj: "') + non_rp_symbols + pynutil.insert('"')
            | req_space + pynutil.insert(' currency_maj: "') + non_rp_codes + pynutil.insert('"')
        )
        trailing_minor = minor_only + (
            space + pynutil.delete(symbols_input) | req_space + pynutil.delete(codes_input)
        )
        trailing = pynutil.add_weight(
            rp_amount + trailing_rp_maj | intl_amount + trailing_non_rp_maj | trailing_minor,
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
            | (pynini.cross("±", 'negative: "kurang lebih" ') + space),
            0,
            1,
        )
        graph = optional_prefix + pos_body
        self.fst = self.add_tokens(graph).optimize()
