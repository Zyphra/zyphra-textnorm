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
from nemo_text_processing.text_normalization.el.taggers.cardinal import (
    CardinalFst,
    _build_cardinal_maps,
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Greek decimals and grouped numbers:
        "3,14" -> τρία κόμμα δεκατέσσερα
        "3.14" -> τρία κόμμα δεκατέσσερα
        "3.5" -> τρία κόμμα πέντε
        "0,05" -> μηδέν κόμμα μηδέν πέντε
        "-0,25" -> μείον μηδέν κόμμα είκοσι πέντε
        "1.000.000" -> ένα εκατομμύριο
        "1.234,56" -> χίλια διακόσια τριάντα τέσσερα κόμμα πενήντα έξι
        "2.5M" -> δύο κόμμα πέντε εκατομμύρια
        "50k" -> πενήντα χιλιάδες
        "0.2 εκατομμύριο" -> μηδέν κόμμα δύο εκατομμύριο
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)

        pure_cardinal = cardinal.pure_cardinal
        digit_trans = cardinal.digit_trans

        pairs, _ = _build_cardinal_maps()
        pairs_0_99 = [p for p in pairs if len(p[0]) <= 2]
        two_digit_map = pynini.string_map(pairs_0_99)

        # Fractional part:
        # 1 digit: 0-9
        frac_1 = NEMO_DIGIT @ digit_trans
        # 2 digits with leading zero: "05" -> "μηδέν πέντε"
        frac_2_zero = pynini.cross("0", "μηδέν ") + (NEMO_DIGIT @ digit_trans)
        # 2 digits normal: "14" -> "δεκατέσσερα", "50" -> "πενήντα", "99" -> "ενενήντα εννέα"
        frac_2_num = (pynini.closure(NEMO_DIGIT, 2, 2) @ two_digit_map)
        # multi-digits (3+): digit by digit, e.g. "1415" -> "ένα τέσσερα ένα πέντε"
        frac_multi = digit_trans + pynini.closure(pynutil.insert(" ") + digit_trans, 2)

        frac_part = (frac_2_zero | frac_2_num | frac_1 | frac_multi).optimize()

        # Decimal point: "," or "."
        dec_point = pynini.cross(pynini.union(",", "."), " κόμμα ")

        # Decimals: <integer> κόμμα <fraction>
        decimal_core = pure_cardinal + dec_point + frac_part

        # Negative decimals: -0,25, −3,14
        neg_prefix = pynini.cross(MINUS, "μείον ")
        neg_decimal = neg_prefix + decimal_core

        # Grouped numbers with thousand separators:
        # Greek: 1.000.000 or 1 000 000
        # Anglo: 1,000,000
        del_dot = pynutil.delete(".")
        del_space = pynutil.delete(" ")
        del_comma = pynutil.delete(",")

        d1_3 = pynini.closure(NEMO_DIGIT, 1, 3)
        d3 = pynini.closure(NEMO_DIGIT, 3, 3)

        ungroup_dot = d1_3 + pynini.closure(del_dot + d3, 1)
        ungroup_space = d1_3 + pynini.closure(del_space + d3, 1)
        ungroup_comma = d1_3 + pynini.closure(del_comma + d3, 1)

        grouped_int_dot = ungroup_dot @ pure_cardinal
        grouped_int_space = ungroup_space @ pure_cardinal
        grouped_int_comma = ungroup_comma @ pure_cardinal

        grouped_integers = grouped_int_dot | grouped_int_space | grouped_int_comma
        self.ungroup_numbers = (ungroup_dot | ungroup_space | ungroup_comma).optimize()

        # Grouped numbers with decimal part:
        # "1.234,56" or "1 234,56" or "1,234.56"
        grouped_decimal = (
            (ungroup_dot @ pure_cardinal) + pynini.cross(",", " κόμμα ") + frac_part
            | (ungroup_space @ pure_cardinal) + pynini.cross(pynini.union(",", "."), " κόμμα ") + frac_part
            | (ungroup_comma @ pure_cardinal) + pynini.cross(".", " κόμμα ") + frac_part
        )

        all_decimals = (decimal_core | neg_decimal | grouped_decimal | grouped_integers).optimize()

        # Shorthand quantities:
        # "0.2 εκατομμύριο", "30.2 δισεκατομμύρια", "10 εκατομμύρια"
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        num_for_qty = decimal_core | pure_cardinal

        qty_words = pynini.string_map(
            [
                ("εκατομμύριο", "εκατομμύριο"),
                ("εκατομμύρια", "εκατομμύρια"),
                ("εκατ.", "εκατομμύρια"),
                ("εκατ", "εκατομμύρια"),
                ("δισεκατομμύριο", "δισεκατομμύριο"),
                ("δισεκατομμύρια", "δισεκατομμύρια"),
                ("δισ.", "δισεκατομμύρια"),
                ("δισ", "δισεκατομμύρια"),
                ("τρισεκατομμύριο", "τρισεκατομμύριο"),
                ("τρισεκατομμύρια", "τρισεκατομμύρια"),
            ]
        )
        qty_phrase = num_for_qty + pynutil.delete(" ") + pynutil.insert(" ") + qty_words

        # Shorthand letter suffixes: 50k, 2.5M, 1B
        shorthand_suffixes = pynini.string_map(
            [
                ("k", " χιλιάδες"),
                ("K", " χιλιάδες"),
                ("M", " εκατομμύρια"),
                ("B", " δισεκατομμύρια"),
            ]
        )
        shorthand_num = num_for_qty + opt_space + shorthand_suffixes

        # Modifiers: ~ and ±
        approx_prefix = pynini.cross("~", "περίπου ")
        plus_minus_prefix = pynini.cross("±", "συν πλην ")
        mod_prefix = approx_prefix | plus_minus_prefix
        modified_decimal = mod_prefix + (all_decimals | shorthand_num | qty_phrase)

        graph = (
            all_decimals
            | qty_phrase
            | shorthand_num
            | modified_decimal
        ).optimize()

        self.decimal_core = decimal_core
        self.grouped_integers = grouped_integers
        self.all_decimals = all_decimals
        self.fst = graph
