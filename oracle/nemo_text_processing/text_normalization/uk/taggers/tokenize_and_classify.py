# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

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
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.uk.taggers.date import DateFst
from nemo_text_processing.text_normalization.uk.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.uk.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.uk.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.uk.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.uk.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.uk.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.uk.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.uk.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.uk.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.uk.taggers.time import TimeFst
from nemo_text_processing.text_normalization.uk.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.uk.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all Ukrainian classification grammars into tokens { name: "..." }.
    Exports .fst and .fst_no_digits as required by the runtime contract.
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
            far_file = os.path.join(cache_dir, f"_uk_tn_{input_case}.far")

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating Ukrainian ClassifyFst grammars...")

            cardinal = CardinalFst()
            ordinal = OrdinalFst(cardinal=cardinal)
            decimal = DecimalFst(cardinal=cardinal)
            fraction = FractionFst(cardinal=cardinal)
            measure = MeasureFst(cardinal=cardinal, decimal=decimal, fraction=fraction)
            money = MoneyFst(cardinal=cardinal, decimal=decimal)
            date = DateFst(cardinal=cardinal, ordinal=ordinal)
            time = TimeFst(cardinal=cardinal)
            telephone = TelephoneFst(cardinal=cardinal)
            electronic = ElectronicFst(cardinal=cardinal)
            roman = RomanFst(cardinal=cardinal, ordinal=ordinal)
            whitelist_tagger = WhiteListFst(cardinal=cardinal, input_case=input_case)
            word = WordFst(deterministic=deterministic)
            punct_graph = PunctuationFst(deterministic=deterministic).fst

            # Prefix modifiers "~" (приблизно) and "±" (плюс-мінус)
            prefix_mod = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(
                    pynini.cross("~", "приблизно") | pynini.cross("±", "плюс-мінус"),
                    -2.0,
                )
                + pynutil.insert('" } ')
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            classify = (
                pynutil.add_weight(whitelist_tagger.fst, 1.01)
                | pynutil.add_weight(roman.fst, 1.02)
                | pynutil.add_weight(electronic.fst, 1.03)
                | pynutil.add_weight(telephone.fst, 1.04)
                | pynutil.add_weight(date.fst, 1.04)
                | pynutil.add_weight(time.fst, 1.05)
                | pynutil.add_weight(money.fst, 1.05)
                | pynutil.add_weight(measure.fst, 1.06)
                | pynutil.add_weight(fraction.fst, 1.07)
                | pynutil.add_weight(decimal.fst, 1.07)
                | pynutil.add_weight(ordinal.fst, 1.08)
                | pynutil.add_weight(cardinal.fst, 1.10)
                | pynutil.add_weight(word.fst, 100.0)
            )

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=1.1) + pynutil.insert(" }")
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
                logger.info(f"ClassifyFst grammars saved to {far_file}.")
