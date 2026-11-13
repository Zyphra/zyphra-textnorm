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


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying Greek Roman numerals in keyed context:
        "Κεφάλαιο IV" -> Κεφάλαιο τέσσερα
        "Louis XIV" -> Louis δέκατος τέταρτος
        "Λουδοβίκος XIV" -> Λουδοβίκος δέκατος τέταρτος
        "XXI αιώνας" -> εικοστός πρώτος αιώνας
        "αιώνας XXI" -> αιώνας εικοστός πρώτος
        "Παύλος II" -> Παύλος δεύτερος

    Safety: Non-numeral letters like "XL", "MIX", "CD", "Section C" remain untransduced.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        # Roman to cardinal (e.g. for chapters/sections)
        roman_to_card = pynini.string_map(
            [
                ("I", "ένα"), ("II", "δύο"), ("III", "τρία"), ("IV", "τέσσερα"), ("V", "πέντε"),
                ("VI", "έξι"), ("VII", "επτά"), ("VIII", "οκτώ"), ("IX", "εννέα"), ("X", "δέκα"),
                ("XI", "έντεκα"), ("XII", "δώδεκα"), ("XIII", "δεκατρία"), ("XIV", "δεκατέσσερα"),
                ("XV", "δεκαπέντε"), ("XVI", "δεκαέξι"), ("XVII", "δεκαεπτά"), ("XVIII", "δεκαοκτώ"),
                ("XIX", "δεκαεννέα"), ("XX", "είκοσι"), ("XXI", "είκοσι ένα"),
            ]
        )

        # Roman to ordinal masculine (e.g. for monarchs/popes and centuries)
        roman_to_ord_m = pynini.string_map(
            [
                ("I", "πρώτος"), ("II", "δεύτερος"), ("III", "τρίτος"), ("IV", "τέταρτος"),
                ("V", "πέμπτος"), ("VI", "έκτος"), ("VII", "έβδομος"), ("VIII", "όγδοος"),
                ("IX", "ένατος"), ("X", "δέκατος"), ("XI", "ενδέκατος"), ("XII", "δωδέκατος"),
                ("XIII", "δέκατος τρίτος"), ("XIV", "δέκατος τέταρτος"), ("XV", "δέκατος πέμπτος"),
                ("XVI", "δέκατος έκτος"), ("XVII", "δέκατος έβδομος"), ("XVIII", "δέκατος όγδοος"),
                ("XIX", "δέκατος ένατος"), ("XX", "εικοστός"), ("XXI", "εικοστός πρώτος"),
            ]
        )

        # Greek numeral letters with keraia (e.g. Β΄, ΙΔ΄, ΚΑ΄)
        keraia = pynini.union("΄", "'", "’")
        greek_num_to_ord = pynini.string_map(
            [
                ("Α", "πρώτος"), ("Β", "δεύτερος"), ("Γ", "τρίτος"), ("Δ", "τέταρτος"),
                ("Ε", "πέμπτος"), ("ΣΤ", "έκτος"), ("Ζ", "έβδομος"), ("Η", "όγδοος"),
                ("Θ", "ένατος"), ("Ι", "δέκατος"), ("ΙΑ", "ενδέκατος"), ("ΙΒ", "δωδέκατος"),
                ("ΙΓ", "δέκατος τρίτος"), ("ΙΔ", "δέκατος τέταρτος"), ("ΙΕ", "δέκατος πέμπτος"),
                ("ΙΣΤ", "δέκατος έκτος"), ("ΙΖ", "δέκατος έβδομος"), ("ΙΗ", "δέκατος όγδοος"),
                ("ΙΘ", "δέκατος ένατος"), ("Κ", "εικοστός"), ("ΚΑ", "εικοστός πρώτος"),
            ]
        ) + pynutil.delete(keraia)

        monarch_names = pynini.string_map(
            [
                ("Louis", "Louis"),
                ("Λουδοβίκος", "Λουδοβίκος"),
                ("Παύλος", "Παύλος"),
                ("Ιωάννης Παύλος", "Ιωάννης Παύλος"),
                ("Βενέδικτος", "Βενέδικτος"),
                ("Κωνσταντίνος", "Κωνσταντίνος"),
                ("Γεώργιος", "Γεώργιος"),
                ("Αλέξανδρος", "Αλέξανδρος"),
                ("Φίλιππος", "Φίλιππος"),
                ("Ελισάβετ", "Ελισάβετ"),
                ("Ναπολέων", "Ναπολέων"),
                ("Ερρίκος", "Ερρίκος"),
                ("Κάρολος", "Κάρολος"),
                ("Όθων", "Όθων"),
            ]
        )
        monarch_phrase = monarch_names + pynutil.insert(" ") + pynutil.delete(" ") + (roman_to_ord_m | greek_num_to_ord)

        # Chapter / Section context:
        chapter_prefix = pynini.string_map(
            [
                ("Κεφάλαιο", "Κεφάλαιο"),
                ("κεφάλαιο", "κεφάλαιο"),
                ("Κεφ.", "Κεφάλαιο"),
                ("κεφ.", "κεφάλαιο"),
                ("Μέρος", "Μέρος"),
                ("μέρος", "μέρος"),
                ("Τόμος", "Τόμος"),
                ("τόμος", "τόμος"),
                ("Τεύχος", "Τεύχος"),
                ("τεύχος", "τεύχος"),
                ("Πράξη", "Πράξη"),
                ("πράξη", "πράξη"),
                ("Σκηνή", "Σκηνή"),
                ("σκηνή", "σκηνή"),
            ]
        )
        chapter_phrase = chapter_prefix + pynutil.insert(" ") + pynutil.delete(" ") + (roman_to_card | pynutil.add_weight(roman_to_ord_m, 0.5))

        # Century context:
        # "XXI αιώνας" -> "εικοστός πρώτος αιώνας"
        # "αιώνας XXI" -> "αιώνας εικοστός πρώτος"
        century_word = pynini.string_map(
            [
                ("αιώνας", "αιώνας"),
                ("αι.", "αιώνας"),
                ("αιώνα", "αιώνα"),
                ("αι", "αιώνας"),
                ("Αιώνας", "Αιώνας"),
            ]
        )
        century_pre = roman_to_ord_m + pynutil.insert(" ") + pynutil.delete(" ") + century_word
        century_post = century_word + pynutil.insert(" ") + pynutil.delete(" ") + roman_to_ord_m

        graph = (monarch_phrase | chapter_phrase | century_pre | century_post).optimize()
        self.fst = graph
