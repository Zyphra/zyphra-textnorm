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

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGIT,
    convert_space,
)
from .cardinal import SINGLE_DIGITS


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying phone numbers in Odia:
        +44 20 7946 0958 -> tokens { name: "ପ୍ଲସ୍ ଚାରି ଚାରି ଦୁଇ ଶୂନ୍ୟ ସାତ ନଅ ଚାରି ଛଅ ଶୂନ୍ୟ ନଅ ପାଞ୍ଚ ଆଠ" }
        +1-555-123-4567 -> tokens { name: "ପ୍ଲସ୍ ଏକ ପାଞ୍ଚ ପାଞ୍ଚ ପାଞ୍ଚ ଏକ ଦୁଇ ତିନି ଚାରି ପାଞ୍ଚ ଛଅ ସାତ" }
    """

    def __init__(self, cardinal=None, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        single_digit_word = pynini.string_map([(k, v) for k, v in SINGLE_DIGITS.items()])
        digit_trans = (NORMALIZE_DIGIT @ single_digit_word).optimize()

        # Delimiters in phone numbers: spaces, hyphens, parentheses
        del_sep = pynutil.delete(pynini.union(" ", "-", "(", ")", "."))

        # A phone digit with optional delimiters
        phone_digit = pynini.closure(del_sep) + digit_trans + pynini.closure(del_sep)

        # Phone digits sequence: at least 7 digits to avoid matching short numbers
        phone_body = phone_digit + pynini.closure(pynutil.insert(" ") + phone_digit, 6, 15)

        # Country code prefix: + followed by 1 to 3 digits
        plus_prefix = pynini.cross("+", "ପ୍ଲସ୍ ")

        # Full phone number:
        phone_with_plus = (plus_prefix + phone_body).optimize()

        # Parenthesized area code followed by phone number: (021) 555-1234
        area_code = pynutil.delete("(") + phone_digit + pynini.closure(pynutil.insert(" ") + phone_digit, 1, 4) + pynutil.delete(")")
        phone_with_area = (area_code + pynutil.insert(" ") + phone_body).optimize()

        all_phones = (phone_with_plus | phone_with_area).optimize()
        self.phone_graph = all_phones

        graph = pynutil.insert('name: "') + convert_space(all_phones) + pynutil.insert('"')
        self.fst = graph.optimize()
