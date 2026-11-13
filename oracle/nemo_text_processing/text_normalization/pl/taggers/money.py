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
    convert_space,
)
from nemo_text_processing.text_normalization.pl.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.pl.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.pl.utils import get_abs_path, load_labels


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Polish currency expressions, e.g.
        "50 zł" -> "pięćdziesiąt złotych"
        "50zł" -> "pięćdziesiąt złotych"
        "1 zł" -> "jeden złoty"
        "2 zł" -> "dwa złote"
        "12,50 zł" -> "dwanaście złotych pięćdziesiąt groszy"
        "-12,50 €" -> "minus dwanaście euro pięćdziesiąt centów"
        "99,95 €" -> "dziewięćdziesiąt dziewięć euro dziewięćdziesiąt pięć centów"
        "$50" -> "pięćdziesiąt dolarów"
        "USD100" -> "sto dolarów"
        "CA$50" -> "pięćdziesiąt dolarów kanadyjskich"
        "$50k" -> "pięćdziesiąt tysięcy dolarów"
        "$2,5M" -> "dwa przecinek pięć miliona dolarów"
        "$15/h" -> "piętnaście dolarów za godzinę"
        "€20/kg" -> "dwadzieścia euro za kilogram"
        "10-20 zł" -> "dziesięć do dwudziestu złotych"
        "$10-$20" -> "dziesięć do dwudziestu dolarów"
        "$10-€20" -> "dziesięć dolarów do dwudziestu euro"
        "25¢" -> "dwadzieścia pięć centów"
    """

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        pn = cardinal.pn
        card_m = cardinal.graph_with_sep
        card_gen = cardinal.graph_genitive_with_sep
        currencies = load_labels(get_abs_path("data/money/currency.tsv"))

        # Build condition transducers for one, few, many
        # Digits ending condition
        not_one = pynini.difference(NEMO_DIGIT, "1")
        ending_one = pynini.accep("1")  # only bare 1 is 'one' in Polish noun agreement!
        ending_few_digit = pynini.union("2", "3", "4")
        any_num_char = NEMO_DIGIT | pynini.union(" ", "\u00a0", ".")
        num_prefix = pynini.closure(any_num_char)
        ending_few = (num_prefix + not_one + ending_few_digit) | ending_few_digit
        ending_many = pynini.difference(pynini.project(card_m, "input"), ending_one | ending_few).optimize()

        # Prefix sign: minus, approx, plus-minus
        prefix_sign = (
            pynini.cross(pynini.union("-", "−"), "minus ")
            | (pynini.cross("~", "około ") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "plus minus ") + pynini.closure(pynutil.delete(" "), 0, 1))
        )
        opt_prefix = pynini.closure(prefix_sign, 0, 1)

        # Rate suffixes (/h, /kg, /godz., etc.)
        per_unit = (
            pynini.cross(pynini.union("/h", "/godz.", "/godz"), " za godzinę")
            | pynini.cross("/kg", " za kilogram")
            | pynini.cross("/m", " za metr")
            | pynini.cross("/s", " za sekundę")
            | pynini.cross("/dzień", " za dzień")
            | pynini.cross("/miesiąc", " za miesiąc")
            | pynini.cross("/rok", " za rok")
            | pynini.cross("/os.", " za osobę")
            | pynini.cross("/osobę", " za osobę")
            | pynini.cross("/szt.", " za sztukę")
            | pynini.cross("/sztukę", " za sztukę")
        )
        opt_per_unit = pynini.closure(per_unit, 0, 1)

        # Magnitudes: k / tys., M / mln, mld
        mag_k = pynini.cross(pynini.union("k", " tys.", " tys"), " tysięcy")
        mag_m = pynini.cross(pynini.union("M", " mln.", " mln"), " miliona")
        mag_b = pynini.cross(pynini.union("B", " mld.", " mld"), " miliarda")
        shorthand_mag = (
            card_m + mag_k
            | decimal.graph + mag_m
            | card_m + mag_m
            | decimal.graph + mag_b
            | card_m + mag_b
        )

        # Bare cents: "25¢"
        cents_sym = pynini.cross("¢", "")
        cents_bare = opt_prefix + (
            (ending_one @ card_m) + cents_sym + pynutil.insert(" cent")
            | (ending_few @ card_m) + cents_sym + pynutil.insert(" centy")
            | (ending_many @ card_m) + cents_sym + pynutil.insert(" centów")
        )

        dash = pynini.union("-", "–", "—")
        range_to = pynini.cross(dash, " do ")

        all_cur_graphs = []
        positive_cur_graphs = []
        trailing_range_graphs = []
        repeated_lead_range_graphs = []
        single_lead_graphs = []
        single_lead_gen_graphs = []

        for row in currencies:
            if not row or len(row) < 7:
                continue
            sym, maj_one, maj_few, maj_many, min_one, min_few, min_many = row[:7]

            del_sym = pynutil.delete(sym)
            opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

            # Integer amounts
            card_one = (ending_one @ card_m) + pynutil.insert(" " + maj_one)
            card_few = (ending_few @ card_m) + pynutil.insert(" " + maj_few)
            card_many = (ending_many @ card_m) + pynutil.insert(" " + maj_many)
            int_amount = card_one | card_few | card_many

            # Positive non-zero integer amounts
            non_zero = (NEMO_DIGIT - "0") + pynini.closure(any_num_char)
            card_one_pos = (non_zero @ ending_one @ card_m) + pynutil.insert(" " + maj_one)
            card_few_pos = (non_zero @ ending_few @ card_m) + pynutil.insert(" " + maj_few)
            card_many_pos = (non_zero @ ending_many @ card_m) + pynutil.insert(" " + maj_many)
            int_amount_pos = card_one_pos | card_few_pos | card_many_pos

            # Decimal / Major+Minor amounts: e.g. "12,50", "12.50", "0,99"
            sep = pynutil.delete(pynini.union(",", "."))
            two_digits = NEMO_DIGIT**2
            cents_digits = two_digits @ (pynutil.delete("0") + NEMO_DIGIT | (NEMO_DIGIT - "0") + NEMO_DIGIT)

            cent_one = (cents_digits @ ending_one @ card_m) + pynutil.insert(" " + min_one)
            cent_few = (cents_digits @ ending_few @ card_m) + pynutil.insert(" " + min_few)
            cent_many = (cents_digits @ ending_many @ card_m) + pynutil.insert(" " + min_many)
            cents_all = cent_one | cent_few | cent_many

            # e.g. 12,50 -> dwanaście złotych pięćdziesiąt groszy
            major_and_minor = int_amount_pos + sep + pynutil.insert(" ") + cents_all
            # 10,00 -> dziesięć złotych (omit zero cents)
            major_zero_cents = pynutil.add_weight(int_amount_pos + sep + pynutil.delete("00"), -0.1)
            # 0,99 -> dziewięćdziesiąt dziewięć groszy
            zero_major = pynutil.add_weight(pynutil.delete(pynini.union("0", "00")) + sep + cents_all, -0.2)

            amounts = (
                shorthand_mag + pynutil.insert(" " + maj_many)
                | major_zero_cents
                | zero_major
                | major_and_minor
                | int_amount
            )

            # Leading symbol: "$50", "USD 100", "USD100"
            lead = del_sym + opt_space + amounts + opt_per_unit
            # Trailing symbol: "50 zł", "50zł", "100 USD"
            trail = amounts + opt_space + del_sym + opt_per_unit

            cur_pos = lead | trail
            positive_cur_graphs.append(cur_pos)
            all_cur_graphs.append(opt_prefix + cur_pos)

            # Ranges for this currency:
            # Trailing range: "10-20 zł" -> "dziesięć do dwudziestu złotych"
            cur_trail_range = (
                card_m
                + range_to
                + card_gen
                + opt_space
                + del_sym
                + pynutil.insert(" " + maj_many)
            )
            trailing_range_graphs.append(cur_trail_range)

            # Repeated leading range: "$10-$20" -> "dziesięć do dwudziestu dolarów"
            cur_rep_lead_range = (
                del_sym
                + opt_space
                + card_m
                + range_to
                + del_sym
                + opt_space
                + card_gen
                + pynutil.insert(" " + maj_many)
            )
            repeated_lead_range_graphs.append(cur_rep_lead_range)

            # Lead amount for mixed currencies: "$10" -> "dziesięć dolarów"
            lead_cur_pos = del_sym + opt_space + amounts
            single_lead_graphs.append(lead_cur_pos)

            # Lead genitive amount for mixed currencies: "€20" -> "dwudziestu euro"
            lead_cur_gen = del_sym + opt_space + card_gen + pynutil.insert(" " + maj_many)
            single_lead_gen_graphs.append(lead_cur_gen)

        combined_money = pynini.union(*all_cur_graphs)
        self.positive_fst = pynini.union(*positive_cur_graphs).optimize()

        trailing_ranges = pynini.union(*trailing_range_graphs)
        repeated_lead_ranges = pynini.union(*repeated_lead_range_graphs)

        # Mixed currency range: "$10-€20" -> "dziesięć dolarów do dwudziestu euro"
        any_lead = pynini.union(*single_lead_graphs)
        any_lead_gen = pynini.union(*single_lead_gen_graphs)
        mixed_lead_range = pynutil.add_weight(any_lead + range_to + any_lead_gen, 0.1)

        self.graph = (
            cents_bare
            | repeated_lead_ranges
            | trailing_ranges
            | mixed_lead_range
            | combined_money
        ).optimize()

        self.fst = (pynutil.insert("name: \"") + convert_space(self.graph) + pynutil.insert("\"")).optimize()
