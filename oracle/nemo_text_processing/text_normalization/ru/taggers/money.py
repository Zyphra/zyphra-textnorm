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
from nemo_text_processing.text_normalization.ru.taggers.units import (
    MARK,
    UNIT_SPACE,
    agreement,
    attach,
    form_map,
    load_currencies,
    load_units,
    per_unit,
    quantity_nouns,
)

_PER_MONEY_EXTRA = [
    ("/ч", "в час"),
    ("/h", "в час"),
    ("/hr", "в час"),
    ("/час", "в час"),
    ("/мин", "в минуту"),
    ("/min", "в минуту"),
    ("/с", "в секунду"),
    ("/сек", "в секунду"),
    ("/s", "в секунду"),
    ("/sec", "в секунду"),
    ("/д", "в день"),
    ("/день", "в день"),
    ("/сут", "в сутки"),
    ("/сутки", "в сутки"),
    ("/d", "в день"),
    ("/day", "в день"),
    ("/нед", "в неделю"),
    ("/wk", "в неделю"),
    ("/мес", "в месяц"),
    ("/мес.", "в месяц"),
    ("/mo", "в месяц"),
    ("/год", "в год"),
    ("/г", "в год"),
    ("/yr", "в год"),
    ("/чел", "на человека"),
    ("/чел.", "на человека"),
    ("/шт", "за штуку"),
    ("/шт.", "за штуку"),
]

_GENITIVE_PREPS = pynini.union(
    "около",
    "Около",
    "более",
    "Более",
    "менее",
    "Менее",
    "больше",
    "Больше",
    "меньше",
    "Меньше",
    "свыше",
    "Свыше",
    "порядка",
    "Порядка",
    "до",
    "До",
    "от",
    "От",
).optimize()


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, e.g.
        "5 руб." -> money { integer_part: "пять рублей" }
        "6 руб. 35 коп." -> money { integer_part: "шесть рублей тридцать пять копеек" }
        "$7.50" -> money { currency: "$" integer_part: "семь"+M fractional_part: "пятьдесят"+M preserve_order: true }
        "$50k" -> money { currency: "$" integer_part: "пятьдесят тысяч"+M preserve_order: true }
        "$2,5M" -> money { currency: "$" integer_part: "две целых пять десятых миллиона"+M preserve_order: true }
        "10-20 €" -> money { integer_part: "от десяти до двадцати евро" }
        "$15/h" -> money { currency: "$" integer_part: "пятнадцать"+M morphosyntactic_features: "в час" preserve_order: true }
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        major, minor, written_minor = load_currencies()
        quantities = quantity_nouns()
        units = load_units()

        decimal_number = decimal.integer_part + pynini.cross(",", " ") + decimal.graph_fractional
        point_decimal_number = (
            pynini.compose(pynini.closure(NEMO_DIGIT, 1, 3), decimal.integer_part)
            + pynini.cross(".", " ")
            + decimal.graph_fractional
        )
        any_decimal_number = decimal_number | pynutil.add_weight(point_decimal_number, 0.05)

        whole = pynini.compose(
            NEMO_DIGIT + pynini.closure(NEMO_DIGIT | (pynini.union(" ", ".", ",", "\u00a0") + NEMO_DIGIT**3)),
            cardinal.marked,
        ).optimize()
        cents = pynini.compose(pynini.difference(NEMO_DIGIT**2, "00"), cardinal.marked).optimize()

        # Shorthand k/K, M, B ("$50k", "€50k", "$2,5M", "$1.2B")
        shorthand_nouns = [
            n
            for q in quantities
            for sym, target in [
                ("k", "тыс"),
                ("K", "тыс"),
                ("к", "тыс"),
                ("К", "тыс"),
                ("M", "млн"),
                ("B", "млрд"),
                ("bn", "млрд"),
            ]
            if q.written == target
            for n in [type(q)(sym, q.gender, q.forms["one"], q.forms["few"], q.forms["many"], q.forms["gen"])]
        ]
        shorthand_amount = (
            cardinal.counted(shorthand_nouns, UNIT_SPACE) + pynutil.insert(MARK["many"])
            | any_decimal_number + UNIT_SPACE + form_map(shorthand_nouns, "gen") + pynutil.insert(MARK["many"])
        ).optimize()

        # The amount with the marker of the form the currency takes: "5", "2,03", "1,23 млрд", "2 тыс", "50k", "2,5M".
        whole_zero_cents = (whole + pynutil.delete(pynini.union(".00", ",00"))).optimize()
        amount = (
            whole
            | pynutil.add_weight(whole_zero_cents, -0.05)
            | decimal_number + pynutil.insert(MARK["gen"])
            | cardinal.counted(quantities, UNIT_SPACE) + pynutil.insert(MARK["many"])
            | decimal_number + UNIT_SPACE + form_map(quantities, "gen") + pynutil.insert(MARK["many"])
            | pynutil.add_weight(shorthand_amount, -0.02)
        ).optimize()

        # Optional per-unit rate ("/h" -> " в час", "/kg" -> " за килограмм" or " на килограмм")
        money_per_pairs = list(_PER_MONEY_EXTRA)
        seen_per = {w for w, _ in money_per_pairs}
        for u in units:
            key = "/" + u.written
            if key not in seen_per:
                money_per_pairs.append((key, "за " + u.forms["acc"]))
                seen_per.add(key)
        rate_str = pynini.string_map(money_per_pairs).optimize()
        opt_rate_inline = pynini.closure(pynutil.insert(" ") + rate_str, 0, 1)

        # Prefix sign / approximate / plus-minus
        opt_sign_inline = pynini.closure(
            pynini.cross("-", "минус ")
            | (pynini.cross("~", "около ") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "плюс-минус ") + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )

        # "~500 руб." / "около 500 руб." -> genitive: "около пятисот рублей"
        _approx_prefix = (pynini.cross("~", "около ") + pynini.closure(pynutil.delete(" "), 0, 1)) | (
            _GENITIVE_PREPS + pynini.accep(" ")
        )
        approx_gen_spoken = (
            _approx_prefix
            + attach(cardinal.genitive_marked, agreement(major, UNIT_SPACE, tail_only=True))
            + opt_rate_inline
        )

        # Money ranges: "10-20 €", "$10-$20", "10–20 руб."
        range_sep = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynini.cross(pynini.union("-", "–"), " до ")
            + pynini.closure(pynutil.delete(" "), 0, 1)
        )
        trailing_range = (
            pynutil.insert("от ")
            + cardinal.range_genitive
            + range_sep
            + attach(cardinal.range_genitive_marked, agreement(major, UNIT_SPACE, tail_only=True))
            + opt_rate_inline
        )

        # Leading currency ranges: "$10-$20" or "$10-20" -> "от десяти до двадцати долларов"
        leading_ranges = []
        for symbol in sorted({n.written for n in major}):
            sym_esc = pynini.escape(symbol)
            maj_group = [n for n in major if n.written == symbol]
            opt_second_sym = pynini.closure(pynutil.delete(sym_esc) + pynini.closure(pynutil.delete(" "), 0, 1), 0, 1)
            lead_r = (
                pynutil.delete(sym_esc)
                + pynini.closure(pynutil.delete(" "), 0, 1)
                + pynutil.insert("от ")
                + cardinal.range_genitive
                + range_sep
                + opt_second_sym
                + pynini.compose(
                    cardinal.range_genitive_marked + pynutil.insert(symbol),
                    agreement(maj_group, pynutil.insert(" "), tail_only=True),
                )
                + opt_rate_inline
            )
            leading_ranges.append(lead_r)
        leading_range = pynini.union(*leading_ranges).optimize()

        # amount, then the currency: "5 руб.", "2,03 руб.", "1,23 млрд руб."; "6 руб. 35 коп.", "35 коп.", "25¢"
        spoken = opt_sign_inline + attach(amount, agreement(major, UNIT_SPACE)) + opt_rate_inline
        minor_written = cardinal.counted(written_minor, UNIT_SPACE)
        spoken |= opt_sign_inline + attach(whole, agreement(major, UNIT_SPACE)) + pynini.accep(" ") + minor_written
        spoken |= opt_sign_inline + minor_written
        spoken |= pynutil.add_weight(approx_gen_spoken, -0.05)
        spoken |= trailing_range | leading_range
        graph = pynutil.insert("integer_part: \"") + spoken + pynutil.insert("\"")

        def field(name, value):
            return pynutil.insert(f"{name}: \"") + value + pynutil.insert("\"")

        opt_neg_field = pynini.closure(
            pynini.cross("-", "negative: \"минус\" ")
            | (pynini.cross("~", "negative: \"приблизительно\" ") + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", "negative: \"плюс-минус\" ") + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )
        opt_rate_field = pynini.closure(pynutil.insert(" ") + field("morphosyntactic_features", rate_str), 0, 1)

        currency = pynini.union(*[pynini.escape(w) for w in sorted({n.written for n in major})])
        minor_currency = pynini.union(*[pynini.escape(w) for w in sorted({n.written for n in minor})])
        with_cents = (
            field("integer_part", whole)
            + pynini.cross(pynini.union(".", ","), " ")
            + field("fractional_part", cents)
        )
        # "$7", "€ 2,5 млн", "$7.50", "-$12.50", "-12,50 €", "$15/h", "€20/kg"
        before = pynutil.delete(pynini.closure(" ", 0, 1)) + pynutil.insert(" ")
        order = pynutil.insert(" preserve_order: true")
        graph |= opt_neg_field + field("currency", currency) + before + field("integer_part", amount) + opt_rate_field + order
        graph |= opt_neg_field + field("currency", minor_currency) + before + with_cents + opt_rate_field + order
        graph |= (
            opt_neg_field
            + (with_cents | pynutil.add_weight(field("integer_part", whole_zero_cents), -0.05))
            + pynini.cross(pynini.closure(" ", 0, 1), " ")
            + field("currency", minor_currency)
            + opt_rate_field
            + order
        )

        self.fst = self.add_tokens(graph.optimize()).optimize()
