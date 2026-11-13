# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)


class TelephoneFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål phone numbers.
    e.g. +47 22 12 34 56 -> pluss førtisju, tjueto tolv trettifire femtiseks
         070-123 45 67 -> null sytti, ett hundre og tjuetre førtifem sekstisju
         +1 555 123 4567 -> pluss en femhundreogfemtifem, ett hundre og tjuetre førtifem sekstisju
         (021) 555-1234 -> null tjueen, femhundreogfemtifem tolv trettifire
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        card = cardinal.cardinal_masculine

        # Read 2-digit number (e.g. 22 -> tjueto, 08 -> null åtte)
        single_digit = pynini.string_map(
            [
                ("0", "null"),
                ("1", "en"),
                ("2", "to"),
                ("3", "tre"),
                ("4", "fire"),
                ("5", "fem"),
                ("6", "seks"),
                ("7", "sju"),
                ("8", "åtte"),
                ("9", "ni"),
            ]
        )
        two_digit = card | (pynini.cross("0", "null ") + single_digit)
        three_digit = card | (pynini.cross("0", "null ") + two_digit)

        # Country code prefix: +47, +1, +46, +44, +358
        country_code = pynini.cross("+", "pluss ") + card

        # 8-digit Norwegian phone: "22 12 34 56"
        nor_8_spaced = (
            two_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
        )

        # Norwegian phone with country code: "+47 22 12 34 56"
        nor_intl = (
            country_code
            + pynutil.delete(" ")
            + pynutil.insert(", ")
            + nor_8_spaced
        )

        # Swedish/Norwegian hyphen format: "070-123 45 67"
        hyphen_phone = (
            (three_digit | two_digit)
            + pynutil.delete("-")
            + pynutil.insert(", ")
            + three_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
        )

        # Area code in parentheses: "(021) 555-1234"
        paren_phone = (
            pynutil.delete("(")
            + three_digit
            + pynutil.delete(") ")
            + pynutil.insert(", ")
            + three_digit
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.insert(" ")
            + two_digit
        )

        paren_phone_us = (
            pynutil.delete("(")
            + three_digit
            + pynutil.delete(") ")
            + pynutil.insert(", ")
            + three_digit
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + (two_digit + pynutil.insert(" ") + two_digit)
        )

        # International US: "+1 555 123 4567"
        intl_us = (
            country_code
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + three_digit
            + pynutil.delete(" ")
            + pynutil.insert(", ")
            + three_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
        )

        # UK: "+44 20 7946 0958"
        intl_uk = (
            country_code
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.delete(" ")
            + pynutil.insert(", ")
            + two_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + two_digit
        )

        # 800 numbers: "+1-800-555-0199"
        toll_free = (
            country_code
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + three_digit
            + pynutil.delete("-")
            + pynutil.insert(", ")
            + three_digit
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + two_digit
            + pynutil.insert(" ")
            + two_digit
        )

        all_phones = (
            nor_intl
            | nor_8_spaced
            | hyphen_phone
            | paren_phone
            | paren_phone_us
            | intl_us
            | intl_uk
            | toll_free
        )

        self.graph = all_phones.optimize()
        self.fst = (self.graph | international_telephone(single_digit, "pluss")).optimize()
