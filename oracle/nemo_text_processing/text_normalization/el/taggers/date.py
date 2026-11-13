# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.el.taggers.cardinal import CardinalFst


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Greek dates, years, decades, and historical eras:
        "15/03/2024" -> δεκαπέντε Μαρτίου δύο χιλιάδες είκοσι τέσσερα
        "2024-03-15" -> δεκαπέντε Μαρτίου δύο χιλιάδες είκοσι τέσσερα
        "15 Μαρτίου 2024" -> δεκαπέντε Μαρτίου δύο χιλιάδες είκοσι τέσσερα
        "1990" -> χίλια εννιακόσια ενενήντα
        "1990–1995" -> χίλια εννιακόσια ενενήντα έως χίλια εννιακόσια ενενήντα πέντε
        "2020s" -> δεκαετία του δύο χιλιάδες είκοσι
        "500 π.Χ." -> πεντακόσια προ Χριστού
        "500 μ.Χ." -> πεντακόσια μετά Χριστόν
        "500 BC" -> πεντακόσια προ Χριστού
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        pure_cardinal = cardinal.pure_cardinal

        # Days 1-31
        days_pairs = [
            ("01", "πρώτη"), ("1", "πρώτη"),
            ("02", "δύο"), ("2", "δύο"),
            ("03", "τρία"), ("3", "τρία"),
            ("04", "τέσσερα"), ("4", "τέσσερα"),
            ("05", "πέντε"), ("5", "πέντε"),
            ("06", "έξι"), ("6", "έξι"),
            ("07", "επτά"), ("7", "επτά"),
            ("08", "οκτώ"), ("8", "οκτώ"),
            ("09", "εννέα"), ("9", "εννέα"),
            ("10", "δέκα"),
            ("11", "έντεκα"),
            ("12", "δώδεκα"),
            ("13", "δεκατρία"),
            ("14", "δεκατέσσερα"),
            ("15", "δεκαπέντε"),
            ("16", "δεκαέξι"),
            ("17", "δεκαεπτά"),
            ("18", "δεκαοκτώ"),
            ("19", "δεκαεννέα"),
            ("20", "είκοσι"),
            ("21", "είκοσι ένα"),
            ("22", "είκοσι δύο"),
            ("23", "είκοσι τρία"),
            ("24", "είκοσι τέσσερα"),
            ("25", "είκοσι πέντε"),
            ("26", "είκοσι έξι"),
            ("27", "είκοσι επτά"),
            ("28", "είκοσι οκτώ"),
            ("29", "είκοσι εννέα"),
            ("30", "τριάντα"),
            ("31", "τριάντα ένα"),
        ]
        day_graph = pynini.string_map(days_pairs)

        # Months in genitive
        month_num_pairs = [
            ("01", "Ιανουαρίου"), ("1", "Ιανουαρίου"),
            ("02", "Φεβρουαρίου"), ("2", "Φεβρουαρίου"),
            ("03", "Μαρτίου"), ("3", "Μαρτίου"),
            ("04", "Απριλίου"), ("4", "Απριλίου"),
            ("05", "Μαΐου"), ("5", "Μαΐου"),
            ("06", "Ιουνίου"), ("6", "Ιουνίου"),
            ("07", "Ιουλίου"), ("7", "Ιουλίου"),
            ("08", "Αυγούστου"), ("8", "Αυγούστου"),
            ("09", "Σεπτεμβρίου"), ("9", "Σεπτεμβρίου"),
            ("10", "Οκτωβρίου"),
            ("11", "Νοεμβρίου"),
            ("12", "Δεκεμβρίου"),
        ]
        month_num = pynini.string_map(month_num_pairs)

        month_names = pynini.string_map(
            [
                ("Ιανουαρίου", "Ιανουαρίου"),
                ("Φεβρουαρίου", "Φεβρουαρίου"),
                ("Μαρτίου", "Μαρτίου"),
                ("Απριλίου", "Απριλίου"),
                ("Μαΐου", "Μαΐου"),
                ("Ιουνίου", "Ιουνίου"),
                ("Ιουλίου", "Ιουλίου"),
                ("Αυγούστου", "Αυγούστου"),
                ("Σεπτεμβρίου", "Σεπτεμβρίου"),
                ("Οκτωβρίου", "Οκτωβρίου"),
                ("Νοεμβρίου", "Νοεμβρίου"),
                ("Δεκεμβρίου", "Δεκεμβρίου"),
            ]
        )

        # Years: 1000 - 2999
        # (e.g. 1990 -> χίλια εννιακόσια ενενήντα, 2024 -> δύο χιλιάδες είκοσι τέσσερα)
        year_num = (pynini.closure(NEMO_DIGIT, 4, 4) @ pure_cardinal).optimize()

        # Separators for numeric dates: "/" or "." or "-"
        sep = pynini.union("/", ".", "-")
        del_sep = pynutil.delete(sep)

        # 1. Numeric date: DD/MM/YYYY or DD.MM.YYYY
        # "15/03/2024" -> "δεκαπέντε Μαρτίου δύο χιλιάδες είκοσι τέσσερα"
        numeric_date_with_year = (
            day_graph + del_sep + pynutil.insert(" ") + month_num + del_sep + pynutil.insert(" ") + year_num
        )
        # Without year: "15/03" -> "δεκαπέντε Μαρτίου"
        numeric_date_no_year = day_graph + del_sep + pynutil.insert(" ") + month_num

        self.iso_fst = (
            pynutil.insert('date { year: "')
            + (NEMO_DIGIT ** 4 @ year_num)
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ month_num)
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ day_graph)
            + pynutil.insert('" }')
        ).optimize()

        # 3. Written date: "15 Μαρτίου 2024", "1 Ιανουαρίου 2000"
        written_date = day_graph + pynutil.delete(" ") + pynutil.insert(" ") + month_names + pynutil.delete(" ") + pynutil.insert(" ") + year_num

        # 4. Standalone years: "1990", "2024" (only 4-digit years 1000-2999)
        # Years with optional trailing dot: "1990."
        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)
        standalone_year = year_num + opt_dot

        # 5. Year ranges: "1990–1995", "1990-1995", "2020-2024"
        range_dash = pynini.cross(pynini.union("-", "–", "—", " - ", " – "), " έως ")
        year_range = year_num + range_dash + year_num

        # 6. Decades: "2020s", "1990s"
        # In Greek: "2020s" -> "δεκαετία του δύο χιλιάδες είκοσι"
        # (CRITICAL: MUST NEVER BE SPOKEN AS SECONDS!)
        decade_s = pynutil.delete(pynini.union("s", "'s", "S"))
        decade_prefix = pynutil.insert("δεκαετία του ")
        decades_num = decade_prefix + (pynini.closure(NEMO_DIGIT, 4, 4) @ pure_cardinal) + decade_s

        written_decade_prefix = pynini.string_map(
            [
                ("δεκαετία του '", "δεκαετία του "),
                ("δεκαετία του ", "δεκαετία του "),
            ]
        )
        decades_written = written_decade_prefix + (
            (pynini.closure(NEMO_DIGIT, 4, 4) @ pure_cardinal)
            | (pynini.closure(NEMO_DIGIT, 2, 2) @ pure_cardinal)
        )

        # 7. Eras: "500 π.Χ.", "500 π.Χ", "500 BC", "500 μ.Χ.", "500 AD"
        bc_sym = pynini.cross(
            pynini.union("π.Χ.", "π.Χ", "πΧ", "π.Κ.Χ.", "BC", "B.C.", "BCE", "B.C.E."),
            "προ Χριστού"
        )
        ad_sym = pynini.cross(
            pynini.union("μ.Χ.", "μ.Χ", "μΧ", "Κ.Χ.", "AD", "A.D.", "CE", "C.E."),
            "μετά Χριστόν"
        )
        era_sym = bc_sym | ad_sym
        era_graph = pure_cardinal + pynutil.delete(pynini.closure(" ", 0, 1)) + pynutil.insert(" ") + era_sym

        all_dates = (
            numeric_date_with_year
            | written_date
            | year_range
            | decades_num
            | decades_written
            | era_graph
        ).optimize()

        self.standalone_year = standalone_year
        self.all_dates = all_dates
        self.fst = all_dates
