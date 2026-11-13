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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ml.graph_utils import (
    MINUS,
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
    delete_space,
    insert_space,
)


class MoneyFst(GraphFst):
    """
    Finite state transducer for verbalizing money, e.g.
        money { currency_maj: "രൂപ" integer_part: "പത്ത്" } -> പത്ത് രൂപ
        money { currency_maj: "രൂപ" integer_part: "പന്ത്രണ്ട്" fractional_part: "അൻപത്" currency_min: "പൈസ" } -> പന്ത്രണ്ട് രൂപ അൻപത് പൈസ
        money { currency_maj: "രൂപ" integer_part: "പൂജ്യം" fractional_part: "എഴുപത്തിയഞ്ച്" currency_min: "പൈസ" } -> എഴുപത്തിയഞ്ച് പൈസ
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="money", kind="verbalize", deterministic=deterministic)

        sp = pynini.accep(NEMO_SPACE)
        optional_sign = pynini.closure(pynini.cross('negative: "true"', MINUS) + pynutil.delete(NEMO_SPACE), 0, 1)

        currencies = [
            "രൂപ", "ഡോളർ", "യൂറോ", "പൗണ്ട്", "യെൻ", "സ്വിസ് ഫ്രാങ്ക്",
            "കനേഡിയൻ ഡോളർ", "ഓസ്ട്രേലിയൻ ഡോളർ", "ബ്രസീലിയൻ റിയാൽ", "മെക്സിക്കൻ പെസോ",
            "റഷ്യൻ റൂബിൾ", "ദക്ഷിണ കൊറിയൻ വോൺ", "ടർക്കിഷ് ലിറ", "ഇസ്രായേലി ന്യൂ ഷെക്കെൽ",
            "ഉക്രേനിയൻ ഹ്രിവ്‌നിയ", "വിയറ്റ്നാമീസ് ഡോങ്", "ബംഗ്ലാദേശി ടാക്ക", "നൈജീരിയൻ നൈറ",
            "ഫിലിപ്പീനി പെസോ", "തായ് ബട്ട്", "അർമേനിയൻ ഡ്രാം", "സെന്റ്"
        ]

        currency_major = pynutil.delete('currency_maj: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        integer_part = pynutil.delete('integer_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        non_zero_int = (
            pynutil.delete('integer_part: "')
            + (pynini.closure(NEMO_NOT_QUOTE, 1) - pynini.accep("പൂജ്യം"))
            + pynutil.delete('"')
        )
        fractional_part = pynutil.delete('fractional_part: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')
        currency_minor = pynutil.delete('currency_min: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"')

        optional_per_unit = pynini.closure(
            delete_space + insert_space + pynutil.delete('morphosyntactic_features: "') + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete('"'),
            0,
            1,
        )

        # When integer is 0 (പൂജ്യം), speak only minor (₹0.75 -> എഴുപത്തിയഞ്ച് പൈസ)
        zero_int = pynutil.delete('integer_part: "പൂജ്യം"') + delete_space
        curr_maj_del = pynini.union(*[pynutil.delete(f'currency_maj: "{c}" ') for c in currencies])
        graph_minor_only = (
            (curr_maj_del + zero_int | zero_int + pynutil.delete(currency_major) + delete_space)
            + fractional_part
            + delete_space
            + insert_space
            + currency_minor
        )

        # Currency maj before integer_part (standard in ml tagger)
        graph_maj_first_both = pynini.union(*[
            pynutil.delete(f'currency_maj: "{c}" ')
            + non_zero_int
            + delete_space
            + pynutil.insert(f" {c} ")
            + fractional_part
            + delete_space
            + insert_space
            + currency_minor
            for c in currencies
        ])
        graph_maj_first_only = pynini.union(*[
            pynutil.delete(f'currency_maj: "{c}" ')
            + integer_part
            + pynutil.insert(f" {c}")
            for c in currencies
        ])

        # Currency maj after integer_part
        graph_int_first_both = (
            non_zero_int
            + sp
            + currency_major
            + sp
            + fractional_part
            + sp
            + currency_minor
        )
        graph_int_first_only = integer_part + sp + currency_major

        graph = optional_sign + (
            graph_minor_only
            | graph_maj_first_both
            | graph_maj_first_only
            | graph_int_first_both
            | graph_int_first_only
        ) + optional_per_unit

        self.fst = self.delete_tokens(graph).optimize()
