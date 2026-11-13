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

# Polish number names from Unicode CLDR release-49 (CLDR pl %spellout-cardinal-*, %spellout-ordinal-*).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, NEMO_SIGMA
from nemo_text_processing.text_normalization.pl.utils import get_abs_path

# Private use symbols for cleaner graph composition
_PAD = pynini.union(*[pynutil.insert("0" * (12 - k)) + NEMO_DIGIT**k for k in range(1, 13)]).optimize()
_STRIP_SPACE = (pynutil.delete(" ") + pynini.closure(NEMO_SIGMA)).optimize()


class PolishNumbers:
    """Helper class providing compiled Polish cardinal and ordinal FSTs across genders and cases."""

    def __init__(self):
        self._load_lexicons()
        self._build_cardinal_groups()
        self._build_ordinal_groups()

    def _load_lexicons(self):
        # Cardinal lexicons
        self.digit_m = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        self.digit_f = pynini.string_file(get_abs_path("data/numbers/digit_fem.tsv"))
        self.digit_n = pynini.string_file(get_abs_path("data/numbers/digit_neut.tsv"))
        self.zero = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))
        self.teen = pynini.string_file(get_abs_path("data/numbers/teen.tsv"))
        self.ties = pynini.string_file(get_abs_path("data/numbers/ties.tsv"))
        self.hundreds = pynini.string_file(get_abs_path("data/numbers/hundreds.tsv"))

        # Cardinal genitive lexicons
        self.digit_gen = pynini.string_file(get_abs_path("data/numbers/digit_gen.tsv"))
        self.teen_gen = pynini.string_file(get_abs_path("data/numbers/teen_gen.tsv"))
        self.ties_gen = pynini.string_file(get_abs_path("data/numbers/ties_gen.tsv"))
        self.hundreds_gen = pynini.string_file(get_abs_path("data/numbers/hundreds_gen.tsv"))

        # Ordinal lexicons
        self.ord_ones_m = pynini.string_file(get_abs_path("data/numbers/ordinal_ones.tsv"))
        self.ord_ones_f = pynini.string_file(get_abs_path("data/numbers/ordinal_ones_fem.tsv"))
        self.ord_ones_n = pynini.string_file(get_abs_path("data/numbers/ordinal_ones_neut.tsv"))
        self.ord_ones_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_ones_gen.tsv"))
        self.ord_ones_f_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_ones_fem_gen.tsv"))

        self.ord_teens_m = pynini.string_file(get_abs_path("data/numbers/ordinal_teens.tsv"))
        self.ord_teens_f = pynini.string_file(get_abs_path("data/numbers/ordinal_teens_fem.tsv"))
        self.ord_teens_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_teens_gen.tsv"))
        self.ord_teens_f_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_teens_fem_gen.tsv"))

        self.ord_tens_m = pynini.string_file(get_abs_path("data/numbers/ordinal_tens.tsv"))
        self.ord_tens_f = pynini.string_file(get_abs_path("data/numbers/ordinal_tens_fem.tsv"))
        self.ord_tens_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_tens_gen.tsv"))
        self.ord_tens_f_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_tens_fem_gen.tsv"))

        self.ord_hund_m = pynini.string_file(get_abs_path("data/numbers/ordinal_hundreds.tsv"))
        self.ord_hund_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_hundreds_gen.tsv"))
        self.ord_hund_f_gen = pynini.string_file(get_abs_path("data/numbers/ordinal_hundreds_fem_gen.tsv"))

        # Lexicons contain complete 20/100 forms; interior triplets consume only their leading digit.
        tens_input = NEMO_DIGIT + pynutil.insert("0")
        hundreds_input = NEMO_DIGIT + pynutil.insert("00")
        self.ties = (tens_input @ self.ties).optimize()
        self.hundreds = (hundreds_input @ self.hundreds).optimize()
        self.ties_gen = (tens_input @ self.ties_gen).optimize()
        self.hundreds_gen = (hundreds_input @ self.hundreds_gen).optimize()
        self.ord_tens_m = (tens_input @ self.ord_tens_m).optimize()
        self.ord_tens_f = (tens_input @ self.ord_tens_f).optimize()
        self.ord_tens_gen = (tens_input @ self.ord_tens_gen).optimize()
        self.ord_tens_f_gen = (tens_input @ self.ord_tens_f_gen).optimize()
        self.ord_hund_m = (hundreds_input @ self.ord_hund_m).optimize()
        self.ord_hund_gen = (hundreds_input @ self.ord_hund_gen).optimize()
        self.ord_hund_f_gen = (hundreds_input @ self.ord_hund_f_gen).optimize()

    def _build_cardinal_groups(self):
        """Builds 3-digit groups partitioned by Polish noun agreement category ('one', 'few', 'many')."""
        def make_group(digit_fst):
            u_one = pynutil.insert(" ") + (pynini.accep("1") @ digit_fst)
            u_few = pynutil.insert(" ") + (pynini.union("2", "3", "4") @ digit_fst)
            u_many = pynutil.insert(" ") + (pynini.union("5", "6", "7", "8", "9") @ digit_fst)

            teens = pynutil.insert(" ") + self.teen
            tens_only = pynutil.insert(" ") + self.ties + pynutil.delete("0")
            tens_compound = pynutil.insert(" ") + self.ties

            hunds = pynutil.insert(" ") + self.hundreds
            h_opt = pynutil.delete("0") | hunds

            # exactly 1 (001)
            one = pynutil.delete("00") + u_one

            # compound ending in 1 (e.g. 021, 101, 121) - in Polish, compound 21 takes genitive plural ('many')!
            one_compound = (hunds + pynutil.delete("0") + u_one) | (h_opt + tens_compound + u_one)

            # few: ends in 2, 3, 4 except 12, 13, 14
            few = h_opt + (pynutil.delete("0") | tens_compound) + u_few

            # many: ends in 0, 5..9, 11..19, or compound 1
            many = (
                h_opt + teens
                | hunds + pynutil.delete("00")
                | h_opt + tens_only
                | h_opt + (pynutil.delete("0") | tens_compound) + u_many
                | one_compound
            )
            return {"one": one.optimize(), "few": few.optimize(), "many": many.optimize()}

        self.groups_m = make_group(self.digit_m)
        self.groups_f = make_group(self.digit_f)
        self.groups_n = make_group(self.digit_n)

    def _build_cardinal_gen_group(self):
        """Builds 3-digit cardinal group for genitive case ('dziesięciu', 'dwudziestu pięciu', 'stu dwudziestu')."""
        non_zero = pynini.union(*[str(i) for i in range(1, 10)])
        u_gen = pynutil.insert(" ") + (non_zero @ self.digit_gen)
        teens = pynutil.insert(" ") + self.teen_gen
        tens_only = pynutil.insert(" ") + self.ties_gen + pynutil.delete("0")
        tens_comp = pynutil.insert(" ") + self.ties_gen + u_gen

        two_digits = pynutil.delete("0") + u_gen | teens | tens_only | tens_comp

        hund_only = pynutil.insert(" ") + self.hundreds_gen + pynutil.delete("00")
        hund_card = pynutil.insert(" ") + self.hundreds_gen
        h_opt = pynutil.delete("0") | hund_card

        three_digits = hund_only | h_opt + two_digits
        return three_digits.optimize()

    def _build_ordinal_groups(self):
        """Builds 3-digit ordinal groups for masculine, feminine, and genitive forms."""
        non_zero = pynini.union(*[str(i) for i in range(1, 10)])

        def make_ord(ones_ord, teens_ord, tens_ord, hund_ord):
            u_ord = pynutil.insert(" ") + (non_zero @ ones_ord)
            t_ord = pynutil.insert(" ") + teens_ord
            tens_only = pynutil.insert(" ") + tens_ord + pynutil.delete("0")
            # compound tens + units: in Polish both take ordinal (dwudziesty pierwszy, trzydziesty piąty)
            tens_compound = pynutil.insert(" ") + tens_ord + u_ord

            hund_only = pynutil.insert(" ") + hund_ord + pynutil.delete("00")
            # hundreds + rest: hundreds stay cardinal (sto pierwszy, dwieście dwudziesty)
            hund_card = pynutil.insert(" ") + self.hundreds
            h_card_opt = pynutil.delete("0") | hund_card

            two_ord = pynutil.delete("0") + u_ord | t_ord | tens_only | tens_compound
            three_ord = hund_only | h_card_opt + two_ord
            return three_ord.optimize()

        self.ord_group_m = make_ord(self.ord_ones_m, self.ord_teens_m, self.ord_tens_m, self.ord_hund_m)
        self.ord_group_f = make_ord(self.ord_ones_f, self.ord_teens_f, self.ord_tens_f, self.ord_hund_m)
        self.ord_group_gen = make_ord(self.ord_ones_gen, self.ord_teens_gen, self.ord_tens_gen, self.ord_hund_gen)
        self.ord_group_f_gen = make_ord(self.ord_ones_f_gen, self.ord_teens_f_gen, self.ord_tens_f_gen, self.ord_hund_f_gen)

    def _magnitude(self, level: int, with_one: bool = True) -> pynini.Fst:
        """Forms for powers of 1000:
        level 1: tysiąc (few: tysiące, many: tysięcy)
        level 2: milion (few: miliony, many: milionów)
        level 3: miliard (few: miliardy, many: miliardów)
        level 4: bilion (few: biliony, many: bilionów)
        """
        names = {
            1: ("tysiąc", "tysiące", "tysięcy"),
            2: ("milion", "miliony", "milionów"),
            3: ("miliard", "miliardy", "miliardów"),
            4: ("bilion", "biliony", "bilionów"),
        }[level]

        grp = self.groups_m
        if not with_one:
            # 001 becomes bare name (e.g. 1000 -> "tysiąc", not "jeden tysiąc")
            one_graph = pynini.cross("001", " " + names[0])
        else:
            one_graph = grp["one"] + pynutil.insert(" " + names[0])

        few_graph = grp["few"] + pynutil.insert(" " + names[1])
        many_graph = grp["many"] + pynutil.insert(" " + names[2])
        zero_grp = pynutil.delete("000")

        return (one_graph | few_graph | many_graph | zero_grp).optimize()

    def cardinal_fst(self, gender: str = "masc", case: str = "nom") -> pynini.Fst:
        """Returns FST converting 1-12 digit integer to Polish cardinal words."""
        valid_digits = pynini.accep("0") | (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT)

        if case == "gen":
            three_digits = self._build_cardinal_gen_group()
            pad3 = pynutil.insert("00") + NEMO_DIGIT | pynutil.insert("0") + NEMO_DIGIT**2 | NEMO_DIGIT**3
            under_1000 = pynini.compose(pad3, three_digits)
            under_1000_stripped = pynini.compose(under_1000, _STRIP_SPACE)
            zero = pynini.cross("0", "zera")

            th_pure = pynini.cross("1000", "tysiąca")
            th_1000 = pynini.cross("1", "tysiąc ") + (pynutil.delete("0") | NEMO_DIGIT**3) @ three_digits @ _STRIP_SPACE

            full_gen = (zero | th_pure | th_1000 | under_1000_stripped).optimize()
            return pynini.compose(valid_digits, full_gen).optimize()

        grp = {"fem": self.groups_f, "neut": self.groups_n}.get(gender, self.groups_m)
        units = (grp["one"] | grp["few"] | grp["many"] | pynutil.delete("000")).optimize()

        body = (
            self._magnitude(3, with_one=False)  # billions / miliardy
            + self._magnitude(2, with_one=False)  # millions / miliony
            + self._magnitude(1, with_one=False)  # thousands / tysiące
            + units
        )
        padded = pynini.compose(_PAD, body)
        stripped = pynini.compose(padded, _STRIP_SPACE)
        zero = pynini.cross("0", "zero")
        card = (stripped | zero).optimize()
        return pynini.compose(valid_digits, card).optimize()

    def ordinal_fst(self, gender: str = "masc", case: str = "nom") -> pynini.Fst:
        """Returns FST converting 1-4 digit integer to Polish ordinal words."""
        if case == "gen":
            if gender == "fem":
                ord_grp = self.ord_group_f_gen
                th_pure = pynini.cross("1000", "tysięcznej") | pynini.cross("2000", "dwutysięcznej")
                th_1000_w = "tysiąc "
                th_2000_w = "dwa tysiące "
                zero_word = "zerowej"
            else:
                ord_grp = self.ord_group_gen
                th_pure = pynini.cross("1000", "tysięcznego") | pynini.cross("2000", "dwutysięcznego")
                th_1000_w = "tysiąc "
                th_2000_w = "dwa tysiące "
                zero_word = "zerowego"
        elif gender == "fem":
            ord_grp = self.ord_group_f
            th_pure = pynini.cross("1000", "tysięczna") | pynini.cross("2000", "dwutysięczna")
            th_1000_w = "tysiąc "
            th_2000_w = "dwa tysiące "
            zero_word = "zerowa"
        else:
            ord_grp = self.ord_group_m
            th_pure = pynini.cross("1000", "tysięczny") | pynini.cross("2000", "dwutysięczny")
            th_1000_w = "tysiąc "
            th_2000_w = "dwa tysiące "
            zero_word = "zerowy"

        zero_ord = pynini.cross("0", zero_word)

        # 1..999
        pad3 = pynutil.insert("00") + NEMO_DIGIT | pynutil.insert("0") + NEMO_DIGIT**2 | NEMO_DIGIT**3
        under_1000 = pynini.compose(pad3, ord_grp)
        under_1000_stripped = pynini.compose(under_1000, _STRIP_SPACE)

        # 1001..2999: compound thousands stay cardinal (e.g. 1995 -> "tysiąc dziewięćset dziewięćdziesiąty piąty")
        th_1000 = pynini.cross("1", th_1000_w) + (pynutil.delete("000") | ((pynutil.delete("0") | NEMO_DIGIT**3) @ ord_grp @ _STRIP_SPACE))
        th_2000 = pynini.cross("2", th_2000_w) + (pynutil.delete("000") | ((pynutil.delete("0") | NEMO_DIGIT**3) @ ord_grp @ _STRIP_SPACE))

        graph = zero_ord | th_pure | th_1000 | th_2000 | under_1000_stripped
        return graph.optimize()
