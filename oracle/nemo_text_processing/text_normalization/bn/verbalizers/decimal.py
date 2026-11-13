# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.bn.graph_utils import MINUS, NEMO_NOT_QUOTE, GraphFst, insert_space
from nemo_text_processing.text_normalization.bn.taggers.decimal import quantities

_SIGN_PREFIX = (
    pynini.cross('negative: "true"', MINUS)
    | pynini.cross('negative: "approx"', "প্রায় ")
    | pynini.cross('negative: "pm"', "যোগ বা বিয়োগ ")
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying decimal, e.g.
        decimal { negative: "true" integer_part: "বারো"  fractional_part: "পাঁচ শূন্য শূন্য ছয়" } -> ঋণ বারো দশমিক পাঁচ শূন্য শূন্য ছয়
        decimal { integer_part: "বারো" quantity: "কোটি" } -> বারো কোটি

    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        delete_space = pynutil.delete(" ")
        self.optional_sign = pynini.closure(_SIGN_PREFIX + delete_space, 0, 1)
        self.integer = pynutil.delete("integer_part: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        self.fractional_default = (
            pynutil.delete("fractional_part: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        )

        self.fractional = pynutil.insert(" দশমিক ") + self.fractional_default

        self.quantity = (
            delete_space + insert_space + pynutil.delete("quantity: \"") + quantities + pynutil.delete("\"")
        )
        self.optional_quantity = pynini.closure(self.quantity, 0, 1)

        graph = self.optional_sign + (
            self.integer + self.quantity | self.integer + delete_space + self.fractional + self.optional_quantity
        )

        self.numbers = graph
        delete_tokens = self.delete_tokens(graph)
        self.fst = delete_tokens.optimize()
