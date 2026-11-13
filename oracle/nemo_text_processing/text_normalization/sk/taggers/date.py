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
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Slovak dates, e.g.
        06.03.2006 -> šiesteho marca dvetisícšesť
        15. 3. 2020 -> pätnásteho marca dvetisícdvadsať
        15. marca 2020 -> pätnásteho marca dvetisícdvadsať
        1. januára -> prvého januára
        2024-12-25 -> dvadsiateho piateho decembra dvetisícdvadsaťštyri
        v roku 1999 -> v roku tisíc deväťsto deväťdesiatdeväť
        1995–2005 -> tisíc deväťsto deväťdesiatpäť až dvetisícpäť
        1990-te, 2020s -> deväťdesiate roky, dvadsiate roky
        500 pred n. l., 500 BC -> päťsto pred naším letopočtom
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        months_map = {
            1: "januára",
            2: "februára",
            3: "marca",
            4: "apríla",
            5: "mája",
            6: "júna",
            7: "júla",
            8: "augusta",
            9: "septembra",
            10: "októbra",
            11: "novembra",
            12: "decembra",
        }

        days_map = {
            1: "prvého",
            2: "druhého",
            3: "tretieho",
            4: "štvrtého",
            5: "piateho",
            6: "šiesteho",
            7: "siedmeho",
            8: "ôsmeho",
            9: "deviateho",
            10: "desiateho",
            11: "jedenásteho",
            12: "dvanásteho",
            13: "trinásteho",
            14: "štrnásteho",
            15: "pätnásteho",
            16: "šestnásteho",
            17: "sedemnásteho",
            18: "osemnásteho",
            19: "devätnásteho",
            20: "dvadsiateho",
            21: "dvadsiateho prvého",
            22: "dvadsiateho druhého",
            23: "dvadsiateho tretieho",
            24: "dvadsiateho štvrtého",
            25: "dvadsiateho piateho",
            26: "dvadsiateho šiesteho",
            27: "dvadsiateho siedmeho",
            28: "dvadsiateho ôsmeho",
            29: "dvadsiateho deviateho",
            30: "tridsiateho",
            31: "tridsiateho prvého",
        }

        months_gen_pairs = []
        for m, name in months_map.items():
            months_gen_pairs.append((str(m), name))
            months_gen_pairs.append((f"{m:02d}", name))
        months_num = pynini.string_map(months_gen_pairs)

        days_gen_pairs = []
        for d, name in days_map.items():
            days_gen_pairs.append((str(d), name))
            days_gen_pairs.append((f"{d:02d}", name))
        days_num = pynini.string_map(days_gen_pairs)

        # Standalone month names in Slovak
        months_written = pynini.string_map([
            ("januára", "januára"),
            ("január", "január"),
            ("februára", "februára"),
            ("február", "február"),
            ("marca", "marca"),
            ("marec", "marec"),
            ("apríla", "apríla"),
            ("apríl", "apríl"),
            ("mája", "mája"),
            ("máj", "máj"),
            ("júna", "júna"),
            ("jún", "jún"),
            ("júla", "júla"),
            ("júl", "júl"),
            ("augusta", "augusta"),
            ("august", "august"),
            ("septembra", "septembra"),
            ("september", "september"),
            ("októbra", "októbra"),
            ("október", "október"),
            ("novembra", "novembra"),
            ("november", "november"),
            ("decembra", "decembra"),
            ("december", "december"),
        ])

        # Years graph
        years_graph = cardinal.all_positive

        # Dot or slash separator
        sep = pynutil.delete(pynini.union(".", "/", ". "))
        opt_suf = pynini.closure(pynutil.delete(pynini.union(".", "г.", "g.", "r.", " roku")), 0, 1)

        # 1. DD.MM.YYYY or D. M. YYYY
        year_numeric = (NEMO_DIGIT ** 4 | NEMO_DIGIT ** 2) @ years_graph
        year_with_suf = years_graph + pynutil.delete(pynini.union("г.", "g.", "r.", " roku"))
        dmy_year = year_numeric + opt_suf | year_with_suf
        date_dmy = (
            days_num
            + sep
            + pynutil.insert(" ")
            + months_num
            + sep
            + pynutil.insert(" ")
            + dmy_year
        )

        # 2. DD. written_month YYYY
        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)
        date_written_dmy = (
            days_num
            + opt_dot
            + pynini.accep(" ")
            + months_written
            + pynini.accep(" ")
            + years_graph
            + opt_suf
        )

        # 3. DD. written_month (e.g. 1. januára)
        date_dm = days_num + opt_dot + pynini.accep(" ") + months_written

        self.iso_fst = (
            pynutil.insert('date { year: "')
            + (NEMO_DIGIT ** 4 @ years_graph)
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ months_num)
            + pynutil.insert('" day: "')
            + pynutil.delete("-")
            + (NEMO_DIGIT ** 2 @ days_num)
            + pynutil.insert('" }')
        ).optimize()

        # 5. Year context: v 1999 roku, v roku 1999
        v_roku = pynini.cross("v roku ", "v roku ") | pynini.cross("v ", "v roku ")
        opt_roku = pynini.closure(pynutil.delete(pynini.union(" roku", " r.")), 0, 1)
        year_context = v_roku + years_graph + opt_roku

        # 6. Year ranges: 1995–2005, 1990–1995
        dash = pynini.cross(pynini.union("-", "–", "—"), " až ")
        year_4d = pynini.closure(pynini.union(*"0123456789"), 4, 4) @ years_graph
        year_range = year_4d + dash + year_4d

        # 7. Decades: 1990-te, 90-te, 90. roky, 2020s
        decade_names = pynini.string_map([
            ("0", "nulté"), ("10", "desiate"), ("20", "dvadsiate"), ("30", "tridsiate"),
            ("40", "štyridsiate"), ("50", "päťdesiate"), ("60", "šesťdesiate"),
            ("70", "sedemdesiate"), ("80", "osemdesiate"), ("90", "deväťdesiate"),
        ])
        short_decade = decade_names + pynutil.delete(pynini.union("-te", "s", ". roky")) + pynutil.insert(" roky")
        dated_decade = (
            pynutil.insert("desaťročie od roku ")
            + ((NEMO_DIGIT**3 + "0") @ years_graph)
            + pynutil.delete(pynini.union("-te", "s", " roky", "-roky"))
        )
        decade = short_decade | dated_decade

        # 8. Eras: 500 pred n. l., 500 pred n.l., 500 BC, 100 n. l., 100 AD
        era_bc = pynutil.delete(pynini.union(" pred n. l.", " pred n.l.", " BC", " BCE")) + pynutil.insert(
            " pred naším letopočtom"
        )
        era_ad = pynutil.delete(pynini.union(" n. l.", " n.l.", " AD", " CE")) + pynutil.insert(" nášho letopočtu")
        era = (years_graph + era_bc) | (years_graph + era_ad)

        all_dates = (
            pynutil.add_weight(date_written_dmy, 0.06)
            | pynutil.add_weight(date_dmy, 0.07)
            | pynutil.add_weight(date_dm, 0.08)
            | pynutil.add_weight(year_context, 0.09)
            | pynutil.add_weight(year_range, 0.09)
            | pynutil.add_weight(decade, 0.05)
            | pynutil.add_weight(era, 0.05)
        )

        self.fst = all_dates.optimize()
