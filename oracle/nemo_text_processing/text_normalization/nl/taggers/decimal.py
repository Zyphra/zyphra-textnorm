# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import (
    NEMO_MINUS,
    wrap_name,
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Dutch decimal numbers.
    Handles:
    - Dutch comma decimal: 1,5 -> een komma vijf
    - 3,14 -> drie komma veertien
    - 0,05 -> nul komma nul vijf
    - -0,25 -> min nul komma vijfentwintig
    - ASCII dot decimal: 3.5 -> drie komma vijf
    - High precision: 3,1415 -> drie komma een vier een vijf
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        # Decimal separator is comma, with period as ASCII fallback
        dec_sep = pynini.cross(",", " komma ") | pynutil.add_weight(pynini.cross(".", " komma "), 0.1)

        # Integer part
        int_part = cardinal.cardinal_numbers

        # Fractional part:
        # 1 digit:
        frac_1 = cardinal.digit
        # 2 digits (e.g. 14 -> veertien, 05 -> nul vijf, 95 -> vijfennegentig):
        frac_2 = (
            pynini.cross("0", "nul ") + cardinal.digit
            | cardinal.nums_1_to_99
        )
        # 3+ digits: digit by digit
        frac_digits = cardinal.digit + pynini.closure(insert_space + cardinal.digit, 1)

        frac_part = (
            pynutil.add_weight(frac_2, 0.98)
            | pynutil.add_weight(frac_1, 1.0)
            | pynutil.add_weight(frac_digits, 1.05)
        )

        pos_decimal = int_part + dec_sep + frac_part
        neg_decimal = pynini.cross(NEMO_MINUS, "min ") + pos_decimal

        self.spoken_decimal = (
            pynutil.add_weight(neg_decimal, 0.99)
            | pynutil.add_weight(pos_decimal, 1.0)
        ).optimize()

        self.fst = wrap_name(self.spoken_decimal)
