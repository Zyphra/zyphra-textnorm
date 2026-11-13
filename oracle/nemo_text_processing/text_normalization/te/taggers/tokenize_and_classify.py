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

from nemo_text_processing.text_normalization.te.graph_utils import (
    NEMO_ALL_DIGIT,
    NEMO_SPACE,
    NEMO_WHITE_SPACE,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.te.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.te.taggers.date import DateFst
from nemo_text_processing.text_normalization.te.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.te.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.te.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.te.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.te.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.te.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.te.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.te.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.te.taggers.serial import SerialFst
from nemo_text_processing.text_normalization.te.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.te.taggers.time import TimeFst
from nemo_text_processing.text_normalization.te.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.te.taggers.word import WordFst
from nemo_text_processing.text_normalization.te.verbalizers.time import TimeFst as TimeVerbalizer


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
    time_range = spoken_time + opt_space + pynini.cross(dash, " నుండి ") + opt_space + spoken_time

    # 2. En-dash cardinal ranges: "10–20" -> "పది నుండి ఇరవై"
    num_short = (pynini.closure(NEMO_ALL_DIGIT, 1, 6) @ cardinal.final_graph).optimize()
    endash_range = num_short + opt_space + pynini.cross("–", " నుండి ") + opt_space + num_short

    # 3. Glued copyright / section symbols: "©2024", "§12" (spaced "© 2024", "§ 12" are handled via whitelist)
    glued_sym = (
        (pynini.cross("©", "కాపీరైట్ ") | pynini.cross("§", "విభాగం "))
        + num_short
    )

    composite = (time_range | endash_range | glued_sym).optimize()
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
                f"_{input_case}_te_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            logging.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logging.info(f"Creating ClassifyFst grammars.")

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

            # Semiotic classes that can take a prefix modifier "~" ("సుమారు") or "±" ("ప్లస్ మైనస్")
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
                | pynutil.add_weight(time_graph, 1.1)
                | pynutil.add_weight(telephone_graph, 1.1)
                | pynutil.add_weight(ordinal_graph, 1.1)
                | pynutil.add_weight(electronic_graph, 1.1)
                | pynutil.add_weight(serial_graph, 1.11)
                | pynutil.add_weight(roman_graph, 1.1)
            )

            prefix_mod = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(
                    pynini.cross("~", "సుమారు") | pynini.cross("±", convert_space(pynini.accep("ప్లస్ మైనస్"))),
                    -2.0,
                )
                + pynutil.insert('" } ')
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=2.1) + pynutil.insert(" }")
            punct = pynini.closure(
                pynini.union(
                    pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space),
                    (pynutil.insert(NEMO_SPACE) + punct),
                ),
                1,
            )

            classify_all = pynini.union(classify, pynutil.add_weight(word_graph, 100))
            plain_token = pynutil.insert("tokens { ") + classify_all + pynutil.insert(" }")
            prefixed_numeric_token = prefix_mod + pynutil.insert("tokens { ") + numeric_semiotic + pynutil.insert(" }")
            token = plain_token | prefixed_numeric_token
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(NEMO_SPACE))
                + token
                + pynini.closure(pynutil.insert(NEMO_SPACE) + punct)
            )

            graph = token_plus_punct + pynini.closure(
                pynini.union(
                    pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space),
                    (pynutil.insert(NEMO_SPACE) + punct + pynutil.insert(NEMO_SPACE)),
                )
                + token_plus_punct
            )

            graph = delete_space + graph + delete_space
            graph = pynini.union(graph, punct)

            self.fst = graph.optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logging.info(f"ClassifyFst grammars are saved to {far_file}.")
