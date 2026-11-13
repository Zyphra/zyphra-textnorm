# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
    delete_space,
)


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing date in day month year [era] order, e.g.
        date { day: "ഇരുപത്തിയഞ്ച്" month: "ഡിസംബർ" year: "രണ്ടായിരത്തി ഇരുപത്തിനാല്" } -> ഇരുപത്തിയഞ്ച് ഡിസംബർ രണ്ടായിരത്തി ഇരുപത്തിനാല്
        date { year: "ആയിരത്തി തൊള്ളായിരത്തി നാൽപ്പത്തിയേഴ്" era: "എ.ഡി." } -> ആയിരത്തി തൊള്ളായിരത്തി നാൽപ്പത്തിയേഴ് എ.ഡി.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="date", kind="verbalize", deterministic=deterministic)

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        sep = delete_space + pynutil.insert(NEMO_SPACE)
        day = field("day")
        month = field("month")
        year = field("year")
        era = pynini.closure(sep + field("era"), 0, 1)

        self.graph = (
            day + sep + month
            | day + sep + month + sep + year + era
            | month + sep + year + era
            | year + era
        ) + delete_space

        self.fst = self.delete_tokens(self.graph).optimize()
