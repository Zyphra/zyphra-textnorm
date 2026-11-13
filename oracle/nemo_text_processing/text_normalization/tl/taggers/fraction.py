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

# Number names from Unicode CLDR release-49 (fil locale, Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Tagalog fractions, e.g.
        "2 1/2" -> fraction { integer_part: "dalawa" numerator: "isa" denominator: "dalawa" preserve_order: true }
        "3/4" -> fraction { numerator: "tatlo" denominator: "apat" preserve_order: true }
        "⅒" -> fraction { numerator: "isa" denominator: "sampu" preserve_order: true }

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
            | (pynini.cross("~", 'negative: "humigit-kumulang" ') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", 'negative: "plus-minus" ') + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )
        integer = pynutil.insert('integer_part: "') + cardinal.graph_with_sep + pynutil.insert('" ')
        slash = pynini.cross(pynini.union("/", " / ", "⁄"), '" denominator: "')
        fraction = pynutil.insert('numerator: "') + number + slash + number + pynutil.insert('"')
        vulgar = pynini.string_map(
            [
                ("½", 'numerator: "isa" denominator: "dalawa"'),
                ("¼", 'numerator: "isa" denominator: "apat"'),
                ("¾", 'numerator: "tatlo" denominator: "apat"'),
                ("⅓", 'numerator: "isa" denominator: "tatlo"'),
                ("⅔", 'numerator: "dalawa" denominator: "tatlo"'),
                ("⅕", 'numerator: "isa" denominator: "lima"'),
                ("⅖", 'numerator: "dalawa" denominator: "lima"'),
                ("⅗", 'numerator: "tatlo" denominator: "lima"'),
                ("⅘", 'numerator: "apat" denominator: "lima"'),
                ("⅙", 'numerator: "isa" denominator: "anim"'),
                ("⅚", 'numerator: "lima" denominator: "anim"'),
                ("⅛", 'numerator: "isa" denominator: "walo"'),
                ("⅜", 'numerator: "tatlo" denominator: "walo"'),
                ("⅝", 'numerator: "lima" denominator: "walo"'),
                ("⅞", 'numerator: "pito" denominator: "walo"'),
                ("⅐", 'numerator: "isa" denominator: "pito"'),
                ("⅑", 'numerator: "isa" denominator: "siyam"'),
                ("⅒", 'numerator: "isa" denominator: "sampu"'),
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
