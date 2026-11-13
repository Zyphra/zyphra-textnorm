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

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_DIGIT,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path

months = pynini.string_file(get_abs_path("data/date/months.tsv"))
month_names = pynini.string_file(get_abs_path("data/date/month_names.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date. Fields are tagged in written order; the verbalizer only
    accepts day month year [era], so the normalizer's field permutation speaks every date in that order, e.g.
        "25/12/2024" -> date { day: "ఇరవై ఐదు" month: "డిసెంబర్" year: "రెండు వేల ఇరవై నాలుగు" }
        "2024-12-25" -> date { year: "రెండు వేల ఇరవై నాలుగు" month: "డిసెంబర్" day: "ఇరవై ఐదు" }
        "15 ఆగస్టు 1947" -> date { day: "పదిహేను" month: "ఆగస్టు" year: "వెయ్యి తొమ్మిది వందల నలభై ఏడు" }
        "1947 క్రీ.శ." -> date { year: "వెయ్యి తొమ్మిది వందల నలభై ఏడు" era: "క్రీస్తు శకం" }
        "1990–1995" -> date { year: "వెయ్యి తొమ్మిది వందల తొంభై నుండి వెయ్యి తొమ్మిది వందల తొంభై ఐదు" }
        "2020s" -> date { year: "రెండు వేల ఇరవైల దశాబ్దం" }
        "1990ల" -> date { year: "వెయ్యి తొమ్మిది వందల తొంభైల దశాబ్దం" }

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

        # Year ranges: "1990–1995", "1990-1995", "1995–2005" -> "... నుండి ..."
        year_range_sep = pynini.cross(pynini.union("-", "–", " - ", " – "), " నుండి ")
        graph_year_range = field("year", year_4 + year_range_sep + year_4)

        # Decades:
        #   - international "1990s", "2020s", "1990's" -> "...ల దశాబ్దం"
        #   - native Telugu "1990ల", "2020ల" -> "...ల దశాబ్దం" (or "1990ల దశాబ్దం" -> "...ల దశాబ్దం")
        #   - "1990లలో" -> "...లలో"
        decade_4_digits = pynini.union("1", "2") + NEMO_DIGIT**2 + "0"
        decade_4 = pynini.compose(to_ascii, decade_4_digits @ number).optimize()
        # If the spoken form already ends in "ల" (e.g. 2000 -> "రెండు వేల"), avoid doubling "ల"
        ends_in_la = NEMO_SIGMA + "ల"
        decade_genitive = (
            pynini.compose(decade_4, ends_in_la)
            | pynini.compose(decade_4, pynini.difference(NEMO_SIGMA, ends_in_la)) + pynutil.insert("ల")
        ).optimize()
        decade_intl = decade_genitive + pynutil.delete(pynini.union("s", "'s")) + pynutil.insert(" దశాబ్దం")
        decade_te = (
            decade_genitive
            + pynutil.delete("ల")
            + (
                pynini.cross("లో", "లో")
                | pynutil.delete(" దశాబ్దం") + pynutil.insert(" దశాబ్దం")
                | pynutil.insert(" దశాబ్దం")
            )
        )
        graph_decade = field("year", (decade_intl | decade_te).optimize())

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
