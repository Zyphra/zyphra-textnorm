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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst, convert_space
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst


class RomanFst(GraphFst):
    """
    Keyed Polish Roman numeral tagger:
      - Structural keywords: "Rozdział IV" -> "Rozdział czwarty", "XXI wiek" -> "dwudziesty pierwszy wiek"
      - Monarchs & popes: "Jan Paweł II" -> "Jan Paweł Drugi", "Henryk VIII" -> "Henryk Ósmy"
      - Wars: "II wojna światowa" -> "druga wojna światowa"
      - Safety: bare "XL", "MIX", "CD", "Sekcja C" are untouched!
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        # Mapping of Roman numerals to spoken Polish ordinals (masculine, feminine, genitive)
        rom_map_m = [
            ("I", "pierwszy"),
            ("II", "drugi"),
            ("III", "trzeci"),
            ("IV", "czwarty"),
            ("V", "piąty"),
            ("VI", "szósty"),
            ("VII", "siódmy"),
            ("VIII", "ósmy"),
            ("IX", "dziewiąty"),
            ("X", "dziesiąty"),
            ("XI", "jedenasty"),
            ("XII", "dwunasty"),
            ("XIII", "trzynasty"),
            ("XIV", "czternasty"),
            ("XV", "piętnasty"),
            ("XVI", "szesnasty"),
            ("XVII", "siedemnasty"),
            ("XVIII", "osiemnasty"),
            ("XIX", "dziewiętnasty"),
            ("XX", "dwudziesty"),
            ("XXI", "dwudziesty pierwszy"),
            ("XXII", "dwudziesty drugi"),
        ]
        rom_map_f = [
            ("I", "pierwsza"),
            ("II", "druga"),
            ("III", "trzecia"),
            ("IV", "czwarta"),
            ("V", "piąta"),
            ("VI", "szósta"),
            ("VII", "siódma"),
            ("VIII", "ósma"),
            ("IX", "dziewiąta"),
            ("X", "dziesiąta"),
            ("XI", "jedenasta"),
            ("XII", "dwunasta"),
            ("XIII", "trzynasta"),
            ("XIV", "czternasta"),
            ("XV", "piętnasta"),
            ("XVI", "szesnasta"),
            ("XVII", "siedemnasta"),
            ("XVIII", "osiemnasta"),
            ("XIX", "dziewiętnasta"),
            ("XX", "dwudziesta"),
            ("XXI", "dwudziesta pierwsza"),
            ("XXII", "dwudziesta druga"),
        ]
        rom_map_gen = [
            ("I", "pierwszego"),
            ("II", "drugiego"),
            ("III", "trzeciego"),
            ("IV", "czwartego"),
            ("V", "piątego"),
            ("VI", "szóstego"),
            ("VII", "siódmego"),
            ("VIII", "ósmego"),
            ("IX", "dziewiątego"),
            ("X", "dziesiątego"),
            ("XI", "jedenastego"),
            ("XII", "dwunastego"),
            ("XIII", "trzynastego"),
            ("XIV", "czternastego"),
            ("XV", "piętnastego"),
            ("XVI", "szesnastego"),
            ("XVII", "siedemnastego"),
            ("XVIII", "osiemnastego"),
            ("XIX", "dziewiętnastego"),
            ("XX", "dwudziestego"),
            ("XXI", "dwudziestego pierwszego"),
            ("XXII", "dwudziestego drugiego"),
        ]

        # Capitalized monarchs for title matching (Jan Paweł Drugi, etc.)
        rom_map_title = [
            ("I", "Pierwszy"),
            ("II", "Drugi"),
            ("III", "Trzeci"),
            ("IV", "Czwarty"),
            ("V", "Piąty"),
            ("VI", "Szósty"),
            ("VII", "Siódmy"),
            ("VIII", "Ósmy"),
            ("IX", "Dziewiąty"),
            ("X", "Dziesiąty"),
            ("XI", "Jedenasty"),
            ("XII", "Dwunasty"),
            ("XIII", "Trzynasty"),
            ("XIV", "Czternasty"),
            ("XV", "Piętnasty"),
            ("XVI", "Szesnasty"),
        ]

        fst_rom_m = pynini.string_map(rom_map_m)
        fst_rom_f = pynini.string_map(rom_map_f)
        fst_rom_gen = pynini.string_map(rom_map_gen)
        fst_rom_title = pynini.string_map(rom_map_title)

        # Context words before Roman numeral
        pre_masc = pynini.union(
            "Rozdział", "rozdział", "Rozdz.", "rozdz.",
            "Tom", "tom",
            "Akt", "akt",
            "Wiek", "wiek", "w.",
            "Artykuł", "artykuł", "art.",
            "Paragraf", "paragraf",
            "Punkt", "punkt", "pkt",
            "Stopień", "stopień",
        )
        pre_fem = pynini.union(
            "Część", "część",
            "Scena", "scena",
            "Klasa", "klasa",
            "Księga", "księga",
        )
        monarch_names = pynini.union(
            "Jan Paweł", "Jan", "Benedykt", "Franciszek", "Pius", "Leon", "Grzegorz",
            "Zygmunt", "Zygmunt August", "Kazimierz", "Władysław", "Bolesław",
            "Stefan", "Stanisław", "Stanisław August", "Henryk", "Ludwik",
            "Karol", "Edward", "Wilhelm", "Aleksander", "Mikołaj", "Piotr",
            "Napoleon", "Filip", "Jerzy", "Ryszard", "Papież", "Król", "Cesarz",
        )
        monarch_fem = pynini.union("Elżbieta", "Katarzyna", "Maria", "Królowa")

        keyed_masc = pre_masc + pynini.accep(" ") + fst_rom_m
        keyed_fem = pre_fem + pynini.accep(" ") + fst_rom_f
        keyed_monarch = monarch_names + pynini.accep(" ") + fst_rom_title
        keyed_monarch_fem = monarch_fem + pynini.accep(" ") + (fst_rom_f @ pynini.string_map([("pierwsza", "Pierwsza"), ("druga", "Druga"), ("trzecia", "Trzecia")]))

        # Context words after Roman numeral: "XXI wiek", "XXI wieku", "II wojna światowa"
        post_wiek = fst_rom_m + pynini.cross(" wiek", " wiek")
        post_wieku = fst_rom_gen + pynini.cross(" wieku", " wieku")
        post_war = fst_rom_f + pynini.cross(" wojna światowa", " wojna światowa")
        post_war_gen = (fst_rom_f @ pynini.cdrewrite(pynini.cross("a", "ej"), "", "[EOS]", pynini.closure(pynini.union(*"abcdefghijklmnopqrstuvwxyząćęłńóśźż")))) + pynini.cross(" wojny światowej", " wojny światowej")

        self.graph = (
            keyed_masc
            | keyed_fem
            | keyed_monarch
            | keyed_monarch_fem
            | post_wiek
            | post_wieku
            | post_war
            | post_war_gen
        ).optimize()

        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
