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
from nemo_text_processing.text_normalization.tr.graph_utils import (
    case_suffix,
    glue_suffix,
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying cardinals in Turkish:
    - 0 -> sıfır
    - 1..9 -> bir..dokuz
    - 10..90 -> on..doksan
    - 100 -> yüz (never bir yüz)
    - 1000 -> bin (never bir bin)
    - 1000000 -> bir milyon
    - 1000000000 -> bir milyar
    - 1000000000000 -> bir trilyon
    - leading zero (007 -> sıfır sıfır yedi)
    - negative (-5 -> eksi beş)
    - suffixes (1995'te -> bin dokuz yüz doksan beşte, 80'ler -> seksenler)
    - ranges (5-10 -> beş ila on)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        d1_to_9 = pynini.string_map([
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        d2_to_9 = pynini.string_map([
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        tens_map = pynini.string_map([
            ("1", "on"),
            ("2", "yirmi"),
            ("3", "otuz"),
            ("4", "kırk"),
            ("5", "elli"),
            ("6", "altmış"),
            ("7", "yetmiş"),
            ("8", "seksen"),
            ("9", "doksan"),
        ])

        tens_exact = tens_map + pynutil.delete("0")
        tens_compound = tens_map + pynutil.insert(" ") + d1_to_9
        two_digits = tens_exact | tens_compound
        one_to_99 = (d1_to_9 | two_digits).optimize()

        rem_1_to_99 = (pynutil.delete("0") + pynutil.insert(" ") + d1_to_9) | (pynutil.insert(" ") + two_digits)
        hundred_1 = pynini.cross("1", "yüz") + (pynutil.delete("00") | rem_1_to_99)
        hundred_2_9 = d2_to_9 + pynutil.insert(" yüz") + (pynutil.delete("00") | rem_1_to_99)
        hundreds = (hundred_1 | hundred_2_9).optimize()

        one_to_999 = (one_to_99 | hundreds).optimize()

        # Tail 3-digit group when preceded by thousands, millions, etc.
        group_3_units = (
            pynutil.delete("000")
            | (pynutil.delete("00") + pynutil.insert(" ") + d1_to_9)
            | (pynutil.delete("0") + pynutil.insert(" ") + two_digits)
            | (pynutil.insert(" ") + hundreds)
        ).optimize()

        # Thousands group when preceded by millions
        group_3_thousands = (
            pynutil.delete("000")
            | (pynutil.delete("001") + pynutil.insert(" bin"))
            | (pynutil.delete("00") + pynutil.insert(" ") + d2_to_9 + pynutil.insert(" bin"))
            | (pynutil.delete("0") + pynutil.insert(" ") + two_digits + pynutil.insert(" bin"))
            | (pynutil.insert(" ") + hundreds + pynutil.insert(" bin"))
        ).optimize()

        # Millions group when preceded by billions
        group_3_millions = (
            pynutil.delete("000")
            | (pynutil.delete("00") + pynutil.insert(" ") + pynini.cross("1", "bir milyon"))
            | (pynutil.delete("00") + pynutil.insert(" ") + d2_to_9 + pynutil.insert(" milyon"))
            | (pynutil.delete("0") + pynutil.insert(" ") + two_digits + pynutil.insert(" milyon"))
            | (pynutil.insert(" ") + hundreds + pynutil.insert(" milyon"))
        ).optimize()

        # Billions group when preceded by trillions
        group_3_billions = (
            pynutil.delete("000")
            | (pynutil.delete("00") + pynutil.insert(" ") + pynini.cross("1", "bir milyar"))
            | (pynutil.delete("00") + pynutil.insert(" ") + d2_to_9 + pynutil.insert(" milyar"))
            | (pynutil.delete("0") + pynutil.insert(" ") + two_digits + pynutil.insert(" milyar"))
            | (pynutil.insert(" ") + hundreds + pynutil.insert(" milyar"))
        ).optimize()

        # Optional thousands separator
        sep = pynini.closure(pynutil.delete(pynini.union(".", " ", "\u202f")), 0, 1)

        # 1k to 999k: 1000 is "bin", 2000..999000 is "... bin"
        thousands_prefix = pynini.cross("1", "bin") | ((d2_to_9 | two_digits | hundreds) + pynutil.insert(" bin"))
        card_1k_999k = (thousands_prefix + sep + group_3_units).optimize()

        # 1m to 999m: "bir milyon", "iki milyon", etc.
        card_1m_999m = (
            one_to_999 + pynutil.insert(" milyon") + sep + group_3_thousands + sep + group_3_units
        ).optimize()

        # 1b to 999b: "bir milyar", etc.
        card_1b_999b = (
            one_to_999
            + pynutil.insert(" milyar")
            + sep
            + group_3_millions
            + sep
            + group_3_thousands
            + sep
            + group_3_units
        ).optimize()

        # 1t to 999t: "bir trilyon", etc.
        card_1t_999t = (
            one_to_999
            + pynutil.insert(" trilyon")
            + sep
            + group_3_billions
            + sep
            + group_3_millions
            + sep
            + group_3_thousands
            + sep
            + group_3_units
        ).optimize()

        zero = pynini.cross("0", "sıfır")
        positive_cardinals = (zero | one_to_999 | card_1k_999k | card_1m_999m | card_1b_999b | card_1t_999t).optimize()
        self.positive_cardinals = positive_cardinals

        # Digit-by-digit for leading zeros (007 -> sıfır sıfır yedi)
        single_digit = pynini.string_map([
            ("0", "sıfır"),
            ("1", "bir"),
            ("2", "iki"),
            ("3", "üç"),
            ("4", "dört"),
            ("5", "beş"),
            ("6", "altı"),
            ("7", "yedi"),
            ("8", "sekiz"),
            ("9", "dokuz"),
        ])
        leading_zero = pynini.cross("0", "sıfır") + pynini.closure(pynutil.insert(" ") + single_digit, 1)

        # Negative numbers (-5 -> eksi beş, −12 -> eksi on iki)
        sign_neg = pynini.cross(pynini.union("-", "−"), "eksi ")
        negative_cardinals = sign_neg + positive_cardinals

        # Approximate (~5 -> yaklaşık beş) & plus-minus (±5 -> artı eksi beş)
        approx = pynini.cross("~", "yaklaşık ") + (positive_cardinals | negative_cardinals)
        plus_minus = pynini.cross("±", "artı eksi ") + (positive_cardinals | negative_cardinals)

        # Numbers with Turkish apostrophe case / plural suffix (1995'te, 80'ler, 2'ye, 4'e)
        suffixed = glue_suffix(positive_cardinals + case_suffix)

        # Cardinal ranges (5-10, 10–20, 100-200)
        dash = pynini.union("-", "–", "—")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        cardinal_range = (
            positive_cardinals
            + opt_sp
            + pynini.cross(dash, " ila ")
            + opt_sp
            + positive_cardinals
        )
        self.range_graph = cardinal_range.optimize()

        # Combine all cardinal representations
        all_nums = (
            suffixed
            | approx
            | plus_minus
            | cardinal_range
            | negative_cardinals
            | leading_zero
            | positive_cardinals
        ).optimize()
        all_nums |= self.positive_cardinals + pynini.cross(":", " iki nokta üst üste ") + self.positive_cardinals
        self.all_nums = all_nums

        # Wrapped as name token
        self.fst = (pynutil.insert('name: "') + convert_space(all_nums) + pynutil.insert('"')).optimize()
