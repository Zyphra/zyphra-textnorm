# Copyright (c) 2023, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst, convert_space
from nemo_text_processing.text_normalization.sv.utils import get_abs_path, load_labels


def _int_to_roman(n: int) -> str:
    vals = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out = []
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying keyed Swedish Roman numerals:
        "kapitel IV" -> word { name: "kapitel fyra" }
        "Karl XII" -> word { name: "Karl den tolfte" }
        "Gustav III" -> word { name: "Gustav den tredje" }
        "sekel XXI" -> word { name: "sekel tjugoett" }
    Bare Roman numerals ("XL", "MIX", "CD") and single-letter section labels ("avsnitt C") are NOT matched.
    """

    def __init__(self, cardinal: GraphFst, ordinal: GraphFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_pairs = [(_int_to_roman(n), str(n)) for n in range(1, 2500)]
        roman_to_arabic = pynini.string_map(roman_pairs).optimize()

        # Keyed cardinal words: kapitel IV -> kapitel fyra, sekel XXI -> sekel tjugoett
        # Exclude lone single-letter C, D, L, M so "avsnitt C" / "klass D" stay letters
        card_roman = pynini.difference(
            pynini.project(roman_to_arabic, "input"), pynini.union("C", "D", "L", "M")
        ).optimize()
        card_num = (card_roman @ roman_to_arabic @ cardinal.graph).optimize()

        key_words_base = [
            "kapitel",
            "kap.",
            "del",
            "avsnitt",
            "avdelning",
            "artikel",
            "paragraf",
            "band",
            "volym",
            "bok",
            "akt",
            "scen",
            "sekel",
            "århundrade",
            "bilaga",
            "tabell",
            "figur",
            "klass",
            "typ",
            "fas",
            "steg",
            "nivå",
            "grupp",
        ]
        kw_forms = []
        for kw in key_words_base:
            kw_out = "kapitel" if kw == "kap." else kw
            kw_forms.append((kw, kw_out))
            cap_in = kw[0].upper() + kw[1:]
            cap_out = kw_out[0].upper() + kw_out[1:]
            kw_forms.append((cap_in, cap_out))
            kw_forms.append((kw.upper(), kw_out.upper() if len(kw) <= 3 and kw != "kap." else cap_out))
        key_words = pynini.string_map(kw_forms).optimize()

        graph_cardinal = key_words + pynini.accep(" ") + card_num

        # Keyed regnal / papal ordinals: Karl XII -> Karl den tolfte, Gustav III -> Gustav den tredje
        # Support I..XXXIX (1..39), excluding bare "I" only if lowercase (uppercase I after monarch name is valid: Oscar I -> Oscar den förste/första)
        regnal_pairs = [(_int_to_roman(n), str(n)) for n in range(1, 40)]
        regnal_to_arabic = pynini.string_map(regnal_pairs).optimize()
        regnal_ord = (
            pynutil.insert("den ")
            + (regnal_to_arabic @ ordinal.bare_ordinals)
            + pynini.closure(pynutil.delete("."), 0, 1)
        ).optimize()
        # Genitive regnal: Karl XII:s -> Karl den tolftes
        regnal_ord_gen = (
            pynutil.insert("den ")
            + (regnal_to_arabic @ ordinal.bare_ordinals)
            + pynini.cross(pynini.union(":s", ":S"), "s")
        ).optimize()

        monarch_names_base = [
            # Swedish & Nordic monarchs
            "Karl",
            "Carl",
            "Gustav",
            "Gustaf",
            "Oscar",
            "Oskar",
            "Erik",
            "Eric",
            "Johan",
            "Sigismund",
            "Kristina",
            "Christina",
            "Ulrika",
            "Fredrik",
            "Adolf",
            "Magnus",
            "Birger",
            "Valdemar",
            "Albrekt",
            "Kristian",
            "Christian",
            "Margareta",
            "Margrethe",
            "Harald",
            "Håkon",
            "Haakon",
            "Olav",
            "Olof",
            "Sven",
            "Knut",
            # European monarchs & popes
            "Ludvig",
            "Louis",
            "Henrik",
            "Henry",
            "Edvard",
            "Edward",
            "Georg",
            "George",
            "Charles",
            "Jakob",
            "James",
            "Vilhelm",
            "Wilhelm",
            "William",
            "Filip",
            "Philip",
            "Felipe",
            "Ferdinand",
            "Alfons",
            "Alfonso",
            "Peter",
            "Pjotr",
            "Nikolaj",
            "Alexander",
            "Katarina",
            "Elisabet",
            "Elizabeth",
            "Victoria",
            "Viktoria",
            "Maria",
            "otto",
            "Otto",
            "Konrad",
            "Fredrik",
            " Frans",
            "Franciskus",
            "Johannes",
            "Paulus",
            "Benedikt",
            "Benedictus",
            "Pius",
            "Leo",
            "Gregorius",
            "Clemens",
            "Innocentius",
            "Urban",
            "Sixtus",
            "Bonifatius",
            "Ramses",
            "Ptolemaios",
            "Napoleon",
        ]
        # Clean list & build titlecase + UPPERCASE forms (only capitalized names trigger regnal Roman numerals!)
        clean_names = sorted({n.strip() for n in monarch_names_base if n.strip() and n.strip()[0].isupper()})
        name_forms = [(n, n) for n in clean_names] + [(n.upper(), n.upper()) for n in clean_names]
        monarch_names = pynini.string_map(name_forms).optimize()

        graph_regnal = monarch_names + pynini.accep(" ") + (regnal_ord | regnal_ord_gen)

        full_graph = convert_space(graph_cardinal | graph_regnal).optimize()
        self.fst = (pynutil.insert('name: "') + full_graph + pynutil.insert('"')).optimize()
