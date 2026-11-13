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

from nemo_text_processing.text_normalization.ta.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
    delete_space,
)


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing date in Tamil, e.g.
        date { day: "இருபத்து ஐந்து" month: "டிசம்பர்" year: "இரண்டாயிரத்து இருபத்து நான்கு" }
            -> இருபத்து ஐந்து டிசம்பர் இரண்டாயிரத்து இருபத்து நான்கு
        date { year: "இரண்டாயிரத்து இருபத்து நான்கு" month: "டிசம்பர்" day: "இருபத்து ஐந்து" }
            -> இரண்டாயிரத்து இருபத்து நான்கு டிசம்பர் இருபத்து ஐந்து
        date { year: "ஆயிரத்து தொள்ளாயிரத்து நாற்பத்து ஏழு" era: "கிறிஸ்துவுக்குப் பின்" }
            -> ஆயிரத்து தொள்ளாயிரத்து நாற்பத்து ஏழு கிறிஸ்துவுக்குப் பின்
        date { year: "ஆயிரத்து தொள்ளாயிரத்து தொண்ணூறு முதல் ஆயிரத்து தொள்ளாயிரத்து தொண்ணூற்று ஐந்து வரை" }
            -> ஆயிரத்து தொள்ளாயிரத்து தொண்ணூறு முதல் ஆயிரத்து தொள்ளாயிரத்து தொண்ணூற்று ஐந்து வரை
        date { year: "இரண்டாயிரத்து இருபதுகளின் காலகட்டம்" }
            -> இரண்டாயிரத்து இருபதுகளின் காலகட்டம்
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

        optional_preserve_order = pynini.closure(
            pynutil.delete("preserve_order:") + delete_space + pynutil.delete("true") + delete_space
            | pynutil.delete("field_order:")
            + delete_space
            + pynutil.delete("\"")
            + NEMO_NOT_QUOTE
            + pynutil.delete("\"")
            + delete_space,
            0,
            1,
        )

        self.graph = (
            day + sep + month + sep + year + era
            | year + sep + month + sep + day
            | day + sep + month
            | month + sep + year + era
            | year + sep + field("era")
            | year
        ) + delete_space + optional_preserve_order

        delete_tokens = self.delete_tokens(self.graph)
        self.fst = delete_tokens.optimize()
