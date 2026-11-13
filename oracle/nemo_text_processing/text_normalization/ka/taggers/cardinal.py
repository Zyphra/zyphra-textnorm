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
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ka.graph_utils import (
    GEORGIAN_ALPHA,
    glue_suffix,
    with_suffix,
)
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Georgian cardinals, e.g.
        0 -> cardinal { integer: "ნული" }
        15 -> cardinal { integer: "თხუთმეტი" }
        55 -> cardinal { integer: "ორმოცდათხუთმეტი" }
        -12 -> cardinal { negative: "true" integer: "თორმეტი" }
        1 000 000 -> cardinal { integer: "ერთი მილიონი" }
        007 -> cardinal { integer: "ნული ნული შვიდი" }
        5-10 -> cardinal { integer: "ხუთიდან ათამდე" }
        2020s -> cardinal { integer: "ორი ათას ოციანი წლები" }
    """

    def __init__(self, ordinal: GraphFst = None):
        super().__init__(name="cardinal", kind="classify")

        zero = pynini.cross("0", "ნული")
        digits_tsv = pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
        digits_1_9 = (NEMO_DIGIT - "0") @ digits_tsv
        digits_10_19 = (pynini.accep("1") + NEMO_DIGIT) @ digits_tsv

        # Georgian vigesimal system:
        # Base 20: 20-39 (ოცი, ოცდა + 1..19)
        # Base 40: 40-59 (ორმოცი, ორმოცდა + 1..19)
        # Base 60: 60-79 (სამოცი, სამოცდა + 1..19)
        # Base 80: 80-99 (ოთხმოცი, ოთხმოცდა + 1..19)
        exact_tens = pynini.string_file(get_abs_path("data/numbers/ties.tsv"))

        unit_1_9 = digits_1_9
        unit_11_19 = (NEMO_DIGIT - "0") @ (
            pynini.cross("1", "თერთმეტი")
            | pynini.cross("2", "თორმეტი")
            | pynini.cross("3", "ცამეტი")
            | pynini.cross("4", "თოთხმეტი")
            | pynini.cross("5", "თხუთმეტი")
            | pynini.cross("6", "თექვსმეტი")
            | pynini.cross("7", "ჩვიდმეტი")
            | pynini.cross("8", "თვრამეტი")
            | pynini.cross("9", "ცხრამეტი")
        )

        compound_20_39 = (pynini.cross("2", "ოცდა") + unit_1_9) | (pynini.cross("3", "ოცდა") + unit_11_19)
        compound_40_59 = (pynini.cross("4", "ორმოცდა") + unit_1_9) | (pynini.cross("5", "ორმოცდა") + unit_11_19)
        compound_60_79 = (pynini.cross("6", "სამოცდა") + unit_1_9) | (pynini.cross("7", "სამოცდა") + unit_11_19)
        compound_80_99 = (pynini.cross("8", "ოთხმოცდა") + unit_1_9) | (pynini.cross("9", "ოთხმოცდა") + unit_11_19)

        double_digits = exact_tens | compound_20_39 | compound_40_59 | compound_60_79 | compound_80_99
        self.double_digits = double_digits.optimize()

        one_to_99 = digits_1_9 | digits_10_19 | double_digits
        self.one_to_99 = one_to_99.optimize()

        # Hundreds:
        exact_hundreds = pynini.string_file(get_abs_path("data/numbers/hundreds.tsv"))
        hundreds_stems = pynini.string_file(get_abs_path("data/numbers/hundreds_stem.tsv"))
        hundreds_remainder = (
            (pynutil.delete("0") + insert_space + digits_1_9)
            | (insert_space + (digits_10_19 | double_digits))
        )
        compound_hundreds = hundreds_stems + hundreds_remainder
        all_hundreds = exact_hundreds | compound_hundreds
        self.all_hundreds = all_hundreds.optimize()

        one_to_999 = one_to_99 | all_hundreds
        self.one_to_999 = one_to_999.optimize()

        digits_2_9 = (NEMO_DIGIT - pynini.union("0", "1")) @ digits_tsv
        digits_10_99 = digits_10_19 | double_digits
        prefix_2_999 = digits_2_9 | digits_10_99 | all_hundreds

        remainder_3 = (
            (pynutil.delete("00") + insert_space + digits_1_9)
            | (pynutil.delete("0") + insert_space + digits_10_99)
            | (insert_space + all_hundreds)
        )
        remainder_3_no_one = (
            (pynutil.delete("00") + insert_space + digits_2_9)
            | (pynutil.delete("0") + insert_space + digits_10_99)
            | (insert_space + all_hundreds)
        )

        # Thousands:
        # 1000 standalone: "ათასი", with remainder: "ათას " + remainder
        one_thousand_exact = pynini.cross("1000", "ათასი")
        one_thousand_compound = pynini.cross("1", "ათას") + remainder_3

        # Multiple thousands (2..999 thousands):
        multi_thousands_exact = prefix_2_999 + pynutil.delete("000") + insert_space + pynutil.insert("ათასი")
        multi_thousands_compound = prefix_2_999 + insert_space + pynutil.insert("ათას") + remainder_3

        all_thousands = (
            one_thousand_exact
            | one_thousand_compound
            | multi_thousands_exact
            | multi_thousands_compound
        )
        self.all_thousands = all_thousands.optimize()

        # Millions (10^6 to 10^9 - 1):
        remainder_6 = (
            (pynutil.delete("000") + remainder_3)
            | (pynutil.delete("001000") + insert_space + pynutil.insert("ათასი"))
            | (pynutil.delete("001") + insert_space + pynutil.insert("ათას") + remainder_3)
            | (remainder_3_no_one + pynutil.delete("000") + insert_space + pynutil.insert("ათასი"))
            | (remainder_3_no_one + insert_space + pynutil.insert("ათას") + remainder_3)
        )
        all_millions = (
            (one_to_999 + pynutil.delete("000000") + insert_space + pynutil.insert("მილიონი"))
            | (one_to_999 + insert_space + pynutil.insert("მილიონ") + remainder_6)
        )
        self.all_millions = all_millions.optimize()

        # Billions (10^9 to 10^12 - 1):
        remainder_9 = (
            (pynutil.delete("000") + remainder_6)
            | (pynutil.delete("001000000") + insert_space + pynutil.insert("ერთი მილიონი"))
            | (pynutil.delete("001") + insert_space + pynutil.insert("ერთი მილიონ") + remainder_6)
            | (remainder_3_no_one + pynutil.delete("000000") + insert_space + pynutil.insert("მილიონი"))
            | (remainder_3_no_one + insert_space + pynutil.insert("მილიონ") + remainder_6)
        )
        all_billions = (
            (one_to_999 + pynutil.delete("000000000") + insert_space + pynutil.insert("მილიარდი"))
            | (one_to_999 + insert_space + pynutil.insert("მილიარდ") + remainder_9)
        )
        self.all_billions = all_billions.optimize()

        # Trillions (10^12 to 10^15 - 1):
        remainder_12 = (
            (pynutil.delete("000") + remainder_9)
            | (pynutil.delete("001000000000") + insert_space + pynutil.insert("ერთი მილიარდი"))
            | (pynutil.delete("001") + insert_space + pynutil.insert("ერთი მილიარდ") + remainder_9)
            | (remainder_3_no_one + pynutil.delete("000000000") + insert_space + pynutil.insert("მილიარდი"))
            | (remainder_3_no_one + insert_space + pynutil.insert("მილიარდ") + remainder_9)
        )
        all_trillions = (
            (one_to_999 + pynutil.delete("000000000000") + insert_space + pynutil.insert("ტრილიონი"))
            | (one_to_999 + insert_space + pynutil.insert("ტრილიონ") + remainder_12)
        )
        self.all_trillions = all_trillions.optimize()
        final_graph = (
            zero
            | digits_1_9
            | digits_10_19
            | double_digits
            | all_hundreds
            | all_thousands
            | all_millions
            | all_billions
            | all_trillions
        )

        # Grouped numbers with space, NBSP, comma or dot: "1 000 000", "1,000,000", "1.000.000"
        group_sep = pynini.union(" ", "\u00a0", ",", ".")
        grouped = (
            (NEMO_DIGIT - "0")
            + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(group_sep) + NEMO_DIGIT ** 3, 1)
        )
        final_graph = final_graph | pynutil.add_weight(pynini.compose(grouped, final_graph), 0.01)
        final_graph = final_graph.optimize()
        self.all_nums_no_tokens = final_graph

        # Leading zeros read digit-by-digit: "007" -> "ნული ნული შვიდი"
        digit_by_digit = (zero | digits_1_9) + pynini.closure(insert_space + (zero | digits_1_9))
        leading_zeros = pynini.compose("0" + pynini.closure(NEMO_DIGIT, 1), digit_by_digit)
        number = final_graph | pynutil.add_weight(leading_zeros, 0.1)
        self.number = number.optimize()

        # List of numbers: "1,2,3"
        plain = pynini.closure(NEMO_DIGIT, 1, 3) @ number
        number_list = plain + pynini.closure(pynini.cross(",", ", ") + plain, 2)

        # Range: "5-10" -> "ხუთიდან ათამდე"
        dash = pynini.union("-", "–", "—", "֊")
        range_from = glue_suffix(final_graph + pynutil.insert("+დან"))
        range_to = glue_suffix(final_graph + pynutil.insert("+მდე"))
        range_graph = range_from + pynutil.delete(dash) + pynutil.insert(" ") + range_to
        self.range_graph = range_graph.optimize()

        # Hyphenated case endings: "5-ს", "10-ით", "2024-ში", "2024-ის", "5-დან", "10-მდე"
        # Exclude ordinals ("1-ელი", "1-ლი", "2-ე", etc.) which are handled by OrdinalFst
        ordinal_marker = (
            (pynini.accep("1") + pynini.union("-", "–", "—", "֊") + pynini.union("ელი", "ლი", "ელ", "ლ") + NEMO_SIGMA)
            | (pynini.closure(NEMO_DIGIT, 1) + pynini.union("-", "–", "—", "֊") + "ე" + NEMO_SIGMA)
        )
        not_ordinal = pynini.difference(NEMO_SIGMA, ordinal_marker)
        suffixed = pynini.compose(not_ordinal, with_suffix(self.all_nums_no_tokens))

        # International decades: "2020s", "1990s" -> "ორი ათას ოციანი წლები", "ათას ცხრაას ოთხმოცდაათიანი წლები"
        # NEVER read as seconds!
        decade_year = (NEMO_DIGIT - "0") + NEMO_DIGIT ** 2 + "0"
        decade_intl = (
            glue_suffix((decade_year @ self.all_nums_no_tokens) + pynini.cross(pynini.union("s", "'s"), "+იანი"))
            + pynutil.insert(" წლები")
        )
        # Native Georgian decades: "1990-იანები" -> "ათას ცხრაას ოთხმოცდაათიანები", "2020-იანი წლები"
        decade_native = (
            glue_suffix((decade_year @ self.all_nums_no_tokens) + pynutil.delete("-") + pynutil.insert("+") + pynini.union("იანი წლები", "იანები", "იანებში", "იანების", "იანებით"))
        )

        optional_negative = pynini.closure(
            pynini.cross("-", 'negative: "true" ') | pynini.cross("−", 'negative: "true" '),
            0,
            1,
        )
        self.final_graph = pynutil.insert('integer: "') + final_graph + pynutil.insert('"')

        graph = optional_negative + pynutil.insert('integer: "') + number + pynutil.insert('"')
        graph |= pynutil.insert('integer: "') + (number_list | range_graph) + pynutil.insert('"')
        graph |= pynutil.add_weight(pynutil.insert('integer: "') + suffixed + pynutil.insert('"'), 0.05)
        graph |= pynutil.add_weight(pynutil.insert('integer: "') + (decade_intl | decade_native) + pynutil.insert('"'), -0.3)
        graph |= (
            pynutil.insert('integer: "') + self.all_nums_no_tokens
            + pynini.cross(":", " ორწერტილი ") + self.all_nums_no_tokens + pynutil.insert('"')
        )
        self.fst = self.add_tokens(graph).optimize()

        # Dotted versions ("3.11.2"), IPv4 ("192.168.1.1"), alphanumeric serials ("COVID-19", "5G", "A4", "BA249")
        code_num = pynini.closure(NEMO_DIGIT, 1, 6) @ self.number
        dot_sep = pynini.cross(".", " წერტილი ")
        port_part = pynini.cross(":", " ორწერტილი ") + code_num
        dotted_numbers = code_num + pynini.closure(dot_sep + code_num, 2, 5) + pynini.closure(port_part, 0, 1)

        version = (
            pynini.cross(pynini.union("v", "V"), "ვერსია ")
            + code_num
            + pynini.closure(dot_sep + code_num, 1, 4)
        )

        alpha = NEMO_ALPHA | GEORGIAN_ALPHA
        alpha_chunk = pynini.closure(alpha, 1)
        sep_chars = pynini.union("-", "–", "—", "֊", "/", "_")
        alnum_run = pynini.closure(alpha | NEMO_DIGIT, 1)
        serial_input = alnum_run + pynini.closure(sep_chars + alnum_run)
        serial_input = pynini.compose(serial_input, not_ordinal)
        serial_input = pynini.compose(serial_input, NEMO_SIGMA + alpha + NEMO_SIGMA)
        serial_input = pynini.compose(serial_input, NEMO_SIGMA + NEMO_DIGIT + NEMO_SIGMA)

        # Exclude plain digit-case combinations or fractions
        num_hyphen_ka = pynini.closure(NEMO_DIGIT, 1) + pynini.union("-", "–", "—", "֊") + pynini.closure(GEORGIAN_ALPHA, 1)
        slash_frac = pynini.closure(NEMO_DIGIT, 1) + "/" + pynini.closure(NEMO_DIGIT, 1)
        serial_input = pynini.compose(serial_input, pynini.difference(NEMO_SIGMA, num_hyphen_ka | slash_frac))

        spaced = (
            pynini.cdrewrite(pynutil.insert(" "), alpha, NEMO_DIGIT, NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.insert(" "), NEMO_DIGIT, alpha, NEMO_SIGMA)
            @ pynini.cdrewrite(pynini.cross(sep_chars, " "), "", "", NEMO_SIGMA)
        )
        piece = alpha_chunk | code_num
        pieces = piece + pynini.closure(pynini.accep(" ") + piece)
        alphanum = pynini.compose(pynini.compose(serial_input, spaced), pieces)

        # Variable powers: "x^2" -> "x კვადრატი", "y^3" -> "y კუბი", "2^3" -> "ორი კუბში"
        greek_var = pynini.union("α", "β", "γ", "δ", "π", "θ", "λ", "μ", "σ", "ω")
        var_base = (NEMO_ALPHA | GEORGIAN_ALPHA | greek_var) + pynini.closure(NEMO_ALPHA | GEORGIAN_ALPHA, 0, 3)
        power_2_3 = pynini.cross("^2", " კვადრატში") | pynini.cross("^3", " კუბში")
        var_power = (var_base | code_num) + power_2_3

        serial_num_end = dotted_numbers | version | pynini.compose(alphanum, NEMO_SIGMA + GEORGIAN_ALPHA)
        serial_graph = (
            dotted_numbers
            | version
            | alphanum
            | var_power
            | pynutil.add_weight(with_suffix(serial_num_end), -0.05)
        )
        self.serial = self.add_tokens(pynutil.insert('integer: "') + serial_graph + pynutil.insert('"')).optimize()
