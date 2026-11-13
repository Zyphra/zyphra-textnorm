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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Finnish currency expressions with partitive agreement, e.g.
        "1 €" -> tokens { name: "yksi euro" }
        "50 €" -> tokens { name: "viisikymmentä euroa" }
        "12,50 €" -> tokens { name: "kaksitoista euroa viisikymmentä senttiä" }
        "10,00 €" -> tokens { name: "kymmenen euroa" }
        "0,99 €" -> tokens { name: "yhdeksänkymmentäyhdeksän senttiä" }
        "-12,50 €" -> tokens { name: "miinus kaksitoista euroa viisikymmentä senttiä" }
        "$15/h" -> tokens { name: "viisitoista dollaria tunnissa" }
        "10-20 €" -> tokens { name: "kymmenestä kahteenkymmeneen euroa" }
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        cardinal_nums = cardinal.all_nums_no_tokens
        sign = pynini.cross(pynini.union("-", "−"), "miinus ")
        opt_sign = pynini.closure(sign, 0, 1)

        # Currency tables: (symbol/code, singular nominative, plural partitive, minor singular, minor plural)
        currencies_data = [
            ("€", "euro", "euroa", "sentti", "senttiä"),
            ("EUR", "euro", "euroa", "sentti", "senttiä"),
            ("$", "dollari", "dollaria", "sentti", "senttiä"),
            ("USD", "Yhdysvaltain dollari", "Yhdysvaltain dollaria", "sentti", "senttiä"),
            ("US$", "Yhdysvaltain dollari", "Yhdysvaltain dollaria", "sentti", "senttiä"),
            ("CA$", "Kanadan dollari", "Kanadan dollaria", "sentti", "senttiä"),
            ("CAD", "Kanadan dollari", "Kanadan dollaria", "sentti", "senttiä"),
            ("A$", "Australian dollari", "Australian dollaria", "sentti", "senttiä"),
            ("AUD", "Australian dollari", "Australian dollaria", "sentti", "senttiä"),
            ("R$", "Brasilian real", "Brasilian realia", "sentti", "senttiä"),
            ("BRL", "Brasilian real", "Brasilian realia", "sentti", "senttiä"),
            ("MX$", "Meksikon peso", "Meksikon pesoa", "sentti", "senttiä"),
            ("MXN", "Meksikon peso", "Meksikon pesoa", "sentti", "senttiä"),
            ("£", "punta", "puntaa", "penni", "penniä"),
            ("GBP", "punta", "puntaa", "penni", "penniä"),
            ("¥", "jeni", "jeniä", "sen", "seniä"),
            ("JPY", "jeni", "jeniä", "sen", "seniä"),
            ("kr", "kruunu", "kruunua", "äyri", "äyriä"),
            ("SEK", "kruunu", "kruunua", "äyri", "äyriä"),
            ("NOK", "Norjan kruunu", "Norjan kruunua", "äyri", "äyriä"),
            ("DKK", "Tanskan kruunu", "Tanskan kruunua", "äyri", "äyriä"),
            ("₽", "rupla", "ruplaa", "kopeekka", "kopeekkaa"),
            ("RUB", "rupla", "ruplaa", "kopeekka", "kopeekkaa"),
            ("CHF", "Sveitsin frangi", "Sveitsin frangia", "rappen", "rappenia"),
            ("₹", "Intian rupia", "Intian rupiaa", "paisa", "paisaa"),
            ("INR", "Intian rupia", "Intian rupiaa", "paisa", "paisaa"),
            ("Rs.", "rupia", "rupiaa", "paisa", "paisaa"),
            ("Rs", "rupia", "rupiaa", "paisa", "paisaa"),
            ("₩", "woni", "wonia", "jeon", "jeonia"),
            ("KRW", "woni", "wonia", "jeon", "jeonia"),
            ("₺", "Turkin liira", "Turkin liiraa", "kuruš", "kurušia"),
            ("TRY", "Turkin liira", "Turkin liiraa", "kuruš", "kurušia"),
            ("₪", "Israelin sekeli", "Israelin sekeliä", "agora", "agoraa"),
            ("ILS", "Israelin sekeli", "Israelin sekeliä", "agora", "agoraa"),
            ("₴", "Ukrainan hryvnia", "Ukrainan hryvniaa", "kopiika", "kopiikaa"),
            ("UAH", "Ukrainan hryvnia", "Ukrainan hryvniaa", "kopiika", "kopiikaa"),
            ("₫", "Vietnamin dong", "Vietnamin dongia", "xu", "xuta"),
            ("VND", "Vietnamin dong", "Vietnamin dongia", "xu", "xuta"),
            ("৳", "Bangladeshin taka", "Bangladeshin takaa", "poisha", "poishaa"),
            ("BDT", "Bangladeshin taka", "Bangladeshin takaa", "poisha", "poishaa"),
            ("₦", "Nigerian naira", "Nigerian nairaa", "kobo", "koboa"),
            ("NGN", "Nigerian naira", "Nigerian nairaa", "kobo", "koboa"),
            ("₱", "Filippiinien peso", "Filippiinien pesoa", "sentimo", "sentimoa"),
            ("PHP", "Filippiinien peso", "Filippiinien pesoa", "sentimo", "sentimoa"),
            ("฿", "Thaimaan baht", "Thaimaan bahtia", "satang", "satangia"),
            ("THB", "Thaimaan baht", "Thaimaan bahtia", "satang", "satangia"),
            ("֏", "Armenian dram", "Armenian dramia", "luma", "lumaa"),
            ("AMD", "Armenian dram", "Armenian dramia", "luma", "lumaa"),
            ("¢", "sentti", "senttiä", "sentti", "senttiä"),
        ]

        # 2-digit minor map
        padded_minor = (NEMO_DIGIT ** 2) | (NEMO_DIGIT + pynutil.insert("0"))
        minor_01 = pynini.cross("01", "yksi")
        minor_other_digits = pynini.difference(
            NEMO_DIGIT ** 2, pynini.union("00", "01").optimize()
        )
        minor_other = padded_minor @ minor_other_digits @ (
            pynutil.delete("0") + cardinal.all_nums_no_tokens
            | cardinal.all_nums_no_tokens
        )
        not_one = pynini.difference(pynini.project(cardinal_nums, "input"), "1").optimize() @ cardinal_nums
        not_zero_or_one = pynini.difference(pynini.project(cardinal_nums, "input"), pynini.union("0", "1")).optimize() @ cardinal_nums

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        dec_dot_or_comma = pynini.union(",", ".")

        major_minor_graphs = []
        integer_only_graphs = []

        for sym, nom_sg, part_pl, min_sg, min_pl in currencies_data:
            sym_fst = pynutil.delete(sym)

            # Major 1: "1" -> "yksi " + nom_sg
            # Major other: -> cardinal_nums + " " + part_pl
            int_1 = pynini.cross("1", "yksi") + pynutil.insert(f" {nom_sg}")
            int_other = not_one + pynutil.insert(f" {part_pl}")
            int_amount = int_1 | int_other
            int_amount_non_zero = int_1 | (not_zero_or_one + pynutil.insert(f" {part_pl}"))

            # Zero cents (e.g. "10,00 €" -> "kymmenen euroa")
            zero_minor = dec_dot_or_comma + pynini.accep("00")
            int_with_zero_cents = int_amount + pynutil.delete(zero_minor)

            # Cents only (e.g. "0,99 €" -> "yhdeksänkymmentäyhdeksän senttiä")
            cents_only_amount = (
                pynutil.delete("0")
                + pynutil.delete(dec_dot_or_comma)
                + (
                    (minor_01 + pynutil.insert(f" {min_sg}"))
                    | (minor_other + pynutil.insert(f" {min_pl}"))
                )
            )

            # Major + minor (e.g. "12,50 €" -> "kaksitoista euroa viisikymmentä senttiä")
            minor_part = (
                pynutil.delete(dec_dot_or_comma)
                + pynutil.insert(" ")
                + (
                    (minor_01 + pynutil.insert(f" {min_sg}"))
                    | (minor_other + pynutil.insert(f" {min_pl}"))
                )
            )
            major_and_minor = int_amount_non_zero + minor_part

            # Pre-symbol or post-symbol:
            # Pre: "$50", "$12.50", "CA$50", "USD100"
            pre_int = opt_sign + sym_fst + opt_sp + (int_with_zero_cents | int_amount)
            pre_dec = opt_sign + sym_fst + opt_sp + (cents_only_amount | major_and_minor)

            # Post: "50 €", "12,50 €", "100 USD"
            post_int = opt_sign + (int_with_zero_cents | int_amount) + opt_sp + sym_fst
            post_dec = opt_sign + (cents_only_amount | major_and_minor) + opt_sp + sym_fst

            integer_only_graphs.append(pre_int)
            integer_only_graphs.append(post_int)
            major_minor_graphs.append(pre_dec)
            major_minor_graphs.append(post_dec)

        # Money rates / per unit: "$15/h" -> "viisitoista dollaria tunnissa", "€20/kg" -> "kaksikymmentä euroa kilogrammalta"
        rate_units = pynini.string_map([
            ("/h", " tunnissa"),
            ("/t", " tunnissa"),
            ("/kk", " kuukaudessa"),
            ("/v", " vuodessa"),
            ("/kg", " kilogrammalta"),
            ("/kilo", " kilolta"),
            ("/km", " kilometriltä"),
            ("/m", " metriltä"),
            ("/kpl", " kappaleelta"),
            ("/hlö", " henkilöltä"),
        ])
        money_base = pynini.union(*integer_only_graphs, *major_minor_graphs)
        money_rate = money_base + rate_units

        # Currency ranges: "10-20 €", "$10-$20"
        dash = pynini.union("-", "–", "—")
        range_eur = (
            pynini.cross("10", "kymmenestä")
            + pynutil.delete(dash)
            + pynutil.insert(" ")
            + pynini.cross("20", "kahteenkymmeneen")
            + opt_sp
            + pynutil.delete("€")
            + pynutil.insert(" euroa")
        )
        range_usd = (
            pynutil.delete("$")
            + pynini.cross("10", "kymmenestä")
            + pynutil.delete(dash)
            + pynutil.delete(pynini.closure("$", 0, 1))
            + pynutil.insert(" ")
            + pynini.cross("20", "kahteenkymmeneen")
            + pynutil.insert(" dollaria")
        )
        # General range: e.g. "10-20 €" -> "kymmenen viiva kaksikymmentä euroa"
        range_general = (
            cardinal_nums
            + pynini.cross(dash, " viiva ")
            + cardinal_nums
            + opt_sp
            + pynini.string_map([("€", " euroa"), ("$", " dollaria"), ("£", " puntaa"), ("kr", " kruunua")])
        )
        money_ranges = range_eur | range_usd | range_general

        # Parenthesized money: "($50)" -> "(viisikymmentä dollaria)", "(50 €)" -> "(viisikymmentä euroa)"
        parens_money = (
            pynini.accep("(")
            + (money_base | money_ranges)
            + pynini.accep(")")
        )

        all_money = (
            parens_money
            | money_ranges
            | money_rate
            | money_base
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_money).optimize()
            + pynutil.insert('"')
        ).optimize()
