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

from nemo_text_processing.text_normalization.ur.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
)
from nemo_text_processing.text_normalization.ur.utils import get_abs_path, load_labels


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing money, e.g.
        money { currency_maj: "روپے" integer_part: "بارہ" } } -> بارہ روپے
        money { currency_maj: "روپے" integer_part: "بارہ" fractional_part: "پچاس" currency_min: "پیسے" } -> بارہ روپے پچاس پیسے
        money { currency_maj: "روپے" integer_part: "صفر" fractional_part: "پچاس" currency_min: "پیسے" } -> پچاس پیسے

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self):
        super().__init__(name="money", kind="verbalize")

        sp = pynini.accep(NEMO_SPACE)
        delete_sp = pynutil.delete(NEMO_SPACE)

        currency_major = pynutil.delete('currency_maj: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        integer_part = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        fractional_part = (
            pynutil.delete('fractional_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        )

        currency_minor = pynutil.delete('currency_min: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        graph_major_only = integer_part + sp + currency_major

        # Keep exact word order: "<integer_part> <currency_maj> <fractional_part> <currency_min>"
        all_major_names = list(
            dict.fromkeys(
                [maj for _, maj in load_labels(get_abs_path("data/money/currency.tsv"))]
                + [maj for _, maj in load_labels(get_abs_path("data/money/currency_singular.tsv"))]
                + [maj for maj, _ in load_labels(get_abs_path("data/money/major_minor_currencies.tsv"))]
            )
        )
        major_minor_graphs = []
        minor_only_graphs = []
        decimal_graphs = []

        for major in all_major_names:
            graph_major_slot = pynutil.delete(f'currency_maj: "{major}"')

            major_minor_graphs.append(
                graph_major_slot
                + delete_sp
                + integer_part
                + pynutil.insert(f" {major}")
                + sp
                + fractional_part
                + sp
                + currency_minor
            )

            minor_only_graphs.append(
                graph_major_slot
                + delete_sp
                + pynutil.delete('integer_part: "صفر"')
                + delete_sp
                + fractional_part
                + sp
                + currency_minor
            )

            decimal_graphs.append(
                graph_major_slot
                + delete_sp
                + integer_part
                + delete_sp
                + pynutil.insert(" اعشاریہ ")
                + fractional_part
                + pynutil.insert(f" {major}")
            )

        graph_major_minor = pynini.union(*major_minor_graphs).optimize()
        graph_minor_only = pynini.union(*minor_only_graphs).optimize()
        graph_decimal_money = pynini.union(*decimal_graphs).optimize()
        optional_per_unit = pynini.closure(
            delete_sp
            + pynutil.insert(NEMO_SPACE)
            + pynutil.delete('morphosyntactic_features: "')
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete('"'),
            0,
            1,
        )

        optional_sign = pynini.closure(pynini.cross('negative: "true" ', MINUS), 0, 1)
        core = (
            graph_major_only | graph_major_minor | pynutil.add_weight(graph_minor_only, -0.1) | graph_decimal_money
        )
        graph = optional_sign + core + optional_per_unit
        self.fst = self.delete_tokens(graph).optimize()
