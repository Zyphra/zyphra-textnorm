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

import os
import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.pl.utils import get_abs_path


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Polish whitelist / abbreviations / symbols, e.g.
        "dr" -> "doktor"
        "np." -> "na przykład"
        "&" -> "i"
        "©" -> "copyright"
        "§" -> "paragraf"
    """

    def __init__(
        self,
        input_case: str = "cased",
        deterministic: bool = True,
        input_file: str = None,
        cardinal: GraphFst = None,
    ):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        # Standard abbreviations from data/whitelist/abbreviations.tsv
        abbrevs = pynini.string_file(get_abs_path("data/whitelist/abbreviations.tsv"))

        # Core symbols
        symbols = pynini.string_map(
            [
                ("&", "i"),
                ("©", "copyright"),
                ("§", "paragraf"),
                ("+", "plus"),
                ("=", "równa się"),
                ("×", "razy"),
                ("÷", "podzielić przez"),
            ]
        )

        graph = abbrevs | symbols

        if input_file and os.path.exists(input_file):
            user_graph = pynini.string_file(input_file)
            graph |= user_graph

        self.graph = graph
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
