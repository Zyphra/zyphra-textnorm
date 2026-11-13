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
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ro.graph_utils import (
    RO_ALPHA,
    RO_DASH,
    build_number_transducer,
    to_name_token,
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Romanian cardinals, e.g.
        "155" -> tokens { name: "o sută cincizeci și cinci" }
        "-5" -> tokens { name: "minus cinci" }
        "~50" -> tokens { name: "aproximativ cincizeci" }
        "±5" -> tokens { name: "plus-minus cinci" }
        "5-10" -> tokens { name: "cinci la zece" }
        "3:1" -> tokens { name: "trei la unu" }
        "x^2" -> tokens { name: "x la pătrat" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        # Build number transducers for different grammatical genders/roles
        self.cardinal_numbers = build_number_transducer(gender="masc")
        self.cardinal_numbers_masc_adj = build_number_transducer(gender="masc_adj")
        self.cardinal_numbers_neut = build_number_transducer(gender="neut")
        self.cardinal_numbers_neut_adj = build_number_transducer(gender="neut_adj")
        self.cardinal_numbers_fem = build_number_transducer(gender="fem")
        self.cardinal_numbers_fem_adj = build_number_transducer(gender="fem_adj")

        # Single digit 0-9
        self.digit = pynini.string_map([
            ("0", "zero"),
            ("1", "unu"),
            ("2", "doi"),
            ("3", "trei"),
            ("4", "patru"),
            ("5", "cinci"),
            ("6", "șase"),
            ("7", "șapte"),
            ("8", "opt"),
            ("9", "nouă"),
        ]).optimize()

        # Digits sequence read one by one (identifiers, leading zero)
        single_digit_space = self.digit + pynutil.insert(" ")
        self.serial_digits = (
            pynini.closure(single_digit_space, 1) + self.digit
        ).optimize()

        # Numbers with leading zero (e.g. 007 -> zero zero șapte, 01 -> zero unu)
        leading_zero = pynini.accep("0") + pynini.closure(NEMO_DIGIT, 1)
        serial_with_leading_zero = leading_zero @ self.serial_digits

        # All numbers without tokens wrapper
        self.all_nums_no_tokens = (self.cardinal_numbers | serial_with_leading_zero).optimize()

        # Negative numbers: -5, −5 -> minus cinci
        minus_prefix = pynutil.delete(pynini.union("-", "−")) + pynutil.insert("minus ")
        neg_cardinal = minus_prefix + self.cardinal_numbers

        # Approximate numbers: ~50 -> aproximativ cincizeci
        approx_prefix = pynutil.delete("~") + pynutil.insert("aproximativ ")
        approx_cardinal = approx_prefix + self.cardinal_numbers

        # Plus-minus: ±5 -> plus-minus cinci
        plus_minus_prefix = pynutil.delete("±") + pynutil.insert("plus-minus ")
        plus_minus_cardinal = plus_minus_prefix + self.cardinal_numbers

        # Cardinal range: 5-10, 10–20 -> cinci la zece, zece la douăzeci
        opt_dash_space = pynini.closure(pynutil.delete(" "), 0, 1)
        range_cardinal = (
            self.cardinal_numbers
            + opt_dash_space
            + pynini.cross(RO_DASH, " la ")
            + opt_dash_space
            + self.cardinal_numbers
        )

        # Ratios / scores: 3:1, 2:0 -> trei la unu, doi la zero
        ratio_graph = (
            self.cardinal_numbers
            + pynini.cross(":", " la ")
            + self.cardinal_numbers
        )

        # Arithmetic operations: 5 + 3, 10 - 4, 5 × 3, 10 ÷ 2, 2 = 2
        arith_op = pynini.union(
            pynini.cross("+", "plus"),
            pynini.cross("-", "minus"),
            pynini.cross("−", "minus"),
            pynini.cross("×", "ori"),
            pynini.cross("*", "ori"),
            pynini.cross("÷", "împărțit la"),
            pynini.cross("/", "împărțit la"),
            pynini.cross("=", "egal cu"),
        )
        arithmetic_graph = (
            self.cardinal_numbers
            + pynutil.delete(pynini.closure(" ", 0, 1))
            + pynutil.insert(" ")
            + arith_op
            + pynutil.insert(" ")
            + pynutil.delete(pynini.closure(" ", 0, 1))
            + self.cardinal_numbers
        )
        spaced_subtraction = (
            self.cardinal_numbers
            + pynini.cross(" - ", " minus ")
            + self.cardinal_numbers
        )

        # Powers: x^2 -> x la pătrat, y^3 -> y la cub, 2^3 -> doi la puterea a treia
        var_char = RO_ALPHA
        square = pynini.cross("^2", " la pătrat")
        cube = pynini.cross("^3", " la cub")
        other_power = pynutil.delete("^") + pynutil.insert(" la puterea ") + self.cardinal_numbers_fem
        power_graph = (
            (var_char | self.cardinal_numbers)
            + (square | cube | other_power)
        )

        # Serial alphanumeric strings (e.g. A4, BA249, COVID-19, AB-123-CD, v2.0)
        alpha_seq = pynini.closure(RO_ALPHA, 1)
        dash_del = pynini.cross("-", " liniuță ")
        alpha_digit = alpha_seq + pynutil.insert(" ") + self.cardinal_numbers
        digit_alpha = self.cardinal_numbers + pynutil.insert(" ") + alpha_seq
        serial_compound = (
            alpha_seq
            + dash_del
            + self.cardinal_numbers
            + dash_del
            + alpha_seq
        )
        serial_covid = pynini.accep("COVID") + pynutil.delete("-") + pynutil.insert(" ") + self.cardinal_numbers
        # Version numbers: "v2.0" -> "v doi punct zero"
        v_pref = pynini.union("v", "V") + pynutil.insert(" ")
        num_code = (pynini.closure(NEMO_DIGIT, 1, 4) @ self.cardinal_numbers) | self.digit
        dot_pt = pynini.cross(".", " punct ")
        version_dotted = (
            pynini.closure(v_pref, 0, 1)
            + num_code
            + dot_pt
            + num_code
            + pynini.closure(dot_pt + num_code, 0, 3)
        )
        serial_graph = (serial_compound | serial_covid | version_dotted | alpha_digit | digit_alpha).optimize()

        composite = (
            pynutil.add_weight(ratio_graph, 0.9)
            | pynutil.add_weight(power_graph, 0.9)
            | pynutil.add_weight(range_cardinal, 0.93)
            | pynutil.add_weight(spaced_subtraction, 0.92)
            | pynutil.add_weight(arithmetic_graph, 0.95)
            | pynutil.add_weight(approx_cardinal, 0.95)
            | pynutil.add_weight(plus_minus_cardinal, 0.95)
            | pynutil.add_weight(neg_cardinal, 0.98)
            | pynutil.add_weight(self.all_nums_no_tokens, 1.05)
            | pynutil.add_weight(serial_graph, 1.1)
        ).optimize()
        self.fst = to_name_token(composite)
