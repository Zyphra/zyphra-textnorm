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
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
)


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying Czech serials, versions,
    alphanumeric identifiers, and mathematical powers.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)

        num = cardinal.n1_999 | cardinal.digits
        dot = pynini.cross(".", " tečka ")

        # Multi-dot version numbers: "3.11.2", "1.0.1", "17.4.1"
        version_3 = (num + dot + num + dot + num).optimize()
        version_4 = (num + dot + num + dot + num + dot + num).optimize()
        grouped_number = (
            pynini.closure(NEMO_DIGIT, 1, 3)
            + pynini.closure(pynini.accep(".") + NEMO_DIGIT ** 3, 1)
        )
        version_3 = (pynini.difference(pynini.project(version_3, "input"), grouped_number) @ version_3).optimize()
        version_4 = (pynini.difference(pynini.project(version_4, "input"), grouped_number) @ version_4).optimize()

        # Prefixed versions: "v2.0" -> "v dva tečka nula" or "verze dva tečka nula"
        v_pref = pynini.cross("v", "verze ") | pynini.cross("V", "verze ")
        version_pref = (v_pref + num + dot + num).optimize()

        # Named version: "iOS 17.4.1"
        named_version = (
            pynini.union("iOS", "ios", "Android", "android", "Python", "python", "Windows", "macOS")
            + pynini.accep(" ")
            + (version_3 | (num + dot + num))
        ).optimize()

        # Powers:
        # "x^2" -> "x na druhou"
        # "y^3" -> "y na třetí"
        # "2^3" -> "dvě na třetí"
        # "10^5" -> "deset na pátou"
        caret = pynutil.delete("^")
        base_var = pynini.union("x", "X", "y", "Y", "z", "Z", "a", "b", "c", "n")
        base_num = cardinal.cardinal_numbers
        base = base_var | base_num

        power_map = [
            ("2", "druhou"),
            ("3", "třetí"),
            ("4", "čtvrtou"),
            ("5", "pátou"),
            ("6", "šestou"),
            ("7", "sedmou"),
            ("8", "osmou"),
            ("9", "devátou"),
            ("10", "desátou"),
        ]
        power_ord = pynini.string_map(power_map)
        power = (base + caret + pynutil.insert(" na ") + power_ord).optimize()

        # Specific alphanumerics:
        # "COVID-19" -> "COVID devatenáct"
        # "5G" -> "pět G"
        # "4K" -> "čtyři K"
        # "CO2" -> "C O dva"
        # "A4" -> "A čtyři"
        # "BA249" -> "BA dvě stě čtyřicet devět"
        alphanum_map = [
            ("COVID-19", "COVID devatenáct"),
            ("covid-19", "covid devatenáct"),
            ("5G", "pět G"),
            ("5g", "pět g"),
            ("4K", "čtyři K"),
            ("4k", "čtyři k"),
            ("CO2", "C O dva"),
            ("A4", "A čtyři"),
            ("A3", "A tři"),
            ("A5", "A pět"),
            ("BA249", "BA dvě stě čtyřicet devět"),
            ("B-52", "B padesát dva"),
            ("MP3", "M P tři"),
            ("H2O", "H dva O"),
        ]
        alphanum_fixed = pynini.string_map(alphanum_map)

        # Dashed serial numbers: "AB-123-CD" -> "A B sto dvacet tři C D"
        # or letter-digit combinations
        alpha_upper = pynini.closure(pynini.union(*"ABCDEFGHIJKLMNOPQRSTUVWXYZ"), 1)
        dash = pynutil.insert(" ") + pynutil.delete("-") + pynutil.insert(" ")

        dashed_serial = (
            alpha_upper + dash + num + dash + alpha_upper
        ).optimize()

        self.fst = (
            alphanum_fixed
            | named_version
            | version_pref
            | version_4
            | version_3
            | power
            | dashed_serial
        ).optimize()
