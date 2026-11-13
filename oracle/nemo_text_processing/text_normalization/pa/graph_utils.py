# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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
import unicodedata
from typing import Dict

import pynini
from pynini.lib import byte, pynutil, utf8

NEMO_CHAR = utf8.VALID_UTF8_CHAR
NEMO_DIGIT = byte.DIGIT

NEMO_PA_DIGIT = pynini.union("੦", "੧", "੨", "੩", "੪", "੫", "੬", "੭", "੮", "੯").optimize()
NEMO_PA_NON_ZERO = pynini.union("੧", "੨", "੩", "੪", "੫", "੬", "੭", "੮", "੯").optimize()
NEMO_PA_ZERO = "੦"

# Combined Gurmukhi and ASCII digits for graphs that need to accept both
NEMO_ALL_DIGIT = pynini.union(NEMO_PA_DIGIT, NEMO_DIGIT).optimize()
NEMO_ALL_ZERO = pynini.union("੦", "0").optimize()
NEMO_ALL_NON_ZERO = pynini.union(NEMO_PA_NON_ZERO, "1", "2", "3", "4", "5", "6", "7", "8", "9").optimize()

# Gurmukhi letters, vowel signs and marks (U+0A00-U+0A7F, categories L and M)
NEMO_PA_CHAR = pynini.union(
    *[chr(i) for i in range(0x0A00, 0x0A80) if unicodedata.category(chr(i))[0] in "LM"]
).optimize()

# Symbol constants
PA_BY = "ਬਾਈ"
LOWERCASE_X = "x"
UPPERCASE_X = "X"
ASTERISK = "*"
HYPHEN = "-"
SLASH = "/"
COMMA = ","
PERIOD = "."
PA_DANDA = "।"
PA_DOUBLE_DANDA = "॥"

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
    pynutil.delete("preserve_order:")
    + delete_space
    + pynutil.delete("true")
    + delete_space
    | pynutil.delete("preserve_order:")
    + delete_space
    + pynutil.delete("false")
    + delete_space
)

MIN_NEG_WEIGHT = -0.0001
MIN_POS_WEIGHT = 0.0001
INPUT_CASED = "cased"
INPUT_LOWER_CASED = "lower_cased"
MINUS = "ਰਿਣ "


def capitalized_input_graph(
    graph: 'pynini.FstLike', original_graph_weight: float = None, capitalized_graph_weight: float = None
) -> 'pynini.FstLike':
    """
    Given a graph that operates on lower case text, returns a graph that accepts both lower-cased and
    capitalized input.

    Args:
        graph: Fst
        original_graph_weight: weight to add to the original graph
        capitalized_graph_weight: weight to add to the capitalized graph
    """
    capitalized_graph = (
        pynini.compose(TO_LOWER, graph)
        | pynini.compose(TO_LOWER + pynini.closure(NEMO_CHAR), graph)
    )

    if capitalized_graph_weight:
        capitalized_graph = pynutil.add_weight(capitalized_graph, capitalized_graph_weight)
    if original_graph_weight:
        graph = pynutil.add_weight(graph, original_graph_weight)

    graph |= capitalized_graph
    return graph


def generator_main(file_name: str, graphs: Dict[str, 'pynini.FstLike']):
    """
    Exports graph as OpenFst finite state archive (FAR) file with proper permissions.

    Args:
        file_name: exported file name
        graphs: Keys are graph names and values are FSTs
    """
    exporter = pynini.Far(file_name, mode="w")
    for k, v in graphs.items():
        exporter[k] = v
    exporter.close()
    logging.info(f'Created {file_name}')


def convert_space(fst) -> 'pynini.FstLike':
    """
    Converts space to non-breaking space, which is required for NeMo verbalizer.

    Args:
        fst: input fst

    Returns:
        fst: output fst
    """
    return fst @ pynini.cdrewrite(pynini.cross(NEMO_SPACE, NEMO_NON_BREAKING_SPACE), "", "", NEMO_SIGMA)


class GraphFst:
    """
    Base class for all grammar fsts.

    Args:
        name: name of grammar
        kind: tagger or verbalizer
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, name: str, kind: str, deterministic: bool = True):
        self.name = name
        self.kind = kind
        self.deterministic = deterministic
        self.fst = None

    def add_tokens(self, fst: 'pynini.FstLike') -> 'pynini.FstLike':
        """
        Adds tokens tag and name to input fst.

        Args:
            fst: input fst

        Returns:
            fst: output fst
        """
        return pynutil.insert(f"{self.name} {{ ") + fst + pynutil.insert(" }")

    def delete_tokens(self, fst: 'pynini.FstLike') -> 'pynini.FstLike':
        """
        Deletes tokens tag and name from input fst.

        Args:
            fst: input fst

        Returns:
            fst: output fst
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
