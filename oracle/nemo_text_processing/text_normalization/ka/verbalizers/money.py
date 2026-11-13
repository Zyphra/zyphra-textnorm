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
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_preserve_order,
    delete_space,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing money in Georgian, e.g.
        money { integer_part: "ათი" currency: "ლარი" } -> ათი ლარი
        money { integer_part: "ათი" currency_maj: "ლარი" fractional_part: "ორმოცდაათი" currency_min: "თეთრი" }
            -> ათი ლარი და ორმოცდაათი თეთრი
        money { integer_part: "ორი" fractional_part: "ხუთი" quantity: "მილიონი" currency: "დოლარი" }
            -> ორი მთელი ხუთი მილიონი დოლარი
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="money", kind="verbalize", deterministic=deterministic)

        def field(name):
            return pynutil.delete(f'{name}: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        optional_sign = pynini.closure(
            pynutil.delete('negative: "true"') + delete_space + pynutil.insert("მინუს "),
            0,
            1,
        )

        integer = field("integer_part")
        fractional = delete_space + pynutil.insert(" მთელი ") + field("fractional_part")
        quantity = delete_space + pynutil.insert(" ") + field("quantity")
        currency = delete_space + pynutil.insert(" ") + (field("currency") | field("currency_maj"))

        minor_num = field("fractional_part")
        minor_unit = delete_space + pynutil.insert(" ") + field("currency_min")

        per_unit = delete_space + pynutil.insert(" ") + field("morphosyntactic_features")
        optional_per = pynini.closure(per_unit, 0, 1)

        amount_simple = integer + pynini.closure(fractional, 0, 1) + pynini.closure(quantity, 0, 1) + currency

        major_minor = (
            integer
            + currency
            + delete_space
            + pynutil.insert(" და ")
            + minor_num
            + minor_unit
        )

        minor_only = minor_num + minor_unit

        body = amount_simple | major_minor | minor_only
        graph = optional_sign + body + optional_per + delete_preserve_order

        self.fst = self.delete_tokens(graph).optimize()
