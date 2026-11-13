# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import (
    MINUS,
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.en.graph_utils import NEMO_SIGMA


def _build_cardinal_maps():
    """Generates full Modern Greek cardinal transductions for numbers 0-999 (neuter & feminine)."""
    units = {0: "μηδέν", 1: "ένα", 2: "δύο", 3: "τρία", 4: "τέσσερα", 5: "πέντε", 6: "έξι", 7: "επτά", 8: "οκτώ", 9: "εννέα"}
    teens = {10: "δέκα", 11: "έντεκα", 12: "δώδεκα", 13: "δεκατρία", 14: "δεκατέσσερα", 15: "δεκαπέντε", 16: "δεκαέξι", 17: "δεκαεπτά", 18: "δεκαοκτώ", 19: "δεκαεννέα"}
    tens = {20: "είκοσι", 30: "τριάντα", 40: "σαράντα", 50: "πενήντα", 60: "εξήντα", 70: "εβδομήντα", 80: "ογδόντα", 90: "ενενήντα"}
    hundreds = {100: "εκατό", 200: "διακόσια", 300: "τριακόσια", 400: "τετρακόσια", 500: "πεντακόσια", 600: "εξακόσια", 700: "επτακόσια", 800: "οκτακόσια", 900: "εννιακόσια"}

    fem_units = dict(units)
    fem_units[1] = "μία"
    fem_units[3] = "τρεις"
    fem_units[4] = "τέσσερις"

    fem_teens = dict(teens)
    fem_teens[13] = "δεκατρείς"
    fem_teens[14] = "δεκατέσσερις"

    fem_hundreds = dict(hundreds)
    fem_hundreds[200] = "διακόσιες"
    fem_hundreds[300] = "τριακόσιες"
    fem_hundreds[400] = "τετρακόσιες"
    fem_hundreds[500] = "πεντακόσιες"
    fem_hundreds[600] = "εξακόσιες"
    fem_hundreds[700] = "επτακόσιες"
    fem_hundreds[800] = "οκτακόσιες"
    fem_hundreds[900] = "εννιακόσιες"

    pairs = []
    fem_pairs = []

    for i in range(1000):
        parts = []
        h = (i // 100) * 100
        rem = i % 100
        if h > 0:
            if h == 100 and rem > 0:
                parts.append("εκατόν")
            else:
                parts.append(hundreds[h])
        if rem > 0 or i == 0:
            if rem in teens:
                parts.append(teens[rem])
            elif rem < 10:
                parts.append(units[rem])
            else:
                t = (rem // 10) * 10
                u = rem % 10
                parts.append(tens[t])
                if u > 0:
                    parts.append(units[u])
        pairs.append((str(i), " ".join(parts)))

        if i > 0:
            fparts = []
            if h > 0:
                if h == 100 and rem > 0:
                    fparts.append("εκατόν")
                else:
                    fparts.append(fem_hundreds[h])
            if rem > 0:
                if rem in fem_teens:
                    fparts.append(fem_teens[rem])
                elif rem < 10:
                    fparts.append(fem_units[rem])
                else:
                    t = (rem // 10) * 10
                    u = rem % 10
                    fparts.append(tens[t])
                    if u > 0:
                        fparts.append(fem_units[u])
            fem_pairs.append((str(i), " ".join(fparts)))

    return pairs, fem_pairs


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Greek cardinal numbers:
        "10" -> δέκα
        "100" -> εκατό
        "105" -> εκατόν πέντε
        "1000" -> χίλια
        "2000" -> δύο χιλιάδες
        "21000" -> είκοσι μία χιλιάδες
        "1000000" -> ένα εκατομμύριο
        "-12" -> μείον δώδεκα
        "~50" -> περίπου πενήντα
        "±5" -> συν πλην πέντε
        "10-20" -> δέκα έως είκοσι
        "007" -> μηδέν μηδέν επτά
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        pairs, fem_pairs = _build_cardinal_maps()
        non_zero_pairs = [p for p in pairs if p[0] != "0"]

        card_0_999 = pynini.string_map(pairs)
        card_1_999 = pynini.string_map(non_zero_pairs)
        card_fem_1_999 = pynini.string_map(fem_pairs)

        pad_3 = NEMO_DIGIT ** 3 @ (pynutil.delete("000") | pynini.closure(pynutil.delete("0")) + card_1_999)

        # 1,000 - 999,999 (Thousands)
        # 1000 -> χίλια; 1001-1999 -> χίλια <rem>
        one_thousand_alone = pynini.cross("1000", "χίλια")
        one_thousand_rem = pynini.cross("1", "χίλια ") + pad_3
        # 2,000 - 999,999: feminine prefix + χιλιάδες [+ remainder]
        # (also accept neuter prefix for robust fallback)
        count_thousands = card_fem_1_999
        lead_thousands = pynini.difference(pynini.closure(NEMO_DIGIT, 1, 3), "1") @ count_thousands
        multi_thousands = (lead_thousands + pynini.cross("000", " χιλιάδες")) | (
            lead_thousands + pynutil.insert(" χιλιάδες ") + pad_3
        )
        card_thousands = one_thousand_alone | one_thousand_rem | multi_thousands

        # Combined 0 - 999,999
        card_0_999999 = card_0_999 | card_thousands

        # Padded 6 digits for millions remainder
        pad_6 = NEMO_DIGIT ** 6 @ (
            pynutil.delete("000000") | pynini.closure(pynutil.delete("0")) + (card_1_999 | card_thousands)
        )

        # 1,000,000 - 999,999,999 (Millions)
        one_million_alone = pynini.cross("1000000", "ένα εκατομμύριο")
        one_million_rem = pynini.cross("1", "ένα εκατομμύριο ") + pad_6
        lead_millions = pynini.difference(pynini.closure(NEMO_DIGIT, 1, 3), "1") @ card_1_999
        multi_millions = (lead_millions + pynini.cross("000000", " εκατομμύρια")) | (
            lead_millions + pynutil.insert(" εκατομμύρια ") + pad_6
        )
        card_millions = one_million_alone | one_million_rem | multi_millions

        # Combined 0 - 999,999,999
        card_0_999999999 = card_0_999999 | card_millions

        # Padded 9 digits for billions remainder
        pad_9 = NEMO_DIGIT ** 9 @ (
            pynutil.delete("000000000")
            | pynini.closure(pynutil.delete("0")) + (card_1_999 | card_thousands | card_millions)
        )

        # 1,000,000,000 - 999,999,999,999 (Billions)
        one_billion_alone = pynini.cross("1000000000", "ένα δισεκατομμύριο")
        one_billion_rem = pynini.cross("1", "ένα δισεκατομμύριο ") + pad_9
        lead_billions = pynini.difference(pynini.closure(NEMO_DIGIT, 1, 3), "1") @ card_1_999
        multi_billions = (lead_billions + pynini.cross("000000000", " δισεκατομμύρια")) | (
            lead_billions + pynutil.insert(" δισεκατομμύρια ") + pad_9
        )
        card_billions = one_billion_alone | one_billion_rem | multi_billions

        # Combined 0 - 999,999,999,999
        card_0_999999999999 = card_0_999999999 | card_billions

        # 1,000,000,000,000+ (Trillions)
        one_trillion_alone = pynini.cross("1000000000000", "ένα τρισεκατομμύριο")
        pad_12 = NEMO_DIGIT ** 12 @ (
            pynutil.delete("000000000000")
            | pynini.closure(pynutil.delete("0")) + (card_1_999 | card_thousands | card_millions | card_billions)
        )
        lead_trillions = pynini.difference(pynini.closure(NEMO_DIGIT, 1, 3), "1") @ card_1_999
        card_trillions = (
            one_trillion_alone
            | pynini.cross("1", "ένα τρισεκατομμύριο ") + pad_12
            | lead_trillions + pynutil.insert(" τρισεκατομμύρια ") + pad_12
        )

        pure_cardinal = (card_0_999999999999 | card_trillions).optimize()

        # Digit by digit for serials / leading zeros
        single_digit_pairs = [
            ("0", "μηδέν"), ("1", "ένα"), ("2", "δύο"), ("3", "τρία"), ("4", "τέσσερα"),
            ("5", "πέντε"), ("6", "έξι"), ("7", "επτά"), ("8", "οκτώ"), ("9", "εννέα")
        ]
        digit_trans = pynini.string_map(single_digit_pairs)
        digit_by_digit = digit_trans + pynini.closure(pynutil.insert(" ") + digit_trans)

        leading_zero = pynini.cross("0", "μηδέν") + pynini.closure(pynutil.insert(" ") + digit_trans, 1)

        # Comma/dot separated list: "1,2,3" -> "ένα, δύο, τρία"
        num_sep = pynini.union(", ", ",", " ")
        digit_list = pure_cardinal + pynini.closure(pynini.cross(num_sep, ", ") + pure_cardinal, 1)

        # Negative numbers: -12, −7
        neg_prefix = pynini.cross(MINUS, "μείον ")
        neg_cardinal = neg_prefix + pure_cardinal

        # Modifiers: ~50 -> περίπου πενήντα, ±5 -> συν πλην πέντε
        approx_prefix = pynini.cross("~", "περίπου ")
        plus_minus_prefix = pynini.cross("±", "συν πλην ")
        modified_cardinal = (approx_prefix | plus_minus_prefix) + (neg_cardinal | pure_cardinal)

        # Ranges: 10-20, 10–20, 10 - 20, 10 με 20
        range_dash = pynini.cross(pynini.union("-", "–", "—", " - ", " – ", " — "), " έως ")
        range_me = pynini.cross(" με ", " έως ")
        card_range = pure_cardinal + (range_dash | range_me) + pure_cardinal

        all_numbers = (
            pure_cardinal
            | neg_cardinal
            | modified_cardinal
            | card_range
            | leading_zero
            | digit_list
        ).optimize()

        # Only the final numeral group agrees with its noun. Coefficients of
        # millions/billions remain neuter; coefficients of χιλιάδες are feminine.
        tail_words = pynini.union(*sorted({
            word for _, spoken in pairs for word in spoken.split()
        }))
        final_group = pynini.closure(pynini.accep(" ") + tail_words) + pynini.closure(" ") + "[EOS]"
        boundary = pynini.union("[BOS]", " ")
        feminine = {
            "ένα": "μία", "τρία": "τρεις", "τέσσερα": "τέσσερις",
            "δεκατρία": "δεκατρείς", "δεκατέσσερα": "δεκατέσσερις",
            "διακόσια": "διακόσιες", "τριακόσια": "τριακόσιες",
            "τετρακόσια": "τετρακόσιες", "πεντακόσια": "πεντακόσιες",
            "εξακόσια": "εξακόσιες", "επτακόσια": "επτακόσιες",
            "οκτακόσια": "οκτακόσιες", "εννιακόσια": "εννιακόσιες", "χίλια": "χίλιες",
        }
        masculine = {
            **feminine, "ένα": "ένας", "διακόσια": "διακόσιοι", "τριακόσια": "τριακόσιοι",
            "τετρακόσια": "τετρακόσιοι", "πεντακόσια": "πεντακόσιοι", "εξακόσια": "εξακόσιοι",
            "επτακόσια": "επτακόσιοι", "οκτακόσια": "οκτακόσιοι", "εννιακόσια": "εννιακόσιοι",
            "χίλια": "χίλιοι",
        }
        def agree(forms):
            rule = pynini.cdrewrite(pynini.string_map(forms.items()), boundary, final_group, NEMO_SIGMA)
            return (pure_cardinal @ rule).optimize()

        fem_cardinal = agree(feminine)
        self.masc_cardinal = agree(masculine)

        self.pure_cardinal = pure_cardinal
        self.fem_cardinal = fem_cardinal
        self.card_fem_1_999 = card_fem_1_999
        self.digit_trans = digit_trans
        self.all_numbers = all_numbers
        self.fst = all_numbers
