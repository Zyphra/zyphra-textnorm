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
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.en.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.fi.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.fi.taggers.date import DateFst
from nemo_text_processing.text_normalization.fi.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.fi.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.fi.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.fi.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.fi.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.fi.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.fi.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.fi.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.fi.taggers.time import TimeFst
from nemo_text_processing.text_normalization.fi.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.fi.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all Finnish classification grammars.

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
                f"_{input_case}_fi_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating ClassifyFst grammars for Finnish. This might take some time...")

            self.cardinal = CardinalFst(deterministic=deterministic)
            self.ordinal = OrdinalFst(cardinal=self.cardinal, deterministic=deterministic)
            self.decimal = DecimalFst(cardinal=self.cardinal, deterministic=deterministic)
            self.fraction = FractionFst(cardinal=self.cardinal, deterministic=deterministic)
            self.money = MoneyFst(cardinal=self.cardinal, decimal=self.decimal, deterministic=deterministic)
            self.measure = MeasureFst(
                cardinal=self.cardinal, decimal=self.decimal, fraction=self.fraction, deterministic=deterministic
            )
            self.date = DateFst(cardinal=self.cardinal, deterministic=deterministic)
            self.time = TimeFst(cardinal=self.cardinal, deterministic=deterministic)
            self.telephone = TelephoneFst(cardinal=self.cardinal, deterministic=deterministic)
            self.electronic = ElectronicFst(cardinal=self.cardinal, deterministic=deterministic)
            self.roman = RomanFst(cardinal=self.cardinal, deterministic=deterministic)
            self.whitelist = WhiteListFst(cardinal=self.cardinal, deterministic=deterministic)
            self.word = WordFst(deterministic=deterministic)
            punctuation = PunctuationFst(deterministic=deterministic)

            number = self.cardinal.all_nums_no_tokens
            ratio = (
                pynutil.insert('name: "')
                + convert_space(number + pynini.cross(":", " kaksoispiste ") + number)
                + pynutil.insert('"')
            )
            money_range = (
                self.money.fst + pynini.closure(pynutil.delete(" "))
                + pynutil.delete(pynini.union("-", "–", "—"))
                + pynutil.insert(' } tokens { name: "viiva" } tokens { ')
                + pynini.closure(pynutil.delete(" ")) + self.money.fst
            )
            classify = (
                pynutil.add_weight(self.whitelist.fst, 1.01)
                | pynutil.add_weight(self.roman.fst, 1.04)
                | pynutil.add_weight(self.time.fst, 1.05)
                | pynutil.add_weight(self.date.fst, 1.06)
                | pynutil.add_weight(self.electronic.fst, 1.07)
                | pynutil.add_weight(self.telephone.fst, 1.08)
                | pynutil.add_weight(self.money.fst, 1.09)
                | pynutil.add_weight(money_range, 1.08)
                | pynutil.add_weight(ratio, 1.15)
                | pynutil.add_weight(self.measure.fst, 1.10)
                | pynutil.add_weight(self.fraction.fst, 1.10)
                | pynutil.add_weight(self.decimal.fst, 1.11)
                | pynutil.add_weight(self.ordinal.fst, 1.11)
                | pynutil.add_weight(self.cardinal.fst, 1.12)
                | pynutil.add_weight(self.word.fst, 100.0)
            )

            prefix_modifier = (
                pynini.cross("~", 'tokens { name: "noin" } ')
                | pynini.cross("±", 'tokens { name: "plus-miinus" } ')
            ) + pynini.closure(pynutil.delete(" "))
            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punctuation.fst, weight=1.1) + pynutil.insert(" }")
            token = pynini.closure(prefix_modifier, 0, 1) + pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" ")) + token + pynini.closure(pynutil.insert(" ") + punct)
            )

            graph = token_plus_punct + pynini.closure(delete_extra_space + token_plus_punct)
            graph = delete_space + graph + delete_space
            self.fst = graph.optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars are saved to {far_file}.")

            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
