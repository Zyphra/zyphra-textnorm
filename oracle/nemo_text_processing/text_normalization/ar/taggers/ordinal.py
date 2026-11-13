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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ar.graph_utils import GraphFst
from nemo_text_processing.text_normalization.ar.utils import get_abs_path


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying ordinals 1-999. Arabic has no written ordinal suffix, so only digits glued
    to the definite article are ordinals; bare digits stay cardinals. Names are CLDR %spellout-ordinal-masculine, e.g.
        "ال3" -> ordinal { integer: "الثالث" }
        "ال21" -> ordinal { integer: "الحادي والعشرون" }
    """

    def __init__(self):
        super().__init__(name="ordinal", kind="classify")
        ordinals = pynini.string_file(get_abs_path("data/ordinal/ordinals.tsv"))
        self.graph = (pynutil.delete("ال") + ordinals).optimize()
        final_graph = pynutil.insert('integer: "') + self.graph + pynutil.insert('"')
        self.fst = self.add_tokens(final_graph).optimize()
