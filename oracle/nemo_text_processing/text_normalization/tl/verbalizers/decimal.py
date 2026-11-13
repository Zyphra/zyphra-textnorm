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
)
from nemo_text_processing.text_normalization.tl.graph_utils import get_linker_fst


class DecimalFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog decimals, e.g.
        decimal { negative: "true" integer_part: "tatlo" fractional_part: "pito lima" }
            -> minus tatlo tuldok pito lima
        decimal { integer_part: "isa" fractional_part: "lima" quantity: "milyon" }
            -> isa tuldok limang milyon
        decimal { integer_part: "lima" quantity: "milyon" }
            -> limang milyon

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="decimal", kind="verbalize", deterministic=deterministic)
        linker = get_linker_fst()

        prefix_sign = (
            pynini.cross('negative: "true" ', "minus ")
            | pynini.cross('negative: "humigit-kumulang" ', "humigit-kumulang ")
            | pynini.cross('negative: "plus-minus" ', "plus-minus ")
        )
        optional_sign = pynini.closure(prefix_sign, 0, 1)

        val = pynini.closure(NEMO_NOT_QUOTE, 1)

        integer = pynutil.delete('integer_part: "') + val + pynutil.delete('"')

        # When quantity is present, the immediately preceding number gets the linker (-ng / na)
        frac_with_qty = (
            pynutil.delete(' fractional_part: "')
            + pynutil.insert(" tuldok ")
            + (val @ linker)
            + pynutil.delete('" quantity: "')
            + pynutil.insert(" ")
            + val
            + pynutil.delete('"')
        )
        int_with_qty = (
            pynutil.delete('integer_part: "')
            + (val @ linker)
            + pynutil.delete('" quantity: "')
            + pynutil.insert(" ")
            + val
            + pynutil.delete('"')
        )
        plain_frac = (
            pynutil.delete(' fractional_part: "')
            + pynutil.insert(" tuldok ")
            + val
            + pynutil.delete('"')
        )

        body = (
            int_with_qty
            | integer + frac_with_qty
            | integer + pynini.closure(plain_frac, 0, 1)
        )

        self.numbers = (optional_sign + body).optimize()
        self.fst = self.delete_tokens(self.numbers + delete_preserve_order).optimize()
