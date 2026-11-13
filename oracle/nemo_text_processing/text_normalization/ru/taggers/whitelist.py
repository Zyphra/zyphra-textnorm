# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_CHAR, GraphFst, convert_space
from nemo_text_processing.text_normalization.ru.alphabet import RU_ALPHA, TO_CYRILLIC
from nemo_text_processing.text_normalization.ru.utils import get_abs_path, load_labels


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying whitelist, e.g.
        г-н -> tokens { name: "господин" }
        д-р -> tokens { name: "доктор" }
    This class has highest priority among all classifier grammars. Whitelisted tokens are defined and loaded from "data/whitelist.tsv".
    """

    def __init__(self, input_case: str, deterministic: bool = True, input_file: str = None):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        def _get_whitelist_graph(input_case, file):
            whitelist = load_labels(file)
            entries = []
            seen = set()
            for row in whitelist:
                written, spoken = row[0], row[1]
                variants = [written.lower()]
                if input_case != "lower_cased":
                    if written != written.lower():
                        variants.append(written)
                    cap = written[0].upper() + written[1:] if written else written
                    if cap not in variants:
                        variants.append(cap)
                for v in variants:
                    arc = pynini.cross(v, spoken)
                    if v in seen:
                        arc = pynutil.add_weight(arc, 0.1)
                    seen.add(v)
                    entries.append(arc)
            return pynini.union(*entries).optimize()

        graph = _get_whitelist_graph(input_case, get_abs_path("data/whitelist.tsv"))

        if input_file:
            graph = _get_whitelist_graph(input_case, input_file)

        # a unit standing alone ("%", "°", "м²", "кг") is read in the nominative singular; single letters stay words
        units = [(row[0], row[2]) for row in load_labels(get_abs_path("data/measure/units.tsv"))]
        units_graph = pynini.string_map(units)
        units_graph = pynini.compose((NEMO_CHAR ** (2, ...) | pynini.difference(NEMO_CHAR, RU_ALPHA)), units_graph)
        graph |= units_graph.optimize()
        graph |= TO_CYRILLIC + pynini.closure(pynutil.insert(" ") + TO_CYRILLIC)

        self.final_graph = convert_space(graph)
        self.fst = (pynutil.insert("name: \"") + self.final_graph + pynutil.insert("\"")).optimize()
