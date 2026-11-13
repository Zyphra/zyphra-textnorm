# Copyright (c) 2026 Zyphra, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    delete_space,
    insert_space,
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Danish cardinals (Unicode CLDR release-49 da).
    Handles:
      - Integers 0-999,999,999,999,999
      - Danish vigesimal tens (halvtreds, tres, halvfjerds, firs, halvfems)
      - Danish inverted unit+ten compounds (enogtyve, tooghalvfjerds)
      - Neuter (et) and common (en) gender forms
      - Grouping with "." or " " (1.000.000 / 1 000 000)
      - Negative numbers with "-" or "−" (U+2212)
      - Prefixed approximate ("~") and plus-minus ("±")
      - Cardinal ranges ("5-10" -> "fem til ti")
      - Leading zeros / digit sequences ("007" -> "nul nul syv")
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        # 0
        zero = pynini.cross("0", "nul")

        # 1-9
        digit_neuter = (
            pynini.cross("1", "et")
            | pynini.cross("2", "to")
            | pynini.cross("3", "tre")
            | pynini.cross("4", "fire")
            | pynini.cross("5", "fem")
            | pynini.cross("6", "seks")
            | pynini.cross("7", "syv")
            | pynini.cross("8", "otte")
            | pynini.cross("9", "ni")
        )

        digit_common = (
            pynini.cross("1", "en")
            | pynini.cross("2", "to")
            | pynini.cross("3", "tre")
            | pynini.cross("4", "fire")
            | pynini.cross("5", "fem")
            | pynini.cross("6", "seks")
            | pynini.cross("7", "syv")
            | pynini.cross("8", "otte")
            | pynini.cross("9", "ni")
        )

        # Digits for single-digit reading
        self.single_digit = (zero | digit_neuter).optimize()
        self.single_digit_common = (zero | digit_common).optimize()

        # Teens 10-19
        teens = (
            pynini.cross("10", "ti")
            | pynini.cross("11", "elleve")
            | pynini.cross("12", "tolv")
            | pynini.cross("13", "tretten")
            | pynini.cross("14", "fjorten")
            | pynini.cross("15", "femten")
            | pynini.cross("16", "seksten")
            | pynini.cross("17", "sytten")
            | pynini.cross("18", "atten")
            | pynini.cross("19", "nitten")
        )

        # Ties 20, 30, ..., 90
        ties = (
            pynini.cross("2", "tyve")
            | pynini.cross("3", "tredive")
            | pynini.cross("4", "fyrre")
            | pynini.cross("5", "halvtreds")
            | pynini.cross("6", "tres")
            | pynini.cross("7", "halvfjerds")
            | pynini.cross("8", "firs")
            | pynini.cross("9", "halvfems")
        )

        exact_ties = ties + pynutil.delete("0")

        # Inverted unit prefixes: unit + "og"
        unit_prefix = (
            pynini.cross("1", "enog")
            | pynini.cross("2", "toog")
            | pynini.cross("3", "treog")
            | pynini.cross("4", "fireog")
            | pynini.cross("5", "femog")
            | pynini.cross("6", "seksog")
            | pynini.cross("7", "syvog")
            | pynini.cross("8", "otteog")
            | pynini.cross("9", "niog")
        )

        # 21-99 compound: e.g. "enogtyve", "tooghalvfjerds", "femoghalvfems"
        tens_compound = pynini.union(
            *[
                pynini.cross(f"{t}{u}", f"{upfx}{tname}")
                for t, tname in [
                    ("2", "tyve"),
                    ("3", "tredive"),
                    ("4", "fyrre"),
                    ("5", "halvtreds"),
                    ("6", "tres"),
                    ("7", "halvfjerds"),
                    ("8", "firs"),
                    ("9", "halvfems"),
                ]
                for u, upfx in [
                    ("1", "enog"),
                    ("2", "toog"),
                    ("3", "treog"),
                    ("4", "fireog"),
                    ("5", "femog"),
                    ("6", "seksog"),
                    ("7", "syvog"),
                    ("8", "otteog"),
                    ("9", "niog"),
                ]
            ]
        )

        # 1-99 unpadded (1 or 2 digits)
        two_digits_neuter = (digit_neuter | teens | exact_ties | tens_compound).optimize()
        two_digits_common = (digit_common | teens | exact_ties | tens_compound).optimize()

        # 01-99 padded (exactly 2 digits)
        two_digits_pad2_neuter = (
            (pynutil.delete("0") + digit_neuter) | teens | exact_ties | tens_compound
        ).optimize()
        two_digits_pad2_common = (
            (pynutil.delete("0") + digit_common) | teens | exact_ties | tens_compound
        ).optimize()

        # Hundreds 100-999
        hundred_names = [
            ("1", "hundrede"),
            ("2", "tohundrede"),
            ("3", "trehundrede"),
            ("4", "firehundrede"),
            ("5", "femhundrede"),
            ("6", "sekshundrede"),
            ("7", "syvhundrede"),
            ("8", "ottehundrede"),
            ("9", "nihundrede"),
        ]

        exact_hundreds = pynini.union(
            *[pynini.cross(d + "00", name) for d, name in hundred_names]
        )

        hundreds_with_rem_neuter = pynini.union(
            *[
                pynini.cross(d, name + " og ") + two_digits_pad2_neuter
                for d, name in hundred_names
            ]
        )
        hundreds_with_rem_common = pynini.union(
            *[
                pynini.cross(d, name + " og ") + two_digits_pad2_common
                for d, name in hundred_names
            ]
        )

        # 1-999 unpadded (1, 2, or 3 digits)
        self.num_1_to_999_neuter = (
            two_digits_neuter | exact_hundreds | hundreds_with_rem_neuter
        ).optimize()
        self.num_1_to_999_common = (
            two_digits_common | exact_hundreds | hundreds_with_rem_common
        ).optimize()

        # Exact 3-digit padded blocks (input length is EXACTLY 3 digits: 000-999)
        pad3_zero = pynutil.delete("000")
        pad3_under_100_neuter = pynutil.delete("0") + two_digits_pad2_neuter
        pad3_under_100_common = pynutil.delete("0") + two_digits_pad2_common
        pad3_over_100_neuter = exact_hundreds | hundreds_with_rem_neuter
        pad3_over_100_common = exact_hundreds | hundreds_with_rem_common

        pad3_nonzero_neuter = (pad3_under_100_neuter | pad3_over_100_neuter).optimize()
        pad3_nonzero_common = (pad3_under_100_common | pad3_over_100_common).optimize()

        digit_2_to_9 = (
            pynini.cross("2", "to")
            | pynini.cross("3", "tre")
            | pynini.cross("4", "fire")
            | pynini.cross("5", "fem")
            | pynini.cross("6", "seks")
            | pynini.cross("7", "syv")
            | pynini.cross("8", "otte")
            | pynini.cross("9", "ni")
        )

        # Multipliers > 1 (2-999 unpadded, 1 to 3 digits)
        mult_2_to_999_neuter = (
            digit_2_to_9
            | teens
            | exact_ties
            | tens_compound
            | exact_hundreds
            | hundreds_with_rem_neuter
        ).optimize()
        mult_2_to_999_common = (
            digit_2_to_9
            | teens
            | exact_ties
            | tens_compound
            | exact_hundreds
            | hundreds_with_rem_common
        ).optimize()

        # Non-1 two digits pad2 (02-99)
        two_digits_pad2_neuter_no_1 = (
            (pynutil.delete("0") + digit_2_to_9)
            | teens
            | exact_ties
            | tens_compound
        ).optimize()
        two_digits_pad2_common_no_1 = two_digits_pad2_neuter_no_1

        # Thousands: mult (1-999, 1-3 digits) + rem3 (EXACTLY 3 digits: 000-999)
        # Total length: 4, 5, or 6 digits.
        th_one_exact = pynini.cross("1000", "tusind")
        th_one_rem_under_100 = pynini.cross("1", "tusind og ") + pad3_under_100_neuter
        th_one_rem_over_100 = pynini.cross("1", "tusind ") + pad3_over_100_neuter
        th_one = th_one_exact | th_one_rem_under_100 | th_one_rem_over_100

        th_higher_exact = mult_2_to_999_neuter + pynutil.insert(" tusind") + pad3_zero
        th_higher_rem_under_100 = (
            mult_2_to_999_neuter
            + pynutil.insert(" tusind og ")
            + pad3_under_100_neuter
        )
        th_higher_rem_over_100 = (
            mult_2_to_999_neuter
            + pynutil.insert(" tusind ")
            + pad3_over_100_neuter
        )
        th_higher = th_higher_exact | th_higher_rem_under_100 | th_higher_rem_over_100

        thousands_graph = (th_one | th_higher).optimize()

        # 3-digit padded thousands block (used inside rem6): EXACTLY 3 digits (001-999)
        pad3_th_one = pynini.cross("001", "tusind")
        pad3_th_higher_word = (
            (pynutil.delete("0") + two_digits_pad2_neuter_no_1)
            | pad3_over_100_neuter
        )
        pad3_th_higher = pad3_th_higher_word + pynutil.insert(" tusind")
        pad3_th_nonzero = (pad3_th_one | pad3_th_higher).optimize()

        # Thousands block followed by non-zero units (3 digits + 3 digits = EXACTLY 6 digits)
        th_with_units = (
            (pynini.cross("001", "tusind og ") + pad3_under_100_neuter)
            | (pynini.cross("001", "tusind ") + pad3_over_100_neuter)
            | (pad3_th_higher_word + pynutil.insert(" tusind og ") + pad3_under_100_neuter)
            | (pad3_th_higher_word + pynutil.insert(" tusind ") + pad3_over_100_neuter)
        ).optimize()

        # Remainder 6: EXACTLY 6 digits (000000 - 999999)
        rem6_only_units = pynutil.delete("000") + pad3_nonzero_neuter
        rem6_only_thousands = pad3_th_nonzero + pynutil.delete("000")
        rem6_nonzero = (rem6_only_units | rem6_only_thousands | th_with_units).optimize()
        rem6_zero = pynutil.delete("000000")
        rem6_all = (rem6_zero | rem6_nonzero).optimize()

        # Millions: mult (1-999, 1-3 digits) + rem6 (EXACTLY 6 digits)
        # Total length: 7, 8, or 9 digits.
        millions_graph = (
            (pynini.cross("1", "en million") + rem6_zero)
            | (pynini.cross("1", "en million ") + rem6_nonzero)
            | (mult_2_to_999_common + pynutil.insert(" millioner") + rem6_zero)
            | (mult_2_to_999_common + pynutil.insert(" millioner ") + rem6_nonzero)
        ).optimize()

        # Remainder 9: EXACTLY 9 digits (000000000 - 999999999)
        pad3_millions_higher_word = (
            (pynutil.delete("0") + two_digits_pad2_common_no_1)
            | pad3_over_100_common
        )
        rem9_nonzero = (
            (pynutil.delete("000") + rem6_nonzero)
            | (pynini.cross("001", "en million") + rem6_zero)
            | (pynini.cross("001", "en million ") + rem6_nonzero)
            | (pad3_millions_higher_word + pynutil.insert(" millioner") + rem6_zero)
            | (pad3_millions_higher_word + pynutil.insert(" millioner ") + rem6_nonzero)
        ).optimize()
        rem9_zero = pynutil.delete("0" * 9)
        rem9_all = (rem9_zero | rem9_nonzero).optimize()

        # Billions: mult (1-999, 1-3 digits) + rem9 (EXACTLY 9 digits)
        # Total length: 10, 11, or 12 digits.
        billions_graph = (
            (pynini.cross("1", "en milliard") + rem9_zero)
            | (pynini.cross("1", "en milliard ") + rem9_nonzero)
            | (mult_2_to_999_common + pynutil.insert(" milliarder") + rem9_zero)
            | (mult_2_to_999_common + pynutil.insert(" milliarder ") + rem9_nonzero)
        ).optimize()

        # Remainder 12: EXACTLY 12 digits (0^12 - 9^12)
        rem12_nonzero = (
            (pynutil.delete("000") + rem9_nonzero)
            | (pynini.cross("001", "en milliard") + rem9_zero)
            | (pynini.cross("001", "en milliard ") + rem9_nonzero)
            | (pad3_millions_higher_word + pynutil.insert(" milliarder") + rem9_zero)
            | (pad3_millions_higher_word + pynutil.insert(" milliarder ") + rem9_nonzero)
        ).optimize()
        rem12_zero = pynutil.delete("0" * 12)
        rem12_all = (rem12_zero | rem12_nonzero).optimize()

        # Trillions: mult (1-999, 1-3 digits) + rem12 (EXACTLY 12 digits)
        # Total length: 13, 14, or 15 digits.
        trillions_graph = (
            (pynini.cross("1", "en billion") + rem12_zero)
            | (pynini.cross("1", "en billion ") + rem12_nonzero)
            | (mult_2_to_999_common + pynutil.insert(" billioner") + rem12_zero)
            | (mult_2_to_999_common + pynutil.insert(" billioner ") + rem12_nonzero)
        ).optimize()

        # Forms with "et hundrede" / "et tusind" for use in measure and money
        et_hundred = pynini.cross("100", "et hundrede")
        et_hundred_with_rem = pynini.cross("1", "et hundrede og ") + two_digits_pad2_neuter
        et_thousand = pynini.cross("1000", "et tusind")
        et_thousand_rem_under_100 = pynini.cross("1", "et tusind og ") + pad3_under_100_neuter
        et_thousand_rem_over_100 = pynini.cross("1", "et tusind ") + pad3_over_100_neuter

        self.integer_with_et = (
            et_hundred
            | et_hundred_with_rem
            | et_thousand
            | et_thousand_rem_under_100
            | et_thousand_rem_over_100
        ).optimize()

        # Full raw integer graph
        raw_integers_neuter = (
            zero
            | self.num_1_to_999_neuter
            | thousands_graph
            | millions_graph
            | billions_graph
            | trillions_graph
        ).optimize()

        raw_integers_common = (
            zero
            | pynini.cross("1", "en")
            | (pynini.difference(pynini.closure(NEMO_DIGIT, 1), "1") @ raw_integers_neuter)
        ).optimize()

        # Grouping separators: dot (".") or space (" ")
        dot_grouped_pat = (
            pynini.closure(NEMO_DIGIT, 1, 3)
            + pynini.closure(pynini.cross(".", "") + NEMO_DIGIT**3, 1)
        )
        space_grouped_pat = (
            pynini.closure(NEMO_DIGIT, 1, 3)
            + pynini.closure(pynini.cross(" ", "") + NEMO_DIGIT**3, 1)
        )
        grouped_to_digits = dot_grouped_pat | space_grouped_pat

        self.integer_neuter = (
            raw_integers_neuter | (grouped_to_digits @ raw_integers_neuter)
        ).optimize()

        self.integer_common = (
            raw_integers_common | (grouped_to_digits @ raw_integers_common)
        ).optimize()

        self.integer_with_et = (
            self.integer_with_et | (grouped_to_digits @ self.integer_with_et)
        ).optimize()

        # Digit-by-digit for leading zeros (e.g. "007" -> "nul nul syv") or serials
        digit_seq = self.single_digit + pynini.closure(insert_space + self.single_digit, 1)
        lead_zero_num = pynini.closure(pynini.cross("0", "nul "), 1) + self.integer_neuter
        self.digit_seq = (lead_zero_num | digit_seq).optimize()

        # Negative numbers: "-" or "−" -> "minus "
        minus_sign = pynini.cross(pynini.union("-", "−"), "minus ")
        optional_minus = pynini.closure(minus_sign, 0, 1)

        # Approximate ("~") and plus-minus ("±")
        approx_sign = pynini.cross("~", "cirka ")
        plus_minus_sign = pynini.cross("±", "plus-minus ")

        prefix_modifiers = minus_sign | approx_sign | plus_minus_sign
        opt_prefix = pynini.closure(prefix_modifiers, 0, 1)

        # Cardinal number with prefix
        number = opt_prefix + self.integer_neuter
        number_common = opt_prefix + self.integer_common

        # Exponent / power: "2^3" -> "to i tredje", "10^3" -> "ti i tredje", "x^2" -> "x i anden"
        power_map = pynini.string_map(
            [
                ("^2", " i anden"),
                ("^3", " i tredje"),
                ("^4", " i fjerde"),
                ("^5", " i femte"),
                ("^6", " i sjette"),
                ("^7", " i syvende"),
                ("^8", " i ottende"),
                ("^9", " i niende"),
                ("^10", " i tiende"),
            ]
        )
        base_num_or_var = self.integer_neuter | pynini.union("x", "y", "z", "n", "a", "b")
        power_graph = base_num_or_var + power_map

        # Math expressions: e.g. "1+5=6" -> "et plus fem er lig med seks", "5 = 5" -> "fem er lig med fem"
        # Division requires surrounding space (e.g. "10 / 2 = 5") or division sign "÷" to avoid shadowing slash fractions
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        plus_op = opt_sp + pynini.cross("+", " plus ") + opt_sp
        minus_op = opt_sp + pynini.cross(pynini.union("-", "−"), " minus ") + opt_sp
        mult_op = opt_sp + pynini.cross(pynini.union("*", "×", "x"), " gange ") + opt_sp
        div_slash = pynutil.delete(" ") + pynini.cross("/", " divideret med ") + pynutil.delete(" ")
        div_symbol = opt_sp + pynini.cross("÷", " divideret med ") + opt_sp
        div_op = div_slash | div_symbol
        eq_op = opt_sp + pynini.cross("=", " er lig med ") + opt_sp

        math_binop = plus_op | minus_op | mult_op | div_op
        math_expr = (
            self.integer_neuter
            + math_binop
            + self.integer_neuter
            + pynini.closure(eq_op + self.integer_neuter, 0, 1)
        )
        math_eq_simple = self.integer_neuter + eq_op + self.integer_neuter

        # Ratio / score: "1:2" -> "en til to", "2-1" -> "to et"
        ratio = (
            self.integer_common
            + pynini.cross(":", " til ")
            + self.integer_common
        )
        score = (
            two_digits_neuter
            + pynini.cross(pynini.union("-", "–"), " ")
            + two_digits_neuter
        )

        # Cardinal range: "5-10" -> "fem til ti", "1990–1995" -> "nitten hundrede og halvfems til nitten hundrede og femoghalvfems"
        range_dash = pynini.cross(pynini.union("-", "–", "—"), " til ")
        cardinal_range = (
            self.integer_neuter
            + opt_sp
            + range_dash
            + opt_sp
            + self.integer_neuter
        )

        # Serial alphanumeric: "iOS 17.4.1", "5G", "4K", "CO2", "AB-123-CD"
        alphanum = (
            (self.integer_neuter + pynutil.insert(" ") + pynini.union("G", "g", "K", "k", "D", "d"))
            | (pynini.union("CO", "co") + pynutil.insert(" ") + pynini.cross("2", "to"))
        )

        version_part = pynini.closure(NEMO_DIGIT, 1) @ self.integer_neuter
        version_dot = (
            version_part
            + pynini.cross(".", " punktum ")
            + version_part
            + pynini.closure(pynini.cross(".", " punktum ") + version_part, 1)
        )

        # Exported sub-graphs
        self.number = number
        self.number_common = number_common
        self.range_graph = pynutil.add_weight(cardinal_range, 0.1).optimize()
        self.math_graph = (
            pynutil.add_weight(score, 0.0)
            | pynutil.add_weight(ratio, 0.05)
            | pynutil.add_weight(power_graph, 0.05)
            | pynutil.add_weight(math_expr, 0.05)
            | pynutil.add_weight(math_eq_simple, 0.05)
        ).optimize()
        self.alphanum_graph = (alphanum | version_dot).optimize()

        # Full cardinal classifier
        all_cardinals = (
            self.math_graph
            | self.range_graph
            | self.alphanum_graph
            | self.number
            | pynutil.add_weight(self.digit_seq, 1.5)
        ).optimize()

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(all_cardinals)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
