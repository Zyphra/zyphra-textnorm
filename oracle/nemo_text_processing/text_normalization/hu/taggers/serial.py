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
from nemo_text_processing.text_normalization.hu.graph_utils import HU_ALPHA, HU_LOWER, HU_UPPER
from nemo_text_processing.text_normalization.hu.utils import get_abs_path


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying Hungarian alphanumeric codes and versions, e.g.
        "A4" -> name: "A négy"
        "BA249" -> name: "B A kétszáznegyvenkilenc"
        "COVID-19" -> name: "COVID tizenkilenc"
        "v2.0" -> name: "v kettő pont nulla"
        "3.11.2" -> name: "három pont tizenegy pont kettő"
        "x^2" -> name: "x a négyzeten"
        "y^3" -> name: "y a köbön"
    """

    def __init__(self, cardinal: GraphFst, ordinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)

        digit = pynini.invert(pynini.string_file(get_abs_path("data/number/digit.tsv"))).optimize()
        zero = pynini.invert(pynini.string_file(get_abs_path("data/number/zero.tsv"))).optimize()
        single_digit = pynini.union(digit, zero).optimize()
        digit_seq = (single_digit + pynini.closure(insert_space + single_digit)).optimize()

        leading_zero = ("0" + pynini.closure(NEMO_DIGIT, 1)) @ digit_seq
        short_cardinal = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ cardinal.graph
        zero_only = pynini.accep("0") @ zero
        long_digits = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 3)) @ digit_seq
        num_part = pynini.union(zero_only, short_cardinal, leading_zero, long_digits).optimize()

        # Spell 1-3 uppercase letters letter-by-letter (e.g. BA249 -> B A ...), while 4+ letter words
        # (COVID, Boeing) or mixed/lower-case words stay whole.
        upper_spelled = (HU_UPPER + pynini.closure(insert_space + HU_UPPER, 0, 2)).optimize()
        single_lower = HU_LOWER
        word_keep = pynini.union(
            pynini.closure(HU_UPPER, 4),
            pynini.closure(HU_LOWER, 2),
            HU_UPPER + pynini.closure(HU_LOWER, 1),
            pynini.closure(HU_ALPHA, 2) - pynini.closure(HU_UPPER, 2, 3),
        ).optimize()
        alpha_part = pynini.union(
            pynutil.add_weight(upper_spelled, -0.01),
            single_lower,
            word_keep,
        ).optimize()

        sep = pynini.cross(pynini.union("-", "/"), " ")

        alpha_then_num = alpha_part + (insert_space | sep) + num_part
        num_then_alpha = num_part + (insert_space | sep) + alpha_part
        tail_after_num = pynini.closure(
            (insert_space | sep) + alpha_part + pynini.closure((insert_space | sep) + num_part, 0, 1)
        )
        tail_after_alpha = pynini.closure(
            (insert_space | sep) + num_part + pynini.closure((insert_space | sep) + alpha_part, 0, 1)
        )

        alphanum = pynini.union(
            alpha_then_num + tail_after_num,
            num_then_alpha + tail_after_alpha,
        ).optimize()

        # Version strings: "v2.0", "v3.11.2", and 3-part dotted versions "3.11.2" (4-part stays IP in TelephoneFst).
        ver_num = pynini.union(zero_only, short_cardinal, leading_zero).optimize()
        dot_pont = pynini.cross(".", " pont ")
        v_prefix = pynini.union("v", "V") + insert_space
        v_version = v_prefix + ver_num + pynini.closure(dot_pont + ver_num, 1, 3)
        multi_dot_version = ver_num + dot_pont + ver_num + dot_pont + ver_num

        # Variable powers: "x^2" -> "x a négyzeten", "y^3" -> "y a köbön", "x^4" -> "x a negyedik hatványon"
        var_base = (HU_ALPHA | pynini.union("α", "β", "γ", "δ", "π", "θ", "λ", "μ", "σ", "ω")) + pynini.closure(
            HU_ALPHA, 0, 3
        )
        power_2_3 = pynini.cross("^2", " a négyzeten") | pynini.cross("^3", " a köbön")
        var_power = var_base + power_2_3
        if ordinal is not None:
            vowel_init_exp = pynini.union("1", "5") | ("1" + (NEMO_DIGIT**3))
            other_exp = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) - pynini.union("1", "2", "3", "5")
            ord_exp_az = pynini.cross("^", " az ") + (vowel_init_exp @ ordinal.bare_ordinals) + pynutil.insert(" hatványon")
            ord_exp_a = pynini.cross("^", " a ") + (other_exp @ ordinal.bare_ordinals) + pynutil.insert(" hatványon")
            var_power |= var_base + (ord_exp_az | ord_exp_a)

        graph = pynini.union(
            pynutil.add_weight(v_version, -0.05),
            pynutil.add_weight(var_power, -0.05),
            multi_dot_version,
            alphanum,
        ).optimize()

        self.graph = convert_space(graph).optimize()
        self.fst = (pynutil.insert("name: \"") + self.graph + pynutil.insert("\"")).optimize()
