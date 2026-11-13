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

from nemo_text_processing.text_normalization.bn.graph_utils import GraphFst, convert_space, insert_space
from nemo_text_processing.text_normalization.bn.utils import get_abs_path, load_labels


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Roman numerals in Bengali text.
        e.g. অধ্যায় XII   -> tokens { roman { key_cardinal: "অধ্যায়" integer: "XII" } }
        e.g. হেনরি-VIII   -> tokens { roman { key_cardinal: "হেনরি" integer: "VIII" } }
        e.g. XIIতম শ্রেণি -> tokens { roman { integer: "XII" default_ordinal: "বারোতম" key_cardinal: "শ্রেণি" } }
        e.g. IVর্থ শ্রেণি -> tokens { roman { integer: "IV" default_ordinal: "চতুর্থ" key_cardinal: "শ্রেণি" } }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_graph = pynini.string_file(get_abs_path("data/roman/roman_to_spoken.tsv")).optimize()
        roman_numeral_only = pynini.project(roman_graph, "input").optimize()

        bengali_chars = pynini.project(
            pynini.string_file(get_abs_path("data/serial/chars.tsv")), "input"
        ).optimize()

        bengali_word = pynini.closure(bengali_chars, 1).optimize()

        bengali_phrase = (
            bengali_word + pynini.closure((pynini.accep(" ") | pynini.accep("-")) + bengali_word)
        ).optimize()

        separator = (pynini.accep("-") | pynini.accep(" ")).optimize()

        # Roman letters are numbers only next to an enumerating key or regnal name.
        # An arbitrary Bengali word before XL, MIX, or CD is not such a context.
        cardinal_key = pynini.union(
            "অধ্যায়", "পর্ব", "খণ্ড", "ভাগ", "শ্রেণি", "শ্রেণী", "শতাব্দী",
            "অঙ্ক", "দৃশ্য", "ধারা", "অনুচ্ছেদ", "পরিচ্ছেদ", "সর্গ",
            "হেনরি", "লুই", "এডওয়ার্ড", "জর্জ", "চার্লস", "এলিজাবেথ",
            "পোপ", "জন পল",
        )

        key_before_numeral = (
            pynutil.insert("preserve_order: true ")
            + pynutil.insert('key_cardinal: "')
            + convert_space(cardinal_key)
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
            + convert_space(cardinal_key)
            + pynutil.insert('"')
        ).optimize()

        roman_rows = load_labels(get_abs_path("data/roman/roman_to_spoken.tsv"))
        numerals_by_len_desc = sorted((n for n, _ in roman_rows), key=len, reverse=True)

        exception_rows = load_labels(get_abs_path("data/roman/roman_ordinal_exceptions.tsv"))
        exception_fused_set = {fused for fused, _ in exception_rows}

        suffix_rows_raw = load_labels(get_abs_path("data/ordinal/suffixes.tsv"))

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

        regular_row_graphs = []
        for numeral, spoken in roman_rows:
            for row in suffix_rows_raw:

                suffix_input = row[0]
                suffix_output = row[1] if len(row) > 1 else row[0]

                fused = numeral + suffix_input
                if fused in exception_fused_set:
                    continue
                spoken_ordinal = spoken + suffix_output
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
                + convert_space(bengali_phrase)
                + pynutil.insert('"'),
                0,
                1,
            )
        ).optimize()

        graph = pynini.union(key_before_numeral, numeral_before_key, roman_glued_ordinal).optimize()

        self.fst = self.add_tokens(graph).optimize()
