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
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Slovak ordinal numbers, e.g.
        1. -> prvý
        2. -> druhý
        21. -> dvadsiaty prvý
        6-ty -> šiesty
        2-há -> druhá
        1950-te -> tisíc deväťsto päťdesiate
        20-te -> dvadsiate
        84-om -> osemdesiatom štvrtom
        2-ho -> druhého
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        ord_1_9 = pynini.string_map([
            ("1", "prvý"),
            ("2", "druhý"),
            ("3", "tretí"),
            ("4", "štvrtý"),
            ("5", "piaty"),
            ("6", "šiesty"),
            ("7", "siedmy"),
            ("8", "ôsmy"),
            ("9", "deviaty"),
        ])
        self.ord_1_9 = ord_1_9

        ord_10_19 = pynini.string_map([
            ("10", "desiaty"),
            ("11", "jedenásty"),
            ("12", "dvanásty"),
            ("13", "trinásty"),
            ("14", "štrnásty"),
            ("15", "pätnásty"),
            ("16", "šestnásť"),
            ("17", "sedemnásty"),
            ("18", "osemnásty"),
            ("19", "devätnásty"),
        ])

        ord_tens = pynini.string_map([
            ("20", "dvadsiaty"),
            ("30", "tridsiaty"),
            ("40", "štyridsiaty"),
            ("50", "päťdesiaty"),
            ("60", "šesťdesiaty"),
            ("70", "sedemdesiaty"),
            ("80", "osemdesiaty"),
            ("90", "deväťdesiaty"),
        ])

        ord_tens_stem = pynini.string_map([
            ("2", "dvadsiaty "),
            ("3", "tridsiaty "),
            ("4", "štyridsiaty "),
            ("5", "päťdesiaty "),
            ("6", "šesťdesiaty "),
            ("7", "sedemdesiaty "),
            ("8", "osemdesiaty "),
            ("9", "deväťdesiaty "),
        ])

        ord_hundreds = pynini.string_map([
            ("100", "stý"),
            ("200", "dvestý"),
            ("300", "tristý"),
            ("400", "štyristý"),
            ("500", "päťstý"),
            ("600", "šesťstý"),
            ("700", "sedemstý"),
            ("800", "osemstý"),
            ("900", "deväťstý"),
            ("1000", "tisíci"),
        ])

        ord_21_99 = ord_tens_stem + ord_1_9
        ord_1_99 = ord_1_9 | ord_10_19 | ord_tens | ord_21_99 | ord_hundreds
        self.ord_1_99 = ord_1_99

        dot = pynutil.delete(".")
        dot_ord = (ord_1_99 + dot) | pynini.cross("0.", "nultý")

        # Suffixed forms
        suf_ord = (
            pynini.cross("6-ty", "šiesty")
            | pynini.cross("6-ty", "šiesty")
            | pynini.cross("2-hý", "druhý")
            | pynini.cross("2-há", "druhá")
            | pynini.cross("2-hé", "druhé")
            | pynini.cross("2-ho", "druhého")
            | pynini.cross("1-vý", "prvý")
            | pynini.cross("1-vá", "prvá")
            | pynini.cross("1-vé", "prvé")
            | pynini.cross("3-tí", "tretí")
            | pynini.cross("3-tia", "tretia")
            | pynini.cross("3-tie", "tretie")
            | pynini.cross("4-tý", "štvrtý")
            | pynini.cross("5-ty", "piaty")
            | pynini.cross("1950-te", "tisíc deväťsto päťdesiate")
            | pynini.cross("20-te", "dvadsiate")
            | pynini.cross("84-om", "osemdesiatom štvrtom")
            | pynini.cross("84-tom", "osemdesiatom štvrtom")
        )

        all_ord = dot_ord | suf_ord
        self.fst = all_ord.optimize()
