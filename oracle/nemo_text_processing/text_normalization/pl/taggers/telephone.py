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
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Polish telephone numbers, read digit by digit, e.g.
        "+48 123 456 789" -> "plus cztery osiem jeden dwa trzy cztery pięć sześć siedem osiem dziewięć"
        "(415) 555-0199" -> "cztery jeden pięć pięć pięć pięć zero jeden dziewięć dziewięć"
        "+1-800-555-0199" -> "plus jeden osiem zero zero pięć pięć pięć zero jeden dziewięć dziewięć"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digit = cardinal.digit
        digits = digit + pynini.closure(insert_space + digit)
        separator = pynini.cross(pynini.union(" ", "-", "."), " ")
        groups = digits + pynini.closure(separator + digits)
        area = (
            pynutil.delete("(")
            + digits
            + pynutil.delete(")")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + insert_space
        )

        separators = pynini.union(" ", "-", ".", "(", ")")
        long_enough = pynini.closure(pynini.closure(separators) + NEMO_DIGIT, 7) + pynini.closure(separators)

        # Exclude date-like patterns (DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY)
        date_like = pynini.union(
            *[NEMO_DIGIT**2 + sep + NEMO_DIGIT**2 + sep + NEMO_DIGIT**4 for sep in ["/", "-", "."]]
            + [NEMO_DIGIT**4 + sep + NEMO_DIGIT**2 + sep + NEMO_DIGIT**2 for sep in ["-", "."]]
        )

        country_code = (
            pynini.cross("+", "plus ")
            + (pynini.closure(NEMO_DIGIT, 1, 3) @ digits)
            + pynini.cross(pynini.union(" ", "-"), " ")
        )

        num_with_country = country_code + (long_enough @ (pynini.closure(area, 0, 1) + groups))
        num_with_area = long_enough @ (area + groups)
        num_local = long_enough @ groups

        telephone = (num_with_country | num_with_area | num_local).optimize()
        valid_input = pynini.difference(pynini.project(telephone, "input"), date_like.optimize()).optimize()
        valid_tel = valid_input @ telephone

        self.graph = valid_tel.optimize()
        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
