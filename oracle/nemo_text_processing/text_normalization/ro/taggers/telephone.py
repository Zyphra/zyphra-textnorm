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
)
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone
from nemo_text_processing.text_normalization.ro.graph_utils import to_name_token


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Romanian telephone numbers, e.g.
        "+40 721 123 456" -> tokens { name: "plus patru zero șapte doi unu unu doi trei patru cinci șase" }
        "+1 555 123 4567" -> tokens { name: "plus unu cinci cinci cinci unu doi trei patru cinci șase șapte" }
        "06 1234 5678" -> tokens { name: "zero șase unu doi trei patru cinci șase șapte opt" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digit_map = pynini.string_map([
            ("0", "zero"),
            ("1", "unu"),
            ("2", "doi"),
            ("3", "trei"),
            ("4", "patru"),
            ("5", "cinci"),
            ("6", "șase"),
            ("7", "șapte"),
            ("8", "opt"),
            ("9", "nouă"),
        ])

        # Delete optional formatting characters: spaces, hyphens, dots, parentheses
        delete_sep = pynutil.delete(pynini.union(" ", "-", ".", "(", ")"))

        # Digits sequence with spaces
        digit_with_space = digit_map + pynutil.insert(" ")
        digit_elem = pynini.closure(delete_sep, 0, 2) + digit_with_space
        last_digit = pynini.closure(delete_sep, 0, 2) + digit_map

        # National numbers start with zero; unmarked grouped integers are not phones.
        phone_body = pynini.closure(digit_elem, 6, 14) + last_digit
        national_inputs = (
            pynini.closure(pynini.union(" ", "("), 0, 2)
            + "0"
            + pynini.closure(NEMO_DIGIT | pynini.union(" ", "-", ".", "(", ")"))
        )
        full_phone = (
            international_telephone(digit_map, "plus")
            | (national_inputs @ phone_body)
        ).optimize()
        self.fst = to_name_token(full_phone)
