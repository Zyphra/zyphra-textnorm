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

from nemo_text_processing.text_normalization.ar.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    TO_LOWER,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ar.utils import get_abs_path


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying dotted version strings, variable powers, and alphanumeric codes/serials, e.g.
        "v2.0" -> name: "في اثنان نقطة صفر"
        "3.11.2" -> name: "ثلاثة نقطة احد عشر نقطة اثنان"
        "A4" -> name: "إيه أربعة"
        "BA249" -> name: "بي إيه مئتان وتسعة وأربعون"
        "COVID-19" -> name: "COVID تسعة عشر"
        "x^2" -> name: "x تربيع"
        "y^3" -> name: "y تكعيب"

    Short Latin abbreviations (1-3 letters) are spelled letter by letter in Arabic; longer Latin words stay intact so
    brand/model names (COVID, iPhone) are preserved.
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="serial", kind="classify")

        digit_word = pynini.string_file(get_abs_path("data/number/digit.tsv")) | pynini.string_file(
            get_abs_path("data/number/zero.tsv")
        )
        digit_seq = (digit_word + pynini.closure(insert_space + digit_word)).optimize()
        leading_zero_num = (pynini.accep("0") + pynini.closure(NEMO_DIGIT, 1)) @ digit_seq
        long_num = pynini.closure(NEMO_DIGIT, 4) @ digit_seq
        short_num = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2) | "0") @ cardinal.cardinal_numbers
        serial_num = (short_num | leading_zero_num | long_num).optimize()

        letters_map = pynini.string_map(
            [
                ("a", "إيه"),
                ("b", "بي"),
                ("c", "سي"),
                ("d", "دي"),
                ("e", "إي"),
                ("f", "إف"),
                ("g", "جي"),
                ("h", "إتش"),
                ("i", "آي"),
                ("j", "جيه"),
                ("k", "كيه"),
                ("l", "إل"),
                ("m", "إم"),
                ("n", "إن"),
                ("o", "أو"),
                ("p", "بي"),
                ("q", "كيو"),
                ("r", "آر"),
                ("s", "إس"),
                ("t", "تي"),
                ("u", "يو"),
                ("v", "في"),
                ("w", "دبليو"),
                ("x", "إكس"),
                ("y", "واي"),
                ("z", "زد"),
            ]
        )
        letter_one = (letters_map | (TO_LOWER @ letters_map)).optimize()
        short_letters = (letter_one + pynini.closure(insert_space + letter_one, 0, 2)).optimize()
        long_letters = pynini.closure(NEMO_ALPHA, 4)
        alpha_seg = short_letters | long_letters

        ver_num = (short_num | leading_zero_num).optimize()
        v_prefix = (
            pynini.cross(pynini.union("v", "V"), "في ")
            + ver_num
            + pynini.closure(pynini.cross(".", " نقطة ") + ver_num, 1, 3)
        ).optimize()
        multi_dot_ver = (ver_num + pynini.closure(pynini.cross(".", " نقطة ") + ver_num, 2, 4)).optimize()

        alnum_piece = alpha_seg | serial_num
        sep_piece = pynini.cross("-", " ") | pynini.cross("/", " شرطة مائلة ")
        glued_an = alpha_seg + insert_space + serial_num
        glued_na = serial_num + insert_space + alpha_seg
        glued_ana = alpha_seg + insert_space + serial_num + insert_space + alpha_seg
        glued_nan = serial_num + insert_space + alpha_seg + insert_space + serial_num
        delim_2 = alnum_piece + sep_piece + alnum_piece + pynini.closure(sep_piece + alnum_piece, 0, 2)
        has_alpha_and_digit = (
            pynini.closure(NEMO_ALPHA | NEMO_DIGIT | "-" | "/")
            @ (NEMO_SIGMA + NEMO_ALPHA + NEMO_SIGMA)
            @ (NEMO_SIGMA + NEMO_DIGIT + NEMO_SIGMA)
        )
        alphanum_graph = (has_alpha_and_digit @ (glued_an | glued_na | glued_ana | glued_nan | delim_2)).optimize()

        # Variable powers: "x^2" -> "x تربيع", "y^3" -> "y تكعيب", "x^4" -> "x أس أربعة"
        var_base = (
            pynini.closure(NEMO_ALPHA, 1, 3)
            | pynini.union("α", "β", "γ", "δ", "θ", "λ", "μ", "π", "σ", "ω", "س", "ص", "ع", "ن")
        )
        other_exp = pynini.difference(
            ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) | "0",
            pynini.union("2", "3"),
        )
        pos_exp = ((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ cardinal.cardinal_numbers
        exp_spoken = (
            pynini.cross("^2", " تربيع")
            | pynini.cross("^3", " تكعيب")
            | (pynini.cross("^", " أس ") + (other_exp @ cardinal.cardinal_numbers))
            | (pynini.cross("^-", " أس سالب ") + pos_exp)
        )
        unit_bases = pynini.union("m", "cm", "mm", "km", "dm", "م", "سم", "مم", "كم")
        sup_spoken = pynini.difference(var_base, unit_bases) + (
            pynini.cross("²", " تربيع") | pynini.cross("³", " تكعيب")
        )
        var_power = ((var_base + exp_spoken) | sup_spoken).optimize()

        graph = v_prefix | multi_dot_ver | alphanum_graph | var_power
        self.fst = (pynutil.insert('name: "') + convert_space(graph) + pynutil.insert('"')).optimize()
