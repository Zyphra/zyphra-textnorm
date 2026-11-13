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

_ROMAN_VALS = [
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

# Malay structural keywords taking cardinal Roman numerals (excluding lone C, D, L, M to keep "Kelas C" safe)
_KEY_WORDS = [
    "bab",
    "abad",
    "bahagian",
    "jilid",
    "volum",
    "volume",
    "seksyen",
    "fasal",
    "pasal",
    "ayat",
    "lampiran",
    "buku",
    "siri",
    "peringkat",
    "tahap",
    "fasa",
    "kelas",
    "semester",
    "suku tahun",
    "perang dunia",
]

# Monarchs, popes, and Malaysian/regional dynastic names taking Roman numerals
_MONARCHS = [
    "Sultan",
    "Raja",
    "Permaisuri",
    "Yang di-Pertuan Agong",
    "Paus",
    "Kaisar",
    "Maharaja",
    "Elizabeth",
    "Charles",
    "Henry",
    "George",
    "Edward",
    "William",
    "Richard",
    "James",
    "Victoria",
    "Louis",
    "Napoleon",
    "Philip",
    "Felipe",
    "Wilhelm",
    "Nicholas",
    "Nikolai",
    "Alexander",
    "Aleksander",
    "Rama",
    "Hassan",
    "Mohammed",
    "Abdullah",
    "Salman",
    "Ramses",
    "Hamengkubuwono",
    "Pakubuwono",
    "Mangkunegara",
    "Yohanes",
    "Benediktus",
    "Fransiskus",
    "Pius",
    "Leo",
    "Paulus",
    "Gregorius",
]


def _int_to_roman(n: int) -> str:
    out = []
    for val, sym in _ROMAN_VALS:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


class RomanFst(GraphFst):
    """
    Keyed-only Malay Roman numeral tagger:
      - Structural keywords: "Bab IV" -> "Bab empat", "Abad XXI" -> "Abad dua puluh satu"
      - Explicit ke- ordinal prefix: "Abad ke-XXI" / "ke-IV" -> "Abad kedua puluh satu" / "keempat"
      - Monarchs, popes & sultans: "Louis XIV" -> "Louis empat belas", "Sultan Abdullah II" -> "Sultan Abdullah dua"
      - Bare tokens like "XL", "MIX", "CD" are untouched!
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        card_nums = list(range(1, 101))
        card_pairs = []
        ord_pairs = []
        for n in card_nums:
            rom = _int_to_roman(n)
            spoken = pynini.shortestpath(str(n) @ cardinal.graph).string()
            card_pairs.append((rom, spoken))
            spoken_ord = "pertama" if n == 1 else f"ke{spoken}"
            ord_pairs.append((rom, spoken_ord))

        # Exclude lone single-letter C, D, L, M after structural words so "Kelas C" / "Vitamin D" stay letters
        safe_card_pairs = [(r, s) for r, s in card_pairs if r not in {"C", "D", "L", "M"}]
        roman_card_safe = pynini.string_map(safe_card_pairs).optimize()

        kw_variants = set()
        for w in _KEY_WORDS:
            kw_variants.add(w)
            kw_variants.add(w.title())
            kw_variants.add(w[0].upper() + w[1:])
            kw_variants.add(w.upper())
        kw_graph = pynini.union(*[pynini.accep(w) for w in sorted(kw_variants)]).optimize()
        keyed_structural = kw_graph + pynini.accep(" ") + roman_card_safe

        # Explicit "ke-IV", "ke-XXI", "Abad ke-XXI" (safe for 1..100 excluding lone C, D, L, M)
        safe_ord_pairs = [(r, s) for r, s in ord_pairs if r not in {"C", "D", "L", "M"}]
        roman_ord_safe = pynini.string_map(safe_ord_pairs).optimize()
        ke_prefix = pynutil.delete(pynini.union("ke-", "Ke-"))
        ke_roman = ke_prefix + roman_ord_safe
        keyed_ke = ke_roman | (kw_graph + pynini.accep(" ") + ke_roman)

        # Monarchs, popes, sultans (1..39)
        monarch_card = pynini.string_map(
            [(_int_to_roman(n), pynini.shortestpath(str(n) @ cardinal.graph).string()) for n in range(1, 40)]
        ).optimize()
        monarch_names = pynini.union(*[pynini.accep(m) for m in _MONARCHS]).optimize()
        keyed_monarch = monarch_names + pynini.accep(" ") + monarch_card

        graph = (keyed_structural | keyed_ke | keyed_monarch).optimize()
        self.graph = convert_space(graph).optimize()
        self.fst = (pynutil.insert('name: "') + self.graph + pynutil.insert('"')).optimize()
