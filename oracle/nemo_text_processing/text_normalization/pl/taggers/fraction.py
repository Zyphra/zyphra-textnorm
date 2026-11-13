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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst, convert_space
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Polish fractions, e.g.
        "½" -> "jedna druga"
        "⅓" -> "jedna trzecia"
        "⅔" -> "dwie trzecie"
        "¼" -> "jedna czwarta"
        "¾" -> "trzy czwarte"
        "⅕" -> "jedna piąta"
        "⅖" -> "dwie piąte"
        "⅗" -> "trzy piąte"
        "⅘" -> "cztery piąte"
        "⅙" -> "jedna szósta"
        "⅚" -> "pięć szóstych"
        "⅛" -> "jedna ósma"
        "⅜" -> "trzy ósme"
        "⅝" -> "pięć ósmych"
        "⅞" -> "siedem ósmych"
        "⅐" -> "jedna siódma"
        "⅑" -> "jedna dziewiąta"
        "⅒" -> "jedna dziesiąta"
        "2½" -> "dwa i pół"
        "-2½" -> "minus dwa i pół"
        "1 1/2" -> "jeden i pół"
        "2 1/2" -> "dwa i pół"
        "3 1/4" -> "trzy i jedna czwarta"
        "5/8" -> "pięć ósmych"
        "-3/4" -> "minus trzy czwarte"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        vulgar = pynini.string_map(
            [
                ("½", "jedna druga"),
                ("⅓", "jedna trzecia"),
                ("⅔", "dwie trzecie"),
                ("¼", "jedna czwarta"),
                ("¾", "trzy czwarte"),
                ("⅕", "jedna piąta"),
                ("⅖", "dwie piąte"),
                ("⅗", "trzy piąte"),
                ("⅘", "cztery piąte"),
                ("⅙", "jedna szósta"),
                ("⅚", "pięć szóstych"),
                ("⅛", "jedna ósma"),
                ("⅜", "trzy ósme"),
                ("⅝", "pięć ósmych"),
                ("⅞", "siedem ósmych"),
                ("⅐", "jedna siódma"),
                ("⅑", "jedna dziewiąta"),
                ("⅒", "jedna dziesiąta"),
            ]
        )

        slash_fracs = pynini.string_map(
            [
                ("1/2", "jedna druga"),
                ("1/3", "jedna trzecia"),
                ("2/3", "dwie trzecie"),
                ("1/4", "jedna czwarta"),
                ("3/4", "trzy czwarte"),
                ("1/5", "jedna piąta"),
                ("2/5", "dwie piąte"),
                ("3/5", "trzy piąte"),
                ("4/5", "cztery piąte"),
                ("1/6", "jedna szósta"),
                ("5/6", "pięć szóstych"),
                ("1/7", "jedna siódma"),
                ("1/8", "jedna ósma"),
                ("3/8", "trzy ósme"),
                ("5/8", "pięć ósmych"),
                ("7/8", "siedem ósmych"),
                ("1/9", "jedna dziewiąta"),
                ("1/10", "jedna dziesiąta"),
            ]
        )

        bare_fraction = vulgar | slash_fracs

        # Mixed fractions: 2½ -> dwa i pół, 1 1/2 -> jeden i pół, 3 1/4 -> trzy i jedna czwarta
        half_sym = pynini.union("½", "1/2")
        mixed_half_tight = cardinal.graph_with_sep + pynini.cross(half_sym, " i pół")
        mixed_half_space = cardinal.graph_with_sep + pynini.cross(" " + half_sym, " i pół")
        mixed_other_tight = cardinal.graph_with_sep + pynutil.insert(" i ") + bare_fraction
        mixed_other_space = cardinal.graph_with_sep + pynini.cross(" ", " i ") + bare_fraction

        mixed = mixed_half_tight | mixed_half_space | mixed_other_tight | mixed_other_space

        prefix_sign = (
            pynini.cross(pynini.union("-", "−"), "minus ")
            | (pynini.cross("~", "około ") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "plus minus ") + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        opt_prefix = pynini.closure(prefix_sign, 0, 1)

        self.graph = (opt_prefix + (mixed | bare_fraction)).optimize()
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
