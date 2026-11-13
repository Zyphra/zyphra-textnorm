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

from nemo_text_processing.text_normalization.ar.graph_utils import GraphFst, convert_space
from nemo_text_processing.text_normalization.ar.utils import get_abs_path, load_labels


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying whitelisted abbreviations (data/whitelist.tsv), e.g.
        "د." -> tokens { name: "دكتور" }

    Args:
        input_file: optional path to a whitelist that replaces the default one
    """

    def __init__(self, input_file: str = None):
        super().__init__(name="whitelist", kind="classify")
        whitelist = load_labels(input_file or get_abs_path("data/whitelist.tsv"))
        self.graph = pynini.string_map(whitelist)
        self.fst = (pynutil.insert('name: "') + convert_space(self.graph) + pynutil.insert('"')).optimize()
