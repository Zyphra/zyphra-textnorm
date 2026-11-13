# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.uk.taggers.ordinal import OrdinalFst


MONTHS_GENITIVE = [
    ("1", "січня"), ("01", "січня"),
    ("2", "лютого"), ("02", "лютого"),
    ("3", "березня"), ("03", "березня"),
    ("4", "квітня"), ("04", "квітня"),
    ("5", "травня"), ("05", "травня"),
    ("6", "червня"), ("06", "червня"),
    ("7", "липня"), ("07", "липня"),
    ("8", "серпня"), ("08", "серпня"),
    ("9", "вересня"), ("09", "вересня"),
    ("10", "жовтня"),
    ("11", "листопада"),
    ("12", "грудня"),
]

DAYS_NEUTER = [
    ("1", "перше"), ("01", "перше"),
    ("2", "друге"), ("02", "друге"),
    ("3", "третє"), ("03", "третє"),
    ("4", "четверте"), ("04", "четверте"),
    ("5", "п'яте"), ("05", "п'яте"),
    ("6", "шосте"), ("06", "шосте"),
    ("7", "сьоме"), ("07", "сьоме"),
    ("8", "восьме"), ("08", "восьме"),
    ("9", "дев'яте"), ("09", "дев'яте"),
    ("10", "десяте"),
    ("11", "одинадцяте"),
    ("12", "дванадцяте"),
    ("13", "тринадцяте"),
    ("14", "чотирнадцяте"),
    ("15", "п'ятнадцяте"),
    ("16", "шістнадцяте"),
    ("17", "сімнадцяте"),
    ("18", "вісімнадцяте"),
    ("19", "дев'ятнадцяте"),
    ("20", "двадцяте"),
    ("21", "двадцять перше"),
    ("22", "двадцять друге"),
    ("23", "двадцять третє"),
    ("24", "двадцять четверте"),
    ("25", "двадцять п'яте"),
    ("26", "двадцять шосте"),
    ("27", "двадцять сьоме"),
    ("28", "двадцять восьме"),
    ("29", "двадцять дев'яте"),
    ("30", "тридцяте"),
    ("31", "тридцять перше"),
]


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian dates:
        06.03.2006 -> шосте березня дві тисячі шостого
        6/3/1006г. -> шосте березня тисяча шостого року
        2024-12-25 -> двадцять п'яте грудня дві тисячі двадцять четвертого
        в 1999 році -> в тисяча дев'ятсот дев'яносто дев'ятому році
        1990–1995 -> від тисяча дев'ятсот дев'яностого до тисяча дев'ятсот дев'яносто п'ятого
        500 до н. е. -> п'ятсот до нашої ери
        500 BC -> п'ятсот до нашої ери
    """

    def __init__(self, cardinal: CardinalFst = None, ordinal: OrdinalFst = None):
        super().__init__(name="date", kind="classify")
        cardinal = cardinal or CardinalFst()
        ordinal = ordinal or OrdinalFst(cardinal=cardinal)

        day = pynini.string_map(DAYS_NEUTER)
        month = pynini.string_map(MONTHS_GENITIVE)
        year_gen = ordinal.ord_gen
        year_loc = ordinal.ord_loc

        # Suffix year words
        year_word_gen = pynutil.delete(pynini.union("р.", "р", "року", "г.", "г", "года")) + pynutil.insert(" року")
        opt_year_word_gen = pynini.closure(pynutil.insert(" ") + year_word_gen, 0, 1)

        # 1. Day.Month.Year: "06.03.2006" -> "шосте березня дві тисячі шостого"
        dot = pynutil.delete(".")
        slash = pynutil.delete("/")
        dash = pynutil.delete("-")

        # Year in numeric dates: restrict to 2 or 4 digits
        year_in_date = pynini.cross("2000", "дві тисячі") | year_gen
        year_numeric = ((NEMO_DIGIT ** 4) | (NEMO_DIGIT ** 2)) @ year_in_date

        date_dmy_dot = (
            day
            + dot
            + pynutil.insert(" ")
            + month
            + dot
            + pynutil.insert(" ")
            + year_numeric
            + opt_year_word_gen
        )

        date_dmy_slash = (
            day
            + slash
            + pynutil.insert(" ")
            + month
            + slash
            + pynutil.insert(" ")
            + year_numeric
            + opt_year_word_gen
        )

        # 2. ISO dates (YYYY-MM-DD): "2024-12-25" -> "двадцять п'яте грудня дві тисячі двадцять четвертого"
        iso_dates = []
        for m_num, m_spoken in MONTHS_GENITIVE:
            if len(m_num) == 2:
                for d_str, d_spoken in DAYS_NEUTER:
                    if len(d_str) == 2:
                        iso_dates.append((m_num, d_str, f"{d_spoken} {m_spoken}"))
        sep_num = pynini.union("-", "/")
        iso_date_graph = pynini.union(
            *[
                pynutil.insert(dm_spoken + " ")
                + year_gen
                + pynutil.delete(sep_num)
                + pynutil.delete(m_str)
                + pynutil.delete(sep_num)
                + pynutil.delete(d_str)
                for m_str, d_str, dm_spoken in iso_dates
            ]
        )

        # 3. Written dates: "1 січня" -> "перше січня", "9 травня", "24 серпня"
        MONTHS_WRITTEN = [
            "січня", "лютого", "березня", "квітня", "травня", "червня",
            "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"
        ]
        month_written = pynini.union(*MONTHS_WRITTEN)
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        written_date_dm = day + opt_sp + pynutil.insert(" ") + month_written
        written_date_dmy = (
            day
            + opt_sp
            + pynutil.insert(" ")
            + month_written
            + opt_sp
            + pynutil.insert(" ")
            + year_numeric
            + opt_year_word_gen
        )

        # 4. Year in context: "в 1999 році" -> "в тисяча дев'ятсот дев'яносто дев'ятому році"
        prep = pynini.union("в ", "у ", "В ", "У ")
        suff_year_loc = (
            pynini.cross("році", "році")
            | pynini.cross("году", "році")
            | pynini.cross("р.", "році")
            | pynini.cross("р", "році")
        )
        year_in_context = (
            prep
            + ((NEMO_DIGIT ** 4) @ year_loc)
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + suff_year_loc
        )

        # 5. Year ranges: "1995–2005" -> "від однієї тисячі дев'ятисот дев'яноста п'яти до двох тисяч п'яти"
        range_dash = pynini.union("-", "–", "—")
        range_year_general = (
            pynutil.insert("від ")
            + ((NEMO_DIGIT ** 4) @ cardinal.graph_genitive)
            + pynini.cross(range_dash, " до ")
            + ((NEMO_DIGIT ** 4) @ cardinal.graph_genitive)
        )

        # 6. Eras: "500 до н. е.", "500 BC"
        era_bc = (
            pynini.cross("до н. е.", "до нашої ери")
            | pynini.cross("до н.е.", "до нашої ери")
            | pynini.cross("до н.е", "до нашої ери")
            | pynini.cross("BC", "до нашої ери")
            | pynini.cross("B.C.", "до нашої ери")
        )
        era_ad = (
            pynini.cross("н. е.", "нашої ери")
            | pynini.cross("н.е.", "нашої ери")
            | pynini.cross("AD", "нашої ери")
            | pynini.cross("A.D.", "нашої ери")
        )
        era_graph = (
            cardinal.graph
            + opt_sp
            + pynutil.insert(" ")
            + (era_bc | era_ad)
        )

        all_dates = (
            pynutil.add_weight(iso_date_graph, -0.1)
            | pynutil.add_weight(written_date_dmy, 0.05)
            | pynutil.add_weight(written_date_dm, 0.05)
            | pynutil.add_weight(date_dmy_dot, 0.06)
            | pynutil.add_weight(date_dmy_slash, 0.06)
            | pynutil.add_weight(year_in_context, 0.07)
            | pynutil.add_weight(era_graph, 0.08)
            | pynutil.add_weight(range_year_general, 0.1)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_dates)
            + pynutil.insert('"')
        ).optimize()
