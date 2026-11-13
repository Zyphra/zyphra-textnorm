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
    insert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew decimals and magnitudes.
    e.g. 3.14 -> שלוש נקודה אחת ארבע (or שלוש נקודה ארבע עשרה)
         1.5 -> אחת נקודה חמש
         -1.5 -> מינוס אחת נקודה חמש
         2.5M -> שתיים נקודה חמש מיליון
         50k -> חמישים אלף
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        digit_f = cardinal.digit_f
        integer_part = cardinal.base_num_f

        # Fractional digits read digit by digit
        frac_by_digit = digit_f + pynini.closure(insert_space + digit_f)

        # Fractional two digits also read as a compound number
        frac_two = cardinal.two_digits_f | (pynini.cross("0", "אפס ") + digit_f)

        fractional = (pynutil.add_weight(frac_by_digit, 0.95) | pynutil.add_weight(frac_two, 1.05)).optimize()

        dot = pynini.cross(".", " נקודה ")

        decimal_core = integer_part + dot + fractional

        # Negative prefix
        neg = pynini.cross("-", "מינוס ") | pynini.cross("−", "מינוס ")
        opt_neg = pynini.closure(neg, 0, 1)

        decimal_num = (opt_neg + decimal_core).optimize()
        self.decimal_num = decimal_num

        # Magnitudes: k, M, B glued or spaced
        # 'k' is lowercase (uppercase K is serial like 4K); 'M' is uppercase (lowercase m is meters).
        mag_k = pynini.cross("k", " אלף")
        mag_m = pynini.cross("M", " מיליון")
        mag_b = pynini.cross("B", " מיליארד")
        magnitudes = mag_k | mag_m | mag_b

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        decimal_mag = (
            opt_neg
            + (decimal_core | integer_part)
            + opt_space
            + magnitudes
        ).optimize()
        self.decimal_mag = decimal_mag

        # Decimal ranges: 1.5-2.5 -> אחת נקודה חמש עד שתיים נקודה חמש
        dash = pynini.union("-", "–", "—", "־")
        decimal_range = (
            decimal_num + pynini.cross(dash, " עד ") + decimal_num
        ).optimize()

        all_decimals = (
            pynutil.add_weight(decimal_mag, -0.1)
            | pynutil.add_weight(decimal_range, 0.95)
            | pynutil.add_weight(decimal_num, 1.0)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_decimals) + pynutil.insert('"')
        ).optimize()
