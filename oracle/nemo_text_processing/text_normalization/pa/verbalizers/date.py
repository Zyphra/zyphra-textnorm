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

from nemo_text_processing.text_normalization.pa.graph_utils import NEMO_NOT_QUOTE, NEMO_SPACE, GraphFst, delete_space


class DateFst(GraphFst):
    """
    Finite state transducer for verbalizing date in Punjabi, e.g.
        date { day: "ਇੱਕ" month: "ਅਪ੍ਰੈਲ" year: "ਦੋ ਹਜ਼ਾਰ ਚੌਵੀ" } -> "ਇੱਕ ਅਪ੍ਰੈਲ ਦੋ ਹਜ਼ਾਰ ਚੌਵੀ"
        date { day: "ਇਕੱਤੀ" month: "ਮਈ" year: "ਇੱਕ ਹਜ਼ਾਰ ਨੌਂ ਸੌ ਨੱਬੇ" era: "ਈਸਵੀ" } -> "ਇਕੱਤੀ ਮਈ ਇੱਕ ਹਜ਼ਾਰ ਨੌਂ ਸੌ ਨੱਬੇ ਈਸਵੀ"

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self):
        super().__init__(name="date", kind="verbalize")

        day = pynutil.delete("day: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        month = pynutil.delete("month: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        year = pynutil.delete("year: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        graph_era = pynutil.delete("era: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        punjabi_months = [
            "ਜਨਵਰੀ", "ਫ਼ਰਵਰੀ", "ਮਾਰਚ", "ਅਪ੍ਰੈਲ", "ਮਈ", "ਜੂਨ",
            "ਜੁਲਾਈ", "ਅਗਸਤ", "ਸਤੰਬਰ", "ਅਕਤੂਬਰ", "ਨਵੰਬਰ", "ਦਸੰਬਰ"
        ]
        month_day_reorder = pynini.union(*[
            pynutil.delete(f'month: "{m}" ') + day + pynutil.insert(f" {m}")
            for m in punjabi_months
        ])

        graph_dd_mm = day + NEMO_SPACE + month
        graph_mm_dd = month_day_reorder
        graph_dd_mm_yyyy = day + NEMO_SPACE + month + NEMO_SPACE + year
        graph_mm_dd_yyyy = month_day_reorder + NEMO_SPACE + year
        graph_mm_yyyy = month + NEMO_SPACE + year

        era = pynutil.delete("era: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")
        optional_era = pynini.closure(delete_space + pynutil.insert(NEMO_SPACE) + era, 0, 1)

        optional_preserve_order = pynini.closure(
            pynutil.delete("preserve_order:") + delete_space + pynutil.delete("true") + delete_space
            | pynutil.delete("field_order:")
            + delete_space
            + pynutil.delete("\"")
            + NEMO_NOT_QUOTE
            + pynutil.delete("\"")
            + delete_space
        )

        final_graph = (
            optional_preserve_order
            + (
                (graph_dd_mm_yyyy | graph_mm_dd_yyyy | graph_mm_yyyy | graph_dd_mm | graph_mm_dd) + optional_era
                | year + optional_era
                | graph_era
            )
        )

        self.fst = self.delete_tokens(final_graph).optimize()
