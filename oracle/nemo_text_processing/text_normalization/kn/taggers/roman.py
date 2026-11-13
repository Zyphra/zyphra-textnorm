# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path, load_labels


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Roman numerals next to a Kannada keyword, e.g.
        ಅಧ್ಯಾಯ IV    -> tokens { roman { preserve_order: true key_cardinal: "ಅಧ್ಯಾಯ" integer: "IV" } }
        ಚಂದ್ರಯಾನ-III -> tokens { roman { preserve_order: true key_cardinal: "ಚಂದ್ರಯಾನ" integer: "III" } }
        XIIನೇ ತರಗತಿ  -> tokens { roman { preserve_order: true integer: "XII" default_ordinal: "ಹನ್ನೆರಡನೇ" key_cardinal: "ತರಗತಿ" } }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_graph = pynini.string_file(get_abs_path("data/roman/roman_to_spoken.tsv")).optimize()
        roman_numeral_only = pynini.project(roman_graph, "input").optimize()

        cardinal_keys = pynini.union(
            "ಅಧ್ಯಾಯ",
            "ಅಧ್ಯಾಯಂ",
            "ಭಾಗ",
            "ಭಾಗಂ",
            "ಸಂಪುಟ",
            "ಖಂಡ",
            "ತರಗತಿ",
            "ದರ್ಜೆ",
            "ವಿಶ್ವಯುದ್ಧ",
            "ಮಹಾಯುದ್ಧ",
            "ಚಂದ್ರಯಾನ",
            "ಆವೃತ್ತಿ",
            "ಶ್ರೇಣಿ",
            "ಶತಮಾನ",
            "ಹಂತ",
            "ಪರ್ವ",
            "ಸರಣಿ",
            "ಅಂಕ",
            "ರೂಪ",
            "ಮೆಟ್ಟಿಲು",
        ).optimize()

        separator = (pynini.accep("-") | pynini.accep(" ")).optimize()
        key_cardinal = pynutil.insert('key_cardinal: "') + convert_space(cardinal_keys) + pynutil.insert('"')
        integer = pynutil.insert('integer: "') + roman_numeral_only + pynutil.insert('"')

        key_before_numeral = (
            pynutil.insert("preserve_order: true ")
            + key_cardinal
            + pynutil.delete(separator)
            + insert_space
            + integer
        ).optimize()

        numeral_before_key = (
            pynutil.insert("preserve_order: true ")
            + integer
            + pynutil.delete(separator)
            + insert_space
            + key_cardinal
        ).optimize()

        # Roman numeral glued to ordinal suffix ನೇ
        glued_graphs = []
        for r_sym, r_ord in load_labels(get_abs_path("data/roman/roman_to_ordinal.tsv")):
            glued_graphs.append(
                pynutil.delete(r_sym)
                + pynutil.delete(pynini.union("ನೇ", "ನೆ"))
                + pynutil.insert(f'integer: "{r_sym}" default_ordinal: "{r_ord}"')
            )
        glued_ordinal = (
            pynutil.insert("preserve_order: true ")
            + pynini.union(*glued_graphs)
            + pynini.closure(pynutil.delete(" ") + insert_space + key_cardinal, 0, 1)
        ).optimize()
        graph = pynini.union(key_before_numeral, numeral_before_key, glued_ordinal).optimize()

        self.fst = self.add_tokens(graph).optimize()
