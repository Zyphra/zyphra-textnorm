# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.uk.taggers.decimal import DecimalFst


def _build_currency_amount(cardinal: CardinalFst, one_word: str, few_word: str, many_word: str, gender: str = "m"):
    """
    Builds amount + currency name with proper Slavic agreement (one / few / many):
    - 1, 21, 101 -> one_word
    - 2..4, 22..24 -> few_word
    - 0, 5..20, 25..30 -> many_word
    """
    g_num = cardinal.graph_feminine if gender == "f" else cardinal.graph
    d_not_1 = pynini.difference(NEMO_DIGIT, "1")
    d_2_4 = pynini.union("2", "3", "4")

    grouped = pynini.closure(NEMO_DIGIT, 1, 3) + pynini.closure(
        pynutil.delete(pynini.union(" ", " ", ".")) + NEMO_DIGIT**3, 1
    )
    num_with_sep = pynini.closure(NEMO_DIGIT, 1) | grouped
    num_digits = pynini.closure(NEMO_DIGIT, 1)

    # Ends in 1 (not 11)
    pat_one = ("1" | (pynini.closure(NEMO_DIGIT, 0) + d_not_1 + "1"))
    # Ends in 2, 3, 4 (not 12..14)
    pat_few = (d_2_4 | (pynini.closure(NEMO_DIGIT, 0) + d_not_1 + d_2_4))
    # All others
    pat_many = pynini.difference(num_digits, pat_one | pat_few)

    g_one = (num_with_sep @ pat_one @ g_num) + pynutil.insert(f" {one_word}")
    g_few = (num_with_sep @ pat_few @ g_num) + pynutil.insert(f" {few_word}")
    g_many = (num_with_sep @ pat_many @ g_num) + pynutil.insert(f" {many_word}")

    return (g_one | g_few | g_many).optimize()


def _build_currency_genitive(cardinal: CardinalFst, gen_word: str):
    """Builds genitive form for ranges: 'від десяти доларів do двадцяти доларів'."""
    return cardinal.graph_genitive + pynutil.insert(f" {gen_word}")


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian money:
        1 ₴ -> одна гривня
        2 ₴ -> дві гривні
        5 ₴ -> п'ять гривень
        500 ₴ -> п'ятсот гривень
        6 грн. 35 коп. -> шість гривень тридцять п'ять копійок
        1,01 ₴ -> одна гривня одна копійка
        2,02 ₴ -> дві гривні дві копійки
        1 USD -> один долар
        $7.50 -> сім доларів п'ятдесят центів
        $50k -> п'ятдесят тисяч доларів
        $2,5M -> дві цілих п'ять десятих мільйона доларів
        -12,50 € -> мінус дванадцять євро п'ятдесят центів
        $15/h -> п'ятнадцять доларів на годину
        €20/kg -> двадцять євро за кілограм
        $10-$20 -> від десяти до двадцяти доларів
        10-20 € -> від десяти до двадцяти євро
    """

    def __init__(self, cardinal: CardinalFst = None, decimal: DecimalFst = None):
        super().__init__(name="money", kind="classify")
        cardinal = cardinal or CardinalFst()
        decimal = decimal or DecimalFst(cardinal=cardinal)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        del_dot = pynutil.delete(pynini.closure(".", 0, 1))

        # 1. Hryvnia (FEMININE: гривня, гривні, гривень) and Kopecks (копійка, копійки, копійок)
        uah_maj = _build_currency_amount(cardinal, "гривня", "гривні", "гривень", gender="f")
        kop_min = _build_currency_amount(cardinal, "копійка", "копійки", "копійок", gender="f")

        uah_sym = pynutil.delete(pynini.union("₴", "грн.", "грн", "UAH"))
        kop_sym = pynutil.delete(pynini.union("коп.", "коп"))

        # Major alone: "500 ₴", "1 ₴", "2 ₴", "500 грн.", "500грн."
        uah_alone = (uah_maj + opt_space + uah_sym) | (uah_sym + opt_space + uah_maj)

        # Compound written: "6 грн. 35 коп.", "6 грн 35 коп"
        num_digits = pynini.closure(NEMO_DIGIT, 1)
        uah_compound_written = (
            (num_digits @ uah_maj)
            + opt_space
            + uah_sym
            + opt_space
            + pynutil.insert(" ")
            + (num_digits @ kop_min)
            + opt_space
            + kop_sym
        )

        # Decimal currency: "1,01 ₴" -> "одна гривня одна копійка", "2,02 ₴" -> "дві гривні дві копійки", "5,50 ₴"
        sep = pynutil.delete(pynini.union(",", "."))
        d_not_1 = pynini.difference(NEMO_DIGIT, "1")
        # 2 decimal digits for kopecks/cents
        strip_zero_kop = pynutil.delete(pynini.closure("0", 0, 1)) + (NEMO_DIGIT - "0") | pynini.cross("00", "")
        kop_2digits = (NEMO_DIGIT ** 2) @ (
            (pynini.cross("01", "одна копійка"))
            | (pynini.cross("02", "дві копійки"))
            | (pynini.cross("03", "три копійки"))
            | (pynini.cross("04", "чотири копійки"))
            | (pynini.cross("05", "п'ять копійок"))
            | (pynini.cross("06", "шість копійок"))
            | (pynini.cross("07", "сім копійок"))
            | (pynini.cross("08", "вісім копійок"))
            | (pynini.cross("09", "дев'ять копійок"))
            | ((pynini.difference(NEMO_DIGIT ** 2, pynini.union("00", "01", "02", "03", "04", "05", "06", "07", "08", "09"))) @ kop_min)
        )
        uah_decimal = (
            (num_digits @ uah_maj)
            + sep
            + insert_space
            + kop_2digits
            + opt_space
            + uah_sym
        ) | (
            uah_sym
            + opt_space
            + (num_digits @ uah_maj)
            + sep
            + insert_space
            + kop_2digits
        )

        # "12,01 грн"
        uah_decimal_grn = (
            (num_digits @ uah_maj)
            + sep
            + insert_space
            + kop_2digits
            + opt_space
            + pynutil.delete(pynini.union("грн", "грн."))
        )

        kop_alone = (kop_min + opt_space + kop_sym) | (kop_sym + opt_space + kop_min)
        all_uah = uah_compound_written | uah_decimal | uah_decimal_grn | uah_alone | kop_alone

        # 2. USD (MASCULINE: долар, долари, доларів) and Cents (цент, центи, центів)
        usd_maj = _build_currency_amount(cardinal, "долар", "долари", "доларів", gender="m")
        cent_min = _build_currency_amount(cardinal, "цент", "центи", "центів", gender="m")
        usd_sym = pynutil.delete(pynini.union("$", "USD"))

        cent_2digits = (NEMO_DIGIT ** 2) @ (
            (pynini.cross("01", "один цент"))
            | (pynini.cross("02", "два центи"))
            | (pynini.cross("03", "три центи"))
            | (pynini.cross("04", "чотири центи"))
            | (pynini.cross("05", "п'ять центів"))
            | ((pynini.difference(NEMO_DIGIT ** 2, pynini.union("00", "01", "02", "03", "04", "05"))) @ cent_min)
        )

        usd_alone = (usd_sym + opt_space + usd_maj) | (usd_maj + opt_space + usd_sym)
        usd_glued = pynutil.delete("USD") + usd_maj
        usd_decimal = (
            usd_sym
            + opt_space
            + (num_digits @ usd_maj)
            + sep
            + insert_space
            + cent_2digits
        ) | (
            (num_digits @ usd_maj)
            + sep
            + insert_space
            + cent_2digits
            + opt_space
            + usd_sym
        )

        all_usd = usd_decimal | usd_alone | usd_glued

        # 3. EUR (INDECLINABLE: євро)
        eur_maj = cardinal.graph + pynutil.insert(" євро")
        eur_sym = pynutil.delete(pynini.union("€", "EUR"))
        eur_alone = (eur_sym + opt_space + eur_maj) | (eur_maj + opt_space + eur_sym)
        eur_decimal = (
            (eur_sym + opt_space + (num_digits @ eur_maj) + sep + insert_space + cent_2digits)
            | ((num_digits @ eur_maj) + sep + insert_space + cent_2digits + opt_space + eur_sym)
        )
        all_eur = eur_decimal | eur_alone

        # 4. RUB (MASCULINE: рубль, рублі, рублів)
        rub_maj = _build_currency_amount(cardinal, "рубль", "рублі", "рублів", gender="m")
        rub_sym = pynutil.delete(pynini.union("₽", "руб.", "руб", "RUB"))
        rub_alone = (rub_maj + opt_space + rub_sym) | (rub_sym + opt_space + rub_maj)
        all_rub = rub_alone

        # 5. Other world currencies
        def make_curr(sym_patterns, one_w, few_w, many_w, gender="m"):
            sym = pynutil.delete(pynini.union(*sym_patterns))
            amt = _build_currency_amount(cardinal, one_w, few_w, many_w, gender=gender)
            return (sym + opt_space + amt) | (amt + opt_space + sym)

        chf = make_curr(["CHF"], "швейцарський франк", "швейцарські франки", "швейцарських франків")
        cad = make_curr(["CAD", "CA$"], "канадський долар", "канадські долари", "канадських доларів")
        aud = make_curr(["A$"], "австралійський долар", "австралійські долари", "австралійських доларів")
        brl = make_curr(["R$"], "бразильський реал", "бразильські реали", "бразильських реалів")
        mxn = make_curr(["MX$", "MXN"], "мексиканський песо", "мексиканські песо", "мексиканських песо")
        inr = make_curr(["INR", "₹", "Rs.", "Rs"], "рупія", "рупії", "рупій", gender="f")
        krw = make_curr(["₩", "KRW"], "вона", "вони", "вон", gender="f")
        try_curr = make_curr(["₺", "TRY"], "турецька ліра", "турецькі ліри", "турецьких лір", gender="f")
        ils = make_curr(["₪", "ILS"], "новий ізраїльський шекель", "нові ізраїльські шекелі", "нових ізраїльських шекелів")
        vnd = make_curr(["₫", "VND"], "в'єтнамський донг", "в'єтнамські донги", "в'єтнамських донгів")
        bdt = make_curr(["৳", "BDT"], "бангладеська така", "бангладеські таки", "бангладеських так", gender="f")
        ngn = make_curr(["₦", "NGN"], "нігерійська найра", "нігерійські найри", "нігерійських найр", gender="f")
        php = make_curr(["₱", "PHP"], "філіппінський песо", "філіппінські песо", "філіппінських песо")
        thb = make_curr(["฿", "THB"], "тайський бат", "тайські бати", "тайських батів")
        amd = make_curr(["֏", "AMD"], "вірменський драм", "вірменські драми", "вірменських драмів")
        cents_alone = (num_digits @ cent_min) + pynutil.delete("¢")

        other_currencies = (
            chf | cad | aud | brl | mxn | inr | krw | try_curr | ils | vnd | bdt | ngn | php | thb | amd | cents_alone
        )

        # 6. Shorthands ($50k, €50k, $2,5M, $2.5M)
        k_shorthand = pynini.cross("k", " тисяч") | pynini.cross("K", " тисяч")
        m_shorthand = pynini.cross("M", " мільйона") | pynini.cross("m", " мільйона")

        usd_50k = usd_sym + (num_digits @ cardinal.graph) + k_shorthand + pynutil.insert(" доларів")
        eur_50k = eur_sym + (num_digits @ cardinal.graph) + k_shorthand + pynutil.insert(" євро")

        # "$2,5M" -> "дві цілих п'ять десятих мільйона доларів"
        dec_core = (
            (pat_one := ("1" | (num_digits + d_not_1 + "1"))) @ cardinal.graph_feminine + pynutil.insert(" ціла ")
            | pynini.difference(num_digits, pat_one) @ cardinal.graph_feminine + pynutil.insert(" цілих ")
        ) + sep + insert_space + (
            (NEMO_DIGIT @ (
                pynini.cross("1", "одна десята")
                | (pynini.difference(NEMO_DIGIT, pynini.union("0", "1")) @ cardinal.graph_feminine + pynutil.insert(" десятих"))
            ))
        )
        usd_2_5m = usd_sym + dec_core + m_shorthand + pynutil.insert(" доларів")
        eur_2_5m = eur_sym + dec_core + m_shorthand + pynutil.insert(" євро")

        shorthands = usd_50k | eur_50k | usd_2_5m | eur_2_5m

        # 7. Rates and per-units: "$15/h" -> "п'ятнадцять доларів на годину", "€20/kg" -> "двадцять євро за кілограм"
        per_hr = pynini.cross("/h", " на годину") | pynini.cross("/год", " на годину")
        per_kg = pynini.cross("/kg", " за кілограм") | pynini.cross("/кг", " за кілограм")

        rate_usd = (usd_sym + (num_digits @ usd_maj) | (num_digits @ usd_maj) + usd_sym) + per_hr
        rate_eur = (eur_sym + (num_digits @ eur_maj) | (num_digits @ eur_maj) + eur_sym) + per_kg

        rates = rate_usd | rate_eur

        # 8. Currency ranges:
        # "$10-$20" -> "від десяти до двадцяти доларів"
        # "10-20 €" -> "від десяти до двадцяти євро"
        dash = pynini.union("-", "–", "—")
        def currency_range(symbols, amount, unit):
            symbol = pynutil.delete(pynini.union(*symbols))
            gap = pynini.closure(pynutil.delete(" "))
            join = gap + pynini.cross(dash, " до ") + gap
            leading = symbol + gap + amount + join + pynini.closure(symbol + gap, 0, 1) + amount
            trailing = amount + join + amount + gap + symbol
            return pynutil.insert("від ") + (leading | trailing) + pynutil.insert(" " + unit)

        range_usd = currency_range(["$", "USD"], cardinal.graph_genitive, "доларів")
        range_eur = currency_range(["€", "EUR"], cardinal.graph_genitive, "євро")
        range_uah = currency_range(["₴", "грн.", "грн"], cardinal.graph_gen_f, "гривень")

        # Mixed currency range: "$10-€20" -> "від десяти доларів до двадцяти євро"
        mixed_usd_eur = (
            pynutil.insert("від ")
            + pynutil.delete("$")
            + cardinal.graph_genitive
            + pynutil.insert(" доларів")
            + pynini.cross(dash, " до ")
            + pynutil.delete("€")
            + cardinal.graph_genitive
            + pynutil.insert(" євро")
        )
        mixed_eur_usd = (
            pynutil.insert("від ")
            + pynutil.delete("€")
            + cardinal.graph_genitive
            + pynutil.insert(" євро")
            + pynini.cross(dash, " до ")
            + pynutil.delete("$")
            + cardinal.graph_genitive
            + pynutil.insert(" доларів")
        )

        ranges = (
            mixed_usd_eur
            | mixed_eur_usd
            | range_usd
            | range_eur
            | range_uah
        )

        minus = pynini.cross(pynini.union("-", "−"), "мінус ")
        opt_minus = pynini.closure(minus, 0, 1)

        total_money = (
            pynutil.add_weight(shorthands, 0.05)
            | pynutil.add_weight(rates, 0.06)
            | pynutil.add_weight(ranges, 0.07)
            | pynutil.add_weight(opt_minus + all_uah, 0.1)
            | pynutil.add_weight(opt_minus + all_usd, 0.1)
            | pynutil.add_weight(opt_minus + all_eur, 0.1)
            | pynutil.add_weight(opt_minus + all_rub, 0.1)
            | pynutil.add_weight(opt_minus + other_currencies, 0.12)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(total_money)
            + pynutil.insert('"')
        ).optimize()
