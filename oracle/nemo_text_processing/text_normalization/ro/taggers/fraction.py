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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.ro.graph_utils import (
    RO_DASH,
    to_name_token,
)
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Romanian fractions, e.g.
        "½" -> tokens { name: "o jumătate" }
        "¼" -> tokens { name: "un sfert" }
        "¾" -> tokens { name: "trei sferturi" }
        "3/4" -> tokens { name: "trei sferturi" }
        "2½" -> tokens { name: "doi și jumătate" }
        "3 1/2" -> tokens { name: "trei și jumătate" }
        "-2½" -> tokens { name: "minus doi și jumătate" }
        "-3/4" -> tokens { name: "minus trei sferturi" }
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        # Vulgar unicode fractions
        vulgar_fractions = pynini.string_map([
            ("½", "o jumătate"),
            ("¼", "un sfert"),
            ("¾", "trei sferturi"),
            ("⅓", "o treime"),
            ("⅔", "două treimi"),
            ("⅕", "o cincime"),
            ("⅖", "două cincimi"),
            ("⅗", "trei cincimi"),
            ("⅘", "patru cincimi"),
            ("⅙", "o șesime"),
            ("⅚", "cinci șesimi"),
            ("⅛", "o optime"),
            ("⅜", "trei optimi"),
            ("⅝", "cinci optimi"),
            ("⅞", "șapte optimi"),
            ("⅐", "o șeptime"),
            ("⅑", "o noime"),
            ("⅒", "o zecime"),
        ])

        # Slashed fractions
        slashed_common = pynini.string_map([
            ("1/2", "o jumătate"),
            ("1/4", "un sfert"),
            ("3/4", "trei sferturi"),
            ("1/3", "o treime"),
            ("2/3", "două treimi"),
            ("1/5", "o cincime"),
            ("2/5", "două cincimi"),
            ("3/5", "trei cincimi"),
            ("4/5", "patru cincimi"),
            ("1/6", "o șesime"),
            ("5/6", "cinci șesimi"),
            ("1/8", "o optime"),
            ("3/8", "trei optimi"),
            ("5/8", "cinci optimi"),
            ("7/8", "șapte optimi"),
            ("1/10", "o zecime"),
        ])

        # General N/D fractions
        denominators_sing = pynini.string_map([
            ("2", "doime"),
            ("3", "treime"),
            ("4", "pătrime"),
            ("5", "cincime"),
            ("6", "șesime"),
            ("7", "șeptime"),
            ("8", "optime"),
            ("9", "noime"),
            ("10", "zecime"),
            ("100", "sutime"),
            ("1000", "miime"),
        ])

        denominators_plur = pynini.string_map([
            ("2", "doimi"),
            ("3", "treimi"),
            ("4", "sferturi"),
            ("5", "cincimi"),
            ("6", "șesimi"),
            ("7", "șeptimi"),
            ("8", "optimi"),
            ("9", "noimi"),
            ("10", "zecimi"),
            ("100", "sutimi"),
            ("1000", "miimi"),
        ])

        gen_frac_one = pynutil.delete("1/") + pynutil.insert("o ") + denominators_sing
        gen_frac_other = (
            cardinal.cardinal_numbers_fem
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + denominators_plur
        )

        pure_fraction = (
            slashed_common
            | vulgar_fractions
            | gen_frac_one
            | gen_frac_other
        ).optimize()

        # Mixed fractions: 2½, 2 1/2, 3 1/2 -> doi și jumătate, trei și jumătate
        # Mixed fractions with 1/2 use "și jumătate" or "și un sfert"
        half_sym = pynini.union("½", "1/2")
        quarter_sym = pynini.union("¼", "1/4")
        three_quarters_sym = pynini.union("¾", "3/4")

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        mixed_half = (
            cardinal.cardinal_numbers
            + opt_space
            + pynutil.delete(half_sym)
            + pynutil.insert(" și jumătate")
        )
        mixed_quarter = (
            cardinal.cardinal_numbers
            + opt_space
            + pynutil.delete(quarter_sym)
            + pynutil.insert(" și un sfert")
        )
        mixed_three_quarters = (
            cardinal.cardinal_numbers
            + opt_space
            + pynutil.delete(three_quarters_sym)
            + pynutil.insert(" și trei sferturi")
        )
        mixed_general = (
            cardinal.cardinal_numbers
            + pynutil.delete(" ")
            + pynutil.insert(" și ")
            + pure_fraction
        )

        mixed_fraction = (
            mixed_half
            | mixed_quarter
            | mixed_three_quarters
            | mixed_general
        ).optimize()

        # Negative fractions: -1/2, -3/4, -2½
        minus_prefix = pynutil.delete(pynini.union("-", "−")) + pynutil.insert("minus ")
        neg_fraction = minus_prefix + (mixed_fraction | pure_fraction)

        self.fraction_no_tokens = (
            neg_fraction
            | mixed_fraction
            | pure_fraction
        ).optimize()

        self.fst = to_name_token(self.fraction_no_tokens)
