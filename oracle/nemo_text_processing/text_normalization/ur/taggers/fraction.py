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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ur.graph_utils import (
    NEMO_SPACE,
    UR_DEDH,
    UR_DHAI,
    UR_PAUNE,
    UR_SADHE,
    UR_SAVA,
    GraphFst,
)
from nemo_text_processing.text_normalization.ur.utils import get_abs_path

ONE_HALF = "1/2"
ONE_QUARTER = "1/4"
THREE_QUARTERS = "3/4"


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fraction
    "23 4/6" ->
    fraction { integer: "تئیس" numerator: "چار" denominator: "چھ"}
    4/6" ->
    fraction { numerator: "چار" denominator: "چھ"}


    Args:
        cardinal: cardinal GraphFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph

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
        half_input = pynini.accep(NEMO_SPACE + ONE_HALF) | (optional_space + pynini.accep("½"))
        quarter_input = pynini.accep(NEMO_SPACE + ONE_QUARTER) | (optional_space + pynini.accep("¼"))
        three_quarters_input = pynini.accep(NEMO_SPACE + THREE_QUARTERS) | (optional_space + pynini.accep("¾"))

        dedh_dhai_graph = (pynutil.delete("1") + pynini.cross(half_input, UR_DEDH)) | (
            pynutil.delete("2") + pynini.cross(half_input, UR_DHAI)
        )

        savva_numbers = cardinal_graph + pynini.cross(quarter_input, "")
        savva_graph = pynutil.insert(UR_SAVA) + pynutil.insert(NEMO_SPACE) + savva_numbers

        sadhe_numbers = cardinal_graph + pynini.cross(half_input, "")
        sadhe_graph = pynutil.insert(UR_SADHE) + pynutil.insert(NEMO_SPACE) + sadhe_numbers

        paune = pynini.string_file(get_abs_path("data/whitelist/paune_mappings.tsv"))
        paune_numbers = paune + pynini.cross(three_quarters_input, "")
        paune_graph = pynutil.insert(UR_PAUNE) + pynutil.insert(NEMO_SPACE) + paune_numbers

        vulgar_other = pynini.string_map(
            [
                ("⅓", "ایک\" denominator: \"تین"),
                ("⅔", "دو\" denominator: \"تین"),
                ("⅕", "ایک\" denominator: \"پانچ"),
                ("⅖", "دو\" denominator: \"پانچ"),
                ("⅗", "تین\" denominator: \"پانچ"),
                ("⅘", "چار\" denominator: \"پانچ"),
                ("⅙", "ایک\" denominator: \"چھ"),
                ("⅚", "پانچ\" denominator: \"چھ"),
                ("⅛", "ایک\" denominator: \"آٹھ"),
                ("⅜", "تین\" denominator: \"آٹھ"),
                ("⅝", "پانچ\" denominator: \"آٹھ"),
                ("⅞", "سات\" denominator: \"آٹھ"),
                ("⅐", "ایک\" denominator: \"سات"),
                ("⅑", "ایک\" denominator: \"نو"),
                ("⅒", "ایک\" denominator: \"دس"),
            ]
        )
        graph_mixed_vulgar = (
            self.optional_graph_negative
            + self.integer
            + optional_space
            + pynutil.insert(NEMO_SPACE + "numerator: \"")
            + vulgar_other
            + pynutil.insert("\"")
        )

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))

        graph_common_fraction = (
            pynutil.insert("morphosyntactic_features: \"")
            + common_fraction_map
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        graph_dedh_dhai = (
            pynutil.insert("morphosyntactic_features: \"")
            + dedh_dhai_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        graph_savva = (
            pynutil.insert("morphosyntactic_features: \"")
            + savva_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        graph_sadhe = (
            pynutil.insert("morphosyntactic_features: \"")
            + sadhe_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        graph_paune = (
            pynutil.insert("morphosyntactic_features: \"")
            + paune_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        final_graph = (
            self.optional_graph_negative
            + pynini.closure(self.integer + pynini.accep(NEMO_SPACE), 0, 1)
            + self.numerator
            + self.denominator
        )

        quarter_forms = (
            pynutil.add_weight(graph_common_fraction, -0.3)
            | pynutil.add_weight(graph_dedh_dhai, -0.2)
            | pynutil.add_weight(graph_paune, -0.2)
            | pynutil.add_weight(graph_savva, -0.1)
            | pynutil.add_weight(graph_sadhe, -0.1)
        )

        weighted_graph = (
            final_graph
            | graph_mixed_vulgar
            | (self.optional_graph_negative + quarter_forms)
        )

        self.graph = weighted_graph

        graph = self.graph
        graph = self.add_tokens(graph)
        self.fst = graph.optimize()
