# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
# Copyright 2015 and onwards Google, Inc.
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
from pynini.export import export
from pynini.lib import byte, pynutil, utf8

NEMO_CHAR = utf8.VALID_UTF8_CHAR
NEMO_DIGIT = byte.DIGIT

NEMO_ML_DIGIT = pynini.union("൦", "൧", "൨", "൩", "൪", "൫", "൬", "൭", "൮", "൯").optimize()
NEMO_ML_NON_ZERO = pynini.union("൧", "൨", "൩", "൪", "൫", "൬", "൭", "൮", "൯").optimize()
NEMO_ML_ZERO = "൦"

# Combined Malayalam and ASCII digits
NEMO_ALL_DIGIT = pynini.union(NEMO_ML_DIGIT, NEMO_DIGIT).optimize()
NEMO_ALL_ZERO = pynini.union("൦", "0").optimize()
NEMO_ALL_NON_ZERO = pynini.union(NEMO_ML_NON_ZERO, "1", "2", "3", "4", "5", "6", "7", "8", "9").optimize()

# Malayalam digits rewritten to ASCII; ASCII digits pass through
TO_ASCII_DIGIT = pynini.union(
    *[pynini.cross(m, a) for m, a in zip("൦൧൨൩൪൫൬൭൮൯", "0123456789")], NEMO_DIGIT
).optimize()

# Malayalam letters, vowel signs and virama (U+0D00-U+0D7F without digits) + ZWNJ/ZWJ
NEMO_ML_CHAR = pynini.union(
    *[chr(i) for i in range(0x0D00, 0x0D80) if not 0x0D66 <= i <= 0x0D6F], "\u200c", "\u200d"
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
NEMO_NON_BREAKING_SPACE = "\u00a0"
NEMO_SPACE = " "
NEMO_WHITE_SPACE = pynini.union(" ", "\t", "\n", "\r", "\u00a0").optimize()
NEMO_NOT_SPACE = pynini.difference(NEMO_CHAR, NEMO_WHITE_SPACE).optimize()
NEMO_NOT_QUOTE = pynini.difference(NEMO_CHAR, r'"').optimize()
NEMO_PUNCT = pynini.union(*map(pynini.escape, string.punctuation)).optimize()
TO_LOWER = pynini.union(*[pynini.cross(x, y) for x, y in zip(string.ascii_uppercase, string.ascii_lowercase)])
TO_UPPER = pynini.invert(TO_LOWER)
NEMO_SIGMA = pynini.closure(NEMO_CHAR)

delete_space = pynutil.delete(pynini.closure(NEMO_WHITE_SPACE))
delete_zero_or_one_space = pynutil.delete(pynini.closure(NEMO_WHITE_SPACE, 0, 1))
insert_space = pynutil.insert(" ")
delete_extra_space = pynini.cross(pynini.closure(NEMO_WHITE_SPACE, 1), " ")

MIN_NEG_WEIGHT = -0.0001
MIN_POS_WEIGHT = 0.0001
INPUT_CASED = "cased"
INPUT_LOWER_CASED = "lower_cased"
MINUS = "മൈനസ് "


def capitalized_input_graph(
    graph: 'pynini.FstLike', original_graph_weight: float = None, capitalized_graph_weight: float = None
) -> 'pynini.FstLike':
    """
    Allow graph input to be capitalized, e.g. for ITN
    """
    capitalized_graph = pynini.compose(TO_LOWER + NEMO_SIGMA, graph).optimize()

    if original_graph_weight is not None:
        graph = pynutil.add_weight(graph, weight=original_graph_weight)

    if capitalized_graph_weight is not None:
        capitalized_graph = pynutil.add_weight(capitalized_graph, weight=capitalized_graph_weight)

    graph |= capitalized_graph
    return graph


def generator_main(file_name: str, graphs: Dict[str, 'pynini.FstLike']):
    """
    Exports graph as OpenFst finite state archive (FAR) file with given file name and rule name.
    """
    exporter = export.Exporter(file_name)
    for rule, graph in graphs.items():
        exporter[rule] = graph.optimize()
    exporter.close()
    logging.info(f'Created {file_name}')


def convert_space(fst) -> 'pynini.FstLike':
    """
    Converts space to nonbreaking space for tokens value serialization.
    """
    return fst @ pynini.cdrewrite(pynini.cross(NEMO_SPACE, NEMO_NON_BREAKING_SPACE), "", "", NEMO_SIGMA)


class GraphFst:
    """
    Base class for all grammar fsts.

    Args:
        name: name of grammar class
        kind: either 'classify' or 'verbalize'
        deterministic: if True will provide a single transduction option
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
        """
        Wraps class name around given fst
        """
        return pynutil.insert(f"{self.name} {{ ") + fst + pynutil.insert(" }")

    def delete_tokens(self, fst) -> 'pynini.FstLike':
        """
        Deletes class name wrapper around output of given fst
        """
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
