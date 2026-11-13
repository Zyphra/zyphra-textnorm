# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, NEMO_SPACE, GraphFst, insert_space
from nemo_text_processing.text_normalization.ru.taggers.number_names import (
    ENDS_IN,
    QUANTITY_WORDS,
    magnitude,
)

# denominator of the fractional part by its number of digits: singular after a numerator ending in 1, else plural
_DENOMINATORS = {
    1: ("десятая", "десятых"),
    2: ("сотая", "сотых"),
    3: ("тысячная", "тысячных"),
    4: ("десятитысячная", "десятитысячных"),
    5: ("стотысячная", "стотысячных"),
    6: ("миллионная", "миллионных"),
}


def quantity_graph(after_decimal: bool) -> dict:
    """Written quantity word -> spoken form, per count category of the number before it ("5 млн" -> "миллионов",
    "2 тыс" -> "тысячи"); after a decimal number always the genitive singular ("2,5 млн" -> "миллиона")."""
    out = {}
    for category in ("one", "few", "many"):
        pairs = []
        for level, written in QUANTITY_WORDS.items():
            forms = magnitude(level)
            spoken = forms["gen"] if after_decimal else forms[category]
            pairs += [(w, spoken) for w in written]
        out[category] = pynini.string_map(pairs).optimize()
    return out


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying decimal, e.g.
        "1,08" -> tokens { decimal { integer_part: "одна целая" fractional_part: "восемь сотых" } }
        "2,5 млн" -> tokens { decimal { integer_part: "две целых" fractional_part: "пять десятых" quantity: "миллиона" } }

    The integer part is a feminine cardinal followed by "целая" (ending in 1, not 11) or "целых"; the fractional part is
    a feminine cardinal followed by the denominator agreeing with it ("одна десятая", "две десятых").

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
                for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = False):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        feminine = cardinal.feminine
        # "одна целая", "две целых" (integer parts up to 12 digits, optionally grouped)
        self.integer_part = (
            pynini.compose(ENDS_IN["one"], feminine) + pynutil.insert(" целая")
            | pynini.compose(ENDS_IN["few"] | ENDS_IN["many"], feminine) + pynutil.insert(" целых")
        ).optimize()
        graph_integer = pynutil.insert("integer_part: \"") + self.integer_part + pynutil.insert("\"")

        # fractional part: up to 6 digits read as a feminine number + the denominator, singular after a numerator
        # ending in 1 (not 11), plural otherwise ("одна десятая", "двадцать одна сотая", "две десятых")
        one, other = "\ue041", "\ue042"
        count = pynini.compose(ENDS_IN["one"], feminine) + pynutil.insert(one) | pynini.compose(
            ENDS_IN["few"] | ENDS_IN["many"], feminine
        ) + pynutil.insert(other)
        words = pynini.closure(pynini.union(*"абвгдеёжзийклмнопрстуфхцчшщъыьэюя ")).optimize()
        graph_fractional = None
        for digits, (singular, plural) in _DENOMINATORS.items():
            resolve = words + (pynini.cross(one, " " + singular) | pynini.cross(other, " " + plural))
            part = pynini.compose(pynini.compose(NEMO_DIGIT**digits, count), resolve)
            graph_fractional = part if graph_fractional is None else graph_fractional | part
        self.graph_fractional = graph_fractional.optimize()
        graph_fractional = pynutil.insert("fractional_part: \"") + self.graph_fractional + pynutil.insert("\"")

        quantity = quantity_graph(after_decimal=True)["one"]
        optional_quantity = pynini.closure(
            pynutil.add_weight(
                pynini.cross(pynini.closure(NEMO_SPACE, 0, 1), " ")
                + pynutil.insert("quantity: \"")
                + quantity
                + pynutil.insert("\""),
                -0.1,
            ),
            0,
            1,
        )
        self.final_graph_wo_quantity = (
            cardinal.optional_graph_negative + graph_integer + pynini.cross(",", " ") + graph_fractional
        ).optimize()
        self.final_graph = (self.final_graph_wo_quantity + optional_quantity).optimize()
        # "99.9%", "1.5 кг": a point decimal is read like a comma one when the integer part has at most 3 digits (so
        # "2.300" stays a grouped thousand) and it is not a date ("01.05" is the date tagger's).
        self.point_decimal = (
            cardinal.optional_graph_negative
            + pynutil.insert("integer_part: \"")
            + pynini.compose(NEMO_DIGIT**(1, 3), self.integer_part)
            + pynutil.insert("\"")
            + pynini.cross(".", " ")
            + pynutil.insert("fractional_part: \"")
            + pynini.compose(NEMO_DIGIT**(1, 2), self.graph_fractional)
            + pynutil.insert("\"")
        ).optimize()
        self.point_decimal_with_quantity = (self.point_decimal + optional_quantity).optimize()

        self.fst = self.add_tokens(
            self.final_graph | pynutil.add_weight(self.point_decimal_with_quantity, 0.08)
        ).optimize()
