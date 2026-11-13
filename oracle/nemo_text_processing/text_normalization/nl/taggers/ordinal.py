# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Dutch ordinal numbers.
    Handles:
    - 1e, 1ste, 1. -> eerste
    - 2e, 2de, 2. -> tweede
    - 3e, 3de, 3. -> derde
    - 4e, 4de -> vierde
    - 8e, 8ste -> achtste
    - 20e, 20ste -> twintigste
    - 21e, 21ste -> eenentwintigste
    - 22e, 22ste -> tweeëntwintigste (trema)
    - 100e, 100ste -> honderdste
    - 1000e, 1000ste -> duizendste
    - Contextual Roman numerals:
      - Hoofdstuk IV -> hoofdstuk vier
      - Willem I/II/III/IV -> Willem de eerste/tweede/derde/vierde
      - Lodewijk XIV -> Lodewijk de veertiende
      - 21e eeuw / XXIe eeuw -> eenentwintigste eeuw
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        # Base 1-19 ordinals
        ord_1_to_19 = [
            ("1", "eerste"),
            ("2", "tweede"),
            ("3", "derde"),
            ("4", "vierde"),
            ("5", "vijfde"),
            ("6", "zesde"),
            ("7", "zevende"),
            ("8", "achtste"),
            ("9", "negende"),
            ("10", "tiende"),
            ("11", "elfde"),
            ("12", "twaalfde"),
            ("13", "dertiende"),
            ("14", "veertiende"),
            ("15", "vijftiende"),
            ("16", "zestiende"),
            ("17", "zeventiende"),
            ("18", "achttiende"),
            ("19", "negentiende"),
        ]

        tens_map = {
            "2": "twintigste",
            "3": "dertigste",
            "4": "veertigste",
            "5": "vijftigste",
            "6": "zestigste",
            "7": "zeventigste",
            "8": "tachtigste",
            "9": "negentigste",
        }

        unit_prefix = {
            "1": "eenen",
            "2": "tweeën",  # trema
            "3": "drieën",  # trema
            "4": "vieren",
            "5": "vijfen",
            "6": "zesen",
            "7": "zevenen",
            "8": "achten",
            "9": "negenen",
        }

        ord_20_99 = []
        for t_digit, t_word in tens_map.items():
            ord_20_99.append((t_digit + "0", t_word))
            for u_digit, u_pref in unit_prefix.items():
                ord_20_99.append((t_digit + u_digit, u_pref + t_word))

        ord_1_99_map = pynini.string_map(ord_1_to_19 + ord_20_99).optimize()

        # Hundreds ordinals:
        hundred_100_ord = pynini.cross("100", "honderdste")
        hundred_1xx_ord = pynini.cross("1", "honderd") + (
            pynutil.delete("0") + pynini.string_map(ord_1_to_19[:9])
            | ord_1_99_map
        )
        hundred_exact_ord = pynini.string_map(
            [
                ("200", "tweehonderdste"),
                ("300", "driehonderdste"),
                ("400", "vierhonderdste"),
                ("500", "vijfhonderdste"),
                ("600", "zeshonderdste"),
                ("700", "zevenhonderdste"),
                ("800", "achthonderdste"),
                ("900", "negenhonderdste"),
            ]
        )
        hundred_nxx_ord = (
            pynini.string_map(
                [
                    ("2", "tweehonderd"),
                    ("3", "driehonderd"),
                    ("4", "vierhonderd"),
                    ("5", "vijfhonderd"),
                    ("6", "zeshonderd"),
                    ("7", "zevenhonderd"),
                    ("8", "achthonderd"),
                    ("9", "negenhonderd"),
                ]
            )
            + (pynutil.delete("0") + pynini.string_map(ord_1_to_19[:9]) | ord_1_99_map)
        )
        ord_100_999_map = (
            hundred_100_ord | hundred_1xx_ord | hundred_exact_ord | hundred_nxx_ord
        ).optimize()

        # Thousands ordinals:
        thousand_1000_ord = pynini.cross("1000", "duizendste")
        thousand_exact_ord = (
            cardinal.nums_1_to_999 + pynutil.delete("000") + pynutil.insert("duizendste")
        )
        thousand_rem_ord = (
            pynutil.delete("00") + pynini.string_map(ord_1_to_19[:9])
            | pynutil.delete("0") + ord_1_99_map
            | ord_100_999_map
        )
        thousand_nxxx_ord = (
            (pynini.cross("1", "duizend ") | (cardinal.nums_1_to_999 + pynutil.insert("duizend ")))
            + thousand_rem_ord
        )
        ord_1000_999999_map = (
            thousand_1000_ord | thousand_exact_ord | thousand_nxxx_ord
        ).optimize()

        million_ord = (
            pynini.cross("1000000", "miljoenste")
            | (cardinal.nums_1_to_999 + pynutil.delete("000000") + pynutil.insert(" miljoenste"))
        )

        all_numeric_ordinals = (
            ord_1_99_map
            | ord_100_999_map
            | ord_1000_999999_map
            | million_ord
        ).optimize()

        # Suffix patterns in written Dutch:
        # e, ste, de, or dot (.)
        ord_suffix = pynini.union("e", "ste", "de")
        ord_with_suffix = all_numeric_ordinals + pynutil.delete(ord_suffix)
        ord_with_dot = all_numeric_ordinals + pynutil.delete(".")

        # Roman numerals in Dutch contexts:
        # 1. Chapters: "Hoofdstuk IV", "hoofdstuk IV" -> "hoofdstuk vier"
        # 2. Monarchs: "Willem I", "Louis XIV", "Filips II" -> "Willem de eerste", etc.
        # 3. Centuries: "XXIe eeuw", "21e eeuw" -> "eenentwintigste eeuw"
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

        # Monarchs: Name + Roman -> Name + " de " + ordinal
        monarch_names = pynini.union(
            "Willem", "Louis", "Lodewijk", "Filips", "Karel", "Hendrik", "Jan", "Albert",
            "Boudewijn", "Leopold", "Elizabeth", "Beatrix", "Wilhelmina", "Juliana",
            "Paus", "Benedictus", "Johannes", "Franciscus"
        )
        monarch_roman = pynini.string_map([(r, ord_w) for r, _, ord_w in roman_map])
        monarch_fst = (
            monarch_names
            + pynini.cross(" ", " de ")
            + monarch_roman
        )

        # Chapter / Section: "Hoofdstuk" / "hoofdstuk" / "Deel" / "deel" + Roman -> "hoofdstuk " + cardinal
        chap_words = pynini.union("Hoofdstuk", "hoofdstuk", "Deel", "deel", "Boek", "boek")
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

        self.spoken_ordinal = (
            pynutil.add_weight(monarch_fst, 0.95)
            | pynutil.add_weight(chap_fst, 0.96)
            | pynutil.add_weight(century_fst, 0.97)
            | pynutil.add_weight(ord_with_suffix, 1.0)
            | pynutil.add_weight(ord_with_dot, 1.05)
        ).optimize()

        self.fst = wrap_name(self.spoken_ordinal)
