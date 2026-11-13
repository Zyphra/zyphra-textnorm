# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import (
    INPUT_LOWER_CASED,
    NEMO_CHAR,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.el.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.el.taggers.date import DateFst
from nemo_text_processing.text_normalization.el.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.el.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.el.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.el.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.el.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.el.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.el.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.el.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.el.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.el.taggers.time import TimeFst
from nemo_text_processing.text_normalization.el.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.el.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all Greek classification grammars.
    Transduces written Greek sentences into tagged tokens format:
        tokens { name: "..." }

    Args:
        input_case: accepting either "lower_cased" or "cased" input.
        deterministic: whether to provide a deterministic transduction.
        cache_dir: path to directory with cached .far files.
        overwrite_cache: whether to overwrite existing .far files.
        whitelist: path to a file with custom whitelist replacements (optional).
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
                f"el_tokenize_and_classify_{input_case}_{deterministic}{whitelist_file}.far",
            )

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst graph was restored from {far_file}.")
        else:
            logger.info("Creating Greek ClassifyFst grammars...")

            cardinal = CardinalFst(deterministic=deterministic)
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            ordinal = OrdinalFst(deterministic=deterministic)
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            money = MoneyFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            measure = MeasureFst(
                cardinal=cardinal, decimal=decimal, fraction=fraction, deterministic=deterministic
            )
            date = DateFst(cardinal=cardinal, deterministic=deterministic)
            time = TimeFst(cardinal=cardinal, deterministic=deterministic)
            telephone = TelephoneFst(deterministic=deterministic)
            electronic = ElectronicFst(deterministic=deterministic)
            roman = RomanFst(deterministic=deterministic)
            whitelist_tagger = WhiteListFst(cardinal=cardinal, deterministic=deterministic)
            punct_tagger = PunctuationFst(deterministic=deterministic)
            word_tagger = WordFst(deterministic=deterministic)

            def to_name_token(fst):
                return pynutil.insert('name: "') + convert_space(fst).optimize() + pynutil.insert('"')

            whitelist_graph = to_name_token(whitelist_tagger.fst)
            roman_graph = to_name_token(roman.fst)
            money_graph = to_name_token(money.fst)
            time_graph = to_name_token(time.fst)
            date_graph = to_name_token(date.fst)
            measure_graph = to_name_token(measure.fst)
            fraction_graph = to_name_token(fraction.fst)
            decimal_graph = to_name_token(decimal.fst)
            ordinal_graph = to_name_token(ordinal.fst)
            cardinal_graph = to_name_token(cardinal.fst)
            telephone_graph = to_name_token(telephone.fst)
            electronic_graph = to_name_token(electronic.fst)
            punct_graph = punct_tagger.fst
            word_graph = word_tagger.fst

            classify = (
                pynutil.add_weight(whitelist_graph, 1.01)
                | pynutil.add_weight(roman_graph, 1.02)
                | pynutil.add_weight(money_graph, 1.03)
                | pynutil.add_weight(time_graph, 1.04)
                | pynutil.add_weight(date_graph, 1.05)
                | pynutil.add_weight(date.iso_fst, 1.05)
                | pynutil.add_weight(measure_graph, 1.06)
                | pynutil.add_weight(fraction_graph, 1.07)
                | pynutil.add_weight(decimal_graph, 1.08)
                | pynutil.add_weight(ordinal_graph, 1.09)
                | pynutil.add_weight(cardinal_graph, 1.10)
                | pynutil.add_weight(telephone_graph, 1.11)
                | pynutil.add_weight(electronic_graph, 1.12)
                | pynutil.add_weight(word_graph, 100.0)
            )

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=1.1) + pynutil.insert(" }")
            token = pynutil.insert("tokens { ") + classify + pynutil.insert(" }")

            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" ")) + token + pynini.closure(pynutil.insert(" ") + punct)
            )
            single_token = token_plus_punct | punct

            graph = single_token + pynini.closure(delete_extra_space + single_token)
            graph = delete_space + graph + delete_space

            self.fst = graph.optimize()

            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars saved to {far_file}.")
