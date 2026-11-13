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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.te.graph_utils import TO_ASCII_DIGIT, GraphFst
from nemo_text_processing.text_normalization.te.taggers.cardinal import (
    HUNDRED_COMBINING_ONE,
    HUNDREDS,
    LAKH_ONE,
    LAKHS,
    THOUSAND_ONE,
    THOUSANDS,
    CardinalFst,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path

ORDINAL_MARK = "వ"


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Telugu ordinals written with the CLDR %digits-ordinal suffix వ
    (ASCII or Telugu digits), spoken per CLDR %spellout-ordinal, e.g.
        1వ -> ordinal { integer: "మొదటి" }
        21వ -> ordinal { integer: "ఇరవై ఒకటవ" }
        200వ -> ordinal { integer: "రెండు వందలవ" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        o2 = pynini.string_file(get_abs_path("data/ordinal/ordinals.tsv"))  # 1-99
        o1 = pynini.compose(pynini.union(*"123456789"), o2).optimize()
        o10_99 = pynini.compose(pynini.union(*"123456789") + pynini.union(*"0123456789"), o2).optimize()
        ro2 = (pynutil.delete("0") + o1 | o10_99).optimize()

        d2_9 = cardinal.ascii_d2_9
        e2 = cardinal.ascii_e2

        def exact_or_rest(zeros: int, rest):
            return pynini.cross("0" * zeros, ORDINAL_MARK) | pynutil.insert(" ") + rest

        o3 = (
            pynini.cross("100", "వందవ")
            | pynutil.delete("1") + pynutil.insert(HUNDRED_COMBINING_ONE + " ") + ro2
            | d2_9 + pynutil.insert(" " + HUNDREDS) + exact_or_rest(2, ro2)
        ).optimize()
        ro3 = (pynutil.delete("0") + ro2 | o3).optimize()

        o4 = (
            pynini.cross("1000", "వెయ్యవ")
            | pynini.cross("1", THOUSAND_ONE + " ") + ro3
            | d2_9 + pynutil.insert(" " + THOUSANDS) + exact_or_rest(3, ro3)
        ).optimize()
        o5 = (e2 + pynutil.insert(" " + THOUSANDS) + exact_or_rest(3, ro3)).optimize()
        ro4 = (pynutil.delete("0") + ro3 | o4).optimize()
        ro5 = (pynutil.delete("0") + ro4 | o5).optimize()

        # 1,00,000 = ఒక లక్ష[ >>|వ]; 2,00,000+ = <cardinal> లక్షల[ >>|వ]
        o6 = (
            pynutil.delete("1") + pynutil.insert(LAKH_ONE) + exact_or_rest(5, ro5)
            | d2_9 + pynutil.insert(" " + LAKHS) + exact_or_rest(5, ro5)
        ).optimize()
        o7 = (e2 + pynutil.insert(" " + LAKHS) + exact_or_rest(5, ro5)).optimize()

        ascii_ordinal = pynini.union(o2, o3, o4, o5, o6, o7).optimize()
        graph = pynini.compose(pynini.closure(TO_ASCII_DIGIT, 1), ascii_ordinal) + pynutil.delete(ORDINAL_MARK)

        self.graph = graph.optimize()

        final_graph = pynutil.insert("integer: \"") + self.graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
