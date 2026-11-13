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

import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ur.graph_utils import (
    NEMO_SPACE,
    NEMO_WHITE_SPACE,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.ur.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.ur.taggers.date import DateFst
from nemo_text_processing.text_normalization.ur.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.ur.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.ur.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.ur.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.ur.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.ur.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.ur.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.ur.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.ur.taggers.serial import SerialFst
from nemo_text_processing.text_normalization.ur.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.ur.taggers.time import TimeFst
from nemo_text_processing.text_normalization.ur.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.ur.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all other classification grammars. This class can process an entire sentence including punctuation.
    For deployment, this grammar will be compiled and exported to OpenFst Finite State Archive (FAR) File.
    More details to deployment at NeMo/tools/text_processing_deployment.

    Args:
        input_case: accepting either "lower_cased" or "cased" input.
        deterministic: if True will provide a single transduction option,
            for False multiple options (used for audio-based normalization)
        cache_dir: path to a dir with .far grammar file. Set to None to avoid using cache.
        overwrite_cache: set to True to overwrite .far files
        whitelist: path to a file with whitelist replacements
    """

    def __init__(
        self,
        input_case: str,
        deterministic: bool = True,
        cache_dir: str = None,
        overwrite_cache: bool = False,
        whitelist: str = None,
    ):
        super().__init__(name="tokenize_and_classify", kind="classify", deterministic=deterministic)

        far_file = None
        if cache_dir is not None and cache_dir != "None":
            os.makedirs(cache_dir, exist_ok=True)
            whitelist_file = os.path.basename(whitelist) if whitelist else ""
            far_file = os.path.join(
                cache_dir,
                f"_{input_case}_ur_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating ClassifyFst grammars.")

            cardinal = CardinalFst(deterministic=deterministic)
            cardinal_graph = cardinal.fst

            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            decimal_graph = decimal.fst

            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            fraction_graph = fraction.fst

            date = DateFst(cardinal=cardinal)
            date_graph = date.fst

            timefst = TimeFst(cardinal=cardinal)
            time_graph = timefst.fst

            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            ordinal_graph = ordinal.fst

            serial = SerialFst(cardinal=cardinal, deterministic=deterministic)
            serial_graph = serial.fst

            measure = MeasureFst(
                cardinal=cardinal, decimal=decimal, ordinal=ordinal, serial=serial, input_case=input_case
            )
            measure_graph = measure.fst

            money = MoneyFst(cardinal=cardinal)
            money_graph = money.fst

            whitelist_graph = WhiteListFst(
                input_case=input_case, deterministic=deterministic, input_file=whitelist
            ).fst

            punctuation = PunctuationFst(deterministic=deterministic)
            punct_graph = punctuation.fst

            word = WordFst(punctuation=punctuation, deterministic=deterministic)
            word_graph = word.fst

            roman = RomanFst(deterministic=deterministic)
            roman_graph = roman.fst

            telephone = TelephoneFst()
            telephone_graph = telephone.fst

            electronic = ElectronicFst(deterministic=deterministic)
            electronic_graph = electronic.fst

            classify = (
                pynutil.add_weight(whitelist_graph, 1.01)
                | pynutil.add_weight(cardinal_graph, 1.1)
                | pynutil.add_weight(decimal_graph, 1.1)
                | pynutil.add_weight(fraction_graph, 1.05)
                | pynutil.add_weight(date_graph, 1.1)
                | pynutil.add_weight(time_graph, 1.1)
                | pynutil.add_weight(measure_graph, 1.1)
                | pynutil.add_weight(money_graph, 1.1)
                | pynutil.add_weight(telephone_graph, 1.1)
                | pynutil.add_weight(ordinal_graph, 1.1)
                | pynutil.add_weight(electronic_graph, 1.1)
                | pynutil.add_weight(serial_graph, 1.11)
                | pynutil.add_weight(roman_graph, 1.1)
            )

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=2.1) + pynutil.insert(" }")
            punct = pynini.closure(
                pynini.union(
                    pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space),
                    (pynutil.insert(NEMO_SPACE) + punct),
                ),
                1,
            )

            prefix_words = convert_space(
                pynini.cross("~", "تقریباً")
                | pynini.cross("≈", "تقریباً")
                | pynini.cross("±", "جمع تفریق")
                | pynini.cross("©", "کاپی رائٹ")
                | pynini.cross("§§", "دفعات")
                | pynini.cross("§", "دفعہ")
            ).optimize()
            prefix_mod = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(prefix_words, -0.5)
                + pynutil.insert('" } ')
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            semiotic_token = (
                pynini.closure(prefix_mod, 0, 1) + pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            )
            word_token = pynutil.insert("tokens { ") + pynutil.add_weight(word_graph, 100) + pynutil.insert(" }")
            token = semiotic_token | word_token
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(NEMO_SPACE))
                + token
                + pynini.closure(pynutil.insert(NEMO_SPACE) + punct)
            )

            graph = token_plus_punct + pynini.closure(
                pynini.union(
                    pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space),
                    (pynutil.insert(NEMO_SPACE) + punct + pynutil.insert(NEMO_SPACE)),
                )
                + token_plus_punct
            )

            graph = delete_space + graph + delete_space
            graph = pynini.union(graph, punct)

            self.fst = graph.optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars are saved to {far_file}.")
