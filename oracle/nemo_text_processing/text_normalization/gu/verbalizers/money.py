# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.gu.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
)
from nemo_text_processing.text_normalization.gu.utils import get_abs_path, load_labels


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing money in Gujarati, e.g.
        money { currency_maj: "રૂપિયા" integer_part: "બાર" } } -> બાર રૂપિયા
        money { currency_maj: "રૂપિયો" integer_part: "એક" } } -> એક રૂપિયો
        money { currency_maj: "રૂપિયા" integer_part: "બાર" fractional_part: "પચાસ" currency_min: "પૈસા" } -> બાર રૂપિયા પચાસ પૈસા
        money { currency_maj: "રૂપિયા" integer_part: "શૂન્ય" fractional_part: "પચાસ" currency_min: "પૈસા" } -> પચાસ પૈસા
    """

    def __init__(self):
        super().__init__(name="money", kind="verbalize")

        sp = pynini.accep(NEMO_SPACE)
        optional_sign = pynini.closure(
            (
                pynini.cross('negative: "true"', MINUS)
                | (
                    pynutil.delete('negative: "')
                    + pynini.difference(pynini.closure(NEMO_NOT_QUOTE, 1), "true")
                    + pynutil.delete('"')
                    + pynutil.insert(NEMO_SPACE)
                )
            )
            + pynutil.delete(NEMO_SPACE),
            0,
            1,
        )

        currency_major = pynutil.delete('currency_maj: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        integer_part = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        fractional_part = (
            pynutil.delete('fractional_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        )
        currency_minor = pynutil.delete('currency_min: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        per_unit = (
            pynutil.delete('morphosyntactic_features: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        )
        optional_per = pynini.closure(sp + per_unit, 0, 1)

        graph_major_only = integer_part + sp + currency_major

        all_major_names = [maj for maj, _ in load_labels(get_abs_path("data/money/major_minor_currencies.tsv"))]

        major_minor_graphs = []
        decimal_graphs = []

        for major in all_major_names:
            graph_major_slot = pynutil.delete(f'currency_maj: "{major}"') + pynutil.delete(NEMO_SPACE)

            major_minor_graphs.append(
                graph_major_slot
                + integer_part
                + pynutil.insert(f" {major}")
                + sp
                + fractional_part
                + sp
                + currency_minor
            )

            decimal_graphs.append(
                graph_major_slot
                + integer_part
                + pynutil.delete(NEMO_SPACE)
                + pynutil.insert(" દશાંશ ")
                + fractional_part
                + pynutil.insert(f" {major}")
            )

        graph_major_minor = pynini.union(*major_minor_graphs).optimize()
        graph_decimal_money = pynini.union(*decimal_graphs).optimize()

        graph_minor_only = (
            pynutil.delete('currency_maj: "')
            + pynutil.delete(pynini.closure(NEMO_NOT_QUOTE, 1))
            + pynutil.delete('"')
            + pynutil.delete(NEMO_SPACE)
            + pynutil.delete('integer_part: "શૂન્ય"')
            + pynutil.delete(NEMO_SPACE)
            + fractional_part
            + sp
            + currency_minor
        ).optimize()

        graph = (
            optional_sign
            + (graph_major_only | graph_major_minor | pynutil.add_weight(graph_minor_only, -0.1) | graph_decimal_money)
            + optional_per
        )

        self.fst = self.delete_tokens(graph).optimize()
