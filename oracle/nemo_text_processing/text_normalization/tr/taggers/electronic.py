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
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic items:
    - URLs: http://localhost:8080/api, https://www.google.com
    - Bare domains: app.dev, model.ai, tool.io
    - Emails: ab3.sdd.3@gmail.com
    - IPv4: 192.168.1.1, 193.1.89.60
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        # Single digit inside emails / URLs
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

        # Letters inside username / domain spelled out or kept
        letters_spoken = pynini.string_map([(c, c) for c in string.ascii_lowercase + string.ascii_uppercase])

        # Symbol readings
        symbol_map = pynini.string_map([
            (".", "nokta"),
            ("@", "et"),
            ("/", "bölü"),
            (":", "iki nokta"),
            ("-", "tire"),
            ("_", "alt çizgi"),
            ("~", "tilde"),
            ("?", "soru işareti"),
            ("=", "eşittir"),
            ("&", "ve"),
            ("%", "yüzde"),
            ("#", "diyez"),
        ])

        # 1. IPv4 addresses: 192.168.1.1, 193.1.89.60
        octet = (pynini.closure(NEMO_DIGIT, 1, 3) @ cardinal.positive_cardinals).optimize()
        dot = pynini.cross(".", " nokta ")
        ipv4_graph = (
            octet + dot + octet + dot + octet + dot + octet
        )

        # 2. Protocol prefix
        proto_map = pynini.string_map([
            ("http://", "h t t p iki nokta üst üste bölü bölü "),
            ("https://", "h t t p s iki nokta üst üste bölü bölü "),
            ("ftp://", "f t p iki nokta üst üste bölü bölü "),
            ("www.", "v v v nokta "),
        ])

        # Top-level domains
        tld_map = pynini.string_map([
            (".com", " nokta com"),
            (".org", " nokta org"),
            (".net", " nokta net"),
            (".edu", " nokta edu"),
            (".gov", " nokta gov"),
            (".io", " nokta i o"),
            (".dev", " nokta dev"),
            (".ai", " nokta a i"),
            (".tr", " nokta t r"),
            (".com.tr", " nokta com nokta t r"),
            (".gov.tr", " nokta gov nokta t r"),
            (".edu.tr", " nokta edu nokta t r"),
            (".org.tr", " nokta org nokta t r"),
            (".de", " nokta d e"),
            (".uk", " nokta u k"),
            (".app", " nokta app"),
            (".co", " nokta c o"),
            (".me", " nokta m e"),
            (".info", " nokta info"),
            (".xyz", " nokta x y z"),
        ])

        # Port: :8080 -> iki nokta sekiz bin seksen
        port_graph = pynini.cross(":", " iki nokta ") + (pynini.closure(NEMO_DIGIT, 1, 5) @ cardinal.positive_cardinals)

        # Path: /api, /v1/chat -> bölü api, bölü v bir bölü chat
        char_in_path = (
            digit_map
            | letters_spoken
            | pynini.cross("/", " bölü ")
            | pynini.cross("-", " tire ")
            | pynini.cross("_", " alt çizgi ")
            | pynini.cross(".", " nokta ")
            | pynini.cross("=", " eşittir ")
            | pynini.cross("?", " soru işareti ")
            | pynini.cross("&", " ve ")
        )
        path_graph = pynini.cross("/", " bölü ") + pynini.closure(char_in_path)

        domain_char = pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.union("-", "_"), 1)

        # Full URL with protocol: http://localhost:8080/api
        url_full = (
            proto_map
            + domain_char
            + pynini.closure(tld_map, 0, 1)
            + pynini.closure(port_graph, 0, 1)
            + pynini.closure(path_graph, 0, 1)
        )

        # Bare domain: app.dev, model.ai, tool.io, google.com
        bare_domain = domain_char + tld_map + pynini.closure(path_graph, 0, 1)

        # 3. Email address: ab3.sdd.3@gmail.com
        email_char = (
            letters_spoken
            | digit_map
            | pynini.cross(".", " nokta ")
            | pynini.cross("_", " alt çizgi ")
            | pynini.cross("-", " tire ")
            | pynini.cross("+", " artı ")
        )
        email_user = email_char + pynini.closure(pynutil.insert(" ") + email_char)
        email_graph = (
            email_user
            + pynini.cross("@", " et ")
            + domain_char
            + tld_map
        )

        all_electronic = (
            ipv4_graph
            | url_full
            | email_graph
            | bare_domain
        ).optimize()
        self.all_electronic = all_electronic

        self.fst = (pynutil.insert('name: "') + convert_space(all_electronic) + pynutil.insert('"')).optimize()
