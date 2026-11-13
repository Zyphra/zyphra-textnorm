# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål fractions.
    e.g. 1/2 -> en halv
         3/4 -> tre fjerdedeler
         2½ -> to og en halv
         -2½ -> minus to og en halv
         ⅓ -> en tredjedel
         ⅔ -> to tredjedeler
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        vulgar_map = [
            ("½", "en halv"),
            ("⅓", "en tredjedel"),
            ("⅔", "to tredjedeler"),
            ("¼", "en fjerdedel"),
            ("¾", "tre fjerdedeler"),
            ("⅕", "en femtedel"),
            ("⅖", "to femtedeler"),
            ("⅗", "tre femtedeler"),
            ("⅘", "fire femtedeler"),
            ("⅙", "en sjettedel"),
            ("⅚", "fem sjettedeler"),
            ("⅛", "en åttendedel"),
            ("⅜", "tre åttendedeler"),
            ("⅝", "fem åttendedeler"),
            ("⅞", "sju åttendedeler"),
            ("⅑", "en niendedel"),
            ("⅒", "en tiendedel"),
        ]
        vulgar = pynini.string_map(vulgar_map)

        # Standard slash fractions
        slashed_common = pynini.string_map(
            [
                ("1/2", "en halv"),
                ("1/3", "en tredjedel"),
                ("2/3", "to tredjedeler"),
                ("1/4", "en fjerdedel"),
                ("3/4", "tre fjerdedeler"),
                ("1/5", "en femtedel"),
                ("2/5", "to femtedeler"),
                ("3/5", "tre femtedeler"),
                ("4/5", "fire femtedeler"),
                ("1/6", "en sjettedel"),
                ("5/6", "fem sjettedeler"),
                ("1/8", "en åttendedel"),
                ("3/8", "tre åttendedeler"),
                ("5/8", "fem åttendedeler"),
                ("7/8", "sju åttendedeler"),
                ("1/10", "en tiendedel"),
                ("24/12", "tjuefire tolvtedeler"),
            ]
        )

        # Generalized slashed fraction
        denominators_sg = pynini.string_map(
            [
                ("2", "halvdel"),
                ("3", "tredjedel"),
                ("4", "fjerdedel"),
                ("5", "femtedel"),
                ("6", "sjettedel"),
                ("7", "sjuendedel"),
                ("8", "åttendedel"),
                ("9", "niendedel"),
                ("10", "tiendedel"),
                ("12", "tolvtedel"),
                ("100", "hundredel"),
                ("1000", "tusendel"),
            ]
        )
        denominators_pl = pynini.string_map(
            [
                ("2", "halvdeler"),
                ("3", "tredjedeler"),
                ("4", "fjerdedeler"),
                ("5", "femtedeler"),
                ("6", "sjettedeler"),
                ("7", "sjuendedeler"),
                ("8", "åttendedeler"),
                ("9", "niendedeler"),
                ("10", "tiendedeler"),
                ("12", "tolvtedeler"),
                ("100", "hundredeler"),
                ("1000", "tusendeler"),
            ]
        )

        digits = pynini.closure(NEMO_DIGIT, 1)
        not_one = pynini.difference(digits, pynini.accep("1"))

        gen_frac_one = (
            pynini.cross("1", "en")
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + denominators_sg
        )
        gen_frac_many = (
            (not_one @ cardinal.cardinal)
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + denominators_pl
        )
        gen_frac = gen_frac_one | gen_frac_many

        base_fraction = vulgar | pynutil.add_weight(slashed_common, -0.1) | gen_frac

        # Mixed fractions (e.g. 2½, 2 1/2)
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        mixed = (
            cardinal.cardinal
            + opt_space
            + pynutil.insert(" og ")
            + base_fraction
        )

        # Negative fractions (-2½, -1/2, −¾)
        neg_sign = pynini.cross("-", "minus ") | pynini.cross("−", "minus ")
        neg_fraction = neg_sign + (mixed | base_fraction)

        all_fractions = (
            neg_fraction
            | mixed
            | base_fraction
        )

        self.graph = all_fractions.optimize()
        self.fst = self.graph
