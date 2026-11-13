# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.uk.taggers.ordinal import OrdinalFst


ROMAN_TO_ORDINAL_M = [
    ("I", "перший"),
    ("II", "другий"),
    ("III", "третій"),
    ("IV", "четвертий"),
    ("V", "п'ятий"),
    ("VI", "шостий"),
    ("VII", "сьомий"),
    ("VIII", "восьмий"),
    ("IX", "дев'ятий"),
    ("X", "десятий"),
    ("XI", "одинадцятий"),
    ("XII", "дванадцятий"),
    ("XIII", "тринадцятий"),
    ("XIV", "чотирнадцятий"),
    ("XV", "п'ятнадцятий"),
    ("XVI", "шістнадцятий"),
    ("XVII", "сімнадцятий"),
    ("XVIII", "вісімнадцятий"),
    ("XIX", "дев'ятнадцятий"),
    ("XX", "двадцятий"),
    ("XXI", "двадцять перший"),
]

ROMAN_TO_ORDINAL_F = [
    ("I", "перша"),
    ("II", "друга"),
    ("III", "третя"),
    ("IV", "четверта"),
    ("V", "п'ята"),
    ("VI", "шоста"),
    ("VII", "сьома"),
    ("VIII", "восьма"),
    ("IX", "дев'ята"),
    ("X", "десята"),
    ("XI", "одинадцята"),
    ("XII", "дванадцята"),
    ("XIII", "тринадцята"),
    ("XIV", "чотирнадцята"),
    ("XV", "п'ятнадцята"),
    ("XVI", "шістнадцята"),
    ("XVII", "сімнадцята"),
    ("XVIII", "вісімнадцята"),
    ("XIX", "дев'ятнадцята"),
    ("XX", "двадцята"),
    ("XXI", "двадцять перша"),
]

ROMAN_TO_ORDINAL_N = [
    ("I", "перше"),
    ("II", "друге"),
    ("III", "третє"),
    ("IV", "четверте"),
    ("V", "п'яте"),
    ("VI", "шосте"),
    ("VII", "сьоме"),
    ("VIII", "восьме"),
    ("IX", "дев'яте"),
    ("X", "десяте"),
    ("XI", "одинадцяте"),
    ("XII", "дванадцяте"),
    ("XIII", "тринадцяте"),
    ("XIV", "чотирнадцяте"),
    ("XV", "п'ятнадцяте"),
    ("XVI", "шістнадцяте"),
    ("XVII", "сімнадцяте"),
    ("XVIII", "вісімнадцяте"),
    ("XIX", "дев'ятнадцяте"),
    ("XX", "двадцяте"),
    ("XXI", "двадцять перше"),
]


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying contextual Roman numerals:
        Глава IV -> Глава четверта
        Розділ IV -> Розділ четвертий
        XXI століття -> двадцять перше століття
        XXI ст. -> двадцять перше століття
        XL -> ікс ель
        CD -> сі ді
        MIX -> ем ай ікс
    """

    def __init__(self, cardinal: CardinalFst = None, ordinal: OrdinalFst = None):
        super().__init__(name="roman", kind="classify")

        rom_m = pynini.string_map(ROMAN_TO_ORDINAL_M)
        rom_f = pynini.string_map(ROMAN_TO_ORDINAL_F)
        rom_n = pynini.string_map(ROMAN_TO_ORDINAL_N)

        # Context words triggering feminine ordinals: "Глава", "Частина", "глава", "частина"
        ctx_f = (
            pynini.cross("Глава", "Глава")
            | pynini.cross("глава", "глава")
            | pynini.cross("Частина", "Частина")
            | pynini.cross("частина", "частина")
        )
        roman_chap_f = ctx_f + pynutil.delete(" ") + pynutil.insert(" ") + rom_f

        # Context words triggering masculine ordinals: "Розділ", "розділ", "Том", "том"
        ctx_m = (
            pynini.cross("Розділ", "Розділ")
            | pynini.cross("розділ", "розділ")
            | pynini.cross("Том", "Том")
            | pynini.cross("том", "том")
        )
        roman_chap_m = ctx_m + pynutil.delete(" ") + pynutil.insert(" ") + rom_m

        # Context words triggering neuter ordinals before or after: "століття", "ст.", "век"
        ctx_century = (
            pynini.cross("століття", "століття")
            | pynini.cross("ст.", "століття")
            | pynini.cross("ст", "століття")
            | pynini.cross("век", "століття")
        )
        roman_century = rom_n + pynutil.delete(" ") + pynutil.insert(" ") + ctx_century

        # Monarch names: "Петро I" -> "Петро перший", "Володимир I" -> "Володимир перший"
        monarch = (
            pynini.cross("Петро", "Петро")
            | pynini.cross("Володимир", "Володимир")
            | pynini.cross("Карл", "Карл")
            | pynini.cross("Людовик", "Людовик")
        )
        roman_monarch = monarch + pynutil.delete(" ") + pynutil.insert(" ") + rom_m

        # Safety control words (MUST NOT be read as Roman numbers!):
        # "XL", "CD", "MIX"
        ctrl_xl = pynini.cross("XL", "ікс ель")
        ctrl_cd = pynini.cross("CD", "сі ді")
        ctrl_mix = pynini.cross("MIX", "ем ай ікс")
        safety_controls = ctrl_xl | ctrl_cd | ctrl_mix

        all_roman = (
            pynutil.add_weight(safety_controls, 0.01)
            | pynutil.add_weight(roman_chap_f, 0.05)
            | pynutil.add_weight(roman_chap_m, 0.05)
            | pynutil.add_weight(roman_century, 0.05)
            | pynutil.add_weight(roman_monarch, 0.05)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_roman)
            + pynutil.insert('"')
        ).optimize()
