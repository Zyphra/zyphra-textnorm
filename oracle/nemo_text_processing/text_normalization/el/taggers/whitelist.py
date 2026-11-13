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

from nemo_text_processing.text_normalization.el.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.el.taggers.cardinal import CardinalFst


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Greek abbreviations, serial alphanumerics, math expressions and symbols:
        "π.χ." -> παραδείγματος χάριν
        "δηλ." -> δηλαδή
        "κ.λπ." -> και λοιπά
        "κ." -> κύριος
        "κα." -> κυρία
        "Δρ. Νικολάου" -> γιατρός Νικολάου
        "Dr. Smith" -> Dr. Smith / γιατρός Smith
        "No. 5" / "Νο. 5" -> νούμερο πέντε
        "&" -> και
        "© 2024" -> πνευματικά δικαιώματα δύο χιλιάδες είκοσι τέσσερα
        "§ 12" -> παράγραφος δώδεκα
        "#5" -> νούμερο πέντε
        "iOS 17.4.1" -> iOS δεκαεπτά τελεία τέσσερα τελεία ένα
        "5G" -> πέντε G
        "4K" -> τέσσερα K
        "CO2" -> CO δύο
        "AB-123-CD" -> AB εκατόν είκοσι τρία CD
        "x^2" -> x στο τετράγωνο
        "y^3" -> y στον κύβο
        "2^3" -> δύο στην τρίτη
        "5+3" -> πέντε συν τρία
        "5 = 5" -> πέντε ίσον πέντε
        "3:1" -> τρία προς ένα
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        pure_cardinal = cardinal.pure_cardinal
        digit_trans = cardinal.digit_trans

        # 1. Abbreviations
        abbrevs = pynini.string_map(
            [
                ("π.χ.", "παραδείγματος χάριν"),
                ("π.χ", "παραδείγματος χάριν"),
                ("δηλ.", "δηλαδή"),
                ("δηλ", "δηλαδή"),
                ("κ.λπ.", "και λοιπά"),
                ("κλπ.", "και λοιπά"),
                ("κ.λ.π.", "και λοιπά"),
                ("κλπ", "και λοιπά"),
                ("κ.α.", "και άλλα"),
                ("κ.ά.", "και άλλα"),
                ("κ.", "κύριος"),
                ("κα.", "κυρία"),
                ("κα", "κυρία"),
                ("δις.", "δεσποινίς"),
                ("δις", "δεσποινίς"),
                ("σελ.", "σελίδα"),
                ("κεφ.", "κεφάλαιο"),
                ("αρ.", "αριθμός"),
                ("αριθ.", "αριθμός"),
                ("τηλ.", "τηλέφωνο"),
                ("αι.", "αιώνας"),
                ("etc.", "και τα λοιπά"),
            ]
        )

        # Contextual titles: "Δρ. Παπαδόπουλος", "Dr. Smith"
        titles = pynini.string_map(
            [
                ("Δρ.", "γιατρός"),
                ("Δρ", "γιατρός"),
                ("δρ.", "γιατρός"),
                ("δρ", "γιατρός"),
                ("Dr.", "γιατρός"),
                ("Dr", "γιατρός"),
            ]
        )
        title_phrase = titles + pynutil.delete(" ") + pynutil.insert(" ") + pynini.closure(NEMO_ALPHA, 1)

        # Number abbreviations before number: "No. 5", "Νο. 5", "Νο 5", "no. 5"
        no_prefix = pynini.string_map(
            [
                ("No.", "νούμερο"),
                ("No", "νούμερο"),
                ("no.", "νούμερο"),
                ("no", "νούμερο"),
                ("Νο.", "νούμερο"),
                ("Νο", "νούμερο"),
                ("νο.", "νούμερο"),
                ("νο", "νούμερο"),
                ("#", "νούμερο "),
            ]
        )
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        no_phrase = no_prefix + opt_space + pynutil.insert(" ") + pure_cardinal

        # 2. Symbols: "&", "©", "§"
        ampersand = pynini.cross("&", "και")
        copyright_sym = pynini.cross("©", "πνευματικά δικαιώματα")
        section_sym = pynini.cross("§", "παράγραφος")

        symbols = (
            ampersand
            | (copyright_sym + pynutil.delete(" ") + pynutil.insert(" ") + pure_cardinal)
            | (section_sym + pynutil.delete(" ") + pynutil.insert(" ") + pure_cardinal)
            | copyright_sym
            | section_sym
        )

        # 3. Alphanumerics & Serials:
        # "iOS 17.4.1" -> "iOS δεκαεπτά τελεία τέσσερα τελεία ένα"
        version_num = pure_cardinal + pynini.closure(pynini.cross(".", " τελεία ") + pure_cardinal, 2, 4)
        ver_prefix = pynini.string_map(
            [
                ("iOS", "iOS"),
                ("Android", "Android"),
                ("Windows", "Windows"),
                ("v", "έκδοση"),
                ("v.", "έκδοση"),
            ]
        )
        ver_phrase = ver_prefix + pynutil.delete(" ") + pynutil.insert(" ") + version_num

        # "5G" -> "πέντε G", "4K" -> "τέσσερα K"
        g_phrase = pure_cardinal + pynutil.delete(pynini.closure(" ", 0, 1)) + pynini.cross("G", " G")
        k_phrase = pure_cardinal + pynutil.delete(pynini.closure(" ", 0, 1)) + pynini.cross("K", " K")

        # "CO2" -> "CO δύο"
        co2_phrase = pynini.cross("CO2", "CO δύο")

        # Serial dash: "AB-123-CD" -> "AB εκατόν είκοσι τρία CD"
        alpha_chunk = pynini.closure(NEMO_ALPHA, 1, 3)
        serial_dash = (
            alpha_chunk
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + pure_cardinal
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + alpha_chunk
        )

        # 4. Powers & Exponents:
        # "x^2" -> "x στο τετράγωνο", "y^3" -> "y στον κύβο", "2^3" -> "δύο στην τρίτη"
        var_power = (
            pynini.closure(NEMO_ALPHA, 1)
            + (pynini.cross("^2", " στο τετράγωνο") | pynini.cross("^3", " στον κύβο"))
        )
        num_power = (
            pure_cardinal
            + pynini.cross("^", " στην ")
            + pynini.string_map(
                [
                    ("2", "δευτέρα"),
                    ("3", "τρίτη"),
                    ("4", "τετάρτη"),
                    ("5", "πέμπτη"),
                    ("6", "έκτη"),
                    ("7", "εβδόμη"),
                    ("8", "ογδόη"),
                    ("9", "ενάτη"),
                    ("10", "δεκάτη"),
                ]
            )
        )
        powers = var_power | num_power

        # 5. Math expressions:
        # "5+3" -> "πέντε συν τρία"
        # "5 = 5" -> "πέντε ίσον πέντε"
        # "3:1" / "3-1" (ratios / score) -> "τρία προς ένα"
        math_plus = pure_cardinal + pynini.cross("+", " συν ") + pure_cardinal
        math_equals = pure_cardinal + pynini.cross(pynini.union(" = ", "="), " ίσον ") + pure_cardinal
        ratio_graph = pure_cardinal + pynini.cross(pynini.union(":", " προς "), " προς ") + pure_cardinal

        math_graphs = math_plus | math_equals | pynutil.add_weight(ratio_graph, 1.5)

        all_whitelist = (
            abbrevs
            | title_phrase
            | titles
            | no_phrase
            | symbols
            | ver_phrase
            | g_phrase
            | k_phrase
            | co2_phrase
            | serial_dash
            | powers
            | math_graphs
        ).optimize()

        self.fst = all_whitelist
