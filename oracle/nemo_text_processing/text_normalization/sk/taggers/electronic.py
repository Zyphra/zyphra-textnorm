# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_ALPHA, NEMO_DIGIT, GraphFst


class ElectronicFst(GraphFst):
    """Productive Slovak URLs, email addresses, domains, IPv4 and versions."""

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)
        digit = pynini.string_map(list(zip("0123456789", ["nula", "jeden", "dva", "tri", "štyri", "päť", "šesť", "sedem", "osem", "deväť"])))
        number = digit + pynini.closure(pynutil.insert(" ") + digit)
        digit_piece = pynutil.insert(" ") + digit + pynutil.insert(" ")
        symbols = pynini.string_map([
            (".", " bodka "), ("/", " lomka "), (":", " dvojbodka "), ("-", " pomlčka "),
            ("_", " podčiarkovník "), ("?", " otáznik "), ("=", " rovná sa "), ("&", " a "),
            ("#", " mriežka "), ("%", " percent "), ("+", " plus "), ("~", " tilda "),
        ])
        reader = pynini.closure(NEMO_ALPHA | digit_piece | symbols, 1)
        protocol = pynini.string_map([
            ("http://", "h t t p dvojbodka lomka lomka "),
            ("https://", "h t t p s dvojbodka lomka lomka "),
            ("www.", "w w w bodka "),
        ])
        url = protocol + reader
        label = pynini.closure(NEMO_ALPHA | digit_piece | pynini.cross("-", " pomlčka "), 1)
        dot = pynini.cross(".", " bodka ")
        host = label + pynini.closure(dot + label) + dot + pynini.closure(NEMO_ALPHA, 2)
        local = pynini.closure(NEMO_ALPHA | digit_piece | pynini.string_map([
            (".", " bodka "), ("-", " pomlčka "), ("_", " podčiarkovník "), ("+", " plus "),
        ]), 1)
        email = local + pynini.cross("@", " zavináč ") + host
        octet_shape = pynini.union(*[str(value) for value in range(256)])
        octet = octet_shape @ number
        ipv4 = octet + (dot + octet) ** 3
        version = number + pynini.closure(dot + number, 2)
        grouped = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2) + pynini.closure("." + NEMO_DIGIT ** 3, 1)
        date_pattern = (
            pynini.closure(NEMO_DIGIT, 1, 2)
            + "."
            + pynini.closure(NEMO_DIGIT, 1, 2)
            + "."
            + pynini.closure(NEMO_DIGIT, 2, 4)
        )
        non_version = grouped | date_pattern
        version = pynini.difference(pynini.project(version, "input"), non_version) @ version
        prefixed = pynini.cross(pynini.union("v", "V"), "verzia ") + number + pynini.closure(dot + number, 1)
        named = pynini.closure(NEMO_ALPHA, 1) + pynini.accep(" ") + number + pynini.closure(dot + number, 1)
        self.fst = (url | email | host | ipv4 | version | prefixed | named).optimize()
