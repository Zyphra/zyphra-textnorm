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

from nemo_text_processing.text_normalization.ar.graph_utils import NEMO_NOT_QUOTE, GraphFst, delete_space


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing dates, e.g.
        date { day: "خمسة وعشرون" month: "ديسمبر" year: "ألفان وأربعة وعشرون" }
            -> "خمسة وعشرون ديسمبر ألفان وأربعة وعشرون"
        date { year: "ألفان وعشرون" era: "ميلادي" } -> "ألفان وعشرون ميلادي"
        date { text: "عشرينيات القرن الحادي والعشرين" } -> "عشرينيات القرن الحادي والعشرين"
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="date", kind="verbalize", deterministic=deterministic)

        def field(name):
            return pynutil.delete(f'{name}: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        graph = (
            field("day")
            + delete_space
            + pynutil.insert(" ")
            + field("month")
            + delete_space
            + pynutil.insert(" ")
            + field("year")
        )
        graph |= field("year") + delete_space + pynutil.insert(" ") + field("era")
        graph |= field("text")
        self.fst = self.delete_tokens(graph).optimize()
