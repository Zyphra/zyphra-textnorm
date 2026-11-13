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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.da.utils import get_abs_path, load_labels
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Danish whitelisted tokens, abbreviations, and symbols.
    """

    def __init__(self, cardinal: CardinalFst, input_file: str = None, deterministic: bool = True):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        if input_file is None:
            input_file = get_abs_path("data/whitelist.tsv")

        labels = load_labels(input_file)
        whitelist_graph = pynini.string_map([(w, s) for w, s in labels if w and s])

        # Number abbreviations before cardinals:
        # e.g. "Nr. 5" -> "nummer fem", "No. 5" -> "nummer fem", "s. 12" -> "side tolv"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        num_prefix = pynini.string_map(
            [
                ("Nr.", "nummer"),
                ("nr.", "nummer"),
                ("Nr", "nummer"),
                ("nr", "nummer"),
                ("No.", "nummer"),
                ("no.", "nummer"),
                ("No", "nummer"),
                ("no", "nummer"),
                ("s.", "side"),
                ("S.", "side"),
                ("kap.", "kapitel"),
                ("Kap.", "kapitel"),
                ("fig.", "figur"),
                ("Fig.", "figur"),
                ("tab.", "tabel"),
                ("Tab.", "tabel"),
                ("§", "paragraf"),
                ("§§", "paragraffer"),
            ]
        )

        abbrev_with_number = (
            num_prefix
            + opt_sp
            + pynutil.insert(" ")
            + (cardinal.integer_neuter | cardinal.range_graph)
        )
        # Cents: 25¢ -> femogtyve cent, 1¢ -> en cent
        cents_num = pynini.cross("1", "en") | cardinal.integer_common | cardinal.num_1_to_999_common | cardinal.integer_neuter
        cents_expr = (cents_num + opt_sp + pynutil.delete("¢") + pynutil.insert(" cent")).optimize()

        # Serial dash codes: AB-123-CD -> a b et to tre c d
        danish_letters = pynini.string_map(
            [
                ("A", "a"), ("B", "b"), ("C", "c"), ("D", "d"), ("E", "e"),
                ("F", "f"), ("G", "g"), ("H", "h"), ("I", "i"), ("J", "j"),
                ("K", "k"), ("L", "l"), ("M", "m"), ("N", "n"), ("O", "o"),
                ("P", "p"), ("Q", "q"), ("R", "r"), ("S", "s"), ("T", "t"),
                ("U", "u"), ("V", "v"), ("W", "w"), ("X", "x"), ("Y", "y"),
                ("Z", "z"), ("Æ", "æ"), ("Ø", "ø"), ("Å", "å"),
                ("a", "a"), ("b", "b"), ("c", "c"), ("d", "d"), ("e", "e"),
                ("f", "f"), ("g", "g"), ("h", "h"), ("i", "i"), ("j", "j"),
                ("k", "k"), ("l", "l"), ("m", "m"), ("n", "n"), ("o", "o"),
                ("p", "p"), ("q", "q"), ("r", "r"), ("s", "s"), ("t", "t"),
                ("u", "u"), ("v", "v"), ("w", "w"), ("x", "x"), ("y", "y"),
                ("z", "z"), ("æ", "æ"), ("ø", "ø"), ("å", "å"),
            ]
        )
        single_digit_words = pynini.string_map(
            [
                ("0", "nul"),
                ("1", "et"),
                ("2", "to"),
                ("3", "tre"),
                ("4", "fire"),
                ("5", "fem"),
                ("6", "seks"),
                ("7", "syv"),
                ("8", "otte"),
                ("9", "ni"),
            ]
        )
        letter_seq = danish_letters + pynini.closure(pynutil.insert(" ") + danish_letters)
        digit_seq = single_digit_words + pynini.closure(pynutil.insert(" ") + single_digit_words)
        serial_dash = (
            letter_seq
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + digit_seq
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + letter_seq
        ).optimize()

        # Multi-dot versions: iOS 17.4.1 -> i o s sytten punktum fire punktum et, v2.0 -> v to punktum nul
        version_prefix = (
            pynini.cross("iOS ", "i o s ")
            | pynini.cross("ios ", "i o s ")
            | pynini.cross("v", "v ")
            | pynini.cross("V", "V ")
            | pynini.cross("ver. ", "version ")
            | pynini.cross("version ", "version ")
        )
        version_part = pynini.closure(NEMO_DIGIT, 1) @ (
            cardinal.integer_neuter | single_digit_words
        )
        dot_num = pynini.cross(".", " punktum ") + version_part
        version_num = version_part + dot_num + pynini.closure(dot_num, 1)
        version_expr = (version_prefix + version_num).optimize()

        # Mathematical powers: 2^3 -> to i tredje, x^2 -> x i anden
        power_sym = pynini.cross("^", " i ")
        power_num = pynini.string_map(
            [
                ("2", "anden"),
                ("3", "tredje"),
                ("4", "fjerde"),
                ("5", "femte"),
                ("6", "sjette"),
                ("7", "syvende"),
                ("8", "ottende"),
                ("9", "niende"),
                ("10", "tiende"),
            ]
        )
        power_base = danish_letters | cardinal.integer_neuter | cardinal.integer_common
        power_expr = (power_base + power_sym + power_num).optimize()

        # Require both a letter and a digit; preserve every identifier digit.
        normalize_digit = pynini.string_map(
            [(str(i), str(i)) for i in range(10)]
            + [(chr(0x2080 + i), str(i)) for i in range(10)]
        )
        identifier_digit = normalize_digit @ single_digit_words
        identifier_digits = identifier_digit + pynini.closure(pynutil.insert(" ") + identifier_digit)
        alphanumerics = (
            letter_seq + pynutil.insert(" ") + identifier_digits
            + pynini.closure(pynutil.insert(" ") + letter_seq, 0, 1)
            | identifier_digits + pynutil.insert(" ") + (pynini.union("G", "g", "K", "k") @ danish_letters)
        )

        all_whitelist = (
            abbrev_with_number
            | serial_dash
            | version_expr
            | power_expr
            | alphanumerics
            | cents_expr
            | whitelist_graph
        ).optimize()
        self.graph = all_whitelist

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
