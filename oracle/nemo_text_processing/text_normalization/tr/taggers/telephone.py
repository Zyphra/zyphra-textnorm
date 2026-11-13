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
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst


class TelephoneFst(GraphFst):
    """
    Finite state transducer for telephone numbers in Turkish:
    - tel. 112 -> telefon bir bir iki
    - tel.: 114 14 -> telefon yüz on dört on dört
    - tfn. 08-789 52 25 -> telefon sıfır sekiz, yedi yüz seksen dokuz elli iki yirmi beş
    - +46 (8) 790 7559 -> plus kırk altı sekiz, yedi yüz doksan yetmiş beş elli dokuz
    - +90 (212) 123 45 67 -> artı doksan iki yüz on iki yüz yirmi üç kırk beş altmış yedi
    - 08 790 7559 ankn. 32 -> ... anknytning / dahili otuz iki
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        digit_map = pynini.string_map([
            ("0", "sıfır"),
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])

        # Chunks of numbers can be read as cardinals (2-4 digits) or digit-by-digit
        num_chunk = (
            (pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal.positive_cardinals)
            | (pynini.cross("0", "sıfır ") + (pynini.closure(NEMO_DIGIT, 1, 3) @ cardinal.positive_cardinals))
            | pynutil.add_weight(digit_map + pynini.closure(pynutil.insert(" ") + digit_map, 1, 3), 0.5)
        ).optimize()

        # Telephone prefixes
        prefix = pynini.string_map([
            ("tel. ", "telefon "),
            ("tel.: ", "telefon "),
            ("tel: ", "telefon "),
            ("tfn. ", "telefon "),
            ("telefon: ", "telefon "),
            ("telefon ", "telefon "),
            ("GSM: ", "g s m "),
            ("gsm: ", "g s m "),
        ])

        # Country code: +90, +46, +1 (native artı in Turkish)
        country_code = (
            pynini.cross("+", "artı ")
            + (pynini.closure(NEMO_DIGIT, 1, 3) @ cardinal.positive_cardinals)
            + pynutil.insert(" ")
            + pynini.closure(pynutil.delete(" "), 0, 1)
        )

        # Area code: (212), (8), 0212, 08
        area_code_paren = (
            pynutil.delete("(")
            + num_chunk
            + pynutil.delete(")")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(" ")
        )

        # Separators between number chunks: space, hyphen
        chunk_sep = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynini.closure(pynutil.delete(pynini.union("-", " ")), 1, 2)
            + pynutil.insert(" ")
        )

        # Number chunks sequence (2 to 5 chunks)
        body = num_chunk + pynini.closure(chunk_sep + num_chunk, 1, 5)

        # Extension: ankn. 32, ankn 32, dahili 32, dahili: 32, ext. 32
        ext_prefix = pynini.string_map([
            (" ankn. ", " anknytning "),
            (" ankn ", " anknytning "),
            (" dahili: ", " dahili "),
            (" dahili ", " dahili "),
            (" ext. ", " dahili "),
            (" ext ", " dahili "),
        ])
        extension = ext_prefix + (pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal.positive_cardinals)

        # Full phone graphs
        full_with_prefix = (
            prefix
            + pynini.closure(country_code, 0, 1)
            + pynini.closure(area_code_paren, 0, 1)
            + body
            + pynini.closure(extension, 0, 1)
        )

        full_with_country = (
            (country_code)
            + pynini.closure(area_code_paren, 0, 1)
            + body
            + pynini.closure(extension, 0, 1)
        )

        full_with_paren = (
            area_code_paren
            + body
            + pynini.closure(extension, 0, 1)
        )

        full_with_ext = (
            body
            + extension
        )

        # Special 3-digit emergency numbers after prefix: tel. 112 -> telefon bir bir iki
        emergency = prefix + (digit_map + pynutil.insert(" ") + digit_map + pynutil.insert(" ") + digit_map)

        all_phone = (
            full_with_prefix
            | full_with_country
            | full_with_paren
            | full_with_ext
            | emergency
        ).optimize()
        self.all_phone = all_phone

        self.fst = (pynutil.insert('name: "') + convert_space(all_phone) + pynutil.insert('"')).optimize()
