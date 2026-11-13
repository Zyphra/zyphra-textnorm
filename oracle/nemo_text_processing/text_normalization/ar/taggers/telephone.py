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

from nemo_text_processing.text_normalization.ar.graph_utils import NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.ar.utils import get_abs_path


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying telephone numbers, read digit by digit; groups are separated by a space,
    "-" or "." and "+" is زائد, e.g.
        "+966 50 123 4567" -> telephone { country_code: "زائد تسعة ستة ستة" number_part: "خمسة صفر ..." preserve_order: true }
        "050-123-4567" -> telephone { number_part: "صفر خمسة صفر واحد ..." preserve_order: true }
    Without a country code the number must start with the trunk prefix 0 and have 9-12 digits, so that cardinals and
    dates stay what they are. An area code in brackets ("(021) 555-1234") is read the same way, brackets dropped.
    """

    def __init__(self):
        super().__init__(name="telephone", kind="classify")
        digit = pynini.string_file(get_abs_path("data/number/digit.tsv")) | pynini.string_file(
            get_abs_path("data/number/zero.tsv")
        )
        separator = pynini.union(" ", "-", ".")
        digits = digit + pynini.closure(pynini.closure(pynini.cross(separator, ""), 0, 1) + insert_space + digit)

        country_code = (
            pynutil.insert('country_code: "')
            + pynini.cross("+", "زائد ")
            + (NEMO_DIGIT ** (1, 3) @ digits)
            + pynutil.insert('"')
            + pynini.cross(pynini.union(" ", "-"), " ")
        )
        optional_separator = pynini.closure(separator, 0, 1)
        local_number = ("0" + (optional_separator + NEMO_DIGIT) ** (8, 11)) @ digits
        international_number = (NEMO_DIGIT + (optional_separator + NEMO_DIGIT) ** (3, 13)) @ digits

        graph = country_code + pynutil.insert('number_part: "') + international_number + pynutil.insert('"')
        graph |= pynutil.insert('number_part: "') + local_number + pynutil.insert('"')
        trunk_area = pynutil.delete("(") + ("0" + NEMO_DIGIT ** (1, 3)) @ digits + pynutil.delete(")")
        trunk_subscriber = (NEMO_DIGIT + (optional_separator + NEMO_DIGIT) ** (4, 7)) @ digits
        nanp_area = pynutil.delete("(") + (pynini.difference(NEMO_DIGIT, "0") + NEMO_DIGIT**2) @ digits + pynutil.delete(")")
        nanp_subscriber = ((NEMO_DIGIT**3 + pynini.union("-", " ", ".") + NEMO_DIGIT**4) | NEMO_DIGIT**7) @ digits
        area_join = pynini.cross(pynini.closure(pynini.union(" ", "-"), 0, 1), " ")
        graph |= (
            pynutil.insert('number_part: "')
            + (trunk_area + area_join + trunk_subscriber | nanp_area + area_join + nanp_subscriber)
            + pynutil.insert('"')
        )
        self.graph = graph.optimize()
        self.fst = self.add_tokens(self.graph + pynutil.insert(" preserve_order: true")).optimize()
