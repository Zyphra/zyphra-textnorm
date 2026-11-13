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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying telephone numbers in Georgian, e.g.
        "(415) 555-0199" -> telephone { number_part: "ოთხი ერთი ხუთი, ხუთი ხუთი ხუთი, ნული ერთი ცხრა ცხრა" }
        "+995 32 2123456" -> telephone { country_code: "პლუს ცხრა ცხრა ხუთი" number_part: "სამი ორი, ორი ერთი ორი სამი ოთხი ხუთი ექვსი" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)
        digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv")) | pynini.cross("0", "ნული")
        digits = digit + pynini.closure(insert_space + digit)
        group = pynini.compose(pynini.closure(NEMO_DIGIT, 1, 8), digits)
        separator = pynini.cross(pynini.union(" ", "-", ".", "–", "—", "֊"), ", ")
        plus = pynini.cross("+", "პლუს ")

        country_code = (
            pynutil.insert('country_code: "')
            + plus
            + pynini.compose(pynini.closure(NEMO_DIGIT, 1, 3), digits)
            + pynutil.insert('"')
        )
        parenthesized = (
            pynutil.delete("(") + group + pynutil.delete(")") + pynini.cross(pynini.closure(" ", 0, 1), ", ")
        )
        grouped = pynini.closure(parenthesized, 0, 1) + group + pynini.closure(separator + group, 1)
        grouped |= parenthesized + group
        number_part = pynutil.insert('number_part: "') + grouped + pynutil.insert('"')

        separator_chars = pynini.union(" ", "-", ".", "–", "—", "֊", "(", ")")
        min_digits = "0" + pynini.closure(pynini.closure(separator_chars) + NEMO_DIGIT, 6)
        min_digits += pynini.closure(separator_chars | NEMO_DIGIT)

        paren_local = (
            "("
            + NEMO_DIGIT ** (2, 5)
            + ")"
            + pynini.closure(" ", 0, 1)
            + (
                (
                    NEMO_DIGIT ** (2, 4)
                    + pynini.union(" ", "-", ".", "–", "—", "֊")
                    + NEMO_DIGIT ** (2, 6)
                    + pynini.closure(pynini.union(" ", "-", ".", "–", "—", "֊") + NEMO_DIGIT ** (1, 4))
                )
                | NEMO_DIGIT ** (6, 8)
            )
        )
        local = pynini.compose(min_digits | paren_local, number_part)
        local |= pynutil.insert('number_part: "') + pynini.compose("0" + NEMO_DIGIT ** (8, 11), digits) + pynutil.insert('"')
        international = country_code + pynini.cross(pynini.union(" ", "-"), " ") + number_part
        international |= (
            pynutil.insert('number_part: "') + plus + pynini.compose(NEMO_DIGIT ** (7, 15), digits) + pynutil.insert('"')
        )

        graph = international | local
        self.fst = self.add_tokens(graph + pynutil.insert(" preserve_order: true")).optimize()
