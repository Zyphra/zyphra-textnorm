# Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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
from nemo_text_processing.text_normalization.sv.graph_utils import SV_ALPHA
from nemo_text_processing.text_normalization.sv.utils import get_abs_path, load_labels


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic: email addresses and URLs
        e.g. "abc@hotmail.com" -> electronic { username: "abc" domain: "hotmail.com" preserve_order: true }
        e.g. "www.abc.com/123" -> electronic { protocol: "www." domain: "abc.com/123" preserve_order: true }
        e.g. "http://localhost:8080/api" -> electronic { protocol: "http://" domain: "localhost:8080/api" preserve_order: true }
        e.g. "app.dev" -> electronic { domain: "app.dev" preserve_order: true }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        alpha = SV_ALPHA | NEMO_ALPHA
        common_domains = [x[0] for x in load_labels(get_abs_path("data/electronic/domain.tsv")) if x and x[0]]
        symbols = [x[0] for x in load_labels(get_abs_path("data/electronic/symbols.tsv")) if x and x[0]]

        dot = pynini.accep(".")
        accepted_common_domains = pynini.union(*common_domains).optimize()
        accepted_symbols = (pynini.union(*symbols) - dot).optimize()
        url_tail_char = alpha | NEMO_DIGIT | accepted_symbols | dot
        accepted_characters = pynini.closure(alpha | NEMO_DIGIT | accepted_symbols, 1)
        accepted_characters_with_dot = pynini.closure(alpha | NEMO_DIGIT | accepted_symbols | dot, 1)

        # Do not consume trailing sentence-ending punctuation (.,!?:;) at the end of a URL/domain unless `/`
        non_trailing_punct = alpha | NEMO_DIGIT | pynini.union("/", "_", "-", "=", "&", "%", "#")
        url_tail = pynini.closure(
            pynini.union("/", ":", "?", "#") + pynini.closure(url_tail_char) + non_trailing_punct
            | pynini.accep("/"),
            0,
            1,
        ).optimize()

        # Email: user@domain.tld
        username = (
            pynutil.insert('username: "')
            + accepted_characters_with_dot
            + pynutil.insert('"')
            + pynini.cross("@", " ")
        )
        email_domain = (
            (alpha | NEMO_DIGIT)
            + pynini.closure(alpha | NEMO_DIGIT | pynini.union("-", "_"))
            + pynini.closure(dot + pynini.closure(alpha | NEMO_DIGIT | pynini.union("-", "_"), 1), 1)
        )
        email_domain_graph = pynutil.insert('domain: "') + email_domain + pynutil.insert('"')

        # Bare domain with known TLD (e.g. app.dev, model.ai, tool.io, nvidia.com, aftonbladet.se/nyheter)
        # Must start with at least one letter so numbers like "3.14" or "12.30" never match!
        label_char = alpha | NEMO_DIGIT | pynini.union("-", "_")
        bare_host_start = pynini.closure(label_char) + alpha + pynini.closure(label_char)
        bare_host = bare_host_start + pynini.closure(dot + pynini.closure(label_char, 1))
        domain_common_graph = (
            pynutil.insert('domain: "')
            + bare_host
            + accepted_common_domains
            + url_tail
            + pynutil.insert('"')
        ).optimize()

        graph = (username + email_domain_graph) | domain_common_graph

        # Full URL with protocol (http://, https://, www.): supports dotted hosts AND localhost + optional :port/path
        protocol_start = pynini.accep("https://") | pynini.accep("http://")
        protocol_end = (
            pynini.accep("www.")
            if deterministic
            else pynini.accep("www.") | pynini.cross("www.", "dubbel ve dubbel ve dubbel ve.")
        )
        protocol_www_only = pynutil.insert('protocol: "') + protocol_end + pynutil.insert('"')
        protocol_http = (
            pynutil.insert('protocol: "') + (protocol_start | (protocol_start + protocol_end)) + pynutil.insert('"')
        )

        dotted_url_host = (
            pynini.closure(label_char, 1)
            + pynini.closure(dot + pynini.closure(label_char, 1), 1)
            + url_tail
        )
        local_or_port_host = (
            (pynini.accep("localhost") | bare_host_start)
            + (
                (pynini.accep(":") + pynini.closure(NEMO_DIGIT, 1) + url_tail)
                | (pynini.accep("/") + pynini.closure(url_tail_char) + non_trailing_punct)
                | pynini.accep("/")
            )
        )
        http_domain = pynutil.insert('domain: "') + (dotted_url_host | local_or_port_host) + pynutil.insert('"')
        www_domain = pynutil.insert('domain: "') + dotted_url_host + pynutil.insert('"')

        graph |= (protocol_http + insert_space + http_domain) | (protocol_www_only + insert_space + www_domain)
        self.graph = graph.optimize()

        final_graph = self.add_tokens(self.graph + pynutil.insert(" preserve_order: true"))
        self.fst = final_graph.optimize()
