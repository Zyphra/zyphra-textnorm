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

from nemo_text_processing.text_normalization.pa.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_NON_ZERO,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.pa.utils import get_abs_path

days = pynini.string_file(get_abs_path("data/date/days.tsv"))
day_ordinal = pynini.string_file(get_abs_path("data/date/day_ordinal.tsv"))
months = pynini.string_file(get_abs_path("data/date/months.tsv"))
month_names = pynini.string_file(get_abs_path("data/date/month_names.tsv"))
month_abbr = pynini.string_file(get_abs_path("data/date/month_abbr.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date (CLDR pa gregorian month names), e.g.
        "੦੧-੦੪-੨੦੨੪" -> date { day: "ਇੱਕ" month: "ਅਪ੍ਰੈਲ" year: "ਦੋ ਹਜ਼ਾਰ ਚੌਵੀ" }
        "2024-04-01" -> date { day: "ਇੱਕ" month: "ਅਪ੍ਰੈਲ" year: "ਦੋ ਹਜ਼ਾਰ ਚੌਵੀ" }
        "੬ ਮਾਰਚ, ੨੦੧੦" -> date { day: "ਛੇ" month: "ਮਾਰਚ" year: "ਦੋ ਹਜ਼ਾਰ ਦਸ" }
        "੫੦੦ ਈ.ਪੂ." -> date { year: "ਪੰਜ ਸੌ" era: "ਈਸਾ ਪੂਰਵ" }
        "2020s" -> date { era: "ਦੋ ਹਜ਼ਾਰ ਵੀਹ ਦਾ ਦਹਾਕਾ" }

    Dates are spoken day month year; years are plain cardinals.

    Args:
        cardinal: CardinalFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="date", kind="classify")

        year_digits = NEMO_ALL_NON_ZERO + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT + NEMO_ALL_DIGIT
        graph_year = pynini.compose(year_digits, cardinal.graph_thousands).optimize()

        era_year_digits = NEMO_ALL_NON_ZERO + pynini.closure(NEMO_ALL_DIGIT, 0, 3)
        graph_era_year = pynini.compose(era_year_digits, cardinal.graph_without_leading_zeros).optimize()

        delete_comma = pynutil.delete(",")
        delete_space = pynutil.delete(" ")
        delete_optional_space = pynini.closure(pynutil.delete(" "), 0, 1)
        delete_comma_sep = pynini.closure(delete_comma, 0, 1) + delete_space

        day = pynutil.insert("day: \"") + days + pynutil.insert("\"") + insert_space
        day_written = pynutil.insert("day: \"") + (days | day_ordinal) + pynutil.insert("\"") + insert_space
        month_numeric = pynutil.insert("month: \"") + months + pynutil.insert("\"") + insert_space
        month_name = (
            pynutil.insert("month: \"")
            + (month_names | (month_abbr + pynini.closure(pynutil.delete("."), 0, 1)))
            + pynutil.insert("\"")
            + insert_space
        )
        year = pynutil.insert("year: \"") + graph_year + pynutil.insert("\"")
        era_year = pynutil.insert("year: \"") + graph_era_year + pynutil.insert("\"")
        era = pynutil.insert(" era: \"") + delete_optional_space + year_suffix + pynutil.insert("\"")
        optional_era = pynini.closure(era, 0, 1)

        graph_numeric = pynini.union(
            *[day + pynutil.delete(sep) + month_numeric + pynutil.delete(sep) + year for sep in ("/", "-", ".")]
        )
        graph_iso = pynini.union(
            *[
                pynutil.insert("year: \"")
                + graph_year
                + pynutil.insert("\" ")
                + pynutil.delete(sep)
                + month_numeric
                + pynutil.delete(sep)
                + pynutil.insert("day: \"")
                + days
                + pynutil.insert("\"")
                for sep in ("-", "/")
            ]
        )
        graph_day_month_year = day_written + delete_space + month_name + delete_comma_sep + year + optional_era
        graph_day_month = day_written + delete_space + pynutil.add_weight(month_name, 0.01)
        graph_month_year = month_name + delete_comma_sep + year + optional_era
        graph_year_era = era_year + era
        graph_year_range = (
            pynutil.insert("era: \"")
            + graph_year
            + pynini.cross(pynini.union("-", "–"), " ਤੋਂ ")
            + graph_year
            + pynutil.insert("\"")
        )

        # Decades: native ("1990 ਦਾ ਦਹਾਕਾ", "੯੦ ਦਾ ਦਹਾਕਾ")
        # and international ("2020s", "1990s", "90s", "'90s")
        decade_tail = pynini.string_map(
            [
                ("00", " ਦਾ ਦਹਾਕਾ"),
                ("੦੦", " ਦਾ ਦਹਾਕਾ"),
                ("10", " ਦਸ ਦਾ ਦਹਾਕਾ"),
                ("੧੦", " ਦਸ ਦਾ ਦਹਾਕਾ"),
                ("20", " ਵੀਹ ਦਾ ਦਹਾਕਾ"),
                ("੨੦", " ਵੀਹ ਦਾ ਦਹਾਕਾ"),
                ("30", " ਤੀਹ ਦਾ ਦਹਾਕਾ"),
                ("੩੦", " ਤੀਹ ਦਾ ਦਹਾਕਾ"),
                ("40", " ਚਾਲੀ ਦਾ ਦਹਾਕਾ"),
                ("੪੦", " ਚਾਲੀ ਦਾ ਦਹਾਕਾ"),
                ("50", " ਪੰਜਾਹ ਦਾ ਦਹਾਕਾ"),
                ("੫੦", " ਪੰਜਾਹ ਦਾ ਦਹਾਕਾ"),
                ("60", " ਸੱਠ ਦਾ ਦਹਾਕਾ"),
                ("੬੦", " ਸੱਠ ਦਾ ਦਹਾਕਾ"),
                ("70", " ਸੱਤਰ ਦਾ ਦਹਾਕਾ"),
                ("੭੦", " ਸੱਤਰ ਦਾ ਦਹਾਕਾ"),
                ("80", " ਅੱਸੀ ਦਾ ਦਹਾਕਾ"),
                ("੮੦", " ਅੱਸੀ ਦਾ ਦਹਾਕਾ"),
                ("90", " ਨੱਬੇ ਦਾ ਦਹਾਕਾ"),
                ("੯੦", " ਨੱਬੇ ਦਾ ਦਹਾਕਾ"),
            ]
        )
        century_19 = (
            pynini.compose(
                (pynini.union("1", "੧") + NEMO_ALL_DIGIT),
                cardinal.teens_and_ties,
            )
            + pynutil.insert(" ਸੌ")
        )
        century_20 = pynini.cross(pynini.union("20", "੨੦"), "ਦੋ ਹਜ਼ਾਰ")
        century_prefix = century_19 | century_20
        century_decade_num = century_prefix + decade_tail
        century_decade_word = (
            pynutil.insert("era: \"")
            + century_decade_num
            + pynutil.delete("s")
            + pynutil.insert("\"")
        )
        short_decade = (
            pynutil.insert("era: \"")
            + pynini.closure(pynutil.delete("'"), 0, 1)
            + pynini.string_map(
                [
                    ("20s", "ਵੀਹ ਦਾ ਦਹਾਕਾ"),
                    ("30s", "ਤੀਹ ਦਾ ਦਹਾਕਾ"),
                    ("40s", "ਚਾਲੀ ਦਾ ਦਹਾਕਾ"),
                    ("50s", "ਪੰਜਾਹ ਦਾ ਦਹਾਕਾ"),
                    ("60s", "ਸੱਠ ਦਾ ਦਹਾਕਾ"),
                    ("70s", "ਸੱਤਰ ਦਾ ਦਹਾਕਾ"),
                    ("80s", "ਅੱਸੀ ਦਾ ਦਹਾਕਾ"),
                    ("90s", "ਨੱਬੇ ਦਾ ਦਹਾਕਾ"),
                ]
            )
            + pynutil.insert("\"")
        )

        final_graph = (
            graph_numeric
            | graph_iso
            | graph_day_month_year
            | graph_day_month
            | graph_month_year
            | graph_year_era
            | graph_year_range
            | century_decade_word
            | short_decade
        )
        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph)
