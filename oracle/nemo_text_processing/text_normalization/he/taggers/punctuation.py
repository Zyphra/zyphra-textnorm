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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst


class PunctuationFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew and ASCII punctuation.
    Includes Hebrew maqaf, gershayim, geresh, sof pasuq, and typographical quotes/dashes.
    """

    def __init__(self):
        super().__init__(name="punctuation", kind="classify")

        s = "!#$%&\'()*+,-./:;<=>?@^_`{|}~\""
        hebrew_marks = "־״׳׀׃«»„“”‘’–—…"
        punct = pynini.union(*s, *hebrew_marks, r"\[", r"\]")

        graph = pynutil.insert('name: "') + punct + pynutil.insert('"')
        self.fst = graph.optimize()
