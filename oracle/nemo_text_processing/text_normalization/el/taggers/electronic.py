# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Greek electronic tokens (emails, URLs, domains, IP addresses):
        "info@example.com" -> info παπάκι example τελεία com
        "ab3.sdd.3@gmail.com" -> ab τρία τελεία sdd τελεία τρία παπάκι gmail τελεία com
        "https://example.com/a?b=1" -> https κάθετος κάθετος example τελεία com κάθετος a ερωτηματικό b ίσον ένα
        "http://localhost:8080/api" -> http κάθετος κάθετος localhost άνω κάτω τελεία οκτώ μηδέν οκτώ μηδέν κάθετος api
        "app.dev" -> app τελεία dev
        "model.ai" -> model τελεία ai
        "tool.io" -> tool τελεία io
        "192.168.1.1" -> ένα εννέα δύο τελεία ένα έξι οκτώ τελεία ένα τελεία ένα
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        digit_pairs = [
            ("0", "μηδέν"),
            ("1", "ένα"),
            ("2", "δύο"),
            ("3", "τρία"),
            ("4", "τέσσερα"),
            ("5", "πέντε"),
            ("6", "έξι"),
            ("7", "επτά"),
            ("8", "οκτώ"),
            ("9", "εννέα"),
        ]
        digit = pynini.string_map(digit_pairs)

        sym_map = pynini.string_map(
            [
                ("@", " παπάκι "),
                (".", " τελεία "),
                ("/", " κάθετος "),
                ("//", " κάθετος κάθετος "),
                (":", " άνω κάτω τελεία "),
                ("?", " ερωτηματικό "),
                ("=", " ίσον "),
                ("&", " και "),
                ("-", " παύλα "),
                ("_", " κάτω παύλα "),
            ]
        )

        char_or_digit = NEMO_ALPHA | (digit + pynutil.insert(" "))
        letters = pynini.closure(NEMO_ALPHA, 1)
        word_or_digit = pynini.closure(char_or_digit, 1)

        # 1. Emails: username @ domain . tld
        email_sep = pynini.string_map([(".", " τελεία "), ("_", " κάτω παύλα "), ("-", " παύλα ")])
        email_user_chunk = word_or_digit
        email_user = email_user_chunk + pynini.closure(email_sep + email_user_chunk)
        at_sign = pynini.cross("@", " παπάκι ")
        email_domain = letters + pynini.cross(".", " τελεία ") + letters
        email_graph = email_user + at_sign + email_domain

        # 2. URLs with protocol: http://, https://
        protocol = pynini.cross("https://", "https κάθετος κάθετος ") | pynini.cross("http://", "http κάθετος κάθετος ")
        url_symbol = pynini.string_map(
            [
                (".", " τελεία "),
                ("/", " κάθετος "),
                (":", " άνω κάτω τελεία "),
                ("?", " ερωτηματικό "),
                ("=", " ίσον "),
                ("&", " και "),
                ("-", " παύλα "),
                ("_", " κάτω παύλα "),
            ]
        )
        url_chunk = word_or_digit | (digit + pynutil.insert(" "))
        url_part = url_chunk + pynini.closure(url_symbol + url_chunk)
        url_graph = protocol + url_part

        # 3. Bare modern domains: app.dev, model.ai, tool.io, zonos.org, test.com
        tlds = pynini.string_map(
            [
                ("dev", "dev"),
                ("ai", "ai"),
                ("io", "io"),
                ("com", "com"),
                ("org", "org"),
                ("net", "net"),
                ("gr", "gr"),
                ("edu", "edu"),
                ("gov", "gov"),
            ]
        )
        domain_graph = letters + pynini.cross(".", " τελεία ") + tlds

        # 4. IPv4 Addresses: 192.168.1.1
        # Each byte: 1 to 3 digits read as digits
        byte_part = digit + pynini.closure(pynutil.insert(" ") + digit, 0, 2)
        ip_dot = pynini.cross(".", " τελεία ")
        ip_graph = byte_part + ip_dot + byte_part + ip_dot + byte_part + ip_dot + byte_part

        all_electronic = (email_graph | url_graph | domain_graph | ip_graph).optimize()
        self.fst = all_electronic
