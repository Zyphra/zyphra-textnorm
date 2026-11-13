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

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    NEMO_SIGMA,
)


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian and international telephone numbers.
    e.g. +359 2 987 6543
         +44 20 7946 0958
         (415) 555-0199
         +1-800-555-0199
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        card = cardinal.number

        # Plus prefix
        plus = pynini.cross("+", "плюс ")

        # Separators between number parts: space, hyphen, period
        sep = pynutil.delete(pynini.union(" ", "-", ".")) + pynutil.insert(" ")

        # Digits group (1 to 4 digits): e.g. "359", "2", "987", "6543", "0199"
        # Digit-by-digit or small number group:
        d_map = pynini.string_map([
            ("0", "нула"), ("1", "едно"), ("2", "две"), ("3", "три"), ("4", "четири"),
            ("5", "пет"), ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
        ])
        group_digit = pynini.closure(NEMO_DIGIT, 1, 4) @ (
            # If starts with 0: read as leading zeros
            (pynini.cross("0", "нула") + pynini.closure(pynutil.insert(" ") + d_map, 1, 3))
            | card
            | d_map
        )

        # Parenthesized area code: "(415)"
        paren_area = (
            pynutil.delete("(")
            + group_digit
            + pynutil.delete(")")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(" ")
        )

        # Phone structures:
        # +359 2 987 6543
        intl_phone = (
            plus
            + group_digit
            + sep
            + group_digit
            + sep
            + group_digit
            + sep
            + group_digit
            + pynini.closure(sep + group_digit, 0, 2)
        )

        # (415) 555-0199
        us_phone = (
            pynini.closure(plus + pynini.cross("1", "едно") + sep, 0, 1)
            + paren_area
            + group_digit
            + sep
            + group_digit
        )

        # Standard 3-part or 4-part phone: "+1-800-555-0199" or "02 987 6543"
        hyphen_phone = (
            pynini.closure(plus, 0, 1)
            + group_digit
            + sep
            + group_digit
            + sep
            + group_digit
            + sep
            + group_digit
        )

        all_phones = (intl_phone | us_phone | hyphen_phone).optimize()
        self.all_phones = all_phones

        graph = pynutil.insert('name: "') + convert_space(all_phones) + pynutil.insert('"')
        self.fst = graph.optimize()
