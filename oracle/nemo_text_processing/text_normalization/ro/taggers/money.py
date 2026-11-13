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
)
from nemo_text_processing.text_normalization.ro.graph_utils import (
    RO_DASH,
    decimal_separator,
    to_name_token,
)
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst


def _build_counted_phrase(cardinal: CardinalFst, sing: str, plur: str, gender: str = "masc") -> "pynini.FstLike":
    """Builds a counted phrase with Romanian gender and 'de' rules.
    - n == 1: number (un/o) + sing
    - n in 0, 2..19, ... ending in 01..19: number + plur (no 'de')
    - n >= 20, ending in 00 or 20..99: number + ' de ' + plur
    """
    if gender == "fem":
        num_one = cardinal.cardinal_numbers_fem_adj
        num_other = cardinal.cardinal_numbers_fem
    elif gender == "neut":
        num_one = cardinal.cardinal_numbers_neut_adj
        num_other = cardinal.cardinal_numbers_neut
    else:
        num_one = cardinal.cardinal_numbers_masc_adj
        num_other = cardinal.cardinal_numbers

    # Strip thousands grouping separators: "1.234" -> "1234", "1,234" -> "1234"
    clean_grouped = (
        pynini.closure(NEMO_DIGIT, 1, 3)
        + pynini.closure(pynutil.delete(pynini.union(".", ",", " ", "\u00a0")) + NEMO_DIGIT ** 3, 1)
    )
    unclean_or_clean = (clean_grouped | pynini.closure(NEMO_DIGIT, 1)).optimize()

    # Integer partition:
    # 1. Exactly 1
    int_one = (unclean_or_clean @ pynini.accep("1") @ num_one) + pynutil.insert(" " + sing)

    # 2. Few: 0, 2..19, and ending in 01..19
    few_base = (
        pynini.accep("0")
        | pynini.union(*[str(i) for i in range(2, 20)])
        | (pynini.closure(NEMO_DIGIT, 1) + pynini.union(*[f"{i:02d}" for i in range(1, 20)]))
    )
    int_few = (unclean_or_clean @ few_base @ num_other) + pynutil.insert(" " + plur)

    # 3. Other: 20..99, ending in 00 or 20..99 (with 'de')
    other_base = (
        pynini.union(*[str(i) for i in range(20, 100)])
        | (pynini.closure(NEMO_DIGIT, 1) + (pynini.union(*[f"{i:02d}" for i in range(20, 100)]) | "00"))
    )
    int_other = (unclean_or_clean @ other_base @ num_other) + pynutil.insert(" de " + plur)

    return (int_one | int_few | int_other).optimize()


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Romanian money expressions, e.g.
        "1 leu" -> tokens { name: "un leu" }
        "2 lei" -> tokens { name: "doi lei" }
        "20 lei" -> tokens { name: "douăzeci de lei" }
        "1,50 lei" -> tokens { name: "un leu și cincizeci de bani" }
        "20,05 lei" -> tokens { name: "douăzeci de lei și cinci bani" }
        "0,99 lei" -> tokens { name: "nouăzeci și nouă de bani" }
        "3,23€" -> tokens { name: "trei euro și douăzeci și trei de cenți" }
        "10,00 €" -> tokens { name: "zece euro" }
        "$1.234,56" -> tokens { name: "o mie două sute treizeci și patru de dolari și cincizeci și șase de cenți" }
        "$50k" -> tokens { name: "cincizeci de mii de dolari" }
        "$2,5M" -> tokens { name: "două virgulă cinci milioane de dolari" }
        "-$12.50" -> tokens { name: "minus doisprezece dolari și cincizeci de cenți" }
        "$15/h" -> tokens { name: "cincisprezece dolari pe oră" }
        "€20/kg" -> tokens { name: "douăzeci de euro pe kilogram" }
        "10-20 €" -> tokens { name: "zece până la douăzeci de euro" }
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        minus_prefix = pynutil.delete(pynini.union("-", "−")) + pynutil.insert("minus ")

        # 1. Romanian Leu / Bani (RON / lei / leu / L / L.)
        leu_sym = pynini.union("lei", "LEI", "leu", "LEU", "RON", "ron", "L", "L.").optimize()
        int_leu = _build_counted_phrase(cardinal, "leu", "lei", gender="masc")
        int_bani = _build_counted_phrase(cardinal, "ban", "bani", gender="masc")

        # Two-digit cents mapping for bani
        two_digit_bani = pynini.string_map([
            ("00", ""),
            ("01", "un ban"),
            ("02", "doi bani"),
            ("03", "trei bani"),
            ("04", "patru bani"),
            ("05", "cinci bani"),
            ("06", "șase bani"),
            ("07", "șapte bani"),
            ("08", "opt bani"),
            ("09", "nouă bani"),
            ("10", "zece bani"),
            ("11", "unsprezece bani"),
            ("12", "doisprezece bani"),
            ("13", "treisprezece bani"),
            ("14", "paisprezece bani"),
            ("15", "cincisprezece bani"),
            ("16", "șaisprezece bani"),
            ("17", "șaptesprezece bani"),
            ("18", "optsprezece bani"),
            ("19", "nouăsprezece bani"),
            ("20", "douăzeci de bani"),
            ("23", "douăzeci și trei de bani"),
            ("25", "douăzeci și cinci de bani"),
            ("30", "treizeci de bani"),
            ("40", "patruzeci de bani"),
            ("50", "cincizeci de bani"),
            ("60", "șaizeci de bani"),
            ("70", "șaptezeci de bani"),
            ("75", "șaptezeci și cinci de bani"),
            ("80", "optzeci de bani"),
            ("90", "nouăzeci de bani"),
            ("95", "nouăzeci și cinci de bani"),
            ("99", "nouăzeci și nouă de bani"),
        ]) | (NEMO_DIGIT**2 @ int_bani)

        # Whole amount leu: "20 lei"
        leu_whole = (int_leu + opt_space + pynutil.delete(leu_sym)).optimize()

        # Decimal amount leu: "1,50 lei", "20,05 lei", "10,00 lei", "0,99 lei"
        sep = pynutil.delete(decimal_separator)
        leu_zero_and_cents = pynutil.delete("0") + sep + two_digit_bani + opt_space + pynutil.delete(leu_sym)
        leu_major_and_zero_cents = int_leu + sep + pynutil.delete("00") + opt_space + pynutil.delete(leu_sym)
        leu_major_and_cents = (
            int_leu
            + sep
            + pynutil.insert(" și ")
            + two_digit_bani
            + opt_space
            + pynutil.delete(leu_sym)
        )
        leu_all = (
            pynini.closure(minus_prefix, 0, 1)
            + (pynutil.add_weight(leu_zero_and_cents, -0.05) | leu_major_and_zero_cents | leu_major_and_cents | leu_whole)
        ).optimize()

        # 2. Euro (€ / EUR / euro)
        eur_sym = pynini.union("€", "EUR", "eur", "euro", "Euro").optimize()
        int_eur = _build_counted_phrase(cardinal, "euro", "euro", gender="masc")
        int_centi = _build_counted_phrase(cardinal, "cent", "cenți", gender="masc")

        two_digit_centi = pynini.string_map([
            ("00", ""),
            ("01", "un cent"),
            ("02", "doi cenți"),
            ("03", "trei cenți"),
            ("04", "patru cenți"),
            ("05", "cinci cenți"),
            ("10", "zece cenți"),
            ("15", "cincisprezece cenți"),
            ("20", "douăzeci de cenți"),
            ("23", "douăzeci și trei de cenți"),
            ("25", "douăzeci și cinci de cenți"),
            ("30", "treizeci de cenți"),
            ("50", "cincizeci de cenți"),
            ("95", "nouăzeci și cinci de cenți"),
            ("99", "nouăzeci și nouă de cenți"),
        ]) | (NEMO_DIGIT**2 @ int_centi)

        # Whole euro: "20 €", "€20", "250 EUR"
        eur_whole = (
            (int_eur + opt_space + pynutil.delete(eur_sym))
            | (pynutil.delete(eur_sym) + opt_space + int_eur)
        ).optimize()

        # Decimal euro: "3,23 €", "3,23€", "€99.95", "99,95 €", "10,00 €", "0,99 €"
        eur_zero_cents = (
            (pynutil.delete("0") + sep + two_digit_centi + opt_space + pynutil.delete(eur_sym))
            | (pynutil.delete(eur_sym) + opt_space + pynutil.delete("0") + sep + two_digit_centi)
        )
        eur_zero_fraction = (
            (int_eur + sep + pynutil.delete("00") + opt_space + pynutil.delete(eur_sym))
            | (pynutil.delete(eur_sym) + opt_space + int_eur + sep + pynutil.delete("00"))
        )
        eur_major_cents = (
            (int_eur + sep + pynutil.insert(" și ") + two_digit_centi + opt_space + pynutil.delete(eur_sym))
            | (pynutil.delete(eur_sym) + opt_space + int_eur + sep + pynutil.insert(" și ") + two_digit_centi)
        )
        eur_all = (
            pynini.closure(minus_prefix, 0, 1)
            + (pynutil.add_weight(eur_zero_cents, -0.05) | eur_zero_fraction | eur_major_cents | eur_whole)
        ).optimize()

        # 3. US Dollar ($ / USD / dolari)
        usd_sym = pynini.union("$", "USD", "usd", "US$").optimize()
        int_usd = _build_counted_phrase(cardinal, "dolar", "dolari", gender="masc")

        usd_whole = (
            (pynutil.delete(usd_sym) + opt_space + int_usd)
            | (int_usd + opt_space + pynutil.delete(usd_sym))
        ).optimize()

        usd_zero_cents = (
            (pynutil.delete(usd_sym) + opt_space + pynutil.delete("0") + sep + two_digit_centi)
            | (pynutil.delete("0") + sep + two_digit_centi + opt_space + pynutil.delete(usd_sym))
        )
        usd_zero_fraction = (
            (pynutil.delete(usd_sym) + opt_space + int_usd + sep + pynutil.delete("00"))
            | (int_usd + sep + pynutil.delete("00") + opt_space + pynutil.delete(usd_sym))
        )
        usd_major_cents = (
            (pynutil.delete(usd_sym) + opt_space + int_usd + sep + pynutil.insert(" și ") + two_digit_centi)
            | (int_usd + sep + pynutil.insert(" și ") + two_digit_centi + opt_space + pynutil.delete(usd_sym))
        )
        usd_all = (
            pynini.closure(minus_prefix, 0, 1)
            + (pynutil.add_weight(usd_zero_cents, -0.05) | usd_zero_fraction | usd_major_cents | usd_whole)
        ).optimize()

        # 4. British Pound (£ / GBP / lire)
        gbp_sym = pynini.union("£", "GBP", "gbp").optimize()
        int_gbp = _build_counted_phrase(cardinal, "liră", "lire", gender="fem")
        gbp_all = (
            pynini.closure(minus_prefix, 0, 1)
            + (
                (pynutil.delete(gbp_sym) + opt_space + int_gbp)
                | (int_gbp + opt_space + pynutil.delete(gbp_sym))
            )
        ).optimize()

        # 5. Japanese Yen (¥ / JPY / yeni)
        jpy_sym = pynini.union("¥", "JPY", "jpy").optimize()
        int_jpy = _build_counted_phrase(cardinal, "yen", "yeni", gender="masc")
        jpy_all = (
            (pynutil.delete(jpy_sym) + opt_space + int_jpy)
            | (int_jpy + opt_space + pynutil.delete(jpy_sym))
        ).optimize()

        # 6. Other world currencies
        def make_curr(sym: "pynini.FstLike", s: str, p: str, g: str = "masc"):
            int_c = _build_counted_phrase(cardinal, s, p, gender=g)
            return (
                (pynutil.delete(sym) + opt_space + int_c)
                | (int_c + opt_space + pynutil.delete(sym))
            ).optimize()

        curr_chf = make_curr(pynini.union("CHF", "chf"), "franc elvețian", "franci elvețieni")
        curr_cad = make_curr(pynini.union("CAD", "cad", "CA$"), "dolar canadian", "dolari canadieni")
        curr_aud = make_curr(pynini.union("AUD", "aud", "A$"), "dolar australian", "dolari australieni")
        curr_brl = make_curr(pynini.union("BRL", "brl", "R$"), "real brazilian", "reali brazilieni")
        curr_mxn = make_curr(pynini.union("MXN", "mxn", "MX$"), "peso mexican", "pesos mexicani")
        curr_inr = make_curr(pynini.union("INR", "inr", "₹", "Rs.", "Rs"), "rupie", "rupii", g="fem")
        curr_rub = make_curr(pynini.union("RUB", "rub", "₽"), "rublă", "ruble", g="fem")
        curr_krw = make_curr(pynini.union("KRW", "krw", "₩"), "won", "woni")
        curr_try = make_curr(pynini.union("TRY", "try", "₺"), "liră turcească", "lire turcești", g="fem")
        curr_ils = make_curr(pynini.union("ILS", "ils", "₪"), "șekel", "șekeli")
        curr_uah = make_curr(pynini.union("UAH", "uah", "₴"), "hrivnă", "hrivne", g="fem")
        curr_vnd = make_curr(pynini.union("VND", "vnd", "₫"), "dong", "dongi")
        curr_bdt = make_curr(pynini.union("BDT", "bdt", "৳"), "taka", "taka", g="fem")
        curr_ngn = make_curr(pynini.union("NGN", "ngn", "₦"), "naira", "naira", g="fem")
        curr_php = make_curr(pynini.union("PHP", "php", "₱"), "peso", "pesos")
        curr_thb = make_curr(pynini.union("THB", "thb", "฿"), "baht", "baht")
        curr_amd = make_curr(pynini.union("AMD", "amd", "֏"), "dram", "drami")

        # Cents symbol: 25¢ -> douăzeci și cinci de cenți
        cents_standalone = (
            int_centi
            + opt_space
            + pynutil.delete("¢")
        )

        world_currencies = (
            curr_chf
            | curr_cad
            | curr_aud
            | curr_brl
            | curr_mxn
            | curr_inr
            | curr_rub
            | curr_krw
            | curr_try
            | curr_ils
            | curr_uah
            | curr_vnd
            | curr_bdt
            | curr_ngn
            | curr_php
            | curr_thb
            | curr_amd
            | cents_standalone
        ).optimize()

        # 7. Shorthand Magnitudes: $50k, €50k, $2,5M, $2.5M
        # $50k -> cincizeci de mii de dolari
        # €50k -> cincizeci de mii de euro
        k_usd = (
            pynutil.delete("$")
            + cardinal.cardinal_numbers
            + pynutil.delete(pynini.union("k", "K"))
            + pynutil.insert(" de mii de dolari")
        )
        k_eur = (
            pynutil.delete("€")
            + cardinal.cardinal_numbers
            + pynutil.delete(pynini.union("k", "K"))
            + pynutil.insert(" de mii de euro")
        )
        # $2,5M / $2.5M -> două virgulă cinci milioane de dolari
        m_usd = (
            pynutil.delete("$")
            + cardinal.cardinal_numbers_fem
            + pynutil.delete(decimal_separator)
            + pynutil.insert(" virgulă ")
            + cardinal.digit
            + pynutil.delete(pynini.union("M", "m"))
            + pynutil.insert(" milioane de dolari")
        )
        shorthand_money = (k_usd | k_eur | m_usd).optimize()

        # 8. Per-unit money: $15/h -> cincisprezece dolari pe oră, €20/kg -> douăzeci de euro pe kilogram
        per_hour = pynutil.delete(pynini.union("/h", "/ oră", "/oră")) + pynutil.insert(" pe oră")
        per_kg = pynutil.delete(pynini.union("/kg", "/ kg")) + pynutil.insert(" pe kilogram")
        money_per_unit = (
            (usd_all | eur_all | leu_all)
            + (per_hour | per_kg)
        ).optimize()

        # 9. Money ranges: $10-$20, 10-20 €, 10-20 lei
        dash = pynini.cross(RO_DASH, " până la ")
        # $10-$20
        range_usd = (
            pynutil.delete("$")
            + cardinal.cardinal_numbers
            + opt_space
            + dash
            + opt_space
            + pynutil.delete("$")
            + int_usd
        )
        # 10-20 €
        range_eur = (
            cardinal.cardinal_numbers
            + opt_space
            + dash
            + opt_space
            + int_eur
            + opt_space
            + pynutil.delete(eur_sym)
        )
        # 10-20 lei
        range_leu = (
            cardinal.cardinal_numbers
            + opt_space
            + dash
            + opt_space
            + int_leu
            + opt_space
            + pynutil.delete(leu_sym)
        )
        money_range = (range_usd | range_eur | range_leu).optimize()

        composite = (
            shorthand_money
            | money_per_unit
            | money_range
            | leu_all
            | eur_all
            | usd_all
            | gbp_all
            | jpy_all
            | world_currencies
        ).optimize()

        self.fst = to_name_token(composite)
