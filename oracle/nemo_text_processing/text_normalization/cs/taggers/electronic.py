# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.cs.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    delete_extra_space,
    delete_space,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Czech electronic addresses:
    URLs, domain names, emails, and IPv4 addresses.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        # Characters and symbols in electronic addresses
        at = pynini.cross("@", " zavináč ")
        dot = pynini.cross(".", " tečka ")
        slash = pynini.cross("/", " lomítko ")
        colon = pynini.cross(":", " dvojtečka ")
        hyphen = pynini.cross("-", " pomlčka ")
        underscore = pynini.cross("_", " podtržítko ")
        question = pynini.cross("?", " otazník ")
        equals = pynini.cross("=", " rovná se ")
        amp = pynini.cross("&", " a ")
        tilde = pynini.cross("~", " tilda ")

        protocol = (
            pynini.cross("https://", "h t t p s dvojtečka dvě lomítka ")
            | pynini.cross("http://", "h t t p dvojtečka dvě lomítka ")
            | pynini.cross("www.", "w w w tečka ")
        )

        # Digits in electronic contexts: can be read as cardinals
        digit_or_num = pynutil.insert(" ") + cardinal.digits + pynutil.insert(" ")

        # IPv4: 192.168.1.1
        octet = cardinal.n1_999 | cardinal.digits
        ipv4 = (
            octet
            + pynini.cross(".", " tečka ")
            + octet
            + pynini.cross(".", " tečka ")
            + octet
            + pynini.cross(".", " tečka ")
            + octet
        ).optimize()

        # Domain extensions
        tld_map = [
            ("com", "com"),
            ("cz", "cz"),
            ("sk", "sk"),
            ("org", "org"),
            ("net", "net"),
            ("edu", "e d u"),
            ("gov", "gov"),
            ("io", "io"),
            ("ai", "ai"),
            ("dev", "dev"),
            ("app", "app"),
            ("eu", "eu"),
            ("info", "info"),
        ]
        tld = pynini.string_map(tld_map)

        # Alpha letters spelled or kept
        alphanumeric = NEMO_ALPHA | digit_or_num

        char_part = pynini.closure(
            alphanumeric | hyphen | underscore, 1
        )

        domain_name = (
            char_part
            + pynini.closure(pynini.cross(".", " tečka ") + char_part)
            + pynini.cross(".", " tečka ")
            + (tld | pynini.closure(NEMO_ALPHA, 2))
        ).optimize()

        # Email: user@domain
        email_alphanumeric = NEMO_ALPHA | (pynutil.insert(" ") + (cardinal.n1_999 | cardinal.digits) + pynutil.insert(" "))
        email_user = pynini.closure(
            email_alphanumeric | dot | hyphen | underscore, 1
        )
        email = (
            email_user + at + domain_name
        ).optimize()

        # URL path / query: /api, /item-42, ?b=1
        url_path_char = alphanumeric | hyphen | underscore | equals | amp | question | tilde | dot
        url_path = pynini.closure(slash + pynini.closure(url_path_char, 1))

        # Port: :8080
        url_port = colon + cardinal.n1_999

        # Full URL
        full_url = (
            pynini.closure(protocol, 0, 1)
            + domain_name
            + pynini.closure(url_port, 0, 1)
            + pynini.closure(url_path, 0, 1)
        ).optimize()

        # URL starting strictly with protocol
        proto_url = (
            protocol
            + pynini.closure(url_path_char | slash | colon, 1)
        ).optimize()

        # Clean spaces in outputs
        strip_spaces = (
            pynini.cdrewrite(pynutil.delete(" "), "[BOS]", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.delete(" "), "", "[EOS]", NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross("  ", " "), "", "", NEMO_SIGMA)
        )

        raw_fst = (
            ipv4
            | email
            | full_url
            | pynutil.add_weight(proto_url, 0.5)
        ).optimize()

        self.fst = (raw_fst @ strip_spaces).optimize()
