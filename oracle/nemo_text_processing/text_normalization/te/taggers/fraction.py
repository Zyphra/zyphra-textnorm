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

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_SIGMA,
    NEMO_SPACE,
    TO_ASCII_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path

# "and a half" fuses with a number word ending in a vowel sign: ఒకటి -> ఒకటిన్నర, రెండు -> రెండున్నర
TE_AND_HALF = "న్నర"


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fraction
        "3/7" -> fraction { numerator: "మూడు" denominator: "ఏడు" }
        "2 3/7" -> fraction { integer_part: "రెండు" numerator: "మూడు" denominator: "ఏడు" }
        "3/4" -> fraction { morphosyntactic_features: "ముప్పావు" }
        "2 1/2" -> fraction { morphosyntactic_features: "రెండున్నర" }

    Args:
        cardinal: cardinal GraphFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph
        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()

        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", "\"true\"") + pynutil.insert(NEMO_SPACE), 0, 1
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
        common_slash = pynini.compose(to_ascii + pynini.accep("/") + to_ascii, common_fraction_map)
        common_glyph = pynini.string_map([("½", "సగం"), ("¼", "పావు"), ("¾", "ముప్పావు")])
        common_fraction = common_slash | common_glyph

        vulgar_num_den = pynini.string_map(
            [
                ("½", "numerator: \"ఒకటి\" denominator: \"రెండు\""),
                ("¼", "numerator: \"ఒకటి\" denominator: \"నాలుగు\""),
                ("¾", "numerator: \"మూడు\" denominator: \"నాలుగు\""),
                ("⅓", "numerator: \"ఒకటి\" denominator: \"మూడు\""),
                ("⅔", "numerator: \"రెండు\" denominator: \"మూడు\""),
                ("⅕", "numerator: \"ఒకటి\" denominator: \"ఐదు\""),
                ("⅖", "numerator: \"రెండు\" denominator: \"ఐదు\""),
                ("⅗", "numerator: \"మూడు\" denominator: \"ఐదు\""),
                ("⅘", "numerator: \"నాలుగు\" denominator: \"ఐదు\""),
                ("⅙", "numerator: \"ఒకటి\" denominator: \"ఆరు\""),
                ("⅚", "numerator: \"ఐదు\" denominator: \"ఆరు\""),
                ("⅐", "numerator: \"ఒకటి\" denominator: \"ఏడు\""),
                ("⅛", "numerator: \"ఒకటి\" denominator: \"ఎనిమిది\""),
                ("⅜", "numerator: \"మూడు\" denominator: \"ఎనిమిది\""),
                ("⅝", "numerator: \"ఐదు\" denominator: \"ఎనిమిది\""),
                ("⅞", "numerator: \"ఏడు\" denominator: \"ఎనిమిది\""),
                ("⅑", "numerator: \"ఒకటి\" denominator: \"తొమ్మిది\""),
                ("⅒", "numerator: \"ఒకటి\" denominator: \"పది\""),
            ]
        )
        vulgar_other_in = pynini.difference(
            pynini.project(vulgar_num_den, "input"), pynini.project(common_glyph, "input")
        )
        vulgar_other = pynini.compose(vulgar_other_in, vulgar_num_den)

        ends_in_vowel_sign = NEMO_SIGMA + pynini.union("ు", "ి")
        half_suffix = (pynutil.delete(NEMO_SPACE) + pynutil.delete(pynini.union("1/2", "౧/౨"))) | (
            optional_space + pynutil.delete("½")
        )
        and_half = pynini.compose(cardinal_graph, ends_in_vowel_sign) + half_suffix + pynutil.insert(TE_AND_HALF)

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
        unicode_mixed_or_other = self.optional_graph_negative + (
            vulgar_other | (self.integer + optional_space + pynutil.insert(NEMO_SPACE) + vulgar_num_den)
        )
        final_graph = slash_fraction | unicode_mixed_or_other

        weighted_graph = (
            final_graph
            | pynutil.add_weight(special(common_fraction), -0.3)
            | pynutil.add_weight(special(and_half), -0.3)
        )

        self.graph = weighted_graph

        graph = self.add_tokens(self.graph)
        self.fst = graph.optimize()
