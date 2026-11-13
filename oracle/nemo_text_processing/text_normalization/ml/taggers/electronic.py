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
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_ML_DIGIT,
    GraphFst,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic: URLs, email addresses, IP addresses.
        user@gmail.com -> electronic { username: "user" domain: "gmail.com" }
        https://www.google.com -> electronic { protocol: "https" domain: "www.google.com" }
        192.168.1.1 -> electronic { domain: "192.168.1.1" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        alphanumeric = NEMO_ALPHA | NEMO_DIGIT | NEMO_ML_DIGIT
        email_syms = pynini.union(".", "-", "_", "+")
        username_chars = alphanumeric | email_syms
        username = pynutil.insert("username: \"") + pynini.closure(username_chars, 1) + pynutil.insert("\"")

        domain_suffix = pynini.closure(NEMO_ALPHA, 2)
        domain_char = alphanumeric | pynini.union("-", "_")
        domain_part = pynini.closure(domain_char, 1)
        full_domain = (
            pynutil.insert(" domain: \"")
            + pynini.closure(domain_part + ".", 1)
            + domain_suffix
            + pynutil.insert("\"")
        )

        email = username + pynutil.delete("@") + full_domain

        # URLs
        protocol_start = (
            pynutil.insert("protocol: \"")
            + (pynini.accep("https") | pynini.accep("http"))
            + pynutil.insert("\"")
            + pynutil.delete("://")
        )
        url_path_char = alphanumeric | pynini.union(".", "/", ":", "-", "_", "~", "?", "=", "&", "%", "#")
        url_www = (
            pynutil.insert("domain: \"www.")
            + pynutil.delete("www.")
            + pynini.closure(url_path_char, 1)
            + pynutil.insert("\"")
        )
        url_domain_and_path = (
            pynutil.insert(" domain: \"")
            + pynini.closure(url_path_char, 1)
            + pynutil.insert("\"")
        )

        url_full = protocol_start + pynutil.insert(" ") + url_domain_and_path
        bare_domain = (
            pynutil.insert("domain: \"")
            + pynini.closure(domain_part + ".", 1)
            + domain_suffix
            + pynutil.insert("\"")
        )

        # IPv4
        octet = pynini.closure(NEMO_DIGIT, 1, 3)
        ipv4 = octet + "." + octet + "." + octet + "." + octet
        ipv4_domain = pynutil.insert("domain: \"") + ipv4 + pynutil.insert("\"")

        graph = email | url_full | url_www | bare_domain | ipv4_domain
        self.fst = self.add_tokens(graph).optimize()
