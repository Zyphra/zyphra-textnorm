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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Danish telephone numbers.
    Handles:
      - Separated 8-digit Danish numbers in pairs: "12 34 56 78" -> "tolv fireogtredive seksoghalvtreds otteoghalvfjerds"
      - Country code: "+45 12 34 56 78" -> "plus femogfyrre tolv fireogtredive seksoghalvtreds otteoghalvfjerds"
      - General international numbers: "+1 555 123 4567", "(021) 555-1234"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # 2-digit reading for pairs
        pair_num = cardinal.num_1_to_999_neuter | (
            pynini.cross("0", "nul ") + cardinal.single_digit
        )

        single_digit = cardinal.single_digit

        # Danish 8-digit numbers: 4 pairs of 2 digits
        # e.g. "12 34 56 78" or "12345678"
        p1 = NEMO_DIGIT**2 @ pair_num
        p2 = NEMO_DIGIT**2 @ pair_num
        p3 = NEMO_DIGIT**2 @ pair_num
        p4 = NEMO_DIGIT**2 @ pair_num

        sp_or_dash = pynini.closure(pynutil.delete(pynini.union(" ", "-")), 0, 1)

        eight_digits = (
            p1
            + sp_or_dash
            + pynutil.insert(" ")
            + p2
            + sp_or_dash
            + pynutil.insert(" ")
            + p3
            + sp_or_dash
            + pynutil.insert(" ")
            + p4
        )

        # Danish country code "+45" / "0045"
        country_dk = (
            pynini.cross("+45", "plus femogfyrre ")
            | pynini.cross("0045", "nul nul femogfyrre ")
        ) + opt_sp

        phone_chars = pynini.closure(NEMO_DIGIT | pynini.union(" ", "-"))
        separated_number = phone_chars + pynini.union(" ", "-") + phone_chars
        phone_dk = country_dk + eight_digits | (separated_number @ eight_digits)

        # General international numbers: e.g. "+1 555 123 4567"
        country_intl = pynini.cross("+", "plus ") + (
            (NEMO_DIGIT**2 @ pair_num) | single_digit
        ) + pynutil.delete(" ") + pynutil.insert(" ")

        digits_grouped = (
            (NEMO_DIGIT**3 @ (single_digit + insert_space + single_digit + insert_space + single_digit))
            | (NEMO_DIGIT**4 @ (pair_num + insert_space + pair_num))
            | (NEMO_DIGIT**2 @ pair_num)
        )

        intl_phone = (
            country_intl
            + digits_grouped
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + digits_grouped
            + pynutil.delete(" ")
            + pynutil.insert(" ")
            + digits_grouped
        )

        # Bracketed area code: e.g. "(021) 555-1234"
        bracket_code = (
            pynutil.delete("(")
            + (single_digit + insert_space + single_digit + insert_space + single_digit)
            + pynutil.delete(")")
            + opt_sp
            + pynutil.insert(" ")
            + digits_grouped
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + digits_grouped
        )

        all_phones = (phone_dk | intl_phone | bracket_code | international_telephone(single_digit, "plus")).optimize()

        self.graph = all_phones

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
