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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Roman numerals next to Malayalam keywords, e.g.
        അധ്യായം IV -> tokens { roman { key_cardinal: "അധ്യായം" integer: "IV" } }
        ഭാഗം III -> tokens { roman { key_cardinal: "ഭാഗം" integer: "III" } }
        ചന്ദ്രയാൻ-III -> tokens { roman { key_cardinal: "ചന്ദ്രയാൻ" integer: "III" } }
        IV-ാം അധ്യായം -> tokens { roman { integer: "IV" default_ordinal: "നാലാം" key_cardinal: "അധ്യായം" } }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_graph = pynini.string_file(get_abs_path("data/roman/roman_to_spoken.tsv")).optimize()
        roman_numeral_only = pynini.project(roman_graph, "input").optimize()

        cardinal_keys = pynini.union(
            "അധ്യായം",
            "ഭാഗം",
            "ചന്ദ്രയാൻ",
            "മഹായുദ്ധം",
            "ലോക മഹായുദ്ധം",
            "ക്ലാസ്",
            "നൂറ്റാണ്ട്",
            "ഖണ്ഡം",
            "രംഗം",
            "വാല്യം",
            "പതിപ്പ്",
            "ഘട്ടം",
            "തലമുറ",
            "സ്റ്റേജ്",
            "ഗ്രൂപ്പ്",
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

        # Roman numerals with ordinal suffixes: IV-ാം -> നാലാം, XII-ാം -> പന്ത്രണ്ടാം
        ord_suffix = pynini.union("-ാം", "ാം")
        ord_mathe_suffix = pynini.union("-ാമത്തെ", "ാമത്തെ")

        roman_ord_map = pynini.string_map([
            ("I", "ഒന്നാം"),
            ("II", "രണ്ടാം"),
            ("III", "മൂന്നാം"),
            ("IV", "നാലാം"),
            ("V", "അഞ്ചാം"),
            ("VI", "ആറാം"),
            ("VII", "ഏഴാം"),
            ("VIII", "എട്ടാം"),
            ("IX", "ഒൻപതാം"),
            ("X", "പത്താം"),
            ("XI", "പതിനൊന്നാം"),
            ("XII", "പന്ത്രണ്ടാം"),
            ("XX", "ഇരുപതാം"),
            ("XXI", "ഇരുപത്തിയൊന്നാം"),
        ])
        roman_ord_mathe_map = pynini.string_map([
            ("I", "ഒന്നാമത്തെ"),
            ("II", "രണ്ടാമത്തെ"),
            ("III", "മൂന്നാമത്തെ"),
            ("IV", "നാലാമത്തെ"),
            ("V", "അഞ്ചാമത്തെ"),
            ("VI", "ആറാമത്തെ"),
            ("VII", "ഏഴാമത്തെ"),
            ("VIII", "എട്ടാമത്തെ"),
            ("IX", "ഒൻപതാമത്തെ"),
            ("X", "പത്താാമത്തെ"),
            ("XI", "പതിനൊന്നാമത്തെ"),
            ("XII", "പന്ത്രണ്ടാമത്തെ"),
        ])

        ord_body = (
            (roman_ord_map + pynutil.delete(ord_suffix))
            | (roman_ord_mathe_map + pynutil.delete(ord_mathe_suffix))
        )
        glued_ordinal = (
            pynutil.insert("preserve_order: true default_ordinal: \"")
            + ord_body
            + pynutil.insert('"')
        ).optimize()
        glued_ordinal = glued_ordinal + pynini.closure(pynutil.delete(" ") + insert_space + key_cardinal, 0, 1)

        graph = pynini.union(key_before_numeral, numeral_before_key, glued_ordinal).optimize()
        self.fst = self.add_tokens(graph).optimize()
