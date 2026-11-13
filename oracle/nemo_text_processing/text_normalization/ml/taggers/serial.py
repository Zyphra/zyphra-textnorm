# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_ML_CHAR,
    NEMO_ML_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)


class SerialFst(GraphFst):
    """
    Finite state transducer for classifying serial strings in Malayalam text:
    alphanumeric codes, versions, exponents, chemical formulas, e.g.
        കോവിഡ്-19 -> tokens { name: "കോവിഡ്-പത്തൊൻപത്" }
        5ജി -> tokens { name: "അഞ്ച് ജി" }
        2^3 -> tokens { name: "രണ്ട് ഘാതം മൂന്ന്" }
        B-60 -> tokens { name: "ബി-അറുപത്" }
        A12 -> tokens { name: "എ പന്ത്രണ്ട്" }
        H2O -> tokens { name: "എച്ച് രണ്ട് ഒ" }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)

        card_num = cardinal.final_graph
        single_digit = cardinal.digit | cardinal.zero

        en_variable = NEMO_ALPHA
        # 1. Powers / exponents: 2^3 -> രണ്ട് ഘാതം മൂന്ന്
        base_num = pynini.closure(NEMO_ALL_DIGIT, 1, 4) @ card_num
        exp_num = pynini.closure(NEMO_ALL_DIGIT, 1, 3) @ card_num
        power_graph = (base_num | en_variable) + pynini.cross("^", " ഘാതം ") + exp_num

        # 2. Letter letter digit (e.g. FY2024, COVID-19, B-60, A12, 5G, 5ജി)
        ml_letters = pynini.closure(NEMO_ML_CHAR, 1)
        en_letters = pynini.string_map([
            ("A", "എ"), ("B", "ബി"), ("C", "സി"), ("D", "ഡി"), ("E", "ഇ"),
            ("F", "എഫ്"), ("G", "ജി"), ("H", "എച്ച്"), ("I", "ഐ"), ("J", "ജെ"),
            ("K", "കെ"), ("L", "എൽ"), ("M", "എം"), ("N", "എൻ"), ("O", "ഒ"),
            ("P", "പി"), ("Q", "ക്യു"), ("R", "ആർ"), ("S", "എസ്"), ("T", "ടി"),
            ("U", "യു"), ("V", "വി"), ("W", "ഡബ്ല്യു"), ("X", "എക്സ്"), ("Y", "വൈ"),
            ("Z", "സെഡ്"),
            ("a", "എ"), ("b", "ബി"), ("c", "സി"), ("d", "ഡി"), ("e", "ഇ"),
            ("f", "എഫ്"), ("g", "ജി"), ("h", "എച്ച്"), ("i", "ഐ"), ("j", "ജെ"),
            ("k", "കെ"), ("l", "എൽ"), ("m", "എം"), ("n", "എൻ"), ("o", "ഒ"),
            ("p", "പി"), ("q", "ക്യു"), ("r", "ആർ"), ("s", "എസ്"), ("t", "ടി"),
            ("u", "യു"), ("v", "വി"), ("w", "ഡബ്ല്യു"), ("x", "എക്സ്"), ("y", "വൈ"),
            ("z", "സെഡ്"),
        ])

        # En letter + space
        spoken_en = en_letters + pynini.closure(pynutil.insert(" ") + en_letters)

        # COVID-19 / കോവിഡ്-19
        covid_ml = pynini.accep("കോവിഡ്-") + (pynini.closure(NEMO_ALL_DIGIT, 1, 3) @ card_num)
        covid_en = pynini.cross(pynini.union("COVID-", "Covid-", "covid-"), "കോവിഡ്-") + (pynini.closure(NEMO_ALL_DIGIT, 1, 3) @ card_num)

        # Digit + letter: 5G -> അഞ്ച് ജി, 5ജി -> അഞ്ച് ജി
        digit_letter = (
            (pynini.closure(NEMO_ALL_DIGIT, 1, 3) @ card_num)
            + pynutil.insert(" ")
            + (pynini.cross("G", "ജി") | pynini.cross("g", "ജി") | pynini.accep("ജി"))
        )

        # Letter + hyphen + number: B-60 -> ബി-അറുപത്
        letter_hyphen_num = (
            en_letters
            + pynini.accep("-")
            + (pynini.closure(NEMO_ALL_DIGIT, 1, 4) @ card_num)
        )

        # Letter + number: A12 -> എ പന്ത്രണ്ട്
        letter_num = (
            en_letters
            + pynutil.insert(" ")
            + (pynini.closure(NEMO_ALL_DIGIT, 1, 4) @ card_num)
        )

        # FY2024 -> എഫ് വൈ രണ്ടായിരത്തി ഇരുപത്തിനാല്
        fy = (
            pynini.cross(pynini.union("FY", "fy"), "എഫ് വൈ ")
            + (pynini.closure(NEMO_ALL_DIGIT, 4, 4) @ card_num)
        )

        # H2O -> എച്ച് രണ്ട് ഒ
        h2o = pynini.cross("H2O", "എച്ച് രണ്ട് ഒ") | pynini.cross("h2o", "എച്ച് രണ്ട് ഒ")
        dot = pynini.cross(".", " ഡോട്ട് ")
        version = card_num + dot + card_num + pynini.closure(dot + card_num)
        named_version = pynini.closure(NEMO_ALPHA, 1) + pynini.accep(" ") + version
        prefixed_version = pynini.union("v", "V") + pynutil.insert(" ") + version
        letter_run = spoken_en | ml_letters
        join = pynini.accep("-") | pynutil.insert(" ")
        mixed_identifier = (
            letter_run + pynini.closure(join + card_num + pynini.closure(join + letter_run, 0, 1), 1)
            | card_num + pynutil.insert(" ") + letter_run
        )

        serial_words = (
            power_graph
            | covid_ml
            | covid_en
            | digit_letter
            | letter_hyphen_num
            | letter_num
            | fy
            | h2o
            | version | named_version | prefixed_version | mixed_identifier
        ).optimize()

        graph = pynutil.insert('name: "') + convert_space(serial_words) + pynutil.insert('"')
        self.fst = graph.optimize()
