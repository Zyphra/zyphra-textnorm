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
)


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Slovak contextual Roman numerals, e.g.
        Kapitola IV -> Kapitola štvrtá
        XXI storočie -> dvadsiate prvé storočie
        Karol IV. -> Karol štvrtý
        XL -> X L
        MIX -> M I X
        CD -> C D
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_ord_masc = pynini.string_map([
            ("I", "prvý"),
            ("II", "druhý"),
            ("III", "tretí"),
            ("IV", "štvrtý"),
            ("V", "piaty"),
            ("VI", "šiesty"),
            ("VII", "siedmy"),
            ("VIII", "ôsmy"),
            ("IX", "deviaty"),
            ("X", "desiaty"),
            ("XI", "jedenásty"),
            ("XII", "dvanásty"),
            ("XIII", "trinásty"),
            ("XIV", "štrnásty"),
            ("XV", "pätnásty"),
            ("XVI", "šestnásty"),
            ("XVII", "sedemnásty"),
            ("XVIII", "osemnásty"),
            ("XIX", "devätnásty"),
            ("XX", "dvadsiaty"),
            ("XXI", "dvadsiaty prvý"),
        ])

        roman_ord_fem = pynini.string_map([
            ("I", "prvá"),
            ("II", "druhá"),
            ("III", "tretia"),
            ("IV", "štvrtá"),
            ("V", "piata"),
            ("VI", "šiesta"),
            ("VII", "siedma"),
            ("VIII", "ôsma"),
            ("IX", "deviata"),
            ("X", "desiata"),
            ("XI", "jedenásta"),
            ("XII", "dvanásta"),
            ("XIII", "trinásta"),
            ("XIV", "štrnásta"),
            ("XV", "pätnásta"),
            ("XVI", "šestnásta"),
            ("XVII", "sedemnásta"),
            ("XVIII", "osemnásta"),
            ("XIX", "devätnásta"),
            ("XX", "dvadsiata"),
            ("XXI", "dvadsiata prvá"),
        ])

        roman_ord_neut = pynini.string_map([
            ("I", "prvé"),
            ("II", "druhé"),
            ("III", "tretie"),
            ("IV", "štvrté"),
            ("V", "piate"),
            ("VI", "šieste"),
            ("VII", "siedme"),
            ("VIII", "ôsme"),
            ("IX", "deviate"),
            ("X", "desiate"),
            ("XI", "jedenáste"),
            ("XII", "dvanáste"),
            ("XIII", "trináste"),
            ("XIV", "štrnáste"),
            ("XV", "pätnáste"),
            ("XVI", "šestnáste"),
            ("XVII", "sedemnáste"),
            ("XVIII", "osemnáste"),
            ("XIX", "devätnáste"),
            ("XX", "dvadsiate"),
            ("XXI", "dvadsiate prvé"),
        ])

        dot = pynini.closure(pynutil.delete("."), 0, 1)

        # Feminine section words (Kapitola, Hlava, Časť)
        fem_keywords = pynini.union("Kapitola", "kapitola", "Hlava", "hlava", "Časť", "časť")
        chap_graph = fem_keywords + pynini.accep(" ") + (roman_ord_fem + dot)

        # Masculine section words (Diel, Oddiel, Článok, Zväzok)
        masc_keywords = pynini.union("Diel", "diel", "Oddiel", "oddiel", "Článok", "článok", "Zväzok", "zväzok")
        masc_sec_graph = masc_keywords + pynini.accep(" ") + (roman_ord_masc + dot)

        # Century (XXI. storočie)
        cent_graph = (roman_ord_neut + dot) + pynini.accep(" ") + pynini.union(
            "storočie", "storočia", "storočí", "st.", "stor."
        )

        # Monarchs
        monarch_names = pynini.union(
            "Karol",
            "Ján Pavol",
            "Ľudovít",
            "František",
            "Alžbeta",
            "Henrich",
            "Juraj",
            "Alexander",
            "Mikuláš",
            "Peter",
            "Viliam",
            "Ferdinand",
            "Štefan",
            "Václav",
            "Matej",
            "Žigmund",
        )
        monarch_graph = monarch_names + pynini.accep(" ") + (roman_ord_masc + dot)

        # Safety controls: abbreviations that resemble Roman numerals
        safety = pynini.string_map([
            ("XL", "X L"),
            ("MIX", "M I X"),
            ("CD", "C D"),
            ("DJ", "D J"),
        ])

        all_roman = chap_graph | masc_sec_graph | cent_graph | monarch_graph | safety
        self.fst = all_roman.optimize()
