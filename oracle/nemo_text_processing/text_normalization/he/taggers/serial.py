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
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew serials, software versions,
    alphanumerics, and variable powers.
    e.g. iOS 17.4.1 -> iOS שבע עשרה נקודה ארבע נקודה אחת
         5G -> חמש ג'י
         4K -> ארבע קיי
         CO2 -> סי או שתיים
         AB-123-CD -> איי בי מאה עשרים ושלוש סי די
         x^2 -> איקס בריבוע
         y^3 -> וואי בשלישית
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)

        # Latin letters to Hebrew phonetics
        letter_map = [
            ("a", "איי"), ("A", "איי"),
            ("b", "בי"), ("B", "בי"),
            ("c", "סי"), ("C", "סי"),
            ("d", "די"), ("D", "די"),
            ("e", "אי"), ("E", "אי"),
            ("f", "אף"), ("F", "אף"),
            ("g", "ג'י"), ("G", "ג'י"),
            ("h", "אייץ'"), ("H", "אייץ'"),
            ("i", "איי"), ("I", "איי"),
            ("j", "ג'יי"), ("J", "ג'יי"),
            ("k", "קיי"), ("K", "קיי"),
            ("l", "אל"), ("L", "אל"),
            ("m", "אם"), ("M", "אם"),
            ("n", "אן"), ("N", "אן"),
            ("o", "או"), ("O", "או"),
            ("p", "פי"), ("P", "פי"),
            ("q", "קיו"), ("Q", "קיו"),
            ("r", "אר"), ("R", "אר"),
            ("s", "אס"), ("S", "אס"),
            ("t", "טי"), ("T", "טי"),
            ("u", "יו"), ("U", "יו"),
            ("v", "וי"), ("V", "וי"),
            ("w", "דבליו"), ("W", "דבליו"),
            ("x", "איקס"), ("X", "איקס"),
            ("y", "וואי"), ("Y", "וואי"),
            ("z", "זד"), ("Z", "זד"),
        ]
        letter_fst = pynini.string_map(letter_map)
        letters_spaced = letter_fst + pynini.closure(insert_space + letter_fst)

        # Digits and numbers
        num_f = cardinal.base_num_f
        dot = pynini.cross(".", " נקודה ")

        # ----------------- Multi-dot Versions -----------------
        # 17.4.1 -> שבע עשרה נקודה ארבע נקודה אחת
        # iOS 17.4.1 -> iOS שבע עשרה נקודה ארבע נקודה אחת
        version_core = num_f + dot + num_f + dot + num_f + pynini.closure(dot + num_f)
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        req_space = pynutil.delete(" ")

        version_lead = pynini.string_map([
            ("iOS", "iOS"),
            ("ios", "iOS"),
            ("v", "v"),
            ("v.", "v"),
            ("version", "version"),
            ("Android", "Android"),
            ("Windows", "Windows"),
            ("Python", "Python"),
        ])
        version_with_lead = version_lead + (req_space | opt_space) + pynutil.insert(" ") + version_core
        all_versions = pynutil.add_weight(version_with_lead, 0.9) | pynutil.add_weight(version_core, 0.95)

        # ----------------- Alphanumerics -----------------
        # 5G -> חמש ג'י
        # 4K -> ארבע קיי
        # CO2 -> סי או שתיים
        # AB-123-CD -> איי בי מאה עשרים ושלוש סי די
        alphanum_num_letter = num_f + opt_space + pynutil.insert(" ") + letters_spaced
        alphanum_letter_num = letters_spaced + opt_space + pynutil.insert(" ") + num_f

        dash = pynutil.delete(pynini.union("-", "–", "—", "־")) + pynutil.insert(" ")
        serial_dash = (
            letters_spaced
            + dash
            + num_f
            + dash
            + letters_spaced
        )

        # ----------------- Variable Powers -----------------
        # x^2 -> איקס בריבוע
        # y^3 -> וואי בשלישית
        # x^4 -> איקס ברביעית
        # x^n -> איקס בחזקת n
        var_map = [
            ("x", "איקס"), ("X", "איקס"),
            ("y", "וואי"), ("Y", "וואי"),
            ("z", "זד"), ("Z", "זד"),
            ("a", "איי"), ("A", "איי"),
            ("b", "בי"), ("B", "בי"),
            ("n", "אן"), ("N", "אן"),
        ]
        var_fst = pynini.string_map(var_map)

        power_map = [
            ("^2", " בריבוע"),
            ("^3", " בשלישית"),
            ("^4", " ברביעית"),
            ("^5", " בחמישית"),
            ("^n", " בחזקת אן"),
            ("^k", " בחזקת קיי"),
            ("^x", " בחזקת איקס"),
        ]
        power_fst = pynini.string_map(power_map)
        variable_powers = var_fst + power_fst

        all_serials = (
            pynutil.add_weight(all_versions, 0.88)
            | pynutil.add_weight(variable_powers, 0.89)
            | pynutil.add_weight(serial_dash, 0.90)
            | pynutil.add_weight(alphanum_letter_num, 2.5)
            | pynutil.add_weight(alphanum_num_letter, 2.5)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_serials) + pynutil.insert('"')
        ).optimize()
