# Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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
from collections import defaultdict

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ar.graph_utils import (
    NEMO_DIGIT,
    NEMO_NON_BREAKING_SPACE,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ar.utils import get_abs_path, load_labels

min_singular = pynini.string_file(get_abs_path("data/money/currency_minor_singular.tsv"))
min_plural = pynini.string_file(get_abs_path("data/money/currency_minor_plural.tsv"))
maj_singular = pynini.string_file(get_abs_path("data/money/currency_major.tsv"))
ar_cur = pynini.string_file((get_abs_path("data/money/local_currency.tsv")))

_PER_UNIT_MAP = [
    ("h", "في الساعة"),
    ("hr", "في الساعة"),
    ("hrs", "في الساعة"),
    ("hour", "في الساعة"),
    ("ساعة", "في الساعة"),
    ("min", "في الدقيقة"),
    ("دقيقة", "في الدقيقة"),
    ("s", "في الثانية"),
    ("sec", "في الثانية"),
    ("ثانية", "في الثانية"),
    ("d", "في اليوم"),
    ("day", "في اليوم"),
    ("يوم", "في اليوم"),
    ("wk", "في الأسبوع"),
    ("week", "في الأسبوع"),
    ("أسبوع", "في الأسبوع"),
    ("mo", "في الشهر"),
    ("month", "في الشهر"),
    ("شهر", "في الشهر"),
    ("yr", "في السنة"),
    ("y", "في السنة"),
    ("year", "في السنة"),
    ("سنة", "في السنة"),
    ("عام", "في السنة"),
    ("kg", "لكل كيلوغرام"),
    ("كغ", "لكل كيلوغرام"),
    ("كجم", "لكل كيلوغرام"),
    ("g", "لكل غرام"),
    ("غ", "لكل غرام"),
    ("جم", "لكل غرام"),
    ("mg", "لكل مليغرام"),
    ("t", "لكل طن"),
    ("طن", "لكل طن"),
    ("lb", "لكل رطل"),
    ("oz", "لكل أونصة"),
    ("L", "لكل لتر"),
    ("l", "لكل لتر"),
    ("لتر", "لكل لتر"),
    ("mL", "لكل مليلتر"),
    ("ml", "لكل مليلتر"),
    ("m", "لكل متر"),
    ("م", "لكل متر"),
    ("km", "لكل كيلومتر"),
    ("كم", "لكل كيلومتر"),
    ("m²", "لكل متر مربع"),
    ("m2", "لكل متر مربع"),
    ("م²", "لكل متر مربع"),
    ("m³", "لكل متر مكعب"),
    ("m3", "لكل متر مكعب"),
    ("م³", "لكل متر مكعب"),
    ("kWh", "لكل كيلوواط ساعة"),
    ("MWh", "لكل ميغاواط ساعة"),
    ("unit", "لكل وحدة"),
    ("وحدة", "لكل وحدة"),
    ("قطعة", "لكل قطعة"),
    ("person", "لكل شخص"),
    ("شخص", "لكل شخص"),
    ("فرد", "لكل فرد"),
]


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, e.g.
        "$1,99" -> money { integer_part: "سبعة" currency_maj: "دولار" fractional_part: "تسعة وتسعون" currency_min: "سنت" preserve_order: true }
        "$50k" -> money { currency_maj: "دولار" integer_part: "خمسون ألف" }
        "$2.5M" -> money { currency_maj: "دولار" integer_part: "اثنان وخمسة من عشرة مليون" }
        "$15/h" -> money { currency_maj: "دولار" integer_part: "خمسة عشر" quantity: "في الساعة" }
        "-$12.50" -> money { negative: "true" integer_part: "اثنا عشر" currency_maj: "دولار" fractional_part: "خمسون" currency_min: "سنت" preserve_order: true }
        "25¢" -> money { fractional_part: "خمسة وعشرون" currency_min: "سنتا" preserve_order: true }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        group = pynutil.delete(",") + NEMO_DIGIT**3
        lead_group = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)
        comma_grouped = (lead_group + pynini.closure(group, 1, 3)) @ cardinal.cardinal_numbers
        cardinal_graph = (cardinal.cardinal_numbers_with_leading_zeros | comma_grouped).optimize()

        # Up to 7 digits for amounts with minor cents/fils (e.g. $1,234,567.89)
        digits_up_to_7 = (
            (pynini.closure("0") + NEMO_DIGIT)
            | ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 1, 6))
            | (lead_group + pynini.closure(group, 1, 2))
        )
        cardinal_minor_base = (digits_up_to_7 @ cardinal_graph).optimize()

        maj_rows = load_labels(get_abs_path("data/money/currency_major.tsv"))
        ar_rows = load_labels(get_abs_path("data/money/local_currency.tsv"))
        min_s_dict = dict(load_labels(get_abs_path("data/money/currency_minor_singular.tsv")))
        min_p_dict = dict(load_labels(get_abs_path("data/money/currency_minor_plural.tsv")))

        maj_singular_graph = convert_space(maj_singular).optimize()
        ar_cur_graph = convert_space(ar_cur).optimize()

        graph_maj_singular = (pynutil.insert('currency_maj: "') + maj_singular_graph + pynutil.insert('"')).optimize()
        graph_ar_cur = (pynutil.insert('currency_maj: "') + ar_cur_graph + pynutil.insert('"')).optimize()
        graph_all_cur = (graph_maj_singular | graph_ar_cur).optimize()

        opt_neg = pynini.closure(
            pynutil.insert('negative: "true" ')
            + pynutil.delete(pynini.union("-", "−") + pynini.closure(" ", 0, 1)),
            0,
            1,
        ).optimize()

        per_unit_fst = pynini.string_map(
            [(k, v.replace(" ", NEMO_NON_BREAKING_SPACE)) for k, v in _PER_UNIT_MAP]
        ).optimize()
        opt_per_unit = pynini.closure(
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.delete("/")
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' quantity: "')
            + per_unit_fst
            + pynutil.insert('"'),
            0,
            1,
        ).optimize()

        optional_delete_fractional_zeros = pynini.closure(
            pynutil.delete(".") + pynini.closure(pynutil.delete("0"), 1), 0, 1
        )
        graph_integer_one = (
            pynutil.insert('integer_part: "') + pynini.cross("1", "واحد") + pynutil.insert('"')
        ).optimize()
        zeros_only = pynini.closure("0", 1)
        non_zero_not_one = pynini.difference(pynini.project(cardinal_graph, "input"), zeros_only | "1")
        graph_integer = (
            pynutil.insert('integer_part: "') + (non_zero_not_one @ cardinal_graph) + pynutil.insert('"')
        ).optimize()

        non_zero_not_one_7 = pynini.difference(pynini.project(cardinal_minor_base, "input"), zeros_only | "1")
        graph_integer_7 = (
            pynutil.insert('integer_part: "') + (non_zero_not_one_7 @ cardinal_minor_base) + pynutil.insert('"')
        ).optimize()

        # Compact magnitude shorthand: integer & decimal (0..999) + k / M / B / T
        int_k = ((lead_group + pynutil.insert("000")) @ cardinal.cardinal_numbers) + pynutil.delete(
            pynini.union("k", "K")
        )
        int_m = ((lead_group + pynutil.insert("000000")) @ cardinal.cardinal_numbers) + pynutil.delete(
            pynini.union("M", "m")
        )
        int_b = ((lead_group + pynutil.insert("000000000")) @ cardinal.cardinal_numbers) + pynutil.delete(
            pynini.union("B", "b")
        )
        digits_3_10 = pynini.union("3", "4", "5", "6", "7", "8", "9", "10")
        other_t = pynini.difference(lead_group, pynini.union("1", "2") | digits_3_10)
        int_t = (
            pynini.cross("1", "تريليون")
            | pynini.cross("2", "تريليونان")
            | ((digits_3_10 @ cardinal.cardinal_numbers) + pynutil.insert(" تريليونات"))
            | ((other_t @ cardinal.cardinal_numbers) + pynutil.insert(" تريليون"))
        ) + pynutil.delete(pynini.union("T", "t"))

        dec_int = (lead_group | "0") @ cardinal.cardinal_numbers
        dec_sep = pynini.cross(pynini.union(".", ","), " و")
        dec_frac_1_2 = (
            (NEMO_DIGIT @ cardinal.cardinal_numbers_with_leading_zeros + pynutil.insert(" من عشرة"))
            | ((NEMO_DIGIT**2) @ cardinal.cardinal_numbers_with_leading_zeros + pynutil.insert(" من مئة"))
        )
        mag_suffix = (
            pynini.cross(pynini.union("k", "K"), " ألف")
            | pynini.cross(pynini.union("M", "m"), " مليون")
            | pynini.cross(pynini.union("B", "b"), " مليار")
            | pynini.cross(pynini.union("T", "t"), " تريليون")
        )
        dec_shorthand = dec_int + dec_sep + dec_frac_1_2 + mag_suffix
        shorthand_spoken = convert_space(int_k | int_m | int_b | int_t | dec_shorthand).optimize()
        graph_shorthand = (pynutil.insert('integer_part: "') + shorthand_spoken + pynutil.insert('"')).optimize()

        currency_first = pynutil.insert(' morphosyntactic_features: "currency_first"')
        # Currency-first tagging for exactly one major unit (e.g. $1 / $1.00 -> دولار واحد).
        graph_integer_one_unit = (
            graph_maj_singular
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + insert_space
            + graph_integer_one
            + currency_first
            + optional_delete_fractional_zeros
        ).optimize()

        # remove trailing zeros of non zero number in the first 2 digits and fill up to 2 digits
        two_digits_fractional_part = (
            (pynini.closure(NEMO_DIGIT) + (NEMO_DIGIT - "0") + pynini.closure(pynutil.delete("0")))
            @ (
                (pynutil.delete("0") + (NEMO_DIGIT - "0"))
                | ((NEMO_DIGIT - "0") + pynutil.insert("0"))
                | ((NEMO_DIGIT - "0") + NEMO_DIGIT)
            )
        ).optimize()

        digits_two_to_ten = pynini.union("2", "3", "4", "5", "6", "7", "8", "9", "10")
        frac_one = (
            pynutil.insert('fractional_part: "')
            + (two_digits_fractional_part @ pynini.cross("1", "واحد"))
            + pynutil.insert('"')
        ).optimize()
        frac_two_to_ten = (
            pynutil.insert('fractional_part: "')
            + (two_digits_fractional_part @ digits_two_to_ten @ cardinal.cardinal_numbers)
            + pynutil.insert('"')
        ).optimize()
        frac_other = (
            pynutil.insert('fractional_part: "')
            + (
                two_digits_fractional_part
                @ (
                    pynini.closure(NEMO_DIGIT, 1, 2)
                    - pynini.union("1", "2", "3", "4", "5", "6", "7", "8", "9", "10")
                )
                @ cardinal.cardinal_numbers
            )
            + pynutil.insert('"')
        ).optimize()
        frac_any = (
            pynutil.insert('fractional_part: "')
            + (two_digits_fractional_part @ cardinal.cardinal_numbers)
            + pynutil.insert('"')
        ).optimize()

        preserve_order = pynutil.insert(" preserve_order: true")

        # Cents symbol "¢" ("25¢" -> "خمسة وعشرون سنتا", "5¢" -> "خمسة سنتات", "1¢" -> "سنت واحد")
        cents_num_all = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 5)
        cents_3_10 = pynini.union("3", "4", "5", "6", "7", "8", "9", "10")
        cents_11_plus = pynini.difference(cents_num_all, pynini.union("1", "2") | cents_3_10)
        cents_cf = (
            pynutil.insert('currency_maj: "سنت" integer_part: "')
            + pynini.cross("1", "واحد")
            + pynutil.insert('"')
            + currency_first
        )
        cents_po = (
            (
                pynutil.insert('integer_part: "')
                + pynini.cross("2", "اثنان")
                + pynutil.insert('" currency_maj: "سنت"')
            )
            | (
                pynutil.insert('fractional_part: "')
                + (cents_3_10 @ cardinal.cardinal_numbers)
                + pynutil.insert('" currency_min: "سنتات"')
            )
            | (
                pynutil.insert('fractional_part: "')
                + (cents_11_plus @ cardinal.cardinal_numbers)
                + pynutil.insert('" currency_min: "سنتا"')
            )
        )
        cents_del_suf = pynini.closure(pynutil.delete(" "), 0, 1) + pynutil.delete("¢")
        cents_del_pre = pynutil.delete("¢") + pynini.closure(pynutil.delete(" "), 0, 1)
        cents_cf_graph = (cents_cf + cents_del_suf) | (cents_del_pre + cents_cf)
        cents_po_graph = (cents_po + cents_del_suf) | (cents_del_pre + cents_po)

        # Single-copy prefix no_minor for ALL currencies (permuted by Normalizer -> integer_part before currency_maj!)
        prefix_no_minor = (
            (
                (graph_maj_singular + pynini.closure(pynutil.delete(" "), 0, 1) + insert_space + (graph_integer + optional_delete_fractional_zeros | graph_shorthand))
                | (graph_ar_cur + pynini.closure(pynutil.delete(" "), 0, 1) + insert_space + ((graph_integer | graph_integer_one) + optional_delete_fractional_zeros | graph_shorthand))
            )
        ).optimize()

        # Single-copy prefix with_minor for currencies WITHOUT minor units (e.g. "aed1.2" -> واحد درهم إماراتي وعشرون)
        no_min_syms = [
            sym
            for sym, _ in (maj_rows + ar_rows)
            if not (min_s_dict.get(sym) and min_p_dict.get(sym))
        ]
        prefix_no_min_decimal = (
            (pynini.union(*sorted(set(no_min_syms))) @ graph_all_cur)
            + pynini.closure(pynutil.delete(" "), 0, 1)
            + insert_space
            + (graph_integer_7 | graph_integer_one)
            + pynini.cross(".", " ")
            + frac_any
        ).optimize()

        # Trailing currencies without minor units ("500 USD", "100 ج.م", "5ر.س", "10.00 ر.س", "50k USD") — single FST!
        maj_symbols = sorted({r[0] for r in maj_rows})
        ascii_alpha_syms = [s for s in maj_symbols if s.isascii() and any(c.isalpha() for c in s)]
        sign_syms = [s for s in maj_symbols if not (s.isascii() and any(c.isalpha() for c in s))]
        suffix_maj = (pynutil.delete(" ") + (pynini.union(*ascii_alpha_syms) @ graph_maj_singular)) | (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + ((pynini.union(*sign_syms) @ graph_maj_singular) | graph_ar_cur)
        )
        suffix_no_minor = (
            (((graph_integer | graph_integer_one) + optional_delete_fractional_zeros) | graph_shorthand)
            + insert_space
            + suffix_maj
        ).optimize()

        # Only currencies WITH minor units need per-(name, ms, mp) branches for ".xx" cents/fils/etc.
        by_minor = defaultdict(list)
        for sym, name in maj_rows + ar_rows:
            ms, mp = min_s_dict.get(sym), min_p_dict.get(sym)
            if ms and mp:
                by_minor[(name, ms, mp)].append(sym)

        po_branches = [cents_po_graph, pynutil.add_weight(suffix_no_minor, 0.01)]
        for (name, ms, mp), syms in by_minor.items():
            maj_tag = pynutil.insert(f'currency_maj: "{name.replace(" ", NEMO_NON_BREAKING_SPACE)}"')
            int_maj_one = (graph_integer_7 | graph_integer_one) + insert_space + maj_tag
            min_s_tag = pynutil.insert(f' currency_min: "{ms.replace(" ", NEMO_NON_BREAKING_SPACE)}"')
            min_p_tag = pynutil.insert(f' currency_min: "{mp.replace(" ", NEMO_NON_BREAKING_SPACE)}"')
            frac_plus_min = ((frac_other | frac_one) + insert_space + min_s_tag) | (
                frac_two_to_ten + insert_space + min_p_tag
            )
            with_minor = (
                (int_maj_one + pynini.cross(".", " ") + frac_plus_min)
                | pynutil.add_weight(int_maj_one + pynini.cross(".", " ") + frac_any, 0.0001)
                | (pynutil.delete("0.") + frac_plus_min)
            )
            del_pre = pynutil.delete(pynini.union(*syms) + pynini.closure(" ", 0, 1))
            po_branches.append(del_pre + with_minor)

            alpha_s = [s for s in syms if s.isascii() and any(c.isalpha() for c in s)]
            other_s = [s for s in syms if not (s.isascii() and any(c.isalpha() for c in s))]
            suf_parts = []
            if alpha_s:
                suf_parts.append(pynini.accep(" ") + pynini.union(*alpha_s))
            if other_s:
                suf_parts.append(pynini.closure(" ", 0, 1) + pynini.union(*other_s))
            del_suf = pynutil.delete(pynini.union(*suf_parts))
            po_branches.append(pynutil.add_weight(with_minor + del_suf, 0.01))

        permuted_all = (graph_integer_one_unit | cents_cf_graph | prefix_no_minor | prefix_no_min_decimal) + opt_per_unit
        po_all = pynini.union(*po_branches).optimize() + opt_per_unit + preserve_order

        final_graph = self.add_tokens(opt_neg + (permuted_all | po_all))
        self.fst = final_graph.optimize()
