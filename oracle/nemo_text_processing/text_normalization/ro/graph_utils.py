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
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    convert_space,
    delete_space,
    insert_space,
)

# Romanian specific letters
RO_LOWER = pynini.union(
    "a", "ă", "â", "b", "c", "d", "e", "f", "g", "h", "i", "î",
    "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "ș", "t", "ț",
    "u", "v", "w", "x", "y", "z",
    # Accept cedilla forms on input and map to standard comma-below
    pynini.cross("ş", "ș"),
    pynini.cross("ţ", "ț"),
).optimize()

RO_UPPER = pynini.union(
    "A", "Ă", "Â", "B", "C", "D", "E", "F", "G", "H", "I", "Î",
    "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "Ș", "T", "Ț",
    "U", "V", "W", "X", "Y", "Z",
    pynini.cross("Ş", "Ș"),
    pynini.cross("Ţ", "Ț"),
).optimize()

RO_ALPHA = (RO_LOWER | RO_UPPER).optimize()
RO_ALNUM = (RO_ALPHA | NEMO_DIGIT).optimize()

# Dashes
RO_DASH = pynini.union("-", "–", "—", "−").optimize()

# Grouping separators: dot or space
cardinal_separator = pynini.union(".", " ", "\u00a0").optimize()

# Decimal separator: comma or dot
decimal_separator = pynini.union(",", ".").optimize()


def to_name_token(graph: "pynini.FstLike") -> "pynini.FstLike":
    """Wraps spoken phrase in tokens { name: \"...\" } using convert_space."""
    return (
        pynutil.insert('name: "')
        + convert_space(graph).optimize()
        + pynutil.insert('"')
    ).optimize()


def spell_triplet(val: int, gender: str = "masc") -> str:
    """Spells an integer in 1..999 in Romanian."""
    c = val // 100
    rem = val % 100
    d = rem // 10
    u = rem % 10

    parts = []
    if c == 1:
        parts.append("o sută")
    elif c == 2:
        parts.append("două sute")
    elif c >= 3:
        digs = {3: "trei", 4: "patru", 5: "cinci", 6: "șase", 7: "șapte", 8: "opt", 9: "nouă"}
        parts.append(digs[c] + " sute")

    if rem > 0:
        if rem == 1:
            if gender == "fem":
                parts.append("una")
            elif gender == "fem_adj":
                parts.append("o")
            elif gender in ("neut_adj", "masc_adj"):
                parts.append("un")
            else:
                parts.append("unu")
        elif rem == 2:
            if gender in ("fem", "fem_adj", "neut", "neut_adj"):
                parts.append("două")
            else:
                parts.append("doi")
        elif rem < 10:
            digs = {3: "trei", 4: "patru", 5: "cinci", 6: "șase", 7: "șapte", 8: "opt", 9: "nouă"}
            parts.append(digs[rem])
        elif rem < 20:
            teens = {
                10: "zece", 11: "unsprezece", 12: "doisprezece", 13: "treisprezece",
                14: "paisprezece", 15: "cincisprezece", 16: "șaisprezece",
                17: "șaptesprezece", 18: "optsprezece", 19: "nouăsprezece"
            }
            word = teens[rem]
            if rem == 12 and gender in ("fem", "fem_adj", "neut", "neut_adj"):
                word = "douăsprezece"
            parts.append(word)
        else:
            ties = {
                2: "douăzeci", 3: "treizeci", 4: "patruzeci", 5: "cincizeci",
                6: "șaizeci", 7: "șaptezeci", 8: "optzeci", 9: "nouăzeci"
            }
            tie = ties[d]
            if u == 0:
                parts.append(tie)
            else:
                if u == 1:
                    u_word = "una" if gender == "fem" else ("o" if gender == "fem_adj" else ("un" if gender in ("masc_adj", "neut_adj") else "unu"))
                elif u == 2:
                    u_word = "două" if gender in ("fem", "fem_adj", "neut", "neut_adj") else "doi"
                else:
                    digs = {3: "trei", 4: "patru", 5: "cinci", 6: "șase", 7: "șapte", 8: "opt", 9: "nouă"}
                    u_word = digs[u]
                parts.append(tie + " și " + u_word)

    return " ".join(parts)


def spell_scale_triplet(val: int, sing: str, plur: str) -> str:
    """Spells thousands/millions/billions with Romanian 'de' rules."""
    if val == 0:
        return ""
    if val == 1:
        if sing == "mie":
            return "o mie"
        return "un " + sing
    rem = val % 100
    words = spell_triplet(val, "fem")
    de = " de" if (rem == 0 or rem >= 20) else ""
    return words + de + " " + plur


def build_number_transducer(gender: str = "masc") -> "pynini.FstLike":
    """Builds a full 0..999,999,999,999 number transducer in Romanian."""
    pad_to_3 = pynini.string_map([(str(i), f"{i:03d}") for i in range(1, 1000)])
    triplet_map = pynini.string_map([(f"{i:03d}", spell_triplet(i, gender)) for i in range(1, 1000)])
    num_1_to_3 = (pad_to_3 @ triplet_map).optimize()

    thousands_triplet = pynini.string_map([(f"{i:03d}", spell_scale_triplet(i, "mie", "mii")) for i in range(1, 1000)])
    thousands_high = (pad_to_3 @ thousands_triplet).optimize()
    units_low = (pynini.cross("000", "") | pynini.string_map([(f"{i:03d}", " " + spell_triplet(i, gender)) for i in range(1, 1000)])).optimize()
    num_4_to_6 = (thousands_high + units_low).optimize()

    millions_triplet = pynini.string_map([(f"{i:03d}", spell_scale_triplet(i, "milion", "milioane")) for i in range(1, 1000)])
    millions_high = (pad_to_3 @ millions_triplet).optimize()
    thousands_mid = (pynini.cross("000", "") | pynini.string_map([(f"{i:03d}", " " + spell_scale_triplet(i, "mie", "mii")) for i in range(1, 1000)])).optimize()
    num_7_to_9 = (millions_high + thousands_mid + units_low).optimize()

    billions_triplet = pynini.string_map([(f"{i:03d}", spell_scale_triplet(i, "miliard", "miliarde")) for i in range(1, 1000)])
    billions_high = (pad_to_3 @ billions_triplet).optimize()
    millions_mid = (pynini.cross("000", "") | pynini.string_map([(f"{i:03d}", " " + spell_scale_triplet(i, "milion", "milioane")) for i in range(1, 1000)])).optimize()
    num_10_to_12 = (billions_high + millions_mid + thousands_mid + units_low).optimize()

    zero_graph = pynini.cross("0", "zero")
    clean_digits = (zero_graph | num_1_to_3 | num_4_to_6 | num_7_to_9 | num_10_to_12).optimize()

    # Support grouped numbers (e.g. 1.000, 1.000.000, 1 000 000)
    cardinal_cleaner = pynini.closure(NEMO_DIGIT, 1, 3) + pynini.closure(pynutil.delete(pynini.union(".", ",", " ", "\u00a0")) + NEMO_DIGIT**3, 1)
    full_cardinal = (cardinal_cleaner | pynini.closure(NEMO_DIGIT, 1)) @ clean_digits

    return full_cardinal.optimize()
