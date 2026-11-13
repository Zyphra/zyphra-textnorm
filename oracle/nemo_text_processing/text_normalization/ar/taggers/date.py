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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ar.graph_utils import NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.ar.utils import get_abs_path


class DateFst(GraphFst):
    """
    Finite state transducer for classifying numeric dates, eras, and decades, e.g.
        "25/12/2024" -> date { day: "خمسة وعشرون" month: "ديسمبر" year: "ألفان وأربعة وعشرون" }
        "2020م" -> date { year: "ألفان وعشرون" era: "ميلادي" }
        "500 BC" -> date { year: "خمس مئة" era: "قبل الميلاد" }
        "2020s" -> date { text: "عشرينيات القرن الحادي والعشرين" }
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="date", kind="classify")
        cardinal_graph = cardinal.cardinal_numbers
        months = pynini.string_file(get_abs_path("data/date/months.tsv"))

        day_digits = pynini.union(*[str(i) for i in range(1, 32)])
        month_digits = pynini.union(*[str(i) for i in range(1, 13)])
        optional_zero = pynini.closure(pynutil.delete("0"), 0, 1)
        year_digits = pynini.union("1", "2") + NEMO_DIGIT**3

        day = pynutil.insert('day: "') + optional_zero + (day_digits @ cardinal_graph) + pynutil.insert('"')
        month = pynutil.insert('month: "') + optional_zero + (month_digits @ months) + pynutil.insert('"')
        year = pynutil.insert('year: "') + (year_digits @ cardinal_graph) + pynutil.insert('"')

        graph = None
        for sep in ["/", "-", "."]:
            delete_sep = pynutil.delete(sep)
            dmy = day + delete_sep + insert_space + month + delete_sep + insert_space + year
            graph = dmy if graph is None else graph | dmy
        for sep in ["/", "-"]:
            delete_sep = pynutil.delete(sep)
            graph |= year + delete_sep + insert_space + month + delete_sep + insert_space + day

        era = pynini.cross("م", "ميلادي") | pynini.cross("هـ", "هجري")
        # the glued era mark outranks the measure reading "2020م" -> metres
        graph |= pynutil.add_weight(
            year
            + pynutil.insert(' era: "')
            + (era | pynutil.delete(" ") + pynini.cross("هـ", "هجري"))
            + pynutil.insert('"'),
            -0.2,
        )

        # Historical eras (1-4 digit years + BC/BCE/AD/CE)
        hist_year = (
            pynutil.insert('year: "')
            + (((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 3)) @ cardinal_graph)
            + pynutil.insert('"')
        )
        era_bc = pynini.union("BC", "B.C.", "BCE", "B.C.E.")
        era_ad = pynini.union("AD", "A.D.", "CE", "C.E.")
        graph |= hist_year + pynutil.delete(" ") + pynutil.insert(' era: "قبل الميلاد"') + pynutil.delete(era_bc)
        graph |= hist_year + pynutil.delete(" ") + pynutil.insert(' era: "ميلادي"') + pynutil.delete(era_ad)

        # International decades ("1990s" -> "تسعينيات القرن العشرين", "2020s" -> "عشرينيات القرن الحادي والعشرين")
        centuries = [
            ("15", "القرن السادس عشر"),
            ("16", "القرن السابع عشر"),
            ("17", "القرن الثامن عشر"),
            ("18", "القرن التاسع عشر"),
            ("19", "القرن العشرين"),
            ("20", "القرن الحادي والعشرين"),
        ]
        dec_tens = [
            ("20", "عشرينيات"),
            ("30", "ثلاثينيات"),
            ("40", "أربعينيات"),
            ("50", "خمسينيات"),
            ("60", "ستينيات"),
            ("70", "سبعينيات"),
            ("80", "ثمانينيات"),
            ("90", "تسعينيات"),
        ]
        decade_pairs = []
        for c_num, c_word in centuries:
            for d_num, d_word in dec_tens:
                spoken = f"{d_word} {c_word}"
                decade_pairs.append((f"{c_num}{d_num}s", spoken))
                decade_pairs.append((f"{c_num}{d_num}'s", spoken))
        early_decades = [
            ("1800", "عقد ألف وثمان مئة"),
            ("1810", "عقد ألف وثمان مئة وعشرة"),
            ("1900", "عقد ألف وتسع مئة"),
            ("1910", "عقد ألف وتسع مئة وعشرة"),
            ("2000", "عقد الألفين"),
            ("2010", "عقد ألفان وعشرة"),
        ]
        for y_num, spoken in early_decades:
            decade_pairs.append((f"{y_num}s", spoken))
            decade_pairs.append((f"{y_num}'s", spoken))
        for d_num, d_word in dec_tens:
            decade_pairs.append((f"'{d_num}s", f"ال{d_word}"))
            decade_pairs.append((f"’{d_num}s", f"ال{d_word}"))

        decade_graph = pynutil.insert('text: "') + pynini.string_map(decade_pairs) + pynutil.insert('"')
        graph |= pynutil.add_weight(decade_graph, -0.1)

        self.graph = graph.optimize()
        self.fst = self.add_tokens(self.graph).optimize()
