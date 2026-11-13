# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.cs.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.cs.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Czech money amounts, currencies,
    koruna/haléř count agreement, ISO codes, shorthand magnitudes, and mixed ranges.
    """

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        sep = pynini.union(",", ".")
        other_number = pynini.difference(
            pynini.project(cardinal.positive_numbers, "input"), pynini.union("1", "2", "3", "4")
        ) @ cardinal.positive_numbers

        # --- Czech Koruna (CZK / Kč) ---
        czk_sym = pynutil.delete(pynini.union("Kč", "CZK", "czk"))
        hal_sym = pynutil.delete(pynini.union("h.", "h", "hal.", "hal"))

        # Major agreement:
        # 1 -> "jedna koruna"
        # 2, 3, 4 -> "dvě/tři/čtyři koruny"
        # 5+ -> "... korun"
        czk_one = pynini.cross("1", "jedna koruna")
        czk_few = pynini.string_map([
            ("2", "dvě koruny"),
            ("3", "tři koruny"),
            ("4", "čtyři koruny"),
        ])
        czk_other = other_number + pynutil.insert(" korun")
        czk_major_int = (czk_one | czk_few | czk_other).optimize()

        # Minor agreement (haléře):
        # 1 -> "jeden haléř"
        # 2, 3, 4 -> "dva/tři/čtyři haléře"
        # 5+ -> "... haléřů"
        hal_one = pynini.cross("1", "jeden haléř") | pynini.cross("01", "jeden haléř")
        hal_few = pynini.string_map([
            ("2", "dva haléře"),
            ("02", "dva haléře"),
            ("3", "tři haléře"),
            ("03", "tři haléře"),
            ("4", "čtyři haléře"),
            ("04", "čtyři haléře"),
        ])
        hal_other_units = pynini.string_map([
            ("5", "pět"), ("05", "pět"),
            ("6", "šest"), ("06", "šest"),
            ("7", "sedm"), ("07", "sedm"),
            ("8", "osm"), ("08", "osm"),
            ("9", "devět"), ("09", "devět"),
            ("10", "deset"), ("15", "patnáct"),
            ("20", "dvacet"), ("25", "dvacet pět"),
            ("30", "třicet"), ("50", "padesát"),
            ("60", "šedesát"), ("70", "sedmdesát"),
            ("80", "osmdesát"), ("90", "devadesát"),
        ]) + pynutil.insert(" haléřů")
        hal_minor_int = (hal_one | hal_few | hal_other_units | (cardinal.n1_999 + pynutil.insert(" haléřů"))).optimize()

        # Decimal CZK: "5,50 Kč", "1,50 Kč", "2,05 Kč", "10,00 Kč", "0,50 Kč"
        # 10,00 -> "deset korun"
        czk_dec_zero = (
            czk_major_int + pynutil.delete(sep) + pynutil.delete("00") + opt_sp + czk_sym
        ).optimize()
        # 0,50 Kč -> "padesát haléřů"
        czk_dec_cents_only = (
            pynutil.delete("0") + pynutil.delete(sep) + hal_minor_int + opt_sp + czk_sym
        ).optimize()
        # 5,50 Kč -> "pět korun padesát haléřů"
        czk_dec_full = (
            czk_major_int + pynutil.delete(sep) + pynutil.insert(" ") + hal_minor_int + opt_sp + czk_sym
        ).optimize()

        # Discrete "1 Kč 50 h"
        czk_h_combo = (
            czk_major_int + opt_sp + czk_sym + opt_sp + pynutil.insert(" ") + hal_minor_int + opt_sp + hal_sym
        ).optimize()

        # Integer only: "50 Kč", "Kč 50", "50 CZK", "CZK 50"
        czk_int_post = (czk_major_int + opt_sp + czk_sym).optimize()
        czk_int_pre = (czk_sym + opt_sp + czk_major_int).optimize()

        czk_all = (
            czk_dec_zero
            | czk_dec_cents_only
            | czk_dec_full
            | czk_h_combo
            | czk_int_post
            | czk_int_pre
            | (hal_minor_int + opt_sp + hal_sym)
        ).optimize()

        # --- Euro (€ / EUR) ---
        eur_sym = pynutil.delete(pynini.union("€", "EUR", "eur"))

        eur_one = pynini.cross("1", "jedno euro")
        eur_few = pynini.string_map([
            ("2", "dvě eura"),
            ("3", "tři eura"),
            ("4", "čtyři eura"),
        ])
        eur_other = other_number + pynutil.insert(" eur")
        eur_major_int = (eur_one | eur_few | eur_other).optimize()

        cent_one = pynini.cross("1", "jeden cent") | pynini.cross("01", "jeden cent")
        cent_few = pynini.string_map([
            ("2", "dva centy"),
            ("02", "dva centy"),
            ("3", "tři centy"),
            ("03", "tři centy"),
            ("4", "čtyři centy"),
            ("04", "čtyři centy"),
        ])
        cent_other_units = pynini.string_map([
            ("5", "pět"), ("05", "pět"),
            ("6", "šest"), ("06", "šest"),
            ("7", "sedm"), ("07", "sedm"),
            ("8", "osm"), ("08", "osm"),
            ("9", "devět"), ("09", "devět"),
            ("10", "deset"), ("15", "patnáct"),
            ("20", "dvacet"), ("25", "dvacet pět"),
            ("50", "padesát"), ("95", "devadesát pět"),
            ("99", "devadesát devět"),
        ]) + pynutil.insert(" centů")
        cent_minor_int = (cent_one | cent_few | cent_other_units | (cardinal.n1_999 + pynutil.insert(" centů"))).optimize()

        eur_dec_zero = (
            (eur_major_int + pynutil.delete(sep) + pynutil.delete("00") + opt_sp + eur_sym)
            | (eur_sym + opt_sp + eur_major_int + pynutil.delete(sep) + pynutil.delete("00"))
        ).optimize()
        eur_dec_cents_only = (
            (pynutil.delete("0") + pynutil.delete(sep) + cent_minor_int + opt_sp + eur_sym)
            | (eur_sym + opt_sp + pynutil.delete("0") + pynutil.delete(sep) + cent_minor_int)
        ).optimize()
        eur_dec_full = (
            (eur_major_int + pynutil.delete(sep) + pynutil.insert(" ") + cent_minor_int + opt_sp + eur_sym)
            | (eur_sym + opt_sp + eur_major_int + pynutil.delete(sep) + pynutil.insert(" ") + cent_minor_int)
        ).optimize()

        eur_int_post = (eur_major_int + opt_sp + eur_sym).optimize()
        eur_int_pre = (eur_sym + opt_sp + eur_major_int).optimize()

        eur_all = (
            eur_dec_zero
            | eur_dec_cents_only
            | eur_dec_full
            | eur_int_post
            | eur_int_pre
        ).optimize()

        # --- US Dollar ($ / USD) ---
        usd_sym = pynutil.delete(pynini.union("$", "USD", "usd"))

        usd_one = pynini.cross("1", "jeden dolar")
        usd_few = pynini.string_map([
            ("2", "dva dolary"),
            ("3", "tři dolary"),
            ("4", "čtyři dolary"),
        ])
        usd_other = other_number + pynutil.insert(" dolarů")
        usd_major_int = (usd_one | usd_few | usd_other).optimize()

        usd_dec_zero = (
            (usd_sym + opt_sp + usd_major_int + pynutil.delete(sep) + pynutil.delete("00"))
            | (usd_major_int + pynutil.delete(sep) + pynutil.delete("00") + opt_sp + usd_sym)
        ).optimize()
        usd_dec_cents_only = (
            (usd_sym + opt_sp + pynutil.delete("0") + pynutil.delete(sep) + cent_minor_int)
            | (pynutil.delete("0") + pynutil.delete(sep) + cent_minor_int + opt_sp + usd_sym)
        ).optimize()
        usd_dec_full = (
            (usd_sym + opt_sp + usd_major_int + pynutil.delete(sep) + pynutil.insert(" ") + cent_minor_int)
            | (usd_major_int + pynutil.delete(sep) + pynutil.insert(" ") + cent_minor_int + opt_sp + usd_sym)
        ).optimize()

        usd_int_pre = (usd_sym + opt_sp + usd_major_int).optimize()
        usd_int_post = (usd_major_int + opt_sp + usd_sym).optimize()

        usd_all = (
            usd_dec_zero
            | usd_dec_cents_only
            | usd_dec_full
            | usd_int_pre
            | usd_int_post
        ).optimize()

        # --- British Pound (£ / GBP) ---
        gbp_sym = pynutil.delete(pynini.union("£", "GBP", "gbp"))
        gbp_one = pynini.cross("1", "jedna libra")
        gbp_few = pynini.string_map([("2", "dvě libry"), ("3", "tři libry"), ("4", "čtyři libry")])
        gbp_other = other_number + pynutil.insert(" liber")
        gbp_major_int = (gbp_one | gbp_few | gbp_other).optimize()

        gbp_all = (
            (gbp_sym + opt_sp + gbp_major_int)
            | (gbp_major_int + opt_sp + gbp_sym)
        ).optimize()

        # Shorthand money: "$50k" -> "padesát tisíc dolarů", "€50k" -> "padesát tisíc eur", "$2.5M" -> "dvě celé pět milionu dolarů"
        money_50k_usd = (
            pynutil.delete("$") + cardinal.cardinal_numbers + pynutil.delete(pynini.union("k", "K")) + pynutil.insert(" tisíc dolarů")
        )
        money_50k_eur = (
            pynutil.delete("€") + cardinal.cardinal_numbers + pynutil.delete(pynini.union("k", "K")) + pynutil.insert(" tisíc eur")
        )
        money_m_usd = (
            pynutil.delete("$") + (cardinal.cardinal_numbers | decimal.decimal_numbers) + pynutil.delete(pynini.union("M", "m")) + pynutil.insert(" milionu dolarů")
        )
        shorthand_money = (money_50k_usd | money_50k_eur | money_m_usd).optimize()

        # Other world currencies and ISO codes
        world_currencies = [
            (["CHF"], "švýcarský frank", "švýcarské franky", "švýcarských franků", "m"),
            (["CAD", "CA$"], "kanadský dolar", "kanadské dolary", "kanadských dolarů", "m"),
            (["INR", "₹", "Rs.", "Rs"], "indická rupie", "indické rupie", "indických rupií", "f"),
            (["AUD", "A$"], "australský dolar", "australské dolary", "australských dolarů", "m"),
            (["BRL", "R$"], "brazilský real", "brazilské realy", "brazilských realů", "m"),
            (["MXN", "MX$"], "mexické peso", "mexická pesa", "mexických pes", "n"),
            (["RUB", "₽", "руб."], "rubl", "rubly", "rublů", "m"),
            (["KRW", "₩"], "won", "wony", "wonů", "m"),
            (["TRY", "₺"], "turecká lira", "turecké liry", "tureckých lir", "f"),
            (["ILS", "₪"], "šekel", "šekely", "šekelů", "m"),
            (["UAH", "₴"], "hřivna", "hřivny", "hřiven", "f"),
            (["VND", "₫"], "dong", "dongy", "dongů", "m"),
            (["BDT", "৳"], "bangladéšská taka", "bangladéšské taky", "bangladéšských tak", "f"),
            (["NGN", "₦"], "nigerijská naira", "nigerijské nairy", "nigerijských nair", "f"),
            (["PHP", "₱"], "filipínské peso", "filipínská pesa", "filipínských pes", "n"),
            (["THB", "฿"], "thajský baht", "thajské bahty", "thajských bahtů", "m"),
            (["AMD", "֏"], "arménský dram", "arménské dramy", "arménských dramů", "m"),
            (["¢"], "cent", "centy", "centů", "m"),
        ]
        currency_graphs = []
        for symbols, singular, few, many, gender in world_currencies:
            one_word = {"m": "jeden", "f": "jedna", "n": "jedno"}[gender]
            two_word = "dva" if gender == "m" else "dvě"
            amount = (
                pynini.cross("1", f"{one_word} {singular}")
                | pynini.string_map([("2", two_word), ("3", "tři"), ("4", "čtyři")]) + pynutil.insert(f" {few}")
                | other_number + pynutil.insert(f" {many}")
            )
            symbol = pynutil.delete(pynini.union(*symbols))
            currency_graphs.extend([symbol + opt_sp + amount, amount + opt_sp + symbol])
        other_cur = pynini.union(*currency_graphs)

        # Per-unit money: "$15/h" -> "patnáct dolarů za hodinu", "€20/kg" -> "dvacet eur za kilogram"
        per_h = pynutil.delete("/h") + pynutil.insert(" za hodinu")
        per_kg = pynutil.delete("/kg") + pynutil.insert(" za kilogram")
        money_per_unit = (
            (usd_int_pre + opt_sp + per_h)
            | (eur_int_pre + opt_sp + per_kg)
            | (czk_int_post + opt_sp + (per_h | per_kg))
        ).optimize()

        # Negatives: "-$12.50" -> "mínus dvanáct dolarů padesát centů", "-12,50 €" -> "mínus dvanáct eur padesát centů"
        neg_sym = pynini.cross("-", "mínus ") | pynini.cross("−", "mínus ")
        money_base = (
            shorthand_money
            | other_cur
            | czk_all
            | eur_all
            | usd_all
            | gbp_all
            | money_per_unit
        ).optimize()

        neg_money = (neg_sym + money_base).optimize()

        # Ranges:
        # Same currency: "$10-$20" -> "deset dolarů až dvacet dolarů", "10-20 €" -> "deset až dvacet eur"
        # Mixed currency: "$10-€20" -> "deset dolarů až dvacet eur"
        dash = pynini.cross("-", " až ") | pynini.cross("–", " až ") | pynini.cross("—", " až ")
        parens_open = pynutil.delete("(")
        parens_close = pynutil.delete(")")

        money_range = (
            money_base + opt_sp + dash + opt_sp + money_base
        ).optimize()

        # Also simple: "10-20 €" where only second has currency symbol
        cur_unit_range = (
            cardinal.cardinal_numbers
            + opt_sp
            + dash
            + opt_sp
            + (eur_int_post | czk_int_post | usd_int_post)
        ).optimize()

        money_with_parens = (
            parens_open + money_base + parens_close
        ).optimize()

        self.fst = (
            money_range
            | cur_unit_range
            | money_with_parens
            | neg_money
            | money_base
        ).optimize()
