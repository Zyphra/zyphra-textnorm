# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying ordinals in Thai (th).
    Supports:
    - ที่ 1 -> ที่หนึ่ง
    - ที่ 21 / ที่21 -> ที่ยี่สิบเอ็ด
    - 1st -> ที่หนึ่ง
    - 2nd -> ที่สอง
    - 3rd -> ที่สาม
    - 4th -> ที่สี่
    - 21st -> ที่ยี่สิบเอ็ด
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Thai prefix ที่
        thai_prefix = pynini.cross("ที่", "ที่") + opt_sp + cardinal.all_positive

        # English suffixes: 1st, 2nd, 3rd, 4th, 21st...
        st = pynutil.delete("st")
        nd = pynutil.delete("nd")
        rd = pynutil.delete("rd")
        th = pynutil.delete("th")
        en_suffix = st | nd | rd | th
        en_ordinal = pynutil.insert("ที่") + (cardinal.all_positive + en_suffix)

        graph = (thai_prefix | en_ordinal).optimize()
        self.fst = (
            pynutil.insert('name: "')
            + convert_space(graph)
            + pynutil.insert('"')
        ).optimize()
