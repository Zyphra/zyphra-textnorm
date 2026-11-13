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


VULGAR_FRACTIONS = [
    ("½", "одна друга"),
    ("⅓", "одна третя"),
    ("⅔", "дві третіх"),
    ("¼", "одна четверта"),
    ("¾", "три четвертих"),
    ("⅕", "одна п'ята"),
    ("⅖", "дві п'ятих"),
    ("⅗", "три п'ятих"),
    ("⅘", "чотири п'ятих"),
    ("⅙", "одна шоста"),
    ("⅚", "п'ять шостих"),
    ("⅛", "одна восьма"),
    ("⅜", "три восьмих"),
    ("⅝", "п'ять восьмих"),
    ("⅞", "сім восьмих"),
    ("⅒", "одна десята"),
]

DENOM_SINGULAR = [
    ("2", "друга"),
    ("3", "третя"),
    ("4", "четверта"),
    ("5", "п'ята"),
    ("6", "шоста"),
    ("7", "сьома"),
    ("8", "восьма"),
    ("9", "дев'ята"),
    ("10", "десята"),
    ("12", "дванадцята"),
    ("100", "сота"),
    ("250", "двісті п'ятдесята"),
    ("1000", "тисячна"),
]

DENOM_PLURAL = [
    ("2", "других"),
    ("3", "третіх"),
    ("4", "четвертих"),
    ("5", "п'ятих"),
    ("6", "шостих"),
    ("7", "сьомих"),
    ("8", "восьмих"),
    ("9", "дев'ятих"),
    ("10", "десятих"),
    ("12", "дванадцятих"),
    ("100", "сотих"),
    ("250", "двісті п'ятдесятих"),
    ("1000", "тисячних"),
]


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian fractions:
        1/2 -> одна друга
        3/4 -> три четвертих
        2 1/2 -> дві цілих одна друга
        1 1/3 -> одна ціла одна третя
        -1/2 -> мінус одна друга
        -2½ -> мінус дві цілих одна друга
        -3 3/4 -> мінус три цілих три четвертих
        ½ -> одна друга
        ⅓ -> одна третя
    """

    def __init__(self, cardinal: CardinalFst = None):
        super().__init__(name="fraction", kind="classify")
        cardinal = cardinal or CardinalFst()

        g_f = cardinal.graph_feminine
        d_not_1 = pynini.difference(NEMO_DIGIT, "1")

        # Numerator ending in 1 (not 11): e.g. 1, 21, 101
        num_digits = pynini.closure(NEMO_DIGIT, 1)
        pat_num_one = ("1" | (pynini.closure(NEMO_DIGIT, 0) + d_not_1 + "1"))
        pat_num_other = pynini.difference(num_digits, pat_num_one)

        numerator_one = pat_num_one @ g_f
        numerator_other = pat_num_other @ g_f

        slash = pynutil.delete("/")
        denom_sg = pynini.string_map(DENOM_SINGULAR)
        denom_pl = pynini.string_map(DENOM_PLURAL)

        simple_fraction = (
            (numerator_one + slash + insert_space + denom_sg)
            | (numerator_other + slash + insert_space + denom_pl)
        )

        vulgar_fraction = pynini.string_map(VULGAR_FRACTIONS)

        any_fraction = simple_fraction | vulgar_fraction

        # Whole part for mixed fractions: e.g. "2 1/2", "1 1/3", "2½"
        pat_whole_one = ("1" | (pynini.closure(NEMO_DIGIT, 0) + d_not_1 + "1"))
        pat_whole_other = pynini.difference(num_digits, pat_whole_one)

        whole_one = (pat_whole_one @ g_f) + pynutil.insert(" ціла ")
        whole_other = (pat_whole_other @ g_f) + pynutil.insert(" цілих ")
        whole_part = whole_one | whole_other

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        # Slashed fractions like 21/100 must have a space after whole part (e.g. "2 1/2"); otherwise 21/100 is simple fraction
        mixed_fraction = (whole_part + pynutil.delete(" ") + simple_fraction) | (whole_part + opt_space + vulgar_fraction)

        minus = pynini.cross(pynini.union("-", "−"), "мінус ")
        opt_minus = pynini.closure(minus, 0, 1)

        total_fraction = (
            opt_minus + (mixed_fraction | any_fraction)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(total_fraction)
            + pynutil.insert('"')
        ).optimize()
