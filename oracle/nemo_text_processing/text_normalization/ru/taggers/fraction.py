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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.ru.taggers.number_names import ENDS_IN

_NON_ZERO = pynini.difference(NEMO_DIGIT, "0").optimize()


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fractions, e.g.
        "3/4" -> fraction { numerator: "три" denominator: "четвертых" }
        "-2 1/2" -> fraction { negative: "true" integer_part: "две целых" numerator: "одна" denominator: "вторая" }

    Numerators are nominative feminine; the denominator is the feminine nominative singular ordinal when the
    numerator ends in 1 (but not 11) and the genitive plural ordinal otherwise. The integer part of a mixed number
    is followed by "целая" (ending in 1, not 11) or "целых".

    Args:
        number_names: number names built by number_names.get_number_names()
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, number_names: dict, deterministic: bool = False):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        up_to_3_digits = pynini.union("0", _NON_ZERO + pynini.closure(NEMO_DIGIT, 0, 2))
        up_to_6_digits = _NON_ZERO + pynini.closure(NEMO_DIGIT, 0, 5)
        ends_in_one = ENDS_IN["one"]
        not_ends_in_one = ENDS_IN["few"] | ENDS_IN["many"]
        feminine = number_names['cardinal']['fem']

        numerator = pynini.compose(up_to_3_digits, feminine)

        denominator_digits = pynini.difference(up_to_3_digits, pynini.union("0", "1")) | pynini.union(
            "1000", "10000", "100000", "1000000"
        )
        denominator_singular = pynini.compose(denominator_digits, number_names['ordinal']['fem_nom']).optimize()
        denominator_plural = pynini.compose(denominator_digits, number_names['ordinal']['pl_gen']).optimize()

        def field(name, graph):
            return pynutil.insert(f"{name}: \"") + graph + pynutil.insert("\"")

        fraction = (
            pynini.compose(ends_in_one, field("numerator", numerator))
            + pynini.cross("/", " ")
            + field("denominator", denominator_singular)
        ) | (
            pynini.compose(not_ends_in_one, field("numerator", numerator))
            + pynini.cross("/", " ")
            + field("denominator", denominator_plural)
        )

        vulgar_map = pynini.string_map(
            [
                ("¼", "1/4"),
                ("½", "1/2"),
                ("¾", "3/4"),
                ("⅐", "1/7"),
                ("⅑", "1/9"),
                ("⅒", "1/10"),
                ("⅓", "1/3"),
                ("⅔", "2/3"),
                ("⅕", "1/5"),
                ("⅖", "2/5"),
                ("⅗", "3/5"),
                ("⅘", "4/5"),
                ("⅙", "1/6"),
                ("⅚", "5/6"),
                ("⅛", "1/8"),
                ("⅜", "3/8"),
                ("⅝", "5/8"),
                ("⅞", "7/8"),
            ]
        )
        vulgar_fraction = pynini.compose(vulgar_map, fraction).optimize()

        integer = pynini.compose(up_to_6_digits, feminine)
        integer = pynini.compose(ends_in_one, integer + pynutil.insert(" целая")) | pynini.compose(
            not_ends_in_one, integer + pynutil.insert(" целых")
        )
        integer_part = field("integer_part", integer)

        negative = pynini.closure(pynutil.insert("negative: ") + pynini.cross("-", "\"true\"") + insert_space, 0, 1)
        graph = negative + (
            pynini.closure(integer_part + pynini.accep(" "), 0, 1) + fraction
            | pynini.closure(integer_part + pynini.cross(pynini.closure(" ", 0, 1), " "), 0, 1) + vulgar_fraction
        )
        self.fst = self.add_tokens(graph).optimize()
