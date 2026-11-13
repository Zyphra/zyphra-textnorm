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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_ALPHA, NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.ms.utils import get_abs_path, load_labels


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic: e-mail addresses and URLs, e.g.
        "info@malaysia.gov.my" -> electronic { username: "info" domain: "malaysia.gov.my" preserve_order: true }
        "https://www.google.com" -> electronic { protocol: "https://www." domain: "google.com" preserve_order: true }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)
        dot = pynini.accep(".")
        symbols = pynini.union(*[x[0] for x in load_labels(get_abs_path("data/electronic/symbols.tsv"))])
        label = pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.union("-", "_"), 1)
        user_chars = pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.difference(symbols, "@"), 1)
        path_char = NEMO_ALPHA | NEMO_DIGIT | pynini.difference(symbols, "@")
        path_end = NEMO_ALPHA | NEMO_DIGIT | pynini.union("/", "=", "_")
        path = pynini.closure(pynini.accep("/") + pynini.closure(pynini.closure(path_char) + path_end, 0, 1))
        port = pynini.closure(pynini.accep(":") + pynini.closure(NEMO_DIGIT, 1, 5), 0, 1)
        tlds = pynini.union(*[x[0] for x in load_labels(get_abs_path("data/electronic/domain.tsv"))])

        domain = pynutil.insert("domain: \"") + label + pynini.closure(dot + label, 1) + port + path + pynutil.insert("\"")
        url_host = pynutil.insert("domain: \"") + label + pynini.closure(dot + label) + port + path + pynutil.insert("\"")
        username = pynutil.insert("username: \"") + user_chars + pynutil.insert("\"") + pynini.cross("@", " ")
        email = username + domain

        protocol_start = pynini.accep("https://") | pynini.accep("http://")
        protocol_end = pynini.accep("www.")
        protocol = protocol_start | protocol_end | (protocol_start + protocol_end)
        protocol = pynutil.insert("protocol: \"") + protocol + pynutil.insert("\"")
        url = protocol + insert_space + url_host

        # bare domains only with a known top-level domain ("malaysia.gov.my", not "dll.")
        bare_domain = (
            pynutil.insert("domain: \"") + label + pynini.closure(dot + label) + tlds + port + path + pynutil.insert("\"")
        )
        graph = url | email | bare_domain
        self.fst = self.add_tokens(graph + pynutil.insert(" preserve_order: true")).optimize()
