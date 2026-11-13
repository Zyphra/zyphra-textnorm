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

from nemo_text_processing.text_normalization.vi.graph_utils import NEMO_DIGIT, GraphFst, insert_space
from nemo_text_processing.text_normalization.vi.utils import get_abs_path


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Vietnamese telephone numbers, read digit by digit, e.g.
        "+84 912 345 678" -> telephone { country_code: "cộng tám tư" number_part: "chín một hai, ba bốn năm, sáu bảy tám" }
        "028-3823-4567" -> telephone { number_part: "không hai tám, ba tám hai ba, bốn năm sáu bảy" }
        "0912345678" -> telephone { number_part: "không chín một hai, ba bốn năm, sáu bảy tám" }

    Written groups (separated by space, "-" or ".") are spoken separated by ", ". Only phone-shaped strings are
    accepted: a leading "+<country code>", or a leading "0" with 9-11 digits in total, so that cardinals, dates,
    times and decimals are not taken over. Unseparated numbers are grouped as 4-3-3 (10 local digits),
    3-4-4 (11 local digits), 3-3-3 (9 digits after +84) or 2-4-4 (10 digits after +84).
    Country code 84 reads "tám tư"; other country codes are read digit by digit.

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv")) | pynini.string_file(
            get_abs_path("data/numbers/zero.tsv")
        )
        digit = digit.optimize()

        def spell(n_min: int, n_max: int = None) -> "pynini.FstLike":
            n_max = n_min if n_max is None else n_max
            return digit + pynini.closure(insert_space + digit, n_min - 1, n_max - 1)

        sep_chars = pynini.union(" ", "-", ".")
        group_sep = pynini.cross(sep_chars, ", ")

        # Digits read one by one, written separators become ", ".
        spelled_groups = digit + pynini.closure((insert_space + digit) | (group_sep + digit))

        def digit_count(n_min: int, n_max: int) -> "pynini.FstLike":
            return (
                pynini.closure(pynini.closure(sep_chars) + NEMO_DIGIT, n_min, n_max) + pynini.closure(sep_chars)
            ).optimize()

        def group(n_min: int, n_max: int) -> "pynini.FstLike":
            return pynini.closure(NEMO_DIGIT, n_min, n_max)

        # Local numbers with a leading 0: 0912 345 678, 028-3823-4567, 0912.345.678.
        zero = pynini.accep("0")
        local_shape = zero + group(1, 3) + pynini.closure(sep_chars + group(2, 4), 1, 4)
        local_shape = pynini.intersect(local_shape, digit_count(9, 11))
        local_separated = pynini.compose(local_shape, spelled_groups)
        # Unseparated local numbers: 0912345678 (4-3-3), 02838234567 (3-4-4).
        local_plain = pynini.compose(
            zero + group(9, 9), spell(4) + pynutil.insert(", ") + spell(3) + pynutil.insert(", ") + spell(3)
        ) | pynini.compose(
            zero + group(10, 10), spell(3) + pynutil.insert(", ") + spell(4) + pynutil.insert(", ") + spell(4)
        )
        # Parenthesized area-code numbers: (021) 555-1234, (415) 555-0199
        paren_area = (
            pynutil.delete("(")
            + pynini.compose(group(2, 4), spell(2, 4))
            + pynutil.delete(")")
            + pynini.closure(pynutil.delete(sep_chars), 0, 1)
            + pynutil.insert(", ")
            + pynini.compose(group(3, 4) + sep_chars + group(3, 4), spelled_groups)
        )
        local = local_separated | local_plain | paren_area
        local = pynutil.insert("number_part: \"") + local + pynutil.insert("\"")

        # International numbers: +84 912 345 678, +1-202-555-0123, +84912345678.
        known_codes = pynini.string_file(get_abs_path("data/telephone/country_code.tsv"))
        other_codes = pynini.compose(pynini.difference(group(1, 3), pynini.project(known_codes, "input")), spell(1, 3))
        country_code = (
            pynutil.delete("+")
            + pynutil.insert("country_code: \"cộng ")
            + (known_codes | other_codes)
            + pynutil.insert("\"")
        )
        intl_rest_shape = (group(1, 4) + pynini.closure(sep_chars + group(1, 4), 1, 5)) | group(6, 12)
        intl_rest_shape = pynini.intersect(intl_rest_shape, digit_count(6, 12))
        intl_separated = country_code + pynutil.delete(sep_chars) + insert_space
        intl_separated += pynutil.insert("number_part: \"") + pynini.compose(intl_rest_shape, spelled_groups)
        intl_separated += pynutil.insert("\"")

        vn_plain = (spell(3) + pynutil.insert(", ") + spell(3) + pynutil.insert(", ") + spell(3)) | (
            spell(2) + pynutil.insert(", ") + spell(4) + pynutil.insert(", ") + spell(4)
        )
        intl_plain = (
            pynutil.delete("+")
            + pynutil.insert("country_code: \"cộng ")
            + known_codes
            + pynutil.insert("\" number_part: \"")
            + vn_plain
            + pynutil.insert("\"")
        )

        graph = local | intl_separated | intl_plain
        self.fst = self.add_tokens(graph).optimize()
