# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone_token
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_DIGIT,
    TO_ASCII_DIGIT,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ml.utils import get_abs_path

ML_PLUS = "പ്ലസ്"
MOBILE_START_DIGITS = pynini.union("6", "7", "8", "9", "൬", "൭", "൮", "൯").optimize()
ZERO_DIGIT = pynini.union("0", "൦").optimize()

digit_to_word = pynini.compose(TO_ASCII_DIGIT, pynini.string_file(get_abs_path("data/telephone/number.tsv"))).optimize()
num_token = (digit_to_word + insert_space).optimize()
group_separator = pynini.union(pynutil.delete(" "), pynutil.delete("-"), pynutil.delete(".")).optimize()


def digits(n_min: int, n_max: int = None) -> pynini.Fst:
    """n_min..n_max digits read one by one, each followed by a space."""
    return pynini.closure(num_token, n_min, n_max if n_max is not None else n_min).optimize()


def grouped(total_min: int, total_max: int) -> pynini.Fst:
    """total_min..total_max digits, groups optionally separated by space/-/. each."""
    shape = NEMO_ALL_DIGIT + pynini.closure(pynini.closure(group_separator, 0, 1) + NEMO_ALL_DIGIT)
    reader = digits(total_min, total_max)
    return pynini.compose(shape, reader).optimize()


def number_part(graph: pynini.Fst) -> pynini.Fst:
    clean_graph = graph + pynini.closure(pynutil.delete(" "), 0, 1)
    return pynutil.insert("number_part: \"") + clean_graph + pynutil.insert("\" ")

def generate_international() -> pynini.Fst:
    """+<country code> followed by 6-12 digits: +91 98480 22338 -> പ്ലസ് ഒൻപത് ഒന്ന് ..."""
    plus = pynini.cross("+", ML_PLUS + " ")
    cc = pynini.closure(num_token, 1, 3)
    country_code = pynutil.insert("country_code: \"") + plus + cc + pynutil.insert("\" ")
    sep = pynini.closure(pynutil.delete(" ") | pynutil.delete("-"), 0, 1)
    return (country_code + sep + number_part(grouped(6, 12))).optimize()


def generate_mobile() -> pynini.Fst:
    """Ten-digit Indian mobile numbers starting with 6-9, optionally with leading 0 or grouped."""
    lead = (MOBILE_START_DIGITS @ num_token).optimize()
    plain = lead + digits(9, 9)
    split_5_5 = lead + digits(4, 4) + group_separator + digits(5, 5)
    split_3_3_4 = lead + digits(2, 2) + group_separator + digits(3, 3) + group_separator + digits(4, 4)
    split = split_5_5 | split_3_3_4
    return number_part(plain | split).optimize()


def generate_landline() -> pynini.Fst:
    """STD code starting with 0 + subscriber number."""
    open_p = pynini.closure(pynutil.delete("("), 0, 1)
    close_p = pynini.closure(pynutil.delete(")"), 0, 1)
    sep = pynini.closure(pynutil.delete("-") | pynutil.delete(" "), 0, 1)
    std = open_p + (ZERO_DIGIT @ num_token).optimize() + digits(2, 4) + close_p
    subscriber = grouped(5, 8)
    graph = std + sep + subscriber
    return number_part(graph).optimize()


class TelephoneFst(GraphFst):
    """
    Finite state transducer for classifying telephone numbers, e.g.
        9848022338 -> telephone { number_part: "ഒൻപത് എട്ട് നാല് എട്ട് പൂജ്യം രണ്ട് രണ്ട് മൂന്ന് മൂന്ന് എട്ട് " }
        +91 98480 22338 -> telephone { country_code: "പ്ലസ് ഒൻപത് ഒന്ന് " number_part: "..." }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)

        mobile = generate_mobile()
        landline = generate_landline()
        international = generate_international()

        self.final = (international | mobile | landline).optimize()
        self.fst = (self.add_tokens(self.final) | international_telephone_token(digit_to_word, ML_PLUS)).optimize()
