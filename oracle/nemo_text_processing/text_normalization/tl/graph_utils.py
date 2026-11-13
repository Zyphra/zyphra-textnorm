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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_CHAR


def get_linker_fst() -> pynini.Fst:
    """
    Returns an FST that applies Tagalog linker (-ng / na) morphology to spoken numbers:
      - Ends in vowel (a, e, i, o, u): append 'ng' (e.g., 'dalawa' -> 'dalawang', 'sampu' -> 'sampung')
      - Ends in 'n': convert final 'n' to 'ng' (e.g., 'daan' -> 'daang', 'milyon' -> 'milyong')
      - Ends in other consonant: append ' na' (e.g., 'apat' -> 'apat na', 'anim' -> 'anim na', 'siyam' -> 'siyam na')
    """
    vowels = pynini.union("a", "e", "i", "o", "u", "A", "E", "I", "O", "U")
    consonants_no_n = pynini.union(
        "b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "p", "q", "r", "s", "t", "v", "w", "x", "y", "z",
        "B", "C", "D", "F", "G", "H", "J", "K", "L", "M", "P", "Q", "R", "S", "T", "V", "W", "X", "Y", "Z",
    )
    all_chars = NEMO_CHAR | pynini.union("'", "-", " ")
    sigma = pynini.closure(all_chars)

    link_vowel = sigma + vowels + pynutil.insert("ng")
    link_n = sigma + pynini.cross(pynini.union("n", "N"), "ng")
    link_cons = sigma + consonants_no_n + pynutil.insert(" na")

    return (link_vowel | link_n | link_cons).optimize()
