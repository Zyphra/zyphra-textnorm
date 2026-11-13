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
from nemo_text_processing.text_normalization.tr.taggers.cardinal import CardinalFst


class DateFst(GraphFst):
    """
    Finite state transducer for dates in Turkish:
    - Numeric dates: 11.05.2024 -> on bir mayıs iki bin yirmi dört
    - Written month dates: 11 Mayıs 2024 -> on bir mayıs iki bin yirmi dört
    - ISO dates: 2024-05-11 -> on bir mayıs iki bin yirmi dört
    - Eras: MÖ 500 / 500 BC -> milattan önce beş yüz, MS 200 -> milattan sonra iki yüz
    - Decades: 1990'lar / 1990s -> bin dokuz yüz doksanlar, 80'ler -> seksenler
    - Year ranges: 1990–1995 -> bin dokuz yüz doksan ila bin dokuz yüz doksan beş
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        d1_to_9 = pynini.string_map([
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        tens_map = pynini.string_map([
            ("1", "on"),
            ("2", "yirmi"),
            ("3", "otuz"),
        ])
        days_1_31 = (
            (pynini.closure(pynutil.delete("0"), 0, 1) + d1_to_9)
            | (tens_map + pynutil.delete("0"))
            | (tens_map + pynutil.insert(" ") + d1_to_9)
            | pynini.cross("31", "otuz bir")
        ).optimize()

        num_to_month = pynini.string_map([
            ("01", "ocak"),
            ("1", "ocak"),
            ("02", "şubat"),
            ("2", "şubat"),
            ("03", "mart"),
            ("3", "mart"),
            ("04", "nisan"),
            ("4", "nisan"),
            ("05", "mayıs"),
            ("5", "mayıs"),
            ("06", "haziran"),
            ("6", "haziran"),
            ("07", "temmuz"),
            ("7", "temmuz"),
            ("08", "ağustos"),
            ("8", "ağustos"),
            ("09", "eylül"),
            ("9", "eylül"),
            ("10", "ekim"),
            ("11", "kasım"),
            ("12", "aralık"),
        ])

        name_to_month = pynini.string_map([
            ("Ocak", "ocak"),
            ("ocak", "ocak"),
            ("Oca.", "ocak"),
            ("Oca", "ocak"),
            ("Şubat", "şubat"),
            ("şubat", "şubat"),
            ("Şub.", "şubat"),
            ("Şub", "şubat"),
            ("Mart", "mart"),
            ("mart", "mart"),
            ("Mar.", "mart"),
            ("Mar", "mart"),
            ("Nisan", "nisan"),
            ("nisan", "nisan"),
            ("Nis.", "nisan"),
            ("Nis", "nisan"),
            ("Mayıs", "mayıs"),
            ("mayıs", "mayıs"),
            ("May.", "mayıs"),
            ("May", "mayıs"),
            ("Haziran", "haziran"),
            ("haziran", "haziran"),
            ("Haz.", "haziran"),
            ("Haz", "haziran"),
            ("Temmuz", "temmuz"),
            ("temmuz", "temmuz"),
            ("Tem.", "temmuz"),
            ("Tem", "temmuz"),
            ("Ağustos", "ağustos"),
            ("ağustos", "ağustos"),
            ("Ağu.", "ağustos"),
            ("Ağu", "ağustos"),
            ("Eylül", "eylül"),
            ("eylül", "eylül"),
            ("Eyl.", "eylül"),
            ("Eyl", "eylül"),
            ("Ekim", "ekim"),
            ("ekim", "ekim"),
            ("Eki.", "ekim"),
            ("Eki", "ekim"),
            ("Kasım", "kasım"),
            ("kasım", "kasım"),
            ("Kas.", "kasım"),
            ("Kas", "kasım"),
            ("Aralık", "aralık"),
            ("aralık", "aralık"),
            ("Ara.", "aralık"),
            ("Ara", "aralık"),
        ])

        year_num = (pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal.positive_cardinals).optimize()

        # 1. Numeric dates: DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY
        date_sep = pynini.union(".", "/", "-")
        numeric_date_full = (
            days_1_31
            + pynutil.delete(date_sep)
            + pynutil.insert(" ")
            + num_to_month
            + pynutil.delete(date_sep)
            + pynutil.insert(" ")
            + year_num
        )

        # 2. Numeric date day + month only: 11.05. or 11.05 (dot only; '-' is range, '/' is fraction)
        numeric_date_dm = (
            days_1_31
            + pynutil.delete(".")
            + pynutil.insert(" ")
            + num_to_month
            + pynini.closure(pynini.closure(pynutil.delete(" "), 0, 1) + pynutil.delete("."), 0, 1)
        )

        iso_date = (
            pynutil.insert('date { year: "')
            + (NEMO_DIGIT ** 4 @ cardinal.positive_cardinals)
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + num_to_month
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + days_1_31
            + pynutil.insert('" }')
        )

        # 4. Written month dates: "11 Mayıs 2024", "29 Ekim 1923", "1 Ocak 2000", "15 Temmuz"
        written_date_full = (
            days_1_31
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + name_to_month
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + year_num
        )
        written_date_dm = (
            days_1_31
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + name_to_month
        )

        # 5. Eras: MÖ 500, 500 MÖ, 500 BC, 500 BCE, MS 200, 200 AD
        era_bc_words = pynini.union("MÖ", "M.Ö.", "BC", "B.C.", "BCE", "B.C.E.")
        era_ad_words = pynini.union("MS", "M.S.", "AD", "A.D.", "CE", "C.E.")

        era_lead_bc = pynutil.delete(era_bc_words) + pynutil.delete(" ") + pynutil.insert("milattan önce ") + year_num
        era_trail_bc = pynutil.insert("milattan önce ") + year_num + pynutil.delete(" ") + pynutil.delete(era_bc_words)
        era_lead_ad = pynutil.delete(era_ad_words) + pynutil.delete(" ") + pynutil.insert("milattan sonra ") + year_num
        era_trail_ad = pynutil.insert("milattan sonra ") + year_num + pynutil.delete(" ") + pynutil.delete(era_ad_words)
        era_graph = era_lead_bc | era_trail_bc | era_lead_ad | era_trail_ad

        # 6. Decades: 1990'lar, 80'ler, 2020'ler, 1990s, 2020s (NEVER 2020 seconds!)
        decade_s = (
            pynini.union(
                pynini.cross("1980s", "bin dokuz yüz seksenler"),
                pynini.cross("1990s", "bin dokuz yüz doksanlar"),
                pynini.cross("2000s", "iki binler"),
                pynini.cross("2010s", "iki bin onlar"),
                pynini.cross("2020s", "iki bin yirmiler"),
                pynini.cross("80s", "seksenler"),
                pynini.cross("90s", "doksanlar"),
            )
        )

        # 7. Year ranges: 1990-1995, 1990–1995
        dash = pynini.union("-", "–", "—")
        year_4d = pynini.closure(NEMO_DIGIT, 4, 4) @ cardinal.positive_cardinals
        year_range = (
            year_4d
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynini.cross(dash, " ila ")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + year_4d
        )

        all_dates = (
            written_date_full
            | written_date_dm
            | numeric_date_full
            | numeric_date_dm
            | era_graph
            | decade_s
            | year_range
        ).optimize()
        self.all_dates = all_dates

        self.fst = (pynutil.insert('name: "') + convert_space(all_dates) + pynutil.insert('"') | pynutil.add_weight(iso_date, -0.1)).optimize()
