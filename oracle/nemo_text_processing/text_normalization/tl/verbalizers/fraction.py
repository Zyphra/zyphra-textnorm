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
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_preserve_order,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog fractions, e.g.
        fraction { integer_part: "dalawa" numerator: "isa" denominator: "dalawa" } -> dalawa at kalahati
        fraction { numerator: "tatlo" denominator: "apat" } -> tatlong-kapat
        fraction { numerator: "isa" denominator: "sampu" } -> isang-kasampu
        fraction { numerator: "lima" denominator: "walo" } -> limang-kawalo
        fraction { numerator: "dalawa" denominator: "pito" } -> dalawa sa pito

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)
        prefix_sign = (
            pynini.cross('negative: "true" ', "minus ")
            | pynini.cross('negative: "humigit-kumulang" ', "humigit-kumulang ")
            | pynini.cross('negative: "plus-minus" ', "plus-minus ")
        )
        optional_sign = pynini.closure(prefix_sign, 0, 1)
        integer = (
            pynutil.delete('integer_part: "')
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('" ')
            + pynutil.insert(" at ")
        )
        numerator = pynutil.delete('numerator: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('" ')
        denominator = pynutil.delete('denominator: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        special = pynini.string_map(
            [
                ("isa|dalawa", "kalahati"),
                ("isa|tatlo", "isang-katlo"),
                ("dalawa|tatlo", "dalawang-katlo"),
                ("isa|apat", "isang-kapat"),
                ("tatlo|apat", "tatlong-kapat"),
                ("isa|lima", "isang-kalima"),
                ("dalawa|lima", "dalawang-kalima"),
                ("tatlo|lima", "tatlong-kalima"),
                ("apat|lima", "apat na kalima"),
                ("isa|anim", "isang-kaanim"),
                ("lima|anim", "limang-kaanim"),
                ("isa|pito", "isang-kapito"),
                ("isa|walo", "isang-kawalo"),
                ("tatlo|walo", "tatlong-kawalo"),
                ("lima|walo", "limang-kawalo"),
                ("pito|walo", "pitong-kawalo"),
                ("isa|siyam", "isang-kasiyam"),
                ("isa|sampu", "isang-kasampu"),
            ]
        )
        general = pynini.closure(NEMO_CHAR, 1) + pynini.cross("|", " sa ") + pynini.closure(NEMO_CHAR, 1)
        pair = (numerator + pynutil.insert("|") + denominator) @ (pynutil.add_weight(special, -0.1) | general)
        self.graph = optional_sign + pynini.closure(integer, 0, 1) + pair
        self.fst = self.delete_tokens(self.graph + delete_preserve_order).optimize()
