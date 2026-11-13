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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Danish electronic tokens:
    URLs, domain names, email addresses, and IPv4 addresses.
    Symbols spoken natively:
      "@" -> "snabel-a"
      "." -> "punktum"
      "/" -> "skråstreg"
      "//" -> "dobbelt skråstreg"
      ":" -> "kolon"
      "-" -> "bindestreg"
      "_" -> "understreg"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        # Characters and symbols in electronic strings
        char_digit = cardinal.single_digit

        # Letter spelled out or single letter:
        # Lowercase letters
        alpha_lower = [
            ("a", "a"),
            ("b", "b"),
            ("c", "c"),
            ("d", "d"),
            ("e", "e"),
            ("f", "f"),
            ("g", "g"),
            ("h", "h"),
            ("i", "i"),
            ("j", "j"),
            ("k", "k"),
            ("l", "l"),
            ("m", "m"),
            ("n", "n"),
            ("o", "o"),
            ("p", "p"),
            ("q", "q"),
            ("r", "r"),
            ("s", "s"),
            ("t", "t"),
            ("u", "u"),
            ("v", "v"),
            ("w", "w"),
            ("x", "x"),
            ("y", "y"),
            ("z", "z"),
            ("æ", "æ"),
            ("ø", "ø"),
            ("å", "å"),
        ]
        alpha_map = pynini.string_map(alpha_lower + [(c.upper(), name) for c, name in alpha_lower])

        # Common words kept whole inside domains / URLs
        common_words = pynini.string_map(
            [
                ("google", "google"),
                ("gmail", "g mail"),
                ("nvidia", "nvidia"),
                ("localhost", "localhost"),
                ("example", "example"),
                ("firma", "firma"),
                ("dr", "d r"),
            ]
        )

        # Symbols
        at = pynini.cross("@", " snabel-a ")
        dot = pynini.cross(".", " punktum ")
        slash = pynini.cross("/", " skråstreg ")
        double_slash = pynini.cross("//", " dobbelt skråstreg ")
        colon = pynini.cross(":", " kolon ")
        dash = pynini.cross("-", " bindestreg ")
        underscore = pynini.cross("_", " understreg ")
        question = pynini.cross("?", " spørgsmålstegn ")
        equals = pynini.cross("=", " er lig med ")
        amp = pynini.cross("&", " og ")

        # Protocols
        http = pynini.cross("http://", "h t t p kolon dobbelt skråstreg ")
        https = pynini.cross("https://", "h t t p s kolon dobbelt skråstreg ")
        ftp = pynini.cross("ftp://", "f t p kolon dobbelt skråstreg ")
        protocol = http | https | ftp

        # Top level domains
        tld_map = pynini.string_map(
            [
                ("com", "com"),
                ("dk", "d k"),
                ("org", "o r g"),
                ("net", "n e t"),
                ("edu", "e d u"),
                ("gov", "g o v"),
                ("io", "i o"),
                ("ai", "a i"),
                ("dev", "dev"),
                ("se", "s e"),
                ("no", "n o"),
                ("de", "d e"),
                ("sm", "s m"),
                ("es", "e s"),
            ]
        )

        www = pynini.cross("www.", "w w w punktum ")

        # Elements of email username / domain labels
        elem = common_words | alpha_map | char_digit

        word_token = elem + pynini.closure(pynutil.insert(" ") + elem)

        # Email address: e.g. "a.bc@gmail.com", "ab3.sdd.3@gmail.com"
        email_user = (
            word_token
            + pynini.closure(
                (dot | dash | underscore) + word_token
            )
        )

        email_domain = (
            word_token
            + dot
            + (tld_map | word_token)
            + pynini.closure(dot + (tld_map | word_token))
        )

        email = email_user + at + email_domain

        # URLs:
        # Path segment
        path_elem = common_words | word_token | cardinal.integer_neuter
        path_segment = (
            slash
            + path_elem
            + pynini.closure(
                (slash | dot | dash | underscore | question | equals | amp) + path_elem
            )
        )

        # Port: e.g. ":8080" -> " kolon otte tusind og firs"
        port = colon + cardinal.integer_neuter

        url_core = (
            pynini.closure(protocol, 0, 1)
            + pynini.closure(www, 0, 1)
            + (common_words | word_token)
            + dot
            + (tld_map | word_token)
            + pynini.closure(dot + (tld_map | word_token))
            + pynini.closure(port, 0, 1)
            + pynini.closure(path_segment, 0, 1)
        )

        # Explicit localhost: e.g. "http://localhost:8080/api"
        localhost_url = (
            protocol
            + pynini.cross("localhost", "localhost")
            + pynini.closure(port, 0, 1)
            + pynini.closure(path_segment, 0, 1)
        )

        # Bare domain: e.g. "app.dev", "model.ai", "tool.io", "www.nvidia.com"
        bare_domain = (
            pynini.closure(www, 0, 1)
            + (common_words | word_token)
            + dot
            + tld_map
            + pynini.closure(path_segment, 0, 1)
        )

        # IPv4 address: e.g. "192.168.1.1"
        octet = pynini.union(*[str(n) for n in range(256)]) @ (
            cardinal.integer_with_et
            | pynutil.add_weight(cardinal.integer_neuter, 0.01)
        )
        ipv4 = octet + dot + octet + dot + octet + dot + octet

        all_electronic = (
            email
            | localhost_url
            | url_core
            | bare_domain
            | pynutil.add_weight(ipv4, -0.05)
        ).optimize()

        self.graph = all_electronic

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
