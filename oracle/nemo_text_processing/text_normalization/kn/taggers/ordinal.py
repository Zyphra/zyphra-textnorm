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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.kn.graph_utils import TO_ASCII_DIGIT, GraphFst
from nemo_text_processing.text_normalization.kn.taggers.cardinal import (
    HUNDREDS_COMB,
    CardinalFst,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path

ORDINAL_MARK = pynini.union("ನೇ", "ನೆ", "st", "nd", "rd", "th")


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Kannada ordinals written with the CLDR %digits-ordinal suffix ನೇ
    (ASCII or Kannada digits), spoken per CLDR %spellout-ordinal, e.g.
        1ನೇ -> ordinal { integer: "ಒಂದನೇ" }
        21ನೇ -> ordinal { integer: "ಇಪ್ಪತ್ತೊಂದನೇ" }
        200ನೇ -> ordinal { integer: "ಇನ್ನೂರನೇ" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        o2 = pynini.string_file(get_abs_path("data/ordinal/ordinals.tsv"))  # 1-99
        o1 = pynini.compose(pynini.union(*"123456789"), o2).optimize()
        o10_99 = pynini.compose(pynini.union(*"123456789") + pynini.union(*"0123456789"), o2).optimize()
        ro2 = (pynutil.delete("0") + o1 | o10_99).optimize()

        d2_9 = cardinal.ascii_d2_9
        e2 = cardinal.ascii_e2

        hundreds_ord_exact = pynini.union(
            *[pynini.cross(k + "00", v + "ನೇ") for k, v in HUNDREDS_COMB.items()]
        ).optimize()
        hundreds_ord_comb = pynini.union(
            *[pynini.cross(k, v + " ") for k, v in HUNDREDS_COMB.items()]
        ).optimize()
        o3 = (hundreds_ord_exact | (hundreds_ord_comb + ro2)).optimize()
        ro3 = (pynutil.delete("0") + ro2 | o3).optimize()

        # Thousands ordinals:
        # 1000ನೇ -> ಸಾವಿರದನೇ / ಸಾವಿರನೇ / ಒಂದು ಸಾವಿರದನೇ
        th_1_ord = (
            pynini.cross("1000", "ಸಾವಿರದನೇ")
            | pynutil.add_weight(pynini.cross("1000", "ಸಾವಿರನೇ"), 0.1)
            | pynutil.add_weight(pynini.cross("1000", "ಒಂದು ಸಾವಿರದನೇ"), 0.1)
            | pynini.cross("1", "ಒಂದು ಸಾವಿರದ ") + ro3
        ).optimize()

        th_2_9_ord = (
            d2_9 + pynini.cross("000", " ಸಾವಿರದನೇ")
            | d2_9 + pynutil.insert(" ಸಾವಿರದ ") + ro3
        ).optimize()

        th_10_99_ord = (
            e2 + pynini.cross("000", " ಸಾವಿರದನೇ")
            | e2 + pynutil.insert(" ಸಾವಿರದ ") + ro3
        ).optimize()

        o4 = (th_1_ord | th_2_9_ord).optimize()
        o5 = th_10_99_ord
        ro4 = (pynutil.delete("0") + ro3 | o4).optimize()
        ro5 = (pynutil.delete("0") + ro4 | o5).optimize()

        # Lakhs ordinals:
        l_1_ord = (
            pynini.cross("100000", "ಒಂದು ಲಕ್ಷದನೇ")
            | pynini.cross("1", "ಒಂದು ಲಕ್ಷದ ") + ro5
        ).optimize()

        l_2_9_ord = (
            d2_9 + pynini.cross("00000", " ಲಕ್ಷದನೇ")
            | d2_9 + pynutil.insert(" ಲಕ್ಷದ ") + ro5
        ).optimize()

        l_10_99_ord = (
            e2 + pynini.cross("00000", " ಲಕ್ಷದನೇ")
            | e2 + pynutil.insert(" ಲಕ್ಷದ ") + ro5
        ).optimize()

        o6 = (l_1_ord | l_2_9_ord).optimize()
        o7 = l_10_99_ord

        ascii_ordinal = pynini.union(o2, o3, o4, o5, o6, o7).optimize()
        graph = pynini.compose(pynini.closure(TO_ASCII_DIGIT, 1), ascii_ordinal) + pynutil.delete(ORDINAL_MARK)

        self.graph = graph.optimize()

        final_graph = pynutil.insert("integer: \"") + self.graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
