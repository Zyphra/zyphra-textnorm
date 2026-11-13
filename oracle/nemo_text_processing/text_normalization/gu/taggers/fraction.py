# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.gu.graph_utils import (
    GU_ADHI,
    GU_DODH,
    GU_PONA,
    GU_SADA,
    GU_SAVVA,
    NEMO_SPACE,
    GraphFst,
)
from nemo_text_processing.text_normalization.gu.utils import get_abs_path

GU_ONE_HALF = pynini.union("૧/૨", "1/2")
GU_ONE_QUARTER = pynini.union("૧/૪", "1/4")
GU_THREE_QUARTERS = pynini.union("૩/૪", "3/4")
UNICODE_FRACTIONS = pynini.string_map(
    [
        ("½", "1/2"),
        ("¼", "1/4"),
        ("¾", "3/4"),
        ("⅓", "1/3"),
        ("⅔", "2/3"),
        ("⅕", "1/5"),
        ("⅖", "2/5"),
        ("⅗", "3/5"),
        ("⅘", "4/5"),
        ("⅙", "1/6"),
        ("⅚", "5/6"),
        ("⅐", "1/7"),
        ("⅛", "1/8"),
        ("⅜", "3/8"),
        ("⅝", "5/8"),
        ("⅞", "7/8"),
        ("⅑", "1/9"),
        ("⅒", "1/10"),
    ]
).optimize()


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fractions in Gujarati, e.g.
        ૨૩ ૪/૬ -> fraction { integer_part: "તેવીસ" numerator: "ચાર" denominator: "છ" }
        ૧/૨ -> fraction { morphosyntactic_features: "અડધો" }
        ૧ ૧/૨ -> fraction { morphosyntactic_features: "દોઢ" }
        ૨ ૧/૨ -> fraction { morphosyntactic_features: "અઢી" }
        ૩ ૧/૨ -> fraction { morphosyntactic_features: "સાડા ત્રણ" }
        ૫ ૧/૪ -> fraction { morphosyntactic_features: "સવા પાંચ" }
        ૭ ૩/૪ -> fraction { morphosyntactic_features: "પોણા આઠ" }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transductions are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph

        delete_opt_sp = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)
        self.optional_graph_negative = pynini.closure(
            (
                (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true"'))
                | (pynini.cross("~", 'negative: "આશરે"') + delete_opt_sp)
                | (pynini.cross("±", 'negative: "વત્તા કે ઓછા"') + delete_opt_sp)
            )
            + pynutil.insert(NEMO_SPACE),
            0,
            1,
        )

        self.integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')

        self.numerator = (
            pynutil.insert('numerator: "')
            + cardinal_graph
            + pynini.cross(pynini.union("/", NEMO_SPACE + "/" + NEMO_SPACE), '"')
            + pynutil.insert(NEMO_SPACE)
        )

        self.denominator = pynutil.insert('denominator: "') + cardinal_graph + pynutil.insert('"')

        optional_space = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)
        half_part = (pynini.accep(NEMO_SPACE) + GU_ONE_HALF) | (optional_space + pynini.accep("½"))
        quarter_part = (pynini.accep(NEMO_SPACE) + GU_ONE_QUARTER) | (optional_space + pynini.accep("¼"))
        three_quarters_part = (pynini.accep(NEMO_SPACE) + GU_THREE_QUARTERS) | (optional_space + pynini.accep("¾"))

        dedh_dhai_graph = pynini.union(
            pynini.cross(pynini.union("૧", "1") + half_part, GU_DODH),
            pynini.cross(pynini.union("૨", "2") + half_part, GU_ADHI),
        )

        savva_numbers = cardinal_graph + pynutil.delete(quarter_part)
        savva_graph = pynutil.insert(GU_SAVVA) + pynutil.insert(NEMO_SPACE) + savva_numbers

        sadhe_numbers = cardinal_graph + pynutil.delete(half_part)
        sadhe_graph = pynutil.insert(GU_SADA) + pynutil.insert(NEMO_SPACE) + sadhe_numbers

        paune = pynini.string_file(get_abs_path("data/whitelist/paune_mappings.tsv"))
        paune_numbers = paune + pynutil.delete(three_quarters_part)
        paune_graph = pynutil.insert(GU_PONA) + pynutil.insert(NEMO_SPACE) + paune_numbers

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))

        graph_common_fraction = (
            pynutil.insert('morphosyntactic_features: "')
            + common_fraction_map
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )

        graph_dedh_dhai = (
            pynutil.insert('morphosyntactic_features: "')
            + dedh_dhai_graph
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )

        graph_savva = (
            pynutil.insert('morphosyntactic_features: "')
            + savva_graph
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )

        graph_sadhe = (
            pynutil.insert('morphosyntactic_features: "')
            + sadhe_graph
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )

        graph_paune = (
            pynutil.insert('morphosyntactic_features: "')
            + paune_graph
            + pynutil.insert('"')
            + pynutil.insert(NEMO_SPACE)
        )

        unicode_slash_fraction = pynini.compose(UNICODE_FRACTIONS, self.numerator + self.denominator)

        final_graph = (
            (pynini.closure(self.integer + pynini.accep(NEMO_SPACE), 0, 1) + self.numerator + self.denominator)
            | (pynini.closure(self.integer + optional_space + pynutil.insert(NEMO_SPACE), 0, 1) + unicode_slash_fraction)
        )

        weighted_graph = (
            final_graph
            | pynutil.add_weight(graph_common_fraction, -0.3)
            | pynutil.add_weight(graph_dedh_dhai, -0.2)
            | pynutil.add_weight(graph_paune, -0.2)
            | pynutil.add_weight(graph_savva, -0.1)
            | pynutil.add_weight(graph_sadhe, -0.1)
        )

        self.graph = self.optional_graph_negative + weighted_graph
        graph = self.add_tokens(self.graph)
        self.fst = graph.optimize()
