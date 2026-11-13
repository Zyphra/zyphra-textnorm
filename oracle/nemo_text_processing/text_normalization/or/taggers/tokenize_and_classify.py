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

from ..graph_utils import (
    GraphFst,
    NEMO_CHAR,
    NEMO_DIGIT,
    delete_extra_space,
    delete_space,
    generator_main,
)
from .cardinal import CardinalFst
from .date import DateFst
from .decimal import DecimalFst
from .electronic import ElectronicFst
from .fraction import FractionFst
from .measure import MeasureFst
from .money import MoneyFst
from .ordinal import OrdinalFst
from .punctuation import PunctuationFst
from .roman import RomanFst
from .telephone import TelephoneFst
from .time import TimeFst
from .whitelist import WhiteListFst
from .word import WordFst


class ClassifyFst(GraphFst):
    """
    Final class that composes all classification grammars for Odia.
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
                f"_{input_case}_or_tn_{deterministic}_deterministic{whitelist_file}.far",
            )

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
        else:
            self.cardinal = CardinalFst(deterministic=deterministic)
            cardinal_graph = self.cardinal.fst

            self.decimal = DecimalFst(cardinal=self.cardinal, deterministic=deterministic)
            decimal_graph = self.decimal.fst

            self.fraction = FractionFst(cardinal=self.cardinal, deterministic=deterministic)
            fraction_graph = self.fraction.fst

            self.ordinal = OrdinalFst(cardinal=self.cardinal, deterministic=deterministic)
            ordinal_graph = self.ordinal.fst

            self.measure = MeasureFst(
                cardinal=self.cardinal,
                decimal=self.decimal,
                fraction=self.fraction,
                deterministic=deterministic,
            )
            measure_graph = self.measure.fst

            self.date = DateFst(cardinal=self.cardinal, deterministic=deterministic)
            date_graph = self.date.fst

            self.time = TimeFst(cardinal=self.cardinal, deterministic=deterministic)
            time_graph = self.time.fst

            self.money = MoneyFst(
                cardinal=self.cardinal,
                decimal=self.decimal,
                deterministic=deterministic,
            )
            money_graph = self.money.fst

            self.telephone = TelephoneFst(cardinal=self.cardinal, deterministic=deterministic)
            telephone_graph = self.telephone.fst

            self.electronic = ElectronicFst(cardinal=self.cardinal, deterministic=deterministic)
            electronic_graph = self.electronic.fst

            self.roman = RomanFst(cardinal=self.cardinal, deterministic=deterministic)
            roman_graph = self.roman.fst

            self.whitelist = WhiteListFst(
                input_case=input_case,
                deterministic=deterministic,
                input_file=whitelist,
                cardinal=self.cardinal,
            )
            whitelist_graph = self.whitelist.fst

            punct_graph = PunctuationFst(deterministic=deterministic).fst
            word_graph = WordFst(deterministic=deterministic).fst

            # Priority assignment across semiotic categories
            classify = (
                pynutil.add_weight(whitelist_graph, 1.01)
                | pynutil.add_weight(roman_graph, 1.08)
                | pynutil.add_weight(time_graph, 1.09)
                | pynutil.add_weight(date_graph, 1.09)
                | pynutil.add_weight(money_graph, 1.09)
                | pynutil.add_weight(measure_graph, 1.10)
                | pynutil.add_weight(fraction_graph, 1.10)
                | pynutil.add_weight(ordinal_graph, 1.10)
                | pynutil.add_weight(decimal_graph, 1.10)
                | pynutil.add_weight(telephone_graph, 1.10)
                | pynutil.add_weight(electronic_graph, 1.11)
                | pynutil.add_weight(cardinal_graph, 1.12)
            )

            classify |= pynutil.add_weight(word_graph, 100.0)

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=1.1) + pynutil.insert(" }")
            token = pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
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
