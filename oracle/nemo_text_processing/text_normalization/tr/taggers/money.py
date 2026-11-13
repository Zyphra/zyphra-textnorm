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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.tr.taggers.decimal import DecimalFst


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying currency amounts in Turkish:
    - Turkish Lira: ₺50, 50 TL -> elli lira; ₺10,50 -> on lira elli kuruş; ₺0,50 -> elli kuruş
    - USD: $50 -> elli dolar; $10.50 -> on dolar elli sent; $0.99 -> doksan dokuz sent
    - EUR: €99,95 -> doksan dokuz euro doksan beş sent; 250 EUR -> iki yüz elli euro
    - GBP: £50 -> elli sterlin; £1,20 -> bir sterlin yirmi peni
    - Ranges: ₺10-₺20 -> on lira ila yirmi lira, $10-$20 -> on dolar ila yirmi dolar
    - Shorthands: ₺50k -> elli bin lira, €2,5M -> iki virgül beş milyon euro
    - Rates: ₺15/saat -> on beş lira bölü saat, $15/h -> on beş dolar bölü saat
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        decimal: DecimalFst = None,
        deterministic: bool = True,
    ):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)

        integer_part = cardinal.positive_cardinals

        # Currency maps: (symbol, major_name, minor_name)
        # Leading currency symbols
        currencies_prefix = [
            ("₺", "lira", "kuruş"),
            ("TL", "lira", "kuruş"),
            ("$", "dolar", "sent"),
            ("US$", "amerikan doları", "sent"),
            ("CA$", "kanada doları", "sent"),
            ("AU$", "avustralya doları", "sent"),
            ("€", "euro", "sent"),
            ("£", "sterlin", "peni"),
            ("¥", "yen", "sen"),
            ("₽", "ruble", "kopek"),
            ("₹", "rupi", "paisa"),
            ("₩", "won", "jeon"),
            ("CHF", "isviçre frangı", "santim"),
        ]

        # Trailing currency symbols
        currencies_suffix = [
            ("TL", "lira", "kuruş"),
            ("TL.", "lira", "kuruş"),
            ("TRY", "türk lirası", "kuruş"),
            ("₺", "lira", "kuruş"),
            ("USD", "amerikan doları", "sent"),
            ("EUR", "euro", "sent"),
            ("GBP", "ingiliz sterlini", "peni"),
            ("JPY", "japon yeni", "sen"),
            ("RUB", "rus rublesi", "kopek"),
            ("CHF", "isviçre frangı", "santim"),
            ("€", "euro", "sent"),
            ("$", "dolar", "sent"),
            ("£", "sterlin", "peni"),
            ("¥", "yen", "sen"),
            ("₽", "ruble", "kopek"),
        ]
        extra_currencies = [
            ('CHF', 'isviçre frangı', 'santim'),
            ('CAD', 'kanada doları', 'sent'),
            ('CA$', 'kanada doları', 'sent'),
            ('AUD', 'avustralya doları', 'sent'),
            ('A$', 'avustralya doları', 'sent'),
            ('BRL', 'brezilya reali', 'sentavo'),
            ('R$', 'brezilya reali', 'sentavo'),
            ('MXN', 'meksika pesosu', 'sentavo'),
            ('MX$', 'meksika pesosu', 'sentavo'),
            ('RUB', 'rus rublesi', 'kopek'),
            ('₽', 'rus rublesi', 'kopek'),
            ('KRW', 'güney kore wonu', 'jeon'),
            ('₩', 'güney kore wonu', 'jeon'),
            ('TRY', 'türk lirası', 'kuruş'),
            ('₺', 'türk lirası', 'kuruş'),
            ('ILS', 'yeni israil şekeli', 'agora'),
            ('₪', 'yeni israil şekeli', 'agora'),
            ('UAH', 'ukrayna grivnası', 'kopiyka'),
            ('₴', 'ukrayna grivnası', 'kopiyka'),
            ('VND', 'vietnam dongu', 'hao'),
            ('₫', 'vietnam dongu', 'hao'),
            ('BDT', 'bangladeş takası', 'poişa'),
            ('৳', 'bangladeş takası', 'poişa'),
            ('NGN', 'nijerya nairası', 'kobo'),
            ('₦', 'nijerya nairası', 'kobo'),
            ('PHP', 'filipinler pesosu', 'sentimo'),
            ('₱', 'filipinler pesosu', 'sentimo'),
            ('THB', 'tayland bahtı', 'satang'),
            ('฿', 'tayland bahtı', 'satang'),
            ('AMD', 'ermenistan dramı', 'luma'),
            ('֏', 'ermenistan dramı', 'luma'),
            ('USD', 'amerikan doları', 'sent'),
            ('EUR', 'euro', 'sent'),
            ('GBP', 'ingiliz sterlini', 'peni'),
            ('JPY', 'japon yeni', 'sen'),
            ('INR', 'Hint rupisi', 'paisa'),
            ('Rs.', 'Hint rupisi', 'paisa'),
            ('Rs', 'Hint rupisi', 'paisa'),
            ('¢', 'sent', 'sent'),
        ]
        for currencies in (currencies_prefix, currencies_suffix):
            known_symbols = {symbol for symbol, _, _ in currencies}
            currencies.extend(row for row in extra_currencies if row[0] not in known_symbols)

        # Minor digits 2-digit mapping
        d1_to_9 = pynini.string_map([
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        tens_map = pynini.string_map([
            ("1", "on"),
            ("2", "yirmi"),
            ("3", "otuz"),
            ("4", "kırk"),
            ("5", "elli"),
            ("6", "altmış"),
            ("7", "yetmiş"),
            ("8", "seksen"),
            ("9", "doksan"),
        ])
        two_digits = (tens_map + pynutil.delete("0")) | (tens_map + pynutil.insert(" ") + d1_to_9)

        # 2-digit minor: "50" -> elli, "05" -> beş, "21" -> yirmi bir, "20" -> yirmi, "01" -> bir
        minor_2digit = (
            (pynutil.delete("0") + d1_to_9)
            | two_digits
        )

        dec_sep = pynini.union(",", ".")
        opt_neg = pynini.closure(pynini.cross(pynini.union("-", "−"), "eksi "), 0, 1)
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        zero_major = pynini.union("0", "00")
        nonzero_major = pynini.difference(
            pynini.project(integer_part, "input"), zero_major.optimize()
        ).optimize() @ integer_part

        # Build graphs per currency
        major_only_graphs = []
        full_graphs = []
        minor_only_graphs = []

        # Prefix currencies
        for sym, maj, min_u in currencies_prefix:
            sym_lead = pynutil.delete(sym) + opt_sp
            # 1. Major only (e.g. $50, ₺100, ₺1.000)
            g_maj = opt_neg + sym_lead + integer_part + pynutil.insert(" " + maj)
            major_only_graphs.append(g_maj)

            # 2. Major with zero minor: $10.00 -> on dolar
            g_zero_min = (
                opt_neg
                + sym_lead
                + integer_part
                + pynutil.insert(" " + maj)
                + pynutil.delete(dec_sep + "00")
            )
            major_only_graphs.append(g_zero_min)

            # 3. Major + non-zero minor: $10.50 -> on dolar elli sent, ₺1,25 -> bir lira yirmi beş kuruş
            g_full = (
                opt_neg
                + sym_lead
                + nonzero_major
                + pynutil.insert(" " + maj + " ")
                + pynutil.delete(dec_sep)
                + minor_2digit
                + pynutil.insert(" " + min_u)
            )
            full_graphs.append(g_full)

            # 4. Minor only: $0.99 -> doksan dokuz sent, ₺0,50 -> elli kuruş
            g_min = (
                opt_neg
                + sym_lead
                + pynutil.delete(zero_major + dec_sep)
                + minor_2digit
                + pynutil.insert(" " + min_u)
            )
            minor_only_graphs.append(g_min)

        # Suffix currencies
        for sym, maj, min_u in currencies_suffix:
            sym_trail = opt_sp + pynutil.delete(sym)
            # 1. Major only (e.g. 50 TL, 250 EUR)
            g_maj = opt_neg + integer_part + sym_trail + pynutil.insert(" " + maj)
            major_only_graphs.append(g_maj)

            # 2. Major with zero minor: 10,00 TL -> on lira
            g_zero_min = (
                opt_neg
                + integer_part
                + pynutil.delete(dec_sep + "00")
                + sym_trail
                + pynutil.insert(" " + maj)
            )
            major_only_graphs.append(g_zero_min)

            # 3. Major + minor: 10,50 TL -> on lira elli kuruş, 99,95 € -> doksan dokuz euro doksan beş sent
            g_full = (
                opt_neg
                + nonzero_major
                + pynutil.insert(" " + maj + " ")
                + pynutil.delete(dec_sep)
                + minor_2digit
                + sym_trail
                + pynutil.insert(" " + min_u)
            )
            full_graphs.append(g_full)

            # 4. Minor only: 0,50 TL -> elli kuruş
            g_min = (
                opt_neg
                + pynutil.delete(zero_major + dec_sep)
                + minor_2digit
                + sym_trail
                + pynutil.insert(" " + min_u)
            )
            minor_only_graphs.append(g_min)

        positive_money = pynini.union(*(full_graphs + major_only_graphs + minor_only_graphs)).optimize()
        self.positive_money = positive_money

        # Shorthand magnitudes: $50k, ₺50 bin, €2,5M, US $76,3 biljoner
        # k -> bin, M -> milyon, B -> milyar
        mag_k = pynini.cross(pynini.union("k", "K", " bin"), " bin")
        mag_m = pynini.cross(pynini.union("M", "m", " milyon"), " milyon")
        mag_b = pynini.cross(pynini.union("B", "b", " milyar"), " milyar")
        mags = mag_k | mag_m | mag_b

        shorthand_graphs = []
        for sym, maj, _ in currencies_prefix:
            sym_lead = pynutil.delete(sym) + opt_sp
            # e.g. $50k -> elli bin dolar
            sh_card = (
                sym_lead
                + integer_part
                + opt_sp
                + mags
                + pynutil.insert(" " + maj)
            )
            # e.g. €2,5M -> iki virgül beş milyon euro
            sh_dec = (
                sym_lead
                + decimal.all_decimals
                + opt_sp
                + mags
                + pynutil.insert(" " + maj)
            )
            shorthand_graphs.extend([sh_card, sh_dec])

        # US $76,3 biljoner / USD$76,3 milyar
        us_prefix = pynini.string_map([
            ("US $", "US "),
            ("US$", "US "),
            ("USD$", ""),
            ("USD $", ""),
        ])
        us_shorthand = (
            us_prefix
            + decimal.all_decimals
            + pynutil.insert(" dolar")
        )
        shorthand_graphs.append(us_shorthand)

        all_shorthands = pynini.union(*shorthand_graphs).optimize()

        # Rates: $15/h -> on beş dolar bölü saat, ₺15/saat -> on beş lira bölü saat, €20/kg -> yirmi euro bölü kilogram
        rate_units = pynini.string_map([
            ("h", "saat"),
            ("saat", "saat"),
            ("kg", "kilogram"),
            ("kilo", "kilogram"),
            ("gün", "gün"),
            ("hafta", "hafta"),
            ("ay", "ay"),
            ("yıl", "yıl"),
            ("adet", "adet"),
            ("tane", "tane"),
            ("kişi", "kişi"),
        ])
        rate_graph = (
            positive_money
            + opt_sp
            + pynini.cross("/", " bölü ")
            + opt_sp
            + rate_units
        ).optimize()

        # Repeated currency ranges: $10-$20 -> on dolar ila yirmi dolar, ₺50,00-₺100,00 -> elli lira ila yüz lira
        dash = pynini.union("-", "–", "—")
        range_graph = (
            positive_money
            + opt_sp
            + pynini.cross(dash, " ila ")
            + opt_sp
            + positive_money
            | pynini.union(*[
                integer_part + opt_sp + pynini.cross(dash, " ila ") + opt_sp
                + integer_part + opt_sp + pynutil.delete(sym) + pynutil.insert(" " + major)
                for sym, major, _ in currencies_suffix
            ])
        ).optimize()
        self.range_graph = range_graph

        all_money = (
            range_graph
            | rate_graph
            | all_shorthands
            | positive_money
        ).optimize()
        self.all_money = all_money

        self.fst = (pynutil.insert('name: "') + convert_space(all_money) + pynutil.insert('"')).optimize()
