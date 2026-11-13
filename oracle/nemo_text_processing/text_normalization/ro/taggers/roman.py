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


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying contextual Roman numerals in Romanian, e.g.
        "Capitolul IV" -> tokens { name: "Capitolul patru" }
        "secolul XXI" -> tokens { name: "secolul douăzeci și unu" }
        "XXI secol" -> tokens { name: "al douăzeci și unulea secol" }
        "Papa Ioan Paul al II-lea" -> tokens { name: "Papa Ioan Paul al doilea" }
        "Carol I" -> tokens { name: "Carol întâi" }
        "clasa a IV-a" -> tokens { name: "clasa a patra" }
    Safety controls:
        Bare "XL", "MIX", "CD" without context are never converted to numbers.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        # Roman to cardinal masculine
        roman_to_cardinal = pynini.string_map([
            ("I", "unu"),
            ("II", "doi"),
            ("III", "trei"),
            ("IV", "patru"),
            ("V", "cinci"),
            ("VI", "șase"),
            ("VII", "șapte"),
            ("VIII", "opt"),
            ("IX", "nouă"),
            ("X", "zece"),
            ("XI", "unsprezece"),
            ("XII", "doisprezece"),
            ("XIII", "treisprezece"),
            ("XIV", "paisprezece"),
            ("XV", "cincisprezece"),
            ("XVI", "șaisprezece"),
            ("XVII", "șaptesprezece"),
            ("XVIII", "optsprezece"),
            ("XIX", "nouăsprezece"),
            ("XX", "douăzeci"),
            ("XXI", "douăzeci și unu"),
            ("XXII", "douăzeci și doi"),
            ("XXIII", "douăzeci și trei"),
            ("XXIV", "douăzeci și patru"),
            ("XXV", "douăzeci și cinci"),
            ("XXX", "treizeci"),
        ])

        # Roman to ordinal masculine
        roman_to_ord_masc = pynini.string_map([
            ("I", "primul"),
            ("II", "doilea"),
            ("III", "treilea"),
            ("IV", "patrulea"),
            ("V", "cincilea"),
            ("VI", "șaselea"),
            ("VII", "șaptelea"),
            ("VIII", "optulea"),
            ("IX", "nouălea"),
            ("X", "zecelea"),
            ("XI", "unsprezecelea"),
            ("XII", "doisprezecelea"),
            ("XIII", "treisprezecelea"),
            ("XIV", "paisprezecelea"),
            ("XV", "cincisprezecelea"),
            ("XVI", "șaisprezecelea"),
            ("XVII", "șaptesprezecelea"),
            ("XVIII", "optsprezecelea"),
            ("XIX", "nouăsprezecelea"),
            ("XX", "douăzecilea"),
            ("XXI", "douăzeci și unulea"),
            ("XXII", "douăzeci și doilea"),
        ])

        # Roman to ordinal feminine
        roman_to_ord_fem = pynini.string_map([
            ("I", "prima"),
            ("II", "doua"),
            ("III", "treia"),
            ("IV", "patra"),
            ("V", "cincea"),
            ("VI", "șasea"),
            ("VII", "șaptea"),
            ("VIII", "opta"),
            ("IX", "noua"),
            ("X", "zecea"),
            ("XI", "unsprezecea"),
            ("XII", "douăsprezecea"),
            ("XIII", "treisprezecea"),
            ("XIV", "paisprezecea"),
            ("XV", "cincisprezecea"),
            ("XVI", "șaisprezecea"),
            ("XVII", "șaptesprezecea"),
            ("XVIII", "optsprezecea"),
            ("XIX", "nouăsprezecea"),
            ("XX", "douăzecea"),
            ("XXI", "douăzeci și una"),
        ])

        # 1. Chapters, volumes, parts, articles:
        # "Capitolul IV" -> "Capitolul patru"
        # "Partea a II-a" -> "Partea a doua"
        chap_prefix = pynini.union(
            pynini.cross("Capitolul ", "Capitolul "),
            pynini.cross("capitolul ", "capitolul "),
            pynini.cross("Cap. ", "capitolul "),
            pynini.cross("cap. ", "capitolul "),
            pynini.cross("Volumul ", "Volumul "),
            pynini.cross("volumul ", "volumul "),
            pynini.cross("Vol. ", "volumul "),
            pynini.cross("vol. ", "volumul "),
            pynini.cross("Partea ", "Partea "),
            pynini.cross("partea ", "partea "),
            pynini.cross("Actul ", "Actul "),
            pynini.cross("actul ", "actul "),
        )
        chap_rule = chap_prefix + roman_to_cardinal

        # 2. Centuries:
        # "secolul XXI" -> "secolul douăzeci și unu"
        # "Secolul XXI" -> "Secolul douăzeci și unu"
        # "sec. XXI" -> "secolul douăzeci și unu"
        century_prefix = pynini.union(
            pynini.cross("secolul ", "secolul "),
            pynini.cross("Secolul ", "Secolul "),
            pynini.cross("sec. ", "secolul "),
            pynini.cross("Sec. ", "secolul "),
        )
        century_rule = century_prefix + roman_to_cardinal

        # "XXI secol" -> "al douăzeci și unulea secol"
        century_suffix = (
            pynutil.insert("al ")
            + roman_to_ord_masc
            + pynini.cross(" secol", " secol")
        )

        # 3. Monarchs & Popes:
        # "Papa Ioan Paul al II-lea" -> "Papa Ioan Paul al doilea"
        # "Carol I" -> "Carol întâi"
        # "Ludovic al XIV-lea" -> "Ludovic al paisprezecelea"
        monarch_names = pynini.union(
            "Carol", "Ferdinand", "Mihai", "Ioan", "Paul", "Ioan Paul",
            "Papa Ioan Paul", "Papa", "Benedict", "Gheorghe", "Alexandru",
            "Petru", "Ludovic", "Henric", "Filip", "Ștefan", "Mircea",
            "Vlad", "Regele", "Regina", "Elisabeta"
        )
        # Carol I -> Carol întâi
        monarch_first = (
            monarch_names
            + pynini.cross(" I", " întâi")
        )
        # With "al II-lea":
        monarch_with_al = (
            monarch_names
            + pynini.accep(" al ")
            + roman_to_ord_masc
            + pynutil.delete("-lea")
        )
        # With "a II-a" (female monarchs):
        fem_monarch_with_a = (
            monarch_names
            + pynini.accep(" a ")
            + roman_to_ord_fem
            + pynutil.delete("-a")
        )

        # 4. Classes:
        # "clasa a IV-a" -> "clasa a patra"
        # "clasa I" -> "clasa întâi"
        class_prefix = pynini.union("clasa ", "Clasa ")
        class_first = class_prefix + pynini.cross("I", "întâi")
        class_ord = (
            class_prefix
            + pynutil.delete("a ")
            + pynutil.insert("a ")
            + roman_to_ord_fem
            + pynutil.delete("-a")
        )

        composite = (
            chap_rule
            | century_rule
            | century_suffix
            | monarch_first
            | monarch_with_al
            | fem_monarch_with_a
            | class_first
            | class_ord
        ).optimize()

        self.fst = to_name_token(composite)
