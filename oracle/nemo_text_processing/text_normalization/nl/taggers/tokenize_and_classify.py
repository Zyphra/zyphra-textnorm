# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    INPUT_CASED,
    INPUT_LOWER_CASED,
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.nl.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.nl.taggers.date import DateFst
from nemo_text_processing.text_normalization.nl.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.nl.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.nl.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.nl.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.nl.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.nl.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.nl.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.nl.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.nl.taggers.serial import SerialFst
from nemo_text_processing.text_normalization.nl.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.nl.taggers.time import TimeFst
from nemo_text_processing.text_normalization.nl.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.nl.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all Dutch classification grammars.
    Tokenizes input text and classifies semiotic entities into tokens { name: "..." }.

    Args:
        input_case: 'cased' or 'lower_cased'
        deterministic: True or False
        cache_dir: path to directory with FAR grammar files
        overwrite_cache: set to True to overwrite FAR files
        whitelist: path to whitelist file
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
            far_file = os.path.join(
                cache_dir, f"_{input_case}_nl_tn_{deterministic}_deterministic_tokenize_and_classify.far"
            )

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating ClassifyFst grammars for Dutch...")
            cardinal = CardinalFst(deterministic=deterministic)
            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            measure = MeasureFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            money = MoneyFst(cardinal=cardinal, deterministic=deterministic)
            date = DateFst(cardinal=cardinal, deterministic=deterministic)
            time = TimeFst(cardinal=cardinal, deterministic=deterministic)
            telephone = TelephoneFst(cardinal=cardinal, deterministic=deterministic)
            electronic = ElectronicFst(cardinal=cardinal, deterministic=deterministic)
            roman = RomanFst(cardinal=cardinal, deterministic=deterministic)
            serial = SerialFst(cardinal=cardinal, deterministic=deterministic)
            whitelist_tagger = WhiteListFst(input_case=input_case, deterministic=deterministic)
            punctuation = PunctuationFst(deterministic=deterministic)
            word = WordFst(deterministic=deterministic)

            # Standalone prefix modifiers "~" (ongeveer) and "±" (plusminus)
            prefix_mod = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(
                    pynini.cross("~", "ongeveer") | pynini.cross("±", "plusminus"),
                    -2.0,
                )
                + pynutil.insert('" } ')
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            classify = (
                pynutil.add_weight(whitelist_tagger.fst, 1.01)
                | pynutil.add_weight(roman.fst, 1.04)
                | pynutil.add_weight(time.fst, 1.05)
                | pynutil.add_weight(date.fst, 1.07)
                | pynutil.add_weight(electronic.fst, 1.08)
                | pynutil.add_weight(telephone.fst, 1.08)
                | pynutil.add_weight(money.fst, 1.09)
                | pynutil.add_weight(measure.fst, 1.10)
                | pynutil.add_weight(fraction.fst, 1.10)
                | pynutil.add_weight(decimal.fst, 1.10)
                | pynutil.add_weight(ordinal.fst, 1.10)
                | pynutil.add_weight(cardinal.fst, 1.11)
                | pynutil.add_weight(serial.fst, 5.0)
                | pynutil.add_weight(word.fst, 100.0)
            )

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punctuation.fst, weight=1.1) + pynutil.insert(" }")
            token = pynini.closure(prefix_mod, 0, 1) + pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" ")) + token + pynini.closure(pynutil.insert(" ") + punct)
            )

            graph = token_plus_punct + pynini.closure(delete_extra_space + token_plus_punct)
            graph = delete_space + graph + delete_space

            self.fst = graph.optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})

        no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
        self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
