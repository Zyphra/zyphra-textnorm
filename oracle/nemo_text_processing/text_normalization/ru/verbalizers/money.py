# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
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
    delete_space,
)
from nemo_text_processing.text_normalization.ru.taggers.units import (
    ANY_MARK,
    WORDS,
    agreement,
    load_currencies,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing money, e.g.
        money { integer_part: "пять рублей" } -> "пять рублей"
        money { currency: "$" integer_part: "семь"+M fractional_part: "пятьдесят"+M preserve_order: true } ->
            "семь долларов пятьдесят центов"
    Number words followed by a marker (units.MARK) are read with the currency in the form the marker asks for.

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="money", kind="verbalize", deterministic=deterministic)

        major, minor, _ = load_currencies()
        marked = WORDS + ANY_MARK

        def value(name, graph):
            return pynutil.delete(f"{name}: \"") + graph + pynutil.delete("\"")

        spoken = value("integer_part", pynini.closure(NEMO_NOT_QUOTE - ANY_MARK, 1))

        opt_neg = pynini.closure(value("negative", pynini.closure(NEMO_NOT_QUOTE, 1)) + delete_space + pynutil.insert(" "), 0, 1)
        opt_rate = pynini.closure(delete_space + pynutil.insert(" ") + value("morphosyntactic_features", pynini.closure(NEMO_NOT_QUOTE, 1)), 0, 1)
        order = delete_space + pynutil.delete("preserve_order: true")

        reorder = None
        for symbol in sorted({n.written for n in major}):
            sym_esc = pynini.escape(symbol)
            currency = value("currency", pynutil.delete(sym_esc)) + delete_space
            major_unit = agreement([n for n in major if n.written == symbol], pynutil.insert(" "))
            amount = value("integer_part", pynini.compose(marked + pynutil.insert(symbol), major_unit))
            graph = currency + amount
            graph |= amount + delete_space + currency
            minors = [n for n in minor if n.written == symbol]
            if minors:
                minor_unit = agreement(minors, pynutil.insert(" "))
                cents = value("fractional_part", pynini.compose(marked + pynutil.insert(symbol), minor_unit))
                with_cents = amount + delete_space + pynutil.insert(" ") + cents
                graph |= currency + with_cents
                graph |= with_cents + delete_space + currency
            reorder = graph if reorder is None else reorder | graph

        full_reorder = opt_neg + reorder + opt_rate + order
        self.fst = self.delete_tokens(spoken | full_reorder).optimize()
