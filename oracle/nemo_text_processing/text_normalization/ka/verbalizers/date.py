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
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_preserve_order,
    delete_space,
)


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing dates in Georgian, e.g.
        date { year: "ორი ათას ოცდაოთხი" day: "ოცდახუთი" month: "დეკემბერი" }
            -> ორი ათას ოცდაოთხი წლის ოცდახუთი დეკემბერი
        date { day: "თხუთმეტ" month: "მაისს" } -> თხუთმეტ მაისს
        date { year: "ხუთასი" era: "ჩვენს ერამდე" } -> ხუთასი ჩვენს ერამდე
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="date", kind="verbalize", deterministic=deterministic)

        def field(name):
            return pynutil.delete(f'{name}: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        year = field("year")
        month = field("month")
        day = field("day")
        era = field("era")

        # 1. Full date: year + day + month -> "<year> წლის <day> <month>"
        year_day_month = (
            year
            + delete_space
            + pynutil.insert(" წლის ")
            + day
            + delete_space
            + pynutil.insert(" ")
            + month
        )

        # 2. Day + Month -> "<day> <month>"
        day_month = day + delete_space + pynutil.insert(" ") + month

        # 3. Year + Era -> "<year> <era>"
        year_era = year + delete_space + pynutil.insert(" ") + era

        # 4. Year alone -> "<year>"
        year_alone = year

        graph = (year_day_month | day_month | year_era | year_alone) + delete_preserve_order
        self.fst = self.delete_tokens(graph).optimize()
