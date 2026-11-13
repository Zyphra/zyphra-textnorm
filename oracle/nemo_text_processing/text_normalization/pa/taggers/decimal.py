# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.pa.graph_utils import GraphFst, insert_space
from nemo_text_processing.text_normalization.pa.utils import get_abs_path

quantities = pynini.string_file(get_abs_path("data/numbers/quantities.tsv"))


def get_quantity(decimal: 'pynini.FstLike', cardinal_up_to_hundred: 'pynini.FstLike') -> 'pynini.FstLike':
    """
    Returns FST that transforms either a cardinal or decimal followed by a quantity into a numeral,
    e.g. ੧ ਲੱਖ -> integer_part: "ਇੱਕ" quantity: "ਲੱਖ"
    e.g. ੧.੫ ਲੱਖ -> integer_part: "ਇੱਕ" fractional_part: "ਪੰਜ" quantity: "ਲੱਖ"

    Args:
        decimal: decimal FST
        cardinal_up_to_hundred: cardinal FST
    """
    numbers = cardinal_up_to_hundred

    res = (
        pynutil.insert("integer_part: \"")
        + numbers
        + pynutil.insert("\"")
        + insert_space
        + pynutil.insert("quantity: \"")
        + quantities
        + pynutil.insert("\"")
    )
    res |= decimal + insert_space + pynutil.insert("quantity: \"") + quantities + pynutil.insert("\"")
    return res


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying decimal in Punjabi, e.g.
        -੧੨.੫੦੦੬ ਕਰੋੜ -> decimal { negative: "true" integer_part: "ਬਾਰਾਂ"  fractional_part: "ਪੰਜ ਸਿਫ਼ਰ ਸਿਫ਼ਰ ਛੇ" quantity: "ਕਰੋੜ" }
        ੧ ਕਰੋੜ -> decimal { integer_part: "ਇੱਕ" quantity: "ਕਰੋੜ" }

    cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        graph_digit = cardinal.digit | cardinal.zero
        cardinal_graph = cardinal.graph_without_leading_zeros

        self.graph = graph_digit + pynini.closure(insert_space + graph_digit).optimize()

        point = pynutil.delete(".")

        sign_prefix = (
            pynini.cross(pynini.union("-", "−"), '"true"')
            | (pynini.cross("~", '"approx"') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", '"pm"') + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + sign_prefix + insert_space,
            0,
            1,
        )

        self.graph_fractional = pynutil.insert("fractional_part: \"") + self.graph + pynutil.insert("\"")
        self.graph_integer = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")

        final_graph_wo_sign = self.graph_integer + point + insert_space + self.graph_fractional

        quantity = pynutil.insert("quantity: \"") + quantities + pynutil.insert("\"")
        quantity_part = pynini.closure(
            pynini.closure(pynutil.delete(" "), 0, 1) + insert_space + quantity, 0, 1
        )

        # Quantity with integer alone (e.g. 2 ਲੱਖ) or with decimal (e.g. 1.5 ਲੱਖ)
        graph_with_quantity = (
            (self.graph_integer + insert_space + quantity)
            | (final_graph_wo_sign + quantity_part)
        )

        final_graph = optional_graph_negative + (final_graph_wo_sign | graph_with_quantity)
        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
