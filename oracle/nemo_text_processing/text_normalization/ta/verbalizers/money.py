# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ta.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
)
from nemo_text_processing.text_normalization.ta.utils import get_abs_path, load_labels


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing money, e.g.
        money { currency_maj: "ரூபாய்" integer_part: "பன்னிரண்டு" } -> பன்னிரண்டு ரூபாய்
        money { currency_maj: "ரூபாய்" integer_part: "பன்னிரண்டு" fractional_part: "ஐம்பது" currency_min: "பைசா" } -> பன்னிரண்டு ரூபாய் ஐம்பது பைசா
        money { currency_maj: "ரூபாய்" integer_part: "பூஜ்யம்" fractional_part: "ஐம்பது" currency_min: "பைசா" } -> ஐம்பது பைசா
        money { morphosyntactic_features: "ஒரு மணிநேரத்திற்கு" integer_part: "பதினைந்து" currency_maj: "டாலர்" } -> ஒரு மணிநேரத்திற்கு பதினைந்து டாலர்
    """

    def __init__(self):
        super().__init__(name="money", kind="verbalize")

        sp = pynini.accep(NEMO_SPACE)
        optional_per_unit = pynini.closure(
            pynutil.delete('morphosyntactic_features: "')
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"')
            + pynutil.delete(NEMO_SPACE)
            + pynutil.insert(NEMO_SPACE),
            0,
            1,
        )
        optional_sign = pynini.closure(pynini.cross('negative: "true"', MINUS) + pynutil.delete(NEMO_SPACE), 0, 1)
        currency_major = pynutil.delete('currency_maj: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        integer_part = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        fractional_part = (
            pynutil.delete('fractional_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        )

        currency_minor = pynutil.delete('currency_min: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        graph_major_only = integer_part + sp + currency_major

        all_major_names = list(
            dict.fromkeys(
                [maj for _, maj in load_labels(get_abs_path("data/money/currency.tsv"))]
                + [maj for _, maj in load_labels(get_abs_path("data/money/currency_singular.tsv"))]
                + [maj for maj, _ in load_labels(get_abs_path("data/money/major_minor_currencies.tsv"))]
                + ["அமெரிக்க டாலர்"]
            )
        )
        major_minor_graphs = []
        minor_only_graphs = []

        for major in all_major_names:
            graph_major_slot = pynutil.delete('currency_maj: "') + pynutil.delete(major) + pynutil.delete('"')

            major_minor_graphs.append(
                graph_major_slot
                + pynutil.delete(NEMO_SPACE)
                + integer_part
                + pynutil.insert(NEMO_SPACE)
                + pynutil.insert(major)
                + sp
                + fractional_part
                + sp
                + currency_minor
            )

            minor_only_graphs.append(
                graph_major_slot
                + pynutil.delete(NEMO_SPACE)
                + pynutil.delete('integer_part: "பூஜ்யம்"')
                + pynutil.delete(NEMO_SPACE)
                + fractional_part
                + sp
                + currency_minor
            )

        graph_major_minor = pynini.union(*major_minor_graphs)
        graph_minor_only = pynini.union(*minor_only_graphs)

        decimal_graphs = []
        for major in all_major_names:
            decimal_graphs.append(
                pynutil.delete('currency_maj: "')
                + pynutil.delete(major)
                + pynutil.delete('"')
                + pynutil.delete(NEMO_SPACE)
                + integer_part
                + sp
                + pynutil.insert(" புள்ளி ")
                + fractional_part
                + pynutil.insert(NEMO_SPACE)
                + pynutil.insert(major)
            )
        graph_decimal_money = pynini.union(*decimal_graphs)

        body = graph_major_only | graph_major_minor | pynutil.add_weight(graph_minor_only, -0.1) | graph_decimal_money
        per_unit_words = [
            "மணிக்கு",
            "ஒரு மணிநேரத்திற்கு",
            "ஒரு கிலோவிற்கு",
            "ஒரு நாளைக்கு",
            "ஒரு மாதத்திற்கு",
            "ஒரு வருடத்திற்கு",
            "ஒரு ஆண்டிற்கு",
            "ஒரு மீட்டருக்கு",
            "ஒரு கிலோமீட்டருக்கு",
        ]
        suf_per_unit_graphs = [
            pynutil.insert(w + " ") + body + pynutil.delete(f' morphosyntactic_features: "{w}"')
            for w in per_unit_words
        ]
        graph = optional_sign + (
            (optional_per_unit + body) | pynini.union(*suf_per_unit_graphs)
        )

        self.fst = self.delete_tokens(graph).optimize()
