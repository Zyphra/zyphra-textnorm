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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_SIGMA, GraphFst
from nemo_text_processing.text_normalization.ka.graph_utils import with_suffix

VULGAR_FRACTIONS = [
    ("½", "ერთი", "მეორედი"),
    ("¼", "ერთი", "მეოთხედი"),
    ("¾", "სამი", "მეოთხედი"),
    ("⅓", "ერთი", "მესამედი"),
    ("⅔", "ორი", "მესამედი"),
    ("⅕", "ერთი", "მეხუთედი"),
    ("⅖", "ორი", "მეხუთედი"),
    ("⅗", "სამი", "მეხუთედი"),
    ("⅘", "ოთხი", "მეხუთედი"),
    ("⅙", "ერთი", "მეექვსედი"),
    ("⅚", "ხუთი", "მეექვსედი"),
    ("⅛", "ერთი", "მერვედი"),
    ("⅜", "სამი", "მერვედი"),
    ("⅝", "ხუთი", "მერვედი"),
    ("⅞", "შვიდი", "მერვედი"),
    ("⅐", "ერთი", "მეშვიდედი"),
    ("⅑", "ერთი", "მეცხრედი"),
    ("⅒", "ერთი", "მეათედი"),
]


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fractions, e.g.
        "1/3" -> fraction { numerator: "ერთი" denominator: "მესამედი" }
        "50/85" -> fraction { numerator: "ორმოცდაათი" denominator: "ოთხმოცდამეხუთედი" }
        "2½" -> fraction { integer_part: "ორი" numerator: "ერთი" denominator: "მეორედი" }
        "-2½" -> fraction { negative: "true" integer_part: "ორი" numerator: "ერთი" denominator: "მეორედი" }
    """

    def __init__(self, cardinal: GraphFst, ordinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify")
        cardinal_graph = cardinal.all_nums_no_tokens

        # Denominator replaces final "ე" of the ordinal with "ედი":
        e_to_edi = pynini.cdrewrite(pynini.cross("ე", "ედი"), "", "[EOS]", NEMO_SIGMA)
        denominator_graph = (ordinal.graph @ e_to_edi).optimize()
        denominator_suffixed = denominator_graph | with_suffix(denominator_graph)

        numerator = pynutil.insert('numerator: "') + cardinal_graph + pynutil.insert('"')
        denominator = pynutil.insert(' denominator: "') + denominator_suffixed + pynutil.insert('"')
        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('" ')
        negative = pynini.closure(
            pynini.cross("-", 'negative: "true" ') | pynini.cross("−", 'negative: "true" '),
            0,
            1,
        )

        slash_graph = numerator + pynutil.delete(pynini.union("/", "\u2044")) + denominator
        slash_mixed = negative + pynini.closure(integer + pynini.closure(pynutil.delete(" "), 0, 1), 0, 1) + slash_graph

        vulgar_graph = pynini.union(
            *[
                pynutil.insert(f'numerator: "{num}" denominator: "')
                + (pynini.cross(sym, den) | with_suffix(pynini.cross(sym, den)))
                + pynutil.insert('"')
                for sym, num, den in VULGAR_FRACTIONS
            ]
        )
        vulgar_mixed = negative + pynini.closure(integer + pynini.closure(pynutil.delete(" "), 0, 1), 0, 1) + vulgar_graph

        final_graph = slash_mixed | vulgar_mixed
        self.fst = self.add_tokens(final_graph).optimize()
