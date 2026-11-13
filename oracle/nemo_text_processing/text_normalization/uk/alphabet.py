# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

UK_LETTERS_LOWER = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
UK_LETTERS_UPPER = UK_LETTERS_LOWER.upper()

UK_LOWER_ALPHA = pynini.union(*UK_LETTERS_LOWER).optimize()
UK_UPPER_ALPHA = pynini.union(*UK_LETTERS_UPPER).optimize()
UK_APOSTROPHE = pynini.union("'", "ʼ", "’").optimize()
UK_ALPHA = (UK_LOWER_ALPHA | UK_UPPER_ALPHA | UK_APOSTROPHE).optimize()

# Mapping Latin letters to spoken Ukrainian phonetic names
LATIN_TO_UK_MAP = [
    ("a", "ей"), ("A", "ей"),
    ("b", "бі"), ("B", "бі"),
    ("c", "сі"), ("C", "сі"),
    ("d", "ді"), ("D", "ді"),
    ("e", "і"), ("E", "і"),
    ("f", "еф"), ("F", "еф"),
    ("g", "джі"), ("G", "джі"),
    ("h", "ейч"), ("H", "ейч"),
    ("i", "ай"), ("I", "ай"),
    ("j", "джей"), ("J", "джей"),
    ("k", "кей"), ("K", "кей"),
    ("l", "ель"), ("L", "ель"),
    ("m", "ем"), ("M", "ем"),
    ("n", "ен"), ("N", "ен"),
    ("o", "оу"), ("O", "оу"),
    ("p", "пі"), ("P", "пі"),
    ("q", "кю"), ("Q", "кю"),
    ("r", "ар"), ("R", "ар"),
    ("s", "ес"), ("S", "ес"),
    ("t", "ті"), ("T", "ті"),
    ("u", "ю"), ("U", "ю"),
    ("v", "ві"), ("V", "ві"),
    ("w", "дабл-ю"), ("W", "дабл-ю"),
    ("x", "ікс"), ("X", "ікс"),
    ("y", "вай"), ("Y", "вай"),
    ("z", "зед"), ("Z", "зед"),
]

TO_CYRILLIC = pynini.string_map(LATIN_TO_UK_MAP).optimize()
