# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Dutch telephone numbers.
    Handles:
    - International format: +44 20 7946 0958, +1-800-555-0199
    - Local formats: (021) 555-1234, 06-12345678
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digit = cardinal.digit

        sep = pynini.union("-", " ", ".", "/")
        del_sep = pynutil.delete(sep)

        del_open_paren = pynutil.delete("(")
        del_close_paren = pynutil.delete(")") + pynini.closure(del_sep, 0, 1)

        plus = pynini.cross("+", "plus ")

        # 800 special handling in 1-800 numbers
        eight_hundred = pynini.cross("800", "achthonderd")

        part_digit = digit + pynini.closure(insert_space + digit, 0, 3)
        part = eight_hundred | part_digit

        # +Country ...
        intl_phone = (
            plus
            + digit + pynini.closure(insert_space + digit, 0, 2)
            + del_sep
            + part
            + pynini.closure(insert_space + del_sep + part, 1, 4)
        )

        # (Area) ...
        parens_phone = (
            del_open_paren
            + digit + pynini.closure(insert_space + digit, 1, 3)
            + del_close_paren
            + insert_space
            + part
            + pynini.closure(insert_space + del_sep + part, 1, 3)
        )

        # General dashed: 06-12345678 or 555-0199
        dashed_phone = (
            digit + pynini.closure(insert_space + digit, 1, 3)
            + del_sep
            + insert_space
            + digit + pynini.closure(insert_space + digit, 2, 7)
        )

        self.spoken_telephone = (
            pynutil.add_weight(intl_phone, 0.95)
            | pynutil.add_weight(parens_phone, 0.96)
            | pynutil.add_weight(dashed_phone, 0.98)
            | pynutil.add_weight(international_telephone(digit, "plus"), 0.90)
        ).optimize()

        self.fst = wrap_name(self.spoken_telephone)
