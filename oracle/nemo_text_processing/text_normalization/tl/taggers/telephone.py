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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst, insert_space


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Tagalog telephone numbers, read digit by digit, e.g.
        "+63 917 123 4567" -> telephone { country_code: "plus anim tatlo" number_part: "siyam isa pito isa dalawa tatlo apat lima anim pito" preserve_order: true }
        "(02) 8123-4567" -> telephone { number_part: "sero dalawa walo isa dalawa tatlo apat lima anim pito" preserve_order: true }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)
        digit = cardinal.digit
        digits = digit + pynini.closure(insert_space + digit)
        separator = pynini.cross(pynini.union(" ", "-", "."), " ")
        groups = digits + pynini.closure(separator + digits)
        area = pynutil.delete("(") + digits + pynutil.delete(")") + pynini.closure(pynutil.delete(" "), 0, 1) + insert_space

        separators = pynini.union(" ", "-", ".", "(", ")")
        long_enough = pynini.closure(pynini.closure(separators) + NEMO_DIGIT, 7) + pynini.closure(separators)
        date_like = pynini.union(
            *[NEMO_DIGIT**2 + sep + NEMO_DIGIT**2 + sep + NEMO_DIGIT**4 for sep in ["/", "-", "."]]
        )
        local_input = pynini.difference(
            pynini.closure("(", 0, 1) + "0" + pynini.closure(NEMO_DIGIT | separators), date_like
        )
        local = (long_enough @ local_input) @ (pynini.closure(area, 0, 1) + groups)

        country_code = (
            pynutil.insert('country_code: "')
            + pynini.cross("+", "plus ")
            + (pynini.closure(NEMO_DIGIT, 1, 3) @ digits)
            + pynutil.insert('" ')
        )
        number_part = (
            pynutil.insert('number_part: "') + (long_enough @ (pynini.closure(area, 0, 1) + groups)) + pynutil.insert('"')
        )
        graph = country_code + pynutil.delete(pynini.union(" ", "-")) + number_part
        graph |= pynutil.insert('number_part: "') + local + pynutil.insert('"')
        graph += pynutil.insert(" preserve_order: true")
        self.fst = self.add_tokens(graph).optimize()
        self.fst = (self.fst | international_telephone_token(digit, "dagdag")).optimize()
