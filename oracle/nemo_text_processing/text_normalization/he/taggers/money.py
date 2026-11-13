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
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.he.taggers.decimal import DecimalFst


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew money expressions.
    Handles Israeli Shekels (₪, ש"ח, ILS) with agorot, Dollars ($), Euros (€),
    Pounds (£), world currencies, shorthand magnitudes ($50k, €50k, $2.5M),
    negative amounts (-$12.50), rates ($15/h, €20/kg), and ranges ($10-$20).
    """

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        req_space = pynutil.delete(" ")

        digits_1_10 = pynini.union(*[str(i) for i in range(1, 11)]).optimize()
        num_m_over_10 = (
            pynini.difference(pynini.project(cardinal.base_num_m, "input"), digits_1_10).optimize()
            @ cardinal.base_num_m
        )
        num_f_over_10 = (
            pynini.difference(pynini.project(cardinal.base_num_f, "input"), digits_1_10).optimize()
            @ cardinal.base_num_f
        )

        # ----------------- Shekel Number Forms -----------------
        # Masculine counted for 1-10
        shekel_1 = pynini.cross("1", "שקל אחד")
        shekel_2 = pynini.cross("2", "שני שקלים")
        shekel_3_10 = pynini.string_map([
            ("3", "שלושה שקלים"),
            ("4", "ארבעה שקלים"),
            ("5", "חמישה שקלים"),
            ("6", "שישה שקלים"),
            ("7", "שבעה שקלים"),
            ("8", "שמונה שקלים"),
            ("9", "תשעה שקלים"),
            ("10", "עשרה שקלים"),
        ])
        shekel_over_10 = (
            pynutil.add_weight(num_m_over_10, -0.05)
            | pynutil.add_weight(num_f_over_10, 0.5)
        ) + pynutil.insert(" שקלים")
        shekel_over_10_alt = (
            pynutil.add_weight(num_m_over_10, -0.05)
            | pynutil.add_weight(num_f_over_10, 0.5)
        ) + pynutil.insert(" שקל")
        shekel_major = (
            shekel_1
            | shekel_2
            | shekel_3_10
            | pynutil.add_weight(shekel_over_10, 0.95)
            | pynutil.add_weight(shekel_over_10_alt, 1.0)
        ).optimize()

        # Agorot (minor unit - feminine)
        agora_1 = pynini.cross("01", "אגורה אחת") | pynini.cross("1", "אגורה אחת")
        agora_2 = pynini.cross("02", "שתי אגורות") | pynini.cross("2", "שתי אגורות")
        agora_3_10 = pynini.string_map([
            ("03", "שלוש אגורות"),
            ("04", "ארבע אגורות"),
            ("05", "חמש אגורות"),
            ("06", "שש אגורות"),
            ("07", "שבע אגורות"),
            ("08", "שמונה אגורות"),
            ("09", "תשע אגורות"),
            ("3", "שלוש אגורות"),
            ("4", "ארבע אגורות"),
            ("5", "חמש אגורות"),
            ("6", "שש אגורות"),
            ("7", "שבע אגורות"),
            ("8", "שמונה אגורות"),
            ("9", "תשע אגורות"),
            ("10", "עשר אגורות"),
        ])
        agora_over_10 = (
            (pynini.difference(pynini.project(cardinal.two_digits_f, "input"), "10").optimize() @ cardinal.two_digits_f)
        ) + pynutil.insert(" אגורות")
        agora_over_10_m = (
            (pynini.difference(pynini.project(cardinal.two_digits_m, "input"), "10").optimize() @ cardinal.two_digits_m)
        ) + pynutil.insert(" אגורות")

        agora_minor = (
            agora_1
            | agora_2
            | agora_3_10
            | pynutil.add_weight(agora_over_10, 0.95)
            | pynutil.add_weight(agora_over_10_m, 1.0)
        ).optimize()

        # ----------------- Dollar Number Forms -----------------
        dolar_1 = pynini.cross("1", "דולר אחד")
        dolar_2 = pynini.cross("2", "שני דולרים")
        dolar_3_10 = pynini.string_map([
            ("3", "שלושה דולרים"),
            ("4", "ארבעה דולרים"),
            ("5", "חמישה דולרים"),
            ("6", "שישה דולרים"),
            ("7", "שבעה דולרים"),
            ("8", "שמונה דולרים"),
            ("9", "תשעה דולרים"),
            ("10", "עשרה דולרים"),
        ])
        dolar_over_10 = (
            pynutil.add_weight(num_m_over_10, -0.05)
            | pynutil.add_weight(num_f_over_10, 0.5)
        ) + pynutil.insert(" דולר")
        dolar_over_10_alt = (
            pynutil.add_weight(num_m_over_10, -0.05)
            | pynutil.add_weight(num_f_over_10, 0.5)
        ) + pynutil.insert(" דולרים")
        dolar_major = (
            dolar_1
            | dolar_2
            | dolar_3_10
            | pynutil.add_weight(dolar_over_10, 0.95)
            | pynutil.add_weight(dolar_over_10_alt, 1.0)
        ).optimize()

        # Cent (minor unit - masculine)
        cent_1 = pynini.cross("01", "סנט אחד") | pynini.cross("1", "סנט אחד")
        cent_2 = pynini.cross("02", "שני סנטים") | pynini.cross("2", "שני סנטים")
        cent_3_10 = pynini.string_map([
            ("03", "שלושה סנטים"),
            ("04", "ארבעה סנטים"),
            ("05", "חמישה סנטים"),
            ("06", "שישה סנטים"),
            ("07", "שבעה סנטים"),
            ("08", "שמונה סנטים"),
            ("09", "תשעה סנטים"),
            ("3", "שלושה סנטים"),
            ("4", "ארבעה סנטים"),
            ("5", "חמישה סנטים"),
            ("6", "שישה סנטים"),
            ("7", "שבעה סנטים"),
            ("8", "שמונה סנטים"),
            ("9", "תשעה סנטים"),
            ("10", "עשרה סנטים"),
        ])
        cent_over_10 = (
            (pynini.difference(pynini.project(cardinal.two_digits_m, "input"), "10").optimize() @ cardinal.two_digits_m)
        ) + pynutil.insert(" סנט")
        cent_over_10_f = (
            (pynini.difference(pynini.project(cardinal.two_digits_f, "input"), "10").optimize() @ cardinal.two_digits_f)
        ) + pynutil.insert(" סנט")

        cent_minor = (
            cent_1
            | cent_2
            | cent_3_10
            | pynutil.add_weight(cent_over_10, 0.95)
            | pynutil.add_weight(cent_over_10_f, 1.0)
        ).optimize()

        # ----------------- Euro Number Forms -----------------
        euro_1 = pynini.cross("1", "אירו אחד")
        euro_2 = pynini.cross("2", "שני אירו")
        euro_3_10 = pynini.string_map([
            ("3", "שלושה אירו"),
            ("4", "ארבעה אירו"),
            ("5", "חמישה אירו"),
            ("6", "שישה אירו"),
            ("7", "שבעה אירו"),
            ("8", "שמונה אירו"),
            ("9", "תשעה אירו"),
            ("10", "עשרה אירו"),
        ])
        euro_over_10 = (
            pynutil.add_weight(num_m_over_10, -0.05)
            | pynutil.add_weight(num_f_over_10, 0.5)
        ) + pynutil.insert(" אירו")
        euro_major = (
            euro_1
            | euro_2
            | euro_3_10
            | pynutil.add_weight(euro_over_10, 0.95)
        ).optimize()

        # Major + Minor combinations
        # Shekel: ₪12.50 -> שנים עשר שקלים וחמישים אגורות
        # Zero cents: ₪10.00 -> עשרה שקלים
        # Cents only: ₪0.50 -> חמישים אגורות
        dot = pynutil.delete(".")
        zero_cents = dot + pynutil.delete("00")

        shekel_sym_lead = pynutil.delete(pynini.union("₪", "ILS")) + opt_space
        shekel_sym_trail = opt_space + pynutil.delete(pynini.union("₪", "ILS", 'ש"ח', 'ש״ח', "שקלים", "שקל"))

        shekel_maj_min = (
            shekel_major
            + dot
            + pynutil.insert(" ו")
            + agora_minor
        )
        shekel_maj_zero = shekel_major + zero_cents
        shekel_cents_only = pynutil.delete("0") + dot + agora_minor

        shekel_full_amount = (
            shekel_maj_zero
            | shekel_maj_min
            | shekel_cents_only
            | shekel_major
        ).optimize()

        shekel_graph = (
            (shekel_sym_lead + shekel_full_amount)
            | (shekel_full_amount + shekel_sym_trail)
        ).optimize()

        # Dollar
        dolar_sym_lead = pynutil.delete(pynini.union("$", "USD")) + opt_space
        dolar_sym_trail = opt_space + pynutil.delete(pynini.union("$", "USD", "דולר", "דולרים"))

        dolar_maj_min = (
            dolar_major
            + dot
            + pynutil.insert(" ו")
            + cent_minor
        )
        dolar_maj_zero = dolar_major + zero_cents
        dolar_cents_only = pynutil.delete("0") + dot + cent_minor

        dolar_full_amount = (
            dolar_maj_zero
            | dolar_maj_min
            | dolar_cents_only
            | dolar_major
        ).optimize()

        dolar_graph = (
            (dolar_sym_lead + dolar_full_amount)
            | (dolar_full_amount + dolar_sym_trail)
        ).optimize()

        # Euro
        euro_sym_lead = pynutil.delete(pynini.union("€", "EUR")) + opt_space
        euro_sym_trail = opt_space + pynutil.delete(pynini.union("€", "EUR", "אירו", "יורו"))

        euro_maj_min = (
            euro_major
            + dot
            + pynutil.insert(" ו")
            + cent_minor
        )
        euro_maj_zero = euro_major + zero_cents
        euro_cents_only = pynutil.delete("0") + dot + cent_minor

        euro_full_amount = (
            euro_maj_zero
            | euro_maj_min
            | euro_cents_only
            | euro_major
        ).optimize()

        euro_graph = (
            (euro_sym_lead + euro_full_amount)
            | (euro_full_amount + euro_sym_trail)
        ).optimize()

        # British Pound (£, GBP)
        pound_sym_lead = pynutil.delete(pynini.union("£", "GBP")) + opt_space
        pound_sym_trail = opt_space + pynutil.delete(pynini.union("£", "GBP", "פאונד", "לירה שטרלינג"))
        pound_major = (
            ((pynini.difference(pynini.project(cardinal.base_num_m, "input"), pynini.union("1", "2").optimize()).optimize() @ cardinal.base_num_m)) | cardinal.base_num_f
        ) + pynutil.insert(" פאונד")
        pound_full = (
            pynini.cross("1", "פאונד אחד")
            | pynini.cross("2", "שני פאונד")
            | pound_major
        )
        pound_graph = (
            (pound_sym_lead + (pound_full + zero_cents | pound_full))
            | ((pound_full + zero_cents | pound_full) + pound_sym_trail)
        ).optimize()

        # Japanese Yen (¥, JPY)
        yen_sym_lead = pynutil.delete(pynini.union("¥", "JPY")) + opt_space
        yen_sym_trail = opt_space + pynutil.delete(pynini.union("¥", "JPY", "ין"))
        yen_full = cardinal.base_num_f + pynutil.insert(" ין")
        yen_graph = ((yen_sym_lead + yen_full) | (yen_full + yen_sym_trail)).optimize()

        # Other World Currencies
        curr_map = [
            ("CHF", " פרנק שוויצרי"),
            ("CAD", " דולר קנדי"),
            ("AUD", " דולר אוסטרלי"),
            ("INR", " רופי הודי"),
            ("₹", " רופי"),
            ("Rs.", " רופי"),
            ("Rs", " רופי"),
            ("RUB", " רובל"),
            ("₽", " רובל"),
            ("KRW", " וון"),
            ("₩", " וון"),
            ("TRY", " לירה טורקית"),
            ("₺", " לירה טורקית"),
            ("UAH", " הריבניה"),
            ("₴", " הריבניה"),
            ("VND", " דונג"),
            ("₫", " דונג"),
            ("BDT", " טאקה"),
            ("৳", " טאקה"),
            ("NGN", " נאירה"),
            ("₦", " נאירה"),
            ("PHP", " פזו"),
            ("₱", " פזו"),
            ("THB", " באט"),
            ("฿", " באט"),
            ("AMD", " דראם"),
            ("֏", " דראם"),
            ("BRL", " ריאל ברזילאי"),
            ("MXN", " פזו מקסיקני"),
        ]
        world_sym_lead = pynini.string_map([
            ("₹", " רופי"),
            ("₽", " רובל"),
            ("₩", " וון"),
            ("₺", " לירה טורקית"),
            ("₴", " הריבניה"),
            ("₫", " דונג"),
            ("৳", " טאקה"),
            ("₦", " נאירה"),
            ("₱", " פזו"),
            ("฿", " באט"),
            ("֏", " דראם"),
            ("Rs. ", " רופי"),
            ("Rs.", " רופי"),
        ])
        world_sym_lead_graph = pynutil.delete(pynini.union(
            "₹", "₽", "₩", "₺", "₴", "₫", "৳", "₦", "₱", "฿", "֏", "Rs.", "Rs. "
        )) + opt_space

        # Prefixed currencies: CA$, A$, R$, MX$, US$
        pref_usd = pynini.cross(pynini.union("US$", "USD", "$"), "") + opt_space + dolar_full_amount
        pref_cad = pynini.cross("CA$", "") + opt_space + cardinal.base_num_f + pynutil.insert(" דולר קנדי")
        pref_aud = pynini.cross("A$", "") + opt_space + cardinal.base_num_f + pynutil.insert(" דולר אוסטרלי")
        pref_brl = pynini.cross("R$", "") + opt_space + cardinal.base_num_f + pynutil.insert(" ריאל ברזילאי")
        pref_mxn = pynini.cross("MX$", "") + opt_space + cardinal.base_num_f + pynutil.insert(" פזו מקסיקני")
        pref_currencies = pref_usd | pref_cad | pref_aud | pref_brl | pref_mxn

        # ISO currency trailing: 100 CHF -> מאה פרנק שוויצרי
        iso_trailing = pynini.string_map(curr_map)
        world_iso_graph = pynutil.add_weight(cardinal.base_num_f + opt_space + iso_trailing, -0.1)

        # World currency leading: ₹500 -> חמש מאות רופי, 500 ₽ -> חמש מאות רובל
        world_sym_trailing = cardinal.base_num_f + opt_space + world_sym_lead
        world_sym_lead_pairs = [
            (pynutil.delete("₹") + opt_space, pynutil.insert(" רופי")),
            (pynutil.delete("₽") + opt_space, pynutil.insert(" רובל")),
            (pynutil.delete("₩") + opt_space, pynutil.insert(" וון")),
            (pynutil.delete("₺") + opt_space, pynutil.insert(" לירה טורקית")),
            (pynutil.delete("₴") + opt_space, pynutil.insert(" הריבניה")),
            (pynutil.delete("₫") + opt_space, pynutil.insert(" דונג")),
            (pynutil.delete("৳") + opt_space, pynutil.insert(" טאקה")),
            (pynutil.delete("₦") + opt_space, pynutil.insert(" נאירה")),
            (pynutil.delete("₱") + opt_space, pynutil.insert(" פזו")),
            (pynutil.delete("฿") + opt_space, pynutil.insert(" באט")),
            (pynutil.delete("֏") + opt_space, pynutil.insert(" דראם")),
            (pynutil.delete("Rs. ") + opt_space, pynutil.insert(" רופי")),
            (pynutil.delete("Rs.") + opt_space, pynutil.insert(" רופי")),
        ]
        world_sym_lead_expr = pynini.union(*[
            (del_sym + cardinal.base_num_f + ins_name)
            for del_sym, ins_name in world_sym_lead_pairs
        ])

        all_base_money = (
            shekel_graph
            | dolar_graph
            | euro_graph
            | pound_graph
            | yen_graph
            | pref_currencies
            | world_iso_graph
            | world_sym_trailing
            | world_sym_lead_expr
        ).optimize()

        # Shorthand money: $50k, €50k, $2.5M
        shorthand_dolar_k = (
            pynutil.delete("$") + opt_space + cardinal.base_num_f + pynutil.delete(pynini.union("k", "K")) + pynutil.insert(" אלף דולר")
        )
        shorthand_euro_k = (
            pynutil.delete("€") + opt_space + cardinal.base_num_f + pynutil.delete(pynini.union("k", "K")) + pynutil.insert(" אלף אירו")
        )
        shorthand_shekel_k = (
            pynutil.delete("₪") + opt_space + cardinal.base_num_f + pynutil.delete(pynini.union("k", "K")) + pynutil.insert(" אלף שקלים")
        )
        shorthand_dolar_m = (
            pynutil.delete("$") + opt_space + decimal.decimal_num + pynutil.delete(pynini.union("M", "m")) + pynutil.insert(" מיליון דולר")
        )
        shorthand_euro_m = (
            pynutil.delete("€") + opt_space + decimal.decimal_num + pynutil.delete(pynini.union("M", "m")) + pynutil.insert(" מיליון אירו")
        )
        shorthand_money = (
            shorthand_dolar_k
            | shorthand_euro_k
            | shorthand_shekel_k
            | shorthand_dolar_m
            | shorthand_euro_m
        ).optimize()

        # Negative money: -$12.50, −$12.50
        neg = pynini.cross("-", "מינוס ") | pynini.cross("−", "מינוס ")
        neg_money = neg + (all_base_money | shorthand_money)

        # Per-unit money: $15/h, €20/kg
        per_unit = pynini.string_map([
            ("/h", " לשעה"),
            ("/hr", " לשעה"),
            ("/kg", " לקילוגרם"),
            ("/m", " למטר"),
            ("/km", " לקילומטר"),
            ("/day", " ליום"),
            ("/month", " לחודש"),
            ("/year", " לשנה"),
        ])
        money_per_unit = (all_base_money | shorthand_money) + per_unit

        # Currency ranges: $10-$20, $10-€20, 10-20 ₪
        dash = pynini.union("-", "–", "—", "־")
        range_diff_curr = (
            all_base_money
            + opt_space
            + pynini.cross(dash, " עד ")
            + opt_space
            + all_base_money
        )
        # Same currency range with symbol on both or on outer:
        range_same_dolar = (
            pynutil.delete("$")
            + cardinal.base_num_m
            + opt_space
            + pynini.cross(dash, " עד ")
            + opt_space
            + pynutil.delete(pynini.closure(pynini.accep("$"), 0, 1))
            + cardinal.base_num_m
            + pynutil.insert(" דולר")
        )
        range_same_euro = (
            pynutil.delete("€")
            + cardinal.base_num_m
            + opt_space
            + pynini.cross(dash, " עד ")
            + opt_space
            + pynutil.delete(pynini.closure(pynini.accep("€"), 0, 1))
            + cardinal.base_num_m
            + pynutil.insert(" אירו")
        )
        range_same_shekel = (
            (
                (pynutil.delete("₪") + cardinal.base_num_m + opt_space + pynini.cross(dash, " עד ") + opt_space + pynutil.delete(pynini.closure(pynini.accep("₪"), 0, 1)) + cardinal.base_num_m)
                | (cardinal.base_num_m + opt_space + pynini.cross(dash, " עד ") + opt_space + pynutil.delete("₪") + cardinal.base_num_m)
            )
            + pynutil.insert(" שקלים")
        )

        currency_ranges = (
            range_diff_curr
            | range_same_dolar
            | range_same_euro
            | range_same_shekel
        ).optimize()

        total_money = (
            pynutil.add_weight(neg_money, 0.9)
            | pynutil.add_weight(money_per_unit, 0.92)
            | pynutil.add_weight(currency_ranges, 0.94)
            | pynutil.add_weight(shorthand_money, 0.95)
            | pynutil.add_weight(all_base_money, 1.0)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(total_money) + pynutil.insert('"')
        ).optimize()
