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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.ka.graph_utils import with_suffix
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, e.g.
        "15 $" -> money { integer_part: "თხუთმეტი" currency: "დოლარი" }
        "£50" -> money { currency: "გირვანქა სტერლინგი" integer_part: "ორმოცდაათი" }
        "10,00 €" -> money { integer_part: "ათი" currency: "ევრო" }
        "10,50 ₾" -> money { integer_part: "ათი" currency_maj: "ლარი" fractional_part: "ორმოცდაათი" currency_min: "თეთრი" }
        "1500 AMD" -> money { integer_part: "ათას ხუთასი" currency: "დრამი" }
        "$50k" -> money { integer_part: "ორმოცდაათი ათასი" currency: "დოლარი" }
        "$15/h" -> money { integer_part: "თხუთმეტი" currency: "დოლარი" morphosyntactic_features: "საათში" }
        "€20/kg" -> money { integer_part: "ოცი" currency: "ევრო" morphosyntactic_features: "კილოგრამზე" }
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)
        cardinal_nums = cardinal.all_nums_no_tokens
        range_nums = cardinal.range_graph

        group_sep = pynini.union(" ", "\u00a0", ",", ".")
        comma_grouped = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(group_sep) + NEMO_DIGIT ** 3, 1)
        )
        amount_int = (cardinal_nums | pynutil.add_weight(pynini.compose(comma_grouped, cardinal_nums), 0.02)).optimize()

        # Zero fractional cents (",00" / ".00") are silent on money amounts: "10,00 €" -> "ათი ევრო"
        zero_cents = pynutil.delete(pynini.union(",", ".") + "00")
        cardinal_amount = (
            pynutil.insert('integer_part: "')
            + (amount_int | range_nums)
            + pynini.closure(zero_cents, 0, 1)
            + pynutil.insert('"')
        )

        comma_dec_fractional = (
            pynini.closure(pynini.cross("0", "ნული "), 0, 5)
            + ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 5)) @ cardinal_nums
        ) | pynini.cross("0", "ნული")
        comma_grouped_decimal = (
            pynutil.insert('integer_part: "')
            + pynini.compose(comma_grouped, cardinal_nums)
            + pynutil.insert('" ')
            + pynutil.delete(pynini.union(".", ","))
            + pynutil.insert('fractional_part: "')
            + comma_dec_fractional
            + pynutil.insert('"')
        )
        decimal_amount = decimal.final_graph_wo_negative | pynutil.add_weight(comma_grouped_decimal, 0.02)

        # Magnitude shorthand: "$50k", "€50k", "$2,5M", "$1.2B"
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        mag_k = pynini.union("k", "K")
        mag_mb = pynini.string_map([("M", "მილიონი"), ("B", "მილიარდი")])
        k_int_num = pynini.cross("1", "ათასი") | (
            ((pynini.closure(NEMO_DIGIT, 1, 6) - "1") @ cardinal_nums) + pynutil.insert(" ათასი")
        )
        shorthand_k_int = (
            pynutil.insert('integer_part: "') + k_int_num + opt_space + pynutil.delete(mag_k) + pynutil.insert('"')
        )
        shorthand_mb_int = (
            pynutil.insert('integer_part: "')
            + (pynini.closure(NEMO_DIGIT, 1, 6) @ cardinal_nums)
            + pynutil.insert('" quantity: "')
            + opt_space
            + mag_mb
            + pynutil.insert('"')
        )
        shorthand_mb_dec = (
            pynutil.insert('integer_part: "')
            + (pynini.closure(NEMO_DIGIT, 1, 6) @ cardinal_nums)
            + pynutil.insert('" fractional_part: "')
            + pynutil.delete(pynini.union(".", ","))
            + comma_dec_fractional
            + pynutil.insert('" quantity: "')
            + opt_space
            + mag_mb
            + pynutil.insert('"')
        )
        shorthand = shorthand_k_int | shorthand_mb_int | shorthand_mb_dec

        curr_labels = []
        with open(get_abs_path("data/currency.tsv"), encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    curr_labels.append((parts[0], parts[1]))

        minor_labels = {}
        with open(get_abs_path("data/currency_minor.tsv"), encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    minor_labels[parts[0]] = parts[1]

        # Per-unit suffix: "$15/h" -> საათში, "€20/kg" -> კილოგრამზე
        per_unit = pynutil.delete("/") + pynutil.insert('morphosyntactic_features: "') + (
            pynini.string_map([
                ("h", "საათში"),
                ("hr", "საათში"),
                ("საათი", "საათში"),
                ("სთ", "საათში"),
                ("kg", "კილოგრამზე"),
                ("კგ", "კილოგრამზე"),
                ("m", "მეტრზე"),
                ("მ", "მეტრზე"),
                ("km", "კილომეტრზე"),
                ("კმ", "კილომეტრზე"),
                ("month", "თვეში"),
                ("თვე", "თვეში"),
                ("year", "წელიწადში"),
                ("წელი", "წელიწადში"),
                ("d", "დღეში"),
                ("დღე", "დღეში"),
            ])
        ) + pynutil.insert('"')
        opt_per_unit = pynini.closure(pynini.accep(" ") | pynutil.delete(" "), 0, 1) + per_unit
        opt_per = pynini.closure(pynutil.insert(" ") + opt_per_unit, 0, 1)

        # Major & Minor currency
        two_digit_cents = (NEMO_DIGIT ** 2) @ cardinal_nums

        maj_min_post_list = []
        maj_min_pre_list = []
        zero_maj_post_list = []
        zero_maj_pre_list = []

        for sym, maj in curr_labels:
            if sym in minor_labels:
                min_name = minor_labels[sym]
                sym_esc = pynini.escape(sym)
                sym_post = pynini.accep(sym_esc) | with_suffix(pynini.accep(sym_esc))

                # Postfix: "10,50 ₾" -> integer_part: "ათი" currency_maj: "ლარი" fractional_part: "ორმოცდაათი" currency_min: "თეთრი"
                mm_post = (
                    pynutil.insert('integer_part: "')
                    + amount_int
                    + pynutil.insert(f'" currency_maj: "{maj}" fractional_part: "')
                    + pynutil.delete(pynini.union(".", ","))
                    + two_digit_cents
                    + pynutil.insert(f'" currency_min: "{min_name}"')
                    + opt_space
                    + pynutil.delete(sym_post)
                    + opt_per
                )
                maj_min_post_list.append(mm_post)

                # Prefix: "-$12.50" -> integer_part: "თორმეტი" currency_maj: "დოლარი" fractional_part: "ორმოცდაათი" currency_min: "ცენტი"
                mm_pre = (
                    pynutil.delete(pynini.accep(sym_esc))
                    + opt_space
                    + pynutil.insert('integer_part: "')
                    + amount_int
                    + pynutil.insert(f'" currency_maj: "{maj}" fractional_part: "')
                    + pynutil.delete(pynini.union(".", ","))
                    + two_digit_cents
                    + pynutil.insert(f'" currency_min: "{min_name}"')
                    + opt_per
                )
                maj_min_pre_list.append(mm_pre)

                # Postfix zero-major: "0,99 €" -> fractional_part: "ოთხმოცდაცხრამეტი" currency_min: "ცენტი"
                zm_post = (
                    pynutil.delete("0")
                    + pynutil.delete(pynini.union(".", ","))
                    + pynutil.insert('fractional_part: "')
                    + two_digit_cents
                    + pynutil.insert(f'" currency_min: "{min_name}"')
                    + opt_space
                    + pynutil.delete(sym_post)
                    + opt_per
                )
                zero_maj_post_list.append(zm_post)

                # Prefix zero-major: "$0.99"
                zm_pre = (
                    pynutil.delete(pynini.accep(sym_esc))
                    + opt_space
                    + pynutil.delete("0")
                    + pynutil.delete(pynini.union(".", ","))
                    + pynutil.insert('fractional_part: "')
                    + two_digit_cents
                    + pynutil.insert(f'" currency_min: "{min_name}"')
                    + opt_per
                )
                zero_maj_pre_list.append(zm_pre)

        maj_min_post = pynini.union(*maj_min_post_list).optimize()
        maj_min_pre = pynini.union(*maj_min_pre_list).optimize()
        zero_maj_post = pynini.union(*zero_maj_post_list).optimize()
        zero_maj_pre = pynini.union(*zero_maj_pre_list).optimize()

        currency_graph = pynini.string_file(get_abs_path("data/currency.tsv"))
        currency_graph = (currency_graph | with_suffix(currency_graph)).optimize()
        currency_tag = pynutil.insert('currency: "') + currency_graph + pynutil.insert('"')

        minor_currency_graph = pynini.string_file(get_abs_path("data/currency_minor.tsv"))
        minor_currency_graph = (minor_currency_graph | with_suffix(minor_currency_graph)).optimize()
        currency_min_tag = pynutil.insert('currency_min: "') + minor_currency_graph + pynutil.insert('"')

        # Cents only: "25¢" -> "ოცდახუთი ცენტი"
        cents_num = (pynini.closure(NEMO_DIGIT, 1, 2) @ cardinal_nums)
        cents_only_direct = (
            pynutil.insert('fractional_part: "')
            + cents_num
            + pynutil.insert('" ')
            + currency_min_tag
        )

        optional_negative = pynini.closure(
            pynini.cross("-", 'negative: "true" ') | pynini.cross("−", 'negative: "true" '),
            0,
            1,
        )

        # Combinations:
        # 1. Prefix currency: "$15", "€ 99.95", "£50k"
        prefix_curr = currency_tag + opt_space + pynutil.insert(" ")
        prefix_graph = (
            pynutil.add_weight(maj_min_pre, -0.05)
            | pynutil.add_weight(zero_maj_pre, -0.05)
            | (prefix_curr + (cardinal_amount | decimal_amount | shorthand) + opt_per)
        )

        # 2. Postfix currency: "15 $", "99,95 €", "50 ₾", "1500 AMD"
        postfix_graph = (
            pynutil.add_weight(maj_min_post, -0.05)
            | pynutil.add_weight(zero_maj_post, -0.05)
            | cents_only_direct
            | ((cardinal_amount | decimal_amount | shorthand) + opt_space + pynutil.insert(" ") + currency_tag + opt_per)
        )

        final_graph = optional_negative + (prefix_graph | postfix_graph)
        self.final_graph = final_graph.optimize()
        self.fst = self.add_tokens(self.final_graph).optimize()
