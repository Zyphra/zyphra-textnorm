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

# Tagalog structural keywords taking cardinal Roman numerals (excluding lone C, D, L, M to keep "Klase C" safe)
_KEY_WORDS = [
    "kabanata",
    "siglo",
    "bahagi",
    "tomo",
    "aklat",
    "aralin",
    "yugto",
    "baitang",
    "antas",
    "seksiyon",
    "artikulo",
    "batas",
    "bilang",
    "blg.",
    "blg",
    "digmaang pandaigdig",
]

# Monarchs, popes, and historical leaders
_MONARCHS = [
    "Papa",
    "Hari",
    "Reyna",
    "Pangulo",
    "Heneral",
    "Gobernador",
    "Juan Pablo",
    "Benedicto",
    "Francisco",
    "Pio",
    "Leo",
    "Pablo",
    "Gregorio",
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
    "Carlos",
    "Alfonso",
    "Fernando",
    "Alexander",
    "Nicholas",
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
    Keyed-only Tagalog Roman numeral tagger:
      - Structural keywords: "Kabanata IV" -> "Kabanata apat", "Siglo XXI" -> "Siglo dalawampu't isa"
      - Explicit ika- ordinal prefix: "ika-XXI" / "ika-IV" -> "ikadalawampu't isa" / "ikaapat"
      - Monarchs & popes: "Louis XIV" -> "Louis labing-apat", "Papa Juan Pablo II" -> "Papa Juan Pablo ikalawa"
      - Bare tokens like "XL", "MIX", "CD" are untouched!
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        card_nums = list(range(1, 101))
        card_pairs = []
        ord_pairs = []
        for n in card_nums:
            rom = _int_to_roman(n)
            spoken = pynini.shortestpath(pynini.accep(str(n)) @ cardinal.graph).string()
            card_pairs.append((rom, spoken))
            if n == 1:
                spoken_ord = "una"
            elif n == 2:
                spoken_ord = "ikalawa"
            elif n == 3:
                spoken_ord = "ikatlo"
            else:
                spoken_ord = f"ika{spoken}"
            ord_pairs.append((rom, spoken_ord))

        # Exclude lone single-letter C, D, L, M after structural words
        safe_card_pairs = [(r, s) for r, s in card_pairs if r not in {"C", "D", "L", "M"}]
        roman_card_safe = pynini.string_map(safe_card_pairs).optimize()

        kw_variants = set()
        for w in _KEY_WORDS:
            kw_variants.add(w)
            kw_variants.add(w.title())
            kw_variants.add(w.upper())
        kw_fst = pynini.string_map(list(kw_variants))

        structural = kw_fst + pynini.accep(" ") + roman_card_safe

        # Explicit ordinal prefix (e.g. "ika-XXI" -> "ikadalawampu't isa", "Ika-IV" -> "ikaapat")
        ord_map = pynini.string_map(ord_pairs).optimize()
        ord_prefix = pynutil.delete(pynini.union("ika-", "Ika-", "pang-", "Pang-")) + ord_map
        structural_ord = (
            kw_fst
            + pynini.accep(" ")
            + ord_prefix
        )

        # Monarchs & popes
        monarch_variants = set()
        for m in _MONARCHS:
            monarch_variants.add(m)
            monarch_variants.add(m.upper())
        monarch_fst = pynini.string_map(list(monarch_variants))
        monarch_rule = monarch_fst + pynini.accep(" ") + (ord_map | roman_card_safe)

        self.graph = (convert_space(structural | structural_ord | monarch_rule | ord_prefix)).optimize()
        self.fst = (pynutil.insert('name: "') + self.graph + pynutil.insert('"')).optimize()
