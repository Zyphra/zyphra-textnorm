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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_NOT_QUOTE, GraphFst, delete_preserve_order


class DecimalFst(GraphFst):
    """
    Finite state transducer for verbalizing decimals, e.g.
        decimal { negative: "true" integer_part: "tiga" fractional_part: "tujuh lima" } -> negatif tiga koma tujuh lima
        decimal { integer_part: "satu" fractional_part: "lima" quantity: "juta" } -> satu koma lima juta
        decimal { integer_part: "dua" point_part: "lima" } -> dua titik lima

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="decimal", kind="verbalize", deterministic=deterministic)
        prefix_sign = (
            pynini.cross('negative: "true" ', "negatif ")
            | pynini.cross('negative: "sekitar" ', "sekitar ")
            | pynini.cross('negative: "kurang lebih" ', "kurang lebih ")
        )
        optional_sign = pynini.closure(prefix_sign, 0, 1)
        integer = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        fractional = (
            pynutil.delete(' fractional_part: "')
            + pynutil.insert(" koma ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        fractional |= (
            pynutil.delete(' point_part: "')
            + pynutil.insert(" titik ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        quantity = (
            pynutil.delete(' quantity: "')
            + pynutil.insert(" ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        self.numbers = (
            optional_sign + integer + pynini.closure(fractional, 0, 1) + pynini.closure(quantity, 0, 1)
        ).optimize()
        self.fst = self.delete_tokens(self.numbers + delete_preserve_order).optimize()
