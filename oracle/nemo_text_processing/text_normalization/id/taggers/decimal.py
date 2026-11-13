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

# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.id.utils import get_abs_path

quantities = pynini.string_file(get_abs_path("data/numbers/quantities.tsv"))


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Indonesian decimals ("," is the decimal point, "." groups thousands), e.g.
        "-3,75" -> decimal { negative: "true" integer_part: "tiga" fractional_part: "tujuh lima" preserve_order: true }
        "1,5 juta" -> decimal { integer_part: "satu" fractional_part: "lima" quantity: "juta" preserve_order: true }
        "2.5" -> decimal { integer_part: "dua" point_part: "lima" preserve_order: true }
        "5 jt" -> decimal { integer_part: "lima" quantity: "juta" preserve_order: true }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)
        self.graph_fractional_digits = (cardinal.digit + pynini.closure(insert_space + cardinal.digit)).optimize()

        integer = pynutil.insert('integer_part: "') + cardinal.graph_with_sep + pynutil.insert('"')
        fractional = (
            pynutil.delete(",")
            + pynutil.insert(' fractional_part: "')
            + self.graph_fractional_digits
            + pynutil.insert('"')
        )
        quantity = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' quantity: "')
            + quantities
            + pynutil.insert('"')
        )
        integer_hundred = pynutil.insert('integer_part: "') + cardinal.graph_hundred + pynutil.insert('"')

        # "2.5" with an ungrouped integer and not three digits after the point: CLDR id "x.x: << titik >>"
        point_fractional = (
            pynutil.delete(".")
            + pynutil.insert(' point_part: "')
            + pynini.difference(pynini.closure(NEMO_DIGIT, 1), NEMO_DIGIT**3) @ self.graph_fractional_digits
            + pynutil.insert('"')
        )
        integer_plain = pynutil.insert('integer_part: "') + cardinal.graph + pynutil.insert('"')
        self.graph_decimal = integer + fractional | pynutil.add_weight(integer_plain + point_fractional, 0.05)
        self.final_graph_wo_negative = (
            self.graph_decimal + pynini.closure(quantity, 0, 1) | integer_hundred + quantity
        ).optimize()
        optional_prefix = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true" '))
            | (pynini.cross("~", 'negative: "sekitar" ') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", 'negative: "kurang lebih" ') + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )
        graph = optional_prefix + self.final_graph_wo_negative + pynutil.insert(" preserve_order: true")
        self.fst = self.add_tokens(graph).optimize()
