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
)
from nemo_text_processing.text_normalization.tl.graph_utils import get_linker_fst
from nemo_text_processing.text_normalization.tl.utils import get_abs_path, load_labels

class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog money, e.g.
        money { integer_part: "labinlimang libo" currency_maj: "piso" } -> labinlimang libong piso
        money { integer_part: "isa" currency_maj: "piso" fractional_part: "limampu" currency_min: "sentimo" }
            -> isang piso at limampung sentimo
        money { integer_part: "dalawa" currency_maj: "dolyar" fractional_part: "limampu" currency_min: "sentimo" }
            -> dalawang dolyar at limampung sentimo
        money { fractional_part: "siyamnapu't siyam" currency_min: "sentimo" }
            -> siyamnapu't siyam na sentimo
        money { integer_part: "limampu" quantity: "libo" currency_maj: "dolyar" }
            -> limampung libong dolyar

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="money", kind="verbalize", deterministic=deterministic)
        linker = get_linker_fst()
        val = pynini.closure(NEMO_NOT_QUOTE, 1)

        optional_sign = pynini.closure(
            pynutil.delete('negative: "')
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('" ')
            + pynutil.insert(" "),
            0,
            1,
        )

        integer = pynutil.delete('integer_part: "') + (val @ linker) + pynutil.delete('"')
        integer_plain = pynutil.delete('integer_part: "') + val + pynutil.delete('"')
        maj = pynutil.delete(' currency_maj: "') + pynutil.insert(" ") + val + pynutil.delete('"')
        minor = pynutil.delete(' fractional_part: "') + (val @ linker) + pynutil.delete('"')
        min_unit = pynutil.delete(' currency_min: "') + pynutil.insert(" ") + val + pynutil.delete('"')
        quantity = pynutil.delete(' quantity: "') + pynutil.insert(" ") + (val @ linker) + pynutil.delete('"')
        fractional = pynutil.delete(' fractional_part: "') + pynutil.insert(" tuldok ") + (val @ linker) + pynutil.delete('"')

        per_unit = (
            pynutil.delete(' morphosyntactic_features: "')
            + pynutil.insert(" ")
            + val
            + pynutil.delete('"')
        )
        optional_per = pynini.closure(per_unit, 0, 1)

        curr_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        currencies = list(dict.fromkeys(r[1] for r in curr_labels if len(r) > 1))
        body_suff_cases = [
            integer + pynutil.insert(f" {c} at ") + minor + min_unit + pynutil.delete(f' currency_maj: "{c}"')
            for c in currencies
        ]
        body_suff = pynini.union(*body_suff_cases)

        body_maj_min = integer + maj + pynutil.insert(" at ") + minor + min_unit
        body_maj = integer + maj
        body_min = pynutil.delete('fractional_part: "') + (val @ linker) + pynutil.delete('"') + min_unit
        body_qty = integer + quantity + maj
        body_dec_qty = integer_plain + fractional + quantity + maj

        body = body_maj_min | body_suff | body_maj | body_min | body_qty | body_dec_qty
        graph = optional_sign + body + optional_per
        self.fst = self.delete_tokens(graph).optimize()
