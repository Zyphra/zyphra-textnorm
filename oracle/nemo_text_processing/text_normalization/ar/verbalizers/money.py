# Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.ar.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_preserve_order,
    delete_space,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing money, e.g.
        money { integer_part: "تسعة" currency_maj: "يورو" preserve_order: true} -> "تسعة يورو"
        money { integer_part: "تسعة" currency_maj: "دولار" preserve_order: true} -> "تسعة دولار"
        money { currency_maj: "دولار" integer_part: "واحد" morphosyntactic_features: "currency_first"} -> "دولار واحد"
        money { negative: "true" integer_part: "اثنا عشر" currency_maj: "دولار" fractional_part: "خمسون" currency_min: "سنت" preserve_order: true } -> "سالب اثنا عشر دولار وخمسون سنت"
        money { integer_part: "خمسة عشر" currency_maj: "دولار" quantity: "في الساعة" preserve_order: true } -> "خمسة عشر دولار في الساعة"
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="money", kind="verbalize", deterministic=deterministic)

        keep_space = pynini.accep(" ")
        opt_sign = pynini.closure(pynini.cross('negative: "true" ', "سالب "), 0, 1)

        maj = pynutil.delete('currency_maj: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        min_unit = pynutil.delete('currency_min: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        fractional_part = (
            pynutil.delete('fractional_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        )

        integer_part = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        per_unit = pynini.closure(
            delete_space
            + pynutil.insert(" ")
            + pynutil.delete('quantity: "')
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"'),
            0,
            1,
        )
        add_and = pynutil.insert(" و")
        morph_currency_first = pynutil.delete(' morphosyntactic_features: "currency_first"')

        # currency_maj before integer_part; disambiguated via morphosyntactic_features for Sparrowhawk.
        graph_currency_first = maj + keep_space + integer_part + delete_space + morph_currency_first + per_unit

        #  *** currency_maj + (***) (و) *** current_min
        graph_integer_with_minor = (
            integer_part
            + keep_space
            + maj
            + delete_space
            + add_and
            + fractional_part
            + delete_space
            + pynini.closure(keep_space + min_unit, 0, 1)
            + per_unit
            + delete_preserve_order
        )
        graph_integer_no_minor = integer_part + keep_space + maj + per_unit + delete_space + delete_preserve_order
        graph_minor = fractional_part + keep_space + delete_space + min_unit + per_unit + delete_preserve_order

        graph = opt_sign + (
            graph_currency_first | graph_integer_with_minor | graph_minor | graph_integer_no_minor
        )

        delete_tokens = self.delete_tokens(graph)
        self.fst = delete_tokens.optimize()
