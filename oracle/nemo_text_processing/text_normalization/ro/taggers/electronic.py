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

import string
import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.ro.graph_utils import to_name_token
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Romanian electronic expressions, e.g.
        "http://localhost:8080/api" -> tokens { name: "h t t p două puncte slash slash l o c a l h o s t două puncte opt zero opt zero slash a p i" }
        "app.dev" -> tokens { name: "a p p punct dev" }
        "model.ai" -> tokens { name: "m o d e l punct a i" }
        "tool.io" -> tokens { name: "t o o l punct i o" }
        "ab3.sdd.3@gmail.com" -> tokens { name: "a b trei punct s d d punct trei arond g m a i l punct c o m" }
        "192.168.1.1" -> tokens { name: "o sută nouăzeci și doi punct o sută șaizeci și opt punct unu punct unu" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        # Single characters in electronic context:
        # Letters spelled with trailing space (except last)
        letters = list(string.ascii_lowercase)
        letter_map = pynini.string_map([(c, c) for c in letters])
        letter_map_upper = pynini.string_map([(c.upper(), c) for c in letters])
        all_letters = letter_map | letter_map_upper

        digit_map = pynini.string_map([
            ("0", "zero"),
            ("1", "unu"),
            ("2", "doi"),
            ("3", "trei"),
            ("4", "patru"),
            ("5", "cinci"),
            ("6", "șase"),
            ("7", "șapte"),
            ("8", "opt"),
            ("9", "nouă"),
        ])

        elem = all_letters | digit_map
        elem_spaced = elem + pynutil.insert(" ")

        # Sequence of letters and digits spaced
        char_seq = (pynini.closure(elem_spaced) + elem).optimize()

        # Electronic symbols
        dot = pynini.cross(".", " punct ")
        at = pynini.cross("@", " arond ")
        colon = pynini.cross(":", " două puncte ")
        slash = pynini.cross("/", " slash ")
        slash_slash = pynini.cross("//", " slash slash ")
        dash = pynini.cross("-", " liniuță ")
        underscore = pynini.cross("_", " linie jos ")

        # Protocol: http://, https://, ftp://
        protocol = pynini.union(
            pynini.cross("http://", "h t t p două puncte slash slash "),
            pynini.cross("https://", "h t t p s două puncte slash slash "),
            pynini.cross("ftp://", "f t p două puncte slash slash "),
            pynini.cross("www.", "w w w punct "),
        )

        # TLDs
        common_tlds = pynini.union(
            "ro", "com", "org", "net", "edu", "gov", "eu", "info", "biz",
            "dev", "ai", "io", "app", "tech", "online", "store", "co", "uk", "de", "fr"
        )
        tld_graph = pynutil.delete(".") + pynutil.insert(" punct ") + char_seq

        # Port: :8080 -> două puncte opt zero opt zero
        port_digits = pynini.closure(digit_map + pynutil.insert(" ")) + digit_map
        port = colon + port_digits

        # Path: /api, /test/page
        path_seg = slash + char_seq
        path = pynini.closure(path_seg, 1)

        # 1. Full URL with protocol: http://localhost:8080/api
        host = char_seq + pynini.closure(dot + char_seq)
        url_with_protocol = (
            protocol
            + host
            + pynini.closure(port, 0, 1)
            + pynini.closure(path, 0, 1)
        ).optimize()

        # 2. Modern bare domain: app.dev, model.ai, tool.io, example.com
        bare_domain = (
            char_seq
            + pynutil.delete(".")
            + pynutil.insert(" punct ")
            + common_tlds
        ).optimize()

        # 3. Emails: ab3.sdd.3@gmail.com, user@domain.ro
        email_elem = (
            all_letters
            | digit_map
            | pynini.cross(".", " punct ")
            | pynini.cross("-", " liniuță ")
            | pynini.cross("_", " linie jos ")
        )
        email_spaced = email_elem + pynini.closure(pynutil.insert(" "), 0, 1)
        email_user = pynini.closure(email_spaced, 1)
        email_domain = char_seq + pynutil.delete(".") + pynutil.insert(" punct ") + (char_seq | common_tlds)
        email_rule = (email_user + at + email_domain).optimize()

        # 4. IPv4 addresses: 192.168.1.1
        # Each octet read as a cardinal number:
        cardinal_fst = cardinal if cardinal else CardinalFst()
        octet = NEMO_DIGIT**1 | NEMO_DIGIT**2 | NEMO_DIGIT**3
        octet_words = octet @ cardinal_fst.cardinal_numbers
        ipv4_rule = (
            octet_words
            + pynini.cross(".", " punct ")
            + octet_words
            + pynini.cross(".", " punct ")
            + octet_words
            + pynini.cross(".", " punct ")
            + octet_words
        ).optimize()

        composite = (
            ipv4_rule
            | url_with_protocol
            | email_rule
            | bare_domain
        ).optimize()

        self.fst = to_name_token(composite)
