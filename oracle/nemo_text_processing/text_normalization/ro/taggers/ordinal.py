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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst
from nemo_text_processing.text_normalization.ro.graph_utils import to_name_token
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst


def _generate_ordinal_maps():
    ord_masc_1_19 = {
        1: "primul", 2: "al doilea", 3: "al treilea", 4: "al patrulea",
        5: "al cincilea", 6: "al șaselea", 7: "al șaptelea", 8: "al optulea",
        9: "al nouălea", 10: "al zecelea", 11: "al unsprezecelea", 12: "al doisprezecelea",
        13: "al treisprezecelea", 14: "al paisprezecelea", 15: "al cincisprezecelea",
        16: "al șaisprezecelea", 17: "al șaptesprezecelea", 18: "al optsprezecelea",
        19: "al nouăsprezecelea",
    }
    ord_fem_1_19 = {
        1: "prima", 2: "a doua", 3: "a treia", 4: "a patra",
        5: "a cincea", 6: "a șasea", 7: "a șaptea", 8: "a opta",
        9: "a noua", 10: "a zecea", 11: "a unsprezecea", 12: "a douăsprezecea",
        13: "a treisprezecea", 14: "a paisprezecea", 15: "a cincisprezecea",
        16: "a șaisprezecea", 17: "a șaptesprezecea", 18: "a optsprezecea",
        19: "a nouăsprezecea",
    }
    ties_ord_masc = {
        20: "al douăzecilea", 30: "al treizecilea", 40: "al patruzecilea",
        50: "al cincizecilea", 60: "al șaizecilea", 70: "al șaptezecilea",
        80: "al optzecilea", 90: "al nouăzecilea", 100: "al o sutălea",
        1000: "al o mielea",
    }
    ties_ord_fem = {
        20: "a douăzecea", 30: "a treizecea", 40: "a patruzecea",
        50: "a cincizecea", 60: "a șaizecea", 70: "a șaptezecea",
        80: "a optzecea", 90: "a nouăzecea", 100: "a o suta",
        1000: "a o mia",
    }
    ties_base = {
        20: "douăzeci", 30: "treizeci", 40: "patruzeci", 50: "cincizeci",
        60: "șaizeci", 70: "șaptezeci", 80: "optzeci", 90: "nouăzeci",
    }
    u_masc = {
        1: "unulea", 2: "doilea", 3: "treilea", 4: "patrulea", 5: "cincilea",
        6: "șaselea", 7: "șaptelea", 8: "optulea", 9: "nouălea",
    }
    u_fem = {
        1: "una", 2: "doua", 3: "treia", 4: "patra", 5: "cincea",
        6: "șasea", 7: "șaptea", 8: "opta", 9: "noua",
    }

    masc_map = {}
    fem_map = {}

    for n in range(1, 1001):
        if n in ord_masc_1_19:
            masc_map[n] = ord_masc_1_19[n]
            fem_map[n] = ord_fem_1_19[n]
        elif n in ties_ord_masc:
            masc_map[n] = ties_ord_masc[n]
            fem_map[n] = ties_ord_fem[n]
        elif 21 <= n <= 99:
            d = (n // 10) * 10
            u = n % 10
            masc_map[n] = f"al {ties_base[d]} și {u_masc[u]}"
            fem_map[n] = f"a {ties_base[d]} și {u_fem[u]}"
        elif 101 <= n <= 199:
            rem = n % 100
            if rem in ord_masc_1_19:
                masc_map[n] = f"al o sută {ord_masc_1_19[rem].removeprefix('al ')}"
                fem_map[n] = f"a o sută {ord_fem_1_19[rem].removeprefix('a ')}"
            elif rem in ties_ord_masc:
                masc_map[n] = f"al o sută {ties_ord_masc[rem].removeprefix('al ')}"
                fem_map[n] = f"a o sută {ties_ord_fem[rem].removeprefix('a ')}"
            else:
                d = (rem // 10) * 10
                u = rem % 10
                masc_map[n] = f"al o sută {ties_base[d]} și {u_masc[u]}"
                fem_map[n] = f"a o sută {ties_base[d]} și {u_fem[u]}"
        else:
            masc_map[n] = f"al {n}-lea"
            fem_map[n] = f"a {n}-a"

    return masc_map, fem_map


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Romanian ordinals, e.g.
        "1-ul" -> tokens { name: "primul" }
        "al 2-lea" -> tokens { name: "al doilea" }
        "2-lea" -> tokens { name: "al doilea" }
        "1-a" -> tokens { name: "prima" }
        "a 2-a" -> tokens { name: "a doua" }
        "2-a" -> tokens { name: "a doua" }
        "1°" -> tokens { name: "primul" }
        "2°" -> tokens { name: "al doilea" }
        "1ª" -> tokens { name: "prima" }
        "2ª" -> tokens { name: "a doua" }
        "al 21-lea" -> tokens { name: "al douăzeci și unulea" }
        "21ª" -> tokens { name: "a douăzeci și una" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        masc_map, fem_map = _generate_ordinal_maps()

        masc_pairs = []
        fem_pairs = []

        opt_al = pynini.closure(pynini.union("al ", "Al "), 0, 1)
        opt_a = pynini.closure(pynini.union("a ", "A "), 0, 1)
        opt_il = pynini.closure(pynini.union("il ", "Il "), 0, 1)

        # 1-ul, 1-lea -> primul
        masc_pairs.extend([
            ("1-ul", "primul"),
            ("1-lea", "primul"),
            ("1°", "primul"),
            ("1º", "primul"),
        ])
        fem_pairs.extend([
            ("1-a", "prima"),
            ("1ª", "prima"),
        ])

        for n in range(2, 1001):
            m_spoken = masc_map[n]
            f_spoken = fem_map[n]

            # Written forms with suffixes: 2-lea, al 2-lea
            masc_pairs.extend([
                (f"{n}-lea", m_spoken),
                (f"al {n}-lea", m_spoken),
                (f"Al {n}-lea", m_spoken),
                (f"{n}°", m_spoken),
                (f"{n}º", m_spoken),
                (f"al {n}°", m_spoken),
                (f"al {n}º", m_spoken),
                (f"Al {n}°", m_spoken),
                (f"Al {n}º", m_spoken),
            ])

            # Written forms feminine: 2-a, a 2-a
            fem_pairs.extend([
                (f"{n}-a", f_spoken),
                (f"a {n}-a", f_spoken),
                (f"A {n}-a", f_spoken),
                (f"{n}ª", f_spoken),
                (f"a {n}ª", f_spoken),
                (f"A {n}ª", f_spoken),
            ])

        masc_graph = (opt_il + pynini.string_map(masc_pairs)).optimize()
        fem_graph = pynini.string_map(fem_pairs).optimize()

        self.ordinal_no_tokens = (masc_graph | fem_graph).optimize()

        self.fst = to_name_token(self.ordinal_no_tokens)
