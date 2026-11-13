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
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    GraphFst,
)


class WordFst(GraphFst):
    """
    Finite state transducer for classifying ordinary Romanian words, e.g.
        "cuvânt" -> tokens { name: "cuvânt" }
        "oraş" -> tokens { name: "oraș" }  # normalizes cedilla to comma-below
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)

        # Cedilla to comma-below rewrite
        cedilla_rewrite = (
            pynini.cdrewrite(pynini.cross("ş", "ș"), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("Ş", "Ș"), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("ţ", "ț"), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("Ţ", "Ț"), "", "", NEMO_SIGMA)
        ).optimize()

        word_raw = pynini.closure(NEMO_NOT_SPACE, 1)
        word_clean = word_raw @ cedilla_rewrite

        self.fst = (
            pynutil.insert('name: "')
            + word_clean.optimize()
            + pynutil.insert('"')
        ).optimize()
