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

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGITS,
    convert_space,
)
from .cardinal import CardinalFst, ODIA_CARDINALS_0_TO_99, SINGLE_DIGITS


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic expressions, URLs, emails, and serials in Odia:
        http://localhost:8080/api -> tokens { name: "http କୋଲନ୍ ସ୍ଲାସ୍ ସ୍ଲାସ୍ localhost କୋଲନ୍ ଆଠ ଶୂନ୍ୟ ଆଠ ଶୂନ୍ୟ ସ୍ଲାସ୍ api" }
        app.dev -> tokens { name: "app ଡଟ୍ dev" }
        model.ai -> tokens { name: "model ଡଟ୍ ai" }
        tool.io -> tokens { name: "tool ଡଟ୍ io" }
        ab3.sdd.3@gmail.com -> tokens { name: "ab ତିନି ଡଟ୍ sdd ଡଟ୍ ତିନି ଆଟ୍ gmail ଡଟ୍ com" }
        iOS 17.4.1 -> tokens { name: "iOS ସତର ଡଟ୍ ଚାରି ଡଟ୍ ଏକ" }
        v2.0 -> tokens { name: "v ଦୁଇ ଡଟ୍ ଶୂନ୍ୟ" }
        x^2 -> tokens { name: "ଏକ୍ସ ସ୍କୋୟାର" }
        y^3 -> tokens { name: "ୱାଇ କ୍ୟୁବ୍" }
        AB-123-CD -> tokens { name: "AB ଏକ ଦୁଇ ତିନି CD" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        self.cardinal = cardinal

        # Symbol mappings in electronic contexts
        electronic_symbols = pynini.string_map([
            (".", " ଡଟ୍ "),
            ("@", " ଆଟ୍ "),
            ("/", " ସ୍ଲାସ୍ "),
            (":", " କୋଲନ୍ "),
            ("-", " ଡ୍ୟାସ୍ "),
            ("_", " ଅଣ୍ଡରସ୍କୋର "),
            ("~", " ଟିଲ୍ଡେ "),
            ("?", " ପ୍ରଶ୍ନ ଚିହ୍ନ "),
            ("=", " ସମାନ "),
            ("&", " ଏବଂ "),
            ("%", " ପ୍ରତିଶତ "),
        ])

        # Power expressions
        powers = pynini.string_map([
            ("x^2", "ଏକ୍ସ ସ୍କୋୟାର"),
            ("x²", "ଏକ୍ସ ସ୍କୋୟାର"),
            ("y^3", "ୱାଇ କ୍ୟୁବ୍"),
            ("y³", "ୱାଇ କ୍ୟୁବ୍"),
            ("x^3", "ଏକ୍ସ କ୍ୟୁବ୍"),
            ("y^2", "ୱାଇ ସ୍କୋୟାର"),
        ])

        # Modern domain extensions: .dev, .ai, .io, .com, .org, .net, .edu, .gov, .in
        domains = pynini.string_map([
            (".dev", " ଡଟ୍ dev"),
            (".ai", " ଡଟ୍ ai"),
            (".io", " ଡଟ୍ io"),
            (".com", " ଡଟ୍ com"),
            (".org", " ଡଟ୍ org"),
            (".net", " ଡଟ୍ net"),
            (".edu", " ଡଟ୍ edu"),
            (".gov", " ଡଟ୍ gov"),
            (".in", " ଡଟ୍ in"),
        ])

        alpha = pynini.union(*string.ascii_letters)
        alpha_seq = pynini.closure(alpha, 1)

        # Bare domain names: e.g. app.dev, model.ai, tool.io
        bare_domain = (alpha_seq + domains).optimize()

        # Digit conversions in electronic strings:
        # Standalone numbers or IP numbers or port numbers (8080 -> ଆଠ ଶୂନ୍ୟ ଆଠ ଶୂନ୍ୟ)
        single_digit_word = pynini.string_map([(k, v) for k, v in SINGLE_DIGITS.items()])
        port_digits = (
            NORMALIZE_DIGITS
            @ (single_digit_word + pynini.closure(pynutil.insert(" ") + single_digit_word))
        ).optimize()

        # Alphanumeric tokens with digits inside: e.g. ab3 -> ab ତିନି
        char_unit = (
            alpha
            | (NORMALIZE_DIGITS @ pynini.string_map([(k, f" {v}") for k, v in SINGLE_DIGITS.items()]))
        )
        alphanum_word = alpha_seq + pynini.closure(char_unit)

        # Full email: e.g. ab3.sdd.3@gmail.com
        email_part = alphanum_word | alpha_seq | port_digits
        email_token = (
            email_part
            + pynini.closure(pynini.cross(".", " ଡଟ୍ ") + email_part)
            + pynini.cross("@", " ଆଟ୍ ")
            + alpha_seq
            + domains
        ).optimize()

        # Full URL: http://localhost:8080/api or https://example.com/a?b=1
        proto = pynini.cross("http://", "http କୋଲନ୍ ସ୍ଲାସ୍ ସ୍ଲାସ୍ ") | pynini.cross("https://", "https କୋଲନ୍ ସ୍ଲାସ୍ ସ୍ଲାସ୍ ")
        port_part = pynini.cross(":", " କୋଲନ୍ ") + port_digits
        path_piece = alpha | electronic_symbols | (pynutil.insert(" ") + (NORMALIZE_DIGITS @ single_digit_word) + pynutil.insert(" "))
        path_part = pynini.cross("/", " ସ୍ଲାସ୍ ") + pynini.closure(path_piece, 1)

        url_graph = (
            proto
            + (alpha_seq | bare_domain)
            + pynini.closure(port_part, 0, 1)
            + pynini.closure(path_part, 0, 1)
        ).optimize()

        # Version numbers: e.g. 17.4.1 -> ସତର ଡଟ୍ ଚାରି ଡଟ୍ ଏକ, v2.0 -> v ଦୁଇ ଡଟ୍ ଶୂନ୍ୟ
        num_part = (NORMALIZE_DIGITS @ cardinal.cardinal_numbers).optimize()
        version_num = (
            num_part
            + pynini.cross(".", " ଡଟ୍ ")
            + num_part
            + pynini.closure(pynini.cross(".", " ଡଟ୍ ") + num_part, 1)
        ).optimize()

        v_prefix = pynini.cross("v", "v ") | pynini.cross("V", "V ")
        v_version = (
            v_prefix
            + num_part
            + pynini.cross(".", " ଡଟ୍ ")
            + (num_part | (NORMALIZE_DIGITS @ pynini.string_map([(k, v) for k, v in SINGLE_DIGITS.items()])))
        ).optimize()

        # Dash serials: AB-123-CD -> AB ଏକ ଦୁଇ ତିନି CD
        dash_serial = (
            alpha_seq
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + port_digits
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + alpha_seq
        ).optimize()
        mixed_identifier = (
            alpha_seq + pynutil.insert(" ") + port_digits + pynini.closure(pynutil.insert(" ") + alpha_seq, 0, 1)
            | port_digits + pynutil.insert(" ") + alpha_seq
        )

        all_electronic = (
            powers
            | email_token
            | url_graph
            | bare_domain
            | v_version
            | version_num
            | dash_serial
            | mixed_identifier
        ).optimize()

        self.electronic_graph = all_electronic

        graph = pynutil.insert('name: "') + convert_space(all_electronic) + pynutil.insert('"')
        self.fst = graph.optimize()
