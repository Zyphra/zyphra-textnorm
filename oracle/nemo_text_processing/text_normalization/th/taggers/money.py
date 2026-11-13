# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.th.taggers.decimal import DecimalFst


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying money expressions in Thai (th).
    Supports:
    - Thai Baht & Satang: ฿500, 500 ฿, 500 THB, 500 บาท, ฿12.50, ฿10.00, ฿0.50, ฿1,234.56
    - World currencies: $, €, £, ¥, ₩, ₹, ₽, ₺, ₪, ₴, ₫, ৳, ₦, ₱, ֏, CHF, CAD, AUD, BRL, MXN
    - Cents: 25¢ -> ยี่สิบห้าเซนต์
    - Multipliers: $50k, €50k, $2.5M
    - Negative: -$12.50, -12,50 €
    - Per-unit: $15/h -> สิบห้าดอลลาร์ต่อชั่วโมง, €20/kg -> ยี่สิบยูโรต่อกิโลกรัม
    - Currency ranges (preserving both units in mixed ranges): $10-$20, $10-€20
    """

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        thai_to_ascii = pynini.string_map(
            [
                ("๐", "0"),
                ("๑", "1"),
                ("๒", "2"),
                ("๓", "3"),
                ("๔", "4"),
                ("๕", "5"),
                ("๖", "6"),
                ("๗", "7"),
                ("๘", "8"),
                ("๙", "9"),
            ]
        )
        single_digit = thai_to_ascii | NEMO_DIGIT
        single_digit_words = pynini.string_map(
            [
                ("0", "ศูนย์"),
                ("1", "หนึ่ง"),
                ("2", "สอง"),
                ("3", "สาม"),
                ("4", "สี่"),
                ("5", "ห้า"),
                ("6", "หก"),
                ("7", "เจ็ด"),
                ("8", "แปด"),
                ("9", "เก้า"),
            ]
        )
        # 2-digit minor readings (00-99)
        satang_numbers = (
            pynini.cross("00", "")
            | (pynutil.delete("0") + (single_digit @ single_digit_words) + pynutil.insert("สตางค์"))
            | (cardinal.all_positive + pynutil.insert("สตางค์"))
        )

        cents_numbers = (
            pynini.cross("00", "")
            | (pynutil.delete("0") + (single_digit @ single_digit_words) + pynutil.insert("เซนต์"))
            | (cardinal.all_positive + pynutil.insert("เซนต์"))
        )

        pence_numbers = (
            pynini.cross("00", "")
            | (pynutil.delete("0") + (single_digit @ single_digit_words) + pynutil.insert("เพนซ์"))
            | (cardinal.all_positive + pynutil.insert("เพนซ์"))
        )

        # 1. Thai Baht (฿, THB, บาท)
        baht_sym = pynini.union("฿", "THB ", "THB", "บาท")

        # Integer Baht
        int_baht_pre = pynutil.delete(pynini.union("฿", "THB ", "THB")) + cardinal.all_positive + pynutil.insert("บาท")
        int_baht_post = cardinal.all_positive + opt_sp + pynutil.delete(baht_sym) + pynutil.insert("บาท")
        int_baht = (int_baht_pre | int_baht_post).optimize()

        # Decimal Baht: ฿12.50, ฿10.00, ฿0.50
        two_digits = single_digit + single_digit
        dec_baht_nonzero = (
            pynutil.delete(pynini.union("฿", "THB ", "THB"))
            + cardinal.all_positive
            + pynutil.insert("บาท")
            + pynutil.delete(".")
            + satang_numbers
        )
        dec_baht_zero = (
            pynutil.delete(pynini.union("฿", "THB ", "THB"))
            + pynutil.delete("0")
            + pynutil.delete(".")
            + (two_digits @ (
                (pynutil.delete("0") + (single_digit @ single_digit_words) + pynutil.insert("สตางค์"))
                | (cardinal.all_positive + pynutil.insert("สตางค์"))
            ))
        )
        dec_baht_post_nonzero = (
            cardinal.all_positive
            + pynutil.insert("บาท")
            + pynutil.delete(".")
            + satang_numbers
            + opt_sp
            + pynutil.delete(baht_sym)
        )
        dec_baht_post_zero = (
            pynutil.delete("0")
            + pynutil.delete(".")
            + (two_digits @ (
                (pynutil.delete("0") + (single_digit @ single_digit_words) + pynutil.insert("สตางค์"))
                | (cardinal.all_positive + pynutil.insert("สตางค์"))
            ))
            + opt_sp
            + pynutil.delete(baht_sym)
        )
        thai_baht = (
            int_baht
            | dec_baht_nonzero
            | dec_baht_zero
            | dec_baht_post_nonzero
            | dec_baht_post_zero
        ).optimize()

        # 2. USD ($)
        usd_prefix_us = pynini.union("US$", "US $", "USD ", "USD")
        usd_prefix_sym = pynini.union("$")
        usd_prefix = usd_prefix_us | usd_prefix_sym
        int_usd_pre = (
            (pynutil.delete(usd_prefix_us) + cardinal.all_positive + pynutil.insert("ดอลลาร์สหรัฐ"))
            | (pynutil.delete(usd_prefix_sym) + cardinal.all_positive + pynutil.insert("ดอลลาร์"))
        )
        int_usd_post = cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("$", "USD")) + pynutil.insert("ดอลลาร์สหรัฐ")
        dec_usd_nonzero = (
            pynutil.delete(usd_prefix)
            + cardinal.all_positive
            + pynutil.insert("ดอลลาร์")
            + pynutil.delete(".")
            + cents_numbers
        )
        dec_usd_zero = (
            pynutil.delete(usd_prefix)
            + pynutil.delete("0")
            + pynutil.insert("ศูนย์ดอลลาร์")
            + pynutil.delete(".")
            + (two_digits @ (
                (pynutil.delete("0") + (single_digit @ single_digit_words) + pynutil.insert("เซนต์"))
                | (cardinal.all_positive + pynutil.insert("เซนต์"))
            ))
        )
        cents_standalone = cardinal.all_positive + opt_sp + pynutil.delete("¢") + pynutil.insert("เซนต์")
        usd = (int_usd_pre | int_usd_post | dec_usd_nonzero | dec_usd_zero | cents_standalone).optimize()

        # 3. EUR (€)
        eur_prefix = pynini.union("€", "EUR ", "EUR")
        int_eur_pre = pynutil.delete(eur_prefix) + cardinal.all_positive + pynutil.insert("ยูโร")
        int_eur_post = cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("€", "EUR")) + pynutil.insert("ยูโร")
        dec_eur_pre = (
            pynutil.delete(eur_prefix)
            + cardinal.all_positive
            + pynutil.insert("ยูโร")
            + pynutil.delete(pynini.union(".", ","))
            + cents_numbers
        )
        dec_eur_post = (
            cardinal.all_positive
            + pynutil.insert("ยูโร")
            + pynutil.delete(pynini.union(".", ","))
            + cents_numbers
            + opt_sp
            + pynutil.delete(pynini.union("€", "EUR"))
        )
        eur = (int_eur_pre | int_eur_post | dec_eur_pre | dec_eur_post).optimize()

        # 4. GBP (£)
        gbp_prefix = pynini.union("£", "GBP ", "GBP")
        int_gbp_pre = pynutil.delete(gbp_prefix) + cardinal.all_positive + pynutil.insert("ปอนด์")
        int_gbp_post = cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("£", "GBP")) + pynutil.insert("ปอนด์")
        dec_gbp_pre = (
            pynutil.delete(gbp_prefix)
            + cardinal.all_positive
            + pynutil.insert("ปอนด์")
            + pynutil.delete(".")
            + pence_numbers
        )
        gbp = (int_gbp_pre | int_gbp_post | dec_gbp_pre).optimize()

        # 5. JPY (¥, 円, JPY)
        jpy_prefix = pynini.union("¥", "JPY ", "JPY")
        int_jpy_pre = pynutil.delete(jpy_prefix) + cardinal.all_positive + pynutil.insert("เยน")
        int_jpy_post = cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("¥", "円", "JPY")) + pynutil.insert("เยน")
        jpy = (int_jpy_pre | int_jpy_post).optimize()

        # 6. Other currencies
        krw = (pynutil.delete(pynini.union("₩", "KRW ", "KRW")) + cardinal.all_positive + pynutil.insert("วอน")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₩", "KRW")) + pynutil.insert("วอน")
        )
        inr = (
            pynutil.delete(pynini.union("₹", "Rs. ", "Rs.", "INR ", "INR"))
            + cardinal.all_positive
            + pynutil.insert("รูปี")
        ) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₹", "INR")) + pynutil.insert("รูปี")
        )
        rub = (pynutil.delete(pynini.union("₽", "RUB ", "RUB")) + cardinal.all_positive + pynutil.insert("รูเบิล")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₽", "RUB")) + pynutil.insert("รูเบิล")
        )
        try_cur = (pynutil.delete(pynini.union("₺", "TRY ", "TRY")) + cardinal.all_positive + pynutil.insert("ลีรา")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₺", "TRY")) + pynutil.insert("ลีรา")
        )
        ils = (pynutil.delete(pynini.union("₪", "ILS ", "ILS")) + cardinal.all_positive + pynutil.insert("เชเกล")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₪", "ILS")) + pynutil.insert("เชเกล")
        )
        uah = (pynutil.delete(pynini.union("₴", "UAH ", "UAH")) + cardinal.all_positive + pynutil.insert("ฮริฟเนีย")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₴", "UAH")) + pynutil.insert("ฮริฟเนีย")
        )
        vnd = (pynutil.delete(pynini.union("₫", "VND ", "VND")) + cardinal.all_positive + pynutil.insert("ดง")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₫", "VND")) + pynutil.insert("ดง")
        )
        bdt = (pynutil.delete(pynini.union("৳", "BDT ", "BDT")) + cardinal.all_positive + pynutil.insert("ตากา")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("৳", "BDT")) + pynutil.insert("ตากา")
        )
        ngn = (pynutil.delete(pynini.union("₦", "NGN ", "NGN")) + cardinal.all_positive + pynutil.insert("ไนรา")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₦", "NGN")) + pynutil.insert("ไนรา")
        )
        php = (pynutil.delete(pynini.union("₱", "PHP ", "PHP")) + cardinal.all_positive + pynutil.insert("เปโซ")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("₱", "PHP")) + pynutil.insert("เปโซ")
        )
        amd = (pynutil.delete(pynini.union("֏", "AMD ", "AMD")) + cardinal.all_positive + pynutil.insert("ดรัม")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("֏", "AMD")) + pynutil.insert("ดรัม")
        )

        chf = (pynutil.delete(pynini.union("CHF ", "CHF")) + cardinal.all_positive + pynutil.insert("ฟรังก์สวิส")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("CHF", "CHF ")) + pynutil.insert("ฟรังก์สวิส")
        )
        cad = (pynutil.delete(pynini.union("CA$", "CAD ", "CAD")) + cardinal.all_positive + pynutil.insert("ดอลลาร์แคนาดา")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("CAD", "CAD ")) + pynutil.insert("ดอลลาร์แคนาดา")
        )
        aud = (pynutil.delete(pynini.union("A$", "AUD ", "AUD")) + cardinal.all_positive + pynutil.insert("ดอลลาร์ออสเตรเลีย")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("AUD", "AUD ")) + pynutil.insert("ดอลลาร์ออสเตรเลีย")
        )
        brl = (pynutil.delete(pynini.union("R$", "BRL ", "BRL")) + cardinal.all_positive + pynutil.insert("เรียลบราซิล")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("BRL", "BRL ")) + pynutil.insert("เรียลบราซิล")
        )
        mxn = (pynutil.delete(pynini.union("MX$", "MXN ", "MXN")) + cardinal.all_positive + pynutil.insert("เปโซเม็กซิโก")) | (
            cardinal.all_positive + opt_sp + pynutil.delete(pynini.union("MXN", "MXN ")) + pynutil.insert("เปโซเม็กซิโก")
        )

        # 7. Shorthand multipliers: $50k -> ห้าหมื่นดอลลาร์, €50k -> ห้าหมื่นยูโร, $2.5M -> สองจุดห้าล้านดอลลาร์
        mult_k = pynini.union("k", "K")
        mult_m = pynini.union("M", "m")
        k_to_thousands = cardinal.all_positive + pynutil.delete(mult_k) + pynutil.insert("หมื่น")  # 50k = 5 หมื่น
        m_to_millions = decimal.positive_decimal + pynutil.delete(mult_m) + pynutil.insert("ล้าน")

        scaled_k = (
            (pynini.closure(single_digit, 1) + pynutil.delete(mult_k) + pynutil.insert("000"))
            @ cardinal.all_positive
        )
        shorthand_usd = (
            (pynutil.delete(pynini.union("$", "US$", "USD")) + scaled_k + pynutil.insert("ดอลลาร์"))
            | (pynutil.delete(pynini.union("$", "US$", "USD")) + m_to_millions + pynutil.insert("ดอลลาร์"))
        )
        shorthand_eur = (
            (pynutil.delete(pynini.union("€", "EUR")) + scaled_k + pynutil.insert("ยูโร"))
            | (pynutil.delete(pynini.union("€", "EUR")) + m_to_millions + pynutil.insert("ยูโร"))
        )
        shorthand_baht = (
            pynutil.delete(pynini.union("฿", "THB")) + scaled_k + pynutil.insert("บาท")
        )

        all_shorthand = pynutil.add_weight(shorthand_usd | shorthand_eur | shorthand_baht, -0.1).optimize()

        positive_money = (
            thai_baht
            | usd
            | eur
            | gbp
            | jpy
            | krw
            | inr
            | rub
            | try_cur
            | ils
            | uah
            | vnd
            | bdt
            | ngn
            | php
            | amd
            | chf
            | cad
            | aud
            | brl
            | mxn
            | all_shorthand
        ).optimize()

        self.positive_money = positive_money

        # Negative money: -$12.50, -12,50 € -> ลบสิบสองดอลลาร์ห้าสิบเซนต์
        minus = pynini.cross("-", "ลบ") | pynini.cross("−", "ลบ")
        neg_money = (minus + positive_money).optimize()

        # Per-unit money: $15/h -> สิบห้าดอลลาร์ต่อชั่วโมง, €20/kg -> ยี่สิบยูโรต่อกิโลกรัม
        per_unit = pynini.string_map(
            [
                ("/h", "ต่อชั่วโมง"),
                ("/hr", "ต่อชั่วโมง"),
                ("/kg", "ต่อกิโลกรัม"),
                ("/m", "ต่อเมตร"),
                ("/month", "ต่อเดือน"),
                ("/year", "ต่อปี"),
                ("/day", "ต่อวัน"),
            ]
        )
        money_per_unit = (positive_money + per_unit).optimize()

        # Currency ranges:
        dash = pynini.union("-", "–", "—")
        range_op = opt_sp + pynini.cross(dash, "ถึง") + opt_sp

        # Same currency ranges: $10-$20 -> สิบถึงยี่สิบดอลลาร์
        range_usd = (
            pynutil.delete("$")
            + cardinal.all_positive
            + range_op
            + pynutil.delete("$")
            + cardinal.all_positive
            + pynutil.insert("ดอลลาร์")
        )
        range_baht = (
            pynutil.delete("฿")
            + cardinal.all_positive
            + range_op
            + pynutil.delete("฿")
            + cardinal.all_positive
            + pynutil.insert("บาท")
        )
        range_eur = (
            cardinal.all_positive
            + range_op
            + cardinal.all_positive
            + opt_sp
            + pynutil.delete("€")
            + pynutil.insert("ยูโร")
        )
        same_cur_ranges = (range_usd | range_baht | range_eur).optimize()

        # Mixed currency ranges: $10-€20 -> สิบดอลลาร์ถึงยี่สิบยูโร
        mixed_cur_ranges = (positive_money + range_op + positive_money).optimize()

        all_money_ranges = (same_cur_ranges | mixed_cur_ranges).optimize()

        graph = (
            pynutil.add_weight(all_money_ranges, 1.05)
            | pynutil.add_weight(money_per_unit, 1.06)
            | pynutil.add_weight(neg_money, 1.07)
            | pynutil.add_weight(positive_money, 1.08)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(graph)
            + pynutil.insert('"')
        ).optimize()
