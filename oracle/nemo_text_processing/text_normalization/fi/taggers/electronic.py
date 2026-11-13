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
    convert_space,
    insert_space,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Finnish electronic expressions, e.g.
        "http://localhost:8080/api" -> tokens { name: "h t t p kaksoispiste kauttaviiva kauttaviiva localhost kaksoispiste kahdeksan nolla kahdeksan nolla kauttaviiva a p i" }
        "app.dev" -> tokens { name: "app piste dev" }
        "model.ai" -> tokens { name: "model piste ai" }
        "tool.io" -> tokens { name: "tool piste io" }
        "user123@gmail.com" -> tokens { name: "u s e r yksi kaksi kolme miuku mauku g m a i l piste c o m" }
        "192.168.1.1" -> tokens { name: "satayhdeksänkymmentäkaksi piste satakuusikymmentäkahdeksan piste yksi piste yksi" }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        digits_map = [
            ("0", "nolla"),
            ("1", "yksi"),
            ("2", "kaksi"),
            ("3", "kolme"),
            ("4", "neljä"),
            ("5", "viisi"),
            ("6", "kuusi"),
            ("7", "seitsemän"),
            ("8", "kahdeksan"),
            ("9", "yhdeksän"),
        ]
        digit = pynini.string_map(digits_map)

        # Characters in username/email: letter -> letter, digit -> word
        alpha = pynini.union(*[chr(c) for c in range(ord("a"), ord("z") + 1)],
                             *[chr(c) for c in range(ord("A"), ord("Z") + 1)])
        
        email_sym = pynini.string_map([
            (".", "piste"),
            ("-", "viiva"),
            ("_", "alaviiva"),
            ("+", "plus"),
        ])

        # Modern bare domains: "app.dev", "model.ai", "tool.io", "example.com", "google.fi"
        domains_tld = pynini.closure(alpha, 2)
        domain_name = pynini.closure(alpha, 1)
        bare_domain = (
            domain_name
            + pynini.cross(".", " piste ")
            + domains_tld
        )

        # IPv4 addresses: "192.168.1.1"
        octet_map = [
            ("0", "nolla"), ("1", "yksi"), ("2", "kaksi"), ("3", "kolme"), ("4", "neljä"),
            ("5", "viisi"), ("6", "kuusi"), ("7", "seitsemän"), ("8", "kahdeksan"), ("9", "yhdeksän"),
            ("10", "kymmenen"), ("12", "kaksitoista"), ("20", "kaksikymmentä"),
            ("100", "sata"), ("127", "satakaksikymmentäseitsemän"),
            ("168", "satakuusikymmentäkahdeksan"), ("192", "satayhdeksänkymmentäkaksi"),
            ("255", "kaksisataaviisikymmentäviisi"),
        ]
        octet = pynini.string_map(octet_map) | (pynini.closure(NEMO_DIGIT, 1, 3) @ (cardinal.all_nums_no_tokens if cardinal else digit))
        ipv4 = octet + pynini.cross(".", " piste ") + octet + pynini.cross(".", " piste ") + octet + pynini.cross(".", " piste ") + octet

        # Direct common URLs and emails
        url_symbol = pynini.string_map([
            (".", "piste"), (":", "kaksoispiste"), ("/", "kauttaviiva"),
            ("?", "kysymysmerkki"), ("=", "on"), ("&", "ja"), ("#", "numero"),
            ("%", "prosenttia"), ("-", "viiva"), ("_", "alaviiva"), ("+", "plus"), ("~", "tilde"),
        ])
        url_char = alpha | digit | url_symbol
        url_body = url_char + pynini.closure(pynutil.insert(" ") + url_char)
        protocol = pynini.string_map([
            ("http://", "h t t p kaksoispiste kauttaviiva kauttaviiva "),
            ("https://", "h t t p s kaksoispiste kauttaviiva kauttaviiva "),
            ("www.", "w w w piste "),
        ])
        url = protocol + url_body

        # General email pattern
        user_char = alpha | digit | email_sym
        user_part = user_char + pynini.closure(pynutil.insert(" ") + user_char)
        at_sign = pynini.cross("@", " miuku mauku ")
        email_general = (
            user_part
            + at_sign
            + user_part
            + pynini.cross(".", " piste ")
            + domains_tld
        )

        number = (pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal.all_nums_no_tokens) if cardinal else (
            digit + pynini.closure(pynutil.insert(" ") + digit)
        )
        version_tail = pynini.cross(".", " piste ") + number
        version = number + pynini.closure(version_tail, 2)
        named_version = pynini.closure(alpha, 1) + pynini.accep(" ") + number + pynini.closure(version_tail, 1)
        prefixed_version = pynini.cross(pynini.union("v", "V"), "versio ") + number + pynini.closure(version_tail, 1)
        all_electronic = (
            url
            | bare_domain
            | ipv4
            | email_general
            | version | named_version | prefixed_version
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_electronic).optimize()
            + pynutil.insert('"')
        ).optimize()
