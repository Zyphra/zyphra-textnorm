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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Danish money expressions.
    Handles:
      - DKK: "50 kr.", "kr. 50", "1 kr.", "20,50 kr.", "kr. 20,50", "0,50 kr.", "0,01 kr."
      - Minor units: "øre" (1 øre -> "en øre", 50 øre -> "halvtreds øre")
      - Major currencies: USD ($), EUR (€), GBP (£), JPY/CNY (¥), CHF, INR (₹), RUB (₽), etc.
      - Shorthand multipliers: "$50k" -> "halvtreds tusind dollar", "$2,5M", "2 mio. kr.", "$45 milliarder"
      - Negative money: "-$12,50", "-12,50 kr."
      - Per-unit money: "$15/h", "€20/kg"
      - Money ranges: "$10-$20", "10-20 kr."
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Currency definitions: (symbol, singular, plural, minor_singular, minor_plural)
        currencies = [
            ("kr.", "krone", "kroner", "øre", "øre"),
            ("kr", "krone", "kroner", "øre", "øre"),
            ("DKK", "krone", "kroner", "øre", "øre"),
            ("$", "dollar", "dollar", "cent", "cent"),
            ("USD", "amerikansk dollar", "amerikanske dollar", "cent", "cent"),
            ("US$", "amerikansk dollar", "amerikanske dollar", "cent", "cent"),
            ("CA$", "canadisk dollar", "canadiske dollar", "cent", "cent"),
            ("CAD", "canadisk dollar", "canadiske dollar", "cent", "cent"),
            ("A$", "australsk dollar", "australske dollar", "cent", "cent"),
            ("AUD", "australsk dollar", "australske dollar", "cent", "cent"),
            ("R$", "brasiliansk real", "brasilianske real", "centavo", "centavos"),
            ("MX$", "mexicansk peso", "mexicanske peso", "centavo", "centavos"),
            ("€", "euro", "euro", "cent", "cent"),
            ("EUR", "euro", "euro", "cent", "cent"),
            ("£", "pund", "pund", "penny", "pence"),
            ("GBP", "britisk pund", "britiske pund", "penny", "pence"),
            ("¥", "yen", "yen", "", ""),
            ("JPY", "japansk yen", "japanske yen", "", ""),
            ("CNY", "kinesisk yuan", "kinesiske yuan", "", ""),
            ("CHF", "schweizerfranc", "schweizerfranc", "rappen", "rappen"),
            ("₹", "indisk rupee", "indiske rupee", "paisa", "paise"),
            ("INR", "indisk rupee", "indiske rupee", "paisa", "paise"),
            ("Rs.", "indisk rupee", "indiske rupee", "paisa", "paise"),
            ("Rs", "indisk rupee", "indiske rupee", "paisa", "paise"),
            ("₽", "rubel", "rubler", "kopek", "kopek"),
            ("RUB", "russisk rubel", "russiske rubler", "kopek", "kopek"),
            ("₩", "won", "won", "", ""),
            ("KRW", "sydkoreansk won", "sydkoreanske won", "", ""),
            ("₺", "tyrkisk lira", "tyrkiske lira", "kurus", "kurus"),
            ("TRY", "tyrkisk lira", "tyrkiske lira", "kurus", "kurus"),
            ("₪", "shekel", "shekel", "agora", "agorot"),
            ("ILS", "israelsk shekel", "israelske shekel", "agora", "agorot"),
            ("₴", "hryvnia", "hryvnia", "kopijka", "kopijky"),
            ("UAH", "ukrainsk hryvnia", "ukrainske hryvnia", "kopijka", "kopijky"),
            ("₫", "dong", "dong", "", ""),
            ("VND", "vietnamesisk dong", "vietnamesiske dong", "", ""),
            ("৳", "taka", "taka", "poisha", "poisha"),
            ("BDT", "bangladeshisk taka", "bangladeshiske taka", "poisha", "poisha"),
            ("₦", "naira", "naira", "kobo", "kobo"),
            ("NGN", "nigeriansk naira", "nigerianske naira", "kobo", "kobo"),
            ("₱", "filippinsk peso", "filippinske peso", "sentimo", "sentimo"),
            ("PHP", "filippinsk peso", "filippinske peso", "sentimo", "sentimo"),
            ("฿", "baht", "baht", "satang", "satang"),
            ("THB", "thailandsk baht", "thailandske baht", "satang", "satang"),
            ("֏", "dram", "dram", "luma", "luma"),
            ("AMD", "armensk dram", "armenske dram", "luma", "luma"),
        ]

        # Negative prefix
        minus_sign = pynini.cross(pynini.union("-", "−"), "minus ")
        optional_minus = pynini.closure(minus_sign, 0, 1)

        # Decimal separator
        dec_sep = pynini.union(",", ".")

        graphs = []

        # 2-digit minor number graph (cents / øre)
        minor_1 = pynini.cross("01", "en") | pynini.cross("1", "en")
        minor_higher = (
            pynini.cross("0", "") + cardinal.num_1_to_999_common
            | cardinal.num_1_to_999_common
        )

        num_int_money = (
            pynutil.add_weight(cardinal.integer_with_et, -0.01)
            | cardinal.integer_common
        )
        non_zero_digits = pynini.difference(pynini.closure(NEMO_DIGIT, 1), pynini.closure("0", 1))
        non_zero_int = (non_zero_digits @ num_int_money).optimize()

        not_one_or_zero_digits = pynini.difference(
            pynini.closure(NEMO_DIGIT, 1),
            pynini.closure("0", 1) | "1"
        )
        non_one_int = (not_one_or_zero_digits @ num_int_money).optimize()

        scale_words_money = pynini.union(
            pynini.cross(pynini.union("million", "millioner", "mio.", "mio", "mn"), " millioner"),
            pynini.cross(pynini.union("milliard", "milliarder", "mia.", "mia", "md"), " milliarder"),
            pynini.cross(pynini.union("billion", "billioner", "bn"), " billioner"),
        )

        for sym, sing, plur, msing, mplur in currencies:
            # Determine agreement gender for "1"
            one_word = "et" if sing in ("pund", "britisk pund") else "en"

            # Major only (integer):
            # 1 -> "en krone", "en dollar", "et pund"
            maj_one = pynini.cross("1", f"{one_word} {sing}")
            maj_plur = non_one_int + pynutil.insert(f" {plur}")
            maj_int = maj_one | maj_plur

            # Prefix symbol: "$50", "kr. 50"
            prefix_sym = pynutil.delete(sym) + opt_sp + maj_int
            # Suffix symbol: "50 kr.", "50 €", "50 USD"
            suffix_sym = maj_int + opt_sp + pynutil.delete(sym)

            # Prefix symbol with magnitude: e.g. "$45 milliarder" -> "femogfyrre milliarder dollar"
            prefix_sym_mag = (
                pynutil.delete(sym)
                + opt_sp
                + non_zero_int
                + opt_sp
                + scale_words_money
                + pynutil.insert(f" {plur}")
            )

            curr_int = prefix_sym | suffix_sym | prefix_sym_mag
            graphs.append(curr_int)

            if msing and mplur:
                # With minor decimals: e.g. "20,50 kr." -> "tyve kroner og halvtreds øre"
                # Major part == 0: e.g. "0,50 kr." -> "halvtreds øre", "0,01 kr." -> "en øre"
                minor_one_part = minor_1 + pynutil.insert(f" {msing}")
                minor_plur_part = minor_higher + pynutil.insert(f" {mplur}")
                minor_part = minor_one_part | minor_plur_part

                zero_major = (
                    pynutil.delete("0")
                    + pynutil.delete(dec_sep)
                    + minor_part
                )
                zero_major_prefix = pynutil.add_weight(pynutil.delete(sym) + opt_sp + zero_major, -0.05)
                zero_major_suffix = pynutil.add_weight(zero_major + opt_sp + pynutil.delete(sym), -0.05)

                # Major with ,00: e.g. "2,00 kr." -> "to kroner", "1,00 kr." -> "en krone"
                maj_zero_cents = maj_int + pynutil.delete(dec_sep) + pynutil.delete("00")
                maj_zero_cents_prefix = pynutil.delete(sym) + opt_sp + maj_zero_cents
                maj_zero_cents_suffix = maj_zero_cents + opt_sp + pynutil.delete(sym)

                # Major + minor: e.g. "20,50 kr." -> "tyve kroner og halvtreds øre" (requires non-zero major)
                maj_with_minor = (
                    maj_int
                    + pynutil.delete(dec_sep)
                    + pynutil.insert(" og ")
                    + minor_part
                )
                maj_with_minor_prefix = pynutil.delete(sym) + opt_sp + maj_with_minor
                maj_with_minor_suffix = maj_with_minor + opt_sp + pynutil.delete(sym)

                graphs.extend(
                    [
                        zero_major_prefix,
                        zero_major_suffix,
                        maj_zero_cents_prefix,
                        maj_zero_cents_suffix,
                        maj_with_minor_prefix,
                        maj_with_minor_suffix,
                    ]
                )

        # Shorthand multipliers: e.g. "$50k" -> "halvtreds tusind dollar", "€50k", "$2,5M"
        k_mult = pynutil.delete("k") + pynutil.insert(" tusind")
        m_mult = pynutil.delete(pynini.union("M", "m")) + pynutil.insert(" millioner")
        b_mult = pynutil.delete(pynini.union("B", "b")) + pynutil.insert(" milliarder")
        mag_mult = k_mult | m_mult | b_mult

        mag_usd = (
            pynutil.delete("$")
            + opt_sp
            + (
                cardinal.integer_common + mag_mult
                | cardinal.integer_common + pynini.cross(",", " komma ") + cardinal.single_digit + m_mult
                | cardinal.integer_common + pynini.cross(".", " komma ") + cardinal.single_digit + m_mult
            )
            + pynutil.insert(" dollar")
        )

        mag_eur = (
            pynutil.delete("€")
            + opt_sp
            + (cardinal.integer_common + mag_mult)
            + pynutil.insert(" euro")
        )

        # DKK words with large multipliers: "2 mio. kr." -> "to millioner kroner", "2 md kr." -> "to milliarder kroner"
        large_dkk = (
            cardinal.integer_common
            + opt_sp
            + pynini.cross(pynini.union("mio.", "mio", "millioner"), " millioner kroner")
            + opt_sp + pynutil.delete(pynini.union("kr.", "kr", "DKK"))
        ) | (
            cardinal.integer_common
            + opt_sp
            + pynini.cross(pynini.union("mia.", "mia", "md", "milliarder"), " milliarder kroner")
            + opt_sp + pynutil.delete(pynini.union("kr.", "kr", "DKK"))
        )

        # Per-unit money: e.g. "$15/h" -> "femten dollar i timen", "€20/kg" -> "tyve euro pr. kilogram"
        per_hour = pynini.cross("/h", " i timen") | pynini.cross("/time", " i timen")
        per_kg = pynini.cross("/kg", " pr. kilogram")
        rate_suffix = per_hour | per_kg

        core_money_all = pynini.union(*graphs) | mag_usd | mag_eur | large_dkk

        money_rates = core_money_all + rate_suffix

        # Money ranges: "$10-$20" -> "ti dollar til tyve dollar", "10-20 kr." -> "ti til tyve kroner"
        range_dash = pynini.cross(pynini.union("-", "–", "—"), " til ")
        money_range_repeated = core_money_all + opt_sp + range_dash + opt_sp + core_money_all

        # Single currency at the end: "10-20 kr."
        money_range_trailing = (
            cardinal.integer_common
            + opt_sp
            + range_dash
            + opt_sp
            + core_money_all
        )

        all_money = optional_minus + (
            money_range_repeated
            | money_range_trailing
            | money_rates
            | core_money_all
        )

        all_money = pynutil.add_weight(all_money, -0.05)

        self.graph = all_money.optimize()

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
