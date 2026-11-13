# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.gu.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
)


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing date in day month year order in Gujarati, e.g.
        date { day: "એક" month: "એપ્રિલ" year: "બે હજાર ચોવીસ" } -> એક એપ્રિલ બે હજાર ચોવીસ
        date { month: "જાન્યુઆરી" year: "એક હજાર નવસો નેવું" era: "ઈસવીસન" } -> જાન્યુઆરી એક હજાર નવસો નેવું ઈસવીસન
    """

    def __init__(self):
        super().__init__(name="date", kind="verbalize")

        def field(name):
            return pynutil.delete(f"{name}: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        day, month, year, era = field("day"), field("month"), field("year"), field("era")
        sep = delete_space + pynutil.insert(" ")
        optional_era = pynini.closure(sep + era, 0, 1)

        self.graph = (
            (day + sep + month + sep + year + optional_era)
            | (day + sep + month)
            | (month + sep + year + optional_era)
            | (year + optional_era)
            | (era + sep + year + delete_space + pynutil.delete("preserve_order: true"))
        )
        self.fst = self.delete_tokens(self.graph + delete_space).optimize()
