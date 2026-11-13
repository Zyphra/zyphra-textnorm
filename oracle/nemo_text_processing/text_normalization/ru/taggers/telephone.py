# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying telephone numbers. Each group of digits is read as a number, a leading zero
    as "ноль", a group of four digits as two pairs, e.g.
        "8-913-983-56-01" -> telephone { number_part: "восемь девятьсот тринадцать девятьсот восемьдесят три
            пятьдесят шесть ноль один" }
        "+1 555 123 4567" -> "плюс один пятьсот пятьдесят пять сто двадцать три сорок пять шестьдесят семь"
        "+7 (495) 123-45-67" -> "плюс семь четыреста девяносто пять сто двадцать три сорок пять шестьдесят семь"

    Args:
        number_names: number names built by number_names.get_number_names()
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, number_names: dict, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        number = number_names['cardinal']['masc']
        not_zero = pynini.difference(NEMO_DIGIT, "0")
        zero = pynini.cross("0", "ноль")

        def group(n):
            """n digits: "983" -> "девятьсот восемьдесят три", "01" -> "ноль один", "007" -> "ноль ноль семь"."""
            graph = pynini.compose(not_zero + NEMO_DIGIT ** (n - 1), number)
            for k in range(1, n):
                graph |= (zero + pynutil.insert(" ")) ** k + pynini.compose(not_zero + NEMO_DIGIT ** (n - 1 - k), number)
            graph |= (zero + pynutil.insert(" ")) ** (n - 1) + zero
            return graph.optimize()

        two, three = group(2), group(3)
        four = two + pynutil.insert(" ") + two
        part = two | three | four
        sep = pynini.cross(pynini.union("-", " ", "."), " ")

        country = pynini.cross("+", "плюс ") + pynini.compose(not_zero + NEMO_DIGIT**(0, 2), number)
        area = pynini.cross("(", "") + part + pynini.cross(")", "")
        # "+1 555 123 4567", "+7 (495) 123-45-67", "+44 20 7946 0958"
        international = country + sep + (area + pynini.accep(" ") | part + sep) + part + pynini.closure(sep + part, 1, 3)
        # "8-913-983-56-01", "(021) 555-1234", "8 (800) 555-35-35"
        first = pynini.compose(NEMO_DIGIT, number) + sep
        local = pynini.closure(first, 0, 1) + area + pynini.accep(" ") + part + pynini.closure(sep + part, 1, 3)
        dashes = pynini.cross("-", " ")
        local |= pynini.compose(NEMO_DIGIT, number) + dashes + three + dashes + three + dashes + two + dashes + two

        graph = (international | local).optimize()
        self.final_graph = graph
        self.fst = self.add_tokens(pynutil.insert("number_part: \"") + graph + pynutil.insert("\"")).optimize()
