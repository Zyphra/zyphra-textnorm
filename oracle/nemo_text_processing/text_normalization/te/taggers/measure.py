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

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path, load_labels

# CLDR te long unit patterns: "one" for exactly 1, "other" for every other number (including decimals)
unit_one = pynini.string_file(get_abs_path("data/measure/unit_one.tsv"))
unit_other = pynini.string_file(get_abs_path("data/measure/unit_other.tsv"))
# Speed/pressure/bitrate units whose CLDR pattern puts a word before the number: "గంటకు {0} కిలోమీటర్లు"
unit_prefixed_one = pynini.string_file(get_abs_path("data/measure/unit_prefixed_one.tsv"))
unit_prefixed_other = pynini.string_file(get_abs_path("data/measure/unit_prefixed_other.tsv"))


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure, e.g.
        1 kg -> measure { cardinal { integer: "ఒక" } units: "కిలోగ్రాము" preserve_order: true }
        -12kg -> measure { cardinal { negative: "true" integer: "పన్నెండు" } units: "కిలోగ్రాములు" preserve_order: true }
        2.5 km -> measure { decimal { integer_part: "రెండు" fractional_part: "ఐదు" } units: "కిలోమీటర్లు" ... }
        60 km/h -> measure { morphosyntactic_features: "గంటకు" cardinal { integer: "అరవై" } units: "కిలోమీటర్లు" ... }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="classify")

        cardinal_graph = cardinal.attributive_graph
        one = pynini.compose(pynini.union("1", "౧"), cardinal_graph).optimize()
        not_one = pynini.difference(pynini.project(cardinal_graph, "input"), pynini.union("1", "౧"))
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

        # Numeric ranges with units/percent ("10-15%", "5-10 kg", "2.5–3.5 km") read with నుండి ("from ... to ...")
        range_digits = pynini.closure(NEMO_ALL_DIGIT, 1, 5)
        range_card = pynini.compose(range_digits, cardinal.final_graph).optimize()
        range_card_attr = pynini.compose(range_digits, cardinal_graph).optimize()
        range_dec_frac = (
            pynini.cross(".", " దశాంశం ") + pynini.compose(pynini.closure(NEMO_ALL_DIGIT, 1, 3), decimal.graph)
        ).optimize()
        range_dec = range_card + range_dec_frac
        range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " నుండి ")
        range_num = ((range_card | range_dec) + range_sep + (range_card_attr | range_dec)).optimize()
        range_number = pynutil.insert("cardinal { integer: \"") + range_num + pynutil.insert("\" }")

        # Vulgar fractions with units ("½ kg" -> "సగం కిలోగ్రాము", "2½ kg" -> "రెండున్నర కిలోగ్రాములు")
        vulgar_one_words = pynini.string_map([("½", "సగం"), ("¼", "పావు"), ("¾", "ముప్పావు")])
        ends_in_vowel_sign = NEMO_SIGMA + pynini.union("ు", "ి")
        mixed_half_words = (
            pynini.compose(pynini.compose(pynini.closure(NEMO_ALL_DIGIT, 1, 4), cardinal.final_graph), ends_in_vowel_sign)
            + optional_space
            + pynini.cross("½", "న్నర")
        ).optimize()
        vulgar_one_number = number(vulgar_one_words)
        vulgar_other_number = number(mixed_half_words)

        def units(graph):
            return optional_space + pynutil.insert(" units: \"") + graph + pynutil.insert("\"")

        def prefixed(num, unit_graph):
            # the prefix word depends on the unit symbol written after the number, so each unit is expanded
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
            pynini.union("1", "2", "౧", "౨")
            + (NEMO_DIGIT | pynini.union("౦", "౧", "౨", "౩", "౪", "౫", "౬", "౭", "౮", "౯")) ** 2
            + pynini.union("0", "౦")
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
            num_one + units(unit_one)
            | num_other + units(unit_other_no_s)
            | s_branch
            | prefixed(num_one, unit_prefixed_one)
            | prefixed(num_other, unit_prefixed_other)
        ) + pynutil.insert(" preserve_order: true")

        self.graph = graph.optimize()
        self.fst = self.add_tokens(self.graph).optimize()
