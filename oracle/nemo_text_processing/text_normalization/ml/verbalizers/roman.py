# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path


class RomanFst(GraphFst):
    """
    Finite state transducer for verbalizing Roman numerals, e.g.
        roman { key_cardinal: "അധ്യായം" integer: "IV" } -> അധ്യായം നാല്
        roman { integer: "IV" default_ordinal: "നാലാം" key_cardinal: "അധ്യായം" } -> നാലാം അധ്യായം
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="verbalize", deterministic=deterministic)

        roman_to_spoken = pynini.string_file(get_abs_path("data/roman/roman_to_spoken.tsv"))
        integer = pynutil.delete('integer: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        spoken_num = pynini.compose(integer, roman_to_spoken)

        default_ord = pynutil.delete('default_ordinal: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        key = pynutil.delete('key_cardinal: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        opt_preserve = pynini.closure(pynutil.delete("preserve_order: true "), 0, 1)

        graph = opt_preserve + (
            key + delete_space + insert_space + spoken_num
            | spoken_num + delete_space + insert_space + key
            | default_ord + pynini.closure(delete_space + insert_space + key, 0, 1)
        )
        self.fst = self.delete_tokens(graph).optimize()
