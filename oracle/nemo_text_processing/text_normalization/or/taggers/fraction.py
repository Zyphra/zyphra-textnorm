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

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGITS,
    convert_space,
)
from .cardinal import CardinalFst, ODIA_CARDINALS_0_TO_99


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fractions in Odia:
        ୧/୨ or ½ -> tokens { name: "ଅଧା" }
        ୧/୪ or ¼ -> tokens { name: "ଚଉଠ" }
        ୩/୪ or ¾ -> tokens { name: "ତିନି ଚତୁର୍ଥାଂଶ" }
        ୧ ୧/୨ or 1½ -> tokens { name: "ଦେଢ଼" }
        ୨ ୧/୨ or 2½ -> tokens { name: "ଅଢ଼େଇ" }
        ୩ ୧/୨ or 3½ -> tokens { name: "ସାଢ଼େ ତିନି" }
        ୪ ୧/୪ -> tokens { name: "ସୱା ଚାରି" }
        ୪ ୩/୪ -> tokens { name: "ପୌଣେ ପାଞ୍ଚ" }
        -୨½ -> tokens { name: "ଋଣ ଅଢ଼େଇ" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        self.cardinal = cardinal

        # Named vulgar fractions
        vulgar_named = pynini.string_map([
            ("½", "ଅଧା"),
            ("¼", "ଚଉଠ"),
            ("¾", "ତିନି ଚତୁର୍ଥାଂଶ"),
            ("⅓", "ଏକ ତୃତୀୟାଂଶ"),
            ("⅔", "ଦୁଇ ତୃତୀୟାଂଶ"),
            ("⅕", "ଏକ ପଞ୍ଚମାଂଶ"),
            ("⅛", "ଏକ ଅଷ୍ଟମାଂଶ"),
            ("⅝", "ପାଞ୍ଚ ଅଷ୍ଟମାଂଶ"),
            ("⅞", "ସାତ ଅଷ୍ଟମାଂଶ"),
            ("⅒", "ଏକ ଦଶମାଂଶ"),
        ])

        slash_named = pynini.string_map([
            ("1/2", "ଅଧା"),
            ("୧/୨", "ଅଧା"),
            ("1/4", "ଚଉଠ"),
            ("୧/୪", "ଚଉଠ"),
            ("3/4", "ତିନି ଚତୁର୍ଥାଂଶ"),
            ("୩/୪", "ତିନି ଚତୁର୍ଥାଂଶ"),
            ("1/3", "ଏକ ତୃତୀୟାଂଶ"),
            ("୧/୩", "ଏକ ତୃତୀୟାଂଶ"),
            ("2/3", "ଦୁଇ ତୃତୀୟାଂଶ"),
            ("୨/୩", "ଦୁଇ ତୃତୀୟାଂଶ"),
            ("1/5", "ଏକ ପଞ୍ଚମାଂଶ"),
            ("୧/୫", "ଏକ ପଞ୍ଚମାଂଶ"),
            ("5/8", "ପାଞ୍ଚ ଅଷ୍ଟମାଂଶ"),
            ("୫/୮", "ପାଞ୍ଚ ଅଷ୍ଟମାଂଶ"),
            ("7/8", "ସାତ ଅଷ୍ଟମାଂଶ"),
            ("୭/୮", "ସାତ ଅଷ୍ଟମାଂଶ"),
            ("1/10", "ଏକ ଦଶମାଂଶ"),
            ("୧/୧୦", "ଏକ ଦଶମାଂଶ"),
        ])

        # Denominator ordinal-like names for generic fractions: <num> <den>ଆଂଶ or <num> ଭାଗରୁ <den>
        denominators = {
            "2": "ଦ୍ୱିତୀୟାଂଶ",
            "3": "ତୃତୀୟାଂଶ",
            "4": "ଚତୁର୍ଥାଂଶ",
            "5": "ପଞ୍ଚମାଂଶ",
            "6": "ଷଷ୍ଠାଂଶ",
            "7": "ସପ୍ତମାଂଶ",
            "8": "ଅଷ୍ଟମାଂଶ",
            "9": "ନବମାଂଶ",
            "10": "ଦଶମାଂଶ",
        }
        den_map = pynini.string_map([(k, v) for k, v in denominators.items()])

        num_part = (NORMALIZE_DIGITS @ cardinal.cardinal_numbers).optimize()
        den_part = (NORMALIZE_DIGITS @ den_map).optimize()

        slash_generic = (num_part + pynutil.delete("/") + pynutil.insert(" ") + den_part).optimize()

        simple_fraction = vulgar_named | slash_named | slash_generic

        # Special mixed fractions:
        # 1 1/2, 1½ -> ଦେଢ଼
        # 2 1/2, 2½ -> ଅଢ଼େଇ
        half_sym = pynini.union("1/2", "୧/୨", "½")
        quarter_sym = pynini.union("1/4", "୧/୪", "¼")
        three_quarters_sym = pynini.union("3/4", "୩/୪", "¾")

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        mixed_1_half = pynini.union("1", "୧") + opt_sp + half_sym
        graph_1_half = pynini.cross(mixed_1_half, "ଦେଢ଼")

        mixed_2_half = pynini.union("2", "୨") + opt_sp + half_sym
        graph_2_half = pynini.cross(mixed_2_half, "ଅଢ଼େଇ")

        # 3+ 1/2 -> ସାଢ଼େ <number> (e.g. 3½ -> ସାଢ଼େ ତିନି, 4½ -> ସାଢ଼େ ଚାରି)
        n_half_lead = pynutil.insert("ସାଢ଼େ ") + num_part + opt_sp + pynutil.delete(half_sym)

        # 4+ 1/4 -> ସୱା <number> (e.g. 4¼ -> ସୱା ଚାରି)
        n_quarter_lead = pynutil.insert("ସୱା ") + num_part + opt_sp + pynutil.delete(quarter_sym)

        # 4+ 3/4 -> ପୌଣେ <number+1>
        # e.g. 4 3/4 -> ପୌଣେ ପାଞ୍ଚ
        paune_map = pynini.string_map([
            ("1", "ଦୁଇ"), ("୧", "ଦୁଇ"),
            ("2", "ତିନି"), ("୨", "ତିନି"),
            ("3", "ଚାରି"), ("୩", "ଚାରି"),
            ("4", "ପାଞ୍ଚ"), ("୪", "ପାଞ୍ଚ"),
            ("5", "ଛଅ"), ("୫", "ଛଅ"),
            ("6", "ସାତ"), ("୬", "ସାତ"),
            ("7", "ଆଠ"), ("୭", "ଆଠ"),
            ("8", "ନଅ"), ("୮", "ନଅ"),
            ("9", "ଦଶ"), ("୯", "ଦଶ"),
        ])
        graph_paune = pynutil.insert("ପୌଣେ ") + paune_map + opt_sp + pynutil.delete(three_quarters_sym)

        # General mixed: <int> <fraction> -> <int> ପୂର୍ଣ୍ଣ <fraction>
        # e.g. 2 3/5 -> ଦୁଇ ପୂର୍ଣ୍ଣ ତିନି ପଞ୍ଚମାଂଶ
        int_lead = num_part + pynutil.delete(" ") + pynutil.insert(" ପୂର୍ଣ୍ଣ ") + simple_fraction

        mixed_fractions = (
            graph_1_half
            | graph_2_half
            | n_half_lead
            | n_quarter_lead
            | graph_paune
            | int_lead
        ).optimize()

        all_frac = (simple_fraction | mixed_fractions).optimize()

        neg_prefix = pynini.cross("-", "ଋଣ ") | pynini.cross("−", "ଋଣ ")
        with_neg = (all_frac | (neg_prefix + all_frac)).optimize()

        self.fraction_numbers = with_neg

        graph = pynutil.insert('name: "') + convert_space(with_neg) + pynutil.insert('"')
        self.fst = graph.optimize()
