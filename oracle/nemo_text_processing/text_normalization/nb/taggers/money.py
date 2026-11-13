# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål currency amounts.
    e.g. 12,50 kr -> tolv kroner og femti øre
         12,01 kr -> tolv kroner og ett øre
         1 kr -> en krone
         2 kr -> to kroner
         100,- kr -> hundre kroner
         0,50 kr -> femti øre
         $50 -> femti dollar
         €10 -> ti euro
         $50k -> femti tusen dollar
         $2,5M -> to komma fem millioner dollar
         -$12,50 -> minus tolv dollar og femti cent
         $10-$20 -> ti dollar til tjue dollar
         $10-€20 -> ti dollar til tjue euro
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        card_masc = cardinal.cardinal_masculine
        card_neut = cardinal.cardinal_neuter

        digits = pynini.closure(NEMO_DIGIT, 1)
        not_one = pynini.difference(digits, pynini.accep("1"))
        not_zero = pynini.difference(digits, pynini.accep("0"))
        non_zero_not_one = pynini.difference(not_zero, pynini.accep("1"))

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        neg_sign = pynini.cross("-", "minus ") | pynini.cross("−", "minus ")
        opt_neg = pynini.closure(neg_sign, 0, 1)

        # -------------------------------------------------------------
        # 1. Norwegian Krone (kr, kr., NOK) and Øre
        # -------------------------------------------------------------
        kr_one = pynini.cross("1", "en krone")
        kr_many = (non_zero_not_one @ card_masc) + pynutil.insert(" kroner")
        kr_int = kr_one | kr_many

        ore_units = pynini.string_map(
            [
                ("01", "ett øre"),
                ("02", "to øre"),
                ("03", "tre øre"),
                ("04", "fire øre"),
                ("05", "fem øre"),
                ("06", "seks øre"),
                ("07", "sju øre"),
                ("08", "åtte øre"),
                ("09", "ni øre"),
            ]
        )
        teens_and_ties = []
        for i in range(10, 100):
            val = pynini.shortestpath(str(i) @ card_neut).string()
            teens_and_ties.append((str(i), val + " øre"))
        ore_all = ore_units | pynini.string_map(teens_and_ties)

        sep = pynutil.delete(",") | pynutil.delete(".")
        kr_symbol_suf = opt_space + (
            pynutil.delete("kr.")
            | pynutil.delete("kr")
            | pynutil.delete("NOK")
            | pynutil.delete("kroner")
        )
        kr_symbol_pre = (
            pynutil.delete("kr.")
            | pynutil.delete("kr")
            | pynutil.delete("NOK")
        ) + opt_space

        # kr + ore: "12,50 kr", "12,01 kr"
        kr_and_ore = kr_int + sep + pynutil.insert(" og ") + ore_all + kr_symbol_suf
        kr_and_ore_pre = kr_symbol_pre + kr_int + sep + pynutil.insert(" og ") + ore_all

        # bare ore: "0,50 kr", "0,01 kr"
        zero_kr_ore = pynutil.delete("0") + sep + ore_all + kr_symbol_suf
        zero_kr_ore_pre = kr_symbol_pre + pynutil.delete("0") + sep + ore_all

        # cash decimals: "100,- kr", "100,-", "10,00 kr"
        zero_decimals = pynutil.delete(",00") | pynutil.delete(",-") | pynutil.delete(".00")
        kr_clean_suf = kr_int + zero_decimals + (kr_symbol_suf | pynutil.delete(""))
        kr_clean_pre = kr_symbol_pre + kr_int + zero_decimals

        # integer only: "100 kr", "kr 100", "50 NOK"
        kr_just_suf = kr_int + kr_symbol_suf
        kr_just_pre = kr_symbol_pre + kr_int

        nok_graph = (
            kr_and_ore
            | kr_and_ore_pre
            | zero_kr_ore
            | zero_kr_ore_pre
            | kr_clean_suf
            | kr_clean_pre
            | kr_just_suf
            | kr_just_pre
        )

        # -------------------------------------------------------------
        # 2. World Currencies: USD, EUR, GBP, JPY, etc.
        # -------------------------------------------------------------
        # Dollar: $, USD
        dollar_one = pynini.cross("1", "en dollar")
        dollar_many = (non_zero_not_one @ card_masc) + pynutil.insert(" dollar")
        dollar_int = dollar_one | dollar_many

        cent_units = pynini.string_map(
            [
                ("01", "ett cent"),
                ("02", "to cent"),
                ("03", "tre cent"),
                ("04", "fire cent"),
                ("05", "fem cent"),
                ("06", "seks cent"),
                ("07", "sju cent"),
                ("08", "åtte cent"),
                ("09", "ni cent"),
            ]
        )
        cent_teens_ties = []
        for i in range(10, 100):
            val = pynini.shortestpath(str(i) @ card_masc).string()
            cent_teens_ties.append((str(i), val + " cent"))
        cent_all = cent_units | pynini.string_map(cent_teens_ties)

        usd_sym_pre = (
            pynutil.delete("$")
            | pynutil.delete("USD")
            | pynutil.delete("US$")
        ) + opt_space
        usd_sym_suf = opt_space + (
            pynutil.delete("$")
            | pynutil.delete("USD")
            | pynutil.delete("dollar")
        )

        usd_and_cents = (
            (usd_sym_pre + dollar_int + sep + pynutil.insert(" og ") + cent_all)
            | (dollar_int + sep + pynutil.insert(" og ") + cent_all + usd_sym_suf)
        )
        usd_int_only = (usd_sym_pre + dollar_int) | (dollar_int + usd_sym_suf)
        usd_clean = (
            (usd_sym_pre + dollar_int + zero_decimals)
            | (dollar_int + zero_decimals + usd_sym_suf)
        )
        usd_zero_cents = (
            (usd_sym_pre + pynutil.delete("0") + sep + cent_all)
            | (pynutil.delete("0") + sep + cent_all + usd_sym_suf)
        )
        usd_graph = usd_and_cents | usd_int_only | usd_clean | usd_zero_cents

        # Euro: €, EUR
        euro_one = pynini.cross("1", "en euro")
        euro_many = (non_zero_not_one @ card_masc) + pynutil.insert(" euro")
        euro_int = euro_one | euro_many

        eur_sym_pre = (pynutil.delete("€") | pynutil.delete("EUR")) + opt_space
        eur_sym_suf = opt_space + (pynutil.delete("€") | pynutil.delete("EUR") | pynutil.delete("euro"))

        eur_and_cents = (
            (eur_sym_pre + euro_int + sep + pynutil.insert(" og ") + cent_all)
            | (euro_int + sep + pynutil.insert(" og ") + cent_all + eur_sym_suf)
        )
        eur_int_only = (eur_sym_pre + euro_int) | (euro_int + eur_sym_suf)
        eur_clean = (
            (eur_sym_pre + euro_int + zero_decimals)
            | (euro_int + zero_decimals + eur_sym_suf)
        )
        eur_zero_cents = (
            (eur_sym_pre + pynutil.delete("0") + sep + cent_all)
            | (pynutil.delete("0") + sep + cent_all + eur_sym_suf)
        )
        eur_graph = eur_and_cents | eur_int_only | eur_clean | eur_zero_cents

        # British Pound: £, GBP
        gbp_int = card_masc + pynutil.insert(" pund")
        gbp_sym_pre = (pynutil.delete("£") | pynutil.delete("GBP")) + opt_space
        gbp_sym_suf = opt_space + (pynutil.delete("£") | pynutil.delete("GBP") | pynutil.delete("britiske pund"))
        gbp_graph = (gbp_sym_pre + gbp_int) | (card_masc + opt_space + pynini.cross("GBP", " britiske pund")) | (gbp_int + gbp_sym_suf)

        # Japanese Yen: ¥, JPY
        jpy_int = card_masc + pynutil.insert(" yen")
        jpy_sym_pre = (pynutil.delete("¥") | pynutil.delete("JPY")) + opt_space
        jpy_sym_suf = opt_space + (pynutil.delete("¥") | pynutil.delete("JPY") | pynutil.delete("yen"))
        jpy_graph = (jpy_sym_pre + jpy_int) | (jpy_int + jpy_sym_suf)

        # Other world currencies with standard symbol/name
        cad_graph = (
            (pynutil.delete("CA$") | pynutil.delete("CAD")) + opt_space + card_masc + pynutil.insert(" kanadiske dollar")
        ) | (
            card_masc + opt_space + pynini.cross("CAD", " kanadiske dollar")
        )
        aud_graph = (
            (pynutil.delete("A$") | pynutil.delete("AUD")) + opt_space + card_masc + pynutil.insert(" australske dollar")
        ) | (
            card_masc + opt_space + pynini.cross("AUD", " australske dollar")
        )
        sek_graph = card_masc + opt_space + pynini.cross("SEK", " svenske kroner")
        dkk_graph = card_masc + opt_space + pynini.cross("DKK", " danske kroner")
        chf_graph = card_masc + opt_space + pynini.cross("CHF", " sveitsiske franc")
        inr_graph = (
            (pynutil.delete("₹") | pynutil.delete("INR") | pynutil.delete("Rs.") | pynutil.delete("Rs"))
            + opt_space
            + card_masc
            + pynutil.insert(" indiske rupier")
        ) | (
            card_masc + opt_space + pynini.cross("INR", " indiske rupier")
        )
        rub_graph = (
            card_masc + opt_space + (pynini.cross("₽", " russiske rubler") | pynini.cross("RUB", " russiske rubler"))
        ) | (
            (pynutil.delete("₽") | pynutil.delete("RUB")) + opt_space + card_masc + pynutil.insert(" russiske rubler")
        )
        brl_graph = (
            (pynutil.delete("R$") | pynutil.delete("BRL")) + opt_space + card_masc + pynutil.insert(" brasilianske real")
        )
        mxn_graph = (
            (pynutil.delete("MX$") | pynutil.delete("MXN")) + opt_space + card_masc + pynutil.insert(" meksikanske pesos")
        )
        krw_graph = card_masc + opt_space + (pynini.cross("₩", " sørkoreanske won") | pynini.cross("KRW", " sørkoreanske won"))
        try_graph = card_masc + opt_space + (pynini.cross("₺", " tyrkiske lire") | pynini.cross("TRY", " tyrkiske lire"))
        ils_graph = card_masc + opt_space + (pynini.cross("₪", " israelske sjekler") | pynini.cross("ILS", " israelske sjekler"))
        uah_graph = card_masc + opt_space + (pynini.cross("₴", " ukrainske hryvnia") | pynini.cross("UAH", " ukrainske hryvnia"))
        vnd_graph = card_masc + opt_space + (pynini.cross("₫", " vietnamesiske dong") | pynini.cross("VND", " vietnamesiske dong"))
        bdt_graph = card_masc + opt_space + (pynini.cross("৳", " bangladeshiske taka") | pynini.cross("BDT", " bangladeshiske taka"))
        ngn_graph = (
            (pynutil.delete("₦") | pynutil.delete("NGN")) + opt_space + card_masc + pynutil.insert(" nigerianske naira")
        )
        php_graph = card_masc + opt_space + (pynini.cross("₱", " filippinske pesos") | pynini.cross("PHP", " filippinske pesos"))
        thb_graph = card_masc + opt_space + (pynini.cross("฿", " thailandske baht") | pynini.cross("THB", " thailandske baht"))
        amd_graph = card_masc + opt_space + (pynini.cross("֏", " armenske dram") | pynini.cross("AMD", " armenske dram"))
        # Bare cents: 25¢ -> tjuefem cent
        bare_cents = card_masc + opt_space + pynini.cross("¢", " cent")

        # Shorthand magnitude ($50k, €50k, $2,5M)
        k_mag = pynini.cross("k", " tusen") | pynini.cross("K", " tusen")
        m_mag = pynini.cross("M", " millioner") | pynini.cross("m", " millioner")
        sep_komma = pynini.cross(",", " komma ") | pynini.cross(".", " komma ")
        shorthand_val = (
            (card_masc + k_mag)
            | (card_masc + sep_komma + (card_masc | card_neut) + m_mag)
            | (card_masc + m_mag)
        )
        usd_short = (
            pynutil.delete("$") + shorthand_val + pynutil.insert(" dollar")
        )
        eur_short = (
            pynutil.delete("€") + shorthand_val + pynutil.insert(" euro")
        )

        # Money rates: $15/h -> femten dollar per time, €20/kg -> tjue euro per kilogram
        time_rate = pynini.cross("/h", " per time") | pynini.cross("/t", " per time")
        mass_rate = pynini.cross("/kg", " per kilogram") | pynini.cross("/kilo", " per kilo")
        rate_unit = time_rate | mass_rate

        single_money_base = (
            nok_graph
            | usd_graph
            | eur_graph
            | gbp_graph
            | jpy_graph
            | cad_graph
            | aud_graph
            | sek_graph
            | dkk_graph
            | chf_graph
            | inr_graph
            | rub_graph
            | brl_graph
            | mxn_graph
            | krw_graph
            | try_graph
            | ils_graph
            | uah_graph
            | vnd_graph
            | bdt_graph
            | ngn_graph
            | php_graph
            | thb_graph
            | amd_graph
            | bare_cents
            | usd_short
            | eur_short
        )

        money_with_rate = single_money_base + rate_unit

        single_money = opt_neg + (money_with_rate | single_money_base)

        # Currency ranges:
        # Same currency: 50-100 kr -> femti til hundre kroner, 10-20 € -> ti til tjue euro
        dash = (
            pynini.cross("-", " til ")
            | pynini.cross("–", " til ")
            | pynini.cross("—", " til ")
        )
        same_kr_range = card_masc + opt_space + dash + opt_space + nok_graph
        same_eur_range = card_masc + opt_space + dash + opt_space + eur_graph
        same_usd_range = card_masc + opt_space + dash + opt_space + usd_graph

        # Mixed currency ranges (retaining both units): $10-$20, $10-€20, €10-$20
        mixed_range = single_money_base + opt_space + dash + opt_space + single_money_base

        all_money = (
            mixed_range
            | same_kr_range
            | same_eur_range
            | same_usd_range
            | single_money
        )

        self.graph = all_money.optimize()
        self.fst = self.graph
