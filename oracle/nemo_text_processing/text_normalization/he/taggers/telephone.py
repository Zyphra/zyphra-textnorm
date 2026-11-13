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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone_token
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew telephone numbers.
    e.g. (021) 555-1234 -> אפס שתיים אחת, חמש חמש חמש, אחת שתיים שלוש ארבע
         +1 555 123 4567 -> פלוס אחת, חמש חמש חמש, אחת שתיים שלוש, ארבע חמש שש שבע
         +972-3-1234567 -> פלוס תשע שבע שתיים, שלוש, אחת שתיים שלוש ארבע חמש שש שבע
         050-1234567 -> אפס חמש אפס, אחת שתיים שלוש ארבע חמש שש שבע
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digit = cardinal.digit_f
        digits = digit + pynini.closure(insert_space + digit)

        # Country code: +1, +972
        plus = pynini.cross("+", "פלוס ")
        country_code = plus + digits + pynutil.insert(", ")

        # Area code in parentheses: (021), (03), (050)
        area_code_paren = (
            pynutil.delete("(")
            + digits
            + pynutil.delete(")")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(", ")
        )

        sep = pynini.cross("-", ", ") | pynini.cross(" ", ", ")

        # Phone chunk of 2 to 4 digits, or 6 to 8 digits
        chunk = digit + insert_space + digit + pynini.closure(insert_space + digit, 0, 2)
        chunk_7 = digit + pynini.closure(insert_space + digit, 5, 7)

        # Israeli standard phone: 050-1234567, 03-1234567, 02-123-4567
        israeli_phone = (
            pynini.closure(country_code, 0, 1)
            + (area_code_paren | (digits + sep))
            + (chunk + sep + chunk | chunk_7)
        )

        # International phone: +1 555 123 4567, (021) 555-1234
        intl_phone = (
            pynini.closure(country_code, 0, 1)
            + (area_code_paren | (digits + sep))
            + chunk
            + pynini.closure(sep + chunk, 1, 3)
        )

        all_phones = (intl_phone | israeli_phone).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_phones) + pynutil.insert('"')
        ).optimize()
        self.fst = (self.fst | pynutil.add_weight(international_telephone_token(digit, "פלוס"), -0.1)).optimize()
