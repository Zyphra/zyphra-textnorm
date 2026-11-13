# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
    Finite state transducer for Norwegian Bokmål contextual Roman numerals.
    e.g. Harald V -> Harald den femte
         Karl XII -> Karl den tolfte
         Louis XIV -> Louis den fjortende
         Elizabeth II -> Elizabeth den andre
         Kapittel IV -> Kapittel fire
         kapittel IV -> kapittel fire
         del II -> del to
         bind III -> bind tre
         akt I -> akt en
         århundre XXI -> århundre tjueen
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        # Roman numerals as cardinals: I -> en, II -> to, IV -> fire
        roman_cardinals = pynini.string_map(
            [
                ("I", "en"),
                ("II", "to"),
                ("III", "tre"),
                ("IV", "fire"),
                ("V", "fem"),
                ("VI", "seks"),
                ("VII", "sju"),
                ("VIII", "åtte"),
                ("IX", "ni"),
                ("X", "ti"),
                ("XI", "elleve"),
                ("XII", "tolv"),
                ("XIII", "tretten"),
                ("XIV", "fjorten"),
                ("XV", "femten"),
                ("XVI", "seksten"),
                ("XVII", "sytten"),
                ("XVIII", "atten"),
                ("XIX", "nitten"),
                ("XX", "tjue"),
                ("XXI", "tjueen"),
            ]
        )

        # Roman numerals as ordinals for monarchs: I -> den første, II -> den andre
        roman_ordinals = pynini.string_map(
            [
                ("I", "den første"),
                ("II", "den andre"),
                ("III", "den tredje"),
                ("IV", "den fjerde"),
                ("V", "den femte"),
                ("VI", "den sjette"),
                ("VII", "den sjuende"),
                ("VIII", "den åttende"),
                ("IX", "den niende"),
                ("X", "den tiende"),
                ("XI", "den ellevte"),
                ("XII", "den tolfte"),
                ("XIII", "den trettende"),
                ("XIV", "den fjortende"),
                ("XV", "den femtende"),
                ("XVI", "den sekstende"),
                ("XVII", "den syttende"),
                ("XVIII", "den attende"),
                ("XIX", "den nittende"),
                ("XX", "den tjuende"),
                ("XXI", "den tjueførste"),
            ]
        )

        # 1. Monarchs & Popes
        monarch_names = [
            "Harald",
            "Olav",
            "Haakon",
            "Karl",
            "Gustav",
            "Louis",
            "Elizabeth",
            "Henrik",
            "Fredrik",
            "Christian",
            "Magnus",
            "Sverre",
            "Eirik",
            "Inge",
            "Sigurd",
            "Pave",
            "Kong",
            "Dronning",
        ]
        monarch_prefix = pynini.union(*monarch_names)
        monarch_graph = (
            monarch_prefix
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + roman_ordinals
        )

        # 2. Keyed structural labels: Kapittel, del, bind, akt, scene, bok, sang, volum
        struct_labels = [
            ("Kapittel", "Kapittel"),
            ("kapittel", "kapittel"),
            ("Del", "Del"),
            ("del", "del"),
            ("Bind", "Bind"),
            ("bind", "bind"),
            ("Akt", "Akt"),
            ("akt", "akt"),
            ("Scene", "Scene"),
            ("scene", "scene"),
            ("Bok", "Bok"),
            ("bok", "bok"),
            ("Volum", "Volum"),
            ("volum", "volum"),
            ("Vol.", "volum"),
            ("vol.", "volum"),
            ("Århundre", "Århundre"),
            ("århundre", "århundre"),
            ("klasse", "klasse"),
            ("Klasse", "Klasse"),
        ]
        struct_prefix = pynini.string_map(struct_labels)
        struct_graph = (
            struct_prefix
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + roman_cardinals
        )

        century_graph = (
            pynini.closure(pynini.accep("det "), 0, 1)
            + roman_ordinals + pynini.closure(pynutil.delete("."), 0, 1)
            + pynini.accep(" århundre")
        )

        all_roman = (
            monarch_graph
            | struct_graph
            | century_graph
        )

        self.graph = all_roman.optimize()
        self.fst = self.graph
