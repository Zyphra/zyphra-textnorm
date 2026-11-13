# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Dutch dates.
    Handles:
    - Day-month dates: 25/12/2024, 07.03.2026, 25-12-2024 -> vijfentwintig december tweeduizend vierentwintig
    - ISO dates: 2024-12-25, 2026-03-07 -> vijfentwintig december tweeduizend vierentwintig
    - Written month dates: 7 maart 2026, 25 december
    - Decades: 2020s, 1990s, jaren 90, jaren 80 -> jaren twintig, jaren negentig
    - Years and year ranges: 1990., 1990–1995, 2020-2024
    - Eras: 500 v.Chr., 500 n.Chr., 500 BC, 500 AD
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        dash = pynini.union("-", "–", "—")

        # Month names: 1 to 12
        months_num = [
            ("01", "januari"),
            ("1", "januari"),
            ("02", "februari"),
            ("2", "februari"),
            ("03", "maart"),
            ("3", "maart"),
            ("04", "april"),
            ("4", "april"),
            ("05", "mei"),
            ("5", "mei"),
            ("06", "juni"),
            ("6", "juni"),
            ("07", "juli"),
            ("7", "juli"),
            ("08", "augustus"),
            ("8", "augustus"),
            ("09", "september"),
            ("9", "september"),
            ("10", "oktober"),
            ("11", "november"),
            ("12", "december"),
        ]
        month_num_map = pynini.string_map(months_num).optimize()

        months_name = [
            ("januari", "januari"),
            ("februari", "februari"),
            ("maart", "maart"),
            ("april", "april"),
            ("mei", "mei"),
            ("juni", "juni"),
            ("juli", "juli"),
            ("augustus", "augustus"),
            ("september", "september"),
            ("oktober", "oktober"),
            ("november", "november"),
            ("december", "december"),
            ("jan.", "januari"),
            ("feb.", "februari"),
            ("mrt.", "maart"),
            ("apr.", "april"),
            ("jun.", "juni"),
            ("jul.", "juli"),
            ("aug.", "augustus"),
            ("sep.", "september"),
            ("sept.", "september"),
            ("okt.", "oktober"),
            ("nov.", "november"),
            ("dec.", "december"),
            ("jan", "januari"),
            ("feb", "februari"),
            ("mrt", "maart"),
            ("apr", "april"),
            ("jun", "juni"),
            ("jul", "juli"),
            ("aug", "augustus"),
            ("sep", "september"),
            ("sept", "september"),
            ("okt", "oktober"),
            ("nov", "november"),
            ("dec", "december"),
        ]
        month_name_map = pynini.string_map(months_name).optimize()

        # Day (1 to 31)
        day_graph = (
            pynini.closure(pynutil.delete("0"), 0, 1)
            + cardinal.nums_1_to_99
        )

        # Year graph: 4 digits (e.g. 2024 -> tweeduizend vierentwintig, 1995 -> negentienhonderdvijfennegentig)
        year_graph = cardinal.nums_1000_to_999999

        date_sep = pynini.union("/", ".", "-")

        # 1. Day-Month-Year: "25/12/2024", "07.03.2026", "25-12-2024"
        dmy = (
            day_graph
            + pynutil.delete(date_sep)
            + pynutil.insert(" ")
            + month_num_map
            + pynutil.delete(date_sep)
            + pynutil.insert(" ")
            + year_graph
        )

        # 2. Day + written month + optional year: "7 maart 2026", "25 december"
        written_date = (
            day_graph
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + month_name_map
            + pynini.closure(
                pynutil.delete(" ") + pynutil.insert(" ") + year_graph,
                0,
                1,
            )
        )

        # 3. Decades:
        # "jaren 90", "jaren '90" -> "jaren negentig"
        # "2020s" -> "jaren twintig"
        # "1990s" -> "jaren negentig"
        # "1980s" -> "jaren tachtig"
        decades_map = [
            ("2020s", "jaren twintig"),
            ("2010s", "jaren tien"),
            ("2000s", "jaren nul"),
            ("1990s", "jaren negentig"),
            ("1980s", "jaren tachtig"),
            ("1970s", "jaren zeventig"),
            ("1960s", "jaren zestig"),
            ("1950s", "jaren vijftig"),
            ("1940s", "jaren veertig"),
            ("1930s", "jaren dertig"),
            ("1920s", "jaren twintig"),
            ("90s", "jaren negentig"),
            ("80s", "jaren tachtig"),
            ("70s", "jaren zeventig"),
            ("60s", "jaren zestig"),
            ("50s", "jaren vijftig"),
        ]
        decades_intl = pynini.string_map(decades_map)

        decades_native = (
            pynini.cross("jaren ", "jaren ")
            + pynini.closure(pynutil.delete("'"), 0, 1)
            + pynini.string_map(
                [
                    ("20", "twintig"),
                    ("30", "dertig"),
                    ("40", "veertig"),
                    ("50", "vijftig"),
                    ("60", "zestig"),
                    ("70", "zeventig"),
                    ("80", "tachtig"),
                    ("90", "negentig"),
                    ("2020", "twintig"),
                    ("1990", "negentig"),
                    ("1980", "tachtig"),
                ]
            )
        )

        # 4. Year ranges: "1990–1995", "1990-1995", "2020-2024"
        year_range = (
            year_graph
            + delete_space
            + pynini.cross(dash, " tot ")
            + delete_space
            + year_graph
        )

        # 5. Eras: "500 v.Chr.", "500 v.C.", "500 BC", "500 n.Chr.", "500 AD"
        era_bc = pynini.union("v.Chr.", "v. Chr.", "v.C.", "v. C.", "BC", "B.C.")
        era_ad = pynini.union("n.Chr.", "n. Chr.", "n.C.", "n. C.", "AD", "A.D.")

        era_fst = (
            cardinal.cardinal_numbers
            + opt_space
            + (
                pynini.cross(era_bc, " voor Christus")
                | pynini.cross(era_ad, " na Christus")
            )
        )

        # 6. ISO direct date: YYYY-MM-DD
        iso_y = NEMO_DIGIT**4
        iso_m = pynini.union("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
        iso_d_digits = pynini.union(
            *[f"{i:02d}" for i in range(1, 32)]
        )
        iso_direct = (
            pynutil.insert('date { year: "')
            + (iso_y @ year_graph)
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + (iso_m @ month_num_map)
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + (iso_d_digits @ day_graph)
            + pynutil.insert('" }')
        )

        self.spoken_date = (
            pynutil.add_weight(dmy, 0.95)
            | pynutil.add_weight(written_date, 0.96)
            | pynutil.add_weight(decades_intl, 0.97)
            | pynutil.add_weight(decades_native, 0.97)
            | pynutil.add_weight(era_fst, 0.98)
            | pynutil.add_weight(year_range, 0.98)
        ).optimize()

        self.fst = (wrap_name(self.spoken_date) | iso_direct).optimize()
