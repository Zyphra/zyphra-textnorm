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

# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst
from nemo_text_processing.text_normalization.id.utils import get_abs_path


class DateFst(GraphFst):
    """
    Finite state transducer for classifying dates, decades, and historical eras, e.g.
        "17/08/1945" -> date { day: "tujuh belas" month: "Agustus" year: "seribu sembilan ratus empat puluh lima" }
        "2024-01-05" -> date { year: "dua ribu dua puluh empat" month: "Januari" day: "lima" }
        "1 Mei 2023" -> date { day: "satu" month: "Mei" year: "dua ribu dua puluh tiga" }
        "1990-an" -> date { year: "seribu sembilan ratus sembilan puluhan" }
        "2020s" -> date { year: "dua ribu dua puluhan" }
        "500 SM" -> date { year: "lima ratus sebelum Masehi" }
    Bare years stay cardinals.

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)
        month_numbers = pynini.string_file(get_abs_path("data/months/numbers.tsv"))
        month_names = pynini.string_file(get_abs_path("data/months/names.tsv"))
        month_abbr = pynini.string_file(get_abs_path("data/months/abbr.tsv"))
        month_abbr += pynini.closure(pynutil.delete("."), 0, 1)

        optional_zero = pynini.closure(pynutil.delete("0"), 0, 1)
        day_digits = pynini.union(*[str(x) for x in range(1, 32)])
        day = pynutil.insert('day: "') + (optional_zero + day_digits) @ cardinal.graph + pynutil.insert('"')
        month_digits = pynini.union(*[str(x) for x in range(1, 13)])
        month_number = (
            pynutil.insert('month: "') + (optional_zero + month_digits) @ month_numbers + pynutil.insert('"')
        )
        month_name = pynutil.insert('month: "') + (month_names | month_abbr) + pynutil.insert('"')
        year_digits = (pynini.union("1", "2") + NEMO_DIGIT**3) | NEMO_DIGIT**2
        year = pynutil.insert('year: "') + year_digits @ cardinal.graph + pynutil.insert('"')
        year_four = (
            pynutil.insert('year: "') + (pynini.union("1", "2") + NEMO_DIGIT**3) @ cardinal.graph + pynutil.insert('"')
        )

        graph = pynini.union(
            *[day + pynini.cross(sep, " ") + month_number + pynini.cross(sep, " ") + year for sep in ["/", "-", "."]]
        )
        graph |= year_four + pynini.cross("-", " ") + month_number + pynini.cross("-", " ") + day
        graph |= day + pynini.accep(" ") + month_name + pynini.closure(pynini.accep(" ") + year_four, 0, 1)
        graph |= month_name + pynini.accep(" ") + year_four

        # Decades: native "1990-an", "2020-an", "90-an", "80an" and international "1990s", "2020s", "90s", "'90s"
        # E.g. "2020" -> "dua ribu dua puluh" + "an" -> "dua ribu dua puluhan", "2000" -> "dua ribuan"
        decade_4d = ((pynini.union("1", "2") + NEMO_DIGIT**2 + "0") @ cardinal.graph) + pynini.cross(
            pynini.union("-an", "an", "s", "'s"), "an"
        )
        decade_2d = (
            pynini.closure(pynutil.delete(pynini.union("'", "’")), 0, 1)
            + (((NEMO_DIGIT - "0") + "0") @ cardinal.graph)
            + pynini.cross(pynini.union("-an", "an", "s", "'s"), "an")
        )
        tahun_prefix = pynini.union("tahun ", "Tahun ", "era ", "Era ")
        decade_expr = pynini.closure(tahun_prefix, 0, 1) + (decade_4d | decade_2d)
        graph |= pynutil.insert('year: "') + decade_expr + pynutil.insert('"')

        # Historical eras: unambiguous ("500 SM", "500 BC", "100 AD", "500 BCE", "200 CE") + keyed "tahun 100 M" / "1445 H"
        era_year_num = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 3)) @ cardinal.graph
        unambiguous_era_suffix = pynini.string_map(
            [
                ("SM", "sebelum Masehi"),
                ("S.M.", "sebelum Masehi"),
                ("SEU", "sebelum Era Umum"),
                ("BC", "sebelum Masehi"),
                ("B.C.", "sebelum Masehi"),
                ("BCE", "sebelum Masehi"),
                ("B.C.E.", "sebelum Masehi"),
                ("AD", "Masehi"),
                ("A.D.", "Masehi"),
                ("CE", "Masehi"),
                ("C.E.", "Masehi"),
                ("EU", "Era Umum"),
            ]
        ).optimize()
        keyed_single_era = pynini.string_map(
            [
                ("M", "Masehi"),
                ("H", "Hijriah"),
            ]
        ).optimize()
        era_expr = (
            pynini.closure(pynini.union("tahun ", "Tahun "), 0, 1)
            + era_year_num
            + pynini.accep(" ")
            + unambiguous_era_suffix
            | pynini.union("tahun ", "Tahun ", "abad ke-")
            + era_year_num
            + pynini.accep(" ")
            + keyed_single_era
        )
        graph |= pynutil.insert('year: "') + era_expr + pynutil.insert('"')

        self.fst = self.add_tokens(graph).optimize()
