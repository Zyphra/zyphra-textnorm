# Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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
    NEMO_DIGIT,
    NEMO_WHITE_SPACE,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.en.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.hu.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.hu.taggers.date import DateFst
from nemo_text_processing.text_normalization.hu.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.hu.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.hu.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.hu.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.hu.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.hu.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.hu.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.hu.taggers.serial import SerialFst
from nemo_text_processing.text_normalization.hu.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.hu.taggers.time import TimeFst
from nemo_text_processing.text_normalization.hu.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.hu.taggers.word import WordFst
from nemo_text_processing.text_normalization.hu.verbalizers.time import TimeFst as TimeVerbalizer
from nemo_text_processing.utils.logging import logger


def _build_composite_fst(
    cardinal: CardinalFst,
    ordinal: OrdinalFst,
    time_tagger: TimeFst,
    deterministic: bool = True,
) -> pynini.Fst:
    opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

    # 1. International decades: "1990s" -> "ezerkilencszázkilencvenes évek", "2020s" -> "kettőezer-húszas évek"
    front_dec = (pynini.union("18", "19", "20") + pynini.union("0", "1", "4", "5", "7", "9") + "0") + pynini.cross(
        pynini.union("s", "'s"), "-es"
    )
    back_dec = (pynini.union("18", "19", "20") + pynini.union("2", "3", "6", "8") + "0") + pynini.cross(
        pynini.union("s", "'s"), "-as"
    )
    decade_intl = ((front_dec | back_dec) @ cardinal.suffixed) + pynutil.insert(" évek")

    # 2. Spaced ordinal before § (textnorm.py spaces '.' before '§': "12. §" -> "12 . §")
    sec_ord = (
        ordinal.filtered_ordinals
        + opt_space
        + pynutil.delete(".")
        + pynini.accep(" ")
        + pynini.cross("§", "paragrafus")
    )

    # 3. Trailing English eras: "500 BC" -> "Krisztus előtt ötszáz", "500 AD" -> "időszámításunk szerint ötszáz"
    era_bc = pynini.union("BC", "B.C.")
    era_bce = pynini.union("BCE", "B.C.E.")
    era_ad = pynini.union("AD", "A.D.", "CE", "C.E.")
    year_num = (pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal.graph).optimize()
    era_trailing = (
        (pynutil.insert("Krisztus előtt ") + year_num + pynutil.delete(" ") + pynutil.delete(era_bc))
        | (pynutil.insert("időszámításunk előtt ") + year_num + pynutil.delete(" ") + pynutil.delete(era_bce))
        | (pynutil.insert("időszámításunk szerint ") + year_num + pynutil.delete(" ") + pynutil.delete(era_ad))
    )

    # 4. Time ranges: "9:00-17:00", "9:00–17:00" -> "kilenc órától tizenhét óráig"
    time_verb = TimeVerbalizer(deterministic=deterministic).fst
    hm_from = (
        pynini.closure(NEMO_DIGIT, 1, 2)
        + ":"
        + NEMO_DIGIT**2
        + pynutil.insert("-tól")
    ) @ time_tagger.fst @ time_verb
    hm_to = (
        pynini.closure(NEMO_DIGIT, 1, 2)
        + ":"
        + NEMO_DIGIT**2
        + pynutil.insert("-ig")
    ) @ time_tagger.fst @ time_verb
    time_range = hm_from + opt_space + pynini.cross(pynini.union("-", "–", "—"), " ") + opt_space + hm_to

    composite = (decade_intl | sec_ord | era_trailing | time_range).optimize()
    return (pynutil.insert("name: \"") + convert_space(composite).optimize() + pynutil.insert("\"")).optimize()


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
        deterministic: bool = False,
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
                f"_{input_case}_hu_tn_{deterministic}_deterministic{whitelist_file}.far",
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info(f"Creating ClassifyFst grammars. This might take some time...")

            self.cardinal = CardinalFst(deterministic=deterministic)
            cardinal_graph = self.cardinal.fst

            self.ordinal = OrdinalFst(cardinal=self.cardinal, deterministic=deterministic)
            ordinal_graph = self.ordinal.fst

            self.decimal = DecimalFst(cardinal=self.cardinal, deterministic=deterministic)
            decimal_graph = self.decimal.fst

            self.fraction = FractionFst(
                cardinal=self.cardinal,
                ordinal=self.ordinal,
                deterministic=deterministic,
            )
            fraction_graph = self.fraction.fst
            self.measure = MeasureFst(
                cardinal=self.cardinal,
                decimal=self.decimal,
                fraction=self.fraction,
                deterministic=deterministic,
            )
            measure_graph = self.measure.fst
            self.date = DateFst(cardinal=self.cardinal, deterministic=deterministic)
            date_graph = self.date.fst
            word_graph = WordFst(deterministic=deterministic).fst
            self.time = TimeFst(self.cardinal, deterministic=deterministic)
            time_graph = self.time.fst
            self.telephone = TelephoneFst(deterministic=deterministic)
            telephone_graph = self.telephone.fst
            self.electronic = ElectronicFst(deterministic=deterministic)
            electronic_graph = self.electronic.fst
            self.money = MoneyFst(
                cardinal=self.cardinal,
                decimal=self.decimal,
                deterministic=deterministic,
            )
            money_graph = self.money.fst
            self.roman = RomanFst(cardinal=self.cardinal, ordinal=self.ordinal, deterministic=deterministic)
            roman_graph = self.roman.fst
            self.serial = SerialFst(cardinal=self.cardinal, ordinal=self.ordinal, deterministic=deterministic)
            serial_graph = self.serial.fst
            self.whitelist = WhiteListFst(input_case=input_case, deterministic=deterministic, input_file=whitelist)
            whitelist_graph = self.whitelist.fst
            composite_graph = _build_composite_fst(
                cardinal=self.cardinal,
                ordinal=self.ordinal,
                time_tagger=self.time,
                deterministic=deterministic,
            )
            punct_graph = PunctuationFst(deterministic=deterministic).fst

            # Prefix modifiers "~" (körülbelül) and "±" (plusz-mínusz) emit their own separate token
            # BEFORE the following semiotic token without duplicating any classifier subgraph!
            prefix_mod = (
                pynutil.insert("tokens { name: \"")
                + pynutil.add_weight(
                    pynini.cross("~", "körülbelül") | pynini.cross("±", "plusz-mínusz"),
                    -1.0,
                )
                + pynutil.insert("\" } ")
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            classify = (
                pynutil.add_weight(whitelist_graph, 1.01)
                | pynutil.add_weight(composite_graph, 1.05)
                | pynutil.add_weight(roman_graph, 1.06)
                | pynutil.add_weight(time_graph, 1.09)
                | pynutil.add_weight(measure_graph, 1.08)
                | pynutil.add_weight(cardinal_graph, 1.1)
                | pynutil.add_weight(fraction_graph, 1.09)
                | pynutil.add_weight(date_graph, 1.1)
                | pynutil.add_weight(ordinal_graph, 1.1)
                | pynutil.add_weight(decimal_graph, 1.1)
                | pynutil.add_weight(money_graph, 1.1)
                | pynutil.add_weight(telephone_graph, 1.1)
                | pynutil.add_weight(electronic_graph, 1.11)
                | pynutil.add_weight(serial_graph, 1.12)
                | pynutil.add_weight(word_graph, 200)
            )
            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=2.1) + pynutil.insert(" }")
            punct = pynini.closure(
                pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space)
                | (pynutil.insert(" ") + punct),
                1,
            )
            token = pynini.closure(prefix_mod, 0, 1) + pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" ")) + token + pynini.closure(pynutil.insert(" ") + punct)
            )

            graph = token_plus_punct + pynini.closure(
                (
                    pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space)
                    | (pynutil.insert(" ") + punct + pynutil.insert(" "))
                )
                + token_plus_punct
            )

            graph = delete_space + graph + delete_space
            graph |= punct

            self.fst = graph.optimize()

            if far_file:
                generator_main(far_file, {"tokenize_and_classify": self.fst})
                logger.info(f"ClassifyFst grammars are saved to {far_file}.")
