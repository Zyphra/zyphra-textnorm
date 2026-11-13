# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ta.graph_utils import TO_ASCII_DIGIT, GraphFst
from nemo_text_processing.text_normalization.ta.taggers.cardinal import (
    CardinalFst,
    _PREFIX_MAP,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Tamil ordinals written with suffixes
    (வது, ஆவது, -வது, -ஆவது, st, nd, rd, th) on ASCII or Tamil digits, e.g.
        1வது -> ordinal { integer: "முதலாவது" }
        21வது -> ordinal { integer: "இருபத்து ஒன்றாவது" }
        100வது -> ordinal { integer: "நூறாவது" }
        200வது -> ordinal { integer: "இருநூறாவது" }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        o2 = pynini.string_file(get_abs_path("data/ordinal/ordinals.tsv"))  # 1-99
        o1 = pynini.compose(pynini.union(*"123456789"), o2).optimize()
        o1_compound = pynini.cross("1", "ஒன்றாவது") | pynini.compose(pynini.union(*"23456789"), o2).optimize()
        o10_99 = pynini.compose(pynini.union(*"123456789") + pynini.union(*"0123456789"), o2).optimize()
        ro2 = (pynutil.delete("0") + o1_compound | o10_99).optimize()

        d2_9 = cardinal.ascii_d2_9
        e2 = cardinal.ascii_e2

        # Hundreds ordinals (100 - 999)
        hundreds_ord_exact = {
            100: "நூறாவது",
            200: "இருநூறாவது",
            300: "முந்நூறாவது",
            400: "நானூறாவது",
            500: "ஐநூறாவது",
            600: "அறுநூறாவது",
            700: "எழுநூறாவது",
            800: "எண்நூறாவது",
            900: "தொள்ளாயிரத்தாவது",
        }
        hundreds_ord_comb = {
            1: "நூற்று ",
            2: "இருநூற்று ",
            3: "முந்நூற்று ",
            4: "நானூற்று ",
            5: "ஐநூற்று ",
            6: "அறுநூற்று ",
            7: "எழுநூற்று ",
            8: "எண்நூற்று ",
            9: "தொள்ளாயிரத்து ",
        }

        h_ord_exact_list = [pynini.cross(str(h), word) for h, word in hundreds_ord_exact.items()]
        h_ord_comb_list = [pynutil.delete(str(d)) + pynutil.insert(prefix) + ro2 for d, prefix in hundreds_ord_comb.items()]

        o3 = pynini.union(*h_ord_exact_list, *h_ord_comb_list).optimize()
        ro3 = (pynutil.delete("0") + ro2 | o3).optimize()

        # Thousands ordinals (1,000 - 99,999)
        th_ord_exact_1_list = [(str(i), _PREFIX_MAP[i] + "ாயிரத்தாவது") for i in range(2, 10)]
        th_comb_1_list = [(str(i), _PREFIX_MAP[i] + "ாயிரத்து ") for i in range(2, 10)]
        th_ord_exact_2_list = [(str(i), _PREFIX_MAP[i] + "ாயிரத்தாவது") for i in range(10, 100)]
        th_comb_2_list = [(str(i), _PREFIX_MAP[i] + "ாயிரத்து ") for i in range(10, 100)]

        th_ord_exact_1 = pynini.string_map(th_ord_exact_1_list).optimize()
        th_comb_1 = pynini.string_map(th_comb_1_list).optimize()
        th_ord_exact_2 = pynini.string_map(th_ord_exact_2_list).optimize()
        th_comb_2 = pynini.string_map(th_comb_2_list).optimize()

        o4 = (
            pynini.cross("1000", "ஆயிரமாவது")
            | pynutil.delete("1") + pynutil.insert("ஆயிரத்து ") + ro3
            | th_ord_exact_1 + pynutil.delete("000")
            | th_comb_1 + ro3
        ).optimize()

        o5 = (
            th_ord_exact_2 + pynutil.delete("000")
            | th_comb_2 + ro3
        ).optimize()

        ro4 = (pynutil.delete("0") + ro3 | o4).optimize()
        ro5 = (pynutil.delete("0") + ro4 | o5).optimize()

        # Lakhs ordinals (1,00,000 - 99,99,999)
        o6 = (
            pynini.cross("100000", "ஒரு லட்சத்தாவது")
            | pynutil.delete("1") + pynutil.insert("ஒரு லட்சத்து ") + ro5
            | d2_9 + pynini.cross("00000", " லட்சத்தாவது")
            | d2_9 + pynutil.insert(" லட்சத்து ") + ro5
        ).optimize()
        o7 = (
            e2 + pynini.cross("00000", " லட்சத்தாவது")
            | e2 + pynutil.insert(" லட்சத்து ") + ro5
        ).optimize()

        ro6 = (pynutil.delete("0") + ro5 | o6).optimize()
        ro7 = (pynutil.delete("0") + ro6 | o7).optimize()

        # Crores ordinals (1,00,00,000 - 99,99,99,999)
        o8 = (
            pynini.cross("10000000", "ஒரு கோடியாவது")
            | pynutil.delete("1") + pynutil.insert("ஒரு கோடியே ") + ro7
            | d2_9 + pynini.cross("0000000", " கோடியாவது")
            | d2_9 + pynutil.insert(" கோடியே ") + ro7
        ).optimize()
        o9 = (
            e2 + pynini.cross("0000000", " கோடியாவது")
            | e2 + pynutil.insert(" கோடியே ") + ro7
        ).optimize()

        ascii_ordinal = pynini.union(o2, o3, o4, o5, o6, o7, o8, o9).optimize()

        # Accepted ordinal suffixes: வது, ஆவது, -வது, -ஆவது, st, nd, rd, th
        suffix_options = pynini.union("வது", "ஆவது", "-வது", "-ஆவது", "st", "nd", "rd", "th")
        delete_suffix = pynutil.delete(suffix_options)

        graph = pynini.compose(pynini.closure(TO_ASCII_DIGIT, 1), ascii_ordinal) + delete_suffix
        self.graph = graph.optimize()

        final_graph = pynutil.insert("integer: \"") + self.graph + pynutil.insert("\"")
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()
