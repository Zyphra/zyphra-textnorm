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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Finnish dates, decades, and eras, e.g.
        "15.3.2024" -> tokens { name: "viidestoista maaliskuuta kaksituhattakaksikymmentäneljä" }
        "15. maaliskuuta 2024" -> tokens { name: "viidestoista maaliskuuta kaksituhattakaksikymmentäneljä" }
        "25/12/2024" -> tokens { name: "kaksikymmentäviides joulukuuta kaksituhattakaksikymmentäneljä" }
        "2024-12-25" -> tokens { name: "kaksikymmentäviides joulukuuta kaksituhattakaksikymmentäneljä" }
        "1990–1995" -> tokens { name: "tuhatyhdeksänsataayhdeksänkymmentä viiva tuhatyhdeksänsataayhdeksänkymmentäviisi" }
        "1990-luku" -> tokens { name: "tuhatyhdeksänsataayhdeksänkymmentäluku" }
        "500 eaa." -> tokens { name: "viisisataa ennen ajanlaskun alkua" }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        # Days 1-31 (with optional dot or leading zero)
        day_names = [
            ("1", "ensimmäinen"),
            ("01", "ensimmäinen"),
            ("2", "toinen"),
            ("02", "toinen"),
            ("3", "kolmas"),
            ("03", "kolmas"),
            ("4", "neljäs"),
            ("04", "neljäs"),
            ("5", "viides"),
            ("05", "viides"),
            ("6", "kuudes"),
            ("06", "kuudes"),
            ("7", "seitsemäs"),
            ("07", "seitsemäs"),
            ("8", "kahdeksas"),
            ("08", "kahdeksas"),
            ("9", "yhdeksäs"),
            ("09", "yhdeksäs"),
            ("10", "kymmenes"),
            ("11", "yhdestoista"),
            ("12", "kahdestoista"),
            ("13", "kolmestoista"),
            ("14", "neljästoista"),
            ("15", "viidestoista"),
            ("16", "kuudestoista"),
            ("17", "seitsemästoista"),
            ("18", "kahdeksastoista"),
            ("19", "yhdeksästoista"),
            ("20", "kahdeskymmenes"),
            ("21", "kahdeskymmenesensimmäinen"),
            ("22", "kahdeskymmenestoinen"),
            ("23", "kahdeskymmeneskolmas"),
            ("24", "kahdeskymmenesneljäs"),
            ("25", "kaksikymmentäviides"),
            ("26", "kaksikymmentäkuudes"),
            ("27", "kaksikymmentäseitsemäs"),
            ("28", "kaksikymmentäkahdeksas"),
            ("29", "kaksikymmentäyhdeksäs"),
            ("30", "kolmaskymmenes"),
            ("31", "kolmaskymmenesensimmäinen"),
        ]
        day_num = pynini.string_map(day_names)
        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)
        day_graph = day_num + opt_dot

        # Months: numbers (1-12, 01-12) and names in partitive
        month_data = [
            ("1", "tammikuuta"),
            ("01", "tammikuuta"),
            ("2", "helmikuuta"),
            ("02", "helmikuuta"),
            ("3", "maaliskuuta"),
            ("03", "maaliskuuta"),
            ("4", "huhtikuuta"),
            ("04", "huhtikuuta"),
            ("5", "toukokuuta"),
            ("05", "toukokuuta"),
            ("6", "kesäkuuta"),
            ("06", "kesäkuuta"),
            ("7", "heinäkuuta"),
            ("07", "heinäkuuta"),
            ("8", "elokuuta"),
            ("08", "elokuuta"),
            ("9", "syyskuuta"),
            ("09", "syyskuuta"),
            ("10", "lokakuuta"),
            ("11", "marraskuuta"),
            ("12", "joulukuuta"),
        ]
        month_num = pynini.string_map(month_data)

        month_names_data = [
            ("tammikuuta", "tammikuuta"),
            ("helmikuuta", "helmikuuta"),
            ("maaliskuuta", "maaliskuuta"),
            ("huhtikuuta", "huhtikuuta"),
            ("toukokuuta", "toukokuuta"),
            ("kesäkuuta", "kesäkuuta"),
            ("heinäkuuta", "heinäkuuta"),
            ("elokuuta", "elokuuta"),
            ("syyskuuta", "syyskuuta"),
            ("lokakuuta", "lokakuuta"),
            ("marraskuuta", "marraskuuta"),
            ("joulukuuta", "joulukuuta"),
            ("tammikuu", "tammikuu"),
            ("helmikuu", "helmikuu"),
            ("maaliskuu", "maaliskuu"),
            ("huhtikuu", "huhtikuu"),
            ("toukokuu", "toukokuu"),
            ("kesäkuu", "kesäkuu"),
            ("heinäkuu", "heinäkuu"),
            ("elokuu", "elokuu"),
            ("syyskuu", "syyskuu"),
            ("lokakuu", "lokakuu"),
            ("marraskuu", "marraskuu"),
            ("joulukuu", "joulukuu"),
            ("tammi", "tammikuuta"),
            ("helmi", "helmikuuta"),
            ("maalis", "maaliskuuta"),
            ("huhti", "huhtikuuta"),
            ("touko", "toukokuuta"),
            ("kesä", "kesäkuuta"),
            ("heinä", "heinäkuuta"),
            ("elo", "elokuuta"),
            ("syys", "syyskuuta"),
            ("loka", "lokakuuta"),
            ("marras", "marraskuuta"),
            ("joulu", "joulukuuta"),
        ]
        month_name = pynini.string_map(month_names_data)

        cardinal_nums = cardinal.all_nums_no_tokens
        year_4d = pynini.closure(NEMO_DIGIT, 4, 4) @ cardinal_nums
        year_graph = year_4d

        # 1. Written dates: "15. maaliskuuta 2024", "15. maaliskuuta", "1. toukokuuta"
        written_date_full = (
            day_graph
            + pynutil.delete(pynini.closure(".", 0, 1))
            + pynutil.insert(" ")
            + pynutil.delete(pynini.closure(" ", 1))
            + month_name
            + pynutil.insert(" ")
            + pynutil.delete(pynini.closure(" ", 1))
            + year_graph
        )
        written_date_short = (
            day_graph
            + pynutil.delete(pynini.closure(".", 0, 1))
            + pynutil.insert(" ")
            + pynutil.delete(pynini.closure(" ", 1))
            + month_name
        )

        # 2. Numeric dot dates: "15.3.2024", "15.03.2024"
        numeric_dot_full = (
            day_num
            + pynutil.delete(".")
            + pynutil.insert(" ")
            + month_num
            + pynutil.delete(".")
            + pynutil.insert(" ")
            + year_graph
        )
        # Numeric dot short: "15.3." -> "viidestoista maaliskuuta"
        numeric_dot_short = (
            day_num
            + pynutil.delete(".")
            + pynutil.insert(" ")
            + month_num
            + pynutil.delete(".")
        )

        # 3. Slash dates: "25/12/2024"
        numeric_slash_full = (
            day_num
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + month_num
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + year_graph
        )

        iso_date = (
            pynutil.insert('date { year: "')
            + (NEMO_DIGIT ** 4 @ year_graph)
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ month_num)
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ day_num)
            + pynutil.insert('" }')
        )

        # 5. Year ranges: "1990–1995", "1990-1995", "2020-2024"
        dash = pynini.union("-", "–", "—")
        year_range = (
            year_4d
            + pynini.cross(dash, " viiva ")
            + year_4d
        )

        # Standalone year with dot at sentence end: "1990." -> "tuhatyhdeksänsataayhdeksänkymmentä"
        year_dot = year_4d + pynutil.delete(".")

        # 6. Decades: "1990-luku", "1990-luvulla", "1990-luvun"
        decades_data = [
            ("1920-luku", "tuhatyhdeksänsataakaksikymmentäluku"),
            ("1930-luku", "tuhatyhdeksänsataakolmekymmentäluku"),
            ("1940-luku", "tuhatyhdeksänsataaneljäkymmentäluku"),
            ("1950-luku", "tuhatyhdeksänsataaviisikymmentäluku"),
            ("1960-luku", "tuhatyhdeksänsataakuusikymmentäluku"),
            ("1970-luku", "tuhatyhdeksänsataaseitsemänkymmentäluku"),
            ("1980-luku", "tuhatyhdeksänsataakahdeksankymmentäluku"),
            ("1990-luku", "tuhatyhdeksänsataayhdeksänkymmentäluku"),
            ("1990-luvulla", "tuhatyhdeksänsataayhdeksänkymmentäluvulla"),
            ("1990-luvun", "tuhatyhdeksänsataayhdeksänkymmentäluvun"),
            ("2000-luku", "kaksituhattaluku"),
            ("2010-luku", "kaksituhattakymmenenluku"),
            ("2020-luku", "kaksituhattakaksikymmentäluku"),
            ("2020-luvulla", "kaksituhattakaksikymmentäluvulla"),
            ("2020-luvun", "kaksituhattakaksikymmentäluvun"),
        ]
        decades = pynini.string_map(decades_data)

        # 7. Eras: "500 eaa.", "500 e.a.a.", "500 eKr.", "500 BC"
        era_bc = pynini.union("eaa.", "eaa", "e.a.a.", "eKr.", "e.Kr.", "BC", "B.C.", "BCE")
        era_ad = pynini.union("jaa.", "jaa", "j.a.a.", "jKr.", "j.Kr.", "AD", "A.D.", "CE")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        era_graph = (
            cardinal_nums
            + opt_sp
            + (
                pynutil.delete(era_bc) + pynutil.insert(" ennen ajanlaskun alkua")
                | pynutil.delete(era_ad) + pynutil.insert(" jälkeen ajanlaskun alun")
            )
        )

        all_dates = (
            written_date_full
            | numeric_dot_full
            | numeric_slash_full
            | written_date_short
            | numeric_dot_short
            | year_range
            | decades
            | era_graph
            | year_dot
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_dates).optimize()
            + pynutil.insert('"')
        ) | iso_date
        self.fst = self.fst.optimize()
