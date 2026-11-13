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
from nemo_text_processing.text_normalization.ml.verbalizers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.ml.verbalizers.decimal import DecimalFst


class MeasureFst(GraphFst):
    """
    Finite state transducer for verbalizing measure, e.g.
        measure { cardinal { integer: "ഒരു" } units: "കിലോഗ്രാം" preserve_order: true } -> ഒരു കിലോഗ്രാം
        measure { cardinal { integer: "അഞ്ച്" } units: "കിലോഗ്രാം" preserve_order: true } -> അഞ്ച് കിലോഗ്രാം
        measure { morphosyntactic_features: "മണിക്കൂറിൽ" cardinal { integer: "അറുപത്" } units: "കിലോമീറ്റർ" ... } -> മണിക്കൂറിൽ അറുപത് കിലോമീറ്റർ
    """

    def __init__(self, cardinal: GraphFst = None, decimal: GraphFst = None, fraction: GraphFst = None, deterministic: bool = True):
        super().__init__(name="measure", kind="verbalize", deterministic=deterministic)

        opt_pre = pynini.closure(
            pynutil.delete('morphosyntactic_features: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"') + delete_space + insert_space,
            0,
            1,
        )

        card_verb = cardinal.fst if cardinal else CardinalFst().fst
        dec_verb = decimal.fst if decimal else DecimalFst().fst

        num = card_verb | dec_verb

        units = pynutil.delete('units: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        opt_preserve = pynini.closure(pynutil.delete(" preserve_order: true"), 0, 1)

        graph = opt_pre + num + delete_space + insert_space + units + opt_preserve
        self.fst = self.delete_tokens(graph).optimize()
