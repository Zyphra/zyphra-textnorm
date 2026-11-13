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

from nemo_text_processing.text_normalization.bn.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALL_NON_ZERO,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.bn.utils import get_abs_path

days = pynini.string_file(get_abs_path("data/date/days.tsv"))
day_ordinal = pynini.string_file(get_abs_path("data/date/day_ordinal.tsv"))
months = pynini.string_file(get_abs_path("data/date/months.tsv"))
month_names = pynini.string_file(get_abs_path("data/date/month_names.tsv"))
month_abbr = pynini.string_file(get_abs_path("data/date/month_abbr.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date (CLDR bn gregorian month names), e.g.
        "০১-০৪-২০২৪" -> date { day: "এক" month: "এপ্রিল" year: "দুই হাজার চব্বিশ" }
        "2024-04-01" -> date { day: "এক" month: "এপ্রিল" year: "দুই হাজার চব্বিশ" }
        "৬ মার্চ, ২০১০" -> date { day: "ছয়" month: "মার্চ" year: "দুই হাজার দশ" }
        "২১শে ফেব্রুয়ারি ১৯৫২" -> date { day: "একুশে" month: "ফেব্রুয়ারি" year: "এক হাজার নয়শো বাহান্ন" }
        "৩১ মে ১৯৯০ খ্রি." -> date { day: "একত্রিশ" month: "মে" year: "এক হাজার নয়শো নব্বই" era: "খ্রিস্টাব্দ" }
        "৫০০ খ্রি." -> date { year: "পাঁচশো" era: "খ্রিস্টাব্দ" }
        "2020s" -> date { era: "দুই হাজার বিশের দশক" }
        "1990-এর দশক" -> date { era: "এক হাজার নয়শো নব্বইয়ের দশক" }

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
            + pynini.cross(pynini.union("-", "–"), " থেকে ")
            + graph_year
            + pynutil.insert("\"")
        )

        # Decades: native ("1990-এর দশক", "১৯৯০-এর দশক", "1990 এর দশক", "৯০-এর দশক")
        # and international ("2020s", "1990s", "90s", "'90s")
        decade_tail = pynini.string_map(
            [
                ("00", "শোয়ের দশক"),
                ("০০", "শোয়ের দশক"),
                ("10", " দশের দশক"),
                ("১০", " দশের দশক"),
                ("20", " বিশের দশক"),
                ("২০", " বিশের দশক"),
                ("30", " ত্রিশের দশক"),
                ("৩০", " ত্রিশের দশক"),
                ("40", " চল্লিশের দশক"),
                ("৪০", " চল্লিশের দশক"),
                ("50", " পঞ্চাশের দশক"),
                ("৫০", " পঞ্চাশের দশক"),
                ("60", " ষাটের দশক"),
                ("৬০", " ষাটের দশক"),
                ("70", " সত্তরের দশক"),
                ("৭০", " সত্তরের দশক"),
                ("80", " আশির দশক"),
                ("৮০", " আশির দশক"),
                ("90", " নব্বইয়ের দশক"),
                ("৯০", " নব্বইয়ের দশক"),
            ]
        )
        decade_2d_stem = pynini.string_map(
            [
                ("10", "দশের দশক"),
                ("১০", "দশের দশক"),
                ("20", "বিশের দশক"),
                ("২০", "বিশের দশক"),
                ("30", "ত্রিশের দশক"),
                ("৩০", "ত্রিশের দশক"),
                ("40", "চল্লিশের দশক"),
                ("৪০", "চল্লিশের দশক"),
                ("50", "পঞ্চাশের দশক"),
                ("৫০", "পঞ্চাশের দশক"),
                ("60", "ষাটের দশক"),
                ("৬০", "ষাটের দশক"),
                ("70", "সত্তরের দশক"),
                ("৭০", "সত্তরের দশক"),
                ("80", "আশির দশক"),
                ("৮০", "আশির দশক"),
                ("90", "নব্বইয়ের দশক"),
                ("৯০", "নব্বইয়ের দশক"),
            ]
        )
        # 1100..1990 or 2100..2990: <thousands> হাজার <hundreds>শো + <decade_tail>
        # 1000..1090 or 2000..2090: <thousands> হাজার + <decade_tail_after_zero_hundred>
        millennium_prefix = pynini.union("1", "2", "১", "২") @ cardinal.digit + pynutil.insert(" হাজার")
        nonzero_hundred_part = cardinal.digit + pynutil.insert("শো")
        zero_hundred_tail = pynini.union("000", "০০০") @ pynini.string_map(
            [("000", "য়ের দশক"), ("০০০", "য়ের দশক")]
        ) | (pynutil.delete(pynini.union("0", "০")) + decade_tail)

        decade_4d_stem = millennium_prefix + (
            (pynutil.insert(" ") + nonzero_hundred_part + decade_tail) | zero_hundred_tail
        )
        decade_suffix = pynini.union(
            "s",
            "'s",
            "-এর দশক",
            " এর দশক",
            "এর দশক",
        )
        graph_decade_4d = decade_4d_stem + pynutil.delete(decade_suffix)
        graph_decade_2d = (
            pynini.closure(pynutil.delete("'"), 0, 1) + decade_2d_stem + pynutil.delete(decade_suffix)
        )
        graph_decade = pynutil.insert('era: "') + (graph_decade_4d | graph_decade_2d) + pynutil.insert('"')

        final_graph = (
            pynutil.add_weight(graph_numeric, -0.5)
            | pynutil.add_weight(graph_iso, -0.5)
            | pynutil.add_weight(graph_day_month_year, -0.5)
            | graph_day_month
            | graph_month_year
            | pynutil.add_weight(graph_year_era, -0.05)
            | pynutil.add_weight(graph_year_range, -0.005)
            | pynutil.add_weight(graph_decade, -0.1)
        )

        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph)
