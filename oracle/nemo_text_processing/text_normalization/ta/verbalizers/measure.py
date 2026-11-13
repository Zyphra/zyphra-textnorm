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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)


class MeasureFst(GraphFst):
    """
    Finite state transducer for verbalizing measure, e.g.
        measure { cardinal { negative: "true" integer: "பன்னிரண்டு" } units: "கிலோகிராம்" } -> மைனஸ் பன்னிரண்டு கிலோகிராம்
        measure { decimal { integer_part: "இரண்டு" fractional_part: "ஐந்து" } units: "கிலோமீட்டர்" } -> இரண்டு புள்ளி ஐந்து கிலோமீட்டர்
        measure { morphosyntactic_features: "ஒரு மணிநேரத்திற்கு" cardinal { integer: "அறுபது" } units: "கிலோமீட்டர்" } -> ஒரு மணிநேரத்திற்கு அறுபது கிலோமீட்டர்

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
