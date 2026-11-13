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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path, load_labels

unit_one = pynini.string_file(get_abs_path("data/measure/unit_one.tsv"))
unit_other = pynini.string_file(get_abs_path("data/measure/unit_other.tsv"))
unit_prefix = pynini.string_file(get_abs_path("data/measure/unit_prefix.tsv"))
unit_prefixed_one = pynini.string_file(get_abs_path("data/measure/unit_prefixed_one.tsv"))
unit_prefixed_other = pynini.string_file(get_abs_path("data/measure/unit_prefixed_other.tsv"))


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure, e.g.
        1 kg -> measure { cardinal { integer: "ಒಂದು" } units: "ಕಿಲೋಗ್ರಾಂ" preserve_order: true }
        5 kg -> measure { cardinal { integer: "ಐದು" } units: "ಕಿಲೋಗ್ರಾಂ" preserve_order: true }
        2.5 km -> measure { decimal { integer_part: "ಎರಡು" fractional_part: "ಐದು" } units: "ಕಿಲೋಮೀಟರ್" preserve_order: true }
        60 km/h -> measure { morphosyntactic_features: "ಗಂಟೆಗೆ" cardinal { integer: "ಅರವತ್ತು" } units: "ಕಿಲೋಮೀಟರ್" preserve_order: true }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="classify")

        cardinal_graph = cardinal.final_graph
        decimal_graph = decimal.final_graph_wo_negative

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        minus_sym = pynini.union("-", "−")
        neg = pynini.closure(pynutil.insert("negative: ") + pynini.cross(minus_sym, "\"true\" "), 0, 1)

        # Standard units
        card_one = pynini.cross("1", "ಒಂದು") | pynini.cross("೧", "ಒಂದು")
        meas_one = (
            pynutil.insert("cardinal { ")
            + neg
            + pynutil.insert("integer: \"")
            + card_one
            + pynutil.insert("\" } units: \"")
            + opt_space
            + unit_one
            + pynutil.insert("\"")
        )
        decade_glued_s = (
            pynini.union("1", "2", "೧", "೨")
            + (NEMO_DIGIT | pynini.union("೦", "೧", "೨", "೩", "೪", "೫", "೬", "೭", "೮", "೯")) ** 2
            + pynini.union("0", "೦")
            + "s"
        )
        unit_other_no_s = pynini.compose(
            pynini.difference(pynini.project(unit_other, "input"), "s"), unit_other
        ).optimize()
        unit_s_only = pynini.compose(pynini.accep("s"), unit_other).optimize()
        meas_other_no_s = (
            pynutil.insert("cardinal { ")
            + neg
            + pynutil.insert('integer: "')
            + cardinal_graph
            + pynutil.insert('" } units: "')
            + opt_space
            + unit_other_no_s
            + pynutil.insert('"')
        )
        s_branch = pynini.compose(
            pynini.difference(NEMO_SIGMA, decade_glued_s),
            pynutil.insert("cardinal { ")
            + neg
            + pynutil.insert('integer: "')
            + cardinal_graph
            + pynutil.insert('" } units: "')
            + opt_space
            + unit_s_only
            + pynutil.insert('"'),
        ).optimize()
        meas_card = meas_one | meas_other_no_s | s_branch

        meas_dec = (
            pynutil.insert("decimal { ")
            + neg
            + decimal_graph
            + pynutil.insert(" } units: \"")
            + opt_space
            + unit_other
            + pynutil.insert("\"")
        )

        def prefixed(num, unit_graph):
            graphs = []
            for sym, pre in load_labels(get_abs_path("data/measure/unit_prefix.tsv")):
                graphs.append(
                    pynutil.insert(f'morphosyntactic_features: "{pre}" ')
                    + num
                    + opt_space
                    + pynutil.insert('units: "')
                    + pynini.compose(pynini.accep(sym), unit_graph)
                    + pynutil.insert('"')
                )
            return pynini.union(*graphs)

        num_card_one = pynutil.insert("cardinal { ") + neg + pynutil.insert('integer: "') + card_one + pynutil.insert('" } ')
        num_card_other = pynutil.insert("cardinal { ") + neg + pynutil.insert('integer: "') + cardinal_graph + pynutil.insert('" } ')
        num_dec = pynutil.insert("decimal { ") + neg + decimal_graph + pynutil.insert(" } ")

        pref_card = prefixed(num_card_one, unit_prefixed_one) | prefixed(num_card_other, unit_prefixed_other)
        pref_dec = prefixed(num_dec, unit_prefixed_other)

        # Vulgar fractions with units: "½ kg" -> "ಅರ್ಧ ಕಿಲೋಗ್ರಾಂ", "2½ kg" -> "ಎರಡುವರೆ ಕಿಲೋಗ್ರಾಂ"
        half_units = (
            pynutil.insert('cardinal { integer: "')
            + (pynini.cross("½", "ಅರ್ಧ") | pynini.cross("1/2", "ಅರ್ಧ") | pynini.cross("2½", "ಎರಡುವರೆ") | pynini.cross("2 1/2", "ಎರಡುವರೆ") | pynini.cross("1½", "ಒಂದೂವರೆ") | pynini.cross("1 1/2", "ಒಂದೂವರೆ"))
            + pynutil.insert('" } units: "')
            + opt_space
            + unit_other
            + pynutil.insert('"')
        )

        # Measure ranges: "10-15%", "5-10 kg", "10–15%"
        dash = pynini.union("-", "–", "—")
        card_num = (pynini.closure(NEMO_ALL_DIGIT, 1, 6) @ cardinal_graph).optimize()
        range_card = (
            pynutil.insert("cardinal { integer: \"")
            + card_num
            + opt_space
            + pynini.cross(dash, " ರಿಂದ ")
            + opt_space
            + card_num
            + pynutil.insert("\" } units: \"")
            + opt_space
            + unit_other
            + pynutil.insert("\"")
        )

        standard_measure = meas_card | meas_dec | pref_card | pref_dec | half_units | range_card
        preserve = pynutil.insert(" preserve_order: true")
        self.graph = (standard_measure + preserve).optimize()
        self.fst = self.add_tokens(self.graph).optimize()
