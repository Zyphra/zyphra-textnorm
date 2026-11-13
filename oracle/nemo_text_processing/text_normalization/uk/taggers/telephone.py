# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian telephone numbers:
        +1 555 123 4567 -> плюс один п'ятсот п'ятдесят п'ять сто двадцять три сорок п'ять шістдесят сім
    """

    def __init__(self, cardinal: CardinalFst = None):
        super().__init__(name="telephone", kind="classify")
        cardinal = cardinal or CardinalFst()

        g_num = cardinal.graph
        plus = pynini.cross("+", "плюс ")
        del_sep = pynutil.delete(pynini.union(" ", "-", "(", ")"))

        d1 = NEMO_DIGIT @ g_num
        d2 = (NEMO_DIGIT ** 2) @ g_num
        d3 = (NEMO_DIGIT ** 3) @ g_num
        d4 = (NEMO_DIGIT ** 4) @ g_num

        part = d1 | d2 | d3

        opt_sep = pynini.closure(del_sep, 0, 1)
        tail_4 = d2 + opt_sep + insert_space + d2

        tel_us = (
            plus + d1 + del_sep + insert_space
            + d3 + del_sep + insert_space
            + d3 + del_sep + insert_space
            + tail_4
        )

        tel_ua = (
            plus + d3 + del_sep + insert_space
            + d2 + del_sep + insert_space
            + d3 + del_sep + insert_space
            + tail_4
        )

        tel_general = (
            pynini.closure(plus, 0, 1)
            + part
            + pynini.closure(del_sep + insert_space + part, 2, 6)
        )

        phone = (
            pynutil.add_weight(tel_us, 0.01)
            | pynutil.add_weight(tel_ua, 0.01)
            | pynutil.add_weight(tel_general, 0.1)
            | pynutil.add_weight(international_telephone(d1, "плюс"), 0.5)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(phone)
            + pynutil.insert('"')
        ).optimize()
