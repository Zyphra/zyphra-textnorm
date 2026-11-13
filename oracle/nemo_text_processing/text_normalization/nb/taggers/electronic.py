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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)


class ElectronicFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål electronic strings, URLs, domains, emails,
    IP addresses, version numbers, alphanumerics, and variable powers.
    e.g. http://localhost:8080/api -> h t t p kolon dobbelt skråstrek localhost kolon åtte null åtte null skråstrek a p i
         app.dev -> app punktum d e v
         model.ai -> model punktum a i
         tool.io -> tool punktum i o
         ab3.sdd.3@gmail.com -> a b tre punktum s d d punktum tre krøllalfa gmail punktum com
         192.168.1.1 -> hundre og nittito punktum hundre og sekstiåtte punktum en punktum en
         iOS 17.4.1 -> iOS sytten punktum fire punktum en
         v2.0 -> v to punktum null
         x^2 -> x i andre
         y^3 -> y i tredje
         2^3 -> to opphøyd i tre
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        card = cardinal.cardinal_masculine

        # Digit spelling
        single_digit = pynini.string_map(
            [
                ("0", "null"),
                ("1", "en"),
                ("2", "to"),
                ("3", "tre"),
                ("4", "fire"),
                ("5", "fem"),
                ("6", "seks"),
                ("7", "sju"),
                ("8", "åtte"),
                ("9", "ni"),
            ]
        )

        # Port pronunciation (digit-by-digit: 8080 -> åtte null åtte null)
        port_digits = pynini.closure(single_digit + pynutil.insert(" "), 1) + single_digit

        # 1. IP Addresses (e.g. 192.168.1.1)
        dot_punkt = pynini.cross(".", " punktum ")
        octet = pynini.closure(NEMO_DIGIT, 1, 3) @ card
        ip_graph = octet + dot_punkt + octet + dot_punkt + octet + dot_punkt + octet
        # 2. URLs (e.g. http://localhost:8080/api)
        protocol = (
            pynini.cross("http://", "h t t p kolon dobbelt skråstrek ")
            | pynini.cross("https://", "h t t p s kolon dobbelt skråstrek ")
        )
        url_symbols = pynini.string_map([
            (".", " punktum "), (":", " kolon "), ("/", " skråstrek "),
            ("?", " spørsmålstegn "), ("=", " lik "), ("&", " og "), ("#", " nummer "),
            ("%", " prosent "), ("-", " bindestrek "), ("_", " understrek "),
            ("+", " pluss "), ("~", " tilde "),
        ])
        digit_word = pynutil.insert(" ") + single_digit + pynutil.insert(" ")
        url_piece = NEMO_ALPHA | digit_word | url_symbols
        url_graph = protocol + pynini.closure(url_piece, 1)

        # 3. Modern bare domains: app.dev, model.ai, tool.io
        domain_endings = (
            pynini.cross(".dev", " punktum d e v")
            | pynini.cross(".ai", " punktum a i")
            | pynini.cross(".io", " punktum i o")
            | pynini.cross(".no", " punktum n o")
            | pynini.cross(".com", " punktum com")
            | pynini.cross(".org", " punktum org")
        )
        domain_graph = pynini.closure(NEMO_ALPHA, 1) + domain_endings

        # 4. Emails: ab3.sdd.3@gmail.com
        local_piece = NEMO_ALPHA | digit_word | (
            pynini.string_map([(".", " punktum "), ("_", " understrek "), ("-", " bindestrek "), ("+", " pluss ")])
        )
        local = pynini.closure(local_piece, 1)
        host_label = pynini.closure(NEMO_ALPHA | digit_word | pynini.cross("-", " bindestrek "), 1)
        host = host_label + pynini.closure(dot_punkt + host_label, 1)
        email_graph = local + pynini.cross("@", " krøllalfa ") + host

        # 5. Version numbers & Alphanumerics
        # iOS 17.4.1 -> iOS sytten punktum fire punktum en
        ver_num = octet + dot_punkt + octet + dot_punkt + octet
        ver_ios = pynini.cross("iOS ", "iOS ") + ver_num
        ver_v = pynini.cross("v", "v ") + octet + dot_punkt + single_digit
        ver_3 = octet + dot_punkt + octet + dot_punkt + octet
        # Alphanumerics: 5G, 4K, CO2, A4, BA249, COVID-19, AB-123-CD
        letters = pynini.closure(NEMO_ALPHA, 1)
        identifier_join = pynini.cross("-", " bindestrek ") | pynutil.insert(" ")
        alphanumerics = (
            letters + pynini.closure(identifier_join + card + pynini.closure(identifier_join + letters, 0, 1), 1)
            | card + pynutil.insert(" ") + letters
        )

        # Powers: x^2 -> x i andre, y^3 -> y i tredje, 2^3 -> to opphøyd i tre
        base = card | NEMO_ALPHA
        powers = base + (
            pynini.cross("^2", " i andre")
            | pynini.cross("^3", " i tredje")
            | pynini.cross("^", " opphøyd i ") + card
        )

        all_electronic = (
            url_graph
            | email_graph
            | domain_graph
            | pynutil.add_weight(ip_graph, -0.1)
            | ver_ios
            | ver_v
            | ver_3
            | alphanumerics
            | powers
        )

        self.graph = all_electronic.optimize()
        self.fst = self.graph
