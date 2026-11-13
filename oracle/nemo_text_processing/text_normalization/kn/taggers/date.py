# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    NEMO_DIGIT,
    NEMO_SIGMA,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.kn.utils import get_abs_path

months = pynini.string_file(get_abs_path("data/date/months.tsv"))
month_names = pynini.string_file(get_abs_path("data/date/month_names.tsv"))
year_suffix = pynini.string_file(get_abs_path("data/date/year_suffix.tsv"))


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date. Fields are tagged in written order; the verbalizer only
    accepts day month year [era], so the normalizer's field permutation speaks every date in that order, e.g.
        "25/12/2024" -> date { day: "ಇಪ್ಪತ್ತೈದು" month: "ಡಿಸೆಂಬರ್" year: "ಎರಡು ಸಾವಿರದ ಇಪ್ಪತ್ತನಾಲ್ಕು" }
        "2024-12-25" -> date { year: "ಎರಡು ಸಾವಿರದ ಇಪ್ಪತ್ತನಾಲ್ಕು" month: "ಡಿಸೆಂಬರ್" day: "ಇಪ್ಪತ್ತೈದು" }
        "15 ಆಗಸ್ಟ್ 1947" -> date { day: "ಹದಿನೈದು" month: "ಆಗಸ್ಟ್" year: "ಒಂದು ಸಾವಿರದ ಒಂಬೈನೂರ ನಲವತ್ತೇಳು" }
        "1947 ಕ್ರಿ.ಶ." -> date { year: "ಒಂದು ಸಾವಿರದ ಒಂಬೈನೂರ ನಲವತ್ತೇಳು" era: "ಕ್ರಿಸ್ತ ಶಕ" }
        "1990–1995" -> date { year: "ಒಂದು ಸಾವಿರದ ಒಂಬೈನೂರ ತೊಂಬತ್ತು ರಿಂದ ಒಂದು ಸಾವಿರದ ಒಂಬೈನೂರ ತೊಂಬತ್ತೈದು" }
        "2020s" -> date { year: "ಎರಡು ಸಾವಿರದ ಇಪ್ಪತ್ತರ ದಶಕ" }
        "1990ರ" -> date { year: "ಒಂದು ಸಾವಿರದ ಒಂಬೈನೂರ ತೊಂಬತ್ತರ ದಶಕ" }

    Args:
        cardinal: cardinal GraphFst
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="date", kind="classify")

        cardinal_graph = cardinal.final_graph
        up_to_999 = cardinal.up_to_999
        to_ascii = pynini.closure(TO_ASCII_DIGIT, 1).optimize()

        # Day: 1-31, optional leading zero dropped
        day_num = pynini.compose(to_ascii, pynini.closure(pynutil.delete("0"), 0, 1) + up_to_999)
        day = pynutil.insert("day: \"") + day_num + pynutil.insert("\"")

        # Month: numeric (01-12) or written Kannada month name
        month_from_num = pynini.compose(to_ascii, months)
        month_word = pynutil.insert("month: \"") + month_names + pynutil.insert("\"")
        month = pynutil.insert("month: \"") + (month_from_num | month_names) + pynutil.insert("\"")

        # Year: full 1-4 digit cardinal
        year_num = pynini.compose(to_ascii, cardinal_graph)
        year = pynutil.insert("year: \"") + year_num + pynutil.insert("\"")

        # Year ranges (e.g. 1990-1995, 1990–1995)
        dash = pynini.union("-", "–", "—")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        year_4 = to_ascii @ (NEMO_DIGIT**4 @ cardinal_graph)
        year_range_num = year_4 + opt_sp + pynini.cross(dash, " ರಿಂದ ") + opt_sp + year_4
        year_range = pynutil.insert("year: \"") + year_range_num + pynutil.insert("\"")

        # Decades: "2020s" -> "ಎರಡು ಸಾವಿರದ ಇಪ್ಪತ್ತರ ದಶಕ", "1990ರ" -> "ಒಂದು ಸಾವಿರದ ಒಂಬೈನೂರ ತೊಂಬತ್ತರ ದಶಕ"
        decade_map = pynini.cdrewrite(pynini.cross("ತ್ತು", "ತ್ತರ ದಶಕ"), "", "[EOS]", NEMO_SIGMA)
        decade_num = pynini.compose(year_num, decade_map)
        decade_s = pynutil.insert("year: \"") + (decade_num + pynutil.delete("s")) + pynutil.insert("\"")
        decade_ra = pynutil.insert("year: \"") + (decade_num + pynutil.delete("ರ")) + pynutil.insert("\"")

        # Era: ಕ್ರಿ.ಶ., ಕ್ರಿ.ಪೂ.
        era_part = pynutil.insert("era: \"") + year_suffix + pynutil.insert("\"")

        # Separators for purely numeric dates
        num_sep = pynini.union(pynutil.delete("/"), pynutil.delete("."), pynutil.delete("-"))
        sp_del = pynini.closure(pynutil.delete(" "), 1)
        ins_sp = insert_space

        # Format 1: DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY
        dmy_numeric = day + num_sep + ins_sp + month + num_sep + ins_sp + year

        # Format 2: YYYY-MM-DD (ISO)
        iso_year = pynutil.insert("year: \"") + pynini.compose(to_ascii, pynini.closure(NEMO_DIGIT, 4) @ cardinal_graph) + pynutil.insert("\"")
        iso_month = pynutil.insert("month: \"") + pynini.compose(to_ascii, months) + pynutil.insert("\"")
        iso_day = pynutil.insert("day: \"") + day_num + pynutil.insert("\"")
        ymd_iso = iso_year + pynutil.delete("-") + ins_sp + iso_month + pynutil.delete("-") + ins_sp + iso_day

        # Format 3: Written month formats: "15 ಆಗಸ್ಟ್ 1947", "15 ಆಗಸ್ಟ್", "ಮಾರ್ಚ್ 2021"
        written_dmy = day + sp_del + ins_sp + month_word + pynini.closure(sp_del + ins_sp + year, 0, 1)
        written_my = month_word + sp_del + ins_sp + year

        # Format 4: Year + Era: "1947 ಕ್ರಿ.ಶ."
        year_with_era = year + sp_del + ins_sp + era_part

        self.final_graph = (
            dmy_numeric
            | ymd_iso
            | written_dmy
            | written_my
            | year_with_era
            | year_range
            | decade_s
            | decade_ra
        ).optimize()

        self.fst = self.add_tokens(self.final_graph)
