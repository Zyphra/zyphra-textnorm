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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_DIGIT,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path

months = pynini.string_file(get_abs_path("data/date/months.tsv"))
month_names = pynini.string_file(get_abs_path("data/date/month_names.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date, e.g.
        "25/12/2024" -> date { day: "இருபத்து ஐந்து" month: "டிசம்பர்" year: "இரண்டாயிரத்து இருபத்து நான்கு" }
        "2024-12-25" -> date { year: "இரண்டாயிரத்து இருபத்து நான்கு" month: "டிசம்பர்" day: "இருபத்து ஐந்து" }
        "15 ஆகஸ்ட் 1947" -> date { day: "பதினைந்து" month: "ஆகஸ்ட்" year: "ஆயிரத்து தொள்ளாயிரத்து நாற்பத்து ஏழு" }
        "1947 கி.பி." -> date { year: "ஆயிரத்து தொள்ளாயிரத்து நாற்பத்து ஏழு" era: "கிறிஸ்துவுக்குப் பின்" }
        "1990–1995" -> date { year: "ஆயிரத்து தொள்ளாயிரத்து தொண்ணூறு முதல் ஆயிரத்து தொள்ளாயிரத்து தொண்ணூற்று ஐந்து வரை" }
        "2020s" -> date { year: "இரண்டாயிரத்து இருபதுகளின் காலகட்டம்" }

    Args:
        cardinal: cardinal GraphFst
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
        month_name = field("month", month_names)
        year = field("year", year_any)
        year4 = field("year", year_4)
        era = field("era", year_suffix)

        space = pynutil.delete(" ") + insert_space
        optional_era = pynini.closure(space + era, 0, 1)
        optional_comma = pynini.closure(pynutil.delete(","), 0, 1)

        # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY (one separator per date)
        graph_dmy = pynini.union(
            *[day + pynutil.delete(s) + insert_space + month_num + pynutil.delete(s) + insert_space + year4 for s in "/-."]
        )
        # YYYY-MM-DD
        graph_ymd = year4 + pynutil.delete("-") + insert_space + month_num + pynutil.delete("-") + insert_space + day

        graph_d_month_y = day + space + month_name + optional_comma + space + year + optional_era
        graph_d_month = day + space + month_name
        graph_month_y = month_name + optional_comma + space + year + optional_era
        graph_year_era = year + space + era

        # Year ranges: "1990–1995", "1990-1995"
        year_range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " முதல் ")
        graph_year_range = field("year", year_4 + year_range_sep + year_4 + pynutil.insert(" வரை"))

        # Decades: "1990s", "2020s", "1990கள்", "1990-கள்"
        decade_4_digits = pynini.union("1", "2") + NEMO_DIGIT**2 + "0"
        decade_4 = pynini.compose(to_ascii, decade_4_digits @ number).optimize()
        decade_genitive = pynini.compose(
            decade_4,
            pynini.cdrewrite(pynini.cross("ு", "ுகளின் காலகட்டம்"), "", "[EOS]", NEMO_SIGMA)
        ).optimize()
        decade_suffix = pynutil.delete(pynini.union("s", "'s", "கள்", "-கள்"))
        graph_decade = field("year", (decade_genitive + decade_suffix).optimize())

        final_graph = (
            graph_dmy
            | graph_ymd
            | graph_d_month_y
            | graph_d_month
            | graph_month_y
            | graph_year_era
            | pynutil.add_weight(graph_year_range, -0.05)
            | pynutil.add_weight(graph_decade, -0.05)
        )

        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph)
