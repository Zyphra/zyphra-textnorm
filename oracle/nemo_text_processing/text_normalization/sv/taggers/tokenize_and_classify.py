# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
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
import time

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    NEMO_WHITE_SPACE,
    GraphFst,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.en.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.sv.taggers.abbreviation import AbbreviationFst
from nemo_text_processing.text_normalization.sv.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.sv.taggers.date import DateFst
from nemo_text_processing.text_normalization.sv.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.sv.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.sv.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.sv.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.sv.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.sv.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.sv.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.sv.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.sv.taggers.time import TimeFst
from nemo_text_processing.text_normalization.sv.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.sv.taggers.word import WordFst
from nemo_text_processing.utils.logging import logger


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
                cache_dir, f"sv_tn_{deterministic}_deterministic_{input_case}_{whitelist_file}_tokenize.far"
            )
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating ClassifyFst grammars.")

            start_time = time.time()
            cardinal = CardinalFst(deterministic=deterministic)
            cardinal_graph = cardinal.fst
            logger.debug(f"cardinal: {time.time() - start_time: .2f}s -- {cardinal_graph.num_states()} nodes")

            start_time = time.time()
            ordinal = OrdinalFst(cardinal=cardinal, deterministic=deterministic)
            ordinal_graph = ordinal.fst
            logger.debug(f"ordinal: {time.time() - start_time: .2f}s -- {ordinal_graph.num_states()} nodes")

            start_time = time.time()
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
            decimal_graph = decimal.fst
            logger.debug(f"decimal: {time.time() - start_time: .2f}s -- {decimal_graph.num_states()} nodes")

            start_time = time.time()
            fraction = FractionFst(deterministic=deterministic, ordinal=ordinal, cardinal=cardinal)
            fraction_graph = fraction.fst
            logger.debug(f"fraction: {time.time() - start_time: .2f}s -- {fraction_graph.num_states()} nodes")

            start_time = time.time()
            measure = MeasureFst(cardinal=cardinal, decimal=decimal, fraction=fraction, deterministic=deterministic)
            measure_graph = measure.fst
            logger.debug(f"measure: {time.time() - start_time: .2f}s -- {measure_graph.num_states()} nodes")

            start_time = time.time()
            date_graph = DateFst(cardinal=cardinal, ordinal=ordinal, deterministic=deterministic).fst
            logger.debug(f"date: {time.time() - start_time: .2f}s -- {date_graph.num_states()} nodes")

            start_time = time.time()
            time_graph = TimeFst(cardinal=cardinal, deterministic=deterministic).fst
            logger.debug(f"time: {time.time() - start_time: .2f}s -- {time_graph.num_states()} nodes")

            start_time = time.time()
            telephone_graph = TelephoneFst(deterministic=deterministic).fst
            logger.debug(f"telephone: {time.time() - start_time: .2f}s -- {telephone_graph.num_states()} nodes")

            start_time = time.time()
            electonic_graph = ElectronicFst(deterministic=deterministic).fst
            logger.debug(f"electronic: {time.time() - start_time: .2f}s -- {electonic_graph.num_states()} nodes")

            start_time = time.time()
            money = MoneyFst(cardinal=cardinal, decimal=decimal, deterministic=deterministic)
            money_graph = money.fst
            logger.debug(f"money: {time.time() - start_time: .2f}s -- {money_graph.num_states()} nodes")

            start_time = time.time()
            roman_graph = RomanFst(cardinal=cardinal, ordinal=ordinal, deterministic=deterministic).fst
            logger.debug(f"roman: {time.time() - start_time: .2f}s -- {roman_graph.num_states()} nodes")

            start_time = time.time()
            whitelist_graph = WhiteListFst(
                input_case=input_case, deterministic=deterministic, input_file=whitelist
            ).fst
            logger.debug(f"whitelist: {time.time() - start_time: .2f}s -- {whitelist_graph.num_states()} nodes")

            start_time = time.time()
            punctuation = PunctuationFst(deterministic=deterministic)
            punct_graph = punctuation.fst
            logger.debug(f"punct: {time.time() - start_time: .2f}s -- {punct_graph.num_states()} nodes")

            start_time = time.time()
            word_graph = WordFst(deterministic=deterministic).fst
            logger.debug(f"word: {time.time() - start_time: .2f}s -- {word_graph.num_states()} nodes")

            opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

            # Time ranges: 9:00-17:00, 9:00–17:00 -> nio till sjutton
            range_dash_till = (
                opt_sp
                + pynutil.insert('name: "')
                + pynini.cross(pynini.union("-", "–", "—"), "till")
                + pynutil.insert('"')
                + opt_sp
            ).optimize()
            graph_range_time = (
                time_graph
                + pynutil.insert(" } tokens { ")
                + range_dash_till
                + pynutil.insert(" } tokens { ")
                + time_graph
            ).optimize()

            # Compact leading-currency integer ranges: $10-$20, €10–€20 -> tio dollar till tjugo dollar
            # (Keep upstream $50,00-$100,00 -> femtio dollar - hundra dollar intact; trailing 10-20 € is in MoneyFst)
            graph_range_money = (
                money.leading_int_fst
                + pynutil.insert(" } tokens { ")
                + range_dash_till
                + pynutil.insert(" } tokens { ")
                + money.leading_int_fst
            ).optimize()

            # Number between double quotes: '"5"' -> '"5"', not '"5 tum"'
            quote = pynutil.insert('name: "') + pynini.accep('"') + pynutil.insert('"')
            quoted_number = (
                quote
                + pynutil.insert(" } tokens { ")
                + (cardinal_graph | decimal_graph)
                + pynutil.insert(" } tokens { ")
                + quote
            ).optimize()

            classify = (
                pynutil.add_weight(whitelist_graph, 1.01)
                | pynutil.add_weight(time_graph, 1.1)
                | pynutil.add_weight(date_graph, 1.09)
                | pynutil.add_weight(decimal_graph, 1.1)
                | pynutil.add_weight(measure_graph, 1.1)
                | pynutil.add_weight(cardinal_graph, 1.1)
                | pynutil.add_weight(ordinal_graph, 1.1)
                | pynutil.add_weight(money_graph, 1.1)
                | pynutil.add_weight(telephone_graph, 1.1)
                | pynutil.add_weight(electonic_graph, 1.1)
                | pynutil.add_weight(fraction_graph, 1.1)
                | pynutil.add_weight(roman_graph, 1.1)
                | pynutil.add_weight(graph_range_time, 1.09)
                | pynutil.add_weight(graph_range_money, 1.1)
                | pynutil.add_weight(quoted_number, 1.08)
                | pynutil.add_weight(cardinal.serial, 2.0)
            )

            if not deterministic:
                abbreviation_graph = AbbreviationFst(whitelist, deterministic=deterministic).fst
                classify |= pynutil.add_weight(abbreviation_graph, 100)

            punct = pynutil.insert("tokens { ") + pynutil.add_weight(punct_graph, weight=2.1) + pynutil.insert(" }")
            punct = pynini.closure(
                pynini.compose(pynini.closure(NEMO_WHITE_SPACE, 1), delete_extra_space)
                | (pynutil.insert(" ") + punct),
                1,
            )

            # Prefix ~ ("ungefär") and ± ("plus minus") as a lightweight token prefix before any token!
            # Wait: what if `~` is standalone or inside a URL `http://example.com/~user`?
            # In a URL, `ElectronicFst` consumes the whole `http://example.com/~user` as ONE `token`!
            # Only when `~` or `±` is at the start of a token (followed by a digit, currency symbol, or space + token) does `prefix_tok` fire!
            # Better yet: if `prefix_tok` is placed in `token_plus_punct` right before `token`, let's check:
            # `~50`: `prefix_tok` matches `~` -> `tokens { name: "ungefär" } `, then `token` matches `50` -> `tokens { cardinal { integer: "femtio" } }`!
            # `~$100`: `prefix_tok` matches `~`, then `token` matches `$100`!
            # `~10 km`: `prefix_tok` matches `~`, then `token` matches `10 km`!
            # `±10%`: `prefix_tok` matches `±`, then `token` matches `10%`!
            # `±2 °C`: `prefix_tok` matches `±`, then `token` matches `2 °C`!
            # `~ 50`: `prefix_tok` matches `~ `, then `token` matches `50`!
            # ZERO state duplication of `classify`! Look how small `prefix_tok` is: ~25 states!
            prefix_tok = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(pynini.cross("~", "ungefär") | pynini.cross("±", "plus\u00a0minus"), 1.05)
                + pynutil.insert('" } ')
                + opt_sp
            ).optimize()

            classify |= pynutil.add_weight(word_graph, 100)
            token = pynutil.insert("tokens { ") + classify + pynutil.insert(" }")
            possibly_prefixed_token = pynini.closure(prefix_tok, 0, 1) + token
            token_plus_punct = (
                pynini.closure(punct + pynutil.insert(" "))
                + possibly_prefixed_token
                + pynini.closure(pynutil.insert(" ") + punct)
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
