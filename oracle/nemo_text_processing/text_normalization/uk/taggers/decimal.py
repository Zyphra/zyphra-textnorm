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


def _build_fractional_part(cardinal: CardinalFst):
    """
    Builds the fractional part of decimals with exact agreement on the denominator:
    1 digit -> десята / десятих
    2 digits -> сота / сотих
    3 digits -> тисячна / тисячних
    4 digits -> десятитисячна / десятитисячних
    5 digits -> стотисячна / стотисячних
    6 digits -> мільйонна / мільйонних
    """
    g_f = cardinal.graph_feminine
    d_not_1 = pynini.difference(NEMO_DIGIT, "1")
    strip_zeros = pynutil.delete(pynini.closure("0")) + (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT)

    def classify_fraction(n_digits: int, denom_one: str, denom_other: str):
        total_pats = NEMO_DIGIT ** n_digits
        # Matches numbers ending in 1 (not 11)
        pat_one = pynini.accep("1") if n_digits == 1 else (
            NEMO_DIGIT ** (n_digits - 2) + d_not_1 + "1"
        )
        pat_other = pynini.difference(total_pats, pat_one | pynini.accep("0" * n_digits))

        graph_one = (pat_one @ strip_zeros @ g_f) + pynutil.insert(f" {denom_one}")
        graph_other = (pat_other @ strip_zeros @ g_f) + pynutil.insert(f" {denom_other}")
        graph_zero = pynini.cross("0" * n_digits, f"нуль {denom_other}")
        return graph_one | graph_other | graph_zero

    f1 = classify_fraction(1, "десята", "десятих")
    f2 = classify_fraction(2, "сота", "сотих")
    f3 = classify_fraction(3, "тисячна", "тисячних")
    f4 = classify_fraction(4, "десятитисячна", "десятитисячних")
    f5 = classify_fraction(5, "стотисячна", "стотисячних")
    f6 = classify_fraction(6, "мільйонна", "мільйонних")

    return (f1 | f2 | f3 | f4 | f5 | f6).optimize()


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian decimals:
        0,729 -> нуль цілих сімсот двадцять дев'ять тисячних
        3,02 -> три цілих дві сотих
        0,003 -> нуль цілих три тисячних
        1,2 -> одна ціла дві десятих
        -2,5 -> мінус дві цілих п'ять десятих
        99.9% -> дев'яносто дев'ять цілих дев'ять десятих відсотка
        1,23 млрд -> одна ціла двадцять три сотих мільярда
    """

    def __init__(self, cardinal: CardinalFst = None):
        super().__init__(name="decimal", kind="classify")
        cardinal = cardinal or CardinalFst()

        g_f = cardinal.graph_feminine
        d_not_1 = pynini.difference(NEMO_DIGIT, "1")

        # Integer part agreement:
        # Ending in 1 (not 11) -> одна ціла / двадцять одна ціла
        # Any other -> нуль цілих / дві цілих / п'ять цілих
        int_digits = pynini.closure(NEMO_DIGIT, 1)
        pat_one = pynini.accep("1") | (pynini.closure(NEMO_DIGIT) + d_not_1 + "1")
        pat_other = pynini.difference(int_digits, pat_one)

        integer_one = (pat_one @ g_f) + pynutil.insert(" ціла ")
        integer_other = (pat_other @ g_f) + pynutil.insert(" цілих ")
        integer_part = (integer_one | integer_other).optimize()

        # Separator: comma or dot
        sep = pynutil.delete(pynini.union(",", "."))

        # Fractional part
        fraction_part = _build_fractional_part(cardinal)

        minus = pynini.cross(pynini.union("-", "−"), "мінус ")
        opt_minus = pynini.closure(minus, 0, 1)

        decimal_core = opt_minus + integer_part + sep + fraction_part

        # Decimals with scale abbreviations (млн, млрд)
        # e.g. "1,23 млрд" -> "одна ціла двадцять три сотих мільярда"
        # "1,23 млн" -> "одна ціла двадцять три сотих мільйона"
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        scale_abbr = (
            pynini.cross("млрд", "мільярда")
            | pynini.cross("млрд.", "мільярда")
            | pynini.cross("млн", "мільйона")
            | pynini.cross("млн.", "мільйона")
        )
        decimal_scaled = decimal_core + opt_space + pynutil.insert(" ") + scale_abbr

        # Decimals with currencies or units:
        # e.g. "1,23 млрд руб." -> "одна ціла двадцять три сотих мільярда рублів"
        # "1,23 млрд грн" -> "одна ціла двадцять три сотих мільярда гривень"
        # "3,2 л" -> "три цілих дві десятих літра"
        scale_curr = (
            pynini.cross("руб.", "рублів")
            | pynini.cross("руб", "рублів")
            | pynini.cross("грн.", "гривень")
            | pynini.cross("грн", "гривень")
        )
        decimal_scaled_curr = (
            decimal_scaled + opt_space + pynutil.insert(" ") + scale_curr
        )

        unit_liters = pynini.cross("л", "літра") | pynini.cross("л.", "літра")
        decimal_unit = decimal_core + opt_space + pynutil.insert(" ") + unit_liters

        # Percentages with decimals: "99.9%" -> "дев'яносто дев'ять цілих дев'ять десятих відсотка"
        pct_sign = pynutil.delete("%")
        pct_word = pynutil.insert(" відсотка")
        decimal_pct = decimal_core + opt_space + pct_sign + pct_word

        all_decimals = (
            pynutil.add_weight(decimal_scaled_curr, 0.05)
            | pynutil.add_weight(decimal_scaled, 0.06)
            | pynutil.add_weight(decimal_unit, 0.07)
            | pynutil.add_weight(decimal_pct, 0.08)
            | pynutil.add_weight(decimal_core, 0.1)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_decimals)
            + pynutil.insert('"')
        ).optimize()
