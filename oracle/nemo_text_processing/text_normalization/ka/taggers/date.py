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
    delete_space,
)
from nemo_text_processing.text_normalization.ka.graph_utils import glue_suffix, with_suffix
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Georgian dates, e.g.
        25.12.2024 -> date { year: "ორი ათას ოცდაოთხი" day: "ოცდახუთი" month: "დეკემბერი" }
        2024-12-25 -> date { year: "ორი ათას ოცდაოთხი" day: "ოცდახუთი" month: "დეკემბერი" }
        2024 წლის 25 დეკემბერს -> date { year: "ორი ათას ოცდაოთხი" day: "ოცდახუთ" month: "დეკემბერს" }
        15 მაისს -> date { day: "თხუთმეტ" month: "მაისს" }
        1990–1995 -> date { year: "ათას ცხრაას ოთხმოცდაათიდან ათას ცხრაას ოთხმოცდათხუთმეტამდე" }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        numbers = cardinal.all_nums_no_tokens
        day_digits = (
            (pynini.closure(pynutil.delete("0"), 0, 1) + (NEMO_DIGIT - "0"))
            | (pynini.union("1", "2") + NEMO_DIGIT)
            | pynini.union("30", "31")
        )
        day_number = (day_digits @ numbers).optimize()
        month_number = pynini.string_file(get_abs_path("data/dates/month_number.tsv"))
        month_name = pynini.string_file(get_abs_path("data/dates/month_name.tsv"))
        year_number = ((NEMO_DIGIT - "0") + NEMO_DIGIT ** 3) @ numbers

        year_word = pynini.union(" წლის", " წელს", " წ.", " წწ.", " წ", " წელი")

        day = pynutil.insert('day: "') + day_number + pynutil.insert('"')
        day_suffixed = pynutil.insert('day: "') + (day_number | with_suffix(day_number)) + pynutil.insert('"')
        month_num = pynutil.insert(' month: "') + month_number + pynutil.insert('" ')
        month = pynutil.insert('month: "') + month_name + pynutil.insert('"')
        year = pynutil.insert('year: "') + year_number + pynutil.insert('"')

        graph = pynini.Fst()
        # DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY
        for sep in (".", "/", "-"):
            graph |= (
                day + pynutil.delete(sep) + month_num + pynutil.delete(sep) + year
                + pynini.closure(pynutil.delete(year_word), 0, 1)
            )

        # YYYY-MM-DD / YYYY.MM.DD
        for sep in ("-", "."):
            graph |= year + pynutil.delete(sep) + month_num + pynutil.delete(sep) + day

        # 2024 წლის 25 დეკემბერი / 2024 წლის 25 დეკემბერს
        graph |= (
            year + pynutil.delete(year_word) + delete_space + pynutil.insert(" ")
            + day_suffixed + pynini.accep(" ") + month
        )

        # 25 დეკემბერი 2024 / 25 დეკემბერს 2024 წელს
        graph |= (
            day_suffixed + pynini.accep(" ") + month + delete_space + pynutil.insert(" ")
            + year + pynini.closure(pynutil.delete(year_word), 0, 1)
        )

        # Day + Month alone: "15 მაისი", "15 მაისს", "1-ელ მაისს"
        graph |= day_suffixed + pynini.accep(" ") + month

        # Year alone with year_word: "2024 წელს" -> "ორი ათას ოცდაოთხ წელს", "2024 წ." -> "ორი ათას ოცდაოთხ წელს"
        year_alone = year + delete_space + pynutil.insert(' era: "') + (
            pynini.cross("წლის", "წლის")
            | pynini.cross("წელს", "წელს")
            | pynini.cross("წ.", "წელს")
            | pynini.cross("წელი", "წელი")
        ) + pynutil.insert('"')
        graph |= year_alone

        # Historical eras: "500 ძვ. წ." / "500 BC" -> "ხუთასი ჩვენს ერამდე"
        era_bc = pynini.cross(pynini.union("ძვ. წ.", "ძვ.წ.", "BC", "B.C."), "ჩვენს ერამდე")
        era_ad = pynini.cross(pynini.union("ახ. წ.", "ახ.წ.", "ჩვ. წ.", "AD", "A.D."), "ჩვენი ერით")
        era_year_num = (pynini.closure(NEMO_DIGIT, 1, 4) @ numbers).optimize()
        era_graph = (
            pynutil.insert('year: "') + era_year_num + pynutil.insert('" era: "')
            + delete_space + (era_bc | era_ad) + pynutil.insert('"')
        )
        graph |= era_graph

        # Year ranges: "1990–1995", "1990-1995"
        dash = pynini.union("-", "–", "—", "֊")
        year_from = glue_suffix(year_number + pynutil.insert("+დან"))
        year_to = glue_suffix(year_number + pynutil.insert("+მდე"))
        year_range = (
            pynutil.insert('year: "')
            + year_from
            + pynutil.delete(dash)
            + pynutil.insert(" ")
            + year_to
            + pynutil.insert('"')
            + pynini.closure(pynutil.delete(year_word), 0, 1)
        )
        graph |= year_range

        self.fst = self.add_tokens(graph).optimize()
