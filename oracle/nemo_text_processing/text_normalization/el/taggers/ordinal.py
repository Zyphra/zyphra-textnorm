# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import GraphFst


def _build_ordinal_maps():
    """Builds ordinal inflection maps for 1-100 across genders and cases."""
    stems = {
        1: ("πρώτ", "ος", "η", "ο"),
        2: ("δεύτερ", "ος", "η", "ο"),
        3: ("τρίτ", "ος", "η", "ο"),
        4: ("τέταρτ", "ος", "η", "ο"),
        5: ("πέμπτ", "ος", "η", "ο"),
        6: ("έκτ", "ος", "η", "ο"),
        7: ("έβδομ", "ος", "η", "ο"),
        8: ("όγδο", "ος", "η", "ο"),
        9: ("ένατ", "ος", "η", "ο"),
        10: ("δέκατ", "ος", "η", "ο"),
        11: ("ενδέκατ", "ος", "η", "ο"),
        12: ("δωδέκατ", "ος", "η", "ο"),
    }
    tens = {
        20: ("εικοστ", "ός", "ή", "ό"),
        30: ("τριακοστ", "ός", "ή", "ό"),
        40: ("τεσσαρακοστ", "ός", "ή", "ό"),
        50: ("πεντηκοστ", "ός", "ή", "ό"),
        60: ("εξηκοστ", "ός", "ή", "ό"),
        70: ("εβδομηκοστ", "ός", "ή", "ό"),
        80: ("ογδοηκοστ", "ός", "ή", "ό"),
        90: ("ενενηκοστ", "ός", "ή", "ό"),
        100: ("εκατοστ", "ός", "ή", "ό"),
    }

    maps = {
        "os": [], "i": [], "o": [], "ou": [], "is": [], "oi": [], "es": [], "a": [], "on": [], "ous": []
    }

    for n in range(1, 101):
        if n in stems:
            stem, _, _, _ = stems[n]
            maps["os"].append((str(n), stem + "ος"))
            maps["i"].append((str(n), stem + "η"))
            maps["o"].append((str(n), stem + "ο"))
            maps["ou"].append((str(n), stem + "ου"))
            maps["is"].append((str(n), stem + "ης"))
            maps["oi"].append((str(n), stem + "οι"))
            maps["es"].append((str(n), stem + "ες"))
            maps["a"].append((str(n), stem + "α"))
            maps["on"].append((str(n), stem + "ων"))
            maps["ous"].append((str(n), stem + "ους"))
        elif 13 <= n <= 19:
            u = n - 10
            ustem = stems[u][0]
            maps["os"].append((str(n), f"δέκατος {ustem}ος"))
            maps["i"].append((str(n), f"δέκατη {ustem}η"))
            maps["o"].append((str(n), f"δέκατο {ustem}ο"))
            maps["ou"].append((str(n), f"δέκατου {ustem}ου"))
            maps["is"].append((str(n), f"δέκατης {ustem}ης"))
            maps["oi"].append((str(n), f"δέκατοι {ustem}οι"))
            maps["es"].append((str(n), f"δέκατες {ustem}ες"))
            maps["a"].append((str(n), f"δέκατα {ustem}α"))
            maps["on"].append((str(n), f"δέκατων {ustem}ων"))
            maps["ous"].append((str(n), f"δέκατους {ustem}ους"))
        elif n in tens:
            stem, _, _, _ = tens[n]
            maps["os"].append((str(n), stem + "ός"))
            maps["i"].append((str(n), stem + "ή"))
            maps["o"].append((str(n), stem + "ό"))
            maps["ou"].append((str(n), stem + "ού"))
            maps["is"].append((str(n), stem + "ής"))
            maps["oi"].append((str(n), stem + "οί"))
            maps["es"].append((str(n), stem + "ές"))
            maps["a"].append((str(n), stem + "ά"))
            maps["on"].append((str(n), stem + "ών"))
            maps["ous"].append((str(n), stem + "ούς"))
        else:
            t = (n // 10) * 10
            u = n % 10
            tstem = tens[t][0]
            ustem = stems[u][0]
            maps["os"].append((str(n), f"{tstem}ός {ustem}ος"))
            maps["i"].append((str(n), f"{tstem}ή {ustem}η"))
            maps["o"].append((str(n), f"{tstem}ό {ustem}ο"))
            maps["ou"].append((str(n), f"{tstem}ού {ustem}ου"))
            maps["is"].append((str(n), f"{tstem}ής {ustem}ης"))
            maps["oi"].append((str(n), f"{tstem}οί {ustem}οι"))
            maps["es"].append((str(n), f"{tstem}ές {ustem}ες"))
            maps["a"].append((str(n), f"{tstem}ά {ustem}α"))
            maps["on"].append((str(n), f"{tstem}ών {ustem}ων"))
            maps["ous"].append((str(n), f"{tstem}ούς {ustem}ους"))

    # Also add 1000 -> χιλιοστός
    maps["os"].append(("1000", "χιλιοστός"))
    maps["i"].append(("1000", "χιλιοστή"))
    maps["o"].append(("1000", "χιλιοστό"))

    return maps


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Greek ordinal numbers:
        "1ος" -> πρώτος
        "1η" -> πρώτη
        "1ο" -> πρώτο
        "1ου" -> πρώτου
        "1ης" -> πρώτης
        "1οι" -> πρώτοι
        "1ες" -> πρώτες
        "1α" -> πρώτα
        "21ος" -> εικοστός πρώτος
        "21η" -> εικοστή πρώτη
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        maps = _build_ordinal_maps()
        hyphen = pynini.closure(pynutil.delete("-"), 0, 1)

        graph_os = (pynini.string_map(maps["os"])) + hyphen + pynutil.delete("ος")
        graph_i = (pynini.string_map(maps["i"])) + hyphen + pynutil.delete("η")
        graph_o = (pynini.string_map(maps["o"])) + hyphen + pynutil.delete("ο")
        graph_ou = (pynini.string_map(maps["ou"])) + hyphen + pynutil.delete("ου")
        graph_is = (pynini.string_map(maps["is"])) + hyphen + pynutil.delete("ης")
        graph_oi = (pynini.string_map(maps["oi"])) + hyphen + pynutil.delete("οι")
        graph_es = (pynini.string_map(maps["es"])) + hyphen + pynutil.delete("ες")
        graph_a = (pynini.string_map(maps["a"])) + hyphen + pynutil.delete("α")
        graph_on = (pynini.string_map(maps["on"])) + hyphen + pynutil.delete("ων")
        graph_ous = (pynini.string_map(maps["ous"])) + hyphen + pynutil.delete("ους")

        all_ordinals = (
            graph_os
            | graph_i
            | graph_o
            | graph_ou
            | graph_is
            | graph_oi
            | graph_es
            | graph_a
            | graph_on
            | graph_ous
        ).optimize()

        self.fst = all_ordinals
