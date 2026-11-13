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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying phone numbers in Finnish, e.g.
        "+44 20 7946 0958" -> tokens { name: "plus neljä neljä kaksi nolla ..." }
        "(415) 555-0199" -> tokens { name: "neljä yksi viisi viisi viisi viisi nolla yksi yhdeksän yhdeksän" }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digits_map = [
            ("0", "nolla"),
            ("1", "yksi"),
            ("2", "kaksi"),
            ("3", "kolme"),
            ("4", "neljä"),
            ("5", "viisi"),
            ("6", "kuusi"),
            ("7", "seitsemän"),
            ("8", "kahdeksan"),
            ("9", "yhdeksän"),
        ]
        digit = pynini.string_map(digits_map)

        # Digits with space separator
        digit_seq = digit + pynini.closure(pynutil.insert(" ") + digit)

        sep = pynini.cross(pynini.union(" ", "-"), " ")
        chunk = digit_seq

        # Optional country code: "+44", "+1", etc.
        plus = pynini.cross("+", "plus ")
        country_code = plus + chunk + sep

        # Parenthesized area code: "(415)", "(021)"
        area_code = pynutil.delete("(") + chunk + pynutil.delete(")") + pynini.closure(pynutil.delete(pynini.union(" ", "-")), 0, 1) + pynutil.insert(" ")

        # Phone body: chunks of digits
        body = chunk + pynini.closure(sep + chunk, 1, 5)

        full_phone = (
            (pynini.closure(country_code, 0, 1) + pynini.closure(area_code, 0, 1) + body)
            | international_telephone(digit, "plus")
        ).optimize()
        counted_input = (
            pynini.closure(NEMO_DIGIT | pynutil.delete(pynini.union(" ", "-", ".", "(", ")", "+")), 1)
            @ pynini.closure(NEMO_DIGIT, 7, 15)
        )
        full_phone = (pynini.project(counted_input, "input") @ full_phone).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(full_phone).optimize()
            + pynutil.insert('"')
        ).optimize()
