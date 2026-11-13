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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.bn.graph_utils import NEMO_NOT_QUOTE, GraphFst, delete_space, insert_space


class MeasureFst(GraphFst):
    """
    Finite state transducer for verbalizing measure, e.g.
        measure { cardinal { negative: "true" integer: "বারো" } units: "কিলোগ্রাম" } -> ঋণ বারো কিলোগ্রাম
        measure { decimal { integer_part: "বারো" fractional_part: "দুই" } units: "কিলোগ্রাম" } -> বারো দশমিক দুই কিলোগ্রাম


    Args:
        decimal: DecimalFst
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="verbalize")

        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", "\"true\"") + insert_space,
            0,
            1,
        )

        unit = (
            pynutil.delete("units: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\"")
            + delete_space
        )

        graph_decimal = (
            pynutil.delete("decimal {")
            + delete_space
            + optional_graph_negative
            + delete_space
            + decimal.numbers
            + delete_space
            + pynutil.delete("}")
        )

        graph_cardinal = (
            pynutil.delete("cardinal {")
            + delete_space
            + optional_graph_negative
            + delete_space
            + cardinal.numbers
            + delete_space
            + pynutil.delete("}")
        )

        graph = (graph_cardinal | graph_decimal) + delete_space + insert_space + unit

        self.decimal = graph_decimal
        delete_tokens = self.delete_tokens(graph)
        self.fst = delete_tokens.optimize()
