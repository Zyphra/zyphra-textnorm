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

import unicodedata

import pynini
from pynini.lib import byte, pynutil, utf8

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    NEMO_WHITE_SPACE,
    NEMO_NOT_SPACE,
    NEMO_NOT_QUOTE,
    convert_space,
    delete_extra_space,
    delete_space,
    insert_space,
    generator_main,
)

OR_DIGITS = ["୦", "୧", "୨", "୩", "୪", "୫", "୬", "୭", "୮", "୯"]
ASCII_DIGITS = [str(i) for i in range(10)]

NEMO_OR_DIGIT = pynini.union(*OR_DIGITS).optimize()
NEMO_OR_NON_ZERO = pynini.union(*OR_DIGITS[1:]).optimize()
NEMO_OR_ZERO = pynini.accep("୦").optimize()

NEMO_ALL_DIGIT = pynini.union(NEMO_OR_DIGIT, NEMO_DIGIT).optimize()
NEMO_ALL_ZERO = pynini.union("୦", "0").optimize()
NEMO_ALL_NON_ZERO = pynini.union(NEMO_OR_NON_ZERO, *ASCII_DIGITS[1:]).optimize()

# Map Odia digits to ASCII digits
_map_or_to_ascii = pynini.union(*[pynini.cross(o, a) for o, a in zip(OR_DIGITS, ASCII_DIGITS)])
_map_ascii_to_ascii = pynini.union(*[pynini.cross(a, a) for a in ASCII_DIGITS])
NORMALIZE_DIGIT = (_map_or_to_ascii | _map_ascii_to_ascii).optimize()
NORMALIZE_DIGITS = pynini.closure(NORMALIZE_DIGIT, 1).optimize()

# Odia letters (U+0B00 to U+0B7F)
NEMO_OR_CHAR = pynini.union(
    *[chr(i) for i in range(0x0B00, 0x0B80) if unicodedata.category(chr(i))[0] in "LM"]
).optimize()

OR_DANDA = "।"
OR_DOUBLE_DANDA = "॥"
