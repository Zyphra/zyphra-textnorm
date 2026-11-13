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

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    NEMO_SIGMA,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian money expressions.
    Includes Bulgarian Lev & Stotinki, Euro, US Dollar, British Pound,
    Russian Ruble, and all major world currencies with native gender agreement.
    e.g. 5 лв. -> tokens { name: "пет лева" }
         10,50 лв. -> tokens { name: "десет лева и петдесет стотинки" }
         0,50 лв. -> tokens { name: "петдесет стотинки" }
         €99.95 -> tokens { name: "деветдесет и девет евро и деветдесет и пет цента" }
         $1,234.56 -> tokens { name: "хиляда двеста тридесет и четири долара и петдесет и шест цента" }
         $50k -> tokens { name: "петдесет хиляди долара" }
         $2.5M -> tokens { name: "два цяло и пет милиона долара" }
         -$12.50 -> tokens { name: "минус дванадесет долара и петдесет цента" }
         $15/h -> tokens { name: "петнадесет долара на час" }
         10-20 лв. -> tokens { name: "десет до двадесет лева" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        card_m = cardinal.cardinal_m
        card_f = cardinal.cardinal_f
        card_n = cardinal.cardinal_n

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # -------------------------------------------------------------
        # 1. BULGARIAN LEV & STOTINKI
        # -------------------------------------------------------------
        # Lev symbols and abbreviations
        lev_words = pynini.union("лв.", "лв", "лева", "лев", "BGN")

        # 1 лв -> един лев
        # 2+ лв -> dva лева, пет лева...
        lev_one = pynini.cross("1", "един лев") + opt_sp + pynutil.delete(lev_words)
        lev_other = card_m + opt_sp + pynutil.delete(lev_words) + pynutil.insert(" лева")
        lev_integer = (lev_one | lev_other).optimize()

        # Stotinki alone: "50 ст.", "1 ст."
        stot_words = pynini.union("ст.", "ст", "стотинки", "стотинка")
        stot_one = pynini.cross("1", "една стотинка") + opt_sp + pynutil.delete(stot_words)
        stot_other = card_f + opt_sp + pynutil.delete(stot_words) + pynutil.insert(" стотинки")
        stot_integer = (stot_one | stot_other).optimize()

        # Lev decimal: "10,50 лв.", "10.50 лв.", "1,01 лв.", "0,50 лв."
        # Minor part (2 digits):
        minor_stot_00 = pynutil.delete("00")
        minor_stot_01 = pynini.cross("01", "една стотинка")
        minor_stot_units = pynutil.delete("0") + (NEMO_DIGIT - "0" - "1") @ card_f + pynutil.insert(" стотинки")
        minor_stot_tens = pynini.string_map([
            ("10", "десет стотинки"), ("20", "двадесет стотинки"), ("30", "тридесет стотинки"),
            ("40", "четиридесет стотинки"), ("50", "петдесет стотинки"), ("60", "шестдесет стотинки"),
            ("70", "седемдесет стотинки"), ("80", "осемдесет стотинки"), ("90", "деветдесет стотинки")
        ])
        minor_stot_other = (NEMO_DIGIT**2 - pynini.union("00", "01", "10", "20", "30", "40", "50", "60", "70", "80", "90")) @ card_f + pynutil.insert(" стотинки")
        minor_stot_voiced = minor_stot_01 | minor_stot_units | minor_stot_tens | minor_stot_other

        dec_sep = pynutil.delete(pynini.union(",", "."))

        # "0,50 лв." -> "петдесет стотинки"
        lev_int_for_dec = pynini.cross("1", "един лев") | (card_m + pynutil.insert(" лева"))
        # "0,50 лв." -> "петдесет стотинки"
        lev_zero_major = pynutil.delete("0") + dec_sep + minor_stot_voiced + opt_sp + pynutil.delete(lev_words)
        # "10.00 лв." -> "десет лева"
        lev_zero_minor = lev_int_for_dec + dec_sep + minor_stot_00 + opt_sp + pynutil.delete(lev_words)
        # "10,50 лв." -> "десет лева и петдесет стотинки"
        lev_major_minor = (
            lev_int_for_dec
            + dec_sep
            + pynutil.insert(" и ")
            + minor_stot_voiced
            + opt_sp
            + pynutil.delete(lev_words)
        )

        neg_sign = pynini.cross(pynini.union("-", "−"), "минус ")
        all_lev_pos = (
            pynutil.add_weight(lev_zero_major, -0.01)
            | lev_major_minor
            | lev_zero_minor
            | lev_integer
            | stot_integer
        ).optimize()
        all_lev = (all_lev_pos | (neg_sign + all_lev_pos)).optimize()

        # -------------------------------------------------------------
        # 2. EURO (€ / EUR)
        # -------------------------------------------------------------
        # Cent minor part:
        minor_cent_00 = pynutil.delete("00")
        minor_cent_01 = pynini.cross("01", "един цент")
        minor_cent_units = pynutil.delete("0") + (NEMO_DIGIT - "0" - "1") @ card_m + pynutil.insert(" цента")
        minor_cent_tens = pynini.string_map([
            ("10", "десет цента"), ("20", "двадесет цента"), ("30", "тридесет цента"),
            ("40", "четиридесет цента"), ("50", "петдесет цента"), ("60", "шестдесет цента"),
            ("70", "седемдесет цента"), ("80", "осемдесет цента"), ("90", "деветдесет цента")
        ])
        minor_cent_other = (NEMO_DIGIT**2 - pynini.union("00", "01", "10", "20", "30", "40", "50", "60", "70", "80", "90")) @ card_m + pynutil.insert(" цента")
        minor_cent_voiced = minor_cent_01 | minor_cent_units | minor_cent_tens | minor_cent_other

        euro_sym = pynini.union("€", "EUR", "евро")
        euro_int = card_n + pynutil.insert(" евро")

        # Leading or trailing €
        # "€50" or "50 €"
        eur_leading_int = pynutil.delete(euro_sym) + opt_sp + euro_int
        eur_trailing_int = euro_int + opt_sp + pynutil.delete(euro_sym)

        # Decimals: €99.95, 99,95 €
        eur_lead_dec = (
            pynutil.delete(euro_sym)
            + opt_sp
            + euro_int
            + dec_sep
            + pynutil.insert(" и ")
            + minor_cent_voiced
        )
        eur_trail_dec = (
            euro_int
            + dec_sep
            + pynutil.insert(" и ")
            + minor_cent_voiced
            + opt_sp
            + pynutil.delete(euro_sym)
        )
        # "€0.99", "0,99 €" -> "деветдесет и девет цента"
        eur_zero_major = (
            pynutil.delete(pynini.closure(euro_sym, 0, 1))
            + opt_sp
            + pynutil.delete("0")
            + dec_sep
            + minor_cent_voiced
            + opt_sp
            + pynutil.delete(pynini.closure(euro_sym, 0, 1))
        )
        # "€10.00", "10,00 €" -> "десет евро"
        eur_zero_minor = (
            pynutil.delete(pynini.closure(euro_sym, 0, 1))
            + opt_sp
            + euro_int
            + dec_sep
            + minor_cent_00
            + opt_sp
            + pynutil.delete(pynini.closure(euro_sym, 0, 1))
        )

        all_euro = (
            pynutil.add_weight(eur_zero_major, -0.01)
            | eur_zero_minor
            | eur_lead_dec
            | eur_trail_dec
            | eur_leading_int
            | eur_trailing_int
        ).optimize()

        # -------------------------------------------------------------
        # 3. US DOLLAR ($ / USD / щ.д.)
        # -------------------------------------------------------------
        usd_sym = pynini.union("$", "USD", "щ.д.")
        usd_one = pynini.cross("1", "един долар")
        usd_other = card_m + pynutil.insert(" долара")
        usd_int = usd_one | usd_other

        # Strip commas in $1,234.56
        strip_thousands = (
            pynini.closure(NEMO_DIGIT, 1, 3)
            + pynini.closure(pynutil.delete(pynini.union(",", " ", "\u00a0")) + NEMO_DIGIT**3, 1, 3)
        )
        usd_int_clean = (strip_thousands @ usd_int) | usd_int

        usd_leading_int = pynutil.delete(usd_sym) + opt_sp + usd_int_clean
        usd_trailing_int = usd_int_clean + opt_sp + pynutil.delete(usd_sym)

        usd_lead_dec = (
            pynutil.delete(usd_sym)
            + opt_sp
            + usd_int_clean
            + dec_sep
            + pynutil.insert(" и ")
            + minor_cent_voiced
        )
        usd_trail_dec = (
            usd_int_clean
            + dec_sep
            + pynutil.insert(" и ")
            + minor_cent_voiced
            + opt_sp
            + pynutil.delete(usd_sym)
        )
        usd_zero_major = (
            pynutil.delete(pynini.closure(usd_sym, 0, 1))
            + opt_sp
            + pynutil.delete("0")
            + dec_sep
            + minor_cent_voiced
            + opt_sp
            + pynutil.delete(pynini.closure(usd_sym, 0, 1))
        )
        usd_zero_minor = (
            pynutil.delete(pynini.closure(usd_sym, 0, 1))
            + opt_sp
            + usd_int_clean
            + dec_sep
            + minor_cent_00
            + opt_sp
            + pynutil.delete(pynini.closure(usd_sym, 0, 1))
        )

        all_usd = (
            pynutil.add_weight(usd_zero_major, -0.01)
            | usd_zero_minor
            | usd_lead_dec
            | usd_trail_dec
            | usd_leading_int
            | usd_trailing_int
        ).optimize()

        # -------------------------------------------------------------
        # 4. OTHER MAJOR WORLD CURRENCIES
        # -------------------------------------------------------------
        # British Pound (£ / GBP) -> паунда / лири
        gbp_sym = pynini.union("£", "GBP")
        gbp_int = (
            pynini.cross("1", "един паунд")
            | (card_m + pynutil.insert(" паунда"))
        )
        gbp = (
            pynutil.delete(gbp_sym) + opt_sp + gbp_int
            | gbp_int + opt_sp + pynutil.delete(gbp_sym)
        ).optimize()

        # Russian Ruble (₽ / руб. / RUB) -> рубли / рубла
        rub_sym = pynini.union("₽", "руб.", "руб", "рубли", "RUB")
        rub_int = (
            pynini.cross("1", "една рубла")
            | pynini.cross("2", "две рубли")
            | (card_f + pynutil.insert(" рубли"))
        )
        rub = (
            pynutil.delete(rub_sym) + opt_sp + rub_int
            | rub_int + opt_sp + pynutil.delete(rub_sym)
        ).optimize()

        # Japanese Yen (¥ / JPY) -> йени
        jpy_sym = pynini.union("¥", "JPY")
        strip_commas = pynini.closure(NEMO_DIGIT, 1, 3) + pynini.closure(pynutil.delete(",") + NEMO_DIGIT**3, 1, 3)
        jpy_num = (strip_commas @ card_f) | card_f
        jpy = (
            pynutil.delete(jpy_sym) + opt_sp + jpy_num + pynutil.insert(" йени")
            | jpy_num + opt_sp + pynutil.delete(jpy_sym) + pynutil.insert(" йени")
        ).optimize()

        # Other ISO codes & symbols
        other_cur = (
            (card_m + opt_sp + pynini.cross("CHF", " швейцарски франка"))
            | (card_m + opt_sp + pynini.cross(pynini.union("CAD", "CA$"), " канадски долара"))
            | (pynutil.delete("CA$") + opt_sp + card_m + pynutil.insert(" канадски долара"))
            | (card_m + opt_sp + pynini.cross(pynini.union("AUD", "A$"), " австралийски долара"))
            | (pynutil.delete("A$") + opt_sp + card_m + pynutil.insert(" австралийски долара"))
            | (card_m + opt_sp + pynini.cross(pynini.union("BRL", "R$"), " бразилски реала"))
            | (pynutil.delete("R$") + opt_sp + card_m + pynutil.insert(" бразилски реала"))
            | (card_n + opt_sp + pynini.cross(pynini.union("MXN", "MX$"), " мексикански песо"))
            | (pynutil.delete("MX$") + opt_sp + card_n + pynutil.insert(" мексикански песо"))
            | (card_f + opt_sp + pynini.cross(pynini.union("INR", "₹"), " индийски рупии"))
            | (pynutil.delete(pynini.union("₹", "Rs.", "Rs")) + opt_sp + card_f + pynutil.insert(" индийски рупии"))
            | (card_m + opt_sp + pynini.cross(pynini.union("KRW", "₩"), " вона"))
            | (card_f + opt_sp + pynini.cross(pynini.union("TRY", "₺"), " турски лири"))
            | (card_m + opt_sp + pynini.cross(pynini.union("ILS", "₪"), " шекела"))
            | (card_f + opt_sp + pynini.cross(pynini.union("UAH", "₴"), " гривни"))
            | (card_m + opt_sp + pynini.cross(pynini.union("VND", "₫"), " виетнамски донга"))
            | (card_f + opt_sp + pynini.cross(pynini.union("BDT", "৳"), " бангладешки таки"))
            | (pynutil.delete("₦") + opt_sp + card_f + pynutil.insert(" нигерийски найри"))
            | (card_n + opt_sp + pynini.cross(pynini.union("PHP", "₱"), " филипински песо"))
            | (card_m + opt_sp + pynini.cross(pynini.union("THB", "฿"), " тайландски бата"))
            | (card_m + opt_sp + pynini.cross(pynini.union("AMD", "֏"), " арменски драма"))
            | (card_m + opt_sp + pynutil.delete("¢") + pynutil.insert(" цента"))
        ).optimize()

        # Shorthand magnitude ($50k, €50k, $2.5M)
        k_mag = pynini.cross(pynini.union("k", "K"), " хиляди")
        m_mag = pynini.cross(pynini.union("M", "млн.", "млн"), " милиона")

        shorthand_usd = (
            pynutil.delete("$")
            + opt_sp
            + (
                (card_f + k_mag + pynutil.insert(" долара"))
                | ((card_m + pynini.cross(pynini.union(",", "."), " цяло и ") + (NEMO_DIGIT @ card_m)) + pynutil.insert(" милиона долара") + opt_sp + pynutil.delete(pynini.union("M", "млн.", "млн")))
                | (card_m + m_mag + pynutil.insert(" долара"))
            )
        )
        shorthand_eur = (
            pynutil.delete("€")
            + opt_sp
            + (
                (card_f + k_mag + pynutil.insert(" евро"))
                | ((card_m + pynini.cross(pynini.union(",", "."), " цяло и ") + (NEMO_DIGIT @ card_m)) + pynutil.insert(" милиона евро") + opt_sp + pynutil.delete(pynini.union("M", "млн.", "млн")))
                | (card_m + m_mag + pynutil.insert(" евро"))
            )
        )
        shorthand = shorthand_usd | shorthand_eur

        # Per unit money ($15/h, €20/kg)
        per_hour = pynini.cross(pynini.union("/h", "/ч", "/час"), " на час")
        per_kg = pynini.cross(pynini.union("/kg", "/кг"), " на килограм")
        per_unit = per_hour | per_kg

        money_rates = (
            (all_usd + opt_sp + per_unit)
            | (all_euro + opt_sp + per_unit)
            | (all_lev + opt_sp + per_unit)
        ).optimize()

        # Ranges: 10-20 лв., 10-20 €, $10-$20
        dash = pynini.cross(pynini.union("-", "–", "—"), " до ")
        money_range = (
            ((all_usd | all_euro | all_lev) + opt_sp + dash + opt_sp + (all_usd | all_euro | all_lev))
            | (card_m + opt_sp + dash + opt_sp + all_lev)
            | (card_n + opt_sp + dash + opt_sp + all_euro)
            | (pynutil.delete("$") + card_m + opt_sp + dash + opt_sp + pynutil.delete("$") + card_m + pynutil.insert(" долара"))
            | (all_usd + opt_sp + dash + opt_sp + all_usd)
        ).optimize()

        # Negative money (-$12.50, -12,50 €, -12,50 лв.)
        neg_sign = pynini.cross(pynini.union("-", "−"), "минус ")
        neg_money = neg_sign + (all_usd | all_euro | all_lev).optimize()

        all_money_graphs = (
            pynutil.add_weight(shorthand, 0.95)
            | pynutil.add_weight(money_rates, 0.96)
            | pynutil.add_weight(money_range, 0.98)
            | pynutil.add_weight(neg_money, 1.0)
            | pynutil.add_weight(all_lev, 1.05)
            | pynutil.add_weight(all_euro, 1.05)
            | pynutil.add_weight(all_usd, 1.05)
            | pynutil.add_weight(gbp, 1.08)
            | pynutil.add_weight(rub, 1.08)
            | pynutil.add_weight(jpy, 1.08)
            | pynutil.add_weight(other_cur, 1.1)
        ).optimize()

        graph = pynutil.insert('name: "') + convert_space(all_money_graphs) + pynutil.insert('"')
        self.fst = graph.optimize()
