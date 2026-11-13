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
    NEMO_SPACE,
    TO_ASCII_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fractions, e.g.
        "3/7" -> fraction { numerator: "മൂന്ന്" denominator: "ഏഴ്" }
        "2 3/7" -> fraction { integer_part: "രണ്ട്" numerator: "മൂന്ന്" denominator: "ഏഴ്" }
        "1/2" -> fraction { morphosyntactic_features: "പകുതി" }
        "1 1/2" -> fraction { morphosyntactic_features: "ഒന്നര" }
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph
        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()

        minus_char = pynini.union("-", "−")
        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(minus_char, "\"true\"") + pynutil.insert(NEMO_SPACE), 0, 1
        )

        self.integer = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")

        self.numerator = (
            pynutil.insert("numerator: \"")
            + cardinal_graph
            + pynini.cross(pynini.union("/", NEMO_SPACE + "/" + NEMO_SPACE), "\"")
            + pynutil.insert(NEMO_SPACE)
        )

        self.denominator = pynutil.insert("denominator: \"") + cardinal_graph + pynutil.insert("\"")

        optional_space = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))
        common_slash = pynini.compose(to_ascii + pynini.closure(NEMO_SPACE + to_ascii, 0, 1) + pynini.accep("/") + to_ascii, common_fraction_map)
        common_glyph = pynini.string_map([("½", "പകുതി"), ("¼", "കാൽ"), ("¾", "മുക്കാൽ")])
        common_fraction = common_fraction_map | common_glyph

        vulgar_num_den = pynini.string_map(
            [
                ("½", "numerator: \"ഒന്ന്\" denominator: \"രണ്ട്\""),
                ("¼", "numerator: \"ഒന്ന്\" denominator: \"നാല്\""),
                ("¾", "numerator: \"മൂന്ന്\" denominator: \"നാല്\""),
                ("⅓", "numerator: \"ഒന്ന്\" denominator: \"മൂന്ന്\""),
                ("⅔", "numerator: \"രണ്ട്\" denominator: \"മൂന്ന്\""),
                ("⅕", "numerator: \"ഒന്ന്\" denominator: \"അഞ്ച്\""),
                ("⅖", "numerator: \"രണ്ട്\" denominator: \"അഞ്ച്\""),
                ("⅗", "numerator: \"മൂന്ന്\" denominator: \"അഞ്ച്\""),
                ("⅘", "numerator: \"നാല്\" denominator: \"അഞ്ച്\""),
                ("⅙", "numerator: \"ഒന്ന്\" denominator: \"ആറ്\""),
                ("⅚", "numerator: \"അഞ്ച്\" denominator: \"ആറ്\""),
                ("⅐", "numerator: \"ഒന്ന്\" denominator: \"ഏഴ്\""),
                ("⅛", "numerator: \"ഒന്ന്\" denominator: \"എട്ട്\""),
                ("⅜", "numerator: \"മൂന്ന്\" denominator: \"എട്ട്\""),
                ("⅝", "numerator: \"അഞ്ച്\" denominator: \"എട്ട്\""),
                ("⅞", "numerator: \"ഏഴ്\" denominator: \"എട്ട്\""),
                ("⅑", "numerator: \"ഒന്ന്\" denominator: \"ഒൻപത്\""),
                ("⅒", "numerator: \"ഒന്ന്\" denominator: \"പത്ത്\""),
            ]
        )

        def special(graph):
            return (
                self.optional_graph_negative
                + pynutil.insert("morphosyntactic_features: \"")
                + graph
                + pynutil.insert("\"")
                + pynutil.insert(NEMO_SPACE)
            )

        slash_fraction = (
            self.optional_graph_negative
            + pynini.closure(self.integer + pynini.accep(NEMO_SPACE), 0, 1)
            + self.numerator
            + self.denominator
        )
        unicode_fraction = self.optional_graph_negative + (
            vulgar_num_den | (self.integer + optional_space + pynutil.insert(NEMO_SPACE) + vulgar_num_den)
        )
        final_graph = slash_fraction | unicode_fraction

        weighted_graph = (
            final_graph
            | pynutil.add_weight(special(common_fraction), -0.3)
        )

        self.graph = weighted_graph
        graph = self.add_tokens(self.graph)
        self.fst = graph.optimize()
