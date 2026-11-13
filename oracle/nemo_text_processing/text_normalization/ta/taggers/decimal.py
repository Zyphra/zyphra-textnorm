# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ta.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.ta.utils import get_abs_path

quantities = pynini.string_file(get_abs_path("data/numbers/quantities.tsv"))


def get_quantity(decimal: 'pynini.FstLike', cardinal_up_to_hundred: 'pynini.FstLike') -> 'pynini.FstLike':
    """
    Returns FST that transforms either a cardinal or decimal followed by a quantity into a numeral,
    e.g. 5 லட்சம் -> integer_part: "ஐந்து" quantity: "லட்சம்"
    e.g. 1.5 கோடி -> integer_part: "ஒன்று" fractional_part: "ஐந்து" quantity: "கோடி"

    Args:
        decimal: decimal FST
        cardinal_up_to_hundred: cardinal FST
    """
    numbers = cardinal_up_to_hundred
    delete_space = pynini.closure(pynutil.delete(" "), 0, 1)

    res = (
        pynutil.insert("integer_part: \"")
        + numbers
        + pynutil.insert("\"")
        + delete_space
        + insert_space
        + pynutil.insert("quantity: \"")
        + quantities
        + pynutil.insert("\"")
    )
    res |= decimal + delete_space + insert_space + pynutil.insert("quantity: \"") + quantities + pynutil.insert("\"")
    return res


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying decimal, e.g.
        -12.5006 -> decimal { negative: "true" integer_part: "பன்னிரண்டு" fractional_part: "ஐந்து பூஜ்யம் பூஜ்யம் ஆறு" }
        1.5 கோடி -> decimal { integer_part: "ஒன்று" fractional_part: "ஐந்து" quantity: "கோடி" }

    cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        delete_space = pynini.closure(pynutil.delete(" "), 0, 1)

        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", "\"true\" ") + delete_space, 0, 1
        )

        self.graph = cardinal.single_digits_graph
        self.graph_fractional = pynutil.insert("fractional_part: \"") + self.graph + pynutil.insert("\"")
        self.graph_integer = pynutil.insert("integer_part: \"") + cardinal.final_graph + pynutil.insert("\"")

        point = pynutil.delete(".")

        graph_decimal = self.graph_integer + point + insert_space + self.graph_fractional

        self.final_graph_wo_sign = graph_decimal | get_quantity(graph_decimal, cardinal.up_to_999)

        final_graph = self.optional_graph_negative + self.final_graph_wo_sign

        self.final_graph = final_graph
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
