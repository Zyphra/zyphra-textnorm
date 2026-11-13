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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.hi.graph_utils import (
    HI_DEDH,
    HI_DHAI,
    HI_PAUNE,
    HI_SADHE,
    HI_SAVVA,
    NEMO_SPACE,
    GraphFst,
)
from nemo_text_processing.text_normalization.hi.utils import get_abs_path

HI_ONE_HALF = pynini.union("१/२", "½")
HI_ONE_QUARTER = pynini.union("१/४", "¼")
HI_THREE_QUARTERS = pynini.union("३/४", "¾")


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fraction
    "२३ ४/६" ->
    fraction { integer: "तेईस" numerator: "चार" denominator: "छह"}
    ४/६" ->
    fraction { numerator: "चार" denominator: "छह"}


    Args:
        cardinal: cardinal GraphFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph

        opt_sp = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)
        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ")
            + (
                pynini.cross(pynini.union("-", "−"), '"true"')
                | pynini.cross(pynini.union("~", "≈") + opt_sp, '"approx"')
                | pynini.cross(pynini.accep("±") + opt_sp, '"plus_minus"')
            )
            + pynutil.insert(NEMO_SPACE),
            0,
            1,
        )

        self.integer = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")

        self.numerator = (
            pynutil.insert("numerator: \"")
            + cardinal_graph
            + pynini.cross(pynini.union("/", NEMO_SPACE + "/" + NEMO_SPACE), "\"")
            + pynutil.insert(NEMO_SPACE)
        )

        self.denominator = pynutil.insert("denominator: \"") + cardinal_graph + pynutil.insert("\"")

        opt_space = pynini.closure(pynini.accep(NEMO_SPACE), 0, 1)
        dedh_dhai_graph = (
            pynini.cross("१" + NEMO_SPACE + "१/२", HI_DEDH)
            | pynini.cross("२" + NEMO_SPACE + "१/२", HI_DHAI)
            | pynini.cross(pynini.union("१", "1") + opt_space + "½", HI_DEDH)
            | pynini.cross(pynini.union("२", "2") + opt_space + "½", HI_DHAI)
        )

        savva_suffix = pynini.union(NEMO_SPACE + "१/४", opt_space + "¼")
        savva_numbers = cardinal_graph + pynini.cross(savva_suffix, "")
        savva_graph = pynutil.insert(HI_SAVVA) + pynutil.insert(NEMO_SPACE) + savva_numbers

        sadhe_suffix = pynini.union(NEMO_SPACE + "१/२", opt_space + "½")
        sadhe_numbers = cardinal_graph + pynini.cross(sadhe_suffix, "")
        sadhe_graph = pynutil.insert(HI_SADHE) + pynutil.insert(NEMO_SPACE) + sadhe_numbers

        en_to_hi = pynini.string_file(get_abs_path("data/ordinal/en_to_hi_digit.tsv"))
        paune_hi = pynini.string_file(get_abs_path("data/whitelist/paune_mappings.tsv"))
        paune_en = pynini.compose(pynini.closure(en_to_hi, 1), paune_hi)
        paune_dev_suffix = NEMO_SPACE + "३/४"
        paune_uni_suffix = opt_space + "¾"
        paune_numbers = (paune_hi + pynini.cross(paune_dev_suffix | paune_uni_suffix, "")) | (
            paune_en + pynini.cross(paune_uni_suffix, "")
        )
        paune_graph = pynutil.insert(HI_PAUNE) + pynutil.insert(NEMO_SPACE) + paune_numbers

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))
        unicode_other_fractions = pynini.string_map(
            [
                ("⅓", 'numerator: "एक" denominator: "तीन"'),
                ("⅔", 'numerator: "दो" denominator: "तीन"'),
                ("⅕", 'numerator: "एक" denominator: "पाँच"'),
                ("⅖", 'numerator: "दो" denominator: "पाँच"'),
                ("⅗", 'numerator: "तीन" denominator: "पाँच"'),
                ("⅘", 'numerator: "चार" denominator: "पाँच"'),
                ("⅙", 'numerator: "एक" denominator: "छह"'),
                ("⅚", 'numerator: "पाँच" denominator: "छह"'),
                ("⅛", 'numerator: "एक" denominator: "आठ"'),
                ("⅜", 'numerator: "तीन" denominator: "आठ"'),
                ("⅝", 'numerator: "पाँच" denominator: "आठ"'),
                ("⅞", 'numerator: "सात" denominator: "आठ"'),
                ("⅐", 'numerator: "एक" denominator: "सात"'),
                ("⅑", 'numerator: "एक" denominator: "नौ"'),
                ("⅒", 'numerator: "एक" denominator: "दस"'),
            ]
        )
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
        ) | (
            self.optional_graph_negative
            + self.integer
            + pynutil.delete(opt_space)
            + pynutil.insert(NEMO_SPACE)
            + unicode_other_fractions
        )

        morpho_graphs = (
            pynutil.add_weight(graph_common_fraction, -0.3)
            | pynutil.add_weight(graph_dedh_dhai, -0.2)
            | pynutil.add_weight(graph_paune, -0.2)
            | pynutil.add_weight(graph_savva, -0.1)
            | pynutil.add_weight(graph_sadhe, -0.1)
        )

        weighted_graph = final_graph | (self.optional_graph_negative + morpho_graphs)

        self.graph = weighted_graph

        graph = self.graph
        graph = self.add_tokens(graph)
        self.fst = graph.optimize()
