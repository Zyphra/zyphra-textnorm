# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)
from nemo_text_processing.text_normalization.nb.taggers.ordinal import (
    OrdinalFst,
)


def _build_year_graph() -> pynini.Fst:
    """Years 1000-2099 read in standard Norwegian Bokmål pronunciation."""
    # 1100 - 1999: "atten fjorten", "nitten nitti", "nitten hundre"
    century_map = [
        ("11", "elleve"),
        ("12", "tolv"),
        ("13", "tretten"),
        ("14", "fjorten"),
        ("15", "femten"),
        ("16", "seksten"),
        ("17", "sytten"),
        ("18", "atten"),
        ("19", "nitten"),
    ]
    century = pynini.string_map(century_map)

    unit = pynini.string_map(
        [
            ("1", "en"),
            ("2", "to"),
            ("3", "tre"),
            ("4", "fire"),
            ("5", "fem"),
            ("6", "seks"),
            ("7", "sju"),
            ("8", "åtte"),
            ("9", "ni"),
        ]
    )
    teens = pynini.string_map(
        [
            ("10", "ti"),
            ("11", "elleve"),
            ("12", "tolv"),
            ("13", "tretten"),
            ("14", "fjorten"),
            ("15", "femten"),
            ("16", "seksten"),
            ("17", "sytten"),
            ("18", "atten"),
            ("19", "nitten"),
        ]
    )
    ties = pynini.string_map(
        [
            ("2", "tjue"),
            ("3", "tretti"),
            ("4", "førti"),
            ("5", "femti"),
            ("6", "seksti"),
            ("7", "sytti"),
            ("8", "åtti"),
            ("9", "nitti"),
        ]
    )
    compound_tens = ties + unit
    exact_ties = ties + pynutil.delete("0")
    two_digits = teens | exact_ties | compound_tens | (pynutil.delete("0") + unit)

    exact_hundred = pynutil.delete("00") + pynutil.insert(" hundre")

    years_1100_1999 = (
        (century + pynutil.insert(" ") + two_digits)
        | (century + exact_hundred)
    )

    # 2000 - 2099: "to tusen", "to tusen og tjuefire", "tjue tjuefire"
    y2k_exact = pynini.cross("2000", "to tusen")
    y2k_rem_formal = (
        pynini.cross("20", "to tusen og ")
        + two_digits
    )
    y2k_rem_colloquial = (
        pynini.cross("20", "tjue ")
        + two_digits
    )
    years_2000_2099 = y2k_exact | y2k_rem_formal | y2k_rem_colloquial

    # 1000 - 1099: "tusen", "tusen og ti"
    y1k_exact = pynini.cross("1000", "tusen")
    y1k_rem = pynini.cross("10", "tusen og ") + two_digits
    years_1000_1099 = y1k_exact | y1k_rem

    all_years = years_1100_1999 | years_2000_2099 | years_1000_1099
    return all_years.optimize()


class DateFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål dates.
    e.g. 17. mai 1814 -> syttende mai atten fjorten
         17. mai -> syttende mai
         17.05.2024 -> syttende mai to tusen og tjuefire
         2024-05-17 -> syttende mai to tusen og tjuefire
         1990-1995 -> nitten nitti til nitten nittifem
         1990-tallet -> nitten nittitallet
         2020s -> tjuetjuetallet
         500 f.Kr. -> fem hundre før Kristus
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        ord_tagger = OrdinalFst(deterministic=deterministic)
        ord_words = ord_tagger.ord_words
        year_words = (
            _build_year_graph()
            | pynutil.add_weight(NEMO_DIGIT ** 4 @ cardinal.cardinal_masculine, 0.1)
        ).optimize()
        self.year_words = year_words

        months_map = [
            ("januar", "januar"),
            ("februar", "februar"),
            ("mars", "mars"),
            ("april", "april"),
            ("mai", "mai"),
            ("juni", "juni"),
            ("juli", "juli"),
            ("august", "august"),
            ("september", "september"),
            ("oktober", "oktober"),
            ("november", "november"),
            ("desember", "desember"),
            # Abbreviations
            ("jan.", "januar"),
            ("feb.", "februar"),
            ("mar.", "mars"),
            ("apr.", "april"),
            ("jun.", "juni"),
            ("jul.", "juli"),
            ("aug.", "august"),
            ("sep.", "september"),
            ("sept.", "september"),
            ("okt.", "oktober"),
            ("nov.", "november"),
            ("des.", "desember"),
        ]
        month_word = pynini.string_map(months_map)

        # Day ordinal (with dot e.g. "17." or bare "17")
        day_ord = (ord_words + pynutil.delete(".")) | ord_words

        # Day + Month (+ Year)
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        day_space = pynutil.delete(" ") + pynutil.insert(" ")

        day_month = day_ord + day_space + month_word
        day_month_year = (
            day_month
            + day_space
            + year_words
        )

        # Numeric dates:
        # DD.MM.YYYY
        num_month_map = [
            ("01", "januar"),
            ("1", "januar"),
            ("02", "februar"),
            ("2", "februar"),
            ("03", "mars"),
            ("3", "mars"),
            ("04", "april"),
            ("4", "april"),
            ("05", "mai"),
            ("5", "mai"),
            ("06", "juni"),
            ("6", "juni"),
            ("07", "juli"),
            ("7", "juli"),
            ("08", "august"),
            ("8", "august"),
            ("09", "september"),
            ("9", "september"),
            ("10", "oktober"),
            ("11", "november"),
            ("12", "desember"),
        ]
        num_month = pynini.string_map(num_month_map)
        date_sep = pynutil.delete(".") | pynutil.delete("/") | pynutil.delete("-")

        dmy_numeric = (
            day_ord
            + date_sep
            + pynutil.insert(" ")
            + num_month
            + date_sep
            + pynutil.insert(" ")
            + year_words
        )

        # Structured fields preserve arbitrary ISO years while permitting native output order.
        day_padded = (pynini.closure(pynutil.delete("0"), 0, 1) + ord_words)
        self.iso_fst = (
            pynutil.insert('date { year: "')
            + (NEMO_DIGIT ** 4 @ year_words)
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ num_month)
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ day_padded)
            + pynutil.insert('" }')
        ).optimize()

        # Year ranges: 1990-1995, 1990–1995
        dash = (
            pynini.cross("-", " til ")
            | pynini.cross("–", " til ")
            | pynini.cross("—", " til ")
        )
        year_range = year_words + opt_space + dash + opt_space + year_words

        # Decades: 1990-tallet, 2020-tallet, 2020s, 1990s
        decade_map = [
            ("1920-tallet", "nitten tjuetallet"),
            ("1930-tallet", "nitten trettitallet"),
            ("1940-tallet", "nitten førtitallet"),
            ("1950-tallet", "nitten femtitallet"),
            ("1960-tallet", "nitten sekstitallet"),
            ("1970-tallet", "nitten syttitallet"),
            ("1980-tallet", "nitten åttitallet"),
            ("1990-tallet", "nitten nittitallet"),
            ("2000-tallet", "totusentallet"),
            ("2010-tallet", "totusenogtitalls"),
            ("2020-tallet", "tjuetjuetallet"),
            ("1990s", "nitten nittitallet"),
            ("2020s", "tjuetjuetallet"),
            ("2010s", "totusenogtitalls"),
            ("1980s", "nitten åttitallet"),
        ]
        decades = pynini.string_map(decade_map)

        # Eras: 500 f.Kr., 500 e.Kr., 500 BC, 500 AD
        era_bc = (
            pynini.cross("f.Kr.", "før Kristus")
            | pynini.cross("f. Kr.", "før Kristus")
            | pynini.cross("BC", "før Kristus")
            | pynini.cross("B.C.", "før Kristus")
            | pynini.cross("BCE", "før Kristus")
        )
        era_ad = (
            pynini.cross("e.Kr.", "etter Kristus")
            | pynini.cross("e. Kr.", "etter Kristus")
            | pynini.cross("AD", "etter Kristus")
            | pynini.cross("A.D.", "etter Kristus")
            | pynini.cross("CE", "etter Kristus")
        )
        era = era_bc | era_ad

        era_date = (
            cardinal.cardinal_masculine
            + opt_space
            + pynutil.insert(" ")
            + era
        )

        all_dates = (
            day_month_year
            | day_month
            | dmy_numeric
            | year_range
            | decades
            | era_date
        )

        self.graph = all_dates.optimize()
        self.fst = self.graph
