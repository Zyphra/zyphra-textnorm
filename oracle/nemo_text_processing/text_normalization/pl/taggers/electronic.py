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
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Polish electronic expressions:
    URLs, email addresses, bare domains, and IPv4 addresses.
    e.g.
        "http://localhost:8080/api" -> "h t t p dwukropek ukośnik ukośnik localhost dwukropek osiem zero osiem zero ukośnik a p i"
        "app.dev" -> "app kropka dev"
        "model.ai" -> "model kropka a i"
        "tool.io" -> "tool kropka i o"
        "user123@gmail.com" -> "u s e r jeden dwa trzy małpa g m a i l kropka c o m"
        "192.168.1.1" -> "sto dziewięćdziesiąt dwa kropka sto sześćdziesiąt osiem kropka jeden kropka jeden"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        # Single digits to Polish words
        digit_words = cardinal.digit

        # Letter spelling: separate each ascii character by space
        letters = pynini.union(*string.ascii_letters)
        spelled_letter = letters + insert_space
        spelled_digit = digit_words + insert_space

        # Symbols
        dot = pynini.cross(".", " kropka ")
        at = pynini.cross("@", " małpa ")
        slash = pynini.cross("/", " ukośnik ")
        colon = pynini.cross(":", " dwukropek ")
        dash = pynini.cross("-", " myślnik ")
        underscore = pynini.cross("_", " podkreślenie ")
        syms = dot | at | slash | colon | dash | underscore

        # Known top-level domains
        tlds = pynini.union(
            pynini.cross(".com", " kropka c o m"),
            pynini.cross(".org", " kropka o r g"),
            pynini.cross(".net", " kropka n e t"),
            pynini.cross(".edu", " kropka e d u"),
            pynini.cross(".gov", " kropka g o v"),
            pynini.cross(".pl", " kropka p l"),
            pynini.cross(".eu", " kropka e u"),
            pynini.cross(".dev", " kropka dev"),
            pynini.cross(".ai", " kropka a i"),
            pynini.cross(".io", " kropka i o"),
            pynini.cross(".app", " kropka app"),
            pynini.cross(".info", " kropka info"),
            pynini.cross(".de", " kropka d e"),
            pynini.cross(".uk", " kropka u k"),
            pynini.cross(".fr", " kropka f r"),
        )

        # Protocol
        http = pynini.cross("http://", "h t t p dwukropek ukośnik ukośnik ")
        https = pynini.cross("https://", "h t t p s dwukropek ukośnik ukośnik ")
        www = pynini.cross("www.", "w w w kropka ")
        protocol = https | http | www | (https + www) | (http + www)

        # Character mapper inside identifiers
        id_char = (
            NEMO_ALPHA
            | pynutil.insert(" ") + digit_words + pynutil.insert(" ")
            | syms
        )
        id_seg = pynini.closure(id_char, 1)

        # Port part: ":8080"
        port_num = pynini.closure(digit_words + insert_space, 1, 5)
        port = colon + port_num

        # Path part: "/api", "/v2/item-42"
        path_char = letters + insert_space | digit_words + insert_space | syms
        path_seg = pynini.closure(path_char, 1)
        path = pynini.closure(slash + path_seg)

        # Full URL with protocol: "http://localhost:8080/api", "https://example.org/v2/item-42"
        host = pynini.closure(NEMO_ALPHA, 1) + pynini.closure(dot + pynini.closure(NEMO_ALPHA, 1))
        url = (
            protocol
            + host
            + pynini.closure(port, 0, 1)
            + pynini.closure(path, 0, 1)
        )

        # Bare domain: "app.dev", "model.ai", "tool.io", "example.pl"
        domain_name = pynini.closure(NEMO_ALPHA | NEMO_DIGIT | "-", 1)
        bare_domain = domain_name + tlds + pynini.closure(port, 0, 1) + pynini.closure(path, 0, 1)

        # Email: "user123@gmail.com", "ab3.sdd.3@gmail.com"
        email_user_char = (
            letters + insert_space
            | digit_words + insert_space
            | pynini.cross(".", "kropka ")
            | pynini.cross("_", "podkreślenie ")
            | pynini.cross("-", "myślnik ")
        )
        email_user = pynini.closure(email_user_char, 1)
        email_domain_char = letters + insert_space | digit_words + insert_space | pynini.cross("-", "myślnik ")
        email_domain = pynini.closure(email_domain_char, 1) + tlds
        email = email_user + pynini.cross("@", "małpa ") + email_domain

        # IPv4: "192.168.1.1"
        octet = NEMO_DIGIT** (1, 3) @ cardinal.graph
        ipv4 = octet + dot + octet + dot + octet + dot + octet

        # Clean multiple spaces
        clean_sp = pynini.cdrewrite(pynini.cross(pynini.closure(" ", 2), " "), "", "", NEMO_SIGMA)

        self.graph = ((url | email | bare_domain | ipv4) @ clean_sp).optimize()
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
