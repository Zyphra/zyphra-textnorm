# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import (
    NEMO_MINUS,
    wrap_name,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Dutch currency expressions.
    Handles:
    - Euro: €50, 50 €, €5,50, 99,95 €, €10.00, €0,99, -12,50 €
    - Dollar: $50, $12,50, -$12,50, $1,234.56, CA$50, A$100, R$100, MX$100
    - Pound: £50
    - Yen: ¥10000, ¥10.000
    - World ISO currencies and symbols: CHF, CAD, INR, ₹, Rs., RUB, ₽, TRY, ₺, ILS, ₪, UAH, ₴,
      VND, ₫, BDT, ৳, NGN, ₦, PHP, ₱, THB, ฿, AMD, ֏, KRW, ₩, USD, EUR
    - Shorthand k/M/B: €50k, $50k, $2,5M
    - Rates: $15/h, €20/kg
    - Ranges: 10-20 €, $10-$20, $10-€20, €10-$20 (preserving both currencies)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        dash = pynini.union("-", "–", "—")

        # Currency symbols and names
        # Single currency names in Dutch remain singular after numbers (euro, cent, dollar, pond, yen, etc.)
        currencies = [
            ("€", "euro", "cent"),
            ("EUR", "euro", "cent"),
            ("$", "dollar", "cent"),
            ("USD", "Amerikaanse dollar", "cent"),
            ("CA$", "Canadese dollar", "cent"),
            ("CAD", "Canadese dollar", "cent"),
            ("A$", "Australische dollar", "cent"),
            ("AUD", "Australische dollar", "cent"),
            ("£", "pond", "pence"),
            ("GBP", "Britse pond", "pence"),
            ("¥", "yen", "sen"),
            ("JPY", "yen", "sen"),
            ("CHF", "Zwitserse frank", "centime"),
            ("₹", "Indiase roepie", "paisa"),
            ("Rs.", "Indiase roepie", "paisa"),
            ("Rs", "Indiase roepie", "paisa"),
            ("INR", "Indiase roepie", "paisa"),
            ("₽", "Russische roebel", "kopeke"),
            ("RUB", "Russische roebel", "kopeke"),
            ("₺", "Turkse lira", "kuruş"),
            ("TRY", "Turkse lira", "kuruş"),
            ("₪", "Israëlische sjekel", "agora"),
            ("ILS", "Israëlische sjekel", "agora"),
            ("₴", "Oekraïense hryvnia", "kopiika"),
            ("UAH", "Oekraïense hryvnia", "kopiika"),
            ("₫", "Vietnamese dong", "xu"),
            ("VND", "Vietnamese dong", "xu"),
            ("৳", "Bengaalse taka", "poisha"),
            ("BDT", "Bengaalse taka", "poisha"),
            ("₦", "Nigeriaanse naira", "kobo"),
            ("NGN", "Nigeriaanse naira", "kobo"),
            ("₱", "Filipijnse peso", "centavo"),
            ("PHP", "Filipijnse peso", "centavo"),
            ("฿", "Thaise baht", "satang"),
            ("THB", "Thaise baht", "satang"),
            ("֏", "Armeense dram", "luma"),
            ("AMD", "Armeense dram", "luma"),
            ("₩", "won", "jeon"),
            ("KRW", "won", "jeon"),
            ("R$", "Braziliaanse real", "centavo"),
            ("BRL", "Braziliaanse real", "centavo"),
            ("MX$", "Mexicaanse peso", "centavo"),
            ("MXN", "Mexicaanse peso", "centavo"),
        ]

        # Cent values (01 to 99)
        cents_graph = cardinal.nums_1_to_99

        dec_sep = pynini.union(",", ".")

        major_amount = cardinal.cardinal_numbers

        # Construct major + minor expressions for each currency
        currency_rules = []
        curr_symbol_map = {}

        for sym, maj_word, min_word in currencies:
            curr_symbol_map[sym] = maj_word

            # 1. Zero cents, e.g. "€10,00" or "$10.00" -> "tien euro"
            zero_cents = pynutil.delete(dec_sep) + pynutil.delete("00")

            # 2. Cents only, e.g. "€0,99" or "0,99 €" -> "negenennegentig cent"
            cents_only_lead = (
                pynutil.delete(sym)
                + opt_space
                + pynutil.delete("0")
                + pynutil.delete(dec_sep)
                + cents_graph
                + pynutil.insert(f" {min_word}")
            )
            cents_only_trail = (
                pynutil.delete("0")
                + pynutil.delete(dec_sep)
                + cents_graph
                + opt_space
                + pynutil.delete(sym)
                + pynutil.insert(f" {min_word}")
            )

            # 3. Major + Minor: "€5,50" -> "vijf euro en vijftig cent"
            # Leading symbol: "€5,50", "€10,00"
            maj_min_lead = (
                pynutil.delete(sym)
                + opt_space
                + major_amount
                + (
                    zero_cents + pynutil.insert(f" {maj_word}")
                    | (
                        pynutil.delete(dec_sep)
                        + pynutil.insert(f" {maj_word} en ")
                        + cents_graph
                        + pynutil.insert(f" {min_word}")
                    )
                )
            )

            # Trailing symbol: "5,50 €", "10,00 €"
            maj_min_trail = (
                major_amount
                + (
                    zero_cents
                    + opt_space
                    + pynutil.delete(sym)
                    + pynutil.insert(f" {maj_word}")
                    | (
                        pynutil.delete(dec_sep)
                        + pynutil.insert(f" {maj_word} en ")
                        + cents_graph
                        + opt_space
                        + pynutil.delete(sym)
                        + pynutil.insert(f" {min_word}")
                    )
                )
            )

            # 4. Major only: "€50", "50 €", "500 USD"
            maj_only_lead = (
                pynutil.delete(sym)
                + opt_space
                + major_amount
                + pynutil.insert(f" {maj_word}")
            )
            maj_only_trail = (
                major_amount
                + opt_space
                + pynutil.delete(sym)
                + pynutil.insert(f" {maj_word}")
            )

            # Shorthand k/M/B: "€50k" -> "vijftigduizend euro", "$2,5M" -> "twee komma vijf miljoen dollar"
            k_lead = (
                pynutil.delete(sym)
                + major_amount
                + pynutil.delete(pynini.union("k", "K"))
                + pynutil.insert(f"duizend {maj_word}")
            )
            m_lead = (
                pynutil.delete(sym)
                + major_amount
                + pynutil.delete(dec_sep)
                + pynutil.insert(" komma ")
                + cardinal.digit
                + pynutil.delete(pynini.union("m", "M"))
                + pynutil.insert(f" miljoen {maj_word}")
            )
            k_trail = (
                major_amount
                + pynutil.delete(pynini.union("k", "K"))
                + opt_space
                + pynutil.delete(sym)
                + pynutil.insert(f"duizend {maj_word}")
            )

            # Per-unit rates: "$15/h" -> "vijftien dollar per uur", "€20/kg" -> "twintig euro per kilogram"
            rate_units = pynini.string_map(
                [
                    ("h", "uur"),
                    ("uur", "uur"),
                    ("hr", "uur"),
                    ("kg", "kilogram"),
                    ("m", "meter"),
                    ("km", "kilometer"),
                    ("maand", "maand"),
                    ("jaar", "jaar"),
                    ("dag", "dag"),
                ]
            )
            rate_lead = (
                maj_only_lead
                + pynutil.delete("/")
                + pynutil.insert(" per ")
                + rate_units
            )
            rate_trail = (
                maj_only_trail
                + pynutil.delete("/")
                + pynutil.insert(" per ")
                + rate_units
            )

            rule = (
                pynutil.add_weight(cents_only_lead, -0.05)
                | pynutil.add_weight(cents_only_trail, -0.05)
                | maj_min_lead
                | maj_min_trail
                | k_lead
                | m_lead
                | k_trail
                | rate_lead
                | rate_trail
                | maj_only_lead
                | maj_only_trail
            )
            currency_rules.append(rule)

        all_single_money = pynini.union(*currency_rules).optimize()

        # Negative money: "-€12,50", "-12,50 €", "-$12.50"
        neg_money = (
            pynini.cross(NEMO_MINUS, "min ")
            + all_single_money
        )

        # Currency ranges:
        # Same currency range: "10-20 €" -> "tien tot twintig euro", "10 € - 20 €" -> "tien euro tot twintig euro"
        same_curr_range = (
            major_amount
            + delete_space
            + pynini.cross(dash, " tot ")
            + delete_space
            + all_single_money
        )

        # Mixed / repeated currency ranges: "$10-$20" -> "tien dollar tot twintig dollar"
        # "$10-€20" -> "tien dollar tot twintig euro"
        mixed_curr_range = (
            all_single_money
            + delete_space
            + pynini.cross(dash, " tot ")
            + delete_space
            + all_single_money
        )

        self.spoken_money = (
            pynutil.add_weight(mixed_curr_range, 0.95)
            | pynutil.add_weight(same_curr_range, 0.96)
            | pynutil.add_weight(neg_money, 0.98)
            | pynutil.add_weight(all_single_money, 1.0)
        ).optimize()

        self.fst = wrap_name(self.spoken_money)
