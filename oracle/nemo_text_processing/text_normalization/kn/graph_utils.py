# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

import logging
import os
import string
from pathlib import Path
from typing import Dict

import pynini
from pynini import Far
from pynini.lib import byte, pynutil, utf8

NEMO_CHAR = utf8.VALID_UTF8_CHAR
NEMO_DIGIT = byte.DIGIT

NEMO_KN_DIGIT = pynini.union("೦", "೧", "೨", "೩", "೪", "೫", "೬", "೭", "೮", "೯").optimize()
NEMO_KN_NON_ZERO = pynini.union("೧", "೨", "೩", "೪", "೫", "೬", "೭", "೮", "೯").optimize()
NEMO_KN_ZERO = "೦"
# Combined Kannada and ASCII digits for graphs that need to accept both
NEMO_ALL_DIGIT = pynini.union(NEMO_KN_DIGIT, NEMO_DIGIT).optimize()
NEMO_ALL_ZERO = pynini.union("೦", "0").optimize()
NEMO_ALL_NON_ZERO = pynini.union(NEMO_KN_NON_ZERO, "1", "2", "3", "4", "5", "6", "7", "8", "9").optimize()
# Kannada digits rewritten to ASCII; ASCII digits pass through
TO_ASCII_DIGIT = pynini.union(
    *[pynini.cross(k, a) for k, a in zip("೦೧೨೩೪೫೬೭೮೯", "0123456789")], NEMO_DIGIT
).optimize()

# Kannada letters, vowel signs and virama (U+0C80-U+0CFF without digits 0x0CE6..0x0CEF)
NEMO_KN_CHAR = pynini.union(
    *[chr(i) for i in range(0x0C80, 0x0D00) if not 0x0CE6 <= i <= 0x0CEF], "\u200c", "\u200d"
).optimize()

# Symbol constants
COMMA = ","
PERIOD = "."
HYPHEN = "-"
SLASH = "/"

NEMO_LOWER = pynini.union(*string.ascii_lowercase).optimize()
NEMO_UPPER = pynini.union(*string.ascii_uppercase).optimize()
NEMO_ALPHA = pynini.union(NEMO_LOWER, NEMO_UPPER).optimize()
NEMO_HEX = pynini.union(*string.hexdigits).optimize()
NEMO_NON_BREAKING_SPACE = u"\u00a0"
NEMO_SPACE = " "
NEMO_WHITE_SPACE = pynini.union(" ", "\t", "\n", "\r", u"\u00a0").optimize()
NEMO_NOT_SPACE = pynini.difference(NEMO_CHAR, NEMO_WHITE_SPACE).optimize()
NEMO_NOT_QUOTE = pynini.difference(NEMO_CHAR, r'"').optimize()
TO_LOWER = pynini.union(*[pynini.cross(x, y) for x, y in zip(string.ascii_uppercase, string.ascii_lowercase)])
TO_UPPER = pynini.invert(TO_LOWER)
NEMO_SIGMA = pynini.closure(NEMO_CHAR)

delete_space = pynutil.delete(pynini.closure(NEMO_WHITE_SPACE))
delete_zero_or_one_space = pynutil.delete(pynini.closure(NEMO_WHITE_SPACE, 0, 1))
insert_space = pynutil.insert(" ")
delete_extra_space = pynini.cross(pynini.closure(NEMO_WHITE_SPACE, 1), " ")
delete_preserve_order = pynini.closure(
    pynutil.delete("preserve_order: true")
    | pynutil.delete("preserve_order: false")
    | pynutil.delete(NEMO_SPACE)
    | pynutil.delete(NEMO_NON_BREAKING_SPACE)
)

MIN_NEG_WEIGHT = -0.0001
MIN_POS_WEIGHT = 0.0001
INPUT_CASED = "cased"
INPUT_LOWER_CASED = "lower_cased"
MINUS = "ಋಣ "


def capitalized_input_graph(
    graph: 'pynini.FstLike', original_graph_weight: float = None, capitalized_graph_weight: float = None
) -> 'pynini.FstLike':
    """
    Selectively capitalizes the first character of the input graph.
    """
    first_char = pynini.closure(NEMO_CHAR, 1, 1)
    capitalized_first_char = first_char @ TO_UPPER
    rest = pynini.closure(NEMO_CHAR)
    capitalized_graph = capitalized_first_char + rest
    capitalized_graph = capitalized_graph @ graph

    if original_graph_weight is not None:
        graph = pynutil.add_weight(graph, original_graph_weight)
    if capitalized_graph_weight is not None:
        capitalized_graph = pynutil.add_weight(capitalized_graph, capitalized_graph_weight)

    graph |= capitalized_graph
    return graph


def generator_main(file_name: str, graphs: Dict[str, 'pynini.FstLike']):
    """
    Exports dictionary of (name, [FST]) to FAR file
    """
    out_dir = os.path.dirname(file_name)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    exporter = pynini.Far(file_name, mode="w")
    for k, v in graphs.items():
        exporter[k] = v.optimize()
    logging.info(f'Created {file_name}')


def convert_space(fst) -> 'pynini.FstLike':
    """
    Converts regular space to non-breaking space
    """
    return fst @ pynini.cdrewrite(pynini.cross(NEMO_SPACE, NEMO_NON_BREAKING_SPACE), "", "", NEMO_SIGMA)


class GraphFst:
    """
    Base class for all grammar fsts.
    """

    def __init__(self, name: str, kind: str, deterministic: bool = True):
        self.name = name
        self.kind = kind
        self._fst = None
        self.deterministic = deterministic

        self.far_path = Path(os.path.dirname(__file__) + '/grammars/' + kind + '/' + name + '.far')
        if self.far_exist():
            self._fst = Far(self.far_path, mode="r", arc_type="standard", far_type="default").get_fst()

    def far_exist(self) -> bool:
        return self.far_path.exists()

    @property
    def fst(self) -> 'pynini.FstLike':
        return self._fst

    @fst.setter
    def fst(self, fst):
        self._fst = fst

    def add_tokens(self, fst) -> 'pynini.FstLike':
        return pynutil.insert(f"{self.name} {{ ") + fst + pynutil.insert(" }")

    def delete_tokens(self, fst) -> 'pynini.FstLike':
        res = (
            pynutil.delete(f"{self.name}")
            + delete_space
            + pynutil.delete("{")
            + delete_space
            + fst
            + delete_space
            + pynutil.delete("}")
        )
        return res @ pynini.cdrewrite(pynini.cross(u"\u00a0", " "), "", "", NEMO_SIGMA)
