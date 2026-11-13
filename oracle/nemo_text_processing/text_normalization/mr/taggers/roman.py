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

from nemo_text_processing.text_normalization.mr.graph_utils import GraphFst, convert_space, insert_space
from nemo_text_processing.text_normalization.mr.utils import get_abs_path, load_labels


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Roman numerals in Marathi text.
        e.g. भाग-II       -> tokens { roman { key_cardinal: "भाग" integer: "II" } }
        e.g. इयत्ता XII   -> tokens { roman { key_cardinal: "इयत्ता" integer: "XII" } }
        e.g. XIIवी इयत्ता -> tokens { roman { integer: "XII" default_ordinal: "बारावी" key_cardinal: "इयत्ता" } }
        e.g. IVथी इयत्ता  -> tokens { roman { integer: "IV" default_ordinal: "चौथी" key_cardinal: "इयत्ता" } }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_graph = pynini.string_file(get_abs_path("data/roman/roman_to_spoken.tsv")).optimize()
        roman_numeral_only = pynini.project(roman_graph, "input").optimize()

        devanagari_chars = pynini.project(
            pynini.string_file(get_abs_path("data/serial/chars.tsv")), "input"
        ).optimize()

        devanagari_word = pynini.closure(devanagari_chars, 1).optimize()

        devanagari_phrase = (
            devanagari_word + pynini.closure((pynini.accep(" ") | pynini.accep("-")) + devanagari_word)
        ).optimize()

        separator = (pynini.accep("-") | pynini.accep(" ")).optimize()

        key_before_numeral = (
            pynutil.insert("preserve_order: true ")
            + pynutil.insert('key_cardinal: "')
            + convert_space(devanagari_phrase)
            + pynutil.insert('"')
            + pynutil.delete(separator)
            + insert_space
            + pynutil.insert('integer: "')
            + roman_numeral_only
            + pynutil.insert('"')
        ).optimize()

        numeral_before_key = (
            pynutil.insert("preserve_order: true ")
            + pynutil.insert('integer: "')
            + roman_numeral_only
            + pynutil.insert('"')
            + pynutil.delete(separator)
            + insert_space
            + pynutil.insert('key_cardinal: "')
            + convert_space(devanagari_phrase)
            + pynutil.insert('"')
        ).optimize()

        roman_rows = load_labels(get_abs_path("data/roman/roman_to_spoken.tsv"))
        numerals_by_len_desc = sorted((n for n, _ in roman_rows), key=len, reverse=True)

        exception_rows = load_labels(get_abs_path("data/roman/roman_ordinal_exceptions.tsv"))
        exception_fused_set = {fused for fused, _ in exception_rows}

        suffixes = [row[0] for row in load_labels(get_abs_path("data/ordinal/suffixes.tsv"))]
        va_numbers = {int(row[0]) for row in load_labels(get_abs_path("data/ordinal/va_numbers.tsv"))}

        exception_graphs = []
        for fused, spoken_word in exception_rows:
            matched_numeral = next(c for c in numerals_by_len_desc if fused.startswith(c))
            exception_graphs.append(
                pynutil.insert('integer: "' + matched_numeral + '"')
                + insert_space
                + pynutil.insert('default_ordinal: "' + spoken_word + '"')
                + pynutil.delete(fused)
            )
        glued_ordinal_exceptions_graph = pynini.union(*exception_graphs).optimize()

        # CLDR mr %spellout-ordinal: cardinal + वा for 11-18, 50 and 79-88, cardinal + ावा otherwise
        regular_row_graphs = []
        for value, (numeral, spoken) in enumerate(roman_rows, start=1):
            for suffix in suffixes:
                fused = numeral + suffix
                if fused in exception_fused_set or value <= 10:
                    continue
                spoken_ordinal = spoken + (suffix if value in va_numbers else "ा" + suffix)
                regular_row_graphs.append(
                    pynutil.insert('integer: "' + numeral + '"')
                    + insert_space
                    + pynutil.insert('default_ordinal: "' + spoken_ordinal + '"')
                    + pynutil.delete(fused)
                )
        glued_ordinal_regular_graph = pynini.union(*regular_row_graphs).optimize()

        roman_glued_ordinal_fields = pynini.union(
            pynutil.add_weight(glued_ordinal_exceptions_graph, -0.1),
            glued_ordinal_regular_graph,
        ).optimize()

        roman_glued_ordinal = (
            pynutil.insert("preserve_order: true ")
            + roman_glued_ordinal_fields
            + pynini.closure(
                pynutil.delete(" ")
                + insert_space
                + pynutil.insert('key_cardinal: "')
                + convert_space(devanagari_phrase)
                + pynutil.insert('"'),
                0,
                1,
            )
        ).optimize()

        graph = pynini.union(key_before_numeral, numeral_before_key, roman_glued_ordinal).optimize()

        self.fst = self.add_tokens(graph).optimize()
