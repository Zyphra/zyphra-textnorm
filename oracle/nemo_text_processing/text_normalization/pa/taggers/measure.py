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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.pa.graph_utils import (
    ASTERISK,
    PA_BY,
    LOWERCASE_X,
    NEMO_ALL_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    UPPERCASE_X,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.pa.utils import get_abs_path


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure (CLDR pa long unit names), e.g.
        -੧੨kg -> measure { cardinal { negative: "true" integer: "ਬਾਰਾਂ" } units: "ਕਿਲੋਗ੍ਰਾਮ" }
        ~੧੦ km -> measure { cardinal { negative: "approx" integer: "ਦਸ" } units: "ਕਿਲੋਮੀਟਰ" }
        ±੧੦% -> measure { cardinal { negative: "pm" integer: "ਦਸ" } units: "ਪ੍ਰਤੀਸ਼ਤ" }
        ੫੦% -> measure { cardinal { integer: "ਪੰਜਾਹ" } units: "ਪ੍ਰਤੀਸ਼ਤ" }
        ੧੦x੨੦ -> measure { cardinal { integer: "ਦਸ" } units: "ਬਾਈ" } tokens { cardinal { integer: "ਵੀਹ" } }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="classify")

        cardinal_graph = cardinal.final_graph
        point = pynutil.delete(".")
        decimal_integers = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")
        decimal_graph = decimal_integers + point + insert_space + decimal.graph_fractional
        unit_graph = pynini.string_file(get_abs_path("data/measure/unit.tsv"))

        sign_prefix = (
            pynini.cross(pynini.union("-", "−"), "\"true\"")
            | (pynini.cross("~", "\"approx\"") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "\"pm\"") + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + sign_prefix + insert_space,
            0,
            1,
        )

        unit = (
            pynutil.insert(NEMO_SPACE)
            + pynutil.insert("units: \"")
            + unit_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
        )

        symbol_graph = pynini.string_map(
            [
                (LOWERCASE_X, PA_BY),
                (UPPERCASE_X, PA_BY),
                (ASTERISK, PA_BY),
            ]
        )

        graph_decimal = (
            pynutil.insert("decimal { ")
            + optional_graph_negative
            + decimal_graph
            + pynutil.insert(" }")
            + delete_space
            + unit
        )

        # Exclude glued decades like "2020s", "1990s", "90s", "80s" from matching "s" as seconds!
        glued_decade_s = (
            (pynini.union("1", "2", "੧", "੨") + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + pynini.union("0", "੦") + "s")
            | (pynini.closure(pynini.accep("'"), 0, 1) + NEMO_ALL_DIGIT + pynini.union("0", "੦") + "s")
        )
        graph_cardinal = pynini.compose(
            pynini.difference(NEMO_SIGMA, glued_decade_s),
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert("integer: \"")
            + cardinal_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("}")
            + delete_space
            + unit,
        )

        range_dash = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynini.cross(pynini.union("-", "–", "—"), " ਤੋਂ ")
            + pynini.closure(pynutil.delete(" "), 0, 1)
        )
        range_num = cardinal_graph | (cardinal_graph + pynini.cross(".", " ਦਸ਼ਮਲਵ ") + decimal.graph)
        graph_range_measure = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert('integer: "')
            + range_num
            + range_dash
            + range_num
            + pynutil.insert('" }')
            + delete_space
            + unit
        )

        # Dimensions: 10x20
        dim_sep = pynini.closure(pynutil.delete(" "), 0, 1) + symbol_graph + pynini.closure(pynutil.delete(" "), 0, 1)
        graph_dimensions = (
            pynutil.insert("cardinal { integer: \"")
            + cardinal_graph
            + pynutil.insert("\" } units: \"")
            + dim_sep
            + insert_space
            + cardinal_graph
            + pynutil.insert("\"")
        )

        final_graph = (
            graph_range_measure
            | graph_cardinal
            | graph_decimal
            | graph_dimensions
        )

        self.fst = self.add_tokens(final_graph).optimize()
