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
from pynini.export import export
from pynini.lib import byte, pynutil, utf8

NEMO_CHAR = utf8.VALID_UTF8_CHAR
NEMO_DIGIT = byte.DIGIT

NEMO_GU_DIGIT = pynini.union("૦", "૧", "૨", "૩", "૪", "૫", "૬", "૭", "૮", "૯").optimize()
NEMO_GU_NON_ZERO = pynini.union("૧", "૨", "૩", "૪", "૫", "૬", "૭", "૮", "૯").optimize()
NEMO_GU_ZERO = "૦"

# Combined Gujarati and ASCII digits for graphs that need to accept both
NEMO_ALL_DIGIT = pynini.union(NEMO_GU_DIGIT, NEMO_DIGIT).optimize()
NEMO_ALL_ZERO = pynini.union("૦", "0").optimize()
NEMO_ALL_NON_ZERO = pynini.union(NEMO_GU_NON_ZERO, "1", "2", "3", "4", "5", "6", "7", "8", "9").optimize()

GU_DODH = "દોઢ"  # 1.5
GU_ADHI = "અઢી"  # 2.5
GU_SAVVA = "સવા"  # quarter more (1.25)
GU_SADA = "સાડા"  # half more (X.5)
GU_PONA = "પોણા"  # quarter less (0.75)

# Gujarati decimal representations
GU_POINT_FIVE = ".૫"
GU_ONE_POINT_FIVE = "૧.૫"
GU_TWO_POINT_FIVE = "૨.૫"
GU_DECIMAL_25 = ".૨૫"
GU_DECIMAL_75 = ".૭૫"

# Arabic/ASCII decimal representations
EN_POINT_FIVE = ".5"
EN_ONE_POINT_FIVE = "1.5"
EN_TWO_POINT_FIVE = "2.5"
EN_DECIMAL_25 = ".25"
EN_DECIMAL_75 = ".75"

# Combined Gujarati and ASCII decimal patterns
POINT_FIVE = pynini.union(GU_POINT_FIVE, EN_POINT_FIVE).optimize()
ONE_POINT_FIVE = pynini.union(GU_ONE_POINT_FIVE, EN_ONE_POINT_FIVE).optimize()
TWO_POINT_FIVE = pynini.union(GU_TWO_POINT_FIVE, EN_TWO_POINT_FIVE).optimize()
DECIMAL_25 = pynini.union(GU_DECIMAL_25, EN_DECIMAL_25).optimize()
DECIMAL_75 = pynini.union(GU_DECIMAL_75, EN_DECIMAL_75).optimize()

# Symbol constants
GU_BY = "બાય"
LOWERCASE_X = "x"
UPPERCASE_X = "X"
ASTERISK = "*"
HYPHEN = "-"
SLASH = "/"
COMMA = ","
PERIOD = "."
GU_PERIOD = "।"

NEMO_LOWER = pynini.union(*string.ascii_lowercase).optimize()
NEMO_UPPER = pynini.union(*string.ascii_uppercase).optimize()
NEMO_ALPHA = pynini.union(NEMO_LOWER, NEMO_UPPER).optimize()
NEMO_HEX = pynini.union(*string.hexdigits).optimize()
NEMO_NON_BREAKING_SPACE = "\u00a0"
NEMO_SPACE = " "
NEMO_WHITE_SPACE = pynini.union(" ", "\t", "\n", "\r", "\u00a0").optimize()
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
    | pynutil.delete("field_order:")
    + delete_space
    + pynutil.delete('"')
    + NEMO_NOT_QUOTE
    + pynutil.delete('"')
    + delete_space
)

MIN_NEG_WEIGHT = -0.0001
MIN_POS_WEIGHT = 0.0001
INPUT_CASED = "cased"
INPUT_LOWER_CASED = "lower_cased"
MINUS = pynini.accep("નકારાત્મક ").optimize()


def capitalized_input_graph(
    graph: 'pynini.FstLike', original_graph_weight: float = None, capitalized_graph_weight: float = None
) -> 'pynini.FstLike':
    """
    Transforms graph to accept capitalized input.
    """
    capitalized_graph = (TO_LOWER + NEMO_SIGMA) @ graph
    if original_graph_weight is not None:
        graph = pynutil.add_weight(graph, original_graph_weight)
    if capitalized_graph_weight is not None:
        capitalized_graph = pynutil.add_weight(capitalized_graph, capitalized_graph_weight)
    return pynini.union(graph, capitalized_graph).optimize()


def generator_main(file_name: str, graphs: Dict[str, 'pynini.FstLike']):
    """
    Exports graph to OpenFst finite state archive (FAR) file with proper keys.
    """
    out_dir = os.path.dirname(file_name)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    exporter = export.Exporter(file_name)
    for k, v in graphs.items():
        exporter[k] = v.optimize()
    exporter.close()
    logging.info(f"Created {file_name}")


def convert_space(fst) -> 'pynini.FstLike':
    """
    Converts breaking spaces to non-breaking spaces.
    """
    return fst @ pynini.cdrewrite(pynini.cross(NEMO_SPACE, NEMO_NON_BREAKING_SPACE), "", "", NEMO_SIGMA)


class GraphFst:
    """
    Base class for all grammar fsts.

    Args:
        name: name of grammar class
        kind: either 'classify' or 'verbalize'
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, name: str, kind: str, deterministic: bool = True):
        self.name = name
        self.kind = kind
        self._fst = None
        self.deterministic = deterministic

        self.far_path = Path(os.path.dirname(__file__) + "/grammars/" + kind + "/" + name + ".far")
        if self.far_exist():
            self._fst = Far(self.far_path, mode="r", arc_type="standard", far_type="default").get_fst()

    def far_exist(self) -> bool:
        """
        Returns true if FAR can be loaded
        """
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
        Deletes class name wrap around output of given fst
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
        return res @ pynini.cdrewrite(pynini.cross("\u00a0", " "), "", "", NEMO_SIGMA)
