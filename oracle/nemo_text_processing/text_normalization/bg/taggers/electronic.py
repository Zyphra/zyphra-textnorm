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

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian electronic expressions.
    URLs, bare modern domains (.dev, .ai, .io, .bg, .com, .org),
    emails with multi-digit usernames, and IPv4 addresses.
    e.g. http://localhost:8080/api
         app.dev -> tokens { name: "app точка dev" }
         model.ai -> tokens { name: "model точка ai" }
         tool.io -> tokens { name: "tool точка io" }
         user123@gmail.com -> tokens { name: "user едно две три кльомба gmail точка com" }
         192.168.1.1 -> tokens { name: "едно девет две точка едно шест осем точка едно точка едно" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        d_map = pynini.string_map([
            ("0", "нула"), ("1", "едно"), ("2", "две"), ("3", "три"), ("4", "четири"),
            ("5", "пет"), ("6", "шест"), ("7", "седем"), ("8", "осем"), ("9", "девет")
        ])
        digit_seq = d_map + pynini.closure(pynutil.insert(" ") + d_map)

        # Symbols
        dot = pynini.cross(".", " точка ")
        at = pynini.cross("@", " кльомба ")
        slash = pynini.cross("/", " наклонена черта ")
        colon = pynini.cross(":", " двоеточие ")
        hyphen = pynini.cross("-", " тире ")
        underscore = pynini.cross("_", " долна черта ")

        # IPv4: e.g. 192.168.1.1
        ip_num = digit_seq
        ipv4 = ip_num + dot + ip_num + dot + ip_num + dot + ip_num

        # Protocol: http://, https://
        protocol = (
            pynini.cross("https://", "х т т п с двоеточие наклонена черта наклонена черта ")
            | pynini.cross("http://", "х т т п двоеточие наклонена черта наклонена черта ")
            | pynini.cross("www.", "в в в точка ")
        )

        # Top-level domains
        tld = pynini.union(
            "dev", "ai", "io", "bg", "com", "org", "net", "edu", "gov", "info", "me", "app", "eu"
        )

        # Word chars inside domain or path
        word_char = NEMO_ALPHA
        word_str = pynini.closure(word_char, 1)

        # Modern bare domain: app.dev, model.ai, tool.io
        bare_domain = word_str + dot + tld

        # Email username: user123, ab3.sdd.3
        email_part = (
            word_str
            | digit_seq
            | (word_str + pynutil.insert(" ") + digit_seq)
            | (digit_seq + pynutil.insert(" ") + word_str)
        )
        email_user = email_part + pynini.closure((dot | hyphen | underscore) + email_part)

        email = email_user + at + word_str + dot + tld

        # Full URL with protocol, port, path: http://localhost:8080/api
        port_part = colon + digit_seq
        path_part = slash + pynini.closure(
            word_str | digit_seq | hyphen | underscore | dot | slash, 1
        )
        domain_part = (
            word_str
            | pynini.cross("localhost", "локалхост")
            | (word_str + dot + tld)
        )

        full_url = (
            protocol
            + domain_part
            + pynini.closure(port_part, 0, 1)
            + pynini.closure(path_part, 0, 1)
        )

        all_electronics = (
            pynutil.add_weight(ipv4, 0.0)
            | pynutil.add_weight(full_url, 0.95)
            | pynutil.add_weight(email, 0.96)
            | pynutil.add_weight(bare_domain, 0.98)
        ).optimize()

        self.all_electronics = all_electronics

        graph = pynutil.insert('name: "') + convert_space(all_electronics) + pynutil.insert('"')
        self.fst = graph.optimize()
