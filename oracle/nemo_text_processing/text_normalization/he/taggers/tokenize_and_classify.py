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

from nemo_text_processing.text_normalization.en.graph_utils import (
    INPUT_LOWER_CASED,
    NEMO_CHAR,
    NEMO_DIGIT,
    GraphFst,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.he.taggers.date import DateFst
from nemo_text_processing.text_normalization.he.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.he.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.he.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.he.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.he.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.he.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.he.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.he.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.he.taggers.serial import SerialFst
from nemo_text_processing.text_normalization.he.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.he.taggers.time import TimeFst
from nemo_text_processing.text_normalization.he.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.he.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all classification grammars for Hebrew.
    Exports .fst and .fst_no_digits.

    Args:
        input_case: accepting either "lower_cased" or "cased" input.
        deterministic: if True will provide a single transduction option
        cache_dir: path to a dir with .far grammar file. Set to None to avoid using cache.
        overwrite_cache: set to True to overwrite .far files
        whitelist: path to a file with whitelist replacements
    """

    def __init__(
        self,
        input_case: str = INPUT_LOWER_CASED,
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
                f"_{input_case}_he_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating ClassifyFst grammars for Hebrew...")

            cardinal = CardinalFst(deterministic=deterministic)
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            roman = RomanFst(cardinal=cardinal, deterministic=deterministic)
            money = MoneyFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            measure = MeasureFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            date = DateFst(cardinal=cardinal, deterministic=deterministic)
            time = TimeFst(cardinal=cardinal, deterministic=deterministic)
            telephone = TelephoneFst(cardinal=cardinal, deterministic=deterministic)
            electronic = ElectronicFst(cardinal=cardinal, deterministic=deterministic)
            serial = SerialFst(cardinal=cardinal, deterministic=deterministic)
            whitelist_fst = WhiteListFst(cardinal=cardinal, deterministic=deterministic, input_file=whitelist)
            punct_fst = PunctuationFst()
            word_fst = WordFst()

            # Prefix modifiers: ~ (בערך) and ± (פלוס מינוס)
            prefix_mod = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(
                    pynini.cross("~", "בערך") | pynini.cross("±", "פלוס\u00a0מינוס"),
                    -2.0,
                )
                + pynutil.insert('" } ')
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            classify = (
                pynutil.add_weight(whitelist_fst.fst, 0.85)
                | pynutil.add_weight(date.fst, 0.88)
                | pynutil.add_weight(time.fst, 0.89)
                | pynutil.add_weight(roman.fst, 0.90)
                | pynutil.add_weight(money.fst, 0.92)
                | pynutil.add_weight(measure.fst, 0.93)
                | pynutil.add_weight(electronic.fst, 0.94)
                | pynutil.add_weight(telephone.fst, 0.95)
                | pynutil.add_weight(serial.fst, 0.96)
                | pynutil.add_weight(fraction.fst, 0.98)
                | pynutil.add_weight(decimal.fst, 1.0)
                | pynutil.add_weight(ordinal.fst, 1.02)
                | pynutil.add_weight(cardinal.fst, 1.05)
                | pynutil.add_weight(word_fst.fst, 100.0)
            )

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_fst.fst, weight=1.1) + pynutil.insert(" }")
            token = pynini.closure(prefix_mod, 0, 1) + pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" ")) + token + pynini.closure(pynutil.insert(" ") + punct)
            )

            graph = token_plus_punct + pynini.closure(delete_extra_space + token_plus_punct)
            graph = delete_space + graph + delete_space

            self.fst = graph.optimize()
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars are saved to {far_file}.")
