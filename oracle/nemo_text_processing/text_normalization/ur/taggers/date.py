# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.ur.graph_utils import (
    NEMO_DIGIT,
    UR_COMMA,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ur.utils import get_abs_path

days = pynini.string_file(get_abs_path("data/date/days.tsv"))
months = pynini.string_file(get_abs_path("data/date/months.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))
digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
teens_ties = pynini.string_file(get_abs_path("data/numbers/teens_and_ties.tsv"))
teens_and_ties = pynutil.add_weight(teens_ties, -0.1)

with open(get_abs_path("data/date/suffixes.tsv"), "r", encoding="utf-8") as f:
    suffix_union = pynini.string_map([line.rstrip("\n") for line in f if line.strip()])

with open(get_abs_path("data/date/prefixes.tsv"), "r", encoding="utf-8") as f:
    prefix_union = pynini.string_map([line.rstrip("\n") for line in f if line.strip()])

verbalized_hundreds = teens_ties.project("output")
verbalized_unit = pynini.union(verbalized_hundreds, digit.project("output"))

verbalized_year_sou = (
    verbalized_hundreds + pynini.accep(" سو") + pynini.closure(pynini.accep(" ") + verbalized_unit, 0, 1)
)

pad_latin = pynini.union(*[pynini.cross(str(i), f"0{i}") for i in range(1, 10)])


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date, e.g.
        "01-04-2024" -> date { day: "ایک" month: "اپریل" year: "دو ہزار چوبیس" }
        "25/12/2024" -> date { day: "پچیس" month: "دسمبر" year: "دو ہزار چوبیس" }
        "2024-04-01" -> date { year: "دو ہزار چوبیس" month: "اپریل" day: "ایک" }
        "6 مارچ، 2010" -> date { day: "چھ" month: "مارچ" year: "دو ہزار دس" }
        "14 اگست 1947ء" -> date { day: "چودہ" month: "اگست" year: "ایک ہزار نو سو سینتالیس" era: "عیسوی" }
        "انیس سو بیس میں" -> date { era: "انیس سو بیس میں" }

    Years are read as plain cardinals; written month names (CLDR gregorian format wide) pass through.

    Args:
        cardinal: cardinal GraphFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="date", kind="classify")

        graph_year = pynini.compose(NEMO_DIGIT**4, cardinal.graph_thousands).optimize()

        cardinal_graph = pynini.union(
            digit,
            teens_and_ties,
            cardinal.graph_hundreds,
            graph_year,
        )

        graph_year_era = pynini.union(graph_year, cardinal.graph_hundreds)

        delete_dash = pynutil.delete("-")
        delete_space = pynutil.delete(" ")
        delete_optional_space = pynini.closure(pynutil.delete(" "), 0, 1)
        delete_comma_sep = (pynutil.delete(pynini.union(",", UR_COMMA)) + delete_optional_space) | delete_space

        day_num_padded = days
        day_num_bare = pynini.compose(pad_latin, days)
        day_num_any = pynini.union(day_num_padded, day_num_bare)

        days_graph_padded = pynutil.insert("day: \"") + day_num_padded + pynutil.insert("\"") + insert_space
        days_graph_bare = pynutil.insert("day: \"") + day_num_bare + pynutil.insert("\"") + insert_space
        days_graph_any = pynutil.insert("day: \"") + day_num_any + pynutil.insert("\"") + insert_space

        month_name_acceptor = pynini.project(months, "output")

        months_numeric_padded = months
        months_numeric_bare = pynini.compose(pad_latin, months)
        months_numeric_any = pynini.union(months_numeric_padded, months_numeric_bare)

        months_graph_padded = pynutil.insert("month: \"") + months_numeric_padded + pynutil.insert("\"") + insert_space
        months_graph_bare = pynutil.insert("month: \"") + months_numeric_bare + pynutil.insert("\"") + insert_space
        months_graph_any = pynutil.insert("month: \"") + months_numeric_any + pynutil.insert("\"") + insert_space

        month_name_graph = pynutil.insert("month: \"") + month_name_acceptor + pynutil.insert("\"") + insert_space

        years_graph = pynutil.insert("year: \"") + graph_year + pynutil.insert("\"") + insert_space

        era_graph = (
            pynutil.insert("era: \"") + delete_optional_space + year_suffix + pynutil.insert("\"") + insert_space
        )

        range_graph = pynini.cross(pynini.union("-", "–"), "سے")

        century_number = pynini.compose(pynini.closure(NEMO_DIGIT, 1), cardinal_graph) + pynini.accep("ویں")
        century_text = pynutil.insert("era: \"") + century_number + pynutil.insert("\"") + insert_space

        year_number = graph_year + suffix_union
        year_text = pynutil.insert("era: \"") + year_number + pynutil.insert("\"") + insert_space

        year_prefix = pynutil.insert("era: \"") + prefix_union + pynini.accep(" ") + graph_year + pynutil.insert("\"")

        year_prefix_suffix = (
            pynutil.insert("era: \"")
            + prefix_union
            + pynini.accep(" ")
            + graph_year
            + suffix_union
            + pynutil.insert("\"")
        )

        graph_verbalized_year_suffix = (
            pynutil.insert("era: \"") + verbalized_year_sou + suffix_union + pynutil.insert("\"") + insert_space
        )

        graph_verbalized_year_bare = (
            pynutil.insert("era: \"") + verbalized_year_sou + pynutil.insert("\"") + insert_space
        )

        graph_verbalized_year_prefix = (
            pynutil.insert("era: \"") + prefix_union + pynini.accep(" ") + verbalized_year_sou + pynutil.insert("\"")
        )

        graph_verbalized_year_prefix_suffix = (
            pynutil.insert("era: \"")
            + prefix_union
            + pynini.accep(" ")
            + verbalized_year_sou
            + suffix_union
            + pynutil.insert("\"")
        )

        graph_dd_mm = days_graph_padded + delete_dash + months_graph_padded

        graph_d_m = days_graph_bare + delete_dash + months_graph_bare

        graph_dd_mm_yyyy = days_graph_padded + delete_dash + months_graph_padded + delete_dash + years_graph

        graph_d_m_yyyy = days_graph_bare + delete_dash + months_graph_bare + delete_dash + years_graph

        # DD/MM/YYYY and DD.MM.YYYY: the year is required, so fractions and decimals are not read as dates.
        graph_slash_dot_yyyy = pynini.union(
            *[
                days_graph_any + pynutil.delete(sep) + months_graph_any + pynutil.delete(sep) + years_graph
                for sep in ("/", ".")
            ]
        )

        # YYYY-MM-DD: tagged year first; the Normalizer's permutation search verbalizes it day month year.
        graph_yyyy_mm_dd = years_graph + delete_dash + months_graph_any + delete_dash + days_graph_any

        graph_dd_month = days_graph_any + delete_space + month_name_graph

        graph_dd_month_comma_yyyy = days_graph_any + delete_space + month_name_graph + delete_comma_sep + years_graph

        graph_dd_month_comma_yyyy_era = (
            days_graph_any + delete_space + month_name_graph + delete_comma_sep + years_graph + era_graph
        )

        graph_month_comma_yyyy = month_name_graph + delete_comma_sep + years_graph

        graph_month_comma_yyyy_era = month_name_graph + delete_comma_sep + years_graph + era_graph

        graph_year_era_only = (
            pynutil.insert("era: \"")
            + graph_year_era
            + delete_optional_space
            + insert_space
            + year_suffix
            + pynutil.insert("\"")
            + insert_space
        )
        # International decades: "1990s" -> "ایک ہزار نو سو نوے کی دہائی", "2020s" -> "دو ہزار بیس کی دہائی"
        decade_year = pynini.compose(pynini.union("1", "2") + (NEMO_DIGIT**2) + "0", cardinal.graph_thousands).optimize()
        graph_intl_decade = (
            pynutil.insert("era: \"")
            + decade_year
            + pynini.cross(pynini.union("s", "'s", "’s"), " کی دہائی")
            + pynutil.insert("\"")
            + insert_space
        )
        graph_range = (
            pynutil.insert("era: \"")
            + cardinal_graph
            + insert_space
            + range_graph
            + insert_space
            + cardinal_graph
            + pynutil.insert("\"")
            + pynutil.insert(" preserve_order: true ")
        )

        graph_year_suffix = era_graph

        final_graph = (
            pynutil.add_weight(graph_dd_month_comma_yyyy_era, -0.003)
            | pynutil.add_weight(graph_month_comma_yyyy_era, -0.003)
            | pynutil.add_weight(graph_dd_mm_yyyy, -0.001)
            | pynutil.add_weight(graph_d_m_yyyy, -0.001)
            | pynutil.add_weight(graph_slash_dot_yyyy, -0.001)
            | pynutil.add_weight(graph_yyyy_mm_dd, -0.001)
            | pynutil.add_weight(graph_dd_month_comma_yyyy, -0.001)
            | pynutil.add_weight(graph_dd_mm, -0.001)
            | pynutil.add_weight(graph_d_m, -0.001)
            | pynutil.add_weight(graph_dd_month, -0.001)
            | pynutil.add_weight(graph_month_comma_yyyy, -0.2)
            | pynutil.add_weight(graph_year_era_only, -0.005)
            | pynutil.add_weight(graph_intl_decade, -0.02)
            | pynutil.add_weight(graph_range, -0.005)
            | pynutil.add_weight(graph_year_suffix, -0.001)
            | pynutil.add_weight(century_text, -0.001)
            | pynutil.add_weight(graph_verbalized_year_prefix_suffix, -0.012)
            | pynutil.add_weight(graph_verbalized_year_prefix, -0.011)
            | pynutil.add_weight(graph_verbalized_year_suffix, -0.010)
            | pynutil.add_weight(graph_verbalized_year_bare, -0.009)
            | pynutil.add_weight(year_prefix_suffix, -0.010)
            | pynutil.add_weight(year_prefix, -0.009)
            | pynutil.add_weight(year_text, -0.001)
        )

        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph)
