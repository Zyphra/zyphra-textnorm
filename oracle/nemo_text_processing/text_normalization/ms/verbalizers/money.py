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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_NOT_QUOTE, GraphFst


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing Malay money, e.g.
        money { integer_part: "lima belas ribu" currency_maj: "ringgit" } -> lima belas ribu ringgit
        money { integer_part: "satu" fractional_part: "lima" quantity: "juta" currency_maj: "ringgit" }
            -> satu perpuluhan lima juta ringgit
        money { integer_part: "dua" fractional_part: "lima puluh" currency_min: "sen" currency_maj: "dolar" }
            -> dua dolar lima puluh sen
        money { negative: "negatif" integer_part: "dua belas" fractional_part: "lima puluh" currency_min: "sen" currency_maj: "euro" }
            -> negatif dua belas euro lima puluh sen
        money { integer_part: "lima belas" currency_maj: "dolar" morphosyntactic_features: "per jam" }
            -> lima belas dolar per jam

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="money", kind="verbalize", deterministic=deterministic)
        optional_sign = pynini.closure(
            pynutil.delete('negative: "')
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('" ')
            + pynutil.insert(" "),
            0,
            1,
        )
        integer = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        fractional = (
            pynutil.delete(' fractional_part: "')
            + pynutil.insert(" perpuluhan ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        quantity = (
            pynutil.delete(' quantity: "')
            + pynutil.insert(" ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        maj = (
            pynutil.delete(' currency_maj: "')
            + pynutil.insert(" ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        minor_amount = pynutil.delete('fractional_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        minor_unit = (
            pynutil.delete(' currency_min: "')
            + pynutil.insert(" ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        per_unit = (
            pynutil.delete(' morphosyntactic_features: "')
            + pynutil.insert(" ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        optional_per = pynini.closure(per_unit, 0, 1)

        amount = integer + pynini.closure(fractional, 0, 1) + pynini.closure(quantity, 0, 1)
        body = amount + maj
        body |= integer + maj + pynini.accep(" ") + minor_amount + minor_unit
        body |= minor_amount + minor_unit
        graph = optional_sign + body + optional_per
        self.fst = self.delete_tokens(graph).optimize()
