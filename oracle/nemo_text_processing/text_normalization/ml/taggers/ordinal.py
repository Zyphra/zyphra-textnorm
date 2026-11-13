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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.ml.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.ml.utils import get_abs_path


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Malayalam ordinals written with CLDR ordinal suffixes:
    '-ാം', 'ാം', '-ാമത്തെ', 'ാമത്തെ' (ASCII and Malayalam digits), e.g.
        1-ാം -> ordinal { integer: "ഒന്നാം" }
        1ാം -> ordinal { integer: "ഒന്നാം" }
        1-ാമത്തെ -> ordinal { integer: "ഒന്നാമത്തെ" }
        21-ാം -> ordinal { integer: "ഇരുപത്തിയൊന്നാം" }
        100-ാം -> ordinal { integer: "നൂറാം" }
        2024-ാം -> ordinal { integer: "രണ്ടായിരത്തി ഇരുപത്തിനാലാം" }
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        o_aam = pynini.string_file(get_abs_path("data/ordinal/ordinals.tsv"))
        o_mathe = pynini.string_file(get_abs_path("data/ordinal/ordinals_mathe.tsv"))

        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()

        suffix_aam = pynini.union("-ാം", "ാം")
        suffix_mathe = pynini.union("-ാമത്തെ", "ാമത്തെ")

        # 1-99 with suffixes
        num_1_99 = pynini.compose(to_ascii, pynini.closure(NEMO_ALL_DIGIT, 1, 2)).optimize()
        ord_1_99_aam = pynini.compose(num_1_99, o_aam) + pynutil.delete(suffix_aam)
        ord_1_99_mathe = pynini.compose(num_1_99, o_mathe) + pynutil.delete(suffix_mathe)

        # 100+ via cardinal transduction and virama/anusvara rewrite
        to_ordinal_aam = pynini.cdrewrite(
            pynini.cross("്", "ാം") | pynini.cross("ം", "ാം"),
            "",
            "[EOS]",
            NEMO_SIGMA,
        )
        to_ordinal_mathe = pynini.cdrewrite(
            pynini.cross("്", "ാമത്തെ") | pynini.cross("ം", "ാമത്തെ"),
            "",
            "[EOS]",
            NEMO_SIGMA,
        )

        card_graph = cardinal.final_graph

        ord_higher_aam = pynini.compose(card_graph, to_ordinal_aam) + pynutil.delete(suffix_aam)
        ord_higher_mathe = pynini.compose(card_graph, to_ordinal_mathe) + pynutil.delete(suffix_mathe)

        graph = ord_1_99_aam | ord_1_99_mathe | ord_higher_aam | ord_higher_mathe
        self.graph = graph.optimize()

        final_graph = pynutil.insert("integer: \"") + self.graph + pynutil.insert("\"")
        self.fst = self.add_tokens(final_graph).optimize()
