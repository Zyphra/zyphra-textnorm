# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst


ORD_DIGITS = {
    "m": [
        ("0", "нульовий"), ("1", "перший"), ("2", "другий"), ("3", "третій"),
        ("4", "четвертий"), ("5", "п'ятий"), ("6", "шостий"), ("7", "сьомий"),
        ("8", "восьмий"), ("9", "дев'ятий"),
    ],
    "f": [
        ("0", "нульова"), ("1", "перша"), ("2", "друга"), ("3", "третя"),
        ("4", "четверта"), ("5", "п'ята"), ("6", "шоста"), ("7", "сьома"),
        ("8", "восьма"), ("9", "дев'ята"),
    ],
    "n": [
        ("0", "нульове"), ("1", "перше"), ("2", "друге"), ("3", "третє"),
        ("4", "четверте"), ("5", "п'яте"), ("6", "шосте"), ("7", "сьоме"),
        ("8", "восьме"), ("9", "дев'яте"),
    ],
    "gen": [
        ("0", "нульового"), ("1", "першого"), ("2", "другого"), ("3", "третього"),
        ("4", "четвертого"), ("5", "п'ятого"), ("6", "шостого"), ("7", "сьомого"),
        ("8", "восьмого"), ("9", "дев'ятого"),
    ],
    "loc": [
        ("0", "нульовому"), ("1", "першому"), ("2", "другому"), ("3", "третьому"),
        ("4", "четвертому"), ("5", "п'ятому"), ("6", "шостому"), ("7", "сьомому"),
        ("8", "восьмому"), ("9", "дев'ятому"),
    ],
    "plural": [
        ("0", "нульові"), ("1", "перші"), ("2", "другі"), ("3", "треті"),
        ("4", "четверті"), ("5", "п'яті"), ("6", "шості"), ("7", "сьомі"),
        ("8", "восьмі"), ("9", "дев'яті"),
    ],
    "plural_gen": [
        ("0", "нульових"), ("1", "перших"), ("2", "других"), ("3", "третіх"),
        ("4", "четвертих"), ("5", "п'ятих"), ("6", "шостих"), ("7", "сьомих"),
        ("8", "восьмих"), ("9", "дев'ятих"),
    ],
}

ORD_TEENS = {
    "m": [
        ("10", "десятий"), ("11", "одинадцятий"), ("12", "дванадцятий"), ("13", "тринадцятий"),
        ("14", "чотирнадцятий"), ("15", "п'ятнадцятий"), ("16", "шістнадцятий"),
        ("17", "сімнадцятий"), ("18", "вісімнадцятий"), ("19", "дев'ятнадцятий"),
    ],
    "f": [
        ("10", "десята"), ("11", "одинадцята"), ("12", "дванадцята"), ("13", "тринадцята"),
        ("14", "чотирнадцята"), ("15", "п'ятнадцята"), ("16", "шістнадцята"),
        ("17", "сімнадцята"), ("18", "вісімнадцята"), ("19", "дев'ятнадцята"),
    ],
    "n": [
        ("10", "десяте"), ("11", "одинадцяте"), ("12", "дванадцяте"), ("13", "тринадцяте"),
        ("14", "чотирнадцяте"), ("15", "п'ятнадцяте"), ("16", "шістнадцяте"),
        ("17", "сімнадцяте"), ("18", "вісімнадцяте"), ("19", "дев'ятнадцяте"),
    ],
    "gen": [
        ("10", "десятого"), ("11", "одинадцятого"), ("12", "дванадцятого"), ("13", "тринадцятого"),
        ("14", "чотирнадцятого"), ("15", "п'ятнадцятого"), ("16", "шістнадцятого"),
        ("17", "сімнадцятого"), ("18", "вісімнадцятого"), ("19", "дев'ятнадцятого"),
    ],
    "loc": [
        ("10", "десятому"), ("11", "одинадцятому"), ("12", "дванадцятому"), ("13", "тринадцятому"),
        ("14", "чотирнадцятому"), ("15", "п'ятнадцятому"), ("16", "шістнадцятому"),
        ("17", "сімнадцятому"), ("18", "вісімнадцятому"), ("19", "дев'ятнадцятому"),
    ],
    "plural": [
        ("10", "десяті"), ("11", "одинадцяті"), ("12", "дванадцяті"), ("13", "тринадцяті"),
        ("14", "чотирнадцяті"), ("15", "п'ятнадцяті"), ("16", "шістнадцяті"),
        ("17", "сімнадцяті"), ("18", "вісімнадцяті"), ("19", "дев'ятнадцяті"),
    ],
    "plural_gen": [
        ("10", "десятих"), ("11", "одинадцятих"), ("12", "дванадцятих"), ("13", "тринадцятих"),
        ("14", "чотирнадцятих"), ("15", "п'ятнадцятих"), ("16", "шістнадцятих"),
        ("17", "сімнадцятих"), ("18", "вісімнадцятих"), ("19", "дев'ятнадцятих"),
    ],
}

ORD_TIES = {
    "m": [
        ("20", "двадцятий"), ("30", "тридцятий"), ("40", "сороковий"), ("50", "п'ятдесятий"),
        ("60", "шістдесятий"), ("70", "сімдесятий"), ("80", "вісімдесятий"), ("90", "дев'яностий"),
    ],
    "f": [
        ("20", "двадцята"), ("30", "тридцята"), ("40", "сорокова"), ("50", "п'ятдесята"),
        ("60", "шістдесята"), ("70", "сімдесята"), ("80", "вісімдесята"), ("90", "дев'яноста"),
    ],
    "n": [
        ("20", "двадцяте"), ("30", "тридцяте"), ("40", "сорокове"), ("50", "п'ятдесяте"),
        ("60", "шістдесяте"), ("70", "сімдесяте"), ("80", "вісімдесяте"), ("90", "дев'яносте"),
    ],
    "gen": [
        ("20", "двадцятого"), ("30", "тридцятого"), ("40", "сорокового"), ("50", "п'ятдесятого"),
        ("60", "шістдесятого"), ("70", "сімдесятого"), ("80", "вісімдесятого"), ("90", "дев'яностого"),
    ],
    "loc": [
        ("20", "двадцятому"), ("30", "тридцятому"), ("40", "сороковому"), ("50", "п'ятдесятому"),
        ("60", "шістдесятому"), ("70", "сімдесятому"), ("80", "вісімдесятому"), ("90", "дев'яностому"),
    ],
    "plural": [
        ("20", "двадцяті"), ("30", "тридцяті"), ("40", "сорокові"), ("50", "п'ятдесяті"),
        ("60", "шістдесяті"), ("70", "сімдесяті"), ("80", "вісімдесяті"), ("90", "дев'яності"),
    ],
    "plural_gen": [
        ("20", "двадцятих"), ("30", "тридцятих"), ("40", "сорокових"), ("50", "п'ятдесятих"),
        ("60", "шістдесятих"), ("70", "сімдесятих"), ("80", "вісімдесятих"), ("90", "дев'яностих"),
    ],
}

ORD_HUNDREDS = {
    "m": [
        ("100", "сотий"), ("200", "двохсотий"), ("300", "трьохсотий"), ("400", "чотирьохсотий"),
        ("500", "п'ятисотий"), ("600", "шестисотий"), ("700", "семисотий"), ("800", "восьмисотий"),
        ("900", "дев'ятисотий"),
    ],
    "f": [
        ("100", "сота"), ("200", "двохсота"), ("300", "трьохсота"), ("400", "чотирьохсота"),
        ("500", "п'ятисота"), ("600", "шестисота"), ("700", "семисота"), ("800", "восьмисота"),
        ("900", "дев'ятисота"),
    ],
    "n": [
        ("100", "соте"), ("200", "двохсоте"), ("300", "трьохсоте"), ("400", "чотирьохсоте"),
        ("500", "п'ятисоте"), ("600", "шестисоте"), ("700", "семисоте"), ("800", "восьмисоте"),
        ("900", "дев'ятисоте"),
    ],
    "gen": [
        ("100", "сотого"), ("200", "двохсотого"), ("300", "трьохсотого"), ("400", "чотирьохсотого"),
        ("500", "п'ятисотого"), ("600", "шестисотого"), ("700", "семисотого"), ("800", "восьмисотого"),
        ("900", "дев'ятисотого"),
    ],
    "loc": [
        ("100", "сотому"), ("200", "двохсотому"), ("300", "трьохсотому"), ("400", "чотирьохсотому"),
        ("500", "п'ятисотому"), ("600", "шестисотому"), ("700", "семисотому"), ("800", "восьмисотому"),
        ("900", "дев'ятисотому"),
    ],
    "plural": [
        ("100", "соті"), ("200", "двохсоті"), ("300", "трьохсоті"), ("400", "чотирьохсоті"),
        ("500", "п'ятисоті"), ("600", "шестисоті"), ("700", "семисоті"), ("800", "восьмисоті"),
        ("900", "дев'ятисоті"),
    ],
    "plural_gen": [
        ("100", "сотих"), ("200", "двохсотих"), ("300", "трьохсотих"), ("400", "чотирьохсотих"),
        ("500", "п'ятисотих"), ("600", "шестисотих"), ("700", "семисотих"), ("800", "восьмисотих"),
        ("900", "дев'ятисотих"),
    ],
}


def _build_ordinal_form(cardinal: CardinalFst, form: str = "m"):
    """
    Builds an ordinal transducer for numbers 1 to 9999 for a given grammatical form:
    In compound ordinals, only the last component is ordinal; the preceding components are cardinal!
    """
    digits_m = ORD_DIGITS[form]
    teens_m = ORD_TEENS[form]
    ties_m = ORD_TIES[form]
    hund_m = ORD_HUNDREDS[form]

    d_one_to_nine = pynini.union(*[pynini.cross(k, v) for k, v in digits_m[1:]])
    teens = pynini.union(*[pynini.cross(k, v) for k, v in teens_m])
    ties_exact = pynini.union(*[pynini.cross(k, v) for k, v in ties_m])
    hundreds_exact = pynini.union(*[pynini.cross(k, v) for k, v in hund_m])

    # Ties compound: 21..99 -> ties_cardinal + " " + ordinal_digit
    # We can get ties_cardinal from cardinal.py
    ties_card = [
        ("2", "двадцять"), ("3", "тридцять"), ("4", "сорок"), ("5", "п'ятдесят"),
        ("6", "шістдесят"), ("7", "сімдесят"), ("8", "вісімдесят"), ("9", "дев'яносто"),
    ]
    ties_c = pynini.union(*[pynini.cross(k, v) for k, v in ties_card])
    ties_compound = ties_c + insert_space + d_one_to_nine

    # 1..99 ordinals
    ord_1_99 = d_one_to_nine | teens | ties_exact | ties_compound

    # Hundreds compound: 100..999
    hund_card = [
        ("1", "сто"), ("2", "двісті"), ("3", "триста"), ("4", "чотириста"),
        ("5", "п'ятсот"), ("6", "шістсот"), ("7", "сімсот"), ("8", "вісімсот"),
        ("9", "дев'ятсот"),
    ]
    hund_c = pynini.union(*[pynini.cross(k, v) for k, v in hund_card])
    hund_remainder = (
        (pynutil.delete("0") + d_one_to_nine)
        | teens
        | ties_exact
        | ties_compound
    )
    hund_compound = hund_c + insert_space + hund_remainder

    ord_1_999 = ord_1_99 | hundreds_exact | hund_compound

    # Thousands: 1000..9999
    # e.g. 1000 -> тисячний, 2000 -> двохсотий / двохтисячний
    # 1999 -> тисяча дев'ятсот дев'яносто дев'ятий
    # 2024 -> дві тисячі двадцять четвертий
    suff_th = "тисячний" if form == "m" else (
        "тисячна" if form == "f" else (
            "тисячне" if form == "n" else (
                "тисячного" if form == "gen" else (
                    "тисячному" if form == "loc" else (
                        "тисячні" if form == "plural" else "тисячних"
                    )
                )
            )
        )
    )
    th_exact_1000 = pynini.cross("1000", suff_th)
    th_exact_multi = (
        (pynini.cross("2", "дво") | pynini.cross("2", "двох") | pynini.cross("3", "трьох") | pynini.cross("4", "чотирьох") | pynini.cross("5", "п'яти"))
        + pynutil.delete("000")
        + pynutil.insert(suff_th)
    )

    # 1001..9999 compound
    # 1xxx:
    th_1 = pynini.cross("1", "тисяча") + insert_space + (
        (pynutil.delete("00") + d_one_to_nine)
        | (pynutil.delete("0") + (teens | ties_exact | ties_compound))
        | hund_compound
        | (hundreds_exact)
    )
    # 2xxx..9xxx:
    th_multi_card = (
        (pynini.cross("2", "дві тисячі") | pynini.cross("3", "три тисячі") | pynini.cross("4", "чотири тисячі") | pynini.cross("5", "п'ять тисяч"))
        + insert_space
        + (
            (pynutil.delete("00") + d_one_to_nine)
            | (pynutil.delete("0") + (teens | ties_exact | ties_compound))
            | hund_compound
            | (hundreds_exact)
        )
    )

    return (ord_1_999 | th_exact_1000 | th_exact_multi | th_1 | th_multi_card).optimize()


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian ordinals:
        6-й -> шостий
        2-а -> друга
        2-е -> друге
        2-го -> другого
        84-му -> вісімдесят четвертому
        84-м -> вісімдесят четвертому
        1950-ті -> тисяча дев'ятсот п'ятдесяті
        20-х -> двадцятих
        2020s -> двадцяті роки
    """

    def __init__(self, cardinal: CardinalFst = None):
        super().__init__(name="ordinal", kind="classify")
        cardinal = cardinal or CardinalFst()

        self.ord_m = _build_ordinal_form(cardinal, "m")
        self.ord_f = _build_ordinal_form(cardinal, "f")
        self.ord_n = _build_ordinal_form(cardinal, "n")
        self.ord_gen = _build_ordinal_form(cardinal, "gen")
        self.ord_loc = _build_ordinal_form(cardinal, "loc")
        self.ord_plural = _build_ordinal_form(cardinal, "plural")
        self.ord_plural_gen = _build_ordinal_form(cardinal, "plural_gen")

        # Hyphenated written suffix forms:
        del_hyphen = pynutil.delete(pynini.union("-", "–"))

        # Masculine: -й, -ий
        suff_m = pynini.union("й", "ий")
        graph_suff_m = self.ord_m + del_hyphen + pynutil.delete(suff_m)

        # Feminine: -а, -я, -ша
        suff_f = pynini.union("а", "я", "ша")
        graph_suff_f = self.ord_f + del_hyphen + pynutil.delete(suff_f)

        # Neuter: -е, -є
        suff_n = pynini.union("е", "є")
        graph_suff_n = self.ord_n + del_hyphen + pynutil.delete(suff_n)

        # Genitive: -го, -ого
        suff_gen = pynini.union("го", "ого")
        graph_suff_gen = self.ord_gen + del_hyphen + pynutil.delete(suff_gen)

        # Locative/Dative/Instrumental: -му, -ому, -м, -им
        suff_loc = pynini.union("му", "ому", "м", "им")
        graph_suff_loc = self.ord_loc + del_hyphen + pynutil.delete(suff_loc)

        # Plural / Decades: -ті, -ні, -і, -ї
        suff_plural = pynini.union("ті", "ні", "і", "ї")
        graph_suff_plural = self.ord_plural + del_hyphen + pynutil.delete(suff_plural)

        # Plural genitive: -х, -их
        suff_plural_gen = pynini.union("х", "их")
        graph_suff_plural_gen = self.ord_plural_gen + del_hyphen + pynutil.delete(suff_plural_gen)

        # International decade: "2020s" -> "двадцяті роки", "1990s" -> "дев'яності роки"
        # Must NEVER be read as seconds!
        intl_decade = (
            pynini.cross("1990s", "дев'яності роки")
            | pynini.cross("2000s", "двотисячні роки")
            | pynini.cross("2010s", "дві тисячі десяті роки")
            | pynini.cross("2020s", "двадцяті роки")
            | pynini.cross("2030s", "тридцяті роки")
        )

        all_ordinals = (
            graph_suff_m
            | graph_suff_f
            | graph_suff_n
            | graph_suff_gen
            | graph_suff_loc
            | graph_suff_plural
            | graph_suff_plural_gen
            | intl_decade
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_ordinals)
            + pynutil.insert('"')
        ).optimize()
