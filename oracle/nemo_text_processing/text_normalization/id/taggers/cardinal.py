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

# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.id.utils import get_abs_path


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Indonesian cardinals (CLDR id %spellout-cardinal), e.g.
        "1.945" -> cardinal { integer: "seribu sembilan ratus empat puluh lima" }
        "-12" -> cardinal { negative: "true" integer: "dua belas" }
        "~50" -> cardinal { negative: "sekitar" integer: "lima puluh" }
        "±5" -> cardinal { negative: "kurang lebih" integer: "lima" }
        "2020-2021" -> cardinal { integer: "dua ribu dua puluh sampai dua ribu dua puluh satu" }
        "3:1" -> cardinal { integer: "tiga banding satu" }
        "x^2" -> cardinal { integer: "x kuadrat" }
    "." groups thousands; numbers up to 999 triliun are read.

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

        # single digit 0-9 read on its own (decimals, telephone numbers)
        self.digit = (zero | digit).optimize()

        # "01"-"99"
        tens = (
            pynutil.delete("0") + digit
            | teen
            | ties + pynutil.delete("0")
            | ties + insert_space + digit
        )
        hundred = pynini.cross("1", "seratus") | (
            pynini.difference(NEMO_DIGIT, pynini.union("0", "1")) @ digit
        ) + pynutil.insert(" ratus")
        # "001"-"999"
        three = hundred + (pynutil.delete("00") | insert_space + tens) | pynutil.delete("0") + tens

        def group(word: str) -> "pynini.FstLike":
            return three + pynutil.insert(f" {word} ") | pynutil.delete("000")

        thousand = (
            pynini.cross("001", "seribu ")
            | (pynini.difference(NEMO_DIGIT**3, "001") @ three) + pynutil.insert(" ribu ")
            | pynutil.delete("000")
        )
        last = three + pynutil.insert(" ") | pynutil.delete("000")
        graph = group("triliun") + group("miliar") + group("juta") + thousand + last

        pad = pynini.cdrewrite(pynini.closure(pynutil.insert("0")), "[BOS]", "", NEMO_SIGMA)
        strip_trailing_space = pynini.cdrewrite(pynutil.delete(" "), "", "[EOS]", NEMO_SIGMA)
        number = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 14)
        self.graph = (number @ pad @ NEMO_DIGIT**15 @ graph @ strip_trailing_space | zero).optimize()

        # 1-999 without leading zeros
        self.graph_hundred = (((NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)) @ self.graph).optimize()

        # "1.000.000" -> "satu juta"
        grouped = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(".") + NEMO_DIGIT**3, 1, 4)
        )
        self.graph_with_sep = (self.graph | grouped @ self.graph).optimize()

        number_range = self.graph_with_sep + pynini.cross(pynini.union("-", "–"), " sampai ") + self.graph_with_sep
        # "3:1" -> "tiga banding satu" (ratios and scores; valid clock times are taken by the time grammar first)
        digits = self.digit + pynini.closure(insert_space + self.digit)
        ratio = self.graph_with_sep + pynini.cross(":", " banding ") + (
            self.graph_with_sep | pynutil.add_weight(digits, 0.1)
        )
        number_range |= pynutil.add_weight(ratio, 0.1)

        leading_zero = pynini.compose(pynini.accep("0") + pynini.closure(NEMO_DIGIT, 1), digits)
        too_long = pynini.compose(pynini.closure(NEMO_DIGIT, 16), digits)
        digit_by_digit = (leading_zero | too_long).optimize()

        # "1,2,3": "," is the decimal separator (only once), so 2+ commas between numbers are a list
        short = pynini.compose(NEMO_DIGIT ** (1, 3), self.graph)
        number_list = short + pynini.closure(pynini.cross(",", ", ") + short, 2)

        optional_prefix = pynini.closure(
            (pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), '"true" '))
            | (pynini.cross("~", 'negative: "sekitar" ') + pynini.closure(pynutil.delete(" "), 0, 1))
            | (pynini.cross("±", 'negative: "kurang lebih" ') + pynini.closure(pynutil.delete(" "), 0, 1)),
            0,
            1,
        )
        final_graph = (
            optional_prefix + pynutil.insert('integer: "') + self.graph_with_sep + pynutil.insert('"')
            | pynutil.insert('integer: "') + (number_range | digit_by_digit | number_list) + pynutil.insert('"')
        )
        self.fst = self.add_tokens(final_graph).optimize()

        # Fallback for tokens mixing letters and digits, multi-dot versions/IPs, or variable powers ("v2.0",
        # "COVID-19", "BA249", "192.168.1.1", "x^2", "y^3"): letters stay, digit runs are read as numbers, "."
        # between digits is "titik" and other separators (- / : _) become a space. Weighted below specific classes.
        alpha_piece = pynini.closure(NEMO_ALPHA, 1)
        num_piece = (self.graph | digit_by_digit).optimize()
        dot_num = num_piece + pynini.closure(pynini.cross(".", " titik ") + num_piece)
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

        # Variable powers: "x^2" -> "x kuadrat", "y^3" -> "y kubik", "a^4" -> "a pangkat empat", "x^-2" -> "x pangkat negatif dua"
        power_exp = (
            pynini.cross("^2", " kuadrat")
            | pynini.cross("^3", " kubik")
            | pynini.cross("²", " kuadrat")
            | pynini.cross("³", " kubik")
            | (
                pynini.cross("^", " pangkat ")
                + pynini.closure(pynini.cross(pynini.union("-", "−"), "negatif "), 0, 1)
                + (pynini.difference(pynini.closure(NEMO_DIGIT, 1, 4), pynini.union("2", "3")) @ self.graph)
            )
        )
        variable_power = (NEMO_ALPHA + power_exp).optimize()

        self.serial = self.add_tokens(
            pynutil.insert('integer: "') + (serial | variable_power) + pynutil.insert('"')
        ).optimize()
