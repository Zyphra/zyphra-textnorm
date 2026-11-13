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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path, load_labels

unit_one = pynini.string_file(get_abs_path("data/measure/unit_one.tsv"))
unit_other = pynini.string_file(get_abs_path("data/measure/unit_other.tsv"))
unit_prefixed_one = pynini.string_file(get_abs_path("data/measure/unit_prefixed_one.tsv"))
unit_prefixed_other = pynini.string_file(get_abs_path("data/measure/unit_prefixed_other.tsv"))


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure, e.g.
        1 kg -> measure { cardinal { integer: "ஒரு" } units: "கிலோகிராம்" preserve_order: true }
        50kg -> measure { cardinal { integer: "ஐம்பது" } units: "கிலோகிராம்" preserve_order: true }
        2.5 km -> measure { decimal { integer_part: "இரண்டு" fractional_part: "ஐந்து" } units: "கிலோமீட்டர்" ... }
        -15°C -> measure { cardinal { negative: "true" integer: "பதினைந்து" } units: "டிகிரி செல்சியஸ்" ... }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="classify")

        cardinal_graph = cardinal.attributive_graph
        one = pynini.compose(pynini.union("1", "௧"), cardinal_graph).optimize()
        not_one = pynini.difference(pynini.project(cardinal_graph, "input"), pynini.union("1", "௧"))
        many = pynini.compose(not_one, cardinal_graph).optimize()

        optional_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", "\"true\"") + insert_space, 0, 1
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

        # Numeric ranges with units/percent ("10-15%", "5-10 kg", "2.5–3.5 km") read with " முதல் ... வரை"
        range_digits = pynini.closure(NEMO_ALL_DIGIT, 1, 5)
        range_card = pynini.compose(range_digits, cardinal.final_graph).optimize()
        range_card_attr = pynini.compose(range_digits, cardinal_graph).optimize()
        range_dec_frac = (
            pynini.cross(".", " புள்ளி ") + pynini.compose(pynini.closure(NEMO_ALL_DIGIT, 1, 3), decimal.graph)
        ).optimize()
        range_dec = range_card + range_dec_frac
        range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " முதல் ")
        range_num = ((range_card | range_dec) + range_sep + (range_card_attr | range_dec)).optimize()
        range_number = pynutil.insert("cardinal { integer: \"") + range_num + pynutil.insert("\" }")

        # Vulgar fractions with units ("½ kg" -> "அரை கிலோகிராம்", "2½ kg" -> "இரண்டரை கிலோகிராம்")
        vulgar_one_words = pynini.string_map([("½", "அரை"), ("¼", "கால்"), ("¾", "முக்கால்")])
        mixed_half_words = pynini.string_map(
            [
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
        ) + (optional_space + pynutil.delete(pynini.union("1/2", "௧/௨", "½")))
        vulgar_one_number = number(vulgar_one_words)
        vulgar_other_number = number(mixed_half_words)

        def units(graph):
            return optional_space + pynutil.insert(" units: \"") + graph + pynutil.insert("\"")

        def prefixed(num, unit_graph):
            graphs = []
            for sym, pre in load_labels(get_abs_path("data/measure/unit_prefix.tsv")):
                graphs.append(
                    pynutil.insert(f"morphosyntactic_features: \"{pre}\" ")
                    + num
                    + units(pynini.compose(pynini.accep(sym), unit_graph))
                )
            return pynini.union(*graphs)
        num_one = (number(one) | vulgar_one_number).optimize()
        num_other = (number(many) | decimal_number | range_number | vulgar_other_number).optimize()

        # Glued 4-digit decade years ("1990s", "2020s") are decades, never seconds!
        decade_glued_s = (
            pynini.union("1", "2", "௧", "௨")
            + (NEMO_DIGIT | pynini.union("௦", "௧", "௨", "௩", "௪", "௫", "௬", "௭", "௮", "௯")) ** 2
            + pynini.union("0", "௦")
            + "s"
        )
        unit_other_no_s = pynini.compose(
            pynini.difference(pynini.project(unit_other, "input"), "s"), unit_other
        ).optimize()
        unit_s_only = pynini.compose(pynini.accep("s"), unit_other).optimize()
        s_branch = pynini.compose(
            pynini.difference(NEMO_SIGMA, decade_glued_s), num_other + units(unit_s_only)
        ).optimize()

        graph = (
            pynutil.add_weight(prefixed(num_one, unit_prefixed_one), -0.01)
            | pynutil.add_weight(prefixed(num_other, unit_prefixed_other), -0.01)
            | num_one + units(unit_one)
            | num_other + units(unit_other_no_s)
            | s_branch
        ) + pynutil.insert(" preserve_order: true")

        self.graph = graph.optimize()
        self.fst = self.add_tokens(self.graph).optimize()
