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
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.tr.taggers.ordinal import OrdinalFst


class RomanFst(GraphFst):
    """
    Finite state transducer for contextual Roman numerals:
    - Centuries: XX. yüzyıl -> yirminci yüzyıl, XXI. yüzyıl -> yirmi birinci yüzyıl
    - Monarchs: II. Mehmed -> ikinci mehmed, IV. Murat -> dördüncü murat, Louis XIV -> louis on dördüncü
    - Wars: I. Dünya Savaşı -> birinci dünya savaşı, II. Dünya Savaşı -> ikinci dünya savaşı
    - Chapters: Bölüm IV -> bölüm dört, Chapter IV -> bölüm dört, Cilt II -> cilt iki
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        ordinal: OrdinalFst = None,
        deterministic: bool = True,
    ):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if ordinal is None:
            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)

        roman_ord = pynini.string_map([
            ("I", "birinci"),
            ("II", "ikinci"),
            ("III", "üçüncü"),
            ("IV", "dördüncü"),
            ("V", "beşinci"),
            ("VI", "altıncı"),
            ("VII", "yedinci"),
            ("VIII", "sekizinci"),
            ("IX", "dokuzuncu"),
            ("X", "onuncu"),
            ("XI", "on birinci"),
            ("XII", "on ikinci"),
            ("XIII", "on üçüncü"),
            ("XIV", "on dördüncü"),
            ("XV", "on beşinci"),
            ("XVI", "on altıncı"),
            ("XVII", "on yedinci"),
            ("XVIII", "on sekizinci"),
            ("XIX", "on dokuzuncu"),
            ("XX", "yirminci"),
            ("XXI", "yirmi birinci"),
        ])

        roman_card = pynini.string_map([
            ("I", "bir"),
            ("II", "iki"),
            ("III", "üç"),
            ("IV", "dört"),
            ("V", "beş"),
            ("VI", "altı"),
            ("VII", "yedi"),
            ("VIII", "sekiz"),
            ("IX", "dokuz"),
            ("X", "on"),
            ("XI", "on bir"),
            ("XII", "on iki"),
            ("XIII", "on üç"),
            ("XIV", "on dört"),
            ("XV", "on beş"),
            ("XVI", "on altı"),
            ("XVII", "on yedi"),
            ("XVIII", "on sekiz"),
            ("XIX", "on dokuz"),
            ("XX", "yirmi"),
            ("XXI", "yirmi bir"),
        ])

        # Centuries: "XX. yüzyıl", "XXI. yüzyıl", "XIX. yy.", "19. yüzyıl"
        century_word = (
            pynini.cross("yüzyıl", "yüzyıl")
            | pynini.cross("yüzyılda", "yüzyılda")
            | pynini.cross("yy.", "yüzyıl")
            | pynini.cross("yy", "yüzyıl")
        )
        dot_opt = pynini.closure(pynutil.delete("."), 0, 1)
        century_roman = (
            roman_ord + dot_opt + pynutil.delete(" ") + pynutil.insert(" ") + century_word
        )
        century_digits = (
            ordinal.cardinal_to_ordinal
            + dot_opt
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + century_word
        )
        century_graph = century_roman | century_digits

        # Monarchs: "II. Mehmed", "IV. Murat", "XVI. Louis", "II. Elizabeth"
        monarch_names_before = pynini.string_map([
            ("Mehmed", "mehmed"),
            ("Mehmet", "mehmet"),
            ("Murat", "murat"),
            ("Louis", "louis"),
            ("Elizabeth", "elizabeth"),
            ("Süleyman", "süleyman"),
            ("Selim", "selim"),
            ("Ahmet", "ahmet"),
            ("Osman", "osman"),
            ("Mahmut", "mahmut"),
            ("İskender", "iskender"),
            ("Nikolay", "nikolay"),
            ("Wilhelm", "wilhelm"),
            ("Edward", "edward"),
            ("George", "george"),
            ("Henry", "henry"),
            ("Charles", "charles"),
            ("Philip", "philip"),
            ("Paul", "paul"),
            ("Pius", "pius"),
            ("Jean", "jean"),
            ("Kral", "kral"),
            ("Çar", "çar"),
            ("Papa", "papa"),
            ("Sultan", "sultan"),
        ])
        monarch_num_first = (
            roman_ord + dot_opt + pynutil.delete(" ") + pynutil.insert(" ") + monarch_names_before
        )
        # Name first: "Louis XIV" -> "on dördüncü louis", "Mustafa IV" -> "dördüncü mustafa", "Elizabeth II" -> "ikinci elizabeth"
        monarch_name_first = (
            pynutil.insert("")
            + roman_ord
            + pynutil.insert(" ")
            + pynini.invert(
                pynini.string_map([
                    ("louis", "Louis"),
                    ("elizabeth", "Elizabeth"),
                    ("mustafa", "Mustafa"),
                    ("mehmet", "Mehmet"),
                    ("murat", "Murat"),
                    ("henry", "Henry"),
                    ("george", "George"),
                    ("edward", "Edward"),
                    ("charles", "Charles"),
                ])
            )
        )
        # Or keeping name first: "Louis XIV" -> "louis on dördüncü"
        monarch_name_first_straight = (
            pynini.string_map([
                ("Louis", "louis"),
                ("Elizabeth", "elizabeth"),
                ("Mustafa", "mustafa"),
                ("Mehmet", "mehmet"),
                ("Murat", "murat"),
                ("Henry", "henry"),
                ("George", "george"),
                ("Edward", "edward"),
                ("Charles", "charles"),
            ])
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + (roman_ord | roman_card)
        )

        # Wars: "I. Dünya Savaşı", "II. Dünya Savaşı"
        war_graph = (
            roman_ord
            + dot_opt
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + pynini.cross("Dünya Savaşı", "dünya savaşı")
        )

        # Chapters / Volumes / Parts / Sections: "Bölüm IV", "Chapter IV", "Cilt II", "Kısım I"
        chap_lead = pynini.string_map([
            ("Bölüm", "bölüm"),
            ("bölüm", "bölüm"),
            ("Chapter", "bölüm"),
            ("chapter", "bölüm"),
            ("Cilt", "cilt"),
            ("cilt", "cilt"),
            ("Volume", "cilt"),
            ("volume", "cilt"),
            ("Kısım", "kısım"),
            ("kısım", "kısım"),
            ("Part", "kısım"),
            ("part", "kısım"),
            ("Fasikül", "fasikül"),
            ("fasikül", "fasikül"),
            ("Madde", "madde"),
            ("madde", "madde"),
        ])
        chap_graph = chap_lead + pynutil.delete(" ") + pynutil.insert(" ") + roman_card

        all_roman = (
            century_graph
            | war_graph
            | monarch_num_first
            | monarch_name_first_straight
            | chap_graph
        ).optimize()

        self.fst = (pynutil.insert('name: "') + convert_space(all_roman) + pynutil.insert('"')).optimize()
