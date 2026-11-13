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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst, convert_space, insert_space
from nemo_text_processing.text_normalization.id.utils import get_abs_path, load_labels


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying whitelisted abbreviations and symbols, e.g.
        "dll" -> tokens { name: "dan lain-lain" }
        "&" -> tokens { name: "dan" }
        "§ 12" -> tokens { name: "pasal dua belas" }
        "© 2024" -> tokens { name: "hak cipta dua ribu dua puluh empat" }
    Loaded from "data/whitelist.tsv".

    Args:
        input_case: accepting either "lower_cased" or "cased" input.
        deterministic: if True will provide a single transduction option,
            for False multiple options (used for audio-based normalization)
        input_file: path to a file with whitelist replacements
        cardinal: optional CardinalFst for keyed symbol+number expansions
    """

    def __init__(
        self,
        input_case: str,
        deterministic: bool = True,
        input_file: str = None,
        cardinal: GraphFst = None,
    ):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        def _get_whitelist_graph(file):
            whitelist = load_labels(file)
            if input_case == "lower_cased":
                whitelist = [[x[0].lower()] + x[1:] for x in whitelist]
            return pynini.string_map(whitelist)

        graph = _get_whitelist_graph(input_file or get_abs_path("data/whitelist.tsv"))

        if cardinal is not None:
            opt_sp = pynini.closure(pynutil.delete(pynini.union(" ", "\u00a0", "\u202f")), 0, 1)
            num = cardinal.graph_with_sep
            no_prefix = pynini.union(
                pynini.cross("No.", "nomor"),
                pynini.cross("no.", "nomor"),
                pynini.cross("N°", "nomor"),
                pynini.cross("n°", "nomor"),
                pynini.cross("Nº", "nomor"),
                pynini.cross("nº", "nomor"),
            )
            keyed_no = no_prefix + opt_sp + insert_space + num
            keyed_sec = pynini.cross("§", "pasal") + opt_sp + insert_space + num
            keyed_copy = pynini.cross("©", "hak cipta") + opt_sp + insert_space + num
            graph |= keyed_no | keyed_sec | keyed_copy

        self.graph = graph
        self.fst = (pynutil.insert('name: "') + convert_space(graph) + pynutil.insert('"')).optimize()
