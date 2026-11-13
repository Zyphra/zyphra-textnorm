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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    GraphFst,
    insert_space,
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for verbalizing decimal, e.g.
        decimal { negative: "true" integer_part: "രണ്ട്" fractional_part: "അഞ്ച്" } -> മൈനസ് രണ്ട് ദശാംശം അഞ്ച്
        decimal { integer_part: "ഒന്ന്" fractional_part: "അഞ്ച്" quantity: "കോടി" } -> ഒന്ന് ദശാംശം അഞ്ച് കോടി
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="decimal", kind="verbalize", deterministic=deterministic)

        delete_space = pynutil.delete(" ")
        self.optional_sign = pynini.closure(pynini.cross('negative: "true"', MINUS) + delete_space, 0, 1)
        self.integer = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        self.fractional_default = (
            pynutil.delete('fractional_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        )

        self.fractional = pynutil.insert(" ദശാംശം ") + self.fractional_default

        self.quantity = (
            delete_space + insert_space + pynutil.delete('quantity: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        )
        self.optional_quantity = pynini.closure(self.quantity, 0, 1)

        graph = self.optional_sign + (
            self.integer + self.quantity | self.integer + delete_space + self.fractional + self.optional_quantity
        )

        self.numbers = graph
        self.fst = self.delete_tokens(graph).optimize()
