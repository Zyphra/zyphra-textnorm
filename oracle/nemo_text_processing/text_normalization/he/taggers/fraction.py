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
    convert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew fractions.
    e.g. ½ -> חצי
         1½ -> אחד וחצי
         -2½ -> מינוס שניים וחצי
         ¾ -> שלושה רבעים
         1/2 -> חצי
         2 1/2 -> שניים וחצי
         7/12 -> שבע חלקי שתים עשרה
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        vulgar_map = [
            ("½", "חצי"),
            ("⅓", "שליש"),
            ("⅔", "שני שליש"),
            ("¼", "רבע"),
            ("¾", "שלושה רבעים"),
            ("⅕", "חמישית"),
            ("⅖", "שתי חמישיות"),
            ("⅗", "שלוש חמישיות"),
            ("⅘", "ארבע חמישיות"),
            ("⅙", "שישית"),
            ("⅚", "חמש שישיות"),
            ("⅐", "שביעית"),
            ("⅛", "שמינית"),
            ("⅜", "שלוש שמיניות"),
            ("⅝", "חמש שמיניות"),
            ("⅞", "שבע שמיניות"),
            ("⅑", "תשיעית"),
            ("⅒", "עשירית"),
        ]
        vulgar_fractions = pynini.string_map(vulgar_map)
        self.vulgar_fractions = vulgar_fractions

        slash_map = [
            ("1/2", "חצי"),
            ("1/3", "שליש"),
            ("2/3", "שני שליש"),
            ("1/4", "רבע"),
            ("3/4", "שלושה רבעים"),
            ("1/5", "חמישית"),
            ("2/5", "שתי חמישיות"),
            ("3/5", "שלוש חמישיות"),
            ("4/5", "ארבע חמישיות"),
            ("1/6", "שישית"),
            ("5/6", "חמש שישיות"),
            ("1/7", "שביעית"),
            ("1/8", "שמינית"),
            ("3/8", "שלוש שמיניות"),
            ("5/8", "חמש שמיניות"),
            ("7/8", "שבע שמיניות"),
            ("1/9", "תשיעית"),
            ("1/10", "עשירית"),
            ("3/10", "שלוש עשיריות"),
            ("7/10", "שבע עשיריות"),
            ("9/10", "תשע עשיריות"),
        ]
        slash_named = pynini.string_map(slash_map)
        self.slash_named = slash_named

        base_fractions = vulgar_fractions | slash_named

        # Mixed fractions: integer + vulgar or slash
        # Integer in mixed fraction: 1 -> אחד, 2 -> שניים, 3 -> שלושה...
        # In Hebrew, mixed numbers use masculine cardinal for the whole part:
        # 1½: אחד וחצי; 2½: שניים וחצי; 3½: שלושה וחצי; 4¼: ארבעה ורבע
        int_mixed_1 = pynini.cross("1", "אחד")
        int_mixed_2 = pynini.cross("2", "שניים")
        int_mixed_3_9 = pynini.string_map([
            ("3", "שלושה"),
            ("4", "ארבעה"),
            ("5", "חמישה"),
            ("6", "שישה"),
            ("7", "שבעה"),
            ("8", "שמונה"),
            ("9", "תשעה"),
        ])
        int_mixed_over = (
            pynutil.add_weight(cardinal.base_num_m, -0.05)
            | pynutil.add_weight(cardinal.base_num_f, 0.5)
        )
        int_mixed = (int_mixed_1 | int_mixed_2 | int_mixed_3_9 | int_mixed_over).optimize()

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        req_space = pynutil.delete(" ")

        # Integer + " ו" + fraction
        # For vulgar fraction without space: 1½ -> אחד וחצי
        mixed_vulgar = int_mixed + opt_space + pynutil.insert(" ו") + vulgar_fractions
        # For slash fraction with space: 2 1/2 -> שניים וחצי
        mixed_slash = int_mixed + req_space + pynutil.insert(" ו") + slash_named

        mixed_fractions = mixed_vulgar | mixed_slash
        self.mixed_fractions = mixed_fractions

        # General slash fraction: N/M -> N חלקי M
        slash_general = (
            cardinal.base_num_f
            + pynini.cross("/", " חלקי ")
            + cardinal.base_num_f
        )

        all_fracs_pos = (
            pynutil.add_weight(mixed_fractions, 0.9)
            | pynutil.add_weight(base_fractions, 0.95)
            | pynutil.add_weight(slash_general, 1.05)
        ).optimize()

        # Negatives
        neg = pynini.cross("-", "מינוס ") | pynini.cross("−", "מינוס ")
        opt_neg = pynini.closure(neg, 0, 1)

        fraction_total = (opt_neg + all_fracs_pos).optimize()
        self.fraction_total = fraction_total

        self.fst = (
            pynutil.insert('name: "') + convert_space(fraction_total) + pynutil.insert('"')
        ).optimize()
