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

from collections import defaultdict

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_TE_DIGIT,
    NEMO_TE_NON_ZERO,
    TO_ASCII_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.te.utils import get_abs_path, load_labels

currency_graph = pynini.string_file(get_abs_path("data/money/currency.tsv"))
currency_singular_graph = pynini.string_file(get_abs_path("data/money/currency_singular.tsv"))


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, suppletive aware, e.g.
        ₹50 -> money { currency_maj: "రూపాయలు" integer_part: "యాభై" }
        ₹50.50 -> money { currency_maj: "రూపాయలు" integer_part: "యాభై" fractional_part: "యాభై" currency_min: "పైసలు" }
        ₹0.50 -> money { currency_maj: "రూపాయలు" integer_part: "సున్నా" fractional_part: "యాభై" currency_min: "పైసలు" }
        $50k -> money { currency_maj: "డాలర్లు" integer_part: "యాభై వేల" }
        $2.5M -> money { currency_maj: "డాలర్లు" integer_part: "రెండు దశాంశం ఐదు మిలియన్" }
        $15/h -> money { currency_maj: "డాలర్లు" integer_part: "పదిహేను" morphosyntactic_features: "గంటకు" }
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="money", kind="classify")

        cardinal_graph = cardinal.attributive_graph

        deva_to_ascii = pynini.closure(TO_ASCII_DIGIT, 1)

        _ascii_digit = pynini.union(*"0123456789")
        _ascii_nonzero = pynini.union(*"123456789")
        _any_digit = _ascii_digit | NEMO_TE_DIGIT
        _any_nonzero = _ascii_nonzero | NEMO_TE_NON_ZERO

        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", '"true"') + insert_space,
            0,
            1,
        )

        # "Rs 500" / "Rs. 500" / "₹ 500" / "500 USD": an optional space between the currency and the amount
        optional_space = pynini.closure(pynutil.delete(" "), 0, 1)

        # Prefix USD/US$ reads as "అమెరికన్ డాలర్లు" ("USD100" -> "వంద అమెరికన్ డాలర్లు"), while suffix "500 USD"
        # keeps "డాలర్లు" from currency.tsv.
        prefix_usd_plural = pynini.string_map([("USD", "అమెరికన్ డాలర్లు"), ("US$", "అమెరికన్ డాలర్లు")])
        prefix_usd_singular = pynini.string_map([("USD", "అమెరికన్ డాలర్"), ("US$", "అమెరికన్ డాలర్")])
        non_usd_in = pynini.difference(pynini.project(currency_graph, "input"), pynini.union("USD", "US$"))
        prefix_currency_graph = pynini.compose(non_usd_in, currency_graph) | prefix_usd_plural
        prefix_currency_singular_graph = pynini.compose(non_usd_in, currency_singular_graph) | prefix_usd_singular

        currency_major = pynutil.insert('currency_maj: "') + prefix_currency_graph + pynutil.insert('"') + optional_space
        currency_major_singular = (
            pynutil.insert('currency_maj: "') + prefix_currency_singular_graph + pynutil.insert('"') + optional_space
        )
        currency_suffix = optional_space + pynutil.insert(' currency_maj: "') + currency_graph + pynutil.insert('"')
        currency_suffix_singular = (
            optional_space + pynutil.insert(' currency_maj: "') + currency_singular_graph + pynutil.insert('"')
        )
        one = pynini.union("1", "౧")
        integer_one = pynutil.insert('integer_part: "') + (one @ cardinal_graph) + pynutil.insert('"')
        integer = pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')

        strip_trailing_zeros = pynini.closure(_ascii_digit) + _ascii_nonzero + pynini.closure(pynutil.delete("0"))
        canonicalise = (
            (pynutil.delete("0") + _ascii_nonzero)
            | (_ascii_nonzero + pynutil.insert("0"))
            | (_ascii_nonzero + _ascii_digit)
        )
        two_digits_fractional_part = deva_to_ascii @ strip_trailing_zeros @ canonicalise

        fraction = (
            pynutil.insert('fractional_part: "') + (two_digits_fractional_part @ cardinal_graph) + pynutil.insert('"')
        ).optimize()

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynini.closure(pynutil.delete("0") | pynutil.delete("౦"), 1),
            0,
            1,
        )

        has_3plus_sig_digits = _any_digit**2 + pynini.closure(_any_digit) + _any_nonzero + pynini.closure(_any_digit)
        single_digit = _any_digit @ cardinal.single_digits_graph
        decimal_digits = (
            pynutil.insert('fractional_part: "')
            + single_digit
            + pynini.closure(insert_space + single_digit)
            + pynutil.insert('"')
        )
        guarded_decimal_digits = (has_3plus_sig_digits @ decimal_digits).optimize()

        integer_final = pynutil.insert('integer_part: "') + cardinal.final_graph + pynutil.insert('"')

        # Per-unit suffix on money: "$15/h" -> "గంటకు పదిహేను డాలర్లు", "€20/kg" -> "కిలోగ్రాముకు ఇరవై యూరోలు"
        per_unit_map = pynini.string_map(
            [
                ("h", "గంటకు"),
                ("hr", "గంటకు"),
                ("s", "సెకనుకు"),
                ("sec", "సెకనుకు"),
                ("min", "నిమిషానికి"),
                ("d", "రోజుకు"),
                ("day", "రోజుకు"),
                ("wk", "వారానికి"),
                ("mo", "నెలకు"),
                ("yr", "సంవత్సరానికి"),
                ("kg", "కిలోగ్రాముకు"),
                ("g", "గ్రాముకు"),
                ("mg", "మిల్లీగ్రాముకు"),
                ("t", "టన్నుకు"),
                ("lb", "పౌండుకు"),
                ("oz", "ఔన్సుకు"),
                ("l", "లీటరుకు"),
                ("L", "లీటరుకు"),
                ("ml", "మిల్లీలీటరుకు"),
                ("mL", "మిల్లీలీటరుకు"),
                ("m", "మీటరుకు"),
                ("km", "కిలోమీటరుకు"),
                ("m²", "చదరపు మీటరుకు"),
                ("m2", "చదరపు మీటరుకు"),
                ("ft²", "చదరపు అడుగుకు"),
                ("kWh", "కిలోవాట్ గంటకు"),
            ]
        )
        optional_per_unit = pynini.closure(
            optional_space
            + pynutil.delete("/")
            + optional_space
            + pynutil.insert(' morphosyntactic_features: "')
            + per_unit_map
            + pynutil.insert('"'),
            0,
            1,
        ).optimize()

        # Magnitude shorthand: "$50k", "€50k", "$2.5M", "$1.2B"
        mag_k = pynini.union("k", "K")
        mag_mb = pynini.string_map([("M", "మిలియన్"), ("B", "బిలియన్"), ("T", "ట్రిలియన్")])
        mag_all = pynini.string_map(
            [("k", "వేల"), ("K", "వేల"), ("M", "మిలియన్"), ("B", "బిలియన్"), ("T", "ట్రిలియన్")]
        )
        short_digits = pynini.closure(NEMO_ALL_DIGIT, 1, 6)
        k_int_words = pynini.compose(one, pynutil.delete(one) + pynutil.insert("వెయ్యి")) | (
            pynini.compose(pynini.difference(short_digits, one), cardinal_graph) + pynutil.insert(" వేల")
        )
        mb_int_words = (
            pynini.compose(short_digits, cardinal_graph) + insert_space + optional_space + mag_mb
        )
        dec_frac_words = single_digit + pynini.closure(insert_space + single_digit, 0, 3)
        short_dec_words = (
            pynini.compose(short_digits, cardinal.final_graph)
            + pynini.cross(".", " దశాంశం ")
            + dec_frac_words
            + insert_space
            + optional_space
            + mag_all
        )
        shorthand_words = (
            (k_int_words + optional_space + pynutil.delete(mag_k)) | mb_int_words | short_dec_words
        ).optimize()
        shorthand_int = pynutil.insert('integer_part: "') + shorthand_words + pynutil.insert('"')

        graph_shorthand_prefix = (
            optional_graph_negative + currency_major + insert_space + shorthand_int + optional_per_unit
        )
        graph_shorthand_suffix = (
            optional_graph_negative + shorthand_int + currency_suffix + optional_per_unit
        )

        # Money ranges: "$10-$20", "$10–$20", "$10-20", "10-20 USD"
        short_num = cardinal.final_graph | (
            cardinal.final_graph
            + pynini.cross(".", " దశాంశం ")
            + single_digit
            + pynini.closure(insert_space + single_digit)
        )
        range_amt = (short_num | shorthand_words).optimize()
        range_dash = pynini.cross(pynini.union("-", "–", " - ", " – "), " నుండి ")
        maj_labels = load_labels(get_abs_path("data/money/currency.tsv"))
        prefix_maj_labels = [
            (sym, "అమెరికన్ డాలర్లు" if sym in ("USD", "US$") else maj) for sym, maj in maj_labels
        ]
        by_maj_prefix = defaultdict(list)
        for sym, maj in prefix_maj_labels:
            by_maj_prefix[maj].append(sym)
        same_sym_ranges = []
        for maj, syms in by_maj_prefix.items():
            sym_u = pynini.union(*syms)
            same_sym_ranges.append(
                pynutil.insert(f'currency_maj: "{maj}" integer_part: "')
                + pynutil.delete(sym_u)
                + optional_space
                + range_amt
                + range_dash
                + pynini.closure(pynutil.delete(sym_u) + optional_space, 0, 1)
                + range_amt
                + pynutil.insert('"')
                + optional_per_unit
            )
        graph_range_prefix = pynini.union(*same_sym_ranges)
        graph_range_suffix = (
            pynutil.insert('integer_part: "')
            + range_amt
            + range_dash
            + range_amt
            + pynutil.insert('"')
            + currency_suffix
            + optional_per_unit
        )

        graph_decimal_path = (
            optional_graph_negative
            + currency_major
            + insert_space
            + integer_final
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + optional_per_unit
        )
        graph_suffix_decimal = (
            optional_graph_negative
            + integer_final
            + pynini.cross(".", " ")
            + guarded_decimal_digits
            + currency_suffix
            + optional_per_unit
        )

        graph_major_only_singular = (
            optional_graph_negative
            + currency_major_singular
            + insert_space
            + integer_one
            + optional_delete_fractional_zeros
            + optional_per_unit
        )
        graph_suffix_only_singular = (
            optional_graph_negative
            + integer_one
            + optional_delete_fractional_zeros
            + currency_suffix_singular
            + optional_per_unit
        )

        graph_major_only = (
            optional_graph_negative
            + currency_major
            + insert_space
            + integer
            + optional_delete_fractional_zeros
            + optional_per_unit
        )
        graph_suffix_only = (
            optional_graph_negative
            + integer
            + optional_delete_fractional_zeros
            + currency_suffix
            + optional_per_unit
        )

        maj_singular_labels = load_labels(get_abs_path("data/money/currency_singular.tsv"))
        prefix_maj_singular_labels = [
            (sym, "అమెరికన్ డాలర్" if sym in ("USD", "US$") else maj) for sym, maj in maj_singular_labels
        ]
        maj_to_min = dict(load_labels(get_abs_path("data/money/major_minor_currencies.tsv")))

        def _build_major_and_minor(pref_labels, suf_labels, int_graph):
            by_pair_pref = defaultdict(list)
            for sym, maj in pref_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_pair_pref[(maj, min_name)].append(sym)
            by_pair_suf = defaultdict(list)
            for sym, maj in suf_labels:
                min_name = maj_to_min.get(maj)
                if min_name:
                    by_pair_suf[(maj, min_name)].append(sym)

            amount = (int_graph + pynini.cross(".", " ") + fraction).optimize()
            graphs = []
            for (maj, min_name), syms in by_pair_pref.items():
                sym_union = pynini.union(*syms)
                curr_maj = pynutil.insert(f'currency_maj: "{maj}"') + pynutil.delete(sym_union) + optional_space
                curr_min = pynutil.insert(f'currency_min: "{min_name}"')
                graphs.append(
                    optional_graph_negative
                    + curr_maj
                    + insert_space
                    + amount
                    + insert_space
                    + curr_min
                    + optional_per_unit
                )
            for (maj, min_name), syms in by_pair_suf.items():
                sym_union = pynini.union(*syms)
                graphs.append(
                    optional_graph_negative
                    + amount
                    + optional_space
                    + pynutil.insert(f' currency_maj: "{maj}" currency_min: "{min_name}"')
                    + pynutil.delete(sym_union)
                    + optional_per_unit
                )
            return pynini.union(*graphs)

        graph_major_and_minor = _build_major_and_minor(prefix_maj_labels, maj_labels, integer)
        graph_major_and_minor_singular = _build_major_and_minor(
            prefix_maj_singular_labels, maj_singular_labels, integer_one
        )

        graph_currencies = (
            pynutil.add_weight(
                graph_major_only_singular | graph_suffix_only_singular | graph_major_and_minor_singular, -0.001
            )
            | pynutil.add_weight(graph_decimal_path | graph_suffix_decimal, -0.0005)
            | pynutil.add_weight(graph_shorthand_prefix | graph_shorthand_suffix, -0.002)
            | pynutil.add_weight(graph_range_prefix | graph_range_suffix, -0.002)
            | graph_major_only
            | graph_suffix_only
            | graph_major_and_minor
        )

        graph = graph_currencies.optimize()
        self.fst = self.add_tokens(graph)
