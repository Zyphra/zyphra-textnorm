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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_SIGMA,
    NEMO_SPACE,
    TO_ASCII_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path
from nemo_text_processing.text_normalization.en.graph_utils import insert_space


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fraction
        "3/7" -> fraction { numerator: "மூன்று" denominator: "ஏழு" }
        "2 3/7" -> fraction { integer_part: "இரண்டு" numerator: "மூன்று" denominator: "ஏழு" }
        "3/4" -> fraction { morphosyntactic_features: "முக்கால்" }
        "2 1/2" -> fraction { morphosyntactic_features: "இரண்டரை" }
        "-2½" -> fraction { negative: "true" morphosyntactic_features: "இரண்டரை" }

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
            + pynutil.delete("/")
            + pynutil.insert("\" ")
        )

        self.denominator = pynutil.insert("denominator: \"") + cardinal_graph + pynutil.insert("\"")

        optional_space = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))
        common_slash = pynini.compose(to_ascii + pynini.accep("/") + to_ascii, common_fraction_map)
        common_glyph = pynini.string_map([("½", "அரை"), ("¼", "கால்"), ("¾", "முக்கால்")])
        common_fraction = common_slash | common_glyph

        vulgar_num_den = pynini.string_map(
            [
                ("½", 'numerator: "ஒன்று" denominator: "இரண்டு"'),
                ("⅓", 'numerator: "ஒன்று" denominator: "மூன்று"'),
                ("⅔", 'numerator: "இரண்டு" denominator: "மூன்று"'),
                ("¼", 'numerator: "ஒன்று" denominator: "நான்கு"'),
                ("¾", 'numerator: "மூன்று" denominator: "நான்கு"'),
                ("⅕", 'numerator: "ஒன்று" denominator: "ஐந்து"'),
                ("⅖", 'numerator: "இரண்டு" denominator: "ஐந்து"'),
                ("⅗", 'numerator: "மூன்று" denominator: "ஐந்து"'),
                ("⅘", 'numerator: "நான்கு" denominator: "ஐந்து"'),
                ("⅙", 'numerator: "ஒன்று" denominator: "ஆறு"'),
                ("⅚", 'numerator: "ஐந்து" denominator: "ஆறு"'),
                ("⅐", 'numerator: "ஒன்று" denominator: "ஏழு"'),
                ("⅛", 'numerator: "ஒன்று" denominator: "எட்டு"'),
                ("⅜", 'numerator: "மூன்று" denominator: "எட்டு"'),
                ("⅝", 'numerator: "ஐந்து" denominator: "எட்டு"'),
                ("⅞", 'numerator: "ஏழு" denominator: "எட்டு"'),
                ("⅑", 'numerator: "ஒன்று" denominator: "ஒன்பது"'),
                ("⅒", 'numerator: "ஒன்று" denominator: "பத்து"'),
            ]
        )
        vulgar_other_in = pynini.difference(
            pynini.project(vulgar_num_den, "input"), pynini.project(common_glyph, "input")
        )
        vulgar_other = pynini.compose(vulgar_other_in, vulgar_num_den)

        # Fused mixed halves in Tamil (1 1/2 -> ஒன்றரை, 2 1/2 -> இரண்டரை, etc.)
        mixed_halves_list = [
            ("1", "ஒன்றரை"), ("௧", "ஒன்றரை"),
            ("2", "இரண்டரை"), ("௨", "இரண்டரை"),
            ("3", "மூன்றரை"), ("௩", "மூன்றரை"),
            ("4", "நான்கரை"), ("௪", "நான்கரை"),
            ("5", "ஐந்தரை"), ("௫", "ஐந்தரை"),
            ("6", "ஆறரை"), ("௬", "ஆறரை"),
            ("7", "ஏழரை"), ("௭", "ஏழரை"),
            ("8", "எட்டரை"), ("௮", "எட்டரை"),
            ("9", "ஒன்பதரை"), ("௯", "ஒன்பதரை"),
            ("10", "பத்தரை"),
        ]
        half_pat = (pynutil.delete(NEMO_SPACE) + pynutil.delete(pynini.union("1/2", "௧/௨"))) | (
            optional_space + pynutil.delete("½")
        )
        mixed_half = pynini.string_map(mixed_halves_list) + half_pat

        def special(graph):
            return pynutil.insert("morphosyntactic_features: \"") + graph + pynutil.insert("\"")

        slash_fraction = self.optional_graph_negative + (
            (self.integer + pynutil.delete(NEMO_SPACE) + insert_space + self.numerator + self.denominator)
            | special(common_fraction)
            | special(mixed_half)
            | (self.numerator + self.denominator)
        )
        unicode_mixed_or_other = self.optional_graph_negative + (
            vulgar_other | (self.integer + optional_space + pynutil.insert(NEMO_SPACE) + vulgar_num_den)
        )
        final_graph = slash_fraction | unicode_mixed_or_other

        weighted_graph = (
            pynutil.add_weight(special(mixed_half), -0.002)
            | pynutil.add_weight(special(common_fraction), -0.001)
            | final_graph
        )

        self.graph = weighted_graph

        graph = self.add_tokens(self.graph)
        self.fst = graph.optimize()
