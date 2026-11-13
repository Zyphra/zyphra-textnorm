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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.tl.utils import get_abs_path

quantities = pynini.string_file(get_abs_path("data/numbers/quantities.tsv"))


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Tagalog decimals ('.' is standard decimal point, ',' groups thousands), e.g.
        "-3.75" -> decimal { negative: "true" integer_part: "tatlo" fractional_part: "pito lima" preserve_order: true }
        "1.5 milyon" -> decimal { integer_part: "isa" fractional_part: "lima" quantity: "milyon" preserve_order: true }
        "5 M" -> decimal { integer_part: "lima" quantity: "milyon" preserve_order: true }

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
            pynutil.delete(".")
            + pynutil.insert(' fractional_part: "')
            + self.graph_fractional_digits
            + pynutil.insert('"')
        )
        # Comma as decimal when not grouping three digits
        fractional_comma = (
            pynutil.delete(",")
            + pynutil.insert(' fractional_part: "')
            + pynini.difference(pynini.closure(NEMO_DIGIT, 1), NEMO_DIGIT**3) @ self.graph_fractional_digits
            + pynutil.insert('"')
        )
        quantity = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' quantity: "')
            + quantities
            + pynutil.insert('"')
        )
        integer_hundred = pynutil.insert('integer_part: "') + cardinal.graph_hundred + pynutil.insert('"')

        self.graph_decimal = integer + (fractional | fractional_comma)
        self.final_graph_wo_negative = (
            self.graph_decimal + pynini.closure(quantity, 0, 1) | integer_hundred + quantity
        ).optimize()

        optional_prefix = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true" '))
            | (pynini.cross("~", 'negative: "humigit-kumulang" ') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", 'negative: "plus-minus" ') + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )
        graph = optional_prefix + self.final_graph_wo_negative + pynutil.insert(" preserve_order: true")
        self.fst = self.add_tokens(graph).optimize()
