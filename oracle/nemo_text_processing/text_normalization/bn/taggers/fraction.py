# Copyright (c) 2026 Zyphra, Inc.
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

from nemo_text_processing.text_normalization.bn.graph_utils import NEMO_SPACE, GraphFst
from nemo_text_processing.text_normalization.bn.utils import get_abs_path

BN_DEDH = "দেড়"  # 1 1/2
BN_ARAI = "আড়াই"  # 2 1/2
BN_SOYA = "সোয়া"  # n 1/4
BN_SARE = "সাড়ে"  # n 1/2
BN_POUNE = "পৌনে"  # n 3/4, read with the next number

ONE_HALF = pynini.union("1/2", "১/২")
ONE_QUARTER = pynini.union("1/4", "১/৪")
THREE_QUARTERS = pynini.union("3/4", "৩/৪")


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fraction
        "২৩ ৪/৬" -> fraction { integer_part: "তেইশ" numerator: "চার" denominator: "ছয়" }
        "৪/৬" -> fraction { numerator: "চার" denominator: "ছয়" }
        "৩ ১/২" -> fraction { morphosyntactic_features: "সাড়ে তিন" }

    Args:
        cardinal: cardinal GraphFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph

        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), "\"true\"") + pynutil.insert(NEMO_SPACE), 0, 1
        )

        self.integer = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")

        self.numerator = (
            pynutil.insert("numerator: \"")
            + cardinal_graph
            + pynini.cross(pynini.union("/", NEMO_SPACE + "/" + NEMO_SPACE), "\"")
            + pynutil.insert(NEMO_SPACE)
        )

        self.denominator = pynutil.insert("denominator: \"") + cardinal_graph + pynutil.insert("\"")

        optional_space = pynini.closure(pynini.accep(NEMO_SPACE), 0, 1)
        half_suffix = (pynini.accep(NEMO_SPACE) + ONE_HALF) | (optional_space + pynini.accep("½"))
        quarter_suffix = (pynini.accep(NEMO_SPACE) + ONE_QUARTER) | (optional_space + pynini.accep("¼"))
        three_quarters_suffix = (pynini.accep(NEMO_SPACE) + THREE_QUARTERS) | (optional_space + pynini.accep("¾"))

        dedh_arai_graph = pynini.union(
            pynini.cross(pynini.union("1", "১") + half_suffix, BN_DEDH),
            pynini.cross(pynini.union("2", "২") + half_suffix, BN_ARAI),
        )

        soya_graph = pynutil.insert(BN_SOYA + NEMO_SPACE) + cardinal_graph + pynutil.delete(quarter_suffix)
        sare_graph = pynutil.insert(BN_SARE + NEMO_SPACE) + cardinal_graph + pynutil.delete(half_suffix)

        next_number = pynini.string_file(get_abs_path("data/fraction/next_number.tsv"))
        poune_graph = pynutil.insert(BN_POUNE + NEMO_SPACE) + next_number + pynutil.delete(three_quarters_suffix)

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))

        vulgar_other = pynini.string_map(
            [
                ("⅐", 'numerator: "এক" denominator: "সাত"'),
                ("⅑", 'numerator: "এক" denominator: "নয়"'),
                ("⅒", 'numerator: "এক" denominator: "দশ"'),
                ("⅕", 'numerator: "এক" denominator: "পাঁচ"'),
                ("⅖", 'numerator: "দুই" denominator: "পাঁচ"'),
                ("⅗", 'numerator: "তিন" denominator: "পাঁচ"'),
                ("⅘", 'numerator: "চার" denominator: "পাঁচ"'),
                ("⅙", 'numerator: "এক" denominator: "ছয়"'),
                ("⅚", 'numerator: "পাঁচ" denominator: "ছয়"'),
                ("⅛", 'numerator: "এক" denominator: "আট"'),
                ("⅜", 'numerator: "তিন" denominator: "আট"'),
                ("⅝", 'numerator: "পাঁচ" denominator: "আট"'),
                ("⅞", 'numerator: "সাত" denominator: "আট"'),
            ]
        )
        vulgar_mixed_only = pynini.string_map(
            [
                ("⅓", 'numerator: "এক" denominator: "তিন"'),
                ("⅔", 'numerator: "দুই" denominator: "তিন"'),
            ]
        )
        vulgar_standalone = self.optional_graph_negative + vulgar_other
        vulgar_mixed = (
            self.optional_graph_negative
            + self.integer
            + pynutil.delete(optional_space)
            + pynutil.insert(NEMO_SPACE)
            + (vulgar_other | vulgar_mixed_only)
        )

        def features(graph):
            return (
                pynutil.insert("morphosyntactic_features: \"")
                + graph
                + pynutil.insert("\"")
                + pynutil.insert(NEMO_SPACE)
            )

        final_graph = (
            self.optional_graph_negative
            + pynini.closure(self.integer + pynini.accep(NEMO_SPACE), 0, 1)
            + self.numerator
            + self.denominator
        )

        weighted_graph = (
            final_graph
            | vulgar_standalone
            | vulgar_mixed
            | pynutil.add_weight(
                self.optional_graph_negative
                + (
                    pynutil.add_weight(features(common_fraction_map), -0.3)
                    | pynutil.add_weight(features(dedh_arai_graph), -0.2)
                    | pynutil.add_weight(features(poune_graph), -0.2)
                    | pynutil.add_weight(features(soya_graph), -0.1)
                    | pynutil.add_weight(features(sare_graph), -0.1)
                ),
                0.0,
            )
        )

        self.graph = weighted_graph

        graph = self.graph
        graph = self.add_tokens(graph)
        self.fst = graph.optimize()
