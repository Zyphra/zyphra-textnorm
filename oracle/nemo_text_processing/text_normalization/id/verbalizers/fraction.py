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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_NOT_QUOTE, NEMO_SIGMA, GraphFst, delete_preserve_order


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing fractions, e.g.
        fraction { integer_part: "dua" numerator: "satu" denominator: "dua" } -> dua setengah
        fraction { numerator: "tiga" denominator: "empat" } -> tiga perempat
        fraction { numerator: "satu" denominator: "sepuluh" } -> sepersepuluh
        fraction { numerator: "dua" denominator: "tujuh" } -> dua per tujuh

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)
        prefix_sign = (
            pynini.cross('negative: "true" ', "negatif ")
            | pynini.cross('negative: "sekitar" ', "sekitar ")
            | pynini.cross('negative: "kurang lebih" ', "kurang lebih ")
        )
        optional_sign = pynini.closure(prefix_sign, 0, 1)
        integer = (
            pynutil.delete('integer_part: "')
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('" ')
            + pynutil.insert(" ")
        )
        numerator = pynutil.delete('numerator: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('" ')
        denominator = pynutil.delete('denominator: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        not_one = pynini.difference(NEMO_SIGMA, "satu")
        special = pynini.string_map(
            [
                ("satu|dua", "setengah"),
                ("satu|tiga", "sepertiga"),
                ("satu|empat", "seperempat"),
                ("satu|sepuluh", "sepersepuluh"),
                ("satu|seratus", "seperseratus"),
                ("satu|seribu", "seperseribu"),
            ]
        )
        special |= not_one + pynini.cross("|tiga", " pertiga") | not_one + pynini.cross("|empat", " perempat")
        general = NEMO_SIGMA + pynini.cross("|", " per ") + NEMO_SIGMA
        pair = (numerator + pynutil.insert("|") + denominator) @ (pynutil.add_weight(special, -0.1) | general)
        self.graph = optional_sign + pynini.closure(integer, 0, 1) + pair
        self.fst = self.delete_tokens(self.graph + delete_preserve_order).optimize()
