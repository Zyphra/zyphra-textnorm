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

import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.da.taggers.date import DateFst
from nemo_text_processing.text_normalization.da.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.da.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.da.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.da.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.da.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.da.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.da.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.da.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.da.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.da.taggers.time import TimeFst
from nemo_text_processing.text_normalization.da.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.da.taggers.word import WordFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    INPUT_LOWER_CASED,
    NEMO_CHAR,
    NEMO_DIGIT,
    GraphFst,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all Danish classification grammars.
    Tokenizes and classifies Danish sentences into tokens for verbalization.

    Args:
        input_case: capitalization type ('cased' or 'lower_cased')
        deterministic: if True provides single transduction option
        cache_dir: path to directory with .far archive
        overwrite_cache: if True, re-builds and overwrites .far files
        whitelist: optional custom whitelist path
    """

    def __init__(
        self,
        input_case: str = "cased",
        deterministic: bool = True,
        cache_dir: str = None,
        overwrite_cache: bool = False,
        whitelist: str = None,
    ):
        super().__init__(name="tokenize_and_classify", kind="classify", deterministic=deterministic)

        far_file = None
        if cache_dir is not None and cache_dir != "None":
            os.makedirs(cache_dir, exist_ok=True)
            far_file = os.path.join(
                cache_dir, f"_{input_case}_da_tn_{deterministic}_deterministic_tokenize_and_classify.far"
            )

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            logger.info(f"ClassifyFst graph was restored from {far_file}.")
        else:
            logger.info("Creating Danish ClassifyFst grammars...")

            cardinal = CardinalFst(deterministic=deterministic)
            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            money = MoneyFst(cardinal=cardinal, deterministic=deterministic)
            measure = MeasureFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            date = DateFst(cardinal=cardinal, ordinal=ordinal, deterministic=deterministic)
            time = TimeFst(cardinal=cardinal, deterministic=deterministic)
            electronic = ElectronicFst(cardinal=cardinal, deterministic=deterministic)
            roman = RomanFst(cardinal=cardinal, deterministic=deterministic)
            telephone = TelephoneFst(cardinal=cardinal, deterministic=deterministic)
            whitelist_fst = WhiteListFst(cardinal=cardinal, input_file=whitelist, deterministic=deterministic)
            punctuation = PunctuationFst(deterministic=deterministic)
            word = WordFst(deterministic=deterministic)

            classify = (
                pynutil.add_weight(whitelist_fst.fst, 1.01)
                | pynutil.add_weight(roman.fst, 1.04)
                | pynutil.add_weight(time.fst, 1.05)
                | pynutil.add_weight(date.fst, 1.08)
                | pynutil.add_weight(measure.fst, 1.10)
                | pynutil.add_weight(money.fst, 1.10)
                | pynutil.add_weight(fraction.fst, 1.10)
                | pynutil.add_weight(decimal.fst, 1.10)
                | pynutil.add_weight(ordinal.fst, 1.10)
                | pynutil.add_weight(telephone.fst, 1.10)
                | pynutil.add_weight(cardinal.fst, 1.10)
                | pynutil.add_weight(electronic.fst, 1.11)
                | pynutil.add_weight(word.fst, 100.0)
            )

            punct = (
                pynutil.insert("tokens { ")
                + pynutil.add_weight(punctuation.fst, weight=1.1)
                + pynutil.insert(" }")
            )
            token = pynutil.insert("tokens { ") + classify + pynutil.insert(" }")

            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" "))
                + token
                + pynini.closure(pynutil.insert(" ") + punct)
            )

            punct_only = punct + pynini.closure(delete_extra_space + punct)

            graph = (token_plus_punct | punct_only) + pynini.closure(
                delete_extra_space + (token_plus_punct | punct_only)
            )
            graph = delete_space + graph + delete_space

            self.fst = graph.optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars saved to {far_file}.")

        no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
        self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
