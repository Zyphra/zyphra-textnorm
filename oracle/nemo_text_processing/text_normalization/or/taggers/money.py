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

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGITS,
    convert_space,
)
from .cardinal import CardinalFst, ODIA_CARDINALS_0_TO_99
from .decimal import DecimalFst

CURRENCY_MAJOR_MINOR = [
    # Indian Rupee
    ("₹", "ଟଙ୍କା", "ପଇସା"),
    ("Rs.", "ଟଙ୍କା", "ପଇସା"),
    ("Rs", "ଟଙ୍କା", "ପଇସା"),
    ("INR", "ଭାରତୀୟ ଟଙ୍କା", "ପଇସା"),
    # USD
    ("$", "ଡଲାର୍", "ସେଣ୍ଟ"),
    ("USD", "ଡଲାର୍", "ସେଣ୍ଟ"),
    # EUR
    ("€", "ୟୁରୋ", "ସେଣ୍ଟ"),
    ("EUR", "ୟୁରୋ", "ସେଣ୍ଟ"),
    # GBP
    ("£", "ପାଉଣ୍ଡ୍", "ପେନ୍ସ"),
    ("GBP", "ପାଉଣ୍ଡ୍", "ପେନ୍ସ"),
    # JPY
    ("¥", "ୟେନ୍", "ସେନ୍"),
    ("JPY", "ୟେନ୍", "ସେନ୍"),
    # BDT
    ("৳", "ଟାକା", "ପଇସା"),
    ("Tk", "ଟାକା", "ପଇସା"),
    ("BDT", "ଟାକା", "ପଇସା"),
    # CAD
    ("CA$", "କାନେଡିୟ ଡଲାର୍", "ସେଣ୍ଟ"),
    ("CAD", "କାନେଡିୟ ଡଲାର୍", "ସେଣ୍ଟ"),
    # AUD
    ("A$", "ଅଷ୍ଟ୍ରେଲିୟ ଡଲାର୍", "ସେଣ୍ଟ"),
    ("AUD", "ଅଷ୍ଟ୍ରେଲିୟ ଡଲାର୍", "ସେଣ୍ଟ"),
    # CHF
    ("CHF", "ସୁଇସ୍ ଫ୍ରାଙ୍କ୍", "ରାପେନ୍"),
    # BRL
    ("R$", "ବ୍ରାଜିଲିୟ ରିଆଲ୍", "ସେଣ୍ଟାଭୋ"),
    ("BRL", "ବ୍ରାଜିଲିୟ ରିଆଲ୍", "ସେଣ୍ଟାଭୋ"),
    # MXN
    ("MX$", "ମେକ୍ସିକାନ୍ ପେସୋ", "ସେଣ୍ଟାଭୋ"),
    ("MXN", "ମେକ୍ସିକାନ୍ ପେସୋ", "ସେଣ୍ଟାଭୋ"),
    # RUB
    ("₽", "ରୁବଲ୍", "କୋପେକ୍"),
    ("RUB", "ରୁବଲ୍", "କୋପେକ୍"),
    # KRW
    ("₩", "ୱୋନ୍", "ଜିଅନ୍"),
    ("KRW", "ୱୋନ୍", "ଜିଅନ୍"),
    # TRY
    ("₺", "ଲିରା", "କୁରୁସ୍"),
    ("TRY", "ଲିରା", "କୁରୁସ୍"),
    # ILS
    ("₪", "ଶେକେଲ୍", "ଅଗୋରା"),
    ("ILS", "ଶେକେଲ୍", "ଅଗୋରା"),
    # UAH
    ("₴", "ହ୍ରିଭନିଆ", "କୋପେକ୍"),
    ("UAH", "ହ୍ରିଭନିଆ", "କୋପେକ୍"),
    # VND
    ("₫", "ଡଙ୍ଗ୍", "ହାଓ"),
    ("VND", "ଡଙ୍ଗ୍", "ହାଓ"),
    # NGN
    ("₦", "ନାଇରା", "କୋବୋ"),
    ("NGN", "ନାଇରା", "କୋବୋ"),
    # PHP
    ("₱", "ପେସୋ", "ସେଣ୍ଟିମୋ"),
    ("PHP", "ପେସୋ", "ସେଣ୍ଟିମୋ"),
    # THB
    ("฿", "ବାଟ୍", "ସତଙ୍ଗ୍"),
    ("THB", "ବାଟ୍", "ସତଙ୍ଗ୍"),
    # AMD
    ("֏", "ଡ୍ରାମ୍", "ଲୁମା"),
    ("AMD", "ଡ୍ରାମ୍", "ଲୁମା"),
]


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money in Odia:
        ₹୫୦୦ -> tokens { name: "ପାଞ୍ଚ ଶହ ଟଙ୍କା" }
        ₹୫୦.୫୦ -> tokens { name: "ପଚାଶ ଟଙ୍କା ପଚାଶ ପଇସା" }
        $୨୦ -> tokens { name: "କୋଡ଼ିଏ ଡଲାର୍" }
        €୧୫ -> tokens { name: "ପନ୍ଦର ୟୁରୋ" }
        ୨୫¢ -> tokens { name: "ପଚିଶ ସେଣ୍ଟ" }
        $୧୦-$୨୦ -> tokens { name: "ଦଶ ଡଲାର୍ ରୁ କୋଡ଼ିଏ ଡଲାର୍" }
        $୧୫/h -> tokens { name: "ପନ୍ଦର ଡଲାର୍ ପ୍ରତି ଘଣ୍ଟା" }
    """

    def __init__(self, cardinal: CardinalFst = None, decimal: DecimalFst = None, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)

        self.cardinal = cardinal
        self.decimal = decimal

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # 2-digit minor map (00 to 99)
        minor_lookup = {}
        for i in range(100):
            s = f"{i:02d}"
            minor_lookup[s] = ODIA_CARDINALS_0_TO_99[i]
        minor_2d = pynini.string_map(list(minor_lookup.items()))
        minor_graph = (NORMALIZE_DIGITS @ minor_2d).optimize()

        # Minor cents symbol alone (e.g. 25¢ -> ପଚିଶ ସେଣ୍ଟ)
        cents_sym = pynini.union("¢", "c", "ct")
        cents_graph = (
            (NORMALIZE_DIGITS @ cardinal.cardinal_numbers)
            + opt_sp
            + pynutil.delete(cents_sym)
            + pynutil.insert(" ସେଣ୍ଟ")
        ).optimize()

        # Multiplier suffixes (k, M, B)
        # e.g. $50k -> ପଚାଶ ହଜାର ଡଲାର୍, €50k -> ପଚାଶ ହଜାର ୟୁରୋ, $2.5M -> ଦୁଇ ଦଶମିକ ପାଞ୍ଚ ମିଲିଅନ୍ ଡଲାର୍
        mult_map = pynini.string_map([
            ("k", " ହଜାର"),
            ("K", " ହଜାର"),
            ("M", " ମିଲିଅନ୍"),
            ("B", " ବିଲିଅନ୍"),
            ("କୋଟି", " କୋଟି"),
            ("ଲକ୍ଷ", " ଲକ୍ଷ"),
            ("ହଜାର", " ହଜାର"),
        ])

        # Per unit suffixes ($15/h, €20/kg)
        per_unit_map = pynini.string_map([
            ("/h", " ପ୍ରତି ଘଣ୍ଟା"),
            ("/hr", " ପ୍ରତି ଘଣ୍ଟା"),
            ("/kg", " ପ୍ରତି କିଲୋଗ୍ରାମ୍"),
            ("/m", " ପ୍ରତି ମିଟର"),
            ("/day", " ପ୍ରତି ଦିନ"),
            ("/yr", " ପ୍ରତି ବର୍ଷ"),
        ])

        money_graphs = []

        for sym, maj_name, min_name in CURRENCY_MAJOR_MINOR:
            del_sym = pynutil.delete(sym)
            ins_maj = pynutil.insert(" " + maj_name)
            ins_min = pynutil.insert(" " + min_name)

            card_val = cardinal.cardinal_numbers

            # 1. Whole currency amount: $50, 50$, 50 USD, USD 50
            # Prefixed
            pre_whole = del_sym + opt_sp + card_val + ins_maj
            # Suffixed
            suf_whole = card_val + opt_sp + del_sym + ins_maj

            # 2. Major and Minor: $50.50, €99.95
            dot = pynini.union(".", ",")
            pre_maj_min = (
                del_sym
                + opt_sp
                + card_val
                + ins_maj
                + pynutil.delete(dot)
                + pynutil.insert(" ")
                + minor_graph
                + ins_min
            )
            suf_maj_min = (
                card_val
                + ins_maj
                + pynutil.delete(dot)
                + pynutil.insert(" ")
                + minor_graph
                + ins_min
                + opt_sp
                + del_sym
            )

            # 3. Minor only: $0.50, ₹0.50 -> ପଚାଶ ପଇସା
            pre_zero = del_sym + opt_sp + pynutil.delete(pynini.union("0", "୦")) + pynutil.delete(dot) + minor_graph + ins_min
            suf_zero = pynutil.delete(pynini.union("0", "୦")) + pynutil.delete(dot) + minor_graph + ins_min + opt_sp + del_sym

            # 4. Glued shorthand multiplier: $50k, $2.5M
            dec_or_card = (decimal.decimal_numbers | card_val)
            pre_mult = del_sym + opt_sp + dec_or_card + opt_sp + mult_map + ins_maj
            suf_mult = dec_or_card + opt_sp + mult_map + opt_sp + del_sym + ins_maj

            curr_unit_graph = (
                pre_maj_min
                | suf_maj_min
                | pre_zero
                | suf_zero
                | pre_mult
                | suf_mult
                | pre_whole
                | suf_whole
            ).optimize()

            # Optional per-unit: $15/h, €20/kg
            with_per_unit = (curr_unit_graph + pynini.closure(per_unit_map, 0, 1)).optimize()

            money_graphs.append(with_per_unit)

        all_single_money = pynini.union(*money_graphs, cents_graph).optimize()

        # Negative money: -$12.50, -₹50
        neg_prefix = pynini.cross("-", "ଋଣ ") | pynini.cross("−", "ଋଣ ")
        all_money_with_neg = (all_single_money | (neg_prefix + all_single_money)).optimize()

        # Money ranges: $10-$20, 10-20 €, ₹100-₹200
        dash = pynini.union("-", "–", "—", " to ")
        range_sep = opt_sp + pynutil.delete(dash) + pynutil.insert(" ରୁ ") + opt_sp
        money_range = (all_money_with_neg + range_sep + all_money_with_neg).optimize()

        final_money = (all_money_with_neg | money_range).optimize()
        self.money_graph = final_money

        graph = pynutil.insert('name: "') + convert_space(final_money) + pynutil.insert('"')
        self.fst = graph.optimize()
