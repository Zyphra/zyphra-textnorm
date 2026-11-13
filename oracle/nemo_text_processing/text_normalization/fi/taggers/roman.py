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
    GraphFst,
    convert_space,
)


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Finnish contextual Roman numerals, e.g.
        "Kaarle XII" -> tokens { name: "Kaarle kahdestoista" }
        "Kustaa III" -> tokens { name: "Kustaa kolmas" }
        "Luku IV" -> tokens { name: "Luku neljä" }
        "XXI vuosisata" -> tokens { name: "kaksikymmentäensimmäinen vuosisata" }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        # Roman ordinals for monarchs:
        monarch_ord = pynini.string_map([
            ("I", "ensimmäinen"),
            ("II", "toinen"),
            ("III", "kolmas"),
            ("IV", "neljäs"),
            ("V", "viides"),
            ("VI", "kuudes"),
            ("VII", "seitsemäs"),
            ("VIII", "kahdeksas"),
            ("IX", "yhdeksäs"),
            ("X", "kymmenes"),
            ("XI", "yhdestoista"),
            ("XII", "kahdestoista"),
            ("XIII", "kolmestoista"),
            ("XIV", "neljästoista"),
            ("XV", "viidestoista"),
            ("XVI", "kuudestoista"),
        ])

        # Monarch names
        monarch_names = pynini.string_map([
            ("Kaarle", "Kaarle"),
            ("Kustaa", "Kustaa"),
            ("Aleksanteri", "Aleksanteri"),
            ("Henrik", "Henrik"),
            ("Louis", "Louis"),
            ("Elisabet", "Elisabet"),
            ("Elizabeth", "Elizabeth"),
            ("Pekka", "Pekka"),
            ("Juhana", "Juhana"),
            ("Fredrik", "Fredrik"),
            ("Kristian", "Kristian"),
            ("Vilhelm", "Vilhelm"),
            ("Yrjö", "Yrjö"),
            ("Eerik", "Eerik"),
            ("Karl", "Karl"),
            ("Gustav", "Gustav"),
        ])
        monarch_full = monarch_names + pynini.accep(" ") + monarch_ord

        # Specific genitive monarch: "Kaarle XII:n" -> "Kaarle kahdennentoista"
        monarch_genitive = pynini.string_map([
            ("Kaarle XII:n", "Kaarle kahdennentoista"),
            ("Kustaa III:n", "Kustaa kolmannen"),
            ("Aleksanteri II:n", "Aleksanteri toisen"),
        ])

        # Chapters / parts: "Luku IV", "Osa II", "Kappale IV"
        chapter_keywords = pynini.string_map([
            ("Luku", "Luku"),
            ("luku", "luku"),
            ("Osa", "Osa"),
            ("osa", "osa"),
            ("Kappale", "Kappale"),
            ("kappale", "kappale"),
            ("Chapter", "Chapter"),
            ("chapter", "chapter"),
            ("Part", "Part"),
            ("part", "part"),
        ])
        chapter_nums = pynini.string_map([
            ("I", "yksi"),
            ("II", "kaksi"),
            ("III", "kolme"),
            ("IV", "neljä"),
            ("V", "viisi"),
            ("VI", "kuusi"),
            ("VII", "seitsemän"),
            ("VIII", "kahdeksan"),
            ("IX", "yhdeksän"),
            ("X", "kymmenen"),
            ("XI", "yksitoista"),
            ("XII", "kaksitoista"),
        ])
        chapter_full = chapter_keywords + pynini.accep(" ") + chapter_nums

        # Centuries: "XXI vuosisata", "XXI. vuosisata", "XXI vuosisadalla"
        century_ord_nom = pynini.string_map([
            ("X", "kymmenes"),
            ("XI", "yhdestoista"),
            ("XII", "kahdestoista"),
            ("XIII", "kolmestoista"),
            ("XIV", "neljästoista"),
            ("XV", "viidestoista"),
            ("XVI", "kuudestoista"),
            ("XVII", "seitsemästoista"),
            ("XVIII", "kahdeksastoista"),
            ("XIX", "yhdeksästoista"),
            ("XX", "kahdeskymmenes"),
            ("XXI", "kaksikymmentäensimmäinen"),
        ])
        century_ord_ades = pynini.string_map([
            ("X", "kymmenennellä"),
            ("XI", "yhdennellätoista"),
            ("XII", "kahdennellatoista"),
            ("XIII", "kolmannellatoista"),
            ("XIV", "neljännellätoista"),
            ("XV", "viidennellätoista"),
            ("XVI", "kuudennellätoista"),
            ("XVII", "seitsemännellätoista"),
            ("XVIII", "kahdeksannellatoista"),
            ("XIX", "yhdeksännellätoista"),
            ("XX", "kahdennellakymmenennellä"),
            ("XXI", "kaksikymmentäensimmäisellä"),
        ])
        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)
        century_nom = century_ord_nom + opt_dot + pynini.accep(" ") + pynini.string_map([
            ("vuosisata", "vuosisata"),
            ("vuosisadan", "vuosisadan"),
            ("vuosisadalle", "vuosisadalle"),
        ])
        century_ades = century_ord_ades + opt_dot + pynini.accep(" ") + pynini.accep("vuosisadalla")
        century_full = century_nom | century_ades

        all_roman = (
            monarch_genitive
            | monarch_full
            | chapter_full
            | century_full
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_roman).optimize()
            + pynutil.insert('"')
        ).optimize()
