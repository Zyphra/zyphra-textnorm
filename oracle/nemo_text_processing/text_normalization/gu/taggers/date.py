# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.gu.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_NON_ZERO,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.gu.utils import get_abs_path

days = pynini.string_file(get_abs_path("data/date/days.tsv"))
months = pynini.string_file(get_abs_path("data/date/months.tsv"))
month_abbr = pynini.string_file(get_abs_path("data/date/month_abbr.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))

pad_latin = pynini.union(*[pynini.cross(str(i), f"0{i}") for i in range(1, 10)])
pad_gujarati = pynini.union(*[pynini.cross(d, f"૦{d}") for d in "૧૨૩૪૫૬૭૮૯"])


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date (day month year order; years read as cardinals), e.g.
        "૦૧-૦૪-૨૦૨૪" -> date { day: "એક" month: "એપ્રિલ" year: "બે હજાર ચોવીસ" }
        "25/12/2024" -> date { day: "પચ્ચીસ" month: "ડિસેમ્બર" year: "બે હજાર ચોવીસ" }
        "2024-12-25" -> date { day: "પચ્ચીસ" month: "ડિસેમ્બર" year: "બે હજાર ચોવીસ" }
        "૬ માર્ચ, ૨૦૧૦" -> date { day: "છ" month: "માર્ચ" year: "બે હજાર દસ" }
        "૩૧ મે ૧૯૯૦ ઈ.સ." -> date { day: "એકત્રીસ" month: "મે" year: "એક હજાર નવ સો નેવું" era: "ઈસવીસન" }

    Args:
        cardinal: cardinal GraphFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="date", kind="classify")

        year_input = pynini.union("1", "2", "૧", "૨") + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        graph_year = pynini.compose(year_input, cardinal.graph_thousands).optimize()
        graph_year_era = pynini.compose(
            NEMO_ALL_NON_ZERO + pynini.closure(NEMO_ALL_DIGIT, 0, 3), cardinal.graph_without_leading_zeros
        ).optimize()

        delete_space = pynutil.delete(" ")
        delete_optional_space = pynini.closure(pynutil.delete(" "), 0, 1)
        delete_comma_sep = pynini.closure(pynutil.delete(","), 0, 1) + delete_optional_space

        day_num = pynini.union(days, pynini.compose(pad_latin, days), pynini.compose(pad_gujarati, days))
        month_num = pynini.union(months, pynini.compose(pad_latin, months), pynini.compose(pad_gujarati, months))
        month_name = pynini.union(pynini.project(months, "output"), month_abbr)

        day_graph = pynutil.insert('day: "') + day_num + pynutil.insert('"') + insert_space
        month_num_graph = pynutil.insert('month: "') + month_num + pynutil.insert('"') + insert_space
        month_name_graph = pynutil.insert('month: "') + month_name + pynutil.insert('"') + insert_space
        year_last = pynutil.insert('year: "') + graph_year + pynutil.insert('"')
        era_graph = pynutil.insert(' era: "') + delete_space + year_suffix + pynutil.insert('"')
        optional_era = pynini.closure(era_graph, 0, 1)

        graph_numeric = pynini.union(
            *[
                day_graph + pynutil.delete(sep) + month_num_graph + pynutil.delete(sep) + year_last
                for sep in ("-", "/", ".")
            ]
        )
        graph_dd_mm = day_graph + pynutil.delete("-") + pynutil.insert('month: "') + month_num + pynutil.insert('"')

        iso_day_month_year = (
            pynutil.insert('year: "')
            + graph_year
            + pynutil.insert('" ')
            + pynutil.delete("-")
            + pynutil.insert('month: "')
            + month_num
            + pynutil.insert('" ')
            + pynutil.delete("-")
            + pynutil.insert('day: "')
            + day_num
            + pynutil.insert('"')
        )

        graph_day_month_year = day_graph + delete_space + month_name_graph + delete_comma_sep + year_last + optional_era
        graph_day_month = day_graph + delete_space + pynutil.insert('month: "') + month_name + pynutil.insert('"')
        graph_month_year = month_name_graph + delete_comma_sep + year_last + optional_era

        graph_year_with_era = (
            pynutil.insert('year: "')
            + graph_year_era
            + pynutil.insert('"')
            + era_graph
        )

        graph_era_year = (
            pynutil.insert('era: "')
            + year_suffix
            + pynutil.insert('" ')
            + delete_space
            + pynutil.insert('year: "')
            + graph_year_era
            + pynutil.insert('" preserve_order: true')
        )

        range_sep = delete_optional_space + pynini.cross(pynini.union("-", "–"), " થી ") + delete_optional_space
        range_graph = (
            pynutil.insert('year: "')
            + graph_year
            + range_sep
            + graph_year
            + pynutil.insert('"')
        )

        zero_digit = pynini.union("0", "૦")
        decade_4d_num = pynini.compose(
            pynini.union("1", "2", "૧", "૨") + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + zero_digit,
            cardinal.graph_thousands,
        ).optimize()
        decade_2d_num = pynini.compose(
            NEMO_ALL_NON_ZERO + zero_digit,
            cardinal.teens_and_ties,
        ).optimize()
        intl_decade_suffix = pynini.cross(pynini.union("s", "'s"), "નો દાયકો")
        decade_graph = (
            pynutil.insert('year: "')
            + (
                ((decade_4d_num | (pynini.closure(pynutil.delete("'"), 0, 1) + decade_2d_num)) + intl_decade_suffix)
                | (
                    (decade_4d_num | decade_2d_num)
                    + delete_optional_space
                    + (
                        pynini.cross("નો દાયકો", "નો દાયકો")
                        | pynini.cross("ના દાયકામાં", "ના દાયકામાં")
                    )
                )
            )
            + pynutil.insert('"')
        ).optimize()

        final_graph = (
            pynutil.add_weight(graph_numeric, -0.001)
            | pynutil.add_weight(iso_day_month_year, -0.001)
            | pynutil.add_weight(graph_dd_mm, -0.001)
            | pynutil.add_weight(graph_day_month_year, -0.003)
            | pynutil.add_weight(graph_day_month, -0.001)
            | pynutil.add_weight(graph_month_year, -0.2)
            | pynutil.add_weight(graph_year_with_era, -0.005)
            | pynutil.add_weight(graph_era_year, -0.005)
            | pynutil.add_weight(range_graph, -0.005)
            | pynutil.add_weight(decade_graph, -0.01)
        )
        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph)
