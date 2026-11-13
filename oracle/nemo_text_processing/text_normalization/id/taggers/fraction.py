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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fractions, e.g.
        "2 1/2" -> fraction { integer_part: "dua" numerator: "satu" denominator: "dua" preserve_order: true }
        "3/4" -> fraction { numerator: "tiga" denominator: "empat" preserve_order: true }
        "⅒" -> fraction { numerator: "satu" denominator: "sepuluh" preserve_order: true }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)
        number = cardinal.graph
        optional_prefix = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true" '))
            | (pynini.cross("~", 'negative: "sekitar" ') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", 'negative: "kurang lebih" ') + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )
        integer = pynutil.insert('integer_part: "') + cardinal.graph_with_sep + pynutil.insert('" ')
        slash = pynini.cross(pynini.union("/", " / ", "⁄"), '" denominator: "')
        fraction = pynutil.insert('numerator: "') + number + slash + number + pynutil.insert('"')
        vulgar = pynini.string_map(
            [
                ("½", 'numerator: "satu" denominator: "dua"'),
                ("¼", 'numerator: "satu" denominator: "empat"'),
                ("¾", 'numerator: "tiga" denominator: "empat"'),
                ("⅓", 'numerator: "satu" denominator: "tiga"'),
                ("⅔", 'numerator: "dua" denominator: "tiga"'),
                ("⅕", 'numerator: "satu" denominator: "lima"'),
                ("⅖", 'numerator: "dua" denominator: "lima"'),
                ("⅗", 'numerator: "tiga" denominator: "lima"'),
                ("⅘", 'numerator: "empat" denominator: "lima"'),
                ("⅙", 'numerator: "satu" denominator: "enam"'),
                ("⅚", 'numerator: "lima" denominator: "enam"'),
                ("⅛", 'numerator: "satu" denominator: "delapan"'),
                ("⅜", 'numerator: "tiga" denominator: "delapan"'),
                ("⅝", 'numerator: "lima" denominator: "delapan"'),
                ("⅞", 'numerator: "tujuh" denominator: "delapan"'),
                ("⅐", 'numerator: "satu" denominator: "tujuh"'),
                ("⅑", 'numerator: "satu" denominator: "sembilan"'),
                ("⅒", 'numerator: "satu" denominator: "sepuluh"'),
            ]
        )
        graph = (
            optional_prefix
            + pynini.closure(integer + pynutil.delete(" "), 0, 1)
            + fraction
            | optional_prefix + pynini.closure(integer + pynini.closure(pynutil.delete(" "), 0, 1), 0, 1) + vulgar
        )
        graph += pynutil.insert(" preserve_order: true")
        self.fst = self.add_tokens(graph).optimize()
