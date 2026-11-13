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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.el.graph_utils import GraphFst


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying Greek telephone numbers:
        "+30 210 1234567" -> συν τριάντα δύο ένα μηδέν ένα δύο τρία τέσσερα πέντε έξι επτά
        "(021) 555-1234" -> μηδέν δύο ένα πέντε πέντε πέντε ένα δύο τρία τέσσερα
        "+1 555 123 4567" -> συν ένα πέντε πέντε πέντε ένα δύο τρία τέσσερα πέντε έξι επτά
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        digit_pairs = [
            ("0", "μηδέν"),
            ("1", "ένα"),
            ("2", "δύο"),
            ("3", "τρία"),
            ("4", "τέσσερα"),
            ("5", "πέντε"),
            ("6", "έξι"),
            ("7", "επτά"),
            ("8", "οκτώ"),
            ("9", "εννέα"),
        ]
        digit = pynini.string_map(digit_pairs)

        del_sep = pynutil.delete(pynini.closure(pynini.union(" ", "-", "(", ")", "."), 0, 1))

        # Single phone digit with optional trailing separator
        p_digit = digit + del_sep + pynutil.insert(" ")

        # Country code prefix
        plus_30 = pynini.cross("+30", "συν τριάντα ") + del_sep
        plus_any = pynini.cross("+", "συν ") + digit + del_sep + pynutil.insert(" ")
        country_code = plus_30 | plus_any

        # Sequence of 7 to 11 phone digits
        phone_body = digit + pynini.closure(del_sep + pynutil.insert(" ") + digit, 6, 12)

        # Full phone number:
        # With country code: +30 210 ...
        # Or with parentheses: (021) 555-1234
        # Or with hyphens: 210-123-4567
        phone_with_cc = country_code + phone_body

        paren_area = pynutil.delete("(") + digit + pynini.closure(del_sep + pynutil.insert(" ") + digit, 1, 4) + pynutil.delete(")") + del_sep + pynutil.insert(" ") + phone_body
        hyphen_phone = digit + pynini.closure(pynutil.insert(" ") + digit, 1, 3) + pynutil.delete("-") + pynutil.insert(" ") + digit + pynini.closure(del_sep + pynutil.insert(" ") + digit, 5, 8)

        all_phones = (phone_with_cc | paren_area | hyphen_phone).optimize()
        self.fst = (all_phones | pynutil.add_weight(international_telephone(digit, "συν"), -0.1)).optimize()
