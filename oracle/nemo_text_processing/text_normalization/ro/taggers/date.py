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
)
from nemo_text_processing.text_normalization.ro.graph_utils import (
    RO_DASH,
    to_name_token,
)
from nemo_text_processing.text_normalization.ro.taggers.cardinal import CardinalFst


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Romanian dates, e.g.
        "25/12/2024" -> tokens { name: "douăzeci și cinci decembrie două mii douăzeci și patru" }
        "25.12.2024" -> tokens { name: "douăzeci și cinci decembrie două mii douăzeci și patru" }
        "25-12-2024" -> tokens { name: "douăzeci și cinci decembrie două mii douăzeci și patru" }
        "2024-12-25" -> tokens { name: "douăzeci și cinci decembrie două mii douăzeci și patru" }
        "1/5/2023" -> tokens { name: "întâi mai două mii douăzeci și trei" }
        "1 mai" -> tokens { name: "întâi mai" }
        "07.03.2026" -> tokens { name: "șapte martie două mii douăzeci și șase" }
        "2020s" -> tokens { name: "anii două mii douăzeci" }
        "1990s" -> tokens { name: "anii nouăzeci" }
        "anii '90" -> tokens { name: "anii nouăzeci" }
        "500 î.Hr." -> tokens { name: "cinci sute înainte de Hristos" }
        "100 d.Hr." -> tokens { name: "o sută după Hristos" }
        "1990–1995" -> tokens { name: "o mie nouă sute nouăzeci până la o mie nouă sute nouăzeci și cinci" }
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        # Days of the month: 1st is "întâi", 2..31 are cardinal masculine
        day_first = pynini.cross("1", "întâi") | pynini.cross("01", "întâi")
        day_other_pairs = [
            ("2", "doi"), ("02", "doi"),
            ("3", "trei"), ("03", "trei"),
            ("4", "patru"), ("04", "patru"),
            ("5", "cinci"), ("05", "cinci"),
            ("6", "șase"), ("06", "șase"),
            ("7", "șapte"), ("07", "șapte"),
            ("8", "opt"), ("08", "opt"),
            ("9", "nouă"), ("09", "nouă"),
            ("10", "zece"),
            ("11", "unsprezece"),
            ("12", "doisprezece"),
            ("13", "treisprezece"),
            ("14", "paisprezece"),
            ("15", "cincisprezece"),
            ("16", "șaisprezece"),
            ("17", "șaptesprezece"),
            ("18", "optsprezece"),
            ("19", "nouăsprezece"),
            ("20", "douăzeci"),
            ("21", "douăzeci și unu"),
            ("22", "douăzeci și doi"),
            ("23", "douăzeci și trei"),
            ("24", "douăzeci și patru"),
            ("25", "douăzeci și cinci"),
            ("26", "douăzeci și șase"),
            ("27", "douăzeci și șapte"),
            ("28", "douăzeci și opt"),
            ("29", "douăzeci și nouă"),
            ("30", "treizeci"),
            ("31", "treizeci și unu"),
        ]
        day_other = pynini.string_map(day_other_pairs)
        day_graph = (day_first | day_other).optimize()

        # Month numbers to words
        month_num = pynini.string_map([
            ("1", "ianuarie"), ("01", "ianuarie"),
            ("2", "februarie"), ("02", "februarie"),
            ("3", "martie"), ("03", "martie"),
            ("4", "aprilie"), ("04", "aprilie"),
            ("5", "mai"), ("05", "mai"),
            ("6", "iunie"), ("06", "iunie"),
            ("7", "iulie"), ("07", "iulie"),
            ("8", "august"), ("08", "august"),
            ("9", "septembrie"), ("09", "septembrie"),
            ("10", "octombrie"),
            ("11", "noiembrie"),
            ("12", "decembrie"),
        ])

        # Month written names (wide & abbreviated)
        month_written = pynini.string_map([
            ("ianuarie", "ianuarie"), ("ian.", "ianuarie"), ("Ianuarie", "ianuarie"), ("Ian.", "ianuarie"),
            ("februarie", "februarie"), ("feb.", "februarie"), ("Februarie", "februarie"), ("Feb.", "februarie"),
            ("martie", "martie"), ("mar.", "martie"), ("Martie", "martie"), ("Mar.", "martie"),
            ("aprilie", "aprilie"), ("apr.", "aprilie"), ("Aprilie", "aprilie"), ("Apr.", "aprilie"),
            ("mai", "mai"), ("Mai", "mai"),
            ("iunie", "iunie"), ("iun.", "iunie"), ("Iunie", "iunie"), ("Iun.", "iunie"),
            ("iulie", "iulie"), ("iul.", "iulie"), ("Iulie", "iulie"), ("Iul.", "iulie"),
            ("august", "august"), ("aug.", "august"), ("August", "august"), ("Aug.", "august"),
            ("septembrie", "septembrie"), ("sept.", "septembrie"), ("Septembrie", "septembrie"), ("Sept.", "septembrie"),
            ("octombrie", "octombrie"), ("oct.", "octombrie"), ("Octombrie", "octombrie"), ("Oct.", "octombrie"),
            ("noiembrie", "noiembrie"), ("nov.", "noiembrie"), ("Noiembrie", "noiembrie"), ("Nov.", "noiembrie"),
            ("decembrie", "decembrie"), ("dec.", "decembrie"), ("Decembrie", "decembrie"), ("Dec.", "decembrie"),
        ])

        # Year graph
        year_graph = cardinal.cardinal_numbers

        # 1. Separated dates: dd/mm/yyyy, dd.mm.yyyy, dd-mm-yyyy
        sep_slash = pynutil.delete("/") + pynutil.insert(" ")
        sep_dot = pynutil.delete(".") + pynutil.insert(" ")
        sep_dash = pynutil.delete("-") + pynutil.insert(" ")

        date_slash = day_graph + sep_slash + month_num + sep_slash + year_graph
        date_dot = day_graph + sep_dot + month_num + sep_dot + year_graph
        date_dash = day_graph + sep_dash + month_num + sep_dash + year_graph

        # 2. ISO format: yyyy-mm-dd -> day month year
        # E.g. 2024-12-25 -> douăzeci și cinci decembrie două mii douăzeci și patru
        iso_year = NEMO_DIGIT**4 @ year_graph
        iso_month = (NEMO_DIGIT**2 | NEMO_DIGIT) @ month_num
        iso_day = (NEMO_DIGIT**2 | NEMO_DIGIT) @ day_graph
        date_iso = (
            pynutil.insert('date { year: "')
            + iso_year
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + iso_month
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + iso_day
            + pynutil.insert('" }')
        )

        # 3. Written month dates: 25 decembrie 2024, 1 mai 2023, 1 mai, 1 ianuarie
        date_written_full = (
            day_graph
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + month_written
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + year_graph
        )
        date_written_short = (
            day_graph
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + month_written
        )

        # 4. Decades:
        # 2020s -> anii două mii douăzeci
        # 1990s -> anii nouăzeci
        # anii '90, anii 90 -> anii nouăzeci
        # anii 1990 -> anii o mie nouă sute nouăzeci
        decades_map = pynini.string_map([
            ("1920s", "anii o mie nouă sute douăzeci"),
            ("1930s", "anii o mie nouă sute treizeci"),
            ("1940s", "anii o mie nouă sute patruzeci"),
            ("1950s", "anii o mie nouă sute cincizeci"),
            ("1960s", "anii o mie nouă sute șaizeci"),
            ("1970s", "anii o mie nouă sute șaptezeci"),
            ("1980s", "anii o mie nouă sute optzeci"),
            ("1990s", "anii nouăzeci"),
            ("2000s", "anii două mii"),
            ("2010s", "anii două mii zece"),
            ("2020s", "anii două mii douăzeci"),
            ("2030s", "anii două mii treizeci"),
            ("anii '90", "anii nouăzeci"),
            ("anii 90", "anii nouăzeci"),
            ("anii '80", "anii optzeci"),
            ("anii 80", "anii optzeci"),
            ("anii '70", "anii șaptezeci"),
            ("anii 70", "anii șaptezeci"),
            ("anii 1990", "anii o mie nouă sute nouăzeci"),
            ("anii 2000", "anii două mii"),
            ("anii 2020", "anii două mii douăzeci"),
        ])

        # 5. Historical Eras:
        # 500 î.Hr., 500 î.e.n., 500 BC -> cinci sute înainte de Hristos
        # 100 d.Hr., 100 e.n., 100 AD -> o sută după Hristos
        era_bc = pynini.union("î.Hr.", "î.e.n.", "î.Hr", "î.e.n", "BC", "B.C.", "BCE", "B.C.E.")
        era_ad = pynini.union("d.Hr.", "e.n.", "d.Hr", "e.n", "AD", "A.D.", "CE", "C.E.")

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        era_bc_rule = (
            year_graph
            + opt_space
            + pynutil.delete(era_bc)
            + pynutil.insert(" înainte de Hristos")
        )
        era_ad_rule = (
            year_graph
            + opt_space
            + pynutil.delete(era_ad)
            + pynutil.insert(" după Hristos")
        )

        # 6. Year ranges: 1990–1995, 2020-2024 -> o mie nouă sute nouăzeci până la o mie nouă sute nouăzeci și cinci
        # Restrict to 4-digit years to avoid clash with other ranges
        four_digit_year = NEMO_DIGIT**4 @ year_graph
        year_range = (
            four_digit_year
            + opt_space
            + pynini.cross(RO_DASH, " până la ")
            + opt_space
            + four_digit_year
        )


        composite = (
            decades_map
            | date_slash
            | date_dot
            | date_dash
            | date_written_full
            | date_written_short
            | era_bc_rule
            | era_ad_rule
            | year_range
        ).optimize()

        self.fst = (date_iso | to_name_token(composite)).optimize()
