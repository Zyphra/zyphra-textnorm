# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.cs.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.cs.taggers.date import DateFst
from nemo_text_processing.text_normalization.cs.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.cs.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.cs.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.cs.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.cs.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.cs.taggers.serial import SerialFst
from nemo_text_processing.text_normalization.cs.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.cs.taggers.time import TimeFst
from nemo_text_processing.text_normalization.cs.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    INPUT_LOWER_CASED,
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_NOT_SPACE,
    NEMO_WHITE_SPACE,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.en.taggers.punctuation import PunctuationFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all Czech classification grammars.
    Exports self.fst and self.fst_no_digits.

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
        input_case: str = "cased",
        deterministic: bool = True,
        cache_dir: str = None,
        overwrite_cache: bool = False,
        whitelist: str = None,
    ):
        super().__init__(name="tokenize_and_classify", kind="classify", deterministic=deterministic)

        far_file = None
        whitelist_file = ""
        if whitelist:
            whitelist_file = os.path.basename(whitelist)
        if cache_dir is not None and cache_dir != "None":
            os.makedirs(cache_dir, exist_ok=True)
            far_file = os.path.join(
                cache_dir, f"cs_tn_{deterministic}_deterministic_{input_case}_{whitelist_file}_tokenize.far"
            )

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating ClassifyFst grammars for Czech (cs)...")

            cardinal = CardinalFst(deterministic=deterministic)
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            date = DateFst(cardinal=cardinal, deterministic=deterministic)
            time = TimeFst(cardinal=cardinal, deterministic=deterministic)
            money = MoneyFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            measure = MeasureFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            electronic = ElectronicFst(cardinal=cardinal, deterministic=deterministic)
            serial = SerialFst(cardinal=cardinal, deterministic=deterministic)
            telephone = TelephoneFst(cardinal=cardinal, deterministic=deterministic)
            whitelist_tagger = WhiteListFst(cardinal=cardinal, deterministic=deterministic)
            punct_tagger = PunctuationFst(deterministic=deterministic)

            # Semiotic rule union with prioritized weights
            classify_rules = (
                pynutil.add_weight(whitelist_tagger.fst, 1.01)
                | pynutil.add_weight(electronic.fst, 1.02)
                | pynutil.add_weight(telephone.fst, 1.025)
                | pynutil.add_weight(time.fst, 1.03)
                | pynutil.add_weight(date.fst, 1.04)
                | pynutil.add_weight(money.fst, 1.05)
                | pynutil.add_weight(measure.fst, 1.06)
                | pynutil.add_weight(decimal.fst, 1.07)
                | pynutil.add_weight(ordinal.fst, 1.08)
                | pynutil.add_weight(serial.fst, 1.09)
                | pynutil.add_weight(cardinal.fst, 1.10)
            )

            # Word fallback for ordinary text tokens
            word_graph = pynutil.insert('name: "') + pynini.closure(NEMO_NOT_SPACE, 1) + pynutil.insert('"')

            # Semiotic tokens converted with convert_space (spaces inside quotes -> NBSP)
            semiotic_token = pynutil.insert('name: "') + convert_space(classify_rules) + pynutil.insert('"')

            token_content = pynutil.add_weight(semiotic_token, 1.0) | pynutil.add_weight(word_graph, 100.0)
            token_content |= pynutil.add_weight(date.iso_fst, 2.04)
            token = pynutil.insert("tokens { ") + token_content + pynutil.insert(" }")

            # Punctuation token
            punct_token = pynutil.insert("tokens { ") + pynutil.add_weight(punct_tagger.fst, 1.1) + pynutil.insert(" }")

            # Prefix modifiers "~" ("přibližně") and "±" ("plus mínus")
            opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
            prefix_tok = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(
                    pynini.cross("~", "přibližně")
                    | pynini.cross("±", "plus\u00a0mínus")
                    | pynini.cross("+/-", "plus\u00a0mínus"),
                    1.05,
                )
                + pynutil.insert('" } ')
                + opt_sp
            ).optimize()

            possibly_prefixed_token = pynini.closure(prefix_tok, 0, 1) + token

            token_plus_punct = (
                pynini.closure(punct_token + pynutil.insert(" "))
                + possibly_prefixed_token
                + pynini.closure(pynutil.insert(" ") + punct_token)
            )

            graph = token_plus_punct + pynini.closure(
                (
                    pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space)
                    | (pynutil.insert(" ") + punct_token + pynutil.insert(" "))
                )
                + token_plus_punct
            )

            graph = delete_space + graph + delete_space
            graph |= punct_token

            self.fst = graph.optimize()
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars saved to {far_file}.")
