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

from nemo_text_processing.text_normalization.kn.graph_utils import NEMO_ALPHA, NEMO_DIGIT, NEMO_KN_DIGIT, GraphFst
from nemo_text_processing.text_normalization.kn.utils import get_abs_path


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic: as URLs, email addresses, file paths,
    IP addresses, domains, and chemical formulas.
        e.g. user@gmail.com -> tokens { electronic { username: "user" domain: "gmail.com" } }
        e.g. https://google.com/ -> tokens { electronic { protocol: "https" domain: "google.com/" } }
        e.g. 192.168.1.1 -> tokens { electronic { domain: "192.168.1.1" } }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        subscript_digit = pynini.project(
            pynini.string_file(get_abs_path("data/electronic/subscript_digit.tsv")), "input"
        )
        alphanumeric = NEMO_ALPHA | NEMO_DIGIT | NEMO_KN_DIGIT | subscript_digit

        symbol_dict = {"email": [], "url": [], "unix": [], "windows": [], "chem": []}

        with open(get_abs_path("data/electronic/symbol_classes.tsv"), "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    sym = parts[0]
                    classes = parts[1].split(",")
                    for c in classes:
                        if c in symbol_dict:
                            symbol_dict[c].append(sym)

        email_symbols = pynini.union(*symbol_dict["email"])
        url_symbols = pynini.union(*symbol_dict["url"])
        unix_symbols = pynini.union(*symbol_dict["unix"])
        win_symbols = pynini.union(*symbol_dict["windows"])
        chemical_symbols = pynini.union(*symbol_dict["chem"])

        unix_segment_syms = pynini.union(*[s for s in symbol_dict["unix"] if s != "/"])

        username_chars = NEMO_ALPHA | NEMO_DIGIT | email_symbols
        username = pynutil.insert("username: \"") + pynini.closure(username_chars, 1) + pynutil.insert("\"")

        domain_chars = NEMO_ALPHA | NEMO_DIGIT | pynini.accep(".") | pynini.accep("-")
        domain = pynutil.insert(" domain: \"") + pynini.closure(domain_chars, 1) + pynutil.insert("\"")

        email_graph = username + pynini.cross("@", "") + domain

        protocol_start = pynini.cross("https://", "https") | pynini.cross("http://", "http")
        protocol_end = pynini.cross("www.", "www")
        protocol = (
            pynutil.insert("protocol: \"")
            + (
                pynutil.add_weight(protocol_start + protocol_end, 1.0)
                | pynutil.add_weight(protocol_start, 1.01)
                | pynutil.add_weight(protocol_end, 1.02)
            )
            + pynutil.insert("\"")
        )

        url_path_chars = alphanumeric | url_symbols
        url_path = pynini.closure(url_path_chars, 1)
        url_domain = pynutil.insert(" domain: \"") + url_path + pynutil.insert("\"")
        url_graph = protocol + url_domain

        drive_letter = NEMO_ALPHA
        windows_path_chars = alphanumeric | win_symbols | pynini.accep(" ")
        windows_path = (
            pynutil.insert("path: \"")
            + drive_letter
            + pynini.accep(":")
            + pynini.accep("\\")
            + pynini.closure(windows_path_chars, 1)
            + pynutil.insert("\"")
        )

        unix_path_chars = alphanumeric | unix_symbols
        unix_segment_chars = alphanumeric | unix_segment_syms
        unix_segment = pynini.closure(unix_segment_chars, 1)

        abs_unix_path = pynini.accep("/") + pynini.closure(unix_path_chars, 1)
        rel_unix_path = (
            pynini.union("./", "../") + pynini.closure(unix_path_chars, 1)
            | unix_segment + pynini.accep("/") + pynini.closure(unix_path_chars, 1)
        )
        unix_path = pynutil.insert("path: \"") + (abs_unix_path | rel_unix_path) + pynutil.insert("\"")

        # IP address: 192.168.1.1
        octet = pynini.closure(NEMO_DIGIT, 1, 3)
        ip_graph = pynutil.insert("domain: \"") + (octet + "." + octet + "." + octet + "." + octet) + pynutil.insert("\"")

        # Domain names: prajavani.net, app.dev
        tlds = pynini.string_file(get_abs_path("data/electronic/domain.tsv"))
        domain_name = pynutil.insert("domain: \"") + (pynini.closure(NEMO_ALPHA, 2) + "." + tlds) + pynutil.insert("\"")

        graph = (
            pynutil.add_weight(email_graph, 1.0)
            | pynutil.add_weight(url_graph, 1.01)
            | pynutil.add_weight(ip_graph, 1.02)
            | pynutil.add_weight(domain_name, 1.03)
            | pynutil.add_weight(windows_path, 1.04)
            | pynutil.add_weight(unix_path, 1.05)
        )

        self.fst = self.add_tokens(graph).optimize()
