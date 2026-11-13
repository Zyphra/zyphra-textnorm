# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
    delete_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import (
    NEMO_MINUS,
    wrap_name,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Dutch fractions.
    Handles:
    - Unicode vulgar fractions: ½ -> een half, ⅓ -> een derde, ¼ -> een kwart, ¾ -> drie kwart, etc.
    - Slash fractions: 1/2 -> een half, 3/4 -> drie kwart, 5/8 -> vijf achtste
    - Mixed fractions: 2 1/2, 2½ -> twee en een half, 3 1/4 -> drie en een kwart
    - Negative fractions: -1/2 -> min een half, -2½ -> min twee en een half
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        # Unicode vulgar fractions
        vulgar_pairs = [
            ("½", "een half"),
            ("⅓", "een derde"),
            ("⅔", "twee derde"),
            ("¼", "een kwart"),
            ("¾", "drie kwart"),
            ("⅕", "een vijfde"),
            ("⅖", "twee vijfde"),
            ("⅗", "drie vijfde"),
            ("⅘", "vier vijfde"),
            ("⅙", "een zesde"),
            ("⅚", "vijf zesde"),
            ("⅛", "een achtste"),
            ("⅜", "drie achtste"),
            ("⅝", "vijf achtste"),
            ("⅞", "zeven achtste"),
            ("⅑", "een negende"),
            ("⅒", "een tiende"),
        ]
        vulgar_fst = pynini.string_map(vulgar_pairs).optimize()

        # Denominator mapping for slash fractions
        denom_pairs = [
            ("2", "half"),
            ("3", "derde"),
            ("4", "kwart"),
            ("5", "vijfde"),
            ("6", "zesde"),
            ("7", "zevende"),
            ("8", "achtste"),
            ("9", "negende"),
            ("10", "tiende"),
            ("12", "twaalfde"),
            ("16", "zestiende"),
            ("20", "twintigste"),
            ("100", "honderdste"),
        ]
        denom_map = pynini.string_map(denom_pairs).optimize()

        # Slash fractions: "1/2" -> "een half", "3/4" -> "drie kwart", "5/8" -> "vijf achtste"
        slash_half = pynini.cross("1/2", "een half")
        slash_quarter = pynini.cross("1/4", "een kwart")
        slash_three_quarters = pynini.cross("3/4", "drie kwart")

        slash_gen = (
            cardinal.nums_1_to_99
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + denom_map
        )

        all_fractions = (
            vulgar_fst
            | slash_half
            | slash_quarter
            | slash_three_quarters
            | slash_gen
        ).optimize()

        # Mixed fractions: integer + fraction
        # e.g. "2 1/2", "2½", "3 1/4" -> "twee en een half", "drie en een kwart"
        mixed_space = (
            cardinal.cardinal_numbers
            + pynutil.delete(" ")
            + pynutil.insert(" en ")
            + (all_fractions | vulgar_fst)
        )
        mixed_glued = (
            cardinal.cardinal_numbers
            + pynutil.insert(" en ")
            + vulgar_fst
        )
        mixed = mixed_space | mixed_glued

        # Negatives
        neg_frac = pynini.cross(NEMO_MINUS, "min ") + (mixed | all_fractions)

        self.spoken_fraction = (
            pynutil.add_weight(neg_frac, 0.98)
            | pynutil.add_weight(mixed, 0.99)
            | pynutil.add_weight(all_fractions, 1.0)
        ).optimize()

        self.fst = wrap_name(self.spoken_fraction)
