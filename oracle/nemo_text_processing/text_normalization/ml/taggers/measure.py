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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_DIGIT,
    NEMO_ML_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path

units_map = pynini.string_file(get_abs_path("data/measure/units.tsv"))


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure, e.g.
        1 kg -> measure { cardinal { integer: "ഒരു" } units: "കിലോഗ്രാം" preserve_order: true }
        5 kg -> measure { cardinal { integer: "അഞ്ച്" } units: "കിലോഗ്രാം" preserve_order: true }
        50kg -> measure { cardinal { integer: "അൻപത്" } units: "കിലോഗ്രാം" preserve_order: true }
        2.5 km -> measure { decimal { integer_part: "രണ്ട്" fractional_part: "അഞ്ച്" } units: "കിലോമീറ്റർ" ... }
        25% -> measure { cardinal { integer: "ഇരുപത്തിയഞ്ച്" } units: "ശതമാനം" ... }
        60 km/h -> measure { morphosyntactic_features: "മണിക്കൂറിൽ" cardinal { integer: "അറുപത്" } units: "കിലോമീറ്റർ" ... }
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="classify")

        cardinal_graph = cardinal.attributive_graph
        minus_char = pynini.union("-", "−")
        optional_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(minus_char, "\"true\"") + insert_space, 0, 1
        )
        optional_space = pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1)

        def number(graph):
            return (
                pynutil.insert("cardinal { ")
                + optional_negative
                + pynutil.insert("integer: \"")
                + graph
                + pynutil.insert("\" }")
            )

        decimal_number = (
            pynutil.insert("decimal { ")
            + optional_negative
            + decimal.graph_integer
            + pynutil.delete(".")
            + insert_space
            + decimal.graph_fractional
            + pynutil.insert(" }")
        ).optimize()

        # Ranges with units: 5-10 kg, 10-15%
        range_digits = pynini.closure(NEMO_ALL_DIGIT, 1, 5)
        range_card = pynini.compose(range_digits, cardinal.final_graph).optimize()
        range_card_attr = pynini.compose(range_digits, cardinal_graph).optimize()
        range_dec_frac = (
            pynini.cross(".", " ദശാംശം ") + pynini.compose(pynini.closure(NEMO_ALL_DIGIT, 1, 3), decimal.graph)
        ).optimize()
        range_dec = range_card + range_dec_frac
        range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " മുതൽ ")
        range_num = ((range_card | range_dec) + range_sep + (range_card_attr | range_dec) + pynutil.insert(" വരെ")).optimize()
        range_number = pynutil.insert("cardinal { integer: \"") + range_num + pynutil.insert("\" }")

        def units(graph):
            return optional_space + pynutil.insert(" units: \"") + graph + pynutil.insert("\"")

        # Speed special handling: 60 km/h -> morphosyntactic_features: "മണിക്കൂറിൽ" cardinal: "അറുപത്" units: "കിലോമീറ്റർ"
        km_h = pynini.accep("km/h")
        speed_unit = pynutil.delete(km_h) + pynutil.insert('units: "കിലോമീറ്റർ"')
        speed_rule = (
            pynutil.insert('morphosyntactic_features: "മണിക്കൂറിൽ" ')
            + (number(cardinal_graph) | decimal_number)
            + optional_space
            + speed_unit
        )

        num_any = (number(cardinal_graph) | decimal_number | range_number).optimize()

        # Exclude glued 4-digit decades (e.g. 1990s, 2020s)
        decade_glued_s = (
            pynini.union("1", "2", "൧", "൨")
            + (NEMO_DIGIT | NEMO_ML_DIGIT) ** 2
            + pynini.union("0", "൦")
            + "s"
        )
        non_decade = pynini.difference(NEMO_SIGMA, decade_glued_s)

        general_measure = pynini.compose(non_decade, num_any + units(units_map))

        graph = (
            pynutil.add_weight(speed_rule, -0.01)
            | general_measure
        ) + pynutil.insert(" preserve_order: true")

        self.graph = graph.optimize()
        self.fst = self.add_tokens(self.graph).optimize()
