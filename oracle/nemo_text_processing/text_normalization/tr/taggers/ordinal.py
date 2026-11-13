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
    NEMO_SIGMA,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying ordinals in Turkish:
    - Dot ordinals: 1. -> birinci, 2. -> ikinci, 20. -> yirminci, 23. -> yirmi üçüncü, 100. -> yüzüncü
    - Chapter / Section ordinals: 9. Bölüm -> dokuzuncu bölüm
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        end_ordinal_map = pynini.string_map([
            ("sıfır", "sıfırıncı"),
            ("bir", "birinci"),
            ("iki", "ikinci"),
            ("üç", "üçüncü"),
            ("dört", "dördüncü"),
            ("beş", "beşinci"),
            ("altı", "altıncı"),
            ("yedi", "yedinci"),
            ("sekiz", "sekizinci"),
            ("dokuz", "dokuzuncu"),
            ("on", "onuncu"),
            ("yirmi", "yirminci"),
            ("otuz", "otuzuncu"),
            ("kırk", "kırkıncı"),
            ("elli", "ellinci"),
            ("altmış", "altmışıncı"),
            ("yetmiş", "yetmişinci"),
            ("seksen", "sekseninci"),
            ("doksan", "doksanıncı"),
            ("yüz", "yüzüncü"),
            ("bin", "bininci"),
            ("milyon", "milyonuncu"),
            ("milyar", "milyarıncı"),
            ("trilyon", "trilyonuncu"),
            ("katrilyon", "katrilyonuncu"),
        ])

        to_ordinal = pynini.cdrewrite(end_ordinal_map, "", "[EOS]", NEMO_SIGMA)
        cardinal_to_ordinal = (cardinal.positive_cardinals @ to_ordinal).optimize()
        self.cardinal_to_ordinal = cardinal_to_ordinal

        # Dot ordinals: 1., 2., 20., 23., 100.
        dot_ordinal = cardinal_to_ordinal + pynutil.delete(".")

        # Letter + colon + a/e ordinal forms like 1:a, 1:inci, 2:nci
        alt_ordinal_suffix = pynini.union(
            pynini.cross(":a", ""),
            pynini.cross(":inci", ""),
            pynini.cross(":nci", ""),
            pynini.cross(":üncü", ""),
            pynini.cross(":uncu", ""),
            pynini.cross(":ncı", ""),
            pynini.cross(":ıncı", ""),
        )
        colon_ordinal = cardinal_to_ordinal + alt_ordinal_suffix

        # Ordinal chapters: 9 kap -> dokuzuncu bölüm
        kap_suffix = pynutil.insert(" ") + pynini.cross(
            pynini.union("kap", "kap.", "bölüm", "kısım"), "bölüm"
        )
        ordinal_chap = (cardinal_to_ordinal + pynini.closure(pynutil.delete("."), 0, 1) + kap_suffix)

        all_ordinals = (dot_ordinal | colon_ordinal | ordinal_chap).optimize()
        self.all_ordinals = all_ordinals

        self.fst = (pynutil.insert('name: "') + convert_space(all_ordinals) + pynutil.insert('"')).optimize()
