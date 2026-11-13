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

# Number names from Unicode CLDR release-49 (fil locale, Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst
from nemo_text_processing.text_normalization.tl.utils import get_abs_path


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Tagalog dates, decades, and historical eras, e.g.
        "17/08/1945" -> date { day: "labimpito" month: "Agosto" year: "isang libo siyam na raan apatnapu't lima" }
        "2024-03-15" -> date { day: "labinlima" month: "Marso" year: "dalawang libo dalawampu't apat" }
        "1 Mayo 2023" -> date { day: "una" month: "Mayo" year: "dalawang libo dalawampu't tatlo" }
        "2020s" -> date { year: "mga taong dalawang libo dalawampu" }
        "500 BC" -> date { year: "limang daan bago si Kristo" }

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
        day_one = pynini.cross("1", "una") | pynini.cross("01", "una")
        day_other_digits = pynini.union(*[str(x) for x in range(2, 32)])
        day_other = (optional_zero + day_other_digits) @ cardinal.graph
        day_graph = day_one | day_other

        day = pynutil.insert('day: "') + day_graph + pynutil.insert('"')
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

        # Numeric date: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        graph = pynini.union(
            *[day + pynini.cross(sep, " ") + month_number + pynini.cross(sep, " ") + year for sep in ["/", "-", "."]]
        )
        month_first = pynini.union(
            *[month_number + pynini.cross(sep, " ") + day + pynini.cross(sep, " ") + year for sep in ["/", "-", "."]]
        )
        graph |= pynutil.add_weight(month_first, -0.01)

        # ISO date: YYYY-MM-DD
        iso_graph = (
            year_four + pynutil.delete("-") + pynutil.insert(" ")
            + month_number + pynutil.delete("-") + pynutil.insert(" ") + day
        )
        graph |= iso_graph

        # Written month date: "17 Agosto 1945", "1 Mayo 2023", "10 Nob 2020"
        graph |= day + pynini.accep(" ") + month_name + pynini.closure(pynini.accep(" ") + year, 0, 1)
        graph |= month_name + pynini.accep(" ") + day + pynini.closure(pynini.closure(pynini.accep(","), 0, 1) + pynini.accep(" ") + year, 0, 1)

        # Standalone Month + Year: "Des 2019", "Enero 2024"
        graph |= month_name + pynini.accep(" ") + year_four

        # Decades: "2020s" -> "mga taong dalawang libo dalawampu", "1990s"
        decade_root = (pynini.union("1", "2") + NEMO_DIGIT**2 + "0") @ cardinal.graph
        decade_graph = (
            pynutil.insert('year: "mga taong ')
            + decade_root
            + pynutil.delete(pynini.union("s", "-an", "s'"))
            + pynutil.insert('"')
        )
        decade_prefix = (
            pynutil.delete(pynini.union("dekada ", "Dekada ", "mga taong "))
            + pynutil.insert('year: "mga taong ')
            + decade_root
            + pynutil.insert('"')
        )
        graph |= decade_graph | decade_prefix

        # Eras: "500 BC", "500 BK", "AD 2024", "2024 MK"
        era_bc = pynini.union("BC", "B.C.", "BK", "B.K.", "BCE", "B.C.E.")
        era_ad = pynini.union("AD", "A.D.", "MK", "M.K.", "CE", "C.E.")
        year_num = (pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal.graph).optimize()

        era_trailing_bc = (
            pynutil.insert('year: "')
            + year_num
            + pynutil.delete(pynini.closure(pynini.accep(" "), 0, 1))
            + pynutil.delete(era_bc)
            + pynutil.insert(' bago si Kristo"')
        )
        era_trailing_ad = (
            pynutil.insert('year: "')
            + year_num
            + pynutil.delete(pynini.closure(pynini.accep(" "), 0, 1))
            + pynutil.delete(era_ad)
            + pynutil.insert(' ng ating panahon"')
        )
        era_leading_ad = (
            pynutil.delete(era_ad)
            + pynutil.delete(pynini.closure(pynini.accep(" "), 0, 1))
            + pynutil.insert('year: "')
            + year_num
            + pynutil.insert(' ng ating panahon"')
        )
        graph |= era_trailing_bc | era_trailing_ad | era_leading_ad

        self.fst = self.add_tokens(graph).optimize()
