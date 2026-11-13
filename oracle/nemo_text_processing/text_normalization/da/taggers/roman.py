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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
    convert_space,
)


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Danish contextual Roman numerals.
    Handles:
      - Regal/Papal names: "Frederik IX" -> "Frederik den niende", "Margrethe II" -> "Margrethe den anden"
      - Document citations: "Kapitel IV" -> "kapitel fire", "del II" -> "del to"
      - Dot Roman ordinals: "I." -> "første", "IV." -> "fjerde"
      - Avoids accidental matching of abbreviations (XL, CD, MIX, etc.)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Roman numeral to cardinal mapping
        roman_cardinal = [
            ("I", "et"),
            ("II", "to"),
            ("III", "tre"),
            ("IV", "fire"),
            ("V", "fem"),
            ("VI", "seks"),
            ("VII", "syv"),
            ("VIII", "otte"),
            ("IX", "ni"),
            ("X", "ti"),
            ("XI", "elleve"),
            ("XII", "tolv"),
            ("XIII", "tretten"),
            ("XIV", "fjorten"),
            ("XV", "femten"),
            ("XVI", "seksten"),
            ("XVII", "sytten"),
            ("XVIII", "atten"),
            ("XIX", "nitten"),
            ("XX", "tyve"),
            ("XXI", "enogtyve"),
            ("XXII", "toogtyve"),
            ("XXV", "femogtyve"),
            ("XXX", "tredive"),
            ("L", "halvtreds"),
            ("C", "hundrede"),
            ("M", "tusind"),
        ]

        # Roman numeral to ordinal mapping
        roman_ordinal = [
            ("I", "første"),
            ("II", "anden"),
            ("III", "tredje"),
            ("IV", "fjerde"),
            ("V", "femte"),
            ("VI", "sjette"),
            ("VII", "syvende"),
            ("VIII", "ottende"),
            ("IX", "niende"),
            ("X", "tiende"),
            ("XI", "ellevte"),
            ("XII", "tolvte"),
            ("XIII", "trettende"),
            ("XIV", "fjortende"),
            ("XV", "femtende"),
            ("XVI", "sekstende"),
            ("XVII", "syttende"),
            ("XVIII", "attende"),
            ("XIX", "nittende"),
            ("XX", "tyvende"),
            ("XXI", "enogtyvende"),
            ("XXII", "toogtyvende"),
            ("XXV", "femogtyvende"),
            ("XXX", "tredivte"),
        ]

        # Monarch and pope names
        monarch_names = [
            "Frederik",
            "Christian",
            "Margrethe",
            "Valdemar",
            "Knud",
            "Erik",
            "Svend",
            "Harald",
            "Henrik",
            "Karl",
            "Poul",
            "Johannes",
            "Johannes Paul",
            "Benedikt",
            "Frans",
            "Vilhelm",
            "Ludvig",
            "Filip",
            "Georg",
            "Alexander",
            "Elisabeth",
            "Elizabeth",
            "Louis",
        ]

        monarch_fst = pynini.union(*monarch_names)
        regal_ord_fst = pynini.string_map(roman_ordinal)

        regal_roman = (
            monarch_fst
            + pynutil.delete(" ")
            + pynutil.insert(" den ")
            + regal_ord_fst
        )

        # Keyword contexts (Kapitel, del, etc.)
        keywords = [
            ("Kapitel", "kapitel"),
            ("kapitel", "kapitel"),
            ("Kap.", "kapitel"),
            ("kap.", "kapitel"),
            ("Del", "del"),
            ("del", "del"),
            ("Klasse", "klasse"),
            ("klasse", "klasse"),
            ("Afsnit", "afsnit"),
            ("afsnit", "afsnit"),
            ("Bind", "bind"),
            ("bind", "bind"),
            ("Akt", "akt"),
            ("akt", "akt"),
            ("Scene", "scene"),
            ("scene", "scene"),
            ("Tabel", "tabel"),
            ("tabel", "tabel"),
            ("Figur", "figur"),
            ("figur", "figur"),
            ("Volumen", "volumen"),
            ("volumen", "volumen"),
            ("Vol.", "bind"),
            ("vol.", "bind"),
        ]

        kw_fst = pynini.string_map(keywords)
        card_fst = pynini.string_map(roman_cardinal)

        kw_roman = (
            kw_fst
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + card_fst
        )

        # Dot ordinals: "I.", "II.", "IV."
        dot = pynutil.delete(".")
        dot_roman = regal_ord_fst + dot

        # Century: "century XXI", "Century XXI", "århundrede XXI", "årh. XXI"
        # and "det XX. århundrede", "XX. århundrede", "det II. århundrede" -> "det andet århundrede"
        century_prefix = (
            pynini.cross("century ", "århundrede ")
            | pynini.cross("century", "århundrede ")
            | pynini.cross("Century ", "århundrede ")
            | pynini.cross("Century", "århundrede ")
            | pynini.cross("århundrede ", "århundrede ")
            | pynini.cross("Århundrede ", "århundrede ")
            | pynini.cross("årh. ", "århundrede ")
            | pynini.cross("årh.", "århundrede ")
            | pynini.cross("årh ", "århundrede ")
        )
        century_pre = century_prefix + (regal_ord_fst | card_fst)

        # II before århundrede is neuter "andet" (et århundrede, århundredet)
        roman_ord_neuter = [
            (r, "andet" if r == "II" else w) for r, w in roman_ordinal
        ]
        regal_ord_neuter_fst = pynini.string_map(roman_ord_neuter)
        century_post = (
            pynini.closure(pynini.cross("det ", "det ") | pynini.cross("Det ", "det "), 0, 1)
            + regal_ord_neuter_fst
            + pynini.closure(dot, 0, 1)
            + pynini.cross(" århundrede", " århundrede")
        )
        century = century_pre | century_post
        all_roman = (regal_roman | kw_roman | dot_roman | century).optimize()

        self.graph = all_roman

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
