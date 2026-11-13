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
    convert_space,
)

WHITELIST_ENTRIES = [
    # Titles & Honorifics
    ("ଡ.", "ଡକ୍ଟର"),
    ("ଡ․", "ଡକ୍ଟର"),
    ("ଡା.", "ଡାକ୍ତର"),
    ("ଡା․", "ଡାକ୍ତର"),
    ("ପ୍ରଫେ.", "ପ୍ରଫେସର"),
    ("ପ୍ରଫେ․", "ପ୍ରଫେସର"),
    ("ପ୍ରୋ.", "ପ୍ରଫେସର"),
    ("ପ୍ରୋ․", "ପ୍ରଫେସର"),
    ("ନଂ.", "ନମ୍ବର"),
    ("ନଂ․", "ନମ୍ବର"),
    ("କ୍ର.", "କ୍ରମିକ"),
    ("କ୍ର․", "କ୍ରମିକ"),
    ("ଇ.", "ଇତ୍ୟାଦି"),
    ("ଇ․", "ଇତ୍ୟାଦି"),
    ("Dr.", "ଡକ୍ଟର"),
    ("Dr", "ଡକ୍ଟର"),
    ("Prof.", "ପ୍ରଫେସର"),
    ("Prof", "ପ୍ରଫେସର"),
    ("Mr.", "ମିଷ୍ଟର"),
    ("Mr", "ମିଷ୍ଟର"),
    ("Mrs.", "ମିସେସ୍"),
    ("Mrs", "ମିସେସ୍"),
    ("Ms.", "ମିସ୍"),
    ("Ms", "ମିସ୍"),
    ("No.", "ନମ୍ବର"),
    ("No", "ନମ୍ବର"),
    ("etc.", "ଇତ୍ୟାଦି"),
    ("etc", "ଇତ୍ୟାଦି"),
    # Standalone symbols
    ("&", "ଏବଂ"),
    ("©", "କପିରାଇଟ୍"),
    ("§", "ଧାରା"),
    ("®", "ରେଜିଷ୍ଟର୍ଡ"),
    ("™", "ଟ୍ରେଡମାର୍କ"),
]


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying abbreviations and whitelist items in Odia:
        ଡ. ମିଶ୍ର -> tokens { name: "ଡକ୍ଟର" } tokens { name: "ମିଶ୍ର" }
        ନଂ. ୫ -> tokens { name: "ନମ୍ବର" } tokens { name: "ପାଞ୍ଚ" }
        A & B -> tokens { name: "A" } tokens { name: "ଏବଂ" } tokens { name: "B" }
        © ୨୦୨୪ -> tokens { name: "କପିରାଇଟ୍" } tokens { name: "ଦୁଇ ହଜାର ଚଉବିଶ" }
        § ୧୨ -> tokens { name: "ଧାରା" } tokens { name: "ବାର" }
    """

    def __init__(self, input_case: str = "cased", deterministic: bool = True, input_file: str = None, cardinal=None):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        wl_map = pynini.string_map(WHITELIST_ENTRIES).optimize()
        self.whitelist_graph = wl_map

        graph = pynutil.insert('name: "') + convert_space(wl_map) + pynutil.insert('"')
        self.fst = graph.optimize()
