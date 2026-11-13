# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.bn.graph_utils import MINUS, NEMO_NOT_QUOTE, GraphFst, insert_space


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing fraction
        e.g. fraction { integer_part: "তেইশ" numerator: "চার" denominator: "ছয়" } -> তেইশ পূর্ণ ছয় ভাগের চার
        e.g. fraction { numerator: "চার" denominator: "ছয়" } -> ছয় ভাগের চার


    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)

        optional_sign = pynini.closure(pynini.cross("negative: \"true\"", MINUS) + pynutil.delete(" "), 0, 1)

        integer = pynutil.delete("integer_part: \"") + pynini.closure(NEMO_NOT_QUOTE) + pynutil.delete("\" ")
        numerator = pynutil.delete("numerator: \"") + pynini.closure(NEMO_NOT_QUOTE) + pynutil.delete("\" ")
        denominator = pynutil.delete("denominator: \"") + pynini.closure(NEMO_NOT_QUOTE) + pynutil.delete("\" ")
        insert_bhager = pynutil.insert(" ভাগের ")
        insert_purno = pynutil.insert(" পূর্ণ ")
        graph_quarter = (
            pynutil.delete("morphosyntactic_features: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        )

        # Bengali reads the denominator first: ৩/৪ -> চার ভাগের তিন. The tag permutations in the normalizer
        # present the fields in this order.
        numerator_last = pynutil.delete("numerator: \"") + pynini.closure(NEMO_NOT_QUOTE) + pynutil.delete("\"")
        fraction_default = denominator + insert_bhager + numerator_last

        self.graph = optional_sign + (
            (pynini.closure(integer + insert_purno, 0, 1) + fraction_default) | graph_quarter
        )

        graph = self.graph

        delete_tokens = self.delete_tokens(graph)
        self.fst = delete_tokens.optimize()
