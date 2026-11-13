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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Danish decimals (CLDR da).
    Handles:
      - Comma decimals: "3,5" -> "tre komma fem", "3,14" -> "tre komma en fire", "0,2" -> "nul komma to"
      - Grouped integer parts: "1.234,56" -> "et tusind tohundrede og fireogtredive komma seksoghalvtreds"
      - Leading zeroes in fractional part: "0,05" -> "nul komma nul fem"
      - Negative decimals: "-3,14" or "−3,14" -> "minus tre komma en fire"
      - Prefixed "~" ("cirka") and "±" ("plus-minus")
      - Decimal multipliers: "1,5 million" / "1,5 mio." / "1,5 mia."
      - Decimal ranges: "1,5-2,5" -> "en komma fem til to komma fem"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        # Decimal separator: comma is standard in Danish
        comma_sep = pynini.cross(",", " komma ")
        # Dot decimal (English notation e.g. 99.9%); weighted so it does not hijack dot-grouping
        dot_sep = pynutil.add_weight(pynini.cross(".", " komma "), 0.5)

        # Fractional digits
        digit = cardinal.single_digit
        fractional_digits = digit + pynini.closure(insert_space + digit)

        # 2-digit reading: e.g. ,15 -> femten
        two_digit_frac = cardinal.num_1_to_999_neuter
        # With leading zeros: ,05 -> nul fem
        lead_zero_frac = pynini.cross("0", "nul ") + fractional_digits
        # Pi reading: 14 -> en fire
        pi_frac = pynini.cross("14", "en fire")

        frac_part_comma = (
            pi_frac
            | two_digit_frac
            | lead_zero_frac
            | fractional_digits
        ).optimize()

        # For dot decimals, exclude 000 (which is thousands grouping)
        non_000 = pynini.difference(pynini.closure(NEMO_DIGIT, 1), "000")
        frac_part_dot = (
            non_000
            @ (pi_frac | two_digit_frac | lead_zero_frac | fractional_digits)
        ).optimize()

        # Integer part: common gender gives "en" for 1 ("en komma fem", "en million")
        integer = cardinal.integer_common

        # Core decimal
        core_comma = integer + comma_sep + frac_part_comma
        core_dot = integer + dot_sep + frac_part_dot

        core_decimal = core_comma | core_dot

        # Prefixes: minus, approx (~), plus-minus (±)
        minus_sign = pynini.cross(pynini.union("-", "−"), "minus ")
        approx_sign = pynini.cross("~", "cirka ")
        plus_minus_sign = pynini.cross("±", "plus-minus ")
        prefix = minus_sign | approx_sign | plus_minus_sign
        opt_prefix = pynini.closure(prefix, 0, 1)

        decimal_number = opt_prefix + core_decimal

        # Decimal with scale words: e.g. "1,5 million", "1,5 millioner", "1,5 mio.", "2,5 mia.", "1,5 mn"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        scale_million_sing = pynini.cross(pynini.union("million", "mio.", "mio", "mn"), " million")
        scale_milliard_sing = pynini.cross(pynini.union("milliard", "mia.", "mia", "md"), " milliard")
        scale_billion_sing = pynini.cross(pynini.union("billion", "bn"), " billion")
        scale_sing = scale_million_sing | scale_milliard_sing | scale_billion_sing

        scale_million_plur = pynini.cross(
            pynini.union("million", "millioner", "mio.", "mio", "mn"), " millioner"
        )
        scale_milliard_plur = pynini.cross(
            pynini.union("milliard", "milliarder", "mia.", "mia", "md"), " milliarder"
        )
        scale_billion_plur = pynini.cross(
            pynini.union("billion", "billioner", "bn"), " billioner"
        )
        scale_plur = scale_million_plur | scale_milliard_plur | scale_billion_plur

        # Integer with scale words:
        # 1 -> "en million", "en milliard"
        integer_scale_one = pynini.cross("1", "en") + opt_sp + scale_sing
        # > 1 -> "2 millioner", "45 milliarder"
        int_higher = (
            pynini.difference(pynini.project(cardinal.integer_common, "input"), "1")
            @ cardinal.integer_common
        ).optimize()
        integer_scale_higher = int_higher + opt_sp + scale_plur
        integer_scale = integer_scale_one | integer_scale_higher

        # Decimal with scale words: always plural (e.g. "1,5 million" -> "en komma fem millioner")
        decimal_scale = (
            decimal_number
            + opt_sp
            + scale_plur
        )

        # Decimal range: "1,5-2,5" -> "en komma fem til to komma fem"
        range_dash = pynini.cross(pynini.union("-", "–", "—"), " til ")
        decimal_range = (
            decimal_number
            + opt_sp
            + range_dash
            + opt_sp
            + decimal_number
        )

        self.core_decimal = decimal_number
        self.scale_graph = (decimal_scale | integer_scale).optimize()
        self.range = decimal_range

        all_decimals = (
            self.range
            | self.scale_graph
            | self.core_decimal
        ).optimize()

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(all_decimals)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
