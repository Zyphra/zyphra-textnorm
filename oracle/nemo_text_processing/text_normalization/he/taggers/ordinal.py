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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew ordinals.
    e.g. 1. -> ראשון
         2. -> שני
         5. -> חמישי
         ה-1 -> הראשון
         ה-20 -> העשרים
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        ord_dot_map = [
            ("1.", "ראשון"),
            ("2.", "שני"),
            ("3.", "שלישי"),
            ("4.", "רביעי"),
            ("5.", "חמישי"),
            ("6.", "שישי"),
            ("7.", "שביעי"),
            ("8.", "שמיני"),
            ("9.", "תשיעי"),
            ("10.", "עשירי"),
        ]
        ord_dot = pynini.string_map(ord_dot_map)

        # Prefix ה-
        ord_def_map = [
            ("ה-1", "הראשון"),
            ("ה-2", "השני"),
            ("ה-3", "השלישי"),
            ("ה-4", "הרביעי"),
            ("ה-5", "החמישי"),
            ("ה-6", "השישי"),
            ("ה-7", "השביעי"),
            ("ה-8", "השמיני"),
            ("ה-9", "התשיעי"),
            ("ה-10", "העשירי"),
            ("ה-11", "האחד עשר"),
            ("ה-12", "השנים עשר"),
            ("ה-13", "השלושה עשר"),
            ("ה-20", "העשרים"),
            ("ה-21", "העשרים ואחד"),
            ("ה-30", "השלושים"),
            ("ה-50", "החמישים"),
            ("ה-100", "המאה"),
        ]
        ord_def = pynini.string_map(ord_def_map)

        all_ordinals = ord_dot | ord_def
        self.fst = (
            pynutil.insert('name: "') + convert_space(all_ordinals) + pynutil.insert('"')
        ).optimize()
