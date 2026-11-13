# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_ALPHA, NEMO_DIGIT, GraphFst, convert_space
from nemo_text_processing.text_normalization.uk.alphabet import TO_CYRILLIC
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst


class ElectronicFst(GraphFst):
    """Productive Ukrainian email, URL, IPv4 and software-version readings."""

    def __init__(self, cardinal: CardinalFst = None):
        super().__init__(name="electronic", kind="classify")
        cardinal = cardinal or CardinalFst()
        digit = NEMO_DIGIT @ cardinal.graph
        digits = digit + pynini.closure(pynutil.insert(" ") + digit)
        letter = TO_CYRILLIC

        def sequence(atom):
            return atom + pynini.closure(pynutil.insert(" ") + atom)

        symbols = pynini.string_map([
            (":", "двокрапка"), ("/", "слеш"), (".", "крапка"),
            ("-", "дефіс"), ("_", "підкреслення"), ("~", "тильда"),
            ("?", "знак питання"), ("=", "дорівнює"), ("&", "і"),
            ("%", "відсоток"), ("#", "решітка"), ("+", "плюс"),
        ])
        dot = pynini.cross(".", " крапка ")
        label = sequence(letter | digit | pynini.cross("-", "дефіс"))
        tld_words = pynini.string_map([
            ("com", "ком"), ("org", "орг"), ("net", "нет"),
            ("edu", "еду"), ("gov", "гов"), ("ua", "ю ей"),
            ("dev", "дев"), ("ai", "ай"), ("io", "і о"), ("app", "апп"),
        ])
        tld = tld_words | pynutil.add_weight(pynini.closure(NEMO_ALPHA, 2) @ sequence(letter), 0.01)
        host = label + pynini.closure(dot + label) + dot + tld
        local = sequence(letter | digit | pynini.string_map([
            (".", "крапка"), ("-", "дефіс"), ("_", "підкреслення"), ("+", "плюс"),
        ]))
        email = local + pynini.cross("@", " собака ") + host
        protocol = pynini.string_map([
            ("http://", "ейч ті ті пі двокрапка слеш слеш "),
            ("https://", "ейч ті ті пі ес двокрапка слеш слеш "),
            ("www.", "дабл ю дабл ю дабл ю крапка "),
        ])
        url = protocol + sequence(letter | digit | symbols)
        octet = pynini.union(*[str(i) for i in range(256)]) @ cardinal.graph
        ipv4 = octet + (dot + octet)**3
        version = digits + pynini.closure(dot + digits, 2)
        grouped = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2) + pynini.closure("." + NEMO_DIGIT**3, 1)
        date = pynini.closure(NEMO_DIGIT, 1, 2) + "." + pynini.closure(NEMO_DIGIT, 1, 2) + "." + (NEMO_DIGIT**2 | NEMO_DIGIT**4)
        version = pynini.difference(pynini.project(version, "input"), grouped | date) @ version
        prefixed = pynini.cross(pynini.union("v", "V"), "версія ") + digits + pynini.closure(dot + digits, 1)
        named = pynini.closure(NEMO_ALPHA, 1) + pynini.accep(" ") + digits + pynini.closure(dot + digits, 1)
        spoken = (email | url | host | ipv4 | version | prefixed | named).optimize()
        self.fst = (pynutil.insert('name: "') + convert_space(spoken) + pynutil.insert('"')).optimize()
