# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
# Copyright 2017 Google Inc.
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

# Adapted from https://github.com/google/TextNormalizationCoveringGrammars
# Russian minimally supervised number grammar.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    NEMO_SPACE,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ru.alphabet import RU_ALPHA, TO_CYRILLIC
from nemo_text_processing.text_normalization.ru.taggers.number_names import ENDS_IN
from nemo_text_processing.text_normalization.ru.taggers.units import (
    MARK,
    UNIT_SPACE,
    agreement,
    attach,
    marked_numbers,
    quantity_nouns,
)
from nemo_text_processing.text_normalization.ru.utils import get_abs_path

_NON_ZERO = pynini.difference(NEMO_DIGIT, "0").optimize()

# Common Latin math variable readings in Russian ("x^2" -> "икс в квадрате", "y^3" -> "игрек в кубе", "z^2" -> "зет в квадрате")
_MATH_VAR_MAP = [
    ("x", "икс"),
    ("X", "икс"),
    ("y", "игрек"),
    ("Y", "игрек"),
    ("z", "зет"),
    ("Z", "зет"),
    ("a", "а"),
    ("A", "а"),
    ("b", "бэ"),
    ("B", "бэ"),
    ("c", "цэ"),
    ("C", "цэ"),
    ("d", "дэ"),
    ("D", "дэ"),
    ("k", "ка"),
    ("K", "ка"),
    ("m", "эм"),
    ("M", "эм"),
    ("n", "эн"),
    ("N", "эн"),
    ("p", "пэ"),
    ("P", "пэ"),
    ("q", "ку"),
    ("Q", "ку"),
    ("r", "эр"),
    ("R", "эр"),
    ("s", "эс"),
    ("S", "эс"),
    ("t", "тэ"),
    ("T", "тэ"),
    ("u", "у"),
    ("U", "у"),
    ("v", "вэ"),
    ("V", "вэ"),
]

_GENITIVE_PREPOSITIONS = [
    "около",
    "Около",
    "более",
    "Более",
    "менее",
    "Менее",
    "больше",
    "Больше",
    "меньше",
    "Меньше",
    "свыше",
    "Свыше",
    "порядка",
    "Порядка",
    "до",
    "До",
    "от",
    "От",
]


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying cardinals, e.g.
        "1 001" -> cardinal { integer: "одна тысяча один" }

    Args:
        number_names: number names for cardinal and ordinal numbers
        alternative_formats: alternative format for cardinal and ordinal numbers
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, number_names: dict, alternative_formats: dict, deterministic: bool = False):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        separators = alternative_formats['separators']
        masculine = number_names['cardinal']['masc']
        # digits (with optional thousands separators) -> masculine nominative
        self.numbers = {'masc': (masculine | pynutil.add_weight(separators @ masculine, 0.01)).optimize()}
        self.feminine = number_names['cardinal']['fem']
        self.numbers_genitive = number_names['cardinal_gen']
        self.ordinal_numbers = number_names['ordinal']
        gen_full = (self.numbers_genitive['masc'] | pynutil.add_weight(separators @ self.numbers_genitive['masc'], 0.01)).optimize()
        self.genitive_marked = (
            pynini.compose(ENDS_IN["one"], gen_full) + pynutil.insert(MARK["gen"])
            | pynini.compose(ENDS_IN["few"] | ENDS_IN["many"], gen_full) + pynutil.insert(MARK["many"])
        ).optimize()

        # the same with the marker of the form a counted noun takes after it (units.py)
        self.marked = marked_numbers(self.numbers['masc'])
        self.cardinal_numbers_default = self.numbers['masc']
        self.cardinal_numbers_nominative = self.numbers['masc']
        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross("-", "\"true\"") + insert_space, 0, 1
        )

        # "123" -> "один два три"
        single_digits_graph = pynini.string_file(get_abs_path("data/numbers/cardinals_nominative_case.tsv")).optimize()
        single_digits_graph = pynini.compose(NEMO_DIGIT, single_digits_graph)
        self.single_digit = single_digits_graph
        self.single_digits_graph = single_digits_graph + pynini.closure(insert_space + single_digits_graph)

        serial_graph = self.get_serial_graph()

        # "5 млн" / "5млн" -> "пять миллионов", "2 тыс." -> "две тысячи"
        quantities = quantity_nouns()
        with_quantity = self.counted(quantities, UNIT_SPACE)
        final_graph = (
            self.optional_graph_negative
            + pynutil.insert("integer: \"")
            + (self.cardinal_numbers_default | with_quantity)
            + pynutil.insert("\"")
        )

        # "~50" -> "около пятидесяти", "±5" -> "плюс-минус пять", "около 500" -> "около пятисот"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        approx_cardinal = (
            pynini.cross("~", "около ") + opt_sp + gen_full
            | (pynini.cross("±", "плюс-минус ") + opt_sp + pynini.closure(pynini.cross("-", "минус "), 0, 1) + (self.cardinal_numbers_default | with_quantity))
            | (pynini.union(*_GENITIVE_PREPOSITIONS) + pynini.accep(" ") + gen_full)
        )
        final_graph |= pynutil.insert("integer: \"") + pynutil.add_weight(approx_cardinal, -0.15) + pynutil.insert("\"")

        # "№ 5" / "№5" -> "номер пять"
        numero_cardinal = pynini.cross("№", "номер ") + opt_sp + self.cardinal_numbers_default
        final_graph |= pynutil.insert("integer: \"") + pynutil.add_weight(numero_cardinal, -0.15) + pynutil.insert("\"")

        final_graph = pynutil.add_weight(final_graph, -0.1)
        final_graph |= pynutil.insert("integer: \"") + pynutil.add_weight(serial_graph, 10) + pynutil.insert("\"")

        # Variable powers ("x^2" -> "икс в квадрате", "y^3" -> "игрек в кубе", "x^4" -> "икс в четвертой степени")
        math_var = pynini.string_map(_MATH_VAR_MAP) | pynutil.add_weight(TO_CYRILLIC | RU_ALPHA, 0.1)
        exp_special = pynini.cross("2", "в квадрате") | pynini.cross("3", "в кубе")
        exp_ord_digits = pynini.difference(_NON_ZERO + pynini.closure(NEMO_DIGIT, 0, 2), pynini.union("2", "3"))
        exp_general = (
            pynutil.insert("в ")
            + (exp_ord_digits @ self.ordinal_numbers["fem_gen"])
            + pynutil.insert(" степени")
            | pynini.cross("0", "в нулевой степени")
            | (
                pynini.cross("-", "в минус ")
                + ((_NON_ZERO + pynini.closure(NEMO_DIGIT, 0, 2)) @ self.ordinal_numbers["fem_gen"])
                + pynutil.insert(" степени")
            )
        )
        var_power = math_var + pynini.cross("^", " ") + (exp_special | exp_general)
        final_graph |= pynutil.insert("integer: \"") + pynutil.add_weight(var_power, -0.2) + pynutil.insert("\"")

        # "5-10" / "10–20" / "1995–2005" -> "от пяти до десяти"; "1,2,3" -> "один, два, три"
        short = _NON_ZERO + pynini.closure(NEMO_DIGIT, 0, 3)
        genitive = pynini.compose(short, self.numbers_genitive['masc']).optimize()
        self.range_genitive = genitive
        self.range_genitive_marked = (
            pynini.compose(ENDS_IN["one"], genitive) + pynutil.insert(MARK["gen"])
            | pynini.compose(ENDS_IN["few"] | ENDS_IN["many"], genitive) + pynutil.insert(MARK["many"])
        ).optimize()
        number_range = pynutil.insert("от ") + genitive + pynini.cross(pynini.union("-", "–"), " до ") + genitive
        listed_number = pynini.compose(short | "0", masculine)
        listed = listed_number + pynini.closure(pynini.cross(",", ", ") + listed_number, 2)
        final_graph |= pynutil.insert("integer: \"") + (number_range | listed) + pynutil.insert("\"")
        # "2-х" / "4-х" -> "двух" / "четырех" (genitive, as in "4-х килограммовый"); "1960-х" is the ordinal tagger's
        final_graph |= (
            pynutil.insert("integer: \"")
            + pynini.compose(pynini.closure(NEMO_DIGIT, 0, 2) + _NON_ZERO, self.numbers_genitive['masc'])
            + pynutil.delete("-х")
            + pynutil.insert("\"")
        )
        final_graph = self.add_tokens(final_graph)
        self.fst = final_graph.optimize()

    def counted(self, nouns, space: pynini.FstLike, suffix: pynini.FstLike = None, number=None) -> pynini.Fst:
        """Number + counted noun with agreement ("5 кг" -> "пять килограммов", "1 т" -> "одна тонна", "22 т" ->
        "двадцать две тонны"). space maps what is written between number and noun to the space between the words.
        number: marked number words to use instead of the plain cardinal (units.marked_numbers)."""
        return attach(self.marked if number is None else number, agreement(nouns, space, suffix))

    def get_serial_graph(self):
        """
        Finite state transducer for classifying alphanumeric serials, versions, and IP addresses, e.g.:
            c325-b -> "си три два пять би"
            A4 -> "эй четыре", BA249 -> "би эй два четыре девять", COVID-19 -> "си оу ви ай ди девятнадцать"
            v2.0 -> "ви два точка ноль", 3.11.2 -> "три точка одиннадцать точка два", 192.168.1.1 -> "сто девяносто два точка ..."
        """
        num_graph = self.single_digits_graph
        alpha = TO_CYRILLIC | RU_ALPHA
        alpha_in = RU_ALPHA | pynini.project(TO_CYRILLIC, "input")

        delimiter = pynini.cross("/", " ") | pynini.cross("-", " ")
        dot = pynini.cross(".", " точка ")

        letter_seq = (alpha + pynini.closure(insert_space + alpha)).optimize()
        # Adjacent letters and digits inside one segment ("A4", "BA249", "v2", "3d") alternate without consuming any separator
        alnum_segment = (
            letter_seq
            | num_graph
            | letter_seq + pynini.closure(insert_space + num_graph + pynini.closure(insert_space + letter_seq, 0, 1), 1)
            | num_graph + pynini.closure(insert_space + letter_seq + pynini.closure(insert_space + num_graph, 0, 1), 1)
        ).optimize()
        # Dot-separated numeric version/IP parts: 1-3 digits without leading zero as cardinal, else digit-by-digit
        dot_num = (
            pynini.compose("0" | (_NON_ZERO + pynini.closure(NEMO_DIGIT, 0, 2)), self.numbers['masc'])
            | pynini.compose(("0" + pynini.closure(NEMO_DIGIT, 1)) | pynini.closure(NEMO_DIGIT, 4), num_graph)
        ).optimize()
        piece_after_dot = dot_num | pynutil.add_weight(alnum_segment, 0.05)

        # Letters-hyphen-number ("COVID-19", "B-52", "T-34") reads a 2-digit number as a cardinal; multi-hyphen serials
        # ("2-б-34", "c325-b") read digit-by-digit.
        model_name = (
            letter_seq
            + pynini.cross("-", " ")
            + pynini.compose(_NON_ZERO + NEMO_DIGIT, self.numbers['masc'])
        )
        serial_body = pynutil.add_weight(model_name, -0.05) | alnum_segment + pynini.closure(
            delimiter + alnum_segment | dot + piece_after_dot
        )
        at_least_one_alpha_num = (NEMO_SIGMA + alpha_in + NEMO_SIGMA + NEMO_DIGIT + NEMO_SIGMA) | (
            NEMO_SIGMA + NEMO_DIGIT + NEMO_SIGMA + alpha_in + NEMO_SIGMA
        )
        serial_graph = pynini.compose(at_least_one_alpha_num, serial_body.optimize()).optimize()

        # Numbers only with 2+ delimiters: "2-3-4" (digit-by-digit) and versions/IPs "3.11.2", "192.168.1.1"
        slash_dash = pynini.cross("-", " ") | pynini.cross("/", " ")
        serial_graph |= (
            num_graph + slash_dash + num_graph + slash_dash + num_graph + pynini.closure(slash_dash + num_graph)
        ).optimize()
        serial_graph |= (dot_num + dot + dot_num + dot + dot_num + pynini.closure(dot + dot_num)).optimize()
        return serial_graph.optimize()
