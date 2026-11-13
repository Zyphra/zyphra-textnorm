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

import os
import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)
from nemo_text_processing.text_normalization.ro.graph_utils import to_name_token


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Romanian abbreviations and standalone symbols, e.g.
        "Dr. Popescu" -> tokens { name: "doctor" } tokens { name: "Popescu" }
        "Nr. 5" -> tokens { name: "numărul" } tokens { name: "cinci" }
        "etc." -> tokens { name: "și așa mai departe" }
        "A & B" -> tokens { name: "A" } tokens { name: "și" } tokens { name: "B" }
        "© 2024" -> tokens { name: "copyright" } tokens { name: "două mii douăzeci și patru" }
        "§ 12" -> tokens { name: "paragraful" } tokens { name: "doisprezece" }
    """

    def __init__(
        self,
        input_case: str = "cased",
        deterministic: bool = True,
        input_file: str = None,
    ):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        abbreviations = pynini.string_map([
            # Titles
            ("Dr.", "doctor"),
            ("Dr", "doctor"),
            ("dr.", "doctor"),
            ("Dna.", "doamna"),
            ("Dna", "doamna"),
            ("D-na", "doamna"),
            ("dna.", "doamna"),
            ("Dl.", "domnul"),
            ("Dl", "domnul"),
            ("D-l", "domnul"),
            ("dl.", "domnul"),
            ("Dra.", "domnișoara"),
            ("Dra", "domnișoara"),
            ("D-ra", "domnișoara"),
            ("dra.", "domnișoara"),
            ("Prof.", "profesor"),
            ("prof.", "profesor"),
            ("Prof", "profesor"),
            ("Ing.", "inginer"),
            ("ing.", "inginer"),
            ("Av.", "avocat"),
            ("av.", "avocat"),
            ("avv.", "avocat"),
            # Numbers & structures
            ("Nr.", "numărul"),
            ("nr.", "numărul"),
            ("Nr", "numărul"),
            ("nr", "numărul"),
            ("No.", "numărul"),
            ("no.", "numărul"),
            ("n.", "numărul"),
            ("etc.", "și așa mai departe"),
            ("etc", "și așa mai departe"),
            ("str.", "strada"),
            ("Str.", "strada"),
            ("bd.", "bulevardul"),
            ("Bd.", "bulevardul"),
            ("b-dul", "bulevardul"),
            ("B-dul", "bulevardul"),
            ("ap.", "apartamentul"),
            ("Ap.", "apartamentul"),
            ("tel.", "telefon"),
            ("Tel.", "telefon"),
            ("pag.", "pagina"),
            ("vol.", "volumul"),
            ("cap.", "capitolul"),
            ("art.", "articolul"),
            ("alin.", "alineatul"),
            ("sf.", "sfântul"),
            ("Sf.", "sfântul"),
        ])

        symbols = pynini.string_map([
            ("&", "și"),
            ("©", "copyright"),
            ("§", "paragraful"),
            ("®", "marcă înregistrată"),
            ("™", "marcă comercială"),
            ("~", "aproximativ"),
            ("±", "plus-minus"),
            ("=", "egal"),
        ])

        composite = abbreviations | symbols

        if input_file and os.path.exists(input_file):
            custom_map = pynini.string_file(input_file)
            composite = composite | custom_map

        self.fst = to_name_token(composite.optimize())
