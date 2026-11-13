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

from collections import defaultdict

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ar.graph_utils import NEMO_DIGIT, GraphFst, convert_space
from nemo_text_processing.text_normalization.ar.utils import get_abs_path, load_labels
from nemo_text_processing.text_normalization.ar.verbalizers.time import TimeFst as TimeVerbalizer


class RangeFst(GraphFst):
    """
    Finite state transducer for number ranges, money ranges, time ranges, and comma lists, tagged as a word token, e.g.
        "5-10" -> tokens { name: "خمسة إلى عشرة" }
        "2020-2024" -> tokens { name: "ألفان وعشرون إلى ألفان وأربعة وعشرون" }
        "$10-$20" -> tokens { name: "عشرة إلى عشرون دولار" }
        "9:00-17:00" -> tokens { name: "الساعة التاسعة إلى الساعة الخامسة مساءً" }
        "1,2,3" -> tokens { name: "واحد، اثنان، ثلاثة" }
    """

    def __init__(self, cardinal: GraphFst, time_tagger: GraphFst = None):
        super().__init__(name="range", kind="classify")
        number = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 5)) | "0"
        number = (number @ cardinal.cardinal_numbers).optimize()
        dash = pynini.union("-", "–", " - ", " – ")
        phone_shape = NEMO_DIGIT**3 + "-" + NEMO_DIGIT**4
        range_graph = number + pynini.cross(dash, " إلى ") + number
        range_graph = pynini.difference(pynini.project(range_graph, "input"), phone_shape) @ range_graph
        short = (NEMO_DIGIT | ((NEMO_DIGIT - "0") + NEMO_DIGIT)) @ number
        list_graph = number + pynini.closure(pynini.cross(",", "، ") + short, 2)

        # Compact money amounts for ranges: 0..9999 + k/M/B shorthand
        num_4d = ((((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 3)) | "0") @ cardinal.cardinal_numbers).optimize()
        lead_group = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)
        amt_k = ((lead_group + pynutil.insert("000")) @ cardinal.cardinal_numbers) + pynutil.delete(
            pynini.union("k", "K")
        )
        amt_m = ((lead_group + pynutil.insert("000000")) @ cardinal.cardinal_numbers) + pynutil.delete(
            pynini.union("M", "m")
        )
        amt_b = ((lead_group + pynutil.insert("000000000")) @ cardinal.cardinal_numbers) + pynutil.delete(
            pynini.union("B", "b")
        )
        short_money_num = (num_4d | amt_k | amt_m | amt_b).optimize()
        full_money_num = (number | amt_k | amt_m | amt_b).optimize()

        sym_to_name = {}
        for sym, name in load_labels(get_abs_path("data/money/currency_major.tsv")):
            sym_to_name.setdefault(sym, name)
        for sym, name in load_labels(get_abs_path("data/money/local_currency.tsv")):
            sym_to_name.setdefault(sym, name)

        alpha_pairs = [(s, f" {n}") for s, n in sym_to_name.items() if s.isascii() and any(c.isalpha() for c in s)]
        other_pairs = [(s, f" {n}") for s, n in sym_to_name.items() if not (s.isascii() and any(c.isalpha() for c in s))]

        all_syms = sorted(sym_to_name.keys())
        del_any_pre = pynutil.delete(pynini.union(*all_syms) + pynini.closure(" ", 0, 1))
        del_any_suf = pynutil.delete(
            (pynini.accep(" ") + pynini.union(*[s for s, _ in alpha_pairs]))
            | (pynini.closure(" ", 0, 1) + pynini.union(*[s for s, _ in other_pairs]))
        )
        suf_to_name = (pynutil.delete(" ") + pynini.string_map(alpha_pairs)) | (
            pynini.closure(pynutil.delete(" "), 0, 1) + pynini.string_map(other_pairs)
        )

        # Trailing currency ranges ("10-20 €", "100-200 USD", "10€-20€", "10-20 ر.س") — O(1) single FST!
        suf_money_range = (
            full_money_num
            + pynini.closure(del_any_suf, 0, 1)
            + pynini.cross(dash, " إلى ")
            + full_money_num
            + suf_to_name
        )

        # Prefix currency ranges:
        # 1) "$10-$20" (symbol on both sides): factor left side once, swap only on right side
        # 2) "$10-20" (symbol on left only): sign/prefixed-$ symbols
        by_name = defaultdict(list)
        sign_by_name = defaultdict(list)
        for sym, name in sym_to_name.items():
            by_name[name].append(sym)
            if not sym.isalpha():
                sign_by_name[name].append(sym)

        rhs_swaps = [
            pynutil.delete(pynini.union(*syms) + pynini.closure(" ", 0, 1))
            + short_money_num
            + pynutil.insert(f" {name}")
            for name, syms in by_name.items()
        ]
        left_only_branches = [
            pynutil.delete(pynini.union(*syms) + pynini.closure(" ", 0, 1))
            + short_money_num
            + pynini.cross(dash, " إلى ")
            + short_money_num
            + pynutil.insert(f" {name}")
            for name, syms in sign_by_name.items()
        ]

        both_pre_range = del_any_pre + full_money_num + pynini.cross(dash, " إلى ") + pynini.union(*rhs_swaps).optimize()
        left_pre_range = pynini.union(*left_only_branches).optimize()
        money_range_graph = (suf_money_range | both_pre_range | left_pre_range).optimize()

        self.range_graph = range_graph.optimize()
        graph = (self.range_graph | list_graph | money_range_graph).optimize()

        if time_tagger is not None and hasattr(time_tagger, "hm_fst"):
            hm_spoken = (time_tagger.hm_fst @ TimeVerbalizer().fst).optimize()
            time_range_graph = (hm_spoken + pynini.cross(dash, " إلى ") + hm_spoken).optimize()
            graph = (graph | time_range_graph).optimize()

        self.fst = (pynutil.insert('name: "') + convert_space(graph).optimize() + pynutil.insert('"')).optimize()
