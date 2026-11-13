# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

import logging
import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ml.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.ml.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.ml.taggers.date import DateFst
from nemo_text_processing.text_normalization.ml.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.ml.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.ml.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.ml.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.ml.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.ml.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.ml.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.ml.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.ml.taggers.serial import SerialFst
from nemo_text_processing.text_normalization.ml.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.ml.taggers.time import TimeFst
from nemo_text_processing.text_normalization.ml.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.ml.taggers.word import WordFst
from nemo_text_processing.text_normalization.ml.verbalizers.time import TimeFst as TimeVerbalizer


def _build_composite_fst(cardinal: CardinalFst, time_tagger: TimeFst) -> pynini.Fst:
    opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
    dash = pynini.union("-", "–", "—")

    # 1. Time ranges: "9:00-17:00", "09:00–17:00", "9:30-18:15"
    time_verb = TimeVerbalizer(cardinal=cardinal).fst
    hm_pat = (
        pynini.closure(NEMO_ALL_DIGIT, 1, 2)
        + ":"
        + NEMO_ALL_DIGIT**2
        + pynini.closure(":" + NEMO_ALL_DIGIT**2, 0, 1)
    )
    spoken_time = (hm_pat @ time_tagger.fst @ time_verb).optimize()
    time_range = spoken_time + opt_space + pynini.cross(dash, " മുതൽ ") + opt_space + spoken_time + pynutil.insert(" വരെ")

    # 2. Arithmetic / Math: 2 + 3 = 5, 10 - 4 = 6, 5 x 2 = 10, 10 / 2 = 5
    num_short = (pynini.closure(NEMO_ALL_DIGIT, 1, 6) @ cardinal.final_graph).optimize()
    plus_sym = pynini.cross("+", " അധികം ")
    minus_sym = pynini.cross(pynini.union("-", "−"), " കുറയ്ക്കണം ")
    times_sym = pynini.cross(pynini.union("x", "*", "×"), " ഗുണം ")
    div_sym = pynini.cross(pynini.union("/", "÷"), " ഹരണം ")
    eq_sym = pynini.cross(pynini.union("=", "സമം"), " സമം ")

    op = plus_sym | minus_sym | times_sym | div_sym
    math_expr = (
        num_short
        + opt_space
        + op
        + opt_space
        + num_short
        + opt_space
        + eq_sym
        + opt_space
        + num_short
    )

    # Standalone multiplication: 5 x 2
    times_expr = num_short + opt_space + times_sym + opt_space + num_short

    # 3. Ratio: 5:3 -> അഞ്ചേ മൂന്ന്
    replace_virama = pynini.cdrewrite(pynini.cross("്", "േ"), "", "[EOS]", NEMO_SIGMA)
    num_short_copula = (num_short @ replace_virama).optimize()
    ratio_expr = pynutil.add_weight(num_short_copula + pynutil.delete(":") + pynutil.insert(" ") + num_short, 0.1)
    # 4. Cardinal ranges: 5-10, 10–20
    card_range = num_short + opt_space + pynini.cross(dash, " മുതൽ ") + opt_space + num_short + pynutil.insert(" വരെ")

    # 5. Glued symbols: ©2024, §12
    glued_sym = (
        pynini.cross("©", "പകർപ്പവകാശം ") | pynini.cross("§", "വിഭാഗം ")
    ) + opt_space + num_short

    composite = (time_range | math_expr | times_expr | ratio_expr | card_range | glued_sym).optimize()
    return (pynutil.insert('name: "') + convert_space(composite).optimize() + pynutil.insert('"')).optimize()


class ClassifyFst(GraphFst):
    """
    Final class that composes all other classification grammars. This class can process an entire sentence including punctuation.
    For deployment, this grammar will be compiled and exported to OpenFst Finite State Archive (FAR) File.
    More details to deployment at NeMo/tools/text_processing_deployment.

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
        input_case: str,
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
                f"_{input_case}_ml_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logging.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logging.info("Creating ClassifyFst grammars.")

            cardinal = CardinalFst(deterministic=deterministic)
            cardinal_graph = cardinal.fst

            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            decimal_graph = decimal.fst

            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)
            fraction_graph = fraction.fst

            date = DateFst(cardinal=cardinal)
            date_graph = date.fst

            timefst = TimeFst(cardinal=cardinal)
            time_graph = timefst.fst

            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            ordinal_graph = ordinal.fst

            serial = SerialFst(cardinal=cardinal, deterministic=deterministic)
            serial_graph = serial.fst

            measure = MeasureFst(cardinal=cardinal, decimal=decimal)
            measure_graph = measure.fst

            money = MoneyFst(cardinal=cardinal)
            money_graph = money.fst

            whitelist_graph = WhiteListFst(
                input_case=input_case, deterministic=deterministic, input_file=whitelist
            ).fst

            punctuation = PunctuationFst(deterministic=deterministic)
            punct_graph = punctuation.fst

            word = WordFst(punctuation=punctuation, deterministic=deterministic)
            word_graph = word.fst

            roman = RomanFst(deterministic=deterministic)
            roman_graph = roman.fst

            telephone = TelephoneFst()
            telephone_graph = telephone.fst

            electronic = ElectronicFst(deterministic=deterministic)
            electronic_graph = electronic.fst

            composite_graph = _build_composite_fst(cardinal=cardinal, time_tagger=timefst)

            money_range = (
                money.fst + pynini.closure(pynutil.delete(" "))
                + pynutil.delete(pynini.union("-", "–", "—"))
                + pynutil.insert(' } tokens { name: "മുതൽ" } tokens { ')
                + pynini.closure(pynutil.delete(" ")) + money.fst
                + pynutil.insert(' } tokens { name: "വരെ"')
            )
            # Prefix modifiers "~" ("ഏകദേശം") and "±" ("പ്ലസ് ഓർ മൈനസ്")
            prefix_mod = (
                pynutil.insert('tokens { name: "')
                + (pynini.cross("~", "ഏകദേശം") | pynini.cross("±", "പ്ലസ് ഓർ മൈനസ്"))
                + pynutil.insert('" } ')
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            numeric_semiotic = (
                pynutil.add_weight(cardinal_graph, 1.1)
                | pynutil.add_weight(decimal_graph, 1.1)
                | pynutil.add_weight(fraction_graph, 1.05)
                | pynutil.add_weight(measure_graph, 1.08)
                | pynutil.add_weight(money_graph, 1.08)
            ).optimize()

            classify = (
                pynutil.add_weight(whitelist_graph, 1.01)
                | pynutil.add_weight(composite_graph, 1.03)
                | numeric_semiotic
                | pynutil.add_weight(date_graph, 1.08)
                | pynutil.add_weight(money_range, 1.04)
                | pynutil.add_weight(time_graph, 1.02)
                | pynutil.add_weight(telephone_graph, 1.1)
                | pynutil.add_weight(ordinal_graph, 1.1)
                | pynutil.add_weight(electronic_graph, 1.1)
                | pynutil.add_weight(serial_graph, 1.11)
                | pynutil.add_weight(roman_graph, 1.1)
            )

            classify |= pynutil.add_weight(word_graph, 100.0)

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
                logging.info(f"ClassifyFst grammars are saved to {far_file}.")
