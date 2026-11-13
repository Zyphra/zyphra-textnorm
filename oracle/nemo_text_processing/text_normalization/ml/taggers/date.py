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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_DIGIT,
    NEMO_ML_DIGIT,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path

months = pynini.string_file(get_abs_path("data/date/months.tsv"))
month_names = pynini.string_file(get_abs_path("data/date/month_names.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))


class DateFst(GraphFst):
    """
    Finite state transducer for classifying dates.
        "25/12/2024" -> date { day: "ഇരുപത്തിയഞ്ച്" month: "ഡിസംബർ" year: "രണ്ടായിരത്തി ഇരുപത്തിനാല്" }
        "2024-03-05" -> date { year: "രണ്ടായിരത്തി ഇരുപത്തിനാല്" month: "മാർച്ച്" day: "അഞ്ച്" }
        "15 ഓഗസ്റ്റ് 1947" -> date { day: "പതിനഞ്ച്" month: "ഓഗസ്റ്റ്" year: "ആയിരത്തി തൊള്ളായിരത്തി നാൽപ്പത്തിയേഴ്" }
        "1947 എ.ഡി." -> date { year: "ആയിരത്തി തൊള്ളായിരത്തി നാൽപ്പത്തിയേഴ്" era: "എ.ഡി." }
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="date", kind="classify")

        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()
        nonzero = pynini.union(*"123456789")
        number = cardinal.graph_without_leading_zeros

        # 1-31 with an optional leading zero
        day_digits = (
            pynini.closure(pynutil.delete("0"), 0, 1) + nonzero
            | pynini.union("1", "2") + NEMO_DIGIT
            | pynini.union("30", "31")
        )
        day_number = pynini.compose(to_ascii, day_digits @ number).optimize()
        month_number = pynini.compose(to_ascii, months).optimize()
        year_any = pynini.compose(to_ascii, (nonzero + pynini.closure(NEMO_DIGIT, 0, 3)) @ number).optimize()
        year_4 = pynini.compose(to_ascii, (pynini.union("1", "2") + NEMO_DIGIT**3) @ number).optimize()

        def field(name, graph):
            return pynutil.insert(f"{name}: \"") + graph + pynutil.insert("\"")

        day = field("day", day_number)
        month_num = field("month", month_number)
        month_name = field("month", month_names + pynini.closure(pynutil.delete("."), 0, 1))
        year = field("year", year_any)
        year4 = field("year", year_4)
        era = field("era", year_suffix)

        space = pynutil.delete(" ") + insert_space
        optional_era = pynini.closure(space + era, 0, 1)
        optional_comma = pynini.closure(pynutil.delete(","), 0, 1)

        # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        graph_dmy = pynini.union(
            *[day + pynutil.delete(s) + insert_space + month_num + pynutil.delete(s) + insert_space + year4 for s in "/-."]
        )
        # YYYY-MM-DD
        graph_ymd = year4 + pynutil.delete("-") + insert_space + month_num + pynutil.delete("-") + insert_space + day

        graph_d_month_y = day + space + month_name + optional_comma + space + year + optional_era
        graph_d_month = day + space + month_name
        graph_month_y = month_name + optional_comma + space + year + optional_era
        graph_year_era = year + space + era

        # Year ranges: "1990–1995" -> "1990 മുതൽ 1995 വരെ"
        year_range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " മുതൽ ")
        graph_year_range = field("year", year_4 + year_range_sep + year_4 + pynutil.insert(" വരെ"))

        decade = field(
            "year",
            (pynini.union("1", "2", "൧", "൨") + (NEMO_DIGIT | NEMO_ML_DIGIT) ** 2 + pynini.union("0", "൦"))
            @ year_4
            + pynini.cross(pynini.union("s", "-കൾ", "കൾ"), "കളിലെ ദശകം"),
        )
        final_graph = (
            graph_dmy
            | graph_ymd
            | graph_d_month_y
            | graph_d_month
            | graph_month_y
            | graph_year_era
            | pynutil.add_weight(graph_year_range, -0.05)
            | decade
        )

        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph)
