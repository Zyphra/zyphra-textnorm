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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Danish fractions (Unicode vulgar and ASCII).
    Handles:
      - Vulgar fractions: "½", "¼", "¾", "⅓", "⅔", "⅕", "⅖", "⅗", "⅘", "⅙", "⅚", "⅛", "⅜", "⅝", "⅞", "⅐", "⅑", "⅒"
      - Slash fractions: "1/2", "1/3", "2/3", "1/4", "3/4", "4/5", etc.
      - Mixed fractions: "2 ½", "2 1/2", "23 4/5" -> "treogtyve og fire femtedele"
      - Negative fractions: "-1/2", "-2½", "−¾"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        # Unicode vulgar fractions
        vulgar = pynini.string_map(
            [
                ("½", "en halv"),
                ("⅓", "en tredjedel"),
                ("⅔", "to tredjedele"),
                ("¼", "en fjerdedel"),
                ("¾", "tre fjerdedele"),
                ("⅕", "en femtedel"),
                ("⅖", "to femtedele"),
                ("⅗", "tre femtedele"),
                ("⅘", "fire femtedele"),
                ("⅙", "en sjettedel"),
                ("⅚", "fem sjettedele"),
                ("⅛", "en ottendedel"),
                ("⅜", "tre ottendedele"),
                ("⅝", "fem ottendedele"),
                ("⅞", "syv ottendedele"),
                ("⅐", "en syvendedel"),
                ("⅑", "en niendedel"),
                ("⅒", "en tiendedel"),
            ]
        )

        # Slash fractions
        slash_common = pynini.string_map(
            [
                ("1/2", "en halv"),
                ("1/3", "en tredjedel"),
                ("2/3", "to tredjedele"),
                ("1/4", "en fjerdedel"),
                ("2/4", "to fjerdedele"),
                ("3/4", "tre fjerdedele"),
                ("1/5", "en femtedel"),
                ("2/5", "to femtedele"),
                ("3/5", "tre femtedele"),
                ("4/5", "fire femtedele"),
                ("1/6", "en sjettedel"),
                ("5/6", "fem sjettedele"),
                ("1/7", "en syvendedel"),
                ("1/8", "en ottendedel"),
                ("2/8", "to ottendedele"),
                ("3/8", "tre ottendedele"),
                ("4/8", "fire ottendedele"),
                ("5/8", "fem ottendedele"),
                ("6/8", "seks ottendedele"),
                ("7/8", "syv ottendedele"),
                ("1/9", "en niendedel"),
                ("1/10", "en tiendedel"),
                ("3/10", "tre tiendedele"),
                ("7/10", "syv tiendedele"),
                ("9/10", "ni tiendedele"),
                ("1/100", "en hundrededel"),
                ("1/1000", "en tusindedel"),
            ]
        )

        # Denominator mapping for general slash fractions
        den_singular = pynini.string_map(
            [
                ("2", "halv"),
                ("3", "tredjedel"),
                ("4", "fjerdedel"),
                ("5", "femtedel"),
                ("6", "sjettedel"),
                ("7", "syvendedel"),
                ("8", "ottendedel"),
                ("9", "niendedel"),
                ("10", "tiendedel"),
                ("12", "tolvtedel"),
                ("16", "sekstendedel"),
                ("20", "tyvendedel"),
                ("100", "hundrededel"),
                ("1000", "tusindedel"),
            ]
        )

        den_plural = pynini.string_map(
            [
                ("2", "halve"),
                ("3", "tredjedele"),
                ("4", "fjerdedele"),
                ("5", "femtedele"),
                ("6", "sjettedele"),
                ("7", "syvendedele"),
                ("8", "ottendedele"),
                ("9", "niendedele"),
                ("10", "tiendedele"),
                ("12", "tolvtedele"),
                ("16", "sekstendedele"),
                ("20", "tyvendedele"),
                ("100", "hundrededele"),
                ("1000", "tusindedele"),
            ]
        )

        slash = pynutil.delete("/")

        # Numerator 1
        one_num = pynini.cross("1", "en") + slash + pynutil.insert(" ") + den_singular
        # Numerator > 1
        not_one_num = pynini.difference(pynini.closure(NEMO_DIGIT, 1), "1")
        multi_int = (not_one_num @ cardinal.integer_common).optimize()
        multi_num = multi_int + slash + pynutil.insert(" ") + den_plural
        general_slash = one_num | multi_num

        pure_fraction = vulgar | slash_common | general_slash

        # Mixed fractions: e.g. "2 ½", "2 1/2", "23 4/5"
        opt_sp = pynini.closure(pynutil.delete(" "))
        mixed_fraction = (
            cardinal.integer_neuter
            + opt_sp
            + pynutil.insert(" og ")
            + pure_fraction
        )

        # Negative fractions: "-1/2", "-2½", "−¾"
        minus_sign = pynini.cross(pynini.union("-", "−"), "minus ")
        optional_minus = pynini.closure(minus_sign, 0, 1)

        all_fractions = pynutil.add_weight(
            optional_minus + (mixed_fraction | pure_fraction), -0.05
        )

        self.graph = all_fractions.optimize()

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
