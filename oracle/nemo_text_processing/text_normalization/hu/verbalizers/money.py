# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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
    Finite state transducer for verbalizing money, e.g.
        money { currency_maj: "euró" integer_part: "egy"} -> "egy euró"
        money { currency_maj: "euró" integer_part: "egy" fractional_part: "egy ezred"} -> "egy egész egy ezred euro"
        money { integer_part: "egy" currency_maj: "font" fractional_part: "negyven" preserve_order: true} -> "egy font negyven"
        money { integer_part: "egy" currency_maj: "font" fractional_part: "negyven" currency_min: "penny" preserve_order: true} -> "egy font negyven penny"
        money { fractional_part: "egy" currency_min: "penny" preserve_order: true} -> "egy penny"
        money { currency_maj: "font" integer_part: "nulla" fractional_part: "null eins" quantity: "millió"} -> "null egész egy század millió font"

    Args:
        decimal: GraphFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="verbalize", deterministic=deterministic)

        keep_space = pynini.accep(" ")
        optional_sign = pynini.closure(pynini.cross("negative: \"true\"", "mínusz ") + delete_space, 0, 1)

        maj = pynutil.delete("currency_maj: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        min = pynutil.delete("currency_min: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        fractional_part = (
            pynutil.delete("fractional_part: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        )

        integer_part = pynutil.delete("integer_part: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        optional_add_and = pynini.closure(pynutil.insert("és "), 0, 1)

        #  *** currency_maj
        graph_integer = optional_sign + integer_part + keep_space + maj + pynini.closure(delete_preserve_order, 0, 1)

        #  *** currency_maj + (***) | ((und) *** current_min)
        minor_part = fractional_part | (fractional_part + keep_space + min)
        if not deterministic:
            minor_part |= optional_add_and + fractional_part + keep_space + min
        graph_integer_with_minor = (
            optional_sign
            + integer_part
            + keep_space
            + maj
            + keep_space
            + minor_part
            + pynini.closure(delete_preserve_order, 0, 1)
        )

        # *** komma *** currency_maj (decimal.numbers already begins with optional_sign)
        graph_decimal = decimal.numbers + keep_space + maj + pynini.closure(delete_preserve_order, 0, 1)

        # *** current_min
        graph_minor = (
            optional_sign + fractional_part + keep_space + min + pynini.closure(delete_preserve_order, 0, 1)
        )

        graph = graph_integer | graph_integer_with_minor | graph_decimal | graph_minor

        per_unit = (
            delete_space
            + pynutil.delete("morphosyntactic_features: \"")
            + pynutil.insert(" ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\"")
            + delete_space
        )
        graph += pynini.closure(per_unit, 0, 1)

        delete_tokens = self.delete_tokens(graph)
        self.fst = delete_tokens.optimize()
