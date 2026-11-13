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

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
    delete_space,
)


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing date in day month year [era] order (the only order accepted, so the
    normalizer's field permutation also speaks "YYYY-MM-DD" input this way), e.g.
        date { day: "ఇరవై ఐదు" month: "డిసెంబర్" year: "రెండు వేల ఇరవై నాలుగు" } -> ఇరవై ఐదు డిసెంబర్ రెండు వేల ఇరవై నాలుగు
        date { year: "వెయ్యి తొమ్మిది వందల నలభై ఏడు" era: "క్రీస్తు శకం" } -> వెయ్యి తొమ్మిది వందల నలభై ఏడు క్రీస్తు శకం
    """

    def __init__(self):
        super().__init__(name="date", kind="verbalize")

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

        delete_tokens = self.delete_tokens(self.graph)
        self.fst = delete_tokens.optimize()
