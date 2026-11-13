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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Roman numerals next to a Tamil keyword, e.g.
        அத்தியாயம் IV    -> tokens { roman { preserve_order: true key_cardinal: "அத்தியாயம்" integer: "IV" } }
        சந்திரயான்-III   -> tokens { roman { preserve_order: true key_cardinal: "சந்திரயான்" integer: "III" } }
        XXI நூற்றாண்டு   -> tokens { roman { preserve_order: true integer: "XXI" key_cardinal: "நூற்றாண்டு" } }
        XIIவது வகுப்பு   -> tokens { roman { preserve_order: true integer: "XII" default_ordinal: "பன்னிரண்டாவது" key_cardinal: "வகுப்பு" } }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_graph = pynini.string_file(get_abs_path("data/roman/roman_to_spoken.tsv")).optimize()
        roman_numeral_only = pynini.project(roman_graph, "input").optimize()

        cardinal_keys = pynini.union(
            "அத்தியாயம்",
            "பாகம்",
            "பிரிவு",
            "நூற்றாண்டு",
            "ஆம் நூற்றாண்டு",
            "உலகப்போர்",
            "ஆம் உலகப்போர்",
            "வகுப்பு",
            "படிவம்",
            "போப்",
            "ராஜா",
            "அரசர்",
            "சந்திரயான்",
            "அப்பல்லோ",
            "சார்லஸ்",
            "ஜார்ஜ்",
            "எலிசபெத்",
            "ஹென்றி",
            "லூயிஸ்",
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

        # Roman numeral glued to ordinal suffix வது, e.g. "XIIவது" -> பன்னிரண்டாவது
        glued_ordinal = pynini.union(
            pynutil.insert('preserve_order: true integer: "')
            + roman_numeral_only
            + pynutil.insert('" default_ordinal: "')
            + (roman_graph + pynutil.delete(pynini.union("வது", "ஆவது", "-வது", "-ஆவது")))
            + pynutil.insert('ாவது"')
        ).optimize()
        glued_ordinal = glued_ordinal + pynini.closure(pynutil.delete(" ") + insert_space + key_cardinal, 0, 1)

        graph = pynini.union(key_before_numeral, numeral_before_key, glued_ordinal).optimize()

        self.fst = self.add_tokens(graph).optimize()
