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
    GraphFst,
)


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying phone numbers in Slovak, e.g.
        +1 555 123 4567 -> plus jeden päť päť päť jeden dva tri štyri päť šesť sedem
        +421 905 123 456 -> plus štyristo dvadsaťjeden deväť nula päť jeden dva tri štyri päť šesť
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digit_words = pynini.string_map([
            ("0", "nula"),
            ("1", "jeden"),
            ("2", "dva"),
            ("3", "tri"),
            ("4", "štyri"),
            ("5", "päť"),
            ("6", "šesť"),
            ("7", "sedem"),
            ("8", "osem"),
            ("9", "deväť"),
        ])

        separator = pynini.closure(pynutil.delete(pynini.union(" ", "-")))
        local = digit_words + pynini.closure(separator + pynutil.insert(" ") + digit_words, 9, 9)
        self.fst = (international_telephone(digit_words, "plus") | local).optimize()
