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
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.pl.utils import get_abs_path


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Polish dates, decades, and eras, e.g.
        "2026-03-07" -> "siódmego marca dwa tysiące dwudziestego szóstego roku"
        "2024-12-25" -> "dwudziestego piątego grudnia dwa tysiące dwudziestego czwartego roku"
        "15.05.2024" -> "piętnastego maja dwa tysiące dwudziestego czwartego roku"
        "25/12/2024" -> "dwudziestego piątego grudnia dwa tysiące dwudziestego czwartego roku"
        "3 maja 1995" -> "trzeciego maja tysiąc dziewięćset dziewięćdziesiątego piątego roku"
        "1995 r." -> "tysiąc dziewięćset dziewięćdziesiątego piątego roku"
        "1990–1995" -> "tysiąc dziewięćset dziewięćdziesiąt do tysiąc dziewięćset dziewięćdziesiąt pięć"
        "lata 90." -> "lata dziewięćdziesiąte"
        "2020s" -> "lata dwudzieste"
        "500 p.n.e." -> "pięćset przed naszą erą"
        "500 n.e." -> "pięćset naszej ery"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        pn = cardinal.pn
        card_m = cardinal.graph_with_sep
        ord_gen = pn.ordinal_fst(gender="masc", case="gen")

        months_gen = pynini.string_file(get_abs_path("data/date/months_gen.tsv"))

        # Days: 1-31 in genitive ordinal (1 -> pierwszego, 31 -> trzydziestego pierwszego)
        day_raw = pynutil.delete("0") + (NEMO_DIGIT - "0") | pynini.union("1", "2") + NEMO_DIGIT | "30" | "31" | (NEMO_DIGIT - "0")
        day_spoken = day_raw @ ord_gen

        # Numeric month (1-12) to genitive month name
        month_num = pynutil.delete("0") + (NEMO_DIGIT - "0") | "10" | "11" | "12" | (NEMO_DIGIT - "0")
        month_spoken = month_num @ months_gen

        # Year spoken (genitive ordinal + " roku", e.g. 2024 -> "dwa tysiące dwudziestego czwartego roku")
        year_4 = (pynini.closure(NEMO_DIGIT, 4)) @ ord_gen
        year_spoken = year_4 + pynutil.insert(" roku")

        # Separators
        sep_dot = pynutil.delete(".")
        sep_slash = pynutil.delete("/")

        # Standard European order: DD.MM.YYYY and DD/MM/YYYY
        date_dot_full = day_spoken + sep_dot + pynutil.insert(" ") + month_spoken + sep_dot + pynutil.insert(" ") + year_spoken
        date_slash_full = day_spoken + sep_slash + pynutil.insert(" ") + month_spoken + sep_slash + pynutil.insert(" ") + year_spoken

        iso_date = (
            pynutil.insert('date { year: "')
            + year_spoken
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + month_spoken
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + day_spoken
            + pynutil.insert('" }')
        )

        # Written month names in dates: "15 maja 2024", "3 maja 1995 r.", "3 maja"
        written_months_list = [
            "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
            "lipca", "sierpnia", "września", "października", "listopada", "grudnia"
        ]
        month_word = pynini.union(*written_months_list)
        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)

        date_written_full = (
            day_spoken
            + opt_dot
            + pynini.accep(" ")
            + month_word
            + pynini.accep(" ")
            + year_spoken
            + pynini.closure(pynutil.delete(pynini.union(" r.", " r", " roku")), 0, 1)
        )
        date_written_short = (
            day_spoken
            + opt_dot
            + pynini.accep(" ")
            + month_word
        )

        # Standalone year with "r." or "roku": "1995 r.", "1995 roku"
        year_with_r = (
            year_4
            + pynini.cross(pynini.union(" r.", " r", " roku"), " roku")
        )

        # Year ranges: 1990–1995, 1995-2005
        dash = pynini.union("-", "–", "—")
        range_to = pynini.cross(dash, " do ")
        year_range = (
            (pynini.closure(NEMO_DIGIT, 4) @ card_m)
            + range_to
            + (pynini.closure(NEMO_DIGIT, 4) @ card_m)
        )

        # Decades: "lata 90.", "lata 1990.", "2020s" (NEVER read as seconds!)
        decade_90 = pynini.cross(pynini.union("lata 90.", "lata 90-te", "lata 90"), "lata dziewięćdziesiąte")
        decade_1990 = pynini.cross(pynini.union("lata 1990.", "lata 1990-te", "lata 1990"), "lata tysiąc dziewięćset dziewięćdziesiąte")
        decade_2020s = pynini.cross("2020s", "lata dwudzieste")
        decade_1990s = pynini.cross("1990s", "lata dziewięćdziesiąte")
        decade_1980s = pynini.cross("1980s", "lata osiemdziesiąte")
        decade_2010s = pynini.cross("2010s", "lata dwutysięczne dziesiąte")
        decades = decade_90 | decade_1990 | decade_2020s | decade_1990s | decade_1980s | decade_2010s

        # Eras: "500 p.n.e.", "500 n.e.", "500 BC", "500 AD"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        era_bc = pynini.cross(pynini.union("p.n.e.", "p.n.e", "BC", "BCE", "B.C.", "B.C.E."), "przed naszą erą")
        era_ad = pynini.cross(pynini.union("n.e.", "n.e", "AD", "CE", "A.D.", "C.E."), "naszej ery")
        eras = (
            card_m + opt_sp + pynutil.insert(" ") + (era_bc | era_ad)
        )

        self.graph = (
            date_dot_full
            | date_slash_full
            | date_written_full
            | date_written_short
            | year_with_r
            | year_range
            | decades
            | eras
        ).optimize()

        self.fst = (pynutil.insert('name: "') + convert_space(self.graph) + pynutil.insert('"') | iso_date).optimize()
