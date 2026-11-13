# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.en.taggers.punctuation import (
    PunctuationFst,
)
from nemo_text_processing.text_normalization.en.taggers.word import (
    WordFst,
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)
from nemo_text_processing.text_normalization.nb.taggers.date import (
    DateFst,
)
from nemo_text_processing.text_normalization.nb.taggers.decimal import (
    DecimalFst,
)
from nemo_text_processing.text_normalization.nb.taggers.electronic import (
    ElectronicFst,
)
from nemo_text_processing.text_normalization.nb.taggers.fraction import (
    FractionFst,
)
from nemo_text_processing.text_normalization.nb.taggers.measure import (
    MeasureFst,
)
from nemo_text_processing.text_normalization.nb.taggers.money import (
    MoneyFst,
)
from nemo_text_processing.text_normalization.nb.taggers.ordinal import (
    OrdinalFst,
)
from nemo_text_processing.text_normalization.nb.taggers.roman import (
    RomanFst,
)
from nemo_text_processing.text_normalization.nb.taggers.telephone import (
    TelephoneFst,
)
from nemo_text_processing.text_normalization.nb.taggers.time import (
    TimeFst,
)
from nemo_text_processing.text_normalization.nb.taggers.whitelist import (
    WhiteListFst,
)
from nemo_text_processing.utils.logging import logger


class ClassifyFst(GraphFst):
    """
    Final class that composes all other classification grammars for Norwegian Bokmål (nb).
    This class processes an entire sentence including punctuation and whitespace.

    Args:
        input_case: accepting either "lower_cased" or "cased" input.
        deterministic: if True will provide a single transduction option.
        cache_dir: path to a dir with .far grammar file. Set to None to avoid using cache.
        overwrite_cache: set to True to overwrite .far files.
        whitelist: path to a file with whitelist replacements (optional).
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
                f"_{input_case}_nb_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            cardinal = CardinalFst(deterministic=deterministic)
            ordinal = OrdinalFst(deterministic=deterministic)
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            money = MoneyFst(cardinal=cardinal, deterministic=deterministic)
            measure = MeasureFst(
                cardinal=cardinal,
                decimal=decimal,
                fraction=fraction,
                deterministic=deterministic,
            )
            date = DateFst(cardinal=cardinal, deterministic=deterministic)
            time_tagger = TimeFst(cardinal=cardinal, deterministic=deterministic)
            telephone = TelephoneFst(cardinal=cardinal, deterministic=deterministic)
            electronic = ElectronicFst(cardinal=cardinal, deterministic=deterministic)
            roman = RomanFst(deterministic=deterministic)
            whitelist_tagger = WhiteListFst(cardinal=cardinal, deterministic=deterministic)
            punctuation = PunctuationFst(deterministic=deterministic)
            word = WordFst(punctuation=punctuation, deterministic=deterministic)

            def wrap(g):
                return (pynutil.insert('name: "') + convert_space(g) + pynutil.insert('"')).optimize()

            punct_graph = punctuation.fst
            word_graph = word.fst

            opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
            prefix_tok = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(
                    pynini.cross("~", "omtrent") | pynini.cross("±", "pluss\u00a0minus"),
                    1.05,
                )
                + pynutil.insert('" } ')
                + opt_sp
            ).optimize()

            classify = (
                pynutil.add_weight(wrap(whitelist_tagger.fst), 1.01)
                | pynutil.add_weight(wrap(telephone.fst), 1.02)
                | pynutil.add_weight(wrap(roman.fst), 1.03)
                | pynutil.add_weight(wrap(time_tagger.fst), 1.04)
                | pynutil.add_weight(wrap(date.fst), 1.05)
                | pynutil.add_weight(date.iso_fst, 1.05)
                | pynutil.add_weight(wrap(ordinal.fst), 1.06)
                | pynutil.add_weight(wrap(cardinal.fst), 1.07)
                | pynutil.add_weight(wrap(decimal.fst), 1.08)
                | pynutil.add_weight(wrap(money.fst), 1.09)
                | pynutil.add_weight(wrap(measure.fst), 1.10)
                | pynutil.add_weight(wrap(fraction.fst), 1.11)
                | pynutil.add_weight(wrap(electronic.fst), 1.12)
                | pynutil.add_weight(word_graph, 100.0)
            )

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=1.1) + pynutil.insert(" }")
            token = pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            possibly_prefixed_token = pynini.closure(prefix_tok, 0, 1) + token
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" "))
                + possibly_prefixed_token
                + pynini.closure(pynutil.insert(" ") + punct)
            )

            graph = token_plus_punct + pynini.closure(delete_extra_space + token_plus_punct)
            graph = delete_space + graph + delete_space

            self.fst = graph.optimize()
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars are saved to {far_file}.")
