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

import pynini
from pynini.lib import pynutil

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGITS,
    convert_space,
)
from .cardinal import CardinalFst, ODIA_CARDINALS_0_TO_99

MONTHS_MAP = [
    ("1", "ଜାନୁଆରୀ"), ("01", "ଜାନୁଆରୀ"), ("୧", "ଜାନୁଆରୀ"), ("୦୧", "ଜାନୁଆରୀ"),
    ("2", "ଫେବୃଆରୀ"), ("02", "ଫେବୃଆରୀ"), ("୨", "ଫେବୃଆରୀ"), ("୦୨", "ଫେବୃଆରୀ"),
    ("3", "ମାର୍ଚ୍ଚ"), ("03", "ମାର୍ଚ୍ଚ"), ("୩", "ମାର୍ଚ୍ଚ"), ("୦୩", "ମାର୍ଚ୍ଚ"),
    ("4", "ଅପ୍ରେଲ"), ("04", "ଅପ୍ରେଲ"), ("୪", "ଅପ୍ରେଲ"), ("୦୪", "ଅପ୍ରେଲ"),
    ("5", "ମଇ"), ("05", "ମଇ"), ("୫", "ମଇ"), ("୦୫", "ମଇ"),
    ("6", "ଜୁନ"), ("06", "ଜୁନ"), ("୬", "ଜୁନ"), ("୦୬", "ଜୁନ"),
    ("7", "ଜୁଲାଇ"), ("07", "ଜୁଲାଇ"), ("୭", "ଜୁଲାଇ"), ("୦୭", "ଜୁଲାଇ"),
    ("8", "ଅଗଷ୍ଟ"), ("08", "ଅଗଷ୍ଟ"), ("୮", "ଅଗଷ୍ଟ"), ("୦୮", "ଅଗଷ୍ଟ"),
    ("9", "ସେପ୍ଟେମ୍ବର"), ("09", "ସେପ୍ଟେମ୍ବର"), ("୯", "ସେପ୍ଟେମ୍ବର"), ("୦୯", "ସେପ୍ଟେମ୍ବର"),
    ("10", "ଅକ୍ଟୋବର"), ("୧୦", "ଅକ୍ଟୋବର"),
    ("11", "ନଭେମ୍ବର"), ("୧୧", "ନଭେମ୍ବର"),
    ("12", "ଡିସେମ୍ବର"), ("୧୨", "ଡିସେମ୍ବର"),
]

MONTH_NAMES = [
    "ଜାନୁଆରୀ", "ଫେବୃଆରୀ", "ମାର୍ଚ୍ଚ", "ଅପ୍ରେଲ", "ମଇ", "ଜୁନ",
    "ଜୁଲାଇ", "ଅଗଷ୍ଟ", "ସେପ୍ଟେମ୍ବର", "ଅକ୍ଟୋବର", "ନଭେମ୍ବର", "ଡିସେମ୍ବର",
]


class DateFst(GraphFst):
    """
    Finite state transducer for classifying dates in Odia:
        ୨୫/୧୨/୨୦୨୪ -> tokens { name: "ପଚିଶ ଡିସେମ୍ବର ଦୁଇ ହଜାର ଚଉବିଶ" }
        01/04/2024 -> tokens { name: "ଏକ ଅପ୍ରେଲ ଦୁଇ ହଜାର ଚଉବିଶ" }
        2024-12-25 -> tokens { name: "ପଚିଶ ଡିସେମ୍ବର ଦୁଇ ହଜାର ଚଉବିଶ" }
        500 BC -> tokens { name: "ଖ୍ରୀଷ୍ଟପୂର୍ବ ପାଞ୍ଚ ଶହ" }
        2020s -> tokens { name: "ଦୁଇ ହଜାର କୋଡ଼ିଏ ଦଶକ" }
        1995-2005 -> tokens { name: "ଉନିଶ ଶହ ପଞ୍ଚାନବେ ରୁ ଦୁଇ ହଜାର ପାଞ୍ଚ" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        self.cardinal = cardinal

        # Days 1 to 31
        days_pairs = []
        for i in range(1, 32):
            w = ODIA_CARDINALS_0_TO_99[i]
            days_pairs.append((str(i), w))
            days_pairs.append((f"{i:02d}", w))
        day_map = pynini.string_map(days_pairs)
        day_graph = (NORMALIZE_DIGITS @ day_map).optimize()

        month_graph = pynini.string_map(MONTHS_MAP).optimize()
        month_word_graph = pynini.union(*MONTH_NAMES).optimize()

        # Years
        year_graph = (NORMALIZE_DIGITS @ cardinal.cardinal_numbers).optimize()
        two_digit_remainder = (
            pynutil.delete("00")
            | pynutil.insert(" ") + (
                pynutil.delete("0") + cardinal.num_1_99
                | (NEMO_ALL_DIGIT**2 @ cardinal.num_1_99)
            )
        )
        historical_year = NORMALIZE_DIGITS @ (pynini.cross("19", "ଉନିଶ ଶହ") + two_digit_remainder)
        year_named = pynutil.add_weight(historical_year, -0.01) | year_graph
        numeric_year = (NEMO_ALL_DIGIT**2 | NEMO_ALL_DIGIT**4) @ year_named

        sep = pynini.union("/", "-", ".")

        # 1. DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        dmy_graph = (
            day_graph
            + pynutil.delete(sep)
            + pynutil.insert(" ")
            + month_graph
            + pynutil.delete(sep)
            + pynutil.insert(" ")
            + numeric_year
        ).optimize()

        ymd_graph = (
            pynutil.insert('date { year: "')
            + (NEMO_ALL_DIGIT ** 4 @ year_graph)
            + pynutil.insert('" month: "')
            + pynutil.delete(sep)
            + (NEMO_ALL_DIGIT ** 2 @ (NORMALIZE_DIGITS @ month_graph))
            + pynutil.insert('" day: "')
            + pynutil.delete(sep)
            + (NEMO_ALL_DIGIT ** 2 @ day_graph)
            + pynutil.insert('" }')
        )

        # 3. Day + Written Month + Year: "25 ଡିସେମ୍ବର 2024" or "25 ଡିସେମ୍ବର"
        sp = pynini.accep(" ")
        d_month_y = (
            day_graph + sp + month_word_graph + pynini.closure(sp + year_graph, 0, 1)
        ).optimize()

        # 4. Eras: "500 BC" -> "ଖ୍ରୀଷ୍ଟପୂର୍ବ ପାଞ୍ଚ ଶହ"
        era_bc = pynini.union("BC", "B.C.", "BCE", "B.C.E.", "ଖ୍ରୀ.ପୂ.", "ଖ୍ରୀଷ୍ଟପୂର୍ବ")
        era_ad = pynini.union("AD", "A.D.", "CE", "C.E.", "ଖ୍ରୀଷ୍ଟାବ୍ଦ")

        bc_graph = (
            pynutil.insert("ଖ୍ରୀଷ୍ଟପୂର୍ବ ")
            + year_graph
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.delete(era_bc)
        ).optimize()
        ad_graph = (
            pynutil.insert("ଖ୍ରୀଷ୍ଟାବ୍ଦ ")
            + year_graph
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.delete(era_ad)
        ).optimize()

        # Native and international decade notation, with an explicit zero-ending
        # numeric decade rather than an example-specific list of years.
        decade_digits = NORMALIZE_DIGITS @ (
            NEMO_ALL_DIGIT + "0" | NEMO_ALL_DIGIT**3 + "0"
        )
        decade_suffix = pynini.union("s", "'s", " ଦଶକ", " ର ଦଶକ")
        decade_graph = (
            pynini.closure(pynutil.delete("'"), 0, 1)
            + (decade_digits @ year_named)
            + pynutil.delete(decade_suffix)
            + pynutil.insert(" ଦଶକ")
        ).optimize()

        year_four = NEMO_ALL_DIGIT**4 @ year_named
        dash = pynini.union("-", "–", "—", " to ")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        year_range = (
            year_four
            + opt_sp
            + pynutil.delete(dash)
            + pynutil.insert(" ରୁ ")
            + opt_sp
            + year_four
        ).optimize()

        all_dates = (
            dmy_graph
            | d_month_y
            | bc_graph
            | ad_graph
            | decade_graph
            | year_range
        ).optimize()

        self.date_graph = all_dates

        graph = pynutil.insert('name: "') + convert_space(all_dates) + pynutil.insert('"')
        self.fst = (graph | ymd_graph).optimize()
