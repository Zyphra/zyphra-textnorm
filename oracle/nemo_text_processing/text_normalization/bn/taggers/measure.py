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

from nemo_text_processing.text_normalization.bn.graph_utils import (
    ASTERISK,
    BN_BY,
    LOWERCASE_X,
    NEMO_ALL_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    UPPERCASE_X,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.bn.utils import get_abs_path


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure (CLDR bn long unit names; Bengali units are invariant), e.g.
        -১২kg -> measure { cardinal { negative: "true" integer: "বারো" } units: "কিলোগ্রাম" }
        ~১০ km -> measure { cardinal { negative: "approx" integer: "দশ" } units: "কিলোমিটার" }
        ±১০% -> measure { cardinal { negative: "pm" integer: "দশ" } units: "শতাংশ" }
        ৫০% -> measure { cardinal { integer: "পঞ্চাশ" } units: "শতাংশ" }
        ১০x২০ -> measure { cardinal { integer: "দশ" } units: "বাই" } tokens { cardinal { integer: "কুড়ি" } }

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
                (LOWERCASE_X, BN_BY),
                (UPPERCASE_X, BN_BY),
                (ASTERISK, BN_BY),
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
            (pynini.union("1", "2", "১", "২") + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + pynini.union("0", "০") + "s")
            | (pynini.closure(pynini.accep("'"), 0, 1) + NEMO_ALL_DIGIT + pynini.union("0", "০") + "s")
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
            + pynini.cross(pynini.union("-", "–", "—"), " থেকে ")
            + pynini.closure(pynutil.delete(" "), 0, 1)
        )
        range_num = cardinal_graph | (cardinal_graph + pynini.cross(".", " দশমিক ") + decimal.graph)
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

        # Handling cardinal clubbed with symbol as single token: ১০x২০ -> দশ বাই কুড়ি
        graph_exceptions = (
            pynutil.insert("cardinal { ")
            + optional_graph_negative
            + pynutil.insert("integer: \"")
            + cardinal_graph
            + pynutil.insert("\"")
            + pynutil.insert(" }")
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("units: \"")
            + symbol_graph
            + pynutil.insert("\"")
            + pynutil.insert(NEMO_SPACE)
            + pynutil.insert("} }")
            + insert_space
            + pynutil.insert("tokens { cardinal { ")
            + optional_graph_negative
            + pynutil.insert("integer: \"")
            + cardinal_graph
            + pynutil.insert("\"")
        )

        # Slightly preferred over a bare cardinal followed by a punctuation run, so "১০%।" reads the percent sign
        graph = (
            pynutil.add_weight(graph_decimal, -0.05)
            | pynutil.add_weight(graph_cardinal, -0.05)
            | pynutil.add_weight(graph_range_measure, -0.05)
            | pynutil.add_weight(graph_exceptions, 0.1)
        )
        self.graph = graph.optimize()

        final_graph = self.add_tokens(graph)
        self.fst = final_graph
