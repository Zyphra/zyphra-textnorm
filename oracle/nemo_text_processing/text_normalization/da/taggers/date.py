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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.da.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Danish dates.
    Handles:
      - Written dates: "2. januar 2022", "2. jan., 2022", "23. jan. 2022", "1. maj"
      - Numeric dates: "02.01.2000", "02/01/2000", "02-01-2000", "2022-01-02", "2022.01.02"
      - Historical eras: "2. jan. 2022 f.Kr.", "2022 f.Kr.", "44 f.Kr.", "33 e.Kr.", "500 BC"
      - Decades: "2020'erne", "2020erne", "2020s", "1990'erne", "1920-tallet", "1920-talsbygninger"
      - Year ranges: "1990–1995", "2020-2024"
    """

    def __init__(self, cardinal: CardinalFst, ordinal: OrdinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Danish month names and abbreviations
        months = [
            ("1", "januar", ["januar", "jan.", "jan"]),
            ("2", "februar", ["februar", "feb.", "feb"]),
            ("3", "marts", ["marts", "mar.", "mar"]),
            ("4", "april", ["april", "apr.", "apr"]),
            ("5", "maj", ["maj"]),
            ("6", "juni", ["juni", "jun.", "jun"]),
            ("7", "juli", ["juli", "jul.", "jul"]),
            ("8", "august", ["august", "aug.", "aug"]),
            ("9", "september", ["september", "sep.", "sep", "sept.", "sept"]),
            ("10", "oktober", ["oktober", "okt.", "okt"]),
            ("11", "november", ["november", "nov.", "nov"]),
            ("12", "december", ["december", "dec.", "dec"]),
        ]

        month_words = pynini.union(
            *[
                pynini.cross(pynini.union(*abbrs), spoken)
                for _, spoken, abbrs in months
            ]
        )

        month_num_to_word = pynini.union(
            *[
                pynini.cross(num, spoken)
                | pynini.cross(f"0{num}" if len(num) == 1 else num, spoken)
                for num, spoken, _ in months
            ]
        )

        # Days: 1-31 as ordinals
        day_ordinal_words = [
            ("1", "første"),
            ("01", "første"),
            ("2", "anden"),
            ("02", "anden"),
            ("3", "tredje"),
            ("03", "tredje"),
            ("4", "fjerde"),
            ("04", "fjerde"),
            ("5", "femte"),
            ("05", "femte"),
            ("6", "sjette"),
            ("06", "sjette"),
            ("7", "syvende"),
            ("07", "syvende"),
            ("8", "ottende"),
            ("08", "ottende"),
            ("9", "niende"),
            ("09", "niende"),
            ("10", "tiende"),
            ("11", "ellevte"),
            ("12", "tolvte"),
            ("13", "trettende"),
            ("14", "fjortende"),
            ("15", "femtende"),
            ("16", "sekstende"),
            ("17", "syttende"),
            ("18", "attende"),
            ("19", "nittende"),
            ("20", "tyvende"),
            ("21", "enogtyvende"),
            ("22", "toogtyvende"),
            ("23", "treogtyvende"),
            ("24", "fireogtyvende"),
            ("25", "femogtyvende"),
            ("26", "seksogtyvende"),
            ("27", "syvogtyvende"),
            ("28", "otteogtyvende"),
            ("29", "niogtyvende"),
            ("30", "tredivte"),
            ("31", "enogtredivte"),
        ]

        # Day with dot (e.g. "2.", "23.", "1.") or suffix ("2:a", "2.den") or bare number ("2", "23")
        dot_opt = pynini.closure(pynutil.delete("."), 0, 1)
        day_with_dot = pynini.union(
            *[
                pynini.cross(d, spoken) + dot_opt
                | pynini.cross(f"{d}:a", spoken)
                | pynini.cross(f"{d}.ste", spoken)
                | pynini.cross(f"{d}.den", spoken)
                | pynini.cross(f"{d}.det", spoken)
                | pynini.cross(f"{d}.de", spoken)
                | pynini.cross(f"{d}.te", spoken)
                | pynini.cross(f"{d}.ende", spoken)
                for d, spoken in day_ordinal_words
            ]
        )

        # Years: 1000-2999
        # In Danish, years like 2022 are spoken as "to tusind og toogtyve"
        # 2000 is "to tusind"
        # 1990 is "nitten hundrede og halvfems"
        year_1900 = pynini.cross("19", "nitten hundrede og ") + cardinal.num_1_to_999_neuter
        year_1900_round = pynini.cross("1900", "nitten hundrede")
        year_2000_round = pynini.cross("2000", "to tusind")
        year_2000 = (
            year_2000_round
            | pynini.cross("200", "to tusind og ") + cardinal.single_digit
            | pynini.cross("20", "to tusind og ") + cardinal.num_1_to_999_neuter
        )
        year_1000 = pynini.cross("1000", "et tusind") | pynini.cross("1000", "tusind")

        # General 4-digit and historical years
        year_graph = (
            year_2000
            | year_1900_round
            | year_1900
            | year_1000
            | cardinal.integer_neuter
        ).optimize()

        # Eras: "f.Kr.", "e.Kr.", "f.v.t.", "v.t.", "BC", "AD"
        era_bc = pynini.cross(pynini.union("f.Kr.", "f. Kr.", "f.v.t.", "BC", "B.C.", "BCE"), " før Kristus")
        era_ad = pynini.cross(pynini.union("e.Kr.", "e. Kr.", "v.t.", "AD", "A.D.", "CE"), " efter Kristus")
        era = era_bc | era_ad
        opt_era = pynini.closure(pynutil.delete(" ") + era | era, 0, 1)

        # 1. Written date with year: e.g. "2. januar, 2022", "2. jan. 2022", "2. jan. 2022 f.Kr."
        comma_opt = pynini.closure(pynutil.delete(","), 0, 1)
        written_day_month_year = (
            day_with_dot
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + month_words
            + comma_opt
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + year_graph
            + opt_era
        )

        # 2. Written day + month only: e.g. "2. januar", "23. jan.", "1. maj"
        written_day_month = (
            day_with_dot
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + month_words
        )

        # 3. Numeric dates:
        # DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY
        sep_num = pynini.union(".", "/", "-")

        numeric_dmy = (
            pynini.union(*[pynini.cross(d, spoken) for d, spoken in day_ordinal_words])
            + pynutil.delete(sep_num)
            + pynutil.insert(" ")
            + month_num_to_word
            + pynutil.delete(sep_num)
            + pynutil.insert(" ")
            + year_graph
        )

        # YYYY-MM-DD, YYYY.MM.DD (ISO format)
        numeric_ymd = (
            pynutil.delete(NEMO_DIGIT**4)
            + pynutil.delete(sep_num)
            + pynutil.delete(NEMO_DIGIT**2)
            + pynutil.delete(sep_num)
        ) # We need to capture the day and month and reorder:
        # Let's construct explicit pairs for ISO dates
        iso_dates = []
        for m_num, m_spoken, _ in months:
            m_str = f"0{m_num}" if len(m_num) == 1 else m_num
            for d_str, d_spoken in day_ordinal_words:
                if len(d_str) == 2:
                    # YYYY-MM-DD -> d_spoken m_spoken year
                    iso_dates.append(
                        (m_str, d_str, f"{d_spoken} {m_spoken}")
                    )

        iso_date_graph = pynini.union(
            *[
                pynutil.insert(dm_spoken + " ")
                + year_graph
                + pynutil.delete(sep_num)
                + pynutil.delete(m_str)
                + pynutil.delete(sep_num)
                + pynutil.delete(d_str)
                for m_str, d_str, dm_spoken in iso_dates
            ]
        )
        # Note: year_graph matched first in iso_date_graph, then separator, month, separator, day!

        # 4. Standalone year with era: e.g. "2022 f.Kr.", "44 f.Kr.", "33 e.Kr.", "500 BC"
        year_with_era = (
            year_graph
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + era
        )

        # 5. Decades: "2020'erne", "2020erne", "2020s", "1990'erne", "1920-tallet", "1920-talsbygninger"
        decade_suffix = pynini.closure(pynutil.delete(pynini.union("'", "’", "‘")), 0, 1) + pynutil.delete(
            pynini.union("erne", "s")
        )
        decade_names = [
            ("1920", "nittentyverne"),
            ("1930", "nittentrediverne"),
            ("1940", "nittenfyrrerne"),
            ("1950", "nittenhalvtredserne"),
            ("1960", "nittentresserne"),
            ("1970", "nittenhalvfjerdserne"),
            ("1980", "nittenfirserne"),
            ("1990", "nittenhalvfemserne"),
            ("2000", "totusinderne"),
            ("2010", "totusindtierne"),
            ("2020", "totusindtyverne"),
        ]
        decade_year = (NEMO_DIGIT - "0") + NEMO_DIGIT ** 2 + "0"
        decade_words = (
            pynini.string_map(decade_names)
            | pynutil.add_weight(
                pynutil.insert("årtiet fra ") + (decade_year @ year_graph), 0.05
            )
        )
        non_century_year = pynini.difference(decade_year, NEMO_DIGIT ** 2 + "00")
        decades = (
            decade_words + decade_suffix
            | (non_century_year @ decade_words)
            + pynutil.delete(pynini.union("-tallet", "tallet"))
        )
        decade_building = (
            pynini.string_map([(year, name[:-2]) for year, name in decade_names])
            + pynini.cross("-talsbygninger", "talsbygninger")
        )
        decade_century = (
            (((NEMO_DIGIT - "0") + NEMO_DIGIT + "00") @ year_graph)
            + pynini.cross("-tallet", "tallet")
        )

        # 6. Year range: "1990–1995", "1990-1995", "2020-2024"
        range_dash = pynini.cross(pynini.union("–", "-", "—"), " til ")
        year_range = (
            year_graph
            + opt_sp
            + range_dash
            + opt_sp
            + year_graph
        )

        all_dates = (
            written_day_month_year
            | written_day_month
            | numeric_dmy
            | iso_date_graph
            | year_with_era
            | decade_building
            | decade_century
            | pynutil.add_weight(decades, -0.2)
            | year_range
        ).optimize()

        self.graph = all_dates

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
