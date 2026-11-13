# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
# Copyright (c) 2023, Jim O'Regan for Språkbanken Tal
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
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.sv.graph_utils import SV_ALPHA, ensure_space
from nemo_text_processing.text_normalization.sv.utils import get_abs_path, load_labels


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money, suppletive aware, e.g.
        $12,05 -> money { currency_maj: "dollar" integer_part: "tolv" fractional_part: "fem" currency_min: "cent" preserve_order: true }
        $1 -> money { currency_maj: "dollar" integer_part: "en" }
        $0,05 -> money { fractional_part: "fem" currency_min: "cent" preserve_order: true }
        $50k -> money { currency_maj: "dollar" integer_part: "femtiotusen" }
        $15/h -> money { currency_maj: "dollar" integer_part: "femton" morphosyntactic_features: "per timme" }
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)
        # an amount of exactly one magnitude is counted: 1 000 000 kr -> en miljon kronor
        cardinal_graph = (cardinal.graph_no_one_en @ cardinal.counted).optimize()
        cardinal_graph_ett = (cardinal.graph_no_one @ cardinal.counted).optimize()
        graph_decimal_final = decimal.final_graph_wo_negative_w_abbr_en.optimize()
        graph_decimal_final_ett = decimal.final_graph_wo_negative_w_abbr.optimize()

        min_singular_dict = dict(load_labels(get_abs_path("data/money/currency_minor_singular.tsv")))
        min_plural_dict = dict(load_labels(get_abs_path("data/money/currency_minor_plural.tsv")))
        maj_singular = pynini.string_file(get_abs_path("data/money/currency_major.tsv"))
        maj_singular_nt = pynini.string_file(get_abs_path("data/money/currency_major_nt.tsv"))
        maj_plural = pynini.string_file(get_abs_path("data/money/currency_plurals.tsv"))
        per_units = convert_space(pynini.string_file(get_abs_path("data/money/per_unit.tsv"))).optimize()

        maj_singular_labels = load_labels(get_abs_path("data/money/currency_major.tsv"))
        maj_singular_labels_nt = load_labels(get_abs_path("data/money/currency_major_nt.tsv"))
        maj_unit_plural = convert_space(maj_singular @ maj_plural).optimize()
        maj_unit_plural_nt = convert_space(maj_singular_nt @ maj_plural).optimize()
        maj_unit_singular = convert_space(maj_singular).optimize()
        maj_unit_singular_nt = convert_space(maj_singular_nt).optimize()

        self.maj_unit_plural = maj_unit_plural
        self.maj_unit_plural_nt = maj_unit_plural_nt
        self.maj_unit_singular = maj_unit_singular
        self.maj_unit_singular_nt = maj_unit_singular_nt

        graph_maj_singular = (pynutil.insert('currency_maj: "') + maj_unit_singular + pynutil.insert('"')).optimize()
        graph_maj_plural = (pynutil.insert('currency_maj: "') + maj_unit_plural + pynutil.insert('"')).optimize()
        graph_maj_singular_nt = (
            pynutil.insert('currency_maj: "') + maj_unit_singular_nt + pynutil.insert('"')
        ).optimize()
        graph_maj_plural_nt = (pynutil.insert('currency_maj: "') + maj_unit_plural_nt + pynutil.insert('"')).optimize()

        optional_delete_fractional_zeros = pynini.closure(
            (
                pynutil.delete(",")
                + (pynini.closure(pynutil.delete("0"), 1) | pynutil.delete(pynini.union("-", "–")))
            )
            | (pynutil.delete(".") + pynutil.delete("00")),
            0,
            1,
        ).optimize()

        graph_integer_sg_en = (
            pynutil.insert('integer_part: "') + pynini.cross("1", "en") + pynutil.insert('"')
        ).optimize()
        graph_integer_sg_ett = (
            pynutil.insert('integer_part: "') + pynini.cross("1", "ett") + pynutil.insert('"')
        ).optimize()

        decimal_delete_last_zeros = (
            pynini.closure(NEMO_DIGIT | pynutil.delete(" "))
            + pynini.accep(",")
            + pynini.closure(NEMO_DIGIT, 2)
            + (NEMO_DIGIT - "0")
            + pynini.closure(pynutil.delete("0"))
        )
        decimal_with_quantity = (
            pynini.cdrewrite(pynini.cross(".", ","), NEMO_DIGIT, NEMO_DIGIT, NEMO_SIGMA) @ (NEMO_SIGMA + SV_ALPHA)
        )

        decimal_part = ((decimal_delete_last_zeros | decimal_with_quantity) @ graph_decimal_final).optimize()
        decimal_part_ett = ((decimal_delete_last_zeros | decimal_with_quantity) @ graph_decimal_final_ett).optimize()

        # Shorthand magnitude suffixes for currencies: $50k -> femtiotusen dollar, $2,5M / $2.5M -> två komma fem miljoner dollar
        k_int_en = (
            pynutil.insert('integer_part: "')
            + ((pynini.closure(NEMO_DIGIT, 1) + pynini.cross(pynini.union("k", "K"), "000")) @ cardinal_graph)
            + pynutil.insert('"')
        )
        k_int_ett = (
            pynutil.insert('integer_part: "')
            + ((pynini.closure(NEMO_DIGIT, 1) + pynini.cross(pynini.union("k", "K"), "000")) @ cardinal_graph_ett)
            + pynutil.insert('"')
        )
        m_suffix = pynini.closure(pynutil.delete(" "), 0, 1) + pynini.accep("M")
        b_suffix = pynini.closure(pynutil.delete(" "), 0, 1) + pynini.accep("B")
        k_dec_suffix = pynini.closure(pynutil.delete(" "), 0, 1) + pynini.union("k", "K")

        mb_int = (
            (
                pynutil.insert('integer_part: "')
                + cardinal.graph_no_one_en
                + pynutil.insert('" quantity: "')
                + (pynini.cross(m_suffix, "miljoner") | pynini.cross(b_suffix, "miljarder"))
                + pynutil.insert('"')
            )
            | (
                pynutil.insert('integer_part: "en" quantity: "')
                + pynutil.delete("1")
                + (pynini.cross(m_suffix, "miljon") | pynini.cross(b_suffix, "miljard"))
                + pynutil.insert('"')
            )
        )
        dec_norm = (
            pynini.closure(NEMO_DIGIT, 1)
            + pynini.cross(pynini.union(",", "."), ",")
            + pynini.closure(NEMO_DIGIT, 1)
        )
        shorthand_dec = (
            (
                (dec_norm @ decimal.final_graph_wo_sign_en)
                + pynutil.insert(' quantity: "')
                + (pynini.cross(m_suffix, "miljoner") | pynini.cross(b_suffix, "miljarder"))
                + pynutil.insert('"')
            )
            | (
                (dec_norm @ decimal.final_graph_wo_sign)
                + pynutil.insert(' quantity: "')
                + pynini.cross(k_dec_suffix, "tusen")
                + pynutil.insert('"')
            )
        )

        decimal_or_shorthand_en = (decimal_part | k_int_en | mb_int | shorthand_dec).optimize()
        decimal_or_shorthand_ett = (decimal_part_ett | k_int_ett | mb_int | shorthand_dec).optimize()

        spelled = (
            pynutil.insert('currency_maj: "') + pynini.project(maj_unit_plural, "output") + pynutil.insert('"')
        ).optimize()
        spelled_nt = (
            pynutil.insert('currency_maj: "') + pynini.project(maj_unit_plural_nt, "output") + pynutil.insert('"')
        ).optimize()

        graph_decimal = pynini.union(
            graph_maj_plural + ensure_space + decimal_or_shorthand_en,
            graph_maj_plural_nt + ensure_space + decimal_or_shorthand_ett,
            decimal_or_shorthand_ett + ensure_space + (graph_maj_plural_nt | spelled_nt),
            decimal_or_shorthand_en + ensure_space + (graph_maj_plural | spelled),
        ).optimize()

        graph_integer = (pynutil.insert('integer_part: "') + cardinal_graph + pynutil.insert('"')).optimize()
        graph_integer_ett = (pynutil.insert('integer_part: "') + cardinal_graph_ett + pynutil.insert('"')).optimize()

        leading_integer_bare = pynini.union(
            graph_maj_singular + ensure_space + graph_integer_sg_en,
            graph_maj_singular_nt + ensure_space + graph_integer_sg_ett,
            graph_maj_plural + ensure_space + graph_integer,
            graph_maj_plural_nt + ensure_space + graph_integer_ett,
        ).optimize()
        leading_integer_only = leading_integer_bare + optional_delete_fractional_zeros

        # Small FST for leading-currency integer ranges ($10-$20, €10–€20), restricted to <= 9 digits for tiny state count
        short_digits = pynini.closure(NEMO_DIGIT, 1, 9)
        short_lead = pynini.union(
            graph_maj_singular + ensure_space + graph_integer_sg_en,
            graph_maj_singular_nt + ensure_space + graph_integer_sg_ett,
            graph_maj_plural + ensure_space + (short_digits @ graph_integer),
            graph_maj_plural_nt + ensure_space + (short_digits @ graph_integer_ett),
        ).optimize()
        self.leading_int_fst = self.add_tokens(short_lead).optimize()

        trailing_integer_only = pynini.union(
            graph_integer_sg_en + optional_delete_fractional_zeros + ensure_space + graph_maj_singular,
            graph_integer_sg_ett + optional_delete_fractional_zeros + ensure_space + graph_maj_singular_nt,
            graph_integer + optional_delete_fractional_zeros + ensure_space + (graph_maj_plural | spelled),
            graph_integer_ett + optional_delete_fractional_zeros + ensure_space + (graph_maj_plural_nt | spelled_nt),
        )
        range_joiner = pynini.cross(pynini.union("-", "–", "—", " - ", " – ", " — "), " till ")
        range_int_en = (cardinal_graph | pynini.cross("1", "en")) + optional_delete_fractional_zeros
        range_int_ett = (cardinal_graph_ett | pynini.cross("1", "ett")) + optional_delete_fractional_zeros
        trailing_integer_only |= (
            pynutil.insert('integer_part: "')
            + range_int_en
            + range_joiner
            + range_int_en
            + pynutil.insert('"')
            + ensure_space
            + (graph_maj_plural | spelled)
        )
        trailing_integer_only |= (
            pynutil.insert('integer_part: "')
            + range_int_ett
            + range_joiner
            + range_int_ett
            + pynutil.insert('"')
            + ensure_space
            + (graph_maj_plural_nt | spelled_nt)
        )

        final_graph = (leading_integer_only | trailing_integer_only | graph_decimal).optimize()

        two_digits_fractional_part = (
            (pynini.closure(NEMO_DIGIT) + (NEMO_DIGIT - "0") + pynini.closure(pynutil.delete("0")))
            @ (
                (pynutil.delete("0") + (NEMO_DIGIT - "0"))
                | ((NEMO_DIGIT - "0") + pynutil.insert("0"))
                | ((NEMO_DIGIT - "0") + NEMO_DIGIT)
            )
        ).optimize()

        graph_fractional_one_en = (
            pynutil.insert('fractional_part: "')
            + (two_digits_fractional_part @ pynini.cross("1", "en"))
            + pynutil.insert('"')
        ).optimize()
        graph_fractional_one_ett = (
            pynutil.insert('fractional_part: "')
            + (two_digits_fractional_part @ pynini.cross("1", "ett"))
            + pynutil.insert('"')
        ).optimize()
        graph_fractional = (
            pynutil.insert('fractional_part: "')
            + (
                two_digits_fractional_part
                @ (pynini.closure(NEMO_DIGIT, 1, 2) - "1")
                @ cardinal.graph_hundreds_component_at_least_one_non_zero_digit_en
            )
            + pynutil.insert('"')
        ).optimize()

        non_zero_int_input = (
            (pynini.closure(NEMO_DIGIT) - "0") | ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT | delete_space))
        ).optimize()
        int_en = pynini.compose(non_zero_int_input, graph_integer).optimize()
        int_ett = pynini.compose(non_zero_int_input, graph_integer_ett).optimize()
        int_sg_en = graph_integer_sg_en.optimize()
        int_sg_ett = graph_integer_sg_ett.optimize()

        # FACTORING: Split currencies SOLELY into two gender buckets ("en" vs "ett") so int_en and int_ett are instantiated ONLY ONCE each!
        maj_singular_labels_all = [(x[0], "en") for x in maj_singular_labels]
        maj_singular_labels_all += [(x[0], "ett") for x in maj_singular_labels_nt]
        groups = {}
        seen_syms = set()
        for curr_symbol, one_form in maj_singular_labels_all:
            if curr_symbol in seen_syms:
                continue
            seen_syms.add(curr_symbol)
            min_sg = min_singular_dict.get(curr_symbol)
            min_pl = min_plural_dict.get(curr_symbol)
            if not min_sg or not min_pl:
                continue
            groups.setdefault((one_form, min_sg, min_pl), []).append(curr_symbol)

        preserve_order = pynutil.insert(" preserve_order: true")
        dec_sep_comma = pynini.cross(",", " ")
        dec_sep_dot = pynini.cross(".", " ")
        two_digit_dot_frac = pynini.closure(NEMO_DIGIT, 1, 2)
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        lead_pl_en_tails = []
        lead_sg_en_tails = []
        lead_pl_ett_tails = []
        lead_sg_ett_tails = []
        trail_pl_en_tails = []
        trail_sg_en_tails = []
        trail_pl_ett_tails = []
        trail_sg_ett_tails = []
        minor_only_graphs = []

        for (one_form, min_sg, min_pl), sym_list in groups.items():
            sym_accep = pynini.union(*sym_list).optimize()
            if one_form == "en":
                sym_maj_pl = (sym_accep @ graph_maj_plural).optimize()
                sym_maj_sg = (sym_accep @ graph_maj_singular).optimize()
            else:
                sym_maj_pl = (sym_accep @ graph_maj_plural_nt).optimize()
                sym_maj_sg = (sym_accep @ graph_maj_singular_nt).optimize()

            graph_fractional_one = graph_fractional_one_ett if min_sg == "öre" else graph_fractional_one_en
            fractional_plus_min = (
                (graph_fractional + pynutil.insert(f' currency_min: "{min_pl}"'))
                | (graph_fractional_one + pynutil.insert(f' currency_min: "{min_sg}"'))
            ).optimize()
            fractional_plus_min_dot = (two_digit_dot_frac @ fractional_plus_min).optimize()
            frac_sep = ((dec_sep_comma + fractional_plus_min) | (dec_sep_dot + fractional_plus_min_dot)).optimize()

            minor_only = (
                pynini.closure(pynutil.delete("0"), 0, 1)
                + ((pynutil.delete(",") + fractional_plus_min) | (pynutil.delete(".") + fractional_plus_min_dot))
            ).optimize()
            minor_only_graphs.append(
                ((pynutil.delete(sym_accep) + opt_sp + minor_only) | (minor_only + opt_sp + pynutil.delete(sym_accep)))
                + preserve_order
            )

            if one_form == "en":
                lead_pl_en_tails.append((sym_maj_pl + opt_sp + insert_space, frac_sep))
                lead_sg_en_tails.append((sym_maj_sg + opt_sp + insert_space, frac_sep))
                trail_pl_en_tails.append(frac_sep + opt_sp + insert_space + sym_maj_pl)
                trail_sg_en_tails.append(frac_sep + opt_sp + insert_space + sym_maj_sg)
            else:
                lead_pl_ett_tails.append((sym_maj_pl + opt_sp + insert_space, frac_sep))
                lead_sg_ett_tails.append((sym_maj_sg + opt_sp + insert_space, frac_sep))
                trail_pl_ett_tails.append(frac_sep + opt_sp + insert_space + sym_maj_pl)
                trail_sg_ett_tails.append(frac_sep + opt_sp + insert_space + sym_maj_sg)

        # Notice: for trailing (`12,50 kr`) and leading (`$12,50`), omitting `preserve_order: true` lets TokenParser
        # permute fields to canonical `(integer_part, currency_maj, fractional_part, currency_min)` order!
        trailing_all = (
            (int_en + pynini.union(*trail_pl_en_tails).optimize())
            | (int_sg_en + pynini.union(*trail_sg_en_tails).optimize())
        )
        if trail_pl_ett_tails:
            trailing_all |= (
                (int_ett + pynini.union(*trail_pl_ett_tails).optimize())
                | (int_sg_ett + pynini.union(*trail_sg_ett_tails).optimize())
            )
        # For leading (`$12,50`), restrict `int_en` to <= 12 digits (nobody writes cent-precision amounts > 999 billion!) or factor by `frac_sep`!
        # Wait: `lead_pl_en_tails` has `head` (before `int_en`) and `frac_sep` (after `int_en`). Notice `groups` already has unique `(one_form, min_sg, min_pl)`!
        # Why did `MoneyFst` have 120k states? Because `int_en` has 24-digit `cardinal_graph` (~3,000 states) x 19 groups = 57,000 states!
        # If we restrict `int_en` in minor-unit expressions (`$12,50`) to <= 12 digits (up to hundreds of billions), `short_int_en` has ~400 states instead of 3,000!
        short_non_zero_int_input = (
            ((pynini.closure(NEMO_DIGIT, 1, 12) - "0") | ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT | delete_space, 0, 14)))
        ).optimize()
        short_int_en = pynini.compose(short_non_zero_int_input, graph_integer).optimize()
        short_int_ett = pynini.compose(short_non_zero_int_input, graph_integer_ett).optimize()

        leading_parts = []
        for head, fsep in lead_pl_en_tails:
            leading_parts.append(head + short_int_en + fsep)
        for head, fsep in lead_sg_en_tails:
            leading_parts.append(head + int_sg_en + fsep)
        for head, fsep in lead_pl_ett_tails:
            leading_parts.append(head + short_int_ett + fsep)
        for head, fsep in lead_sg_ett_tails:
            leading_parts.append(head + int_sg_ett + fsep)
        decimal_graph_with_minor = (
            pynini.union(*leading_parts) | trailing_all | pynini.union(*minor_only_graphs)
        ).optimize()

        if not deterministic:
            default_fraction_graph = decimal_part
            all_en_syms = pynini.union(*[s for (of, _, _), sl in groups.items() if of == "en" for s in sl]).optimize()
            all_ett_syms = pynini.union(*[s for (of, _, _), sl in groups.items() if of == "ett" for s in sl]).optimize()
            integer_graph_reordered = (
                ((all_en_syms @ graph_maj_plural) + insert_space + short_int_en + preserve_order)
                | ((all_en_syms @ graph_maj_singular) + insert_space + int_sg_en + preserve_order)
                | ((all_ett_syms @ graph_maj_plural_nt) + insert_space + short_int_ett + preserve_order)
                | ((all_ett_syms @ graph_maj_singular_nt) + insert_space + int_sg_ett + preserve_order)
            ).optimize()
            decimal_default_reordered = (
                ((all_en_syms @ graph_maj_plural) + ensure_space + default_fraction_graph)
                | ((all_ett_syms @ graph_maj_plural_nt) + ensure_space + default_fraction_graph)
            ).optimize()
            final_graph |= integer_graph_reordered | decimal_default_reordered
            final_graph |= pynini.compose(
                NEMO_SIGMA + pynutil.delete(",") + pynini.closure(pynutil.delete("0"), 1), integer_graph_reordered
            )

        # weight for SH
        final_graph |= pynutil.add_weight(decimal_graph_with_minor, -0.0001)

        # Standalone cent symbol: 1¢ -> en cent, 25¢ -> tjugofem cent, ¢50 -> femtio cent
        cent_sg = (
            pynutil.insert('fractional_part: "')
            + pynini.cross("1", "en")
            + pynutil.insert('" currency_min: "cent" preserve_order: true')
        )
        cent_pl = (
            pynutil.insert('fractional_part: "')
            + cardinal_graph
            + pynutil.insert('" currency_min: "cent" preserve_order: true')
        )
        cent_sym = pynutil.delete("¢")
        cent_graph = (
            ((cent_sg | cent_pl) + opt_sp + cent_sym) | (cent_sym + opt_sp + (cent_sg | cent_pl))
        ).optimize()
        final_graph |= cent_graph

        # Optional per-unit suffix: $15/h -> femton dollar per timme, €20/kg -> tjugo euro per kilogram
        graph_per_units = (
            pynini.closure(pynutil.delete(" "), 0, 1)
            + pynutil.insert(' morphosyntactic_features: "')
            + per_units
            + pynutil.insert('"')
        ).optimize()

        pos_final = (final_graph + pynini.closure(graph_per_units, 0, 1)).optimize()
        self.positive_fst = self.add_tokens(pos_final).optimize()

        optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true" ') + opt_sp, 0, 1
        )
        self.fst = self.add_tokens(optional_graph_negative + pos_final).optimize()
