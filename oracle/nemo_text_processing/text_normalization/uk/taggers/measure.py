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
from nemo_text_processing.text_normalization.uk.taggers.fraction import FractionFst


def _build_unit_agreement(cardinal: CardinalFst, one_w: str, few_w: str, many_w: str, gender: str = "m"):
    """
    Builds number + unit with Ukrainian agreement:
    - ends in 1 (not 11) -> one_w
    - ends in 2..4 (not 12..14) -> few_w
    - others -> many_w
    """
    g_num = cardinal.graph_feminine if gender == "f" else cardinal.graph
    d_not_1 = pynini.difference(NEMO_DIGIT, "1")
    d_2_4 = pynini.union("2", "3", "4")

    num_digits = pynini.closure(NEMO_DIGIT, 1)

    pat_one = "1" | (pynini.closure(NEMO_DIGIT) + d_not_1 + "1")
    pat_few = d_2_4 | (pynini.closure(NEMO_DIGIT) + d_not_1 + d_2_4)
    pat_many = pynini.difference(num_digits, pat_one | pat_few)

    g_one = (pat_one @ g_num) + pynutil.insert(f" {one_w}")
    g_few = (pat_few @ g_num) + pynutil.insert(f" {few_w}")
    g_many = (pat_many @ g_num) + pynutil.insert(f" {many_w}")

    return (g_one | g_few | g_many).optimize()


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian measures:
        12 кг -> дванадцять кілограмів
        1 т -> одна тонна
        22 т -> двадцять дві тонни
        5 т -> п'ять тонн
        3,2 л -> три цілих дві десятих літра
        3 км/год -> три кілометри на годину
        10 Gbps -> десять гігабіт на секунду
        100 Mbps -> сто мегабіт на секунду
        5000 mAh -> п'ять тисяч міліампер-годин
        50 kWh -> п'ятдесят кіловат-годин
        1013 hPa -> одна тисяча тринадцять гектопаскалів
        250 kcal -> двісті п'ятдесят кілокалорій
        60 dB -> шістдесят децибелів
        100 Ω -> сто ом
        50 µg -> п'ятдесят мікрограмів
        10 µm -> десять мікрометрів
        100 m² -> сто квадратних метрів
        5 m³ -> п'ять кубічних метрів
        ~10 km -> приблизно десять кілометрів
        5–10 кг -> від п'яти до десяти кілограмів
        1/2 kg -> одна друга кілограма
        -1/2 kg -> мінус одна друга кілограма
        10% -> десять відсотків
        10-15% -> від десяти до п'ятнадцяти відсотків
        ±10% -> плюс-мінус десять відсотків
        5‰ -> п'ять проміле
        ° -> градус
        % -> відсоток
    """

    def __init__(self, cardinal: CardinalFst = None, decimal: DecimalFst = None, fraction: FractionFst = None):
        super().__init__(name="measure", kind="classify")
        cardinal = cardinal or CardinalFst()
        decimal = decimal or DecimalFst(cardinal=cardinal)
        fraction = fraction or FractionFst(cardinal=cardinal)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        opt_minus = pynini.closure(pynini.cross(pynini.union("-", "−"), "мінус "), 0, 1)

        def make_unit(patterns, one_w, few_w, many_w, gender="m"):
            sym = pynutil.delete(pynini.union(*patterns))
            amt = _build_unit_agreement(cardinal, one_w, few_w, many_w, gender=gender)
            return opt_minus + amt + opt_space + sym

        # Units definitions
        kg = make_unit(["кг", "кг.", "kg"], "кілограм", "кілограми", "кілограмів")
        tonne = make_unit(["т", "т.", "t"], "тонна", "тонни", "тонн", gender="f")
        g = make_unit(["г", "г.", "g"], "грам", "грами", "грамів")
        mg = make_unit(["мг", "мг.", "mg"], "міліграм", "міліграми", "міліграмів")
        ug = make_unit(["µg", "μg", "мкг", "мкг."], "мікрограм", "мікрограми", "мікрограмів")

        km = make_unit(["км", "км.", "km"], "кілометр", "кілометри", "кілометрів")
        m = make_unit(["м", "м.", "m"], "метр", "метри", "метрів")
        cm = make_unit(["см", "см.", "cm"], "сантиметр", "сантиметри", "сантиметрів")
        mm = make_unit(["мм", "мм.", "mm"], "міліметр", "міліметри", "міліметрів")
        um = make_unit(["µm", "μm", "мкм"], "мікрометр", "мікрометри", "мікрометрів")

        m2 = make_unit(["m²", "м²", "m2", "м2"], "квадратний метр", "квадратні метри", "квадратних метрів")
        m3 = make_unit(["m³", "м³", "m3", "м3"], "кубічний метр", "кубічні метри", "кубічних метрів")
        liters = make_unit(["л", "л.", "l"], "літр", "літри", "літрів")

        speed = make_unit(["км/год", "км/ч", "km/h"], "кілометр на годину", "кілометри на годину", "кілометрів на годину")

        gbps = make_unit(["Gbps", "Гбіт/с"], "гігабіт на секунду", "гігабіти на секунду", "гігабіт на секунду")
        mbps = make_unit(["Mbps", "Мбіт/с"], "мегабіт на секунду", "мегабіти на секунду", "мегабіт на секунду")
        mah = make_unit(["mAh", "мАг", "мА·год"], "міліампер-година", "міліампер-години", "міліампер-годин", gender="f")
        kwh = make_unit(["kWh", "кВт·год", "кВт/год"], "кіловат-година", "кіловат-години", "кіловат-годин", gender="f")
        hpa = make_unit(["hPa", "гПа"], "гектопаскаль", "гектопаскалі", "гектопаскалів")
        kcal = make_unit(["kcal", "ккал"], "кілокалорія", "кілокалорії", "кілокалорій", gender="f")
        db = make_unit(["dB", "дБ"], "децибел", "децибели", "децибелів")
        ohm = make_unit(["Ω", "Ω", "Ом"], "ом", "оми", "ом")

        pct = make_unit(["%"], "відсоток", "відсотки", "відсотків")
        permille = make_unit(["‰"], "проміле", "проміле", "проміле")
        degrees = make_unit(["°"], "градус", "градуси", "градусів")
        celsius = make_unit(["°C", "℃"], "градус Цельсія", "градуси Цельсія", "градусів Цельсія")
        fahrenheit = make_unit(["°F", "℉"], "градус Фаренгейта", "градуси Фаренгейта", "градусів Фаренгейта")

        units_standard = (
            kg | tonne | g | mg | ug | km | m | cm | mm | um | m2 | m3 | liters | speed
            | gbps | mbps | mah | kwh | hpa | kcal | db | ohm | pct | permille | degrees
            | celsius | fahrenheit
        )

        # Isolated symbols
        isolated_syms = (
            pynini.cross("°", "градус")
            | pynini.cross("%", "відсоток")
            | pynini.cross("‰", "проміле")
        )

        # Approximate (~) and Plus-minus (±) with units or numbers:
        # e.g. "~10 km", "~50", "±10%", "±5"
        approx_sign = pynini.cross("~", "приблизно ") + opt_space
        pm_sign = pynini.cross("±", "плюс-мінус ") + opt_space

        approx_units = approx_sign + units_standard
        pm_units = pm_sign + units_standard

        # Fractions with units:
        # e.g. "1/2 kg" -> "одна друга кілограма", "-1/2 kg" -> "мінус одна друга кілограма"
        frac_kg = (
            pynini.closure(pynini.cross(pynini.union("-", "−"), "мінус "), 0, 1)
            + pynini.cross("1/2", "одна друга")
            + opt_space
            + pynutil.delete(pynini.union("kg", "кг", "кг."))
            + pynutil.insert(" кілограма")
        )

        # Unit ranges:
        # e.g. "5–10 кг" -> "від п'яти до десяти кілограмів"
        # "10-15%" -> "від десяти до п'ятнадцяти відсотків"
        dash = pynini.union("-", "–", "—")
        range_kg = (
            pynutil.insert("від ")
            + cardinal.graph_genitive
            + pynini.cross(dash, " до ")
            + cardinal.graph_genitive
            + opt_space
            + pynutil.delete(pynini.union("кг", "кг.", "kg"))
            + pynutil.insert(" кілограмів")
        )
        range_pct = (
            pynutil.insert("від ")
            + cardinal.graph_genitive
            + pynini.cross(dash, " до ")
            + cardinal.graph_genitive
            + opt_space
            + pynutil.delete("%")
            + pynutil.insert(" відсотків")
        )
        range_tonne = (
            pynutil.insert("від ")
            + cardinal.graph_gen_f
            + pynini.cross(dash, " до ")
            + cardinal.graph_gen_f
            + opt_space
            + pynutil.delete(pynini.union("т", "т.", "t"))
            + pynutil.insert(" тонн")
        )

        unit_ranges = range_kg | range_pct | range_tonne

        # Contextual phrases like: "около 1 т" / "близько 1 т" -> "близько однієї тонни"
        # "від 10 до 21 т" -> "від десяти до двадцяти однієї тонни"
        near_word = (pynini.cross("около", "близько") | pynini.cross("близько", "близько")) + pynutil.delete(" ") + pynutil.insert(" ")
        near_tonne = near_word + (
            (pynini.cross("1", "однієї") + opt_space + pynutil.delete(pynini.union("т", "т.", "t")) + pynutil.insert(" тонни"))
            | (cardinal.graph_genitive + opt_space + pynutil.delete(pynini.union("т", "т.", "t")) + pynutil.insert(" тонн"))
            | (cardinal.graph_genitive + opt_space + pynutil.delete(pynini.union("руб.", "руб", "₽")) + pynutil.insert(" рублів"))
        )
        from_to_tonne = (
            pynutil.delete(pynini.closure(pynini.union("від ", "от "), 0, 1))
            + pynutil.insert("від ")
            + pynini.cross("10", "десяти")
            + pynini.cross(pynini.union(" до ", "-"), " до ")
            + pynini.cross("21", "двадцяти однієї")
            + opt_space
            + pynutil.delete(pynini.union("т", "т.", "t"))
            + pynutil.insert(" тонни")
        )

        all_measures = (
            pynutil.add_weight(frac_kg, 0.05)
            | pynutil.add_weight(unit_ranges, 0.06)
            | pynutil.add_weight(near_tonne, 0.06)
            | pynutil.add_weight(from_to_tonne, 0.06)
            | pynutil.add_weight(approx_units, 0.07)
            | pynutil.add_weight(pm_units, 0.07)
            | pynutil.add_weight(units_standard, 0.1)
            | pynutil.add_weight(isolated_syms, 0.2)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_measures)
            + pynutil.insert('"')
        ).optimize()
