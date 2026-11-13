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
from nemo_text_processing.text_normalization.tl.graph_utils import get_linker_fst


class MeasureFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog measure with native linker morphology, e.g.
        measure { cardinal { integer: "lima" } units: "kilometro" } -> limang kilometro
        measure { cardinal { integer: "apat" } units: "kilo" } -> apat na kilo
        measure { cardinal { integer: "isang daan" } units: "metro" } -> isang daang metro
        measure { decimal { integer_part: "dalawa" fractional_part: "apat" } units: "gigahertz" }
            -> dalawa tuldok apat na gigahertz

    Args:
        cardinal: cardinal verbalizer
        decimal: decimal verbalizer
        fraction: fraction verbalizer
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, fraction: GraphFst, deterministic: bool = True):
        super().__init__(name="measure", kind="verbalize", deterministic=deterministic)
        linker = get_linker_fst()
        units = (
            delete_space
            + pynutil.delete('units: "')
            + pynutil.insert(" ")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
        )
        number = (cardinal.fst | decimal.fst | fraction.fst) @ linker
        self.fst = self.delete_tokens(number + units + delete_preserve_order).optimize()
