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
    insert_space,
)
from nemo_text_processing.text_normalization.ka.graph_utils import GEORGIAN_ALPHA
from nemo_text_processing.text_normalization.ka.utils import get_abs_path, load_labels


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic: e-mail addresses and URLs, e.g.
        "ab3.sdd.3@gmail.com" -> electronic { username: "ab3.sdd.3" domain: "gmail.com" preserve_order: true }
        "http://localhost:8080/api" -> electronic { protocol: "http://" domain: "localhost:8080/api" preserve_order: true }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        dot = pynini.accep(".")
        symbols = pynini.union(*[row[0] for row in load_labels(get_abs_path("data/electronic/symbols.tsv"))])
        symbols_no_period = pynini.difference(symbols, dot | "@")
        letter = NEMO_ALPHA | GEORGIAN_ALPHA | NEMO_DIGIT
        accepted_characters = pynini.closure(letter | symbols_no_period, 1)
        all_characters = pynini.closure(letter | pynini.difference(symbols, "@"), 1)

        domain = dot + accepted_characters
        domain_graph = (
            pynutil.insert('domain: "') + (accepted_characters + pynini.closure(domain, 1)) + pynutil.insert('"')
        )
        username = pynutil.insert('username: "') + all_characters + pynutil.insert('"') + pynini.cross("@", " ")
        email = username + domain_graph

        protocol_start = pynini.accep("https://") | pynini.accep("http://")
        protocol_end = pynini.accep("www.")
        url_with_scheme = (
            pynutil.insert('protocol: "')
            + (protocol_start | (protocol_start + protocol_end))
            + pynutil.insert('"')
            + insert_space
            + pynutil.insert('domain: "')
            + all_characters
            + pynutil.insert('"')
        )
        url_www_only = pynutil.insert('protocol: "') + protocol_end + pynutil.insert('"') + insert_space + domain_graph
        url = url_with_scheme | url_www_only

        bare_domain = pynini.compose(
            pynini.closure(letter | symbols_no_period) + dot + (NEMO_ALPHA | GEORGIAN_ALPHA)
            + pynini.closure(NEMO_ALPHA | GEORGIAN_ALPHA, 1)
            + pynini.closure("/" + pynini.closure(letter | symbols)),
            domain_graph,
        )
        graph = url | bare_domain | email
        self.fst = self.add_tokens(graph + pynutil.insert(" preserve_order: true")).optimize()
