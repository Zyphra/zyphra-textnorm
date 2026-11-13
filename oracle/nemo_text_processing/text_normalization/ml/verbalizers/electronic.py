# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_CHAR,
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    insert_space,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for verbalizing electronic, e.g.
        electronic { username: "user" domain: "gmail.com" } -> user അറ്റ് gmail ഡോട്ട് com
        electronic { protocol: "https" domain: "www.google.com" } -> https കോളൻ സ്ലാഷ് സ്ലാഷ് www ഡോട്ട് google ഡോട്ട് com
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="verbalize", deterministic=deterministic)

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        username = pynini.closure(field("username") + delete_space + pynutil.insert(" അറ്റ് "), 0, 1)
        protocol = pynini.closure(field("protocol") + delete_space + pynutil.insert(" കോളൻ സ്ലാഷ് സ്ലാഷ് "), 0, 1)
        domain = field("domain")

        raw_graph = protocol + username + domain

        # Digit mapping for IPv4 and addresses
        digit_map = pynini.string_map([
            ("0", "പൂജ്യം"), ("1", "ഒന്ന്"), ("2", "രണ്ട്"), ("3", "മൂന്ന്"),
            ("4", "നാല്"), ("5", "അഞ്ച്"), ("6", "ആറ്"), ("7", "ഏഴ്"),
            ("8", "എട്ട്"), ("9", "ഒൻപത്"),
            ("൦", "പൂജ്യം"), ("൧", "ഒന്ന്"), ("൨", "രണ്ട്"), ("൩", "മൂന്ന്"),
            ("൪", "നാല്"), ("൫", "അഞ്ച്"), ("൬", "ആറ്"), ("൭", "ഏഴ്"),
            ("൮", "എട്ട്"), ("൯", "ഒൻപത്"),
        ])
        all_digits = pynini.union(*"0123456789൦൧൨൩൪൫൬൭൮൯")
        insert_space_between_digits = pynini.cdrewrite(pynutil.insert(" "), all_digits, all_digits, NEMO_SIGMA)

        symbol_rewrites = (
            insert_space_between_digits
            @ pynini.cdrewrite(pynini.cross(".", " ഡോട്ട് "), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("/", " സ്ലാഷ് "), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("_", " അണ്ടർസ്കോർ "), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("-", " ഹൈഫൻ "), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.string_map([
                (":", " കോളൻ "), ("?", " ചോദ്യചിഹ്നം "), ("=", " സമം "),
                ("&", " ആൻഡ് "), ("#", " ഹാഷ് "), ("%", " ശതമാനം "), ("+", " പ്ലസ് "),
            ]), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(digit_map, "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("  ", " "), "", "", NEMO_SIGMA)
        )

        verbalized = raw_graph @ symbol_rewrites
        self.fst = self.delete_tokens(verbalized).optimize()
