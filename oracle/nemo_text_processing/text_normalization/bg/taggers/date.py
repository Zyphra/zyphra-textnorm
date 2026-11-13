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

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.bg.taggers.ordinal import _build_ordinal_graph


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian dates.
    e.g. 07.03.2026 -> tokens { name: "седми март две хиляди двадесет и шеста година" }
         2026-03-07 -> tokens { name: "седми март две хиляди двадесет и шеста година" }
         24 май -> tokens { name: "двадесет и четвърти май" }
         2026 г. -> tokens { name: "две хиляди двадесет и шеста година" }
         1990–1995 -> tokens { name: "хиляда деветстотин и деветдесета до хиляда деветстотин деветдесет и пета" }
         500 пр.н.е. -> tokens { name: "петстотин преди новата ера" }
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        card_m = cardinal.cardinal_m

        # Days of the month (1-31) in masculine ordinal
        day_ord = pynini.string_map([
            ("01", "първи"), ("1", "първи"),
            ("02", "втори"), ("2", "втори"),
            ("03", "трети"), ("3", "трети"),
            ("04", "четвърти"), ("4", "четвърти"),
            ("05", "пети"), ("5", "пети"),
            ("06", "шести"), ("6", "шести"),
            ("07", "седми"), ("7", "седми"),
            ("08", "осми"), ("8", "осми"),
            ("09", "девети"), ("9", "девети"),
            ("10", "десети"),
            ("11", "единадесети"),
            ("12", "дванадесети"),
            ("13", "тринадесети"),
            ("14", "четиринадесети"),
            ("15", "петнадесети"),
            ("16", "шестнадесети"),
            ("17", "седемнадесети"),
            ("18", "осемнадесети"),
            ("19", "деветнадесети"),
            ("20", "двадесети"),
            ("21", "двадесет и първи"),
            ("22", "двадесет и втори"),
            ("23", "двадесет и трети"),
            ("24", "двадесет и четвърти"),
            ("25", "двадесет и пети"),
            ("26", "двадесет и шести"),
            ("27", "двадесет и седми"),
            ("28", "двадесет и осми"),
            ("29", "двадесет и девети"),
            ("30", "тридесети"),
            ("31", "тридесет и първи")
        ])

        # Month names: numbers and written Bulgarian Cyrillic
        month_num = pynini.string_map([
            ("01", "януари"), ("1", "януари"),
            ("02", "февруари"), ("2", "февруари"),
            ("03", "март"), ("3", "март"),
            ("04", "април"), ("4", "април"),
            ("05", "май"), ("5", "май"),
            ("06", "юни"), ("6", "юни"),
            ("07", "юли"), ("7", "юли"),
            ("08", "август"), ("8", "август"),
            ("09", "септември"), ("9", "септември"),
            ("10", "октомври"),
            ("11", "ноември"),
            ("12", "декември")
        ])

        month_written = pynini.union(
            "януари", "февруари", "март", "април", "май", "юни",
            "юли", "август", "септември", "октомври", "ноември", "декември"
        )

        month_any = month_num | month_written

        # Year in Bulgarian (feminine ordinal before "година" / "г.")
        year_ord_f = _build_ordinal_graph("f", cardinal_fst=cardinal)

        # Full numeric dates:
        # DD.MM.YYYY or DD/MM/YYYY
        digits = pynini.union(*"0123456789")
        year_dmy = ((digits ** 4) @ year_ord_f) | ((digits ** 2) @ year_ord_f)
        sep = pynutil.delete(pynini.union(".", "/"))
        opt_year_label = pynini.closure(
            pynini.closure(pynutil.delete(" "), 0, 1) + pynutil.delete(pynini.union("г.", "г", "година")),
            0, 1
        )

        date_dmy = (
            day_ord
            + sep
            + pynutil.insert(" ")
            + month_num
            + sep
            + pynutil.insert(" ")
            + year_dmy
            + opt_year_label
            + pynutil.insert(" година")
        )

        # The parser reorders localized ISO fields; no complete dates are hard-coded.
        digits = pynini.union(*"0123456789")
        date_iso = (
            pynutil.insert('date { year: "')
            + (digits ** 4 @ year_ord_f)
            + pynutil.insert(' година" month: "')
            + pynutil.delete("-")
            + (digits ** 2 @ month_num)
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + (digits ** 2 @ day_ord)
            + pynutil.insert('" }')
        )

        # Day + written month: "24 май", "1 януари"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        day_written_month = (
            day_ord + pynutil.delete(" ") + pynutil.insert(" ") + month_written
        )
        # Day + written month + year: "24 май 2024 г."
        day_written_month_year = (
            day_ord
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + month_written
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + year_ord_f
            + opt_year_label
            + pynutil.insert(" година")
        )

        # Year alone with "г." or "година": "2026 г.", "1990 г."
        year_alone = (
            year_ord_f
            + opt_sp
            + pynutil.delete(pynini.union("г.", "г", "година"))
            + pynutil.insert(" година")
        )

        # Year range: "1990–1995", "1990-1995"
        range_dash = pynini.cross(pynini.union("-", "–", "—"), " до ")
        year_range = (
            year_ord_f + opt_sp + range_dash + opt_sp + year_ord_f
        )

        # Historical eras: "500 пр.н.е.", "500 пр. Хр.", "500 BC", "500 след н.е.", "AD 500"
        era_bc = pynini.cross(
            pynini.union("пр.н.е.", "пр. н. е.", "пр.н.е", "пр. Хр.", "пр.Хр.", "BC", "B.C."),
            "преди новата ера"
        )
        era_ad = pynini.cross(
            pynini.union("след н.е.", "след н. е.", "от н.е.", "AD", "A.D."),
            "след новата ера"
        )
        year_num_card = card_m

        era_trailing = year_num_card + opt_sp + pynutil.insert(" ") + (era_bc | era_ad)
        era_leading_ad = pynutil.delete(pynini.union("AD", "A.D.")) + opt_sp + year_num_card + pynutil.insert(" след новата ера")

        all_dates = (
            pynutil.add_weight(date_dmy, 0.95)
            | pynutil.add_weight(day_written_month_year, 0.96)
            | pynutil.add_weight(day_written_month, 0.97)
            | pynutil.add_weight(year_alone, 0.98)
            | pynutil.add_weight(year_range, 0.99)
            | pynutil.add_weight(era_trailing, 1.0)
            | pynutil.add_weight(era_leading_ad, 1.0)
        ).optimize()

        self.all_dates = all_dates

        graph = pynutil.insert('name: "') + convert_space(all_dates) + pynutil.insert('"')
        self.fst = (date_iso | graph).optimize()
