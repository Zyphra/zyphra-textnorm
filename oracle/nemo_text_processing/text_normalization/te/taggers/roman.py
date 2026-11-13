# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.te.graph_utils import (
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path, load_labels


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Roman numerals next to a Telugu keyword, e.g.
        అధ్యాయం IV    -> tokens { roman { preserve_order: true key_cardinal: "అధ్యాయం" integer: "IV" } }
        చంద్రయాన్-III -> tokens { roman { preserve_order: true key_cardinal: "చంద్రయాన్" integer: "III" } }
        XIIవ తరగతి    -> tokens { roman { preserve_order: true integer: "XII" default_ordinal: "పన్నెండవ" key_cardinal: "తరగతి" } }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_graph = pynini.string_file(get_abs_path("data/roman/roman_to_spoken.tsv")).optimize()
        roman_numeral_only = pynini.project(roman_graph, "input").optimize()

        # A Telugu word alone is not evidence of a Roman numeral: size labels
        # such as "పరిమాణం XL" must retain their letters.
        cardinal_keys = pynini.union(
            "అధ్యాయం",
            "భాగం",
            "చంద్రయాన్",
            "ప్రపంచ యుద్ధం",
            "యుద్ధం",
            "తరగతి",
            "ఖండం",
            "అంకం",
            "సర్గ",
            "సర్గం",
            "విభాగం",
            "సంపుటి",
            "శతాబ్దం",
            "శతాబ్దము",
            "దశ",
            "పాఠం",
            "కాండం",
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

        # Roman numeral glued to the CLDR ordinal suffix వ, e.g. "XIIవ" -> పన్నెండవ
        glued_ordinal = pynini.union(
            *[
                pynutil.insert(f'preserve_order: true integer: "{numeral}" default_ordinal: "{spoken}"')
                + pynutil.delete(numeral + "వ")
                for numeral, spoken in load_labels(get_abs_path("data/roman/roman_to_ordinal.tsv"))
            ]
        ).optimize()
        glued_ordinal = glued_ordinal + pynini.closure(pynutil.delete(" ") + insert_space + key_cardinal, 0, 1)

        graph = pynini.union(key_before_numeral, numeral_before_key, glued_ordinal).optimize()

        self.fst = self.add_tokens(graph).optimize()
