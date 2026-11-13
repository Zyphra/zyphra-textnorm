# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Dutch Roman numerals in context.
    Prevents false positives like XL, MIX, CD, Section C, Part L.
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_map = [
            ("I", "een", "eerste"),
            ("II", "twee", "tweede"),
            ("III", "drie", "derde"),
            ("IV", "vier", "vierde"),
            ("V", "vijf", "vijfde"),
            ("VI", "zes", "zesde"),
            ("VII", "zeven", "zevende"),
            ("VIII", "acht", "achtste"),
            ("IX", "negen", "negende"),
            ("X", "tien", "tiende"),
            ("XI", "elf", "elfde"),
            ("XII", "twaalf", "twaalfde"),
            ("XIII", "dertien", "dertiende"),
            ("XIV", "veertien", "veertiende"),
            ("XV", "vijftien", "vijftiende"),
            ("XVI", "zestien", "zestiende"),
            ("XVII", "zeventien", "zeventiende"),
            ("XVIII", "achttien", "achttiende"),
            ("XIX", "negentien", "negentiende"),
            ("XX", "twintig", "twintigste"),
            ("XXI", "eenentwintig", "eenentwintigste"),
        ]

        # Monarchs and Popes: Name + Roman -> Name + " de " + ordinal
        monarch_names = pynini.union(
            "Willem", "Louis", "Lodewijk", "Filips", "Karel", "Hendrik", "Jan", "Albert",
            "Boudewijn", "Leopold", "Elizabeth", "Beatrix", "Wilhelmina", "Juliana",
            "Paus", "Benedictus", "Johannes", "Franciscus", "Alexander", "Peter"
        )
        monarch_roman = pynini.string_map([(r, ord_w) for r, _, ord_w in roman_map])
        monarch_fst = (
            monarch_names
            + pynini.cross(" ", " de ")
            + monarch_roman
        )

        # Chapter / Section: "Hoofdstuk" / "hoofdstuk" / "Deel" / "deel" + Roman -> "hoofdstuk " + cardinal
        chap_words = (
            pynini.cross("Hoofdstuk", "hoofdstuk")
            | pynini.accep("hoofdstuk")
            | pynini.cross("Deel", "deel")
            | pynini.accep("deel")
            | pynini.cross("Boek", "boek")
            | pynini.accep("boek")
            | pynini.cross("Klasse", "klasse")
            | pynini.accep("klasse")
        )
        chap_roman = pynini.string_map([(r, card_w) for r, card_w, _ in roman_map])
        chap_fst = (
            chap_words
            + pynutil.insert(" ")
            + pynutil.delete(" ")
            + chap_roman
        )

        # Centuries: "XXIe eeuw" / "XXI eeuw" -> "eenentwintigste eeuw"
        century_roman = pynini.string_map([(r, ord_w) for r, _, ord_w in roman_map])
        century_fst = (
            century_roman
            + pynini.closure(pynutil.delete("e"), 0, 1)
            + pynini.cross(" eeuw", " eeuw")
        )

        # Controls to explicitly keep XL, MIX, CD as letters or spoken acronyms:
        ctrl_fst = pynini.string_map(
            [
                ("XL", "X L"),
                ("MIX", "M I X"),
                ("CD", "C D"),
            ]
        )

        self.spoken_roman = (
            pynutil.add_weight(ctrl_fst, 0.9)
            | pynutil.add_weight(monarch_fst, 0.95)
            | pynutil.add_weight(chap_fst, 0.96)
            | pynutil.add_weight(century_fst, 0.97)
        ).optimize()

        self.fst = wrap_name(self.spoken_roman)
