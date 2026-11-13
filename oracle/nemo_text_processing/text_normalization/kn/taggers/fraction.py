# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_SIGMA,
    NEMO_SPACE,
    TO_ASCII_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fraction
        "3/7" -> fraction { numerator: "ಮೂರು" denominator: "ಏಳು" }
        "2 3/7" -> fraction { integer_part: "ಎರಡು" numerator: "ಮೂರು" denominator: "ಏಳು" }
        "3/4" -> fraction { morphosyntactic_features: "ಮುಕ್ಕಾಲು" }
        "2 1/2" -> fraction { morphosyntactic_features: "ಎರಡುವರೆ" }

    Args:
        cardinal: cardinal GraphFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph
        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()

        minus_sym = pynini.union("-", "−")
        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(minus_sym, "\"true\"") + pynutil.insert(NEMO_SPACE), 0, 1
        )

        self.integer = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")

        self.numerator = (
            pynutil.insert("numerator: \"")
            + (pynini.compose(to_ascii, cardinal_graph) | cardinal_graph)
            + pynutil.insert("\"")
        )

        self.denominator = pynutil.insert("denominator: \"") + cardinal_graph + pynutil.insert("\"")

        optional_space = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))
        common_slash = pynini.compose(to_ascii + pynini.accep("/") + to_ascii, common_fraction_map)
        common_glyph = pynini.string_map([("½", "ಅರ್ಧ"), ("¼", "ಕಾಲು"), ("¾", "ಮುಕ್ಕಾಲು")])
        common_fraction = common_slash | common_glyph

        vulgar_num_den = pynini.string_map(
            [
                ("½", 'numerator: "ಒಂದು" denominator: "ಎರಡು"'),
                ("⅓", 'numerator: "ಒಂದು" denominator: "ಮೂರು"'),
                ("⅔", 'numerator: "ಎರಡು" denominator: "ಮೂರು"'),
                ("¼", 'numerator: "ಒಂದು" denominator: "ನಾಲ್ಕು"'),
                ("¾", 'numerator: "ಮೂರು" denominator: "ನಾಲ್ಕು"'),
                ("⅕", 'numerator: "ಒಂದು" denominator: "ಐದು"'),
                ("⅖", 'numerator: "ಎರಡು" denominator: "ಐದು"'),
                ("⅗", 'numerator: "ಮೂರು" denominator: "ಐದು"'),
                ("⅘", 'numerator: "ನಾಲ್ಕು" denominator: "ಐದು"'),
                ("⅙", 'numerator: "ಒಂದು" denominator: "ಆರು"'),
                ("⅚", 'numerator: "ಐದು" denominator: "ಆರು"'),
                ("⅛", 'numerator: "ಒಂದು" denominator: "ಎಂಟು"'),
                ("⅜", 'numerator: "ಮೂರು" denominator: "ಎಂಟು"'),
                ("⅝", 'numerator: "ಐದು" denominator: "ಎಂಟು"'),
                ("⅞", 'numerator: "ಏಳು" denominator: "ಎಂಟು"'),
                ("⅒", 'numerator: "ಒಂದು" denominator: "ಹತ್ತು"'),
            ]
        )
        vulgar_other_in = pynini.difference(
            pynini.project(vulgar_num_den, "input"), pynini.project(common_glyph, "input")
        )
        vulgar_other = pynini.compose(vulgar_other_in, vulgar_num_den)

        # Special Kannada mixed fractions with half:
        # 1 1/2 -> ಒಂದೂವರೆ, 2 1/2 -> ಎರಡುವರೆ, 3 1/2 -> ಮೂರೂವರೆ, 4 1/2 -> ನಾಲ್ಕೂವರೆ, 5 1/2 -> ಐದೂವರೆ
        half_map = pynini.string_map(
            [
                ("1", "ಒಂದೂವರೆ"),
                ("೧", "ಒಂದೂವರೆ"),
                ("2", "ಎರಡುವರೆ"),
                ("೨", "ಎರಡುವರೆ"),
                ("3", "ಮೂರೂವರೆ"),
                ("೩", "ಮೂರೂವರೆ"),
                ("4", "ನಾಲ್ಕೂವರೆ"),
                ("೪", "ನಾಲ್ಕೂವರೆ"),
                ("5", "ಐದೂವರೆ"),
                ("೫", "ಐದೂವರೆ"),
                ("6", "ಆರೂವರೆ"),
                ("೬", "ಆರೂವರೆ"),
                ("7", "ಏಳೂವರೆ"),
                ("೭", "ಏಳೂವರೆ"),
                ("8", "ಎಂಟೂವರೆ"),
                ("೮", "ಎಂಟೂವರೆ"),
                ("9", "ಒಂಬತ್ತೂವರೆ"),
                ("೯", "ಒಂಬತ್ತೂವರೆ"),
                ("10", "ಹತ್ತೂವರೆ"),
                ("೧೦", "ಹತ್ತೂವರೆ"),
            ]
        )
        half_suffix = (pynutil.delete(NEMO_SPACE) + pynutil.delete(pynini.union("1/2", "೧/೨"))) | (
            optional_space + pynutil.delete("½")
        )
        and_half = half_map + half_suffix

        # Special quarter / three quarters:
        # 1 1/4 -> ಒಂದು ಕಾಲು, 2 1/4 -> ಎರಡು ಕಾಲು, 1 3/4 -> ಒಂದು ಮುಕ್ಕಾಲು
        quarter_suffix = (pynutil.delete(NEMO_SPACE) + pynutil.delete(pynini.union("1/4", "೧/೪"))) | (
            optional_space + pynutil.delete("¼")
        )
        and_quarter = cardinal_graph + quarter_suffix + pynutil.insert(" ಕಾಲು")

        three_quarter_suffix = (pynutil.delete(NEMO_SPACE) + pynutil.delete(pynini.union("3/4", "೩/೪"))) | (
            optional_space + pynutil.delete("¾")
        )
        and_three_quarter = cardinal_graph + three_quarter_suffix + pynutil.insert(" ಮುಕ್ಕಾಲು")

        def special(graph):
            return (
                self.optional_graph_negative
                + pynutil.insert("morphosyntactic_features: \"")
                + graph
                + pynutil.insert("\"")
            )

        slash_fraction = (
            special(common_fraction)
            | special(and_half)
            | special(and_quarter)
            | special(and_three_quarter)
            | self.optional_graph_negative
            + pynini.closure(self.integer + pynutil.delete(NEMO_SPACE) + pynutil.insert(NEMO_SPACE), 0, 1)
            + self.numerator
            + pynutil.delete("/")
            + pynutil.insert(NEMO_SPACE)
            + self.denominator
        )
        unicode_mixed_or_other = self.optional_graph_negative + (
            vulgar_other | (self.integer + optional_space + pynutil.insert(NEMO_SPACE) + vulgar_num_den)
        )
        final_graph = slash_fraction | unicode_mixed_or_other

        weighted_graph = (
            pynutil.add_weight(special(common_fraction), -0.05)
            | pynutil.add_weight(special(and_half), -0.05)
            | pynutil.add_weight(special(and_quarter), -0.04)
            | pynutil.add_weight(special(and_three_quarter), -0.04)
            | final_graph
        )

        self.graph = weighted_graph

        graph = self.add_tokens(self.graph)
        self.fst = graph.optimize()
