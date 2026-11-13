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

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)


class MeasureFst(GraphFst):
    """
    Finite state transducer for verbalizing measure, e.g.
        measure { cardinal { negative: "true" integer: "పన్నెండు" } units: "కిలోగ్రాములు" } -> ఋణ పన్నెండు కిలోగ్రాములు
        measure { decimal { integer_part: "రెండు" fractional_part: "ఐదు" } units: "కిలోమీటర్లు" } -> రెండు దశాంశం ఐదు కిలోమీటర్లు
        measure { morphosyntactic_features: "గంటకు" cardinal { integer: "అరవై" } units: "కిలోమీటర్లు" } -> గంటకు అరవై కిలోమీటర్లు

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="verbalize")

        prefix = pynini.closure(
            pynutil.delete("morphosyntactic_features: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\"")
            + delete_space
            + insert_space,
            0,
            1,
        )
        unit = pynutil.delete("units: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        graph_decimal = (
            pynutil.delete("decimal {") + delete_space + decimal.numbers + delete_space + pynutil.delete("}")
        )
        graph_cardinal = (
            pynutil.delete("cardinal {") + delete_space + cardinal.numbers + delete_space + pynutil.delete("}")
        )

        preserve_order = pynini.closure(
            delete_space + pynutil.delete("preserve_order:") + delete_space + pynutil.delete("true"), 0, 1
        )
        graph = prefix + (graph_cardinal | graph_decimal) + delete_space + insert_space + unit + preserve_order

        self.decimal = graph_decimal
        delete_tokens = self.delete_tokens(graph + delete_space)
        self.fst = delete_tokens.optimize()
