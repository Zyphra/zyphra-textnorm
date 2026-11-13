# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)


def _build_ordinal_words() -> pynini.Fst:
    """Mapping from digit string to Norwegian Bokmål ordinal word."""
    digits_1_19 = [
        ("0", "nullte"),
        ("1", "første"),
        ("2", "andre"),
        ("3", "tredje"),
        ("4", "fjerde"),
        ("5", "femte"),
        ("6", "sjette"),
        ("7", "sjuende"),
        ("8", "åttende"),
        ("9", "niende"),
        ("10", "tiende"),
        ("11", "ellevte"),
        ("12", "tolvte"),
        ("13", "trettende"),
        ("14", "fjortende"),
        ("15", "femtende"),
        ("16", "sekstende"),
        ("17", "syttende"),
        ("18", "attende"),
        ("19", "nittende"),
    ]
    ord_1_19 = pynini.string_map(digits_1_19)

    ties_stem = [
        ("2", "tjue"),
        ("3", "tretti"),
        ("4", "førti"),
        ("5", "femti"),
        ("6", "seksti"),
        ("7", "sytti"),
        ("8", "åtti"),
        ("9", "nitti"),
    ]
    ties_graph = pynini.string_map(ties_stem)

    ord_ties_exact = ties_graph + pynutil.delete("0") + pynutil.insert("ende")

    ord_units = pynini.string_map(
        [
            ("1", "første"),
            ("2", "andre"),
            ("3", "tredje"),
            ("4", "fjerde"),
            ("5", "femte"),
            ("6", "sjette"),
            ("7", "sjuende"),
            ("8", "åttende"),
            ("9", "niende"),
        ]
    )
    ord_compound = ties_graph + ord_units

    ord_1_99 = ord_1_19 | ord_ties_exact | ord_compound

    ord_100 = pynini.cross("100", "hundrede") | pynini.cross("100", "ett hundrede")
    ord_1000 = pynini.cross("1000", "tusende") | pynini.cross("1000", "ett tusende")
    ord_1000000 = pynini.cross("1000000", "millionte")

    # Hundreds + ordinal unit (e.g. 101 -> hundre og første)
    unit_no_one = pynini.string_map(
        [
            ("2", "to"),
            ("3", "tre"),
            ("4", "fire"),
            ("5", "fem"),
            ("6", "seks"),
            ("7", "sju"),
            ("8", "åtte"),
            ("9", "ni"),
        ]
    )
    ord_teens = pynini.string_map(digits_1_19[10:])
    ord_two_digits = ord_teens | ord_ties_exact | ord_compound | (pynutil.delete("0") + ord_units)

    hundre_rem_ord = (
        (pynutil.delete("1") | pynutil.add_weight(pynini.cross("1", "ett "), 0.1))
        + pynutil.insert("hundre og ")
        + ord_two_digits
    ) | (
        unit_no_one
        + pynutil.insert(" hundre og ")
        + ord_two_digits
    )

    all_ord = (
        ord_1_99
        | ord_100
        | hundre_rem_ord
        | ord_1000
        | ord_1000000
    )
    return all_ord.optimize()


class OrdinalFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål ordinals.
    e.g. 1. -> første
         17. -> syttende
         den 1. -> den første
         1ste -> første
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        ord_words = _build_ordinal_words()
        self.ord_words = ord_words

        # Number followed by period: "1.", "17."
        dot_ord = ord_words + pynutil.delete(".")

        # With leading 'den ' or 'Den ': "den 1." -> "den første"
        den_prefix = pynini.cross("den ", "den ") | pynini.cross("Den ", "Den ")
        den_ord = den_prefix + dot_ord

        # Suffix notation: "1ste", "2dre", "3dje", "4de"
        suffix = (
            pynutil.delete("ste")
            | pynutil.delete("dre")
            | pynutil.delete("dje")
            | pynutil.delete("de")
            | pynutil.delete("ende")
            | pynutil.delete("te")
        )
        suffix_ord = ord_words + suffix

        self.graph = (den_ord | dot_ord | suffix_ord).optimize()
        self.fst = self.graph
