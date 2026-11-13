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
    NEMO_CHAR,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    delete_extra_space,
    generator_main,
)
from nemo_text_processing.text_normalization.en.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.sk.taggers.date import DateFst
from nemo_text_processing.text_normalization.sk.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.sk.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.sk.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.sk.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.sk.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.sk.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.sk.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.sk.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.sk.taggers.time import TimeFst
from nemo_text_processing.text_normalization.sk.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.sk.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all other classification grammars for Slovak.
    This class can process an entire sentence including punctuation.

    Args:
        input_case: accepting either "lower_cased" or "cased" input.
        deterministic: if True will provide a single transduction option
        cache_dir: path to a dir with .far grammar file. Set to None to avoid using cache.
        overwrite_cache: set to True to overwrite .far files
        whitelist: path to a file with whitelist replacements
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
            whitelist_file = os.path.basename(whitelist) if whitelist else ""
            far_file = os.path.join(
                cache_dir,
                f"_{input_case}_sk_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating ClassifyFst grammars for Slovak. This might take some time...")

            cardinal = CardinalFst(deterministic=deterministic)
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            roman = RomanFst(deterministic=deterministic)
            date = DateFst(cardinal=cardinal, deterministic=deterministic)
            time = TimeFst(cardinal=cardinal, deterministic=deterministic)
            money = MoneyFst(cardinal=cardinal, deterministic=deterministic)
            measure = MeasureFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            electronic = ElectronicFst(deterministic=deterministic)
            telephone = TelephoneFst(deterministic=deterministic)
            whitelist_fst = WhiteListFst(cardinal=cardinal, input_file=whitelist, deterministic=deterministic)
            money_inputs = pynini.arcmap(
                pynini.project(money.fst, "input"), map_type="rmweight"
            ).optimize()
            whitelist_inputs = pynini.difference(
                pynini.project(whitelist_fst.fst, "input"), money_inputs
            )
            whitelist_graph = (whitelist_inputs @ whitelist_fst.fst).optimize()
            word = WordFst(deterministic=deterministic)
            punct = PunctuationFst(deterministic=deterministic)

            def wrap_name(r):
                return pynutil.insert('name: "') + convert_space(r) + pynutil.insert('"')

            classify = (
                pynutil.add_weight(wrap_name(whitelist_graph), 1.01)
                | pynutil.add_weight(wrap_name(date.fst), 1.02)
                | pynutil.add_weight(date.iso_fst, 1.02)
                | pynutil.add_weight(wrap_name(electronic.fst), 1.025)
                | pynutil.add_weight(wrap_name(roman.fst), 1.03)
                | pynutil.add_weight(wrap_name(telephone.fst), 1.04)
                | pynutil.add_weight(wrap_name(time.fst), 1.05)
                | pynutil.add_weight(wrap_name(money.fst), 1.06)
                | pynutil.add_weight(wrap_name(measure.fst), 1.07)
                | pynutil.add_weight(wrap_name(fraction.fst), 1.08)
                | pynutil.add_weight(wrap_name(decimal.fst), 1.09)
                | pynutil.add_weight(wrap_name(ordinal.fst), 1.10)
                | pynutil.add_weight(wrap_name(cardinal.fst), 1.11)
                | pynutil.add_weight(word.fst, 100.0)
            )

            punct_tok = (
                pynutil.insert("tokens { ")
                + pynutil.add_weight(punct.fst, weight=1.1)
                + pynutil.insert(" }")
            )
            token = pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            token_plus_punct = (
                pynini.closure(punct_tok + pynutil.insert(" "))
                + token
                + pynini.closure(pynutil.insert(" ") + punct_tok)
            )
            graph = (
                token_plus_punct
                + pynini.closure(delete_extra_space + token_plus_punct)
            )
            graph |= punct_tok

            self.fst = graph.optimize()
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars are saved to {far_file}.")
