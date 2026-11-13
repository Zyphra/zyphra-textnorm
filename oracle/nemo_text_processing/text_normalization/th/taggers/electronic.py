# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic identifiers in Thai (th).
    Supports:
    - URLs: http://localhost:8080/api, https://example.com/page
    - Bare modern domains: app.dev, model.ai, tool.io
    - Emails: user@example.com, user123@gmail.com, ab3.sdd.3@gmail.com
    - IPv4 addresses: 192.168.1.1, 10.0.0.1
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        digit_words = pynini.string_map(
            [
                ("0", "ศูนย์"),
                ("1", "หนึ่ง"),
                ("2", "สอง"),
                ("3", "สาม"),
                ("4", "สี่"),
                ("5", "ห้า"),
                ("6", "หก"),
                ("7", "เจ็ด"),
                ("8", "แปด"),
                ("9", "เก้า"),
            ]
        )

        # Electronic symbols
        dot = pynini.cross(".", " ดอท ")
        at = pynini.cross("@", " แอท ")
        slash = pynini.cross("/", " สแลช ")
        colon = pynini.cross(":", " โคลอน ")
        hyphen = pynini.cross("-", " ขีด ")
        underscore = pynini.cross("_", " อันเดอร์สโกร ")

        # IPv4: 192.168.1.1 -> หนึ่งเก้าสองจุดหนึ่งหกแปดจุดหนึ่งจุดหนึ่ง
        octet = pynini.closure(NEMO_DIGIT @ digit_words, 1, 3)
        ipv4 = (
            octet
            + pynini.cross(".", "จุด")
            + octet
            + pynini.cross(".", "จุด")
            + octet
            + pynini.cross(".", "จุด")
            + octet
        ).optimize()

        # Domains and TLDs
        tlds = pynini.string_map(
            [
                (".com", " ดอท com"),
                (".org", " ดอท org"),
                (".net", " ดอท net"),
                (".edu", " ดอท edu"),
                (".gov", " ดอท gov"),
                (".io", " ดอท io"),
                (".ai", " ดอท ai"),
                (".dev", " ดอท dev"),
                (".app", " ดอท app"),
                (".co.th", " ดอท co ดอท th"),
                (".go.th", " ดอท go ดอท th"),
                (".ac.th", " ดอท ac ดอท th"),
                (".in.th", " ดอท in ดอท th"),
                (".co.jp", " ดอท co ดอท jp"),
                (".cn", " ดอท cn"),
                (".th", " ดอท th"),
            ]
        )

        alpha_run = pynini.closure(NEMO_ALPHA, 1)
        digit_run = pynini.closure(NEMO_DIGIT @ digit_words, 1)
        domain_chunk = alpha_run | digit_run
        domain_body = domain_chunk + pynini.closure(pynini.union(hyphen, underscore) + domain_chunk)

        # Bare domains: app.dev, model.ai, tool.io, example.com
        bare_domain = (domain_body + tlds).optimize()

        # Emails: user@example.com, ab3.sdd.3@gmail.com
        email_part = alpha_run | digit_run
        email_sep = dot | hyphen | underscore
        email_username = email_part + pynini.closure(email_sep + email_part)
        email = (email_username + at + domain_body + tlds).optimize()

        # URLs: https://example.com/page, http://localhost:8080/api
        protocol = pynini.string_map(
            [
                ("http://", "http โคลอน สแลช สแลช "),
                ("https://", "https โคลอน สแลช สแลช "),
                ("HTTP://", "HTTP โคลอน สแลช สแลช "),
                ("HTTPS://", "HTTPS โคลอน สแลช สแลช "),
            ]
        )

        port = colon + digit_run
        url_host = domain_body + pynini.closure(dot + domain_body)
        url_path_elem = domain_body | (pynutil.insert("v ") + pynutil.delete("v") + (NEMO_DIGIT @ cardinal.all_positive))
        url_path = pynini.closure(slash + url_path_elem)

        url = (
            protocol
            + url_host
            + pynini.closure(tlds)
            + pynini.closure(port)
            + pynini.closure(url_path)
        ).optimize()

        all_electronic = (
            pynutil.add_weight(url, 1.01)
            | pynutil.add_weight(email, 1.02)
            | pynutil.add_weight(bare_domain, 1.03)
            | pynutil.add_weight(ipv4, 1.04)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_electronic)
            + pynutil.insert('"')
        ).optimize()
