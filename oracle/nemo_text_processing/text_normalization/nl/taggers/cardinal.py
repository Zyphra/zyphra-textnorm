# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import (
    NEMO_MINUS,
    wrap_name,
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Dutch cardinal numbers.
    Handles:
    - 0 to 9 digits: nul, een, twee, drie, vier, vijf, zes, zeven, acht, negen
    - Teens 10 to 19: tien, elf, twaalf, dertien, veertien, vijftien, zestien, zeventien, achttien, negentien
    - Tens 20 to 90: twintig, dertig, veertig, vijftig, zestig, zeventig, tachtig, negentig
    - Inverted compound tens 21-99: eenentwintig, tweeëntwintig (trema), drieëntwintig (trema), etc.
    - Hundreds 100-999: honderd, tweehonderd, honderdeen, honderdtweeëntwintig
    - Thousands 1000-999999: duizend, tweeduizend, tienduizend, honderdduizend
    - Millions and billions: een miljoen, twee miljoen, een miljard, twee miljard
    - Grouped numbers with '.' or space: 1.000.000, 1 000 000
    - Negative numbers: -12, −7 -> min twaalf, min zeven
    - Number ranges: 10-20, 10–20 -> tien tot twintig
    - Leading zeros and digit sequences: 007 -> nul nul zeven, 1,2,3 -> een, twee, drie
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        # 0 - 9
        digit_pairs = [
            ("0", "nul"),
            ("1", "een"),
            ("2", "twee"),
            ("3", "drie"),
            ("4", "vier"),
            ("5", "vijf"),
            ("6", "zes"),
            ("7", "zeven"),
            ("8", "acht"),
            ("9", "negen"),
        ]
        self.digit = pynini.string_map(digit_pairs).optimize()
        self.zero = pynini.cross("0", "nul").optimize()
        self.digit_no_zero = pynini.string_map(digit_pairs[1:]).optimize()

        # Teens 10 - 19
        teens_pairs = [
            ("10", "tien"),
            ("11", "elf"),
            ("12", "twaalf"),
            ("13", "dertien"),
            ("14", "veertien"),
            ("15", "vijftien"),
            ("16", "zestien"),
            ("17", "zeventien"),
            ("18", "achttien"),
            ("19", "negentien"),
        ]
        teens = pynini.string_map(teens_pairs).optimize()

        # Tens 20 - 90
        tens_map = {
            "2": "twintig",
            "3": "dertig",
            "4": "veertig",
            "5": "vijftig",
            "6": "zestig",
            "7": "zeventig",
            "8": "tachtig",
            "9": "negentig",
        }
        tens = pynini.string_map([(k + "0", v) for k, v in tens_map.items()]).optimize()

        # Inverted units 1-9 prefix with "en" or trema "ën"
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

        # 21 - 99 inverted compounds (single word in Dutch)
        compounds = []
        for t_digit, t_word in tens_map.items():
            for u_digit, u_pref in unit_prefix.items():
                compounds.append((t_digit + u_digit, u_pref + t_word))
        compound_tens = pynini.string_map(compounds).optimize()

        # Numbers 1 to 99
        self.nums_1_to_99 = (self.digit_no_zero | teens | tens | compound_tens).optimize()
        self.nums_0_to_99 = (self.zero | self.nums_1_to_99).optimize()

        # Hundreds 100 - 999
        # 100
        hundred_100 = pynini.cross("100", "honderd")
        hundred_1xx = pynini.cross("1", "honderd") + pynutil.delete("0", weight=0.01) + self.digit_no_zero
        hundred_1xx |= pynini.cross("1", "honderd") + (teens | tens | compound_tens)

        # 200 - 900
        hundred_exact = pynini.string_map(
            [(k + "00", v + "honderd") for k, v in digit_pairs[2:]]
        )
        hundred_nxx = (
            pynini.string_map([(k, v + "honderd") for k, v in digit_pairs[2:]])
            + (pynutil.delete("0") + self.digit_no_zero | teens | tens | compound_tens)
        )

        self.nums_100_to_999 = (hundred_100 | hundred_1xx | hundred_exact | hundred_nxx).optimize()
        self.nums_1_to_999 = (self.nums_1_to_99 | self.nums_100_to_999).optimize()

        # Thousands 1000 - 999999
        thousand_1000 = pynini.cross("1000", "duizend")
        thousand_1xxx = (
            pynini.cross("1", "duizend")
            + pynini.closure(pynutil.add_weight(pynutil.insert(" "), 0.00001), 0, 1)
            + (
                pynutil.delete("00") + self.digit_no_zero
                | pynutil.delete("0") + (teens | tens | compound_tens)
                | pynutil.add_weight(self.nums_100_to_999, 0.00001)
            )
        )
        # Keep the regular "eenduizend" paths, but prefer the dedicated
        # "duizend" graph for a coefficient of one at every scale depth.
        thousand_coefficient = (
            pynutil.add_weight(pynini.cross("1", "een"), 0.00001)
            | (pynini.union(*"23456789") @ self.digit_no_zero)
            | teens | tens | compound_tens | self.nums_100_to_999
        )


        thousand_exact = (
            thousand_coefficient
            + pynutil.delete("000")
            + pynutil.insert("duizend")
        )

        thousand_remainder = (
            pynutil.delete("00") + self.digit_no_zero
            | pynutil.delete("0") + (teens | tens | compound_tens)
            | self.nums_100_to_999
        )
        thousand_nxxx = (
            thousand_coefficient
            + pynutil.insert("duizend ")
            + thousand_remainder
        )

        # Year pronunciation for 1100-1999 (e.g. 1995 -> negentienhonderdvijfennegentig)
        year_teens = pynini.string_map([(k, v + "honderd") for k, v in teens_pairs[1:]])
        year_1100_1999 = (
            year_teens
            + (
                pynutil.delete("00")
                | pynutil.delete("0") + self.digit_no_zero
                | (teens | tens | compound_tens)
            )
        )

        self.nums_1000_to_999999 = (
            thousand_1000 | thousand_1xxx | thousand_exact | thousand_nxxx | year_1100_1999
        ).optimize()
        self.nums_1_to_999999 = (self.nums_1_to_999 | self.nums_1000_to_999999).optimize()

        # Each remainder occupies exactly the scale's decimal width. Delete
        # leading zeroes only within that fixed-width field before reading its
        # nonzero value; otherwise short remainders shift the scale boundary.
        def scale_graph(word, width, lower):
            coefficient = self.nums_1_to_999 + pynutil.insert(f" {word}")
            padded_remainder = pynini.compose(
                NEMO_DIGIT ** width,
                pynini.closure(pynutil.delete("0"), 0, width - 1) + lower,
            )
            return (
                coefficient + pynutil.delete("0" * width)
                | coefficient + pynutil.insert(" ") + padded_remainder
            ).optimize()

        lower = self.nums_1_to_999999
        self.nums_millions = scale_graph("miljoen", 6, lower)
        lower = (lower | self.nums_millions).optimize()
        self.nums_billions = scale_graph("miljard", 9, lower)

        # All positive integer strings
        self.raw_cardinal = (
            self.nums_0_to_99
            | self.nums_100_to_999
            | self.nums_1000_to_999999
            | self.nums_millions
            | self.nums_billions
        ).optimize()

        # Grouped integers (thousands separated by '.' or ' ')
        leading_digits = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)
        group_sep = pynutil.delete(".") | pynutil.delete(" ")
        grouped_digits = leading_digits + pynini.closure(group_sep + NEMO_DIGIT**3, 1)
        grouped_raw = grouped_digits @ self.raw_cardinal

        self.cardinal_numbers = (grouped_raw | self.raw_cardinal).optimize()

        # Negative numbers: -12, −7 -> min twaalf, min zeven
        neg_cardinal = pynini.cross(NEMO_MINUS, "min ") + self.cardinal_numbers

        # Single digits / digit sequences / leading zeros:
        # "007" -> "nul nul zeven"
        single_digit_word = self.digit
        digit_sequence = (
            single_digit_word
            + pynini.closure(insert_space + single_digit_word, 1)
        )
        # Leading zero numbers (e.g. 007, 021)
        leading_zero_num = (
            pynini.cross("0", "nul ")
            + pynini.closure(pynini.cross("0", "nul "), 0)
            + (self.nums_1_to_99 | self.digit_no_zero)
        )

        # Lists of numbers: "1,2,3" -> "een, twee, drie"
        num_list = (
            self.cardinal_numbers
            + pynini.closure(pynini.cross(",", ", ") + self.cardinal_numbers, 2)
        )

        # Cardinal ranges: "10-20", "10–20", "10 - 20" -> "tien tot twintig"
        dash = pynini.union("-", "–", "—")
        cardinal_range = (
            self.cardinal_numbers
            + delete_space
            + pynini.cross(dash, " tot ")
            + delete_space
            + self.cardinal_numbers
        )

        # Combined spoken cardinal
        self.spoken_cardinal = (
            pynutil.add_weight(num_list, 0.95)
            | pynutil.add_weight(cardinal_range, 0.98)
            | pynutil.add_weight(neg_cardinal, 1.0)
            | pynutil.add_weight(self.cardinal_numbers, 1.0)
            | pynutil.add_weight(leading_zero_num, 1.05)
            | pynutil.add_weight(digit_sequence, 1.2)
        ).optimize()

        self.fst = wrap_name(self.spoken_cardinal)
