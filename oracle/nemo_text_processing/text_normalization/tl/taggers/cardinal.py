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

# Number names from Unicode CLDR release-49 (fil locale, Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.tl.graph_utils import get_linker_fst
from nemo_text_processing.text_normalization.tl.utils import get_abs_path


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Tagalog cardinals (CLDR fil %spellout-cardinal), e.g.
        "1,945" -> cardinal { integer: "isang libo siyam na daan at apatnapu't lima" }
        "-12" -> cardinal { negative: "true" integer: "labindalawa" }
        "~50" -> cardinal { negative: "humigit-kumulang" integer: "limampu" }
        "±5" -> cardinal { negative: "plus-minus" integer: "lima" }
        "2020-2021" -> cardinal { integer: "dalawang libo dalawampu hanggang dalawang libo dalawampu't isa" }
        "3:1" -> cardinal { integer: "tatlo laban sa isa" }
        "x^2" -> cardinal { integer: "x kuwadrado" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)
        zero = pynini.string_file(get_abs_path("data/numbers/zero.tsv"))
        digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        teen = pynini.string_file(get_abs_path("data/numbers/teen.tsv"))
        ties = pynini.string_file(get_abs_path("data/numbers/ties.tsv"))
        linker = get_linker_fst()

        # single digit 0-9 read on its own (decimals, telephone numbers)
        self.digit = (zero | digit).optimize()

        # "01"-"99"
        tens = (
            pynutil.delete("0") + digit
            | teen
            | (ties + pynutil.delete("0"))
            | (ties + pynutil.insert("'t ") + digit)
        )

        hundred_mult = (
            pynini.cross("1", "isang daan")
            | pynini.cross("2", "dalawang daan")
            | pynini.cross("3", "tatlong daan")
            | pynini.cross("4", "apat na daan")
            | pynini.cross("5", "limang daan")
            | pynini.cross("6", "anim na daan")
            | pynini.cross("7", "pitong daan")
            | pynini.cross("8", "walong daan")
            | pynini.cross("9", "siyam na daan")
        )

        # "001"-"999"
        three = (
            hundred_mult + (pynutil.delete("00") | (pynutil.insert(" at ") + tens))
            | pynutil.delete("0") + tens
        ).optimize()

        def scale_group(name: str):
            return (three @ linker) + pynutil.insert(f" {name} ") | pynutil.delete("000")

        last = three + pynutil.insert(" ") | pynutil.delete("000")
        graph = (
            scale_group("trilyon")
            + scale_group("bilyon")
            + scale_group("milyon")
            + scale_group("libo")
            + last
        )

        pad = pynini.cdrewrite(pynini.closure(pynutil.insert("0")), "[BOS]", "", NEMO_SIGMA)
        strip_trailing_space = pynini.cdrewrite(pynutil.delete(" "), "", "[EOS]", NEMO_SIGMA)
        number = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 14)
        self.graph = (number @ pad @ NEMO_DIGIT**15 @ graph @ strip_trailing_space | zero).optimize()

        # 1-999 without leading zeros
        self.graph_hundred = (((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ self.graph).optimize()

        # "1,000,000" or "1.000.000"
        grouped = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(pynini.union(",", ".")) + NEMO_DIGIT**3, 1, 4)
        )
        self.graph_with_sep = (self.graph | grouped @ self.graph).optimize()

        number_range = self.graph_with_sep + pynini.cross(pynini.union("-", "–"), " hanggang ") + self.graph_with_sep
        # "3:1" -> "tatlo laban sa isa" (ratios and scores)
        digits = self.digit + pynini.closure(insert_space + self.digit)
        ratio = self.graph_with_sep + pynini.cross(":", " laban sa ") + (
            self.graph_with_sep | pynutil.add_weight(digits, 0.1)
        )
        number_range |= pynutil.add_weight(ratio, 0.1)

        leading_zero = pynini.compose(pynini.accep("0") + pynini.closure(NEMO_DIGIT, 1), digits)
        too_long = pynini.compose(pynini.closure(NEMO_DIGIT, 16), digits)
        digit_by_digit = (leading_zero | too_long).optimize()

        # "1, 2, 3": lists of numbers
        short = pynini.compose(NEMO_DIGIT ** (1, 3), self.graph)
        number_list = short + pynini.closure(pynini.cross(",", ", ") + short, 2)

        optional_prefix = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true" '))
            | (pynini.cross("~", 'negative: "humigit-kumulang" ') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", 'negative: "plus-minus" ') + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )
        final_graph = (
            optional_prefix + pynutil.insert('integer: "') + self.graph_with_sep + pynutil.insert('"')
            | pynutil.insert('integer: "') + (number_range | digit_by_digit | number_list) + pynutil.insert('"')
        )
        self.fst = self.add_tokens(final_graph).optimize()

        # Fallback for tokens mixing letters and digits, multi-dot versions/IPs, or variable powers
        alpha_piece = pynini.closure(NEMO_ALPHA, 1)
        num_piece = (self.graph | digit_by_digit).optimize()
        dot_num = num_piece + pynini.closure(pynini.cross(".", " tuldok ") + num_piece)
        alnum_seg = (
            alpha_piece
            | dot_num
            | alpha_piece + pynutil.insert(" ") + dot_num
            | dot_num + pynutil.insert(" ") + alpha_piece
            | alpha_piece + pynutil.insert(" ") + dot_num + pynutil.insert(" ") + alpha_piece
            | dot_num + pynutil.insert(" ") + alpha_piece + pynutil.insert(" ") + dot_num
        ).optimize()
        delim = pynini.cross(pynini.union("-", "/", ":", "_"), " ") | pynutil.add_weight(pynini.cross(".", " "), 0.1)
        serial_body = alnum_seg + pynini.closure(delim + alnum_seg)
        has_digit = NEMO_SIGMA + NEMO_DIGIT + NEMO_SIGMA
        serial = pynini.compose(has_digit, serial_body).optimize()

        # Variable powers: "x^2" -> "x kuwadrado", "y^3" -> "y kubiko", "a^4" -> "a sa kapangyarihan ng apat"
        power_exp = (
            pynini.cross("^2", " kuwadrado")
            | pynini.cross("^3", " kubiko")
            | pynini.cross("²", " kuwadrado")
            | pynini.cross("³", " kubiko")
            | (
                pynini.cross("^", " sa kapangyarihan ng ")
                + pynini.closure(pynini.cross(pynini.union("-", "−"), "minus "), 0, 1)
                + (pynini.difference(pynini.closure(NEMO_DIGIT, 1, 4), pynini.union("2", "3")) @ self.graph)
            )
        )
        variable_power = (NEMO_ALPHA + power_exp).optimize()

        self.serial = self.add_tokens(
            pynutil.insert('integer: "') + (serial | variable_power) + pynutil.insert('"')
        ).optimize()
