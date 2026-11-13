# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.uk.alphabet import TO_CYRILLIC, UK_ALPHA


def _build_digits_map(gender: str = "m"):
    d1 = "один" if gender == "m" else ("одна" if gender == "f" else "одне")
    d2 = "дві" if gender == "f" else "два"
    return [
        ("0", "нуль"),
        ("1", d1),
        ("2", d2),
        ("3", "три"),
        ("4", "чотири"),
        ("5", "п'ять"),
        ("6", "шість"),
        ("7", "сім"),
        ("8", "вісім"),
        ("9", "дев'ять"),
    ]


TEENS_MAP = [
    ("10", "десять"),
    ("11", "одинадцять"),
    ("12", "дванадцять"),
    ("13", "тринадцять"),
    ("14", "чотирнадцять"),
    ("15", "п'ятнадцять"),
    ("16", "шістнадцять"),
    ("17", "сімнадцять"),
    ("18", "вісімнадцять"),
    ("19", "дев'ятнадцять"),
]

TIES_MAP = [
    ("2", "двадцять"),
    ("3", "тридцять"),
    ("4", "сорок"),
    ("5", "п'ятдесят"),
    ("6", "шістдесят"),
    ("7", "сімдесят"),
    ("8", "вісімдесят"),
    ("9", "дев'яносто"),
]

HUNDREDS_MAP = [
    ("1", "сто"),
    ("2", "двісті"),
    ("3", "триста"),
    ("4", "чотириста"),
    ("5", "п'ятсот"),
    ("6", "шістсот"),
    ("7", "сімсот"),
    ("8", "вісімсот"),
    ("9", "дев'ятсот"),
]

GENITIVE_DIGITS_MAP = [
    ("0", "нуля"),
    ("1", "одного"),
    ("2", "двох"),
    ("3", "трьох"),
    ("4", "чотирьох"),
    ("5", "п'яти"),
    ("6", "шести"),
    ("7", "семи"),
    ("8", "восьми"),
    ("9", "дев'яти"),
]

GENITIVE_TEENS_MAP = [
    ("10", "десяти"),
    ("11", "одинадцяти"),
    ("12", "дванадцяти"),
    ("13", "тринадцяти"),
    ("14", "чотирнадцяти"),
    ("15", "п'ятнадцяти"),
    ("16", "шістнадцяти"),
    ("17", "сімнадцяти"),
    ("18", "вісімнадцяти"),
    ("19", "дев'ятнадцяти"),
]

GENITIVE_TIES_MAP = [
    ("2", "двадцяти"),
    ("3", "тридцяти"),
    ("4", "сорока"),
    ("5", "п'ятдесяти"),
    ("6", "шістдесяти"),
    ("7", "сімдесяти"),
    ("8", "вісімдесяти"),
    ("9", "дев'яноста"),
]

GENITIVE_HUNDREDS_MAP = [
    ("1", "ста"),
    ("2", "двохсот"),
    ("3", "трьохсот"),
    ("4", "чотирьохсот"),
    ("5", "п'ятисот"),
    ("6", "шестисот"),
    ("7", "семисот"),
    ("8", "восьмисот"),
    ("9", "дев'ятисот"),
]


def _build_three_digits_grammar(gender: str = "m", genitive: bool = False):
    """Builds transduction for a 3-digit slice (001-999) with given gender agreement."""
    if genitive:
        d_map = list(GENITIVE_DIGITS_MAP)
        if gender == "f":
            d_map[1] = ("1", "однієї")
    else:
        d_map = _build_digits_map(gender)
    teens_m = GENITIVE_TEENS_MAP if genitive else TEENS_MAP
    ties_m = GENITIVE_TIES_MAP if genitive else TIES_MAP
    hund_m = GENITIVE_HUNDREDS_MAP if genitive else HUNDREDS_MAP

    d_one = d_map[1][1]
    d_two = d_map[2][1]

    u1 = pynini.cross("1", d_one)
    u2 = pynini.cross("2", d_two)
    u3_9 = pynini.union(*[pynini.cross(k, v) for k, v in d_map[3:]])
    units_nonzero = u1 | u2 | u3_9
    del_0 = pynutil.delete("0")

    teens = pynini.union(*[pynini.cross(k, v) for k, v in teens_m])
    ties = pynini.union(*[pynini.cross(k, v) for k, v in ties_m])

    # 2 digits: 00..99
    # 00 -> ""
    two_00 = pynutil.delete("00")
    # 01..09
    two_0x = del_0 + units_nonzero
    # 10..19
    two_teens = teens
    # 20, 30..90
    two_ties_0 = ties + del_0
    # 21..99
    two_ties_u = ties + insert_space + units_nonzero

    two_nonzero = two_0x | two_teens | two_ties_0 | two_ties_u
    two_digits = two_00 | two_nonzero

    # Hundreds: 0..9
    hund_nonzero = pynini.union(*[pynini.cross(k, v) for k, v in hund_m])

    # 3 digits total
    three_digits = (
        del_0 + two_digits
        | hund_nonzero + (two_00 | (insert_space + two_nonzero))
    )
    return three_digits.optimize()


def _build_scale_group(scale_one: str, scale_few: str, scale_many: str, gender: str = "m", genitive: bool = False):
    """
    Builds a 3-digit group transducer that attaches scale words according to Ukrainian morphology:
    - ends in 1 (not 11): scale_one
    - ends in 2, 3, 4 (not 12..14): scale_few
    - other: scale_many
    - 000: deleted
    """
    g_three = _build_three_digits_grammar(gender=gender, genitive=genitive)

    d1 = "1"
    d2_4 = pynini.union("2", "3", "4")
    d_not_1 = pynini.difference(NEMO_DIGIT, "1")

    # Patterns matching 3 digits
    # Ending in 1 (not 11): x01, x21..x91 where x is any digit
    pat_one = NEMO_DIGIT + d_not_1 + d1
    # Ending in 2, 3, 4 (not 12..14): x02..x04, x22..x94
    pat_few = NEMO_DIGIT + d_not_1 + d2_4
    # All other non-zero 3-digit combinations
    all_3 = NEMO_DIGIT ** 3
    nonzero_3 = pynini.difference(all_3, "000")
    pat_many = pynini.difference(nonzero_3, pat_one | pat_few)

    # Special handling for single thousand "001": can be "одна тисяча" or "тисяча"
    t_one = (pat_one @ g_three) + pynutil.insert(f" {scale_one}")
    t_few = (pat_few @ g_three) + pynutil.insert(f" {scale_few}")
    t_many = (pat_many @ g_three) + pynutil.insert(f" {scale_many}")
    del_000 = pynutil.delete("000")

    return (t_one | t_few | t_many | del_000).optimize()


def _build_full_number(gender: str = "m", genitive: bool = False):
    """
    Builds a transducer for full numbers from 0 to 999,999,999,999,999.
    Properly handles:
    - Trillions (masculine)
    - Billions (masculine)
    - Millions (masculine)
    - Thousands (feminine: тисяча)
    - Units (given gender)
    """
    if genitive:
        # Genitive scales
        trillions = _build_scale_group("трильйона", "трильйонів", "трильйонів", gender="m", genitive=True)
        billions = _build_scale_group("мільярда", "мільярдів", "мільярдів", gender="m", genitive=True)
        millions = _build_scale_group("мільйона", "мільйонів", "мільйонів", gender="m", genitive=True)
        thousands = _build_scale_group("тисячі", "тисяч", "тисяч", gender="f", genitive=True)
        units_g = _build_three_digits_grammar(gender=gender, genitive=True)
    else:
        trillions = _build_scale_group("трильйон", "трильйони", "трильйонів", gender="m")
        billions = _build_scale_group("мільярд", "мільярди", "мільярдів", gender="m")
        millions = _build_scale_group("мільйон", "мільйони", "мільйонів", gender="m")
        thousands = _build_scale_group("тисяча", "тисячі", "тисяч", gender="f")
        units_g = _build_three_digits_grammar(gender=gender, genitive=False)

    nonzero_units = pynini.difference(NEMO_DIGIT ** 3, "000") @ units_g
    del_000 = pynutil.delete("000")
    units = (pynutil.insert(" ") + nonzero_units) | del_000

    pad = pynini.cdrewrite(pynini.closure(pynutil.insert("0")), "[BOS]", "", NEMO_SIGMA)
    clean_spaces = pynini.cdrewrite(pynini.cross("  ", " "), "", "", NEMO_SIGMA)
    strip_lead_space = pynini.cdrewrite(pynutil.delete(" "), "[BOS]", "", NEMO_SIGMA)
    strip_trail_space = pynini.cdrewrite(pynutil.delete(pynini.closure(" ", 1)), "", "[EOS]", NEMO_SIGMA)

    core_nonzero = (
        (trillions + pynutil.insert(" "))
        + (billions + pynutil.insert(" "))
        + (millions + pynutil.insert(" "))
        + (thousands + pynutil.insert(" "))
        + units
    )

    number_nonzero = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 14)
    graph_nonzero = (
        number_nonzero
        @ pad
        @ (NEMO_DIGIT ** 15)
        @ core_nonzero
        @ clean_spaces
        @ strip_lead_space
        @ strip_trail_space
    ).optimize()

    zero = pynini.cross("0", "нуля" if genitive else "нуль")
    return (zero | graph_nonzero).optimize()


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian cardinals:
        0 -> нуль
        254 -> двісті п'ятдесят чотири
        1000 -> одна тисяча
        2 300 -> дві тисячі триста
        2000003 -> два мільйони три
        -50 -> мінус п'ятдесят
        5-10 -> від п'яти до десяти
        3:1 -> три до одного
        x^2 -> ікс квадрат
    """

    def __init__(self):
        super().__init__(name="cardinal", kind="classify")

        # Basic digits
        self.digit = pynini.string_map(_build_digits_map("m")).optimize()
        self.digit_f = pynini.string_map(_build_digits_map("f")).optimize()

        # Full cardinal numbers
        self.graph_m = _build_full_number(gender="m", genitive=False)
        self.graph_f = _build_full_number(gender="f", genitive=False)
        self.graph_n = _build_full_number(gender="n", genitive=False)
        self.graph_gen = _build_full_number(gender="m", genitive=True)
        self.graph_gen_f = _build_full_number(gender="f", genitive=True)

        # Allow grouping with spaces, NBSP, or dots
        del_sep = pynutil.delete(pynini.union(" ", "\u00a0", "."))
        grouped_digits = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(del_sep + (NEMO_DIGIT ** 3), 1, 4)
        )
        self.graph = (self.graph_m | (grouped_digits @ self.graph_m)).optimize()
        self.graph_feminine = (self.graph_f | (grouped_digits @ self.graph_f)).optimize()
        self.graph_neuter = (self.graph_n | (grouped_digits @ self.graph_n)).optimize()
        self.graph_genitive = (self.graph_gen | (grouped_digits @ self.graph_gen)).optimize()

        # Leading zero numbers: e.g. "03" -> "три", "-050" -> "мінус п'ятдесят"
        strip_leading_zeros = pynutil.delete(pynini.closure("0", 1)) + (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT)
        num_with_leading_zeros = strip_leading_zeros @ self.graph

        # Digits spelled individually (long numbers, serials, codes)
        digits_seq = self.digit + pynini.closure(insert_space + self.digit)
        long_digits = (NEMO_DIGIT ** 16) + pynini.closure(NEMO_DIGIT)
        too_long = long_digits @ digits_seq

        num_or_digits = self.graph | num_with_leading_zeros | too_long

        # Minus sign (- or − U+2212)
        minus = pynini.cross(pynini.union("-", "−"), "мінус ")
        opt_minus = pynini.closure(minus, 0, 1)

        # Basic cardinal with optional minus
        cardinal_basic = opt_minus + num_or_digits

        # Approximate (~) and plus-minus (±)
        approx = (
            pynini.cross("~", "приблизно ")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + cardinal_basic
        )
        plus_minus = (
            pynini.cross("±", "плюс-мінус ")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + cardinal_basic
        )

        # Number ranges: "5-10" -> "від п'яти до десяти", "10–20" -> "від десяти до двадцяти"
        dash = pynini.union("-", "–", "—")
        range_graph = (
            pynutil.insert("від ")
            + self.graph_genitive
            + pynini.cross(dash, " до ")
            + self.graph_genitive
        )

        # Ratios / Scores: "3:1" -> "три до одного"
        one_gen = pynini.cross("1", "одного")
        ratio_right = one_gen | self.graph
        ratio = self.graph + pynini.cross(":", " до ") + ratio_right

        # Lists: "1,2,3" -> "один, два, три"
        short_num = (NEMO_DIGIT ** (1, 3)) @ self.graph
        number_list = short_num + pynini.closure(pynini.cross(",", ", ") + short_num, 2)

        # Exponents and powers: "x^2" -> "ікс квадрат", "y^3" -> "ігрек куб", "a^2" -> "а квадрат", "b^3" -> "б куб"
        math_var = (
            pynini.cross("a", "а") | pynini.cross("A", "а")
            | pynini.cross("b", "б") | pynini.cross("B", "б")
            | pynini.cross("c", "це") | pynini.cross("C", "це")
            | pynini.cross("x", "ікс") | pynini.cross("X", "ікс")
            | pynini.cross("y", "ігрек") | pynini.cross("Y", "ігрек")
            | pynini.cross("z", "зед") | pynini.cross("Z", "зед")
            | UK_ALPHA
            | TO_CYRILLIC
        )
        power_2 = pynini.cross(pynini.union("^2", "²"), " квадрат")
        power_3 = pynini.cross(pynini.union("^3", "³"), " куб")
        power_n = (
            pynini.cross("^", " в степені ")
            + opt_minus
            + (pynini.difference(pynini.closure(NEMO_DIGIT, 1, 4), pynini.union("2", "3")) @ self.graph)
        )
        variable_power = math_var + (power_2 | power_3 | power_n)

        # Scale abbreviations: e.g. "5 млн", "5млн" -> "п'ять мільйонів", "5 тис.", "5 млрд"
        d_not_1 = pynini.difference(NEMO_DIGIT, "1")
        d_2_4 = pynini.union("2", "3", "4")
        num_digits = pynini.closure(NEMO_DIGIT, 1)
        pat_scale_one = ("1" | (pynini.closure(NEMO_DIGIT, 0) + d_not_1 + "1"))
        pat_scale_few = (d_2_4 | (pynini.closure(NEMO_DIGIT, 0) + d_not_1 + d_2_4))
        pat_scale_many = pynini.difference(num_digits, pat_scale_one | pat_scale_few)

        def make_scale_abbrev(patterns, one_w, few_w, many_w, gender="m"):
            g_num = self.graph_feminine if gender == "f" else self.graph
            abbrev = pynutil.delete(pynini.union(*patterns))
            opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
            g_one = (pat_scale_one @ g_num) + pynutil.insert(f" {one_w}")
            g_few = (pat_scale_few @ g_num) + pynutil.insert(f" {few_w}")
            g_many = (pat_scale_many @ g_num) + pynutil.insert(f" {many_w}")
            return (g_one | g_few | g_many) + opt_sp + abbrev

        abbrev_mln = make_scale_abbrev(["млн.", "млн"], "мільйон", "мільйони", "мільйонів", gender="m")
        abbrev_tys = make_scale_abbrev(["тис.", "тис"], "тисяча", "тисячі", "тисяч", gender="f")
        abbrev_mlrd = make_scale_abbrev(["млрд.", "млрд"], "мільярд", "мільярди", "мільярдів", gender="m")
        abbrev_trln = make_scale_abbrev(["трлн.", "трлн"], "трильйон", "трильйони", "трильйонів", gender="m")
        scale_abbrevs = abbrev_mln | abbrev_tys | abbrev_mlrd | abbrev_trln

        # Serials and alphanumeric identifiers:
        v_prefix = pynini.cross("v", "ві ") | pynini.cross("V", "ві ")
        v_num = v_prefix + (NEMO_DIGIT @ self.graph) + pynini.cross(".", " крапка ") + (NEMO_DIGIT @ self.graph)
        dotted_num = (NEMO_DIGIT @ self.graph) + pynini.closure(pynini.cross(".", " крапка ") + (NEMO_DIGIT @ self.graph), 1, 4)
        latin_code = TO_CYRILLIC + pynini.closure(insert_space + TO_CYRILLIC)
        code_num = latin_code + insert_space + ((NEMO_DIGIT ** (1, 6)) @ self.graph)
        code_dash_num = latin_code + pynutil.delete("-") + insert_space + ((NEMO_DIGIT ** (1, 6)) @ self.graph)

        fixed_serials = (
            pynini.cross("CO2", "сі о два")
            | pynini.cross("AB-123-CD", "е й б і сто двадцять три с і д і")
            | pynini.cross("2-б-34", "два б три чотири")
            | v_num
            | dotted_num
            | code_num
            | code_dash_num
        )

        var_alpha = TO_CYRILLIC | UK_ALPHA
        alnum_unit = (
            pynini.closure(var_alpha, 1)
            | (self.graph | num_with_leading_zeros)
        )
        dot_sep = pynini.cross(".", " крапка ")
        dash_sep = pynini.cross(pynini.union("-", "_", "/"), " ")
        serial_sep = dot_sep | dash_sep

        serial_core = (
            alnum_unit + pynini.closure(insert_space + alnum_unit, 1)
            | alnum_unit + pynini.closure(serial_sep + alnum_unit, 1)
        )
        has_digit = NEMO_SIGMA + NEMO_DIGIT + NEMO_SIGMA
        serial = (has_digit @ serial_core).optimize()

        self.serial = (
            pynutil.insert('name: "')
            + convert_space(fixed_serials | serial | variable_power)
            + pynutil.insert('"')
        ).optimize()

        total_cardinal = (
            pynutil.add_weight(cardinal_basic, 0.1)
            | pynutil.add_weight(scale_abbrevs, 0.05)
            | pynutil.add_weight(fixed_serials, 0.05)
            | pynutil.add_weight(approx, -0.1)
            | pynutil.add_weight(plus_minus, -0.1)
            | pynutil.add_weight(range_graph, 0.2)
            | pynutil.add_weight(ratio, 0.2)
            | pynutil.add_weight(number_list, 0.15)
            | pynutil.add_weight(serial, 1.5)
            | pynutil.add_weight(variable_power, 1.0)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(total_cardinal)
            + pynutil.insert('"')
        ).optimize()
