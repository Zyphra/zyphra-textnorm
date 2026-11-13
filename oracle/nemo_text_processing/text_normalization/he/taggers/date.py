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
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew dates, years, decades, and eras.
    e.g. 25/12/2024 -> עשרים וחמישה בדצמבר אלפיים עשרים וארבע
         2024-12-25 -> עשרים וחמישה בדצמבר אלפיים עשרים וארבע
         15.05.2024 -> חמישה עשר במאי אלפיים עשרים וארבע
         15 במאי 2024 -> חמישה עשר במאי אלפיים עשרים וארבע
         1 בינואר -> אחד בינואר
         1990 -> אלף תשע מאות ותשעים
         1990–1995 -> אלף תשע מאות ותשעים עד אלף תשע מאות תשעים וחמש
         שנות ה-90 -> שנות התשעים
         2020s -> שנות האלפיים עשרים
         500 לפנה״ס -> חמש מאות לפני הספירה
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        req_space = pynutil.delete(pynini.closure(" ", 1)) + pynutil.insert(" ")
        # ----------------- Month Mappings -----------------
        # Numeric month (1-12 or 01-12) to Hebrew month with prefix ב-
        num_to_month_b = pynini.string_map([
            ("01", "בינואר"),
            ("1", "בינואר"),
            ("02", "בפברואר"),
            ("2", "בפברואר"),
            ("03", "במרץ"),
            ("3", "במרץ"),
            ("04", "באפריל"),
            ("4", "באפריל"),
            ("05", "במאי"),
            ("5", "במאי"),
            ("06", "ביוני"),
            ("6", "ביוני"),
            ("07", "ביולי"),
            ("7", "ביולי"),
            ("08", "באוגוסט"),
            ("8", "באוגוסט"),
            ("09", "בספטמבר"),
            ("9", "בספטמבר"),
            ("10", "באוקטובר"),
            ("11", "בנובמבר"),
            ("12", "בדצמבר"),
        ])

        # Hebrew month written names with or without ב-
        hebrew_month_b = pynini.string_map([
            ("בינואר", "בינואר"),
            ("ינואר", "בינואר"),
            ("בפברואר", "בפברואר"),
            ("פברואר", "בפברואר"),
            ("במרץ", "במרץ"),
            ("מרץ", "במרץ"),
            ("באפריל", "באפריל"),
            ("אפריל", "באפריל"),
            ("במאי", "במאי"),
            ("מאי", "במאי"),
            ("ביוני", "ביוני"),
            ("יוני", "ביוני"),
            ("ביולי", "ביולי"),
            ("יולי", "ביולי"),
            ("באוגוסט", "באוגוסט"),
            ("אוגוסט", "באוגוסט"),
            ("בספטמבר", "בספטמבר"),
            ("ספטמבר", "בספטמבר"),
            ("באוקטובר", "באוקטובר"),
            ("אוקטובר", "באוקטובר"),
            ("בנובמבר", "בנובמבר"),
            ("נובמבר", "בנובמבר"),
            ("בדצמבר", "בדצמבר"),
            ("דצמבר", "בדצמבר"),
        ])

        # English month names in written dates
        english_month_b = pynini.string_map([
            ("January", "בינואר"),
            ("Jan", "בינואר"),
            ("February", "בפברואר"),
            ("Feb", "בפברואר"),
            ("March", "במרץ"),
            ("Mar", "במרץ"),
            ("April", "באפריל"),
            ("Apr", "באפריל"),
            ("May", "במאי"),
            ("June", "ביוני"),
            ("Jun", "ביוני"),
            ("July", "ביולי"),
            ("Jul", "ביולי"),
            ("August", "באוגוסט"),
            ("Aug", "באוגוסט"),
            ("September", "בספטמבר"),
            ("Sep", "בספטמבר"),
            ("Sept", "בספטמבר"),
            ("October", "באוקטובר"),
            ("Oct", "באוקטובר"),
            ("November", "בנובמבר"),
            ("Nov", "בנובמבר"),
            ("December", "בדצמבר"),
            ("Dec", "בדצמבר"),
        ])

        all_month_names = hebrew_month_b | english_month_b

        # ----------------- Day of Month (Masculine) -----------------
        day_map = [
            ("01", "אחד"),
            ("1", "אחד"),
            ("02", "שני"),
            ("2", "שני"),
            ("03", "שלושה"),
            ("3", "שלושה"),
            ("04", "ארבעה"),
            ("4", "ארבעה"),
            ("05", "חמישה"),
            ("5", "חמישה"),
            ("06", "שישה"),
            ("6", "שישה"),
            ("07", "שבעה"),
            ("7", "שבעה"),
            ("08", "שמונה"),
            ("8", "שמונה"),
            ("09", "תשעה"),
            ("9", "תשעה"),
            ("10", "עשרה"),
            ("11", "אחד עשר"),
            ("12", "שנים עשר"),
            ("13", "שלושה עשר"),
            ("14", "ארבעה עשר"),
            ("15", "חמישה עשר"),
            ("16", "שישה עשר"),
            ("17", "שבעה עשר"),
            ("18", "שמונה עשר"),
            ("19", "תשעה עשר"),
            ("20", "עשרים"),
            ("21", "עשרים ואחד"),
            ("22", "עשרים ושניים"),
            ("23", "עשרים ושלושה"),
            ("24", "עשרים וארבעה"),
            ("25", "עשרים וחמישה"),
            ("26", "עשרים ושישה"),
            ("27", "עשרים ושבעה"),
            ("28", "עשרים ושמונה"),
            ("29", "עשרים ותשעה"),
            ("30", "שלושים"),
            ("31", "שלושים ואחד"),
        ]
        # Day 1 can also be ראשון
        day_fst_primary = pynini.string_map(day_map)
        day_1_alt = pynini.cross("1", "ראשון") | pynini.cross("01", "ראשון")
        day_fst = (day_fst_primary | pynutil.add_weight(day_1_alt, 0.05)).optimize()

        # ----------------- Year -----------------
        # 4-digit years 1000-2099
        year_fst = cardinal.base_num_f

        # ----------------- Written Month Dates -----------------
        # 15 במאי 2024 -> חמישה עשר במאי אלפיים עשרים וארבע
        written_date_with_year = (
            day_fst
            + req_space
            + all_month_names
            + req_space
            + year_fst
        )

        # 1 בינואר -> אחד בינואר
        written_date_no_year = (
            day_fst
            + req_space
            + all_month_names
        )

        # English order: May 15, 2024 -> חמישה עשר במאי אלפיים עשרים וארבע
        opt_comma = pynini.closure(pynutil.delete(","), 0, 1)
        written_date_eng_order = (
            english_month_b
            + req_space
            + day_fst
            + opt_comma
            + req_space
            + year_fst
        )

        written_dates = (
            pynutil.add_weight(written_date_with_year, 0.9)
            | pynutil.add_weight(written_date_eng_order, 0.92)
            | pynutil.add_weight(written_date_no_year, 0.95)
        ).optimize()

        # ----------------- Numeric Dates -----------------
        slash = pynutil.delete("/")
        dot = pynutil.delete(".")
        dash = pynutil.delete(pynini.union("-", "–", "—", "־"))

        # DD/MM/YYYY -> <day> <month> <year>
        numeric_slash_ymd = (
            day_fst
            + slash
            + pynutil.insert(" ")
            + num_to_month_b
            + slash
            + pynutil.insert(" ")
            + year_fst
        )

        # DD.MM.YYYY -> <day> <month> <year>
        numeric_dot_ymd = (
            day_fst
            + dot
            + pynutil.insert(" ")
            + num_to_month_b
            + dot
            + pynutil.insert(" ")
            + year_fst
        )

        year_4d = NEMO_DIGIT ** 4 @ year_fst
        iso_graph = (
            pynutil.insert('date { year: "')
            + year_4d
            + pynutil.insert('" month: "')
            + dash
            + (NEMO_DIGIT ** 2 @ num_to_month_b)
            + pynutil.insert('" day: "')
            + dash
            + (NEMO_DIGIT ** 2 @ day_fst)
            + pynutil.insert('" }')
        )

        # DD/MM (day and month only): 25/12 -> עשרים וחמישה בדצמבר
        # Numeric dates without year must not eat fractions (e.g. 1/2, 1/4, 3/4, 5/8, 7/12);
        # only unambiguous days (13-31) match without year. Full dates (with year) handle all days 1-31.
        day_unambiguous = pynini.string_map([
            (str(d), name) for d, name in day_map if int(d) >= 13
        ])
        numeric_dm_slash = day_unambiguous + slash + pynutil.insert(" ") + num_to_month_b

        numeric_dates = (
            pynutil.add_weight(numeric_dm_slash, -0.2)
            | pynutil.add_weight(numeric_slash_ymd, 0.9)
            | pynutil.add_weight(numeric_dot_ymd, 0.9)
        ).optimize()

        # ----------------- Year Ranges -----------------
        # 1990–1995 -> אלף תשע מאות ותשעים עד אלף תשע מאות תשעים וחמש
        range_dash = pynini.union("-", "–", "—", "־")
        year_range = (
            year_4d
            + pynini.cross(range_dash, " עד ")
            + year_4d
        ).optimize()

        # ----------------- Decades -----------------
        # שנות ה-90 -> שנות התשעים
        # שנות ה-1990 -> שנות התשעים
        # 2020s -> שנות האלפיים עשרים
        decade_map = [
            ("שנות ה-20", "שנות העשרים"),
            ("שנות ה-30", "שנות השלושים"),
            ("שנות ה-40", "שנות הארבעים"),
            ("שנות ה-50", "שנות החמישים"),
            ("שנות ה-60", "שנות השישים"),
            ("שנות ה-70", "שנות השבעים"),
            ("שנות ה-80", "שנות השמונים"),
            ("שנות ה-90", "שנות התשעים"),
            ("שנות ה-1920", "שנות העשרים"),
            ("שנות ה-1930", "שנות השלושים"),
            ("שנות ה-1940", "שנות הארבעים"),
            ("שנות ה-1950", "שנות החמישים"),
            ("שנות ה-1960", "שנות השישים"),
            ("שנות ה-1970", "שנות השבעים"),
            ("שנות ה-1980", "שנות השמונים"),
            ("שנות ה-1990", "שנות התשעים"),
            ("שנות ה-2000", "שנות האלפיים"),
            ("שנות ה-2010", "שנות האלפיים ועשר"),
            ("שנות ה-2020", "שנות האלפיים עשרים"),
            # International decades (MUST NOT be read as seconds!)
            ("1920s", "שנות העשרים"),
            ("1930s", "שנות השלושים"),
            ("1940s", "שנות הארבעים"),
            ("1950s", "שנות החמישים"),
            ("1960s", "שנות השישים"),
            ("1970s", "שנות השבעים"),
            ("1980s", "שנות השמונים"),
            ("1990s", "שנות התשעים"),
            ("2000s", "שנות האלפיים"),
            ("2010s", "שנות האלפיים ועשר"),
            ("2020s", "שנות האלפיים עשרים"),
            ("2030s", "שנות האלפיים שלושים"),
            ("20s", "שנות העשרים"),
            ("30s", "שנות השלושים"),
            ("40s", "שנות הארבעים"),
            ("50s", "שנות החמישים"),
            ("60s", "שנות השישים"),
            ("70s", "שנות השבעים"),
            ("80s", "שנות השמונים"),
            ("90s", "שנות התשעים"),
        ]
        decades_fst = pynini.string_map(decade_map)

        # ----------------- Eras -----------------
        # 500 לפנה״ס -> חמש מאות לפני הספירה
        # 500 לספירה -> חמש מאות לספירה
        # 500 BC / BCE -> חמש מאות לפני הספירה
        # 500 AD / CE -> חמש מאות לספירה
        era_bc = pynini.string_map([
            ("לפנה\"ס", " לפני הספירה"),
            ("לפנה״ס", " לפני הספירה"),
            ("לפנהס", " לפני הספירה"),
            ("לפנה\"צ", " לפני הספירה"),
            ("לפני הספירה", " לפני הספירה"),
            ("BC", " לפני הספירה"),
            ("B.C.", " לפני הספירה"),
            ("BCE", " לפני הספירה"),
            ("B.C.E.", " לפני הספירה"),
        ])
        era_ad = pynini.string_map([
            ("לספירה", " לספירה"),
            ("לסה\"נ", " לספירה"),
            ("לסה״נ", " לספירה"),
            ("לספירה הנוצרית", " לספירה"),
            ("AD", " לספירה"),
            ("A.D.", " לספירה"),
            ("CE", " לספירה"),
            ("C.E.", " לספירה"),
        ])
        all_eras = era_bc | era_ad
        era_dates = cardinal.base_num_f + opt_space + all_eras

        # Combine all date categories
        all_dates = (
            pynutil.add_weight(decades_fst, 0.88)
            | pynutil.add_weight(era_dates, 0.89)
            | pynutil.add_weight(written_dates, 0.90)
            | pynutil.add_weight(numeric_dates, 0.92)
            | pynutil.add_weight(year_range, 0.94)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_dates) + pynutil.insert('"')
        ) | iso_graph
        self.fst = self.fst.optimize()
