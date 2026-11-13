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
    NEMO_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


def get_quantity(decimal_graph: "pynini.FstLike", cardinal_graph: "pynini.FstLike") -> "pynini.FstLike":
    """
    Transforms either a cardinal or decimal followed by a quantity word into a numeral,
    e.g. 10 მილიარდი -> integer_part: "ათი" quantity: "მილიარდი"
    e.g. 30.2 მილიარდი -> integer_part: "ოცდაათი" fractional_part: "ორი" quantity: "მილიარდი"
    """
    quantities = (
        pynini.string_file(get_abs_path("data/numbers/quantities.tsv"))
        | pynini.string_map([("ათასი", "ათასი"), ("ათას", "ათასი")])
    )
    delete_separator = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)
    numbers = pynini.closure(NEMO_DIGIT, 1, 6) @ cardinal_graph
    numbers = pynini.cdrewrite(pynutil.delete(delete_separator), "", "", NEMO_SIGMA) @ numbers

    res = (
        pynutil.insert('integer_part: "')
        + numbers
        + pynutil.insert('"')
        + NEMO_SPACE
        + pynutil.insert('quantity: "')
        + quantities
        + pynutil.insert('"')
    )
    res |= decimal_graph + NEMO_SPACE + pynutil.insert('quantity: "') + quantities + pynutil.insert('"')
    return res


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Georgian decimals, e.g.
        0.2 -> decimal { integer_part: "ნული" fractional_part: "ორი" }
        3,14 -> decimal { integer_part: "სამი" fractional_part: "თოთხმეტი" }
        30.2 მილიარდი -> decimal { integer_part: "ოცდაათი" fractional_part: "ორი" quantity: "მილიარდი" }
        -15.5 -> decimal { negative: "true" integer_part: "თხუთმეტი" fractional_part: "ხუთი" }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        delete_separator = pynutil.delete(pynini.union(".", ","))
        optional_graph_negative = pynini.closure(
            pynutil.insert('negative: "true" ') + pynutil.delete(pynini.union("-", "−")),
            0,
            1,
        )

        integers = cardinal.all_nums_no_tokens
        leading_zeros = pynini.closure(pynini.cross("0", "ნული "), 0, 5)
        fractional = (
            leading_zeros + ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 5)) @ integers
        ) | pynini.cross("0", "ნული")

        graph_fractional = pynutil.insert('fractional_part: "') + fractional.optimize() + pynutil.insert('"')
        graph_integer = pynutil.insert('integer_part: "') + integers + pynutil.insert('"')
        final_graph_wo_sign = graph_integer + delete_separator + insert_space + graph_fractional

        final_graph_wo_negative = final_graph_wo_sign | get_quantity(final_graph_wo_sign, integers)
        self.final_graph_wo_negative = final_graph_wo_negative.optimize()

        final_graph = optional_graph_negative + final_graph_wo_negative
        self.final_graph = final_graph.optimize()

        self.fst = self.add_tokens(final_graph).optimize()
