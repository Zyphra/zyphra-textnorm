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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst


class FractionFst(GraphFst):
    """
    Finite state transducer for fractions in Turkish:
    - Vulgar fractions: ½ -> yarım, ¼ -> çeyrek, ¾ -> üç bölü dört, ⅓ -> üçte bir
    - Mixed fractions: 1 ½ -> bir buçuk, 2 ½ -> iki buçuk, 3 ¼ -> üç tam çeyrek
    - Negative mixed: -2 ½ -> eksi iki buçuk
    - Slash fractions: 1/2 -> yarım, 1/4 -> çeyrek, 3/4 -> üç bölü dört, 5/8 -> sekizde beş
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        integer_part = cardinal.positive_cardinals

        vulgar_map = pynini.string_map([
            ("½", "yarım"),
            ("¼", "çeyrek"),
            ("¾", "üç bölü dört"),
            ("⅓", "üçte bir"),
            ("⅔", "üçte iki"),
            ("⅕", "beşte bir"),
            ("⅖", "beşte iki"),
            ("⅗", "beşte üç"),
            ("⅘", "beşte dört"),
            ("⅙", "altıda bir"),
            ("⅚", "altıda beş"),
            ("⅛", "sekizde bir"),
            ("⅜", "sekizde üç"),
            ("⅝", "sekizde beş"),
            ("⅞", "sekizde yedi"),
            ("⅐", "yedide bir"),
            ("⅑", "dokuzda bir"),
            ("⅒", "onda bir"),
        ])

        opt_neg = pynini.closure(pynini.cross(pynini.union("-", "−"), "eksi "), 0, 1)
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        # Standalone vulgar fraction: ½ -> yarım, -¾ -> eksi üç bölü dört
        bare_vulgar = opt_neg + vulgar_map

        # Mixed with half: 1 ½ -> bir buçuk, 2½ -> iki buçuk
        mixed_half = opt_neg + integer_part + opt_space + pynini.cross("½", " buçuk")

        # Mixed with quarter: 3 ¼ -> üç tam çeyrek
        mixed_quarter = opt_neg + integer_part + opt_space + pynini.cross("¼", " tam çeyrek")

        # Other mixed vulgar: 3 ¾ -> üç tam üç bölü dört
        other_vulgar = pynini.difference(
            pynini.project(vulgar_map, "input"), pynini.union("½", "¼").optimize()
        ).optimize() @ vulgar_map
        mixed_other = opt_neg + integer_part + opt_space + pynutil.insert(" tam ") + other_vulgar

        # Common slash fractions
        slash_common = pynini.string_map([
            ("1/2", "yarım"),
            ("1/4", "çeyrek"),
            ("3/4", "üç bölü dört"),
            ("1/3", "üçte bir"),
            ("2/3", "üçte iki"),
            ("1/5", "beşte bir"),
            ("2/5", "beşte iki"),
            ("3/5", "beşte üç"),
            ("4/5", "beşte dört"),
            ("1/8", "sekizde bir"),
            ("3/8", "sekizde üç"),
            ("5/8", "sekizde beş"),
            ("7/8", "sekizde yedi"),
        ])
        bare_slash_common = opt_neg + slash_common

        # Mixed slash fractions: 1 1/2 -> bir buçuk, 2 1/2 -> iki buçuk
        mixed_slash_half = opt_neg + integer_part + opt_space + pynini.cross("1/2", " buçuk")
        mixed_slash_quarter = opt_neg + integer_part + opt_space + pynini.cross("1/4", " tam çeyrek")
        mixed_slash_common = (
            opt_neg
            + integer_part
            + opt_space
            + pynutil.insert(" tam ")
            + (pynini.difference(
                pynini.project(slash_common, "input"), pynini.union("1/2", "1/4").optimize()
            ).optimize() @ slash_common)
        )

        # General slash fraction: X/Y -> X bölü Y
        general_slash = (
            opt_neg
            + integer_part
            + pynini.cross("/", " bölü ")
            + integer_part
        )

        all_fractions = (
            mixed_half
            | mixed_quarter
            | mixed_slash_half
            | mixed_slash_quarter
            | mixed_other
            | mixed_slash_common
            | bare_vulgar
            | bare_slash_common
            | general_slash
        ).optimize()
        self.all_fractions = all_fractions

        self.fst = (pynutil.insert('name: "') + convert_space(all_fractions) + pynutil.insert('"')).optimize()
