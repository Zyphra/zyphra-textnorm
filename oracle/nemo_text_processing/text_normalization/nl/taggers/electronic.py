# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import string

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Dutch electronic expressions (URLs, emails, domains).
    Handles:
    - info@example.com -> info apenstaartje example punt com
    - user123@gmail.com -> user een twee drie apenstaartje gmail punt com
    - https://example.com/a?b=1 -> h t t p s dubbele punt slash slash example punt com slash a vraagteken b is een
    - app.dev, model.ai, tool.io -> app punt dev, model punt a i, tool punt i o
    - http://localhost:8080/api -> h t t p dubbele punt slash slash localhost dubbele punt tachtig tachtig slash api
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        digit = cardinal.digit

        # Letter spelled out or word
        letter = pynini.union(*string.ascii_letters)
        word = pynini.closure(letter, 1)

        # Characters in electronic contexts:
        symbols = [
            ("@", " apenstaartje "),
            (".", " punt "),
            ("/", " slash "),
            ("://", " dubbele punt slash slash "),
            (":", " dubbele punt "),
            ("?", " vraagteken "),
            ("=", " is "),
            ("&", " en "),
            ("-", " streepje "),
            ("_", " laag streepje "),
            ("~", " tilde "),
            ("%", " procent "),
            ("#", " hekje "),
        ]
        symbol_map = pynini.string_map(symbols).optimize()

        # Domains
        domains = [
            (".nl", " punt n l"),
            (".be", " punt b e"),
            (".de", " punt d e"),
            (".com", " punt com"),
            (".org", " punt org"),
            (".net", " punt net"),
            (".edu", " punt edu"),
            (".gov", " punt gov"),
            (".dev", " punt dev"),
            (".ai", " punt a i"),
            (".io", " punt i o"),
            (".eu", " punt e u"),
            (".info", " punt info"),
        ]
        domain_map = pynini.string_map(domains).optimize()

        # Protocols
        protocols = [
            ("https://", "h t t p s dubbele punt slash slash "),
            ("http://", "h t t p dubbele punt slash slash "),
            ("ftp://", "f t p dubbele punt slash slash "),
            ("www.", "w w w punt "),
        ]
        protocol_map = pynini.string_map(protocols).optimize()


        char_component = (
            letter
            | digit
            | symbol_map
            | domain_map
        )

        # Full URL
        url_core = pynini.closure(char_component, 1)
        full_url = (
            protocol_map + url_core
            | url_core + domain_map + pynini.closure(char_component)
        )

        # Email
        email_username = pynini.closure(letter | digit | pynini.cross(".", " punt ") | pynini.cross("_", " laag streepje ") | pynini.cross("-", " streepje "), 1)
        email_domain = word + domain_map
        email_fst = (
            email_username
            + pynini.cross("@", " apenstaartje ")
            + email_domain
        )

        # Bare domains: app.dev, model.ai, tool.io
        bare_domain = word + domain_map

        self.spoken_electronic = (
            pynutil.add_weight(email_fst, 0.95)
            | pynutil.add_weight(full_url, 0.96)
            | pynutil.add_weight(bare_domain, 0.98)
        ).optimize()

        self.fst = wrap_name(self.spoken_electronic)
