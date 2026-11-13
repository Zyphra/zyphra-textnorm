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

from nemo_text_processing.text_normalization.ar.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ar.utils import get_abs_path, load_labels


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying e-mail addresses, URLs (including localhost, ports, and paths),
    bare domains, and IPv4 addresses, e.g.
        "info@example.com" -> electronic { username: "info" domain: "example.com" preserve_order: true }
        "https://www.gov.sa" -> electronic { protocol: "https://www." domain: "gov.sa" preserve_order: true }
        "http://localhost:8080/api" -> electronic { protocol: "http://" domain: "localhost:8080/api" preserve_order: true }
        "app.dev" -> electronic { domain: "app.dev" preserve_order: true }
    """

    def __init__(self):
        super().__init__(name="electronic", kind="classify")
        dot = pynini.accep(".")
        symbols = pynini.union(*[x[0] for x in load_labels(get_abs_path("data/electronic/symbols.tsv"))])
        symbols_no_period = pynini.difference(symbols, pynini.union(".", "@"))
        host_chars = NEMO_ALPHA | NEMO_DIGIT | pynini.union("-", "_")
        accepted = pynini.closure(host_chars, 1)
        all_characters = pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.difference(symbols, "@"), 1)

        top_level = pynini.closure(NEMO_ALPHA, 2)
        octet = pynini.closure(NEMO_DIGIT, 1, 3)
        port = pynini.closure(pynini.accep(":") + pynini.closure(NEMO_DIGIT, 1, 5), 0, 1)
        path = pynini.closure(
            pynini.accep("/") + pynini.closure(NEMO_ALPHA | NEMO_DIGIT | (symbols_no_period - "/") | dot), 1
        )

        domain = accepted + pynini.closure(dot + accepted) + dot + top_level
        email_domain = pynutil.insert('domain: "') + domain + pynutil.insert('"')
        email = (
            pynutil.insert('username: "')
            + all_characters
            + pynutil.insert('"')
            + pynini.cross("@", " ")
            + email_domain
        )

        url_host = domain | pynini.accep("localhost") | (octet + (dot + octet) ** 3)
        url_domain = pynutil.insert('domain: "') + url_host + port + pynini.closure(path, 0, 1) + pynutil.insert('"')
        protocol = pynini.string_file(get_abs_path("data/electronic/protocol.tsv")).project("input")
        url = pynutil.insert('protocol: "') + protocol + pynutil.insert('"') + insert_space + url_domain

        known_tld = pynini.string_file(get_abs_path("data/electronic/domain.tsv")).project("input")
        bare_domain = (
            pynutil.insert('domain: "')
            + accepted
            + pynini.closure(dot + accepted)
            + known_tld
            + port
            + pynini.closure(path, 0, 1)
            + pynutil.insert('"')
        )
        ip_addr = pynutil.insert('domain: "') + octet + (dot + octet) ** 3 + port + pynini.closure(path, 0, 1) + pynutil.insert('"')

        graph = email | url | bare_domain | ip_addr
        self.graph = graph.optimize()
        self.fst = self.add_tokens(self.graph + pynutil.insert(" preserve_order: true")).optimize()
