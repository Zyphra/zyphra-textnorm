# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_NON_BREAKING_SPACE,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.hu.utils import get_abs_path, naive_inflector


def _load_measure_units():
    with open(get_abs_path("data/measures/measurements.tsv")) as tsv:
        rows = [line.strip().split("\t") for line in tsv if line.strip()]

    base_dict = {}
    all_dict = {}
    for key, val in rows:
        base_dict.setdefault(key, val)
        all_dict.setdefault(key, val)
        if " " not in val:
            for ikey, ival in naive_inflector(key, val, False):
                all_dict.setdefault(ikey, ival)

    for key, val in rows:
        lkey = key.lower()
        base_dict.setdefault(lkey, val)
        all_dict.setdefault(lkey, val)
        if " " not in val:
            for ikey, ival in naive_inflector(lkey, val, False):
                all_dict.setdefault(ikey, ival)

    base_fst = convert_space(pynini.string_map(list(base_dict.items()))).optimize()
    all_fst = convert_space(pynini.string_map(list(all_dict.items()))).optimize()
    return base_fst, all_fst


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure,  e.g.
        "2,4 oz" -> measure { cardinal { integer_part: "zwei" fractional_part: "vier" units: "unzen" preserve_order: true } }
        "1 oz" -> measure { cardinal { integer: "zwei" units: "unze" preserve_order: true } }
        "1 million oz" -> measure { cardinal { integer: "eins" quantity: "million" units: "unze" preserve_order: true } }
        This class also converts words containing numbers and letters
        e.g. "a-8" —> "a acht"
        e.g. "1,2-a" —> "ein komma zwei a"

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, fraction: GraphFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)
        cardinal_graph = cardinal.graph

        base_unit_singular, graph_unit_singular = _load_measure_units()
        optional_graph_negative = pynini.closure(pynini.cross(pynini.union("-", "−"), 'negative: "true" '), 0, 1)

        graph_unit_denominator = (
            pynini.cross("/", "per") + pynutil.insert(NEMO_NON_BREAKING_SPACE) + graph_unit_singular
        )

        unit_expr = (
            graph_unit_singular
            | (base_unit_singular + pynutil.insert(NEMO_NON_BREAKING_SPACE) + graph_unit_denominator)
            | graph_unit_denominator
        ).optimize()

        unit_singular_graph = (pynutil.insert("units: \"") + unit_expr + pynutil.insert("\"")).optimize()

        # Exclude glued international decades like "1990s" / "2020s" from matching "s" (másodperc)
        unit_expr_no_s = pynini.compose(NEMO_SIGMA - "s", unit_expr).optimize()
        glued_s_unit = pynutil.insert("units: \"") + pynini.cross("s", "másodperc") + pynutil.insert("\"")
        non_decade_unit_graph = (
            pynutil.insert("units: \"")
            + (pynini.closure(pynutil.delete(" "), 0, 1) + unit_expr_no_s | pynini.cross(" s", "másodperc"))
            + pynutil.insert("\"")
        ).optimize()

        glued_intl_decade = pynini.union("18", "19", "20") + NEMO_DIGIT + "0"
        non_decade_cardinal = (
            pynini.compose(NEMO_SIGMA - glued_intl_decade, cardinal.graph) @ cardinal.counted
        ) | cardinal.range

        subgraph_decimal = decimal.fst + insert_space + pynini.closure(pynutil.delete(" "), 0, 1) + unit_singular_graph

        subgraph_cardinal = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert("integer: \"")
            + ((cardinal.graph @ cardinal.counted) | cardinal.range)
            + pynutil.insert("\" } ")
            + non_decade_unit_graph
        ) | (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert("integer: \"")
            + non_decade_cardinal
            + pynutil.insert("\" } ")
            + glued_s_unit
        )

        subgraph_fraction = (
            fraction.fst + insert_space + pynini.closure(pynutil.delete(" "), 0, 1) + unit_singular_graph
        )

        # "1990-ben", "3-szor": a case suffix after a number is glued to it by the cardinal tagger
        cardinal_dash_alpha = (
            pynutil.insert("cardinal { integer: \"")
            + cardinal_graph
            + pynutil.delete('-')
            + pynutil.insert("\" } units: \"")
            + (pynini.closure(NEMO_ALPHA, 1) - cardinal.case_suffix)
            + pynutil.insert("\"")
        )

        alpha_dash_cardinal = (
            pynutil.insert("units: \"")
            + pynini.closure(NEMO_ALPHA, 1)
            + pynutil.delete('-')
            + pynutil.insert("\"")
            + pynutil.insert(" cardinal { integer: \"")
            + cardinal_graph
            + pynutil.insert("\" }")
        )

        decimal_dash_alpha = (
            pynutil.insert("decimal { ")
            + decimal.final_graph_wo_negative
            + pynutil.delete('-')
            + pynutil.insert(" } units: \"")
            + pynini.closure(NEMO_ALPHA, 1)
            + pynutil.insert("\"")
        )

        decimal_times = (
            pynutil.insert("decimal { ")
            + decimal.final_graph_wo_negative
            + pynutil.insert(" } units: \"")
            + pynini.union('x', 'X')
            + pynutil.insert("\"")
        )

        cardinal_times = (
            pynutil.insert("cardinal { integer: \"")
            + cardinal_graph
            + pynutil.insert("\" } units: \"")
            + pynini.union('x', 'X')
            + pynutil.insert("\"")
        )

        alpha_dash_decimal = (
            pynutil.insert("units: \"")
            + pynini.closure(NEMO_ALPHA, 1)
            + pynutil.delete('-')
            + pynutil.insert("\"")
            + pynutil.insert(" decimal { ")
            + decimal.final_graph_wo_negative
            + pynutil.insert(" }")
        )

        final_graph = (
            subgraph_decimal
            | subgraph_cardinal
            | cardinal_dash_alpha
            | alpha_dash_cardinal
            | decimal_dash_alpha
            | decimal_times
            | alpha_dash_decimal
            | subgraph_fraction
            | cardinal_times
        )
        final_graph += pynutil.insert(" preserve_order: true")
        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
