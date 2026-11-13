# Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.vi.graph_utils import NEMO_SPACE, GraphFst
from nemo_text_processing.text_normalization.vi.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.vi.utils import get_abs_path, load_labels


UNICODE_FRACTIONS = [
    ("½", "một", "hai"),
    ("¼", "một", "tư"),
    ("¾", "ba", "tư"),
    ("⅓", "một", "ba"),
    ("⅔", "hai", "ba"),
    ("⅕", "một", "năm"),
    ("⅖", "hai", "năm"),
    ("⅗", "ba", "năm"),
    ("⅘", "bốn", "năm"),
    ("⅙", "một", "sáu"),
    ("⅚", "năm", "sáu"),
    ("⅛", "một", "tám"),
    ("⅜", "ba", "tám"),
    ("⅝", "năm", "tám"),
    ("⅞", "bảy", "tám"),
    ("⅐", "một", "bảy"),
    ("⅑", "một", "chín"),
    ("⅒", "một", "mười"),
]

class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Vietnamese fraction numbers, e.g.
        23 1/5 -> fraction { integer_part: "hai mươi ba" numerator: "một" denominator: "năm" }
        3/9 -> fraction { numerator: "ba" denominator: "chín" }
        1/4 -> fraction { numerator: "một" denominator: "tư" }

    Args:
        cardinal: CardinalFst for converting numbers to Vietnamese words
        deterministic: if True will provide a single transduction option,
            for False multiple options (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.graph
        digit = pynini.union(*[str(i) for i in range(10)])
        number = pynini.closure(digit, 1)

        denominator_exceptions = {
            row[0]: row[1] for row in load_labels(get_abs_path("data/fraction/denominator_exceptions.tsv"))
        }

        denominator_exception_patterns = [pynini.cross(k, v) for k, v in denominator_exceptions.items()]
        denominator_exception_graph = (
            pynini.union(*denominator_exception_patterns) if denominator_exception_patterns else None
        )
        denominator_graph = (
            pynini.union(denominator_exception_graph, cardinal_graph)
            if denominator_exception_graph
            else cardinal_graph
        )

        slash = pynutil.delete(pynini.union("/", "⁄"))
        numerator = pynutil.insert("numerator: \"") + (number @ cardinal_graph) + pynutil.insert("\" ") + slash
        denominator = pynutil.insert("denominator: \"") + (number @ denominator_graph) + pynutil.insert("\"")
        integer_part = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\" ")

        vulgar = pynini.string_map(
            [(ch, f'numerator: "{num}" denominator: "{den}"') for ch, num, den in UNICODE_FRACTIONS]
        )

        simple_fraction = (numerator + denominator) | vulgar
        mixed_fraction = (integer_part + pynutil.delete(NEMO_SPACE) + numerator + denominator) | (
            integer_part + pynini.closure(pynutil.delete(NEMO_SPACE), 0, 1) + vulgar
        )

        # Create graph without negative for reuse in other FSTs (like measure)
        fraction_wo_negative = simple_fraction | mixed_fraction
        self.final_graph_wo_negative = fraction_wo_negative.optimize()

        optional_graph_negative = pynini.closure(pynutil.insert("negative: ") + pynini.cross("-", "\"true\" "), 0, 1)

        self.fst = self.add_tokens(optional_graph_negative + fraction_wo_negative).optimize()
