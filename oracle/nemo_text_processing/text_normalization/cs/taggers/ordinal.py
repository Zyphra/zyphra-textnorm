# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.cs.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Czech ordinal numbers and contextual Roman numerals.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        # Base ordinals 1..19 (masculine citation form)
        ord_1_19_map = [
            ("1", "první"),
            ("2", "druhý"),
            ("3", "třetí"),
            ("4", "čtvrtý"),
            ("5", "pátý"),
            ("6", "šestý"),
            ("7", "sedmý"),
            ("8", "osmý"),
            ("9", "devátý"),
            ("10", "desátý"),
            ("11", "jedenáctý"),
            ("12", "dvanáctý"),
            ("13", "třináctý"),
            ("14", "čtrnáctý"),
            ("15", "patnáctý"),
            ("16", "šestnáctý"),
            ("17", "sedmnáctý"),
            ("18", "osmnáctý"),
            ("19", "devatenáctý"),
        ]
        ord_1_19 = pynini.string_map(ord_1_19_map)
        digits_ord = pynini.string_map(ord_1_19_map[:9])

        # Tens ordinals
        tens_ord_map = [
            ("2", "dvacátý"),
            ("3", "třicátý"),
            ("4", "čtyřicátý"),
            ("5", "padesátý"),
            ("6", "šedesátý"),
            ("7", "sedmdesátý"),
            ("8", "osmdesátý"),
            ("9", "devadesátý"),
        ]
        tens_ord = pynini.string_map(tens_ord_map)

        tens_ord_with_unit = (
            (tens_ord + pynutil.delete("0"))
            | (tens_ord + pynutil.insert(" ") + digits_ord)
        )

        ord_1_99 = (ord_1_19 | tens_ord_with_unit).optimize()

        hundreds_ord_map = [
            ("1", "stý"),
            ("2", "dvoustý"),
            ("3", "třístý"),
            ("4", "čtyřstý"),
            ("5", "pětistý"),
            ("6", "šestistý"),
            ("7", "sedmistý"),
            ("8", "osmistý"),
            ("9", "devítistý"),
        ]
        hundreds_ord = pynini.string_map(hundreds_ord_map)

        # Compound hundreds ordinals e.g. 101 -> "sto první", 125 -> "sto dvacátý pátý"
        hundreds_card_map = [
            ("1", "sto"),
            ("2", "dvě stě"),
            ("3", "tři sta"),
            ("4", "čtyři sta"),
            ("5", "pět set"),
            ("6", "šest set"),
            ("7", "sedm set"),
            ("8", "osm set"),
            ("9", "devět set"),
        ]
        hundreds_card = pynini.string_map(hundreds_card_map)

        del_00 = pynutil.delete("00")
        del_0 = pynutil.delete("0")

        ord_100_999 = (
            (hundreds_ord + del_00)
            | (hundreds_card + del_0 + pynutil.insert(" ") + digits_ord)
            | (hundreds_card + pynutil.insert(" ") + (NEMO_DIGIT**2 @ (ord_1_19 | tens_ord_with_unit)))
        )

        ord_1_999 = (ord_1_99 | ord_100_999).optimize()

        # Thousands ordinals
        th_ord = pynini.cross("1000", "tisící") | pynini.cross("2000", "dvoutisící")
        compound_th_ord = (
            pynini.cross("1", "tisíc ")
            | pynini.cross("2", "dva tisíce ")
            | pynini.cross("3", "tři tisíce ")
        ) + (
            (del_00 + digits_ord)
            | (del_0 + ord_1_99)
            | ord_100_999
        )

        full_ordinals = (
            ord_1_999
            | th_ord
            | compound_th_ord
        ).optimize()

        dot = pynutil.delete(".")
        self.dot_ordinals = (full_ordinals + dot).optimize()

        # Roman numerals to numbers (1 to 30)
        roman_map = [
            ("I", "1"),
            ("II", "2"),
            ("III", "3"),
            ("IV", "4"),
            ("V", "5"),
            ("VI", "6"),
            ("VII", "7"),
            ("VIII", "8"),
            ("IX", "9"),
            ("X", "10"),
            ("XI", "11"),
            ("XII", "12"),
            ("XIII", "13"),
            ("XIV", "14"),
            ("XV", "15"),
            ("XVI", "16"),
            ("XVII", "17"),
            ("XVIII", "18"),
            ("XIX", "19"),
            ("XX", "20"),
            ("XXI", "21"),
            ("XXII", "22"),
            ("XXV", "25"),
            ("XXX", "30"),
        ]
        roman_to_digit = pynini.string_map(roman_map)

        # Roman monarchs: e.g. "Karel IV." / "Karel IV" -> "Karel Čtvrtý"
        monarch_names = pynini.union(
            "Karel", "karel", "Ludvík", "ludvík", "Jan Pavel", "jan pavel",
            "Petr", "petr", "Jiří", "jiří", "Václav", "václav", "Rudolf", "rudolf",
            "František", "františek", "Josef", "josef", "Jindřich", "jindřich",
            "Vilém", "vilém", "Filip", "filip", "Eduard", "eduard", "Richard", "richard",
            "Jan", "jan"
        )
        monarch_ord_map = [
            ("I", "První"),
            ("II", "Druhý"),
            ("III", "Třetí"),
            ("IV", "Čtvrtý"),
            ("V", "Pátý"),
            ("VI", "Šestý"),
            ("VII", "Sedmý"),
            ("VIII", "Osmý"),
            ("IX", "Devátý"),
            ("X", "Desátý"),
            ("XI", "Jedenáctý"),
            ("XII", "Dvanáctý"),
            ("XIII", "Třináctý"),
            ("XIV", "Čtrnáctý"),
            ("XV", "Patnáctý"),
            ("XVI", "Šestnáctý"),
        ]
        monarch_ord = pynini.string_map(monarch_ord_map)
        fem_monarch = pynini.union("Alžběta", "alžběta", "Marie", "marie", "Kateřina", "kateřina")
        fem_monarch_ord = pynini.string_map([
            ("I", "První"),
            ("II", "Druhá"),
            ("III", "Třetí"),
        ])

        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)
        sp = pynini.accep(" ")

        monarch_masc = monarch_names + sp + monarch_ord + opt_dot
        monarch_fem = fem_monarch + sp + fem_monarch_ord + opt_dot
        self.monarchs = (monarch_masc | monarch_fem).optimize()

        # Centuries: "XXI. století" / "21. století" -> "dvacáté první století"
        century_nouns = pynini.union("století", "stoleti", "st.", "st") + pynutil.delete(pynini.closure(".", 0, 1))
        century_ord_map = [
            ("I", "první"),
            ("II", "druhé"),
            ("III", "třetí"),
            ("IV", "čtvrté"),
            ("V", "páté"),
            ("VI", "šesté"),
            ("VII", "sedmé"),
            ("VIII", "osmé"),
            ("IX", "deváté"),
            ("X", "desáté"),
            ("XI", "jedenácté"),
            ("XII", "dvanácté"),
            ("XIII", "třinácté"),
            ("XIV", "čtrnácté"),
            ("XV", "patnácté"),
            ("XVI", "šestnácté"),
            ("XVII", "sedmnácté"),
            ("XVIII", "osmnácté"),
            ("XIX", "devatenácté"),
            ("XX", "dvacáté"),
            ("XXI", "dvacáté první"),
            ("XXII", "dvacáté druhé"),
            ("1", "první"),
            ("2", "druhé"),
            ("3", "třetí"),
            ("4", "čtvrté"),
            ("5", "páté"),
            ("6", "šesté"),
            ("7", "sedmé"),
            ("8", "osmé"),
            ("9", "deváté"),
            ("10", "desáté"),
            ("19", "devatenácté"),
            ("20", "dvacáté"),
            ("21", "dvacáté první"),
            ("22", "dvacáté druhé"),
        ]
        century_ord = pynini.string_map(century_ord_map)
        self.century = (
            century_ord + opt_dot + sp + pynutil.insert("století") + pynutil.delete(century_nouns)
        ).optimize()

        # Chapters / sections: "Kapitola IV", "část II", "oddíl III", "hlava IV"
        sec_prefix = pynini.string_map([
            ("Kapitola", "Kapitola"),
            ("kapitola", "kapitola"),
            ("Část", "Část"),
            ("část", "část"),
            ("Oddíl", "Oddíl"),
            ("oddíl", "oddíl"),
            ("Hlava", "Hlava"),
            ("hlava", "hlava"),
            ("Paragraf", "Paragraf"),
            ("paragraf", "paragraf"),
        ])
        sec_num_card = pynini.string_map([
            ("I", "jedna"),
            ("II", "dvě"),
            ("III", "tři"),
            ("IV", "čtyři"),
            ("V", "pět"),
            ("VI", "šest"),
            ("VII", "sedm"),
            ("VIII", "osm"),
            ("IX", "devět"),
            ("X", "deset"),
            ("XI", "jedenáct"),
            ("XII", "dvanáct"),
        ])
        self.chapters = (sec_prefix + sp + sec_num_card + opt_dot).optimize()

        # Floor / place / class:
        # "IV. patro" / "4. patro" -> "čtvrté patro"
        # "5. třída" -> "pátá třída"
        # "3. místo" -> "třetí místo"
        floor_ord_map = [
            ("I", "první"),
            ("II", "druhé"),
            ("III", "třetí"),
            ("IV", "čtvrté"),
            ("V", "páté"),
            ("1", "první"),
            ("2", "druhé"),
            ("3", "třetí"),
            ("4", "čtvrté"),
            ("5", "páté"),
        ]
        floor_ord = pynini.string_map(floor_ord_map) + opt_dot + sp + pynini.accep("patro")

        place_ord_map = [
            ("1", "první"),
            ("2", "druhé"),
            ("3", "třetí"),
            ("4", "čtvrté"),
            ("5", "páté"),
        ]
        place_ord = pynini.string_map(place_ord_map) + opt_dot + sp + pynini.accep("místo")

        class_ord_map = [
            ("1", "první"),
            ("2", "druhá"),
            ("3", "třetí"),
            ("4", "čtvrtá"),
            ("5", "pátá"),
            ("6", "šestá"),
            ("7", "sedmá"),
            ("8", "osmá"),
            ("9", "devátá"),
        ]
        class_ord = pynini.string_map(class_ord_map) + opt_dot + sp + pynini.accep("třída")

        self.contextual_ordinals = (floor_ord | place_ord | class_ord).optimize()

        # Safety controls: XL, MIX, CD, Section C, Section L
        # Must NOT be transduced as numbers!
        self.safety_controls = pynini.string_map([
            ("XL", "X L"),
            ("MIX", "M I X"),
            ("CD", "C D"),
            ("Section C", "Section C"),
            ("Section L", "Section L"),
            ("Sekce C", "Sekce C"),
            ("Sekce L", "Sekce L"),
        ])

        self.fst = (
            self.safety_controls
            | self.monarchs
            | self.century
            | self.chapters
            | self.contextual_ordinals
            | self.dot_ordinals
        ).optimize()
