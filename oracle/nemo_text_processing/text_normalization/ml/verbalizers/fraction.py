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
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for verbalizing fraction, e.g.
        fraction { numerator: "രണ്ട്" denominator: "മൂന്ന്" } -> മൂന്നിൽ രണ്ട്
        fraction { integer_part: "അഞ്ച്" numerator: "രണ്ട്" denominator: "മൂന്ന്" } -> അഞ്ച് മൂന്നിൽ രണ്ട്
        fraction { morphosyntactic_features: "പകുതി" } -> പകുതി
        fraction { morphosyntactic_features: "ഒന്നര" } -> ഒന്നര
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="fraction", kind="verbalize", deterministic=deterministic)

        delete_space = pynutil.delete(" ")
        optional_sign = pynini.closure(pynini.cross('negative: "true"', MINUS) + delete_space, 0, 1)

        integer = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        numerator = pynutil.delete('numerator: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        denominator = pynutil.delete('denominator: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        # Convert denominator to locative with -ൽ: e.g. മൂന്ന് -> മൂന്നിൽ, ഏഴ് -> ഏഴിൽ
        to_locative = pynini.cdrewrite(
            pynini.cross("്", "ിൽ") | pynini.cross("ം", "ത്തിൽ"),
            "",
            "[EOS]",
            NEMO_SIGMA,
        )
        den_locative = pynini.compose(denominator, to_locative)

        frac_regular = den_locative + delete_space + pynutil.insert(" ") + numerator
        frac_with_int = integer + delete_space + pynutil.insert(" ") + frac_regular

        morph = pynutil.delete('morphosyntactic_features: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        graph = optional_sign + (morph | frac_with_int | frac_regular)
        self.fst = self.delete_tokens(graph).optimize()
