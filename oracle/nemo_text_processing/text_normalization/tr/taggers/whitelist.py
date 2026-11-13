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

import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.tr.taggers.decimal import DecimalFst


class WhiteListFst(GraphFst):
    """
    Finite state transducer for whitelist abbreviations, symbols, arithmetic, percentages, and serials in Turkish:
    - Titles & abbrevs: Dr. Smith -> doktor smith, No. 5 -> numara beş, etc. -> ve saire
    - Percent: %50 -> yüzde elli, 50% -> yüzde elli, ‰5 -> binde beş, %10-%15 -> yüzde on ila yüzde on beş
    - Symbols: & -> ve, © -> telif hakkı, § -> madde, #5 -> numara beş
    - Powers: x^2 -> x kare, y^3 -> y küp, 2^3 -> iki üzeri üç
    - Serials / versions: iOS 17.4.1, 5G, 4K, CO2, AB-123-CD
    - Arithmetic: 2 + 2 = 4 -> iki artı iki eşittir dört
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        decimal: DecimalFst = None,
        input_case: str = "cased",
        deterministic: bool = True,
        input_file: str = None,
    ):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)

        num = decimal.all_decimals | cardinal.positive_cardinals

        # 1. Titles and common abbreviations
        abbrevs = pynini.string_map([
            ("Dr.", "doktor"),
            ("Dr", "doktor"),
            ("Prof.", "profesör"),
            ("Prof", "profesör"),
            ("Doç.", "doçent"),
            ("Doç", "doçent"),
            ("Av.", "avukat"),
            ("Av", "avukat"),
            ("Müh.", "mühendis"),
            ("Müh", "mühendis"),
            ("Ecz.", "eczacı"),
            ("Uzm.", "uzman"),
            ("vb.", "ve benzeri"),
            ("vs.", "ve saire"),
            ("vd.", "ve diğerleri"),
            ("bkz.", "bakınız"),
            ("etc.", "ve saire"),
            ("etc", "ve saire"),
            ("Cad.", "caddesi"),
            ("Sok.", "sokağı"),
            ("Mah.", "mahallesi"),
            ("Apt.", "apartmanı"),
            ("s:t erik", "sankt erik"),
            ("S:t Erik", "sankt erik"),
        ])

        # Number abbreviations: "No. 5" -> "numara beş", "No: 12" -> "numara on iki"
        num_prefix = pynini.string_map([
            ("No. ", "numara "),
            ("No ", "numara "),
            ("No: ", "numara "),
            ("No:", "numara "),
            ("no. ", "numara "),
            ("no ", "numara "),
            ("no: ", "numara "),
            ("#", "numara "),
        ])
        num_abbrev_graph = num_prefix + cardinal.positive_cardinals

        # 2. Percentages & Per-milles
        # In Turkish, % is written before: %50 -> yüzde elli, %0,5 -> yüzde sıfır virgül beş
        # Or written after: 50% -> yüzde elli
        # Per-mille: ‰5 -> binde beş
        pct_prefix = pynini.cross("%", "yüzde ") + num
        pct_suffix = pynutil.insert("yüzde ") + num + pynutil.delete("%")
        permille_prefix = pynini.cross("‰", "binde ") + num
        permille_suffix = pynutil.insert("binde ") + num + pynutil.delete("‰")

        # Percent range: %10-%20, %10-15, 10-15%
        dash = pynini.union("-", "–", "—")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        pct_range_1 = (
            pynini.cross("%", "yüzde ")
            + num
            + opt_sp
            + pynini.cross(dash, " ila ")
            + opt_sp
            + pynini.closure(pynutil.delete("%"), 0, 1)
            + pynutil.insert("yüzde ")
            + num
        )
        pct_range_2 = (
            pynutil.insert("yüzde ")
            + num
            + opt_sp
            + pynini.cross(dash, " ila ")
            + opt_sp
            + num
            + pynutil.delete("%")
        )
        percent_graph = (
            pct_range_1
            | pct_range_2
            | pct_prefix
            | pct_suffix
            | permille_prefix
            | permille_suffix
        ).optimize()

        # 3. Special standalone symbols: &, ©, §
        symbol_graph = pynini.string_map([
            ("&", "ve"),
            ("©", "telif hakkı"),
            ("§", "madde"),
        ])

        # 4. Powers and Exponents: x^2 -> x kare, y^3 -> y küp, 2^3 -> iki üzeri üç
        base_var = pynini.closure(NEMO_ALPHA, 1, 3)
        base_num = cardinal.positive_cardinals
        exp_special = (
            pynini.cross("2", "kare")
            | pynini.cross("3", "küp")
            | (pynutil.insert("üzeri ") + cardinal.positive_cardinals)
            | (pynutil.insert("üzeri ") + pynini.closure(NEMO_ALPHA, 1, 2))
        )
        power_graph = (
            (base_var | base_num)
            + pynini.cross("^", " ")
            + exp_special
        )

        # 5. Arithmetic: 2 + 2 = 4, 5 - 3 = 2, 3 x 3 = 9
        arith_op = (
            pynini.cross("+", " artı ")
            | pynini.cross("=", " eşittir ")
            | pynini.cross("x", " çarpı ")
            | pynini.cross("×", " çarpı ")
            | pynini.cross("*", " çarpı ")
            | pynini.cross("eşittir", " eşittir ")
        )
        arith_graph = (
            num
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + arith_op
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + num
            + pynini.closure(
                pynini.closure(pynutil.delete(" "), 0, 1)
                + arith_op
                + pynini.closure(pynutil.delete(" "), 0, 1)
                + num,
                0,
                2,
            )
        )

        # 6. Alphanumerics & Multi-dot serials:
        # iOS 17.4.1 -> i o s on yedi nokta dört nokta bir
        # 5G -> beş g, 4K -> dört k, CO2 -> c o iki
        # AB-123-CD -> a b yüz yirmi üç c d
        single_digit = pynini.string_map([
            ("0", "sıfır"),
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        letters_lower_map = pynini.string_map([(c, c.lower()) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"])
        alpha_spaced = letters_lower_map + pynini.closure(pynutil.insert(" ") + letters_lower_map)

        # Version numbers: patch version is 1-2 digits, so 4-digit years (e.g. 29.10.1923) are NOT matched as versions
        ver_chunk = pynini.closure(NEMO_DIGIT, 1, 3) @ cardinal.positive_cardinals
        ver_patch = pynini.closure(NEMO_DIGIT, 1, 2) @ cardinal.positive_cardinals
        version_num = (
            ver_chunk
            + pynini.cross(".", " nokta ")
            + ver_chunk
            + pynini.cross(".", " nokta ")
            + ver_patch
        )
        version_named = (
            (pynini.cross("iOS", "i o s") | alpha_spaced)
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + version_num
        )

        # 5G -> beş g, 4K -> dört k, 3D -> üç d
        num_letter = cardinal.positive_cardinals + pynutil.insert(" ") + pynini.string_map([
            ("G", "g"), ("g", "g"),
            ("K", "k"), ("k", "k"),
            ("D", "d"), ("d", "d"),
        ])

        # CO2, H2O
        chemical = (
            pynini.cross("CO2", "c o iki")
            | pynini.cross("H2O", "h iki o")
            | pynini.cross("O2", "o iki")
            | pynini.cross("N2", "n iki")
        )

        # License plate / serial: AB-123-CD -> a b yüz yirmi üç c d
        plate = (
            alpha_spaced
            + pynini.cross("-", " ")
            + cardinal.positive_cardinals
            + pynini.cross("-", " ")
            + alpha_spaced
        )

        serial_graph = (
            version_named
            | version_num
            | num_letter
            | chemical
            | plate
        ).optimize()

        all_whitelist = (
            abbrevs
            | num_abbrev_graph
            | percent_graph
            | symbol_graph
            | power_graph
            | arith_graph
            | serial_graph
        ).optimize()

        if input_file and os.path.exists(input_file):
            file_graph = pynini.string_file(input_file)
            all_whitelist = (file_graph | all_whitelist).optimize()

        self.all_whitelist = all_whitelist

        self.fst = (pynutil.insert('name: "') + convert_space(all_whitelist) + pynutil.insert('"')).optimize()
