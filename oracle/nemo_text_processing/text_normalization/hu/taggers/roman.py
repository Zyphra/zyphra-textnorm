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
from nemo_text_processing.text_normalization.hu.utils import naive_inflector


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
    for val, sym in vals:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


_KEY_WORDS = [
    "fejezet",
    "század",
    "rész",
    "kötet",
    "cikk",
    "szakasz",
    "paragrafus",
    "törvénycikk",
    "osztály",
    "évfolyam",
    "emelet",
    "kerület",
    "csoport",
    "fokozat",
    "világháború",
    "szimfónia",
    "felvonás",
    "jelenet",
    "tétel",
    "könyv",
    "korszak",
    "évszázad",
    "évezred",
]

_FIXED_KEY_WORDS = [
    "sz.",
    "§",
    "fej.",
    "ker.",
    "em.",
    "évf.",
    "bek.",
    "világháborúban",
    "világháborúig",
    "világháborútól",
    "században",
    "századi",
    "századtól",
    "századig",
    "fejezetben",
]

_ROYAL_NAMES = [
    "István",
    "Béla",
    "László",
    "Károly",
    "Lajos",
    "Mátyás",
    "András",
    "Endre",
    "Géza",
    "Imre",
    "Salamon",
    "Kálmán",
    "Zsigmond",
    "Ulászló",
    "Ferdinánd",
    " Lipót",
    "Lipót",
    "József",
    "Ferenc",
    "Miklós",
    "Sándor",
    "Pál",
    "János",
    "Péter",
    " György",
    "György",
    "Henrik",
    "Eduárd",
    " Jakab",
    "Jakab",
    "Vilmos",
    "Frigyes",
    "Fülöp",
    "Alfonz",
    " Viktor",
    "Viktor",
    " Napóleon",
    "Napóleon",
    "Erzsébet",
    "Mária",
    "Katalin",
    "Anna",
    " Viktória",
    "Viktória",
    "Margit",
    "Krisztina",
    "Piusz",
    "Pius",
    "Benedek",
    " Leó",
    "Leó",
    " Gergely",
    "Gergely",
    " Kelemen",
    "Kelemen",
    "Ince",
    " Orbán",
    "Orbán",
    "Sixtus",
    " Gusztáv",
    "Gusztáv",
    " Krisztián",
    "Krisztián",
    " Ramszesz",
    "Ramszesz",
    "Konstantin",
    " Mehmed",
    "Mehmed",
    "Szulejmán",
]


class RomanFst(GraphFst):
    """
    Keyed Roman numerals for Hungarian:
        "IV. fejezet" -> "negyedik fejezet"
        "XXI. század" -> "huszonegyedik század"
        "IV. Béla" -> "negyedik Béla"
        "II. János Pál" -> "második János Pál"
        "fejezet IV" -> "fejezet négy"
    Bare "XL", "MIX", "CD", "Section C" are untouched.
    """

    def __init__(self, cardinal: GraphFst, ordinal: GraphFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_pairs_1_100 = [(_int_to_roman(n), str(n)) for n in range(1, 101)]
        roman_to_num_100 = pynini.string_map(roman_pairs_1_100).optimize()
        roman_ord_100 = (roman_to_num_100 @ ordinal.bare_ordinals).optimize()

        roman_pairs_post = [
            (_int_to_roman(n), str(n)) for n in range(1, 101) if _int_to_roman(n) not in ("C", "D", "L", "M")
        ]
        roman_card_post = (pynini.string_map(roman_pairs_post) @ cardinal.graph).optimize()

        roman_pairs_royal = [(_int_to_roman(n), str(n)) for n in range(1, 31)]
        roman_ord_royal = (pynini.string_map(roman_pairs_royal) @ ordinal.bare_ordinals).optimize()

        kw_forms = set(_FIXED_KEY_WORDS)
        kw_map = {
            "sz.": "szám",
            "§": "paragrafus",
            "fej.": "fejezet",
            "ker.": "kerület",
            "em.": "emelet",
            "évf.": "évfolyam",
            "bek.": "bekezdés",
        }
        for w in _KEY_WORDS:
            kw_forms.add(w)
            kw_forms.add(w.capitalize())
            try:
                for _, infl in naive_inflector(".", w, False):
                    kw_forms.add(infl)
                    kw_forms.add(infl.capitalize())
            except KeyError:
                pass

        kw_pairs = [(k, kw_map.get(k, k)) for k in kw_forms]
        key_word_fst = pynini.string_map(kw_pairs).optimize()

        post_kw_pairs = []
        for w in _KEY_WORDS:
            post_kw_pairs.append((w, w))
            post_kw_pairs.append((w.capitalize(), w.capitalize()))
        post_kw_fst = pynini.string_map(post_kw_pairs).optimize()

        royal_clean = sorted({r.strip() for r in _ROYAL_NAMES})
        royal_fst = pynini.union(*royal_clean).optimize()

        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)

        # 1. Preposed ordinal with period + key word: "IV. fejezet", "XXI. század", "II. rész", "II. világháború"
        preposed_kw = roman_ord_100 + pynutil.delete(".") + pynini.accep(" ") + key_word_fst
        # Also allow preposed without period for 2+ character Roman numerals before lowercase key words (excluding C/D/L/M/V/X single letters)
        multi_roman_ord = (
            pynini.string_map([(_int_to_roman(n), str(n)) for n in range(2, 51) if len(_int_to_roman(n)) >= 2 and _int_to_roman(n) != "XL"])
            @ ordinal.bare_ordinals
        ).optimize()
        preposed_kw |= multi_roman_ord + pynini.accep(" ") + pynini.union(*_KEY_WORDS)

        # 2. Preposed ordinal with period + royal/papal name: "IV. Béla", "II. János Pál", "XIV. Lajos"
        preposed_royal = roman_ord_royal + pynutil.delete(".") + pynini.accep(" ") + royal_fst

        # 3. Postposed key word + Roman numeral: "fejezet IV" -> "fejezet négy", "Louis XIV" -> "Louis tizennegyedik"
        postposed_kw = post_kw_fst + pynini.accep(" ") + roman_card_post + opt_dot
        foreign_royal = pynini.union(
            "Louis", "Elizabeth", "Charles", "Henry", "George", "Edward", "Philip", "Wilhelm", "Karl", "Gustaf", "Juan"
        )
        postposed_royal = foreign_royal + pynini.accep(" ") + roman_ord_royal + opt_dot

        graph = (preposed_kw | preposed_royal | postposed_kw | postposed_royal).optimize()
        self.graph = convert_space(graph).optimize()
        self.fst = (pynutil.insert("name: \"") + self.graph + pynutil.insert("\"")).optimize()
