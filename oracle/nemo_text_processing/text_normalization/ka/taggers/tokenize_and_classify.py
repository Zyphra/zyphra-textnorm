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

from nemo_text_processing.text_normalization.en.graph_utils import (
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
from nemo_text_processing.text_normalization.ka.graph_utils import glue_suffix
from nemo_text_processing.text_normalization.ka.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.ka.taggers.date import DateFst
from nemo_text_processing.text_normalization.ka.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.ka.taggers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.ka.taggers.fraction import FractionFst
from nemo_text_processing.text_normalization.ka.taggers.measure import MeasureFst
from nemo_text_processing.text_normalization.ka.taggers.money import MoneyFst
from nemo_text_processing.text_normalization.ka.taggers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.ka.taggers.punctuation import PunctuationFst
from nemo_text_processing.text_normalization.ka.taggers.roman import RomanFst
from nemo_text_processing.text_normalization.ka.taggers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.ka.taggers.time import TimeFst
from nemo_text_processing.text_normalization.ka.taggers.whitelist import WhiteListFst
from nemo_text_processing.text_normalization.ka.taggers.word import WordFst
from nemo_text_processing.text_normalization.ka.verbalizers.time import TimeFst as TimeVerbalizer
from nemo_text_processing.utils.logging import logger


def _build_composite_fst(cardinal: CardinalFst, time_tagger: TimeFst) -> pynini.Fst:
    opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
    dash = pynini.union("-", "–", "—", "֊")

    # 1. Time ranges: "9:00-17:00", "09:00–17:00" -> "ცხრიდან ჩვიდმეტამდე"
    time_verb = TimeVerbalizer().fst
    hm_pat = pynini.closure(NEMO_DIGIT, 1, 2) + ":" + NEMO_DIGIT ** 2
    hm_from = glue_suffix((hm_pat @ time_tagger.fst @ time_verb) + pynutil.insert("+დან"))
    hm_to = glue_suffix((hm_pat @ time_tagger.fst @ time_verb) + pynutil.insert("+მდე"))
    time_range = hm_from + opt_space + pynutil.delete(dash) + pynutil.insert(" ") + opt_space + hm_to

    # 2. Number abbreviations before numbers: "№ 5", "No. 5" -> "ნომერი ხუთი", "გვ. 20" -> "გვერდი ოცი"
    num_abbrevs = pynini.string_map([
        ("№", "ნომერი"),
        ("No.", "ნომერი"),
        ("no.", "ნომერი"),
        ("გვ.", "გვერდი"),
        ("გვ", "გვერდი"),
        ("ტ.", "ტომი"),
        ("ტ", "ტომი"),
        ("სურ.", "სურათი"),
        ("ცხრ.", "ცხრილი"),
    ])
    abbrev_num = num_abbrevs + opt_space + pynutil.insert(" ") + (cardinal.number | cardinal.range_graph)

    # 3. Trailing eras: "500 BC" -> "ჩვენს ერამდე ხუთასი"
    era_bc = pynini.union("BC", "B.C.", "BCE", "B.C.E.", "ძვ. წ.", "ძვ.წ.")
    era_ad = pynini.union("AD", "A.D.", "CE", "C.E.", "ახ. წ.", "ახ.წ.", "ჩვ. წ.")
    year_num = (pynini.closure(NEMO_DIGIT, 1, 4) @ cardinal.all_nums_no_tokens).optimize()
    era_trailing = (
        pynutil.insert("ჩვენს ერამდე ") + year_num + pynutil.delete(" ") + pynutil.delete(era_bc)
    ) | (
        pynutil.insert("ჩვენი ერით ") + year_num + pynutil.delete(" ") + pynutil.delete(era_ad)
    )

    composite = (time_range | abbrev_num | era_trailing).optimize()
    return (pynutil.insert('name: "') + convert_space(composite).optimize() + pynutil.insert('"')).optimize()


class ClassifyFst(GraphFst):
    """
    Final class that composes all other classification grammars for Georgian.
    This class can process an entire sentence.

    Args:
        input_case: accepting either "lower_cased" or "cased" input
        deterministic: if True will provide a single transduction option
        cache_dir: path to a dir with .far grammar file
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
        super().__init__(name="tokenize_and_classify", kind="classify")

        far_file = None
        if cache_dir is not None and cache_dir != "None":
            os.makedirs(cache_dir, exist_ok=True)
            far_file = os.path.join(cache_dir, f"_ka_tn_{input_case}.far")
        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["tokenize_and_classify"]
            no_digits = pynini.closure(pynini.difference(NEMO_CHAR, NEMO_DIGIT))
            self.fst_no_digits = pynini.compose(self.fst, no_digits).optimize()
            logger.info(f"ClassifyFst.fst was restored from {far_file}.")
        else:
            logger.info("Creating Georgian ClassifyFst grammars.")

            base_cardinal = CardinalFst()
            ordinal = OrdinalFst(base_cardinal)
            ordinal_graph = ordinal.fst

            cardinal = CardinalFst(ordinal=ordinal)
            cardinal_graph = cardinal.fst

            fraction = FractionFst(cardinal=cardinal, ordinal=ordinal)
            fraction_graph = fraction.fst

            decimal = DecimalFst(cardinal)
            decimal_graph = decimal.fst

            measure_graph = MeasureFst(cardinal=cardinal, decimal=decimal).fst
            word_graph = WordFst().fst
            time_tagger = TimeFst(cardinal=cardinal)
            time_graph = time_tagger.fst
            money_graph = MoneyFst(cardinal=cardinal, decimal=decimal).fst

            # Range of money: 10-20 € -> "ათიდან ოც ევრომდე"
            dash = pynini.union("-", "–", "—", "֊")
            currency_from = glue_suffix(
                money_graph
                @ pynini.cdrewrite(
                    pynutil.insert("+დან"),
                    pynini.accep('currency: "') + pynini.closure(NEMO_NOT_QUOTE, 1),
                    '"',
                    NEMO_SIGMA,
                )
            )
            currency_to = glue_suffix(
                money_graph
                @ pynini.cdrewrite(
                    pynutil.insert("+მდე"),
                    pynini.accep('currency: "') + pynini.closure(NEMO_NOT_QUOTE, 1),
                    '"',
                    NEMO_SIGMA,
                )
            )
            money_range = (
                currency_from
                + delete_space
                + pynutil.delete(dash)
                + delete_space
                + pynutil.insert(' } tokens { ')
                + currency_to
            )

            punct_graph = PunctuationFst().fst
            date_graph = DateFst(cardinal=cardinal).fst
            telephone_graph = TelephoneFst().fst
            electronic_graph = ElectronicFst().fst
            roman_graph = RomanFst(cardinal=cardinal, ordinal=ordinal).fst
            composite_graph = _build_composite_fst(cardinal=cardinal, time_tagger=time_tagger)
            whitelist_graph = WhiteListFst(
                input_case=input_case, deterministic=deterministic, input_file=whitelist
            ).fst

            # Prefix modifiers "~" (დაახლოებით) and "±" (პლუს-მინუს)
            prefix_mod = (
                pynutil.insert('tokens { name: "')
                + pynutil.add_weight(
                    pynini.cross("~", "დაახლოებით") | pynini.cross("±", "პლუს-მინუს"),
                    -2.0,
                )
                + pynutil.insert('" } ')
                + pynini.closure(pynutil.delete(" "), 0, 1)
            ).optimize()

            classify = (
                pynutil.add_weight(whitelist_graph, 1.01)
                | pynutil.add_weight(composite_graph, 1.02)
                | pynutil.add_weight(roman_graph, 1.04)
                | pynutil.add_weight(time_graph, 1.1)
                | pynutil.add_weight(decimal_graph, 1.1)
                | pynutil.add_weight(measure_graph, 0.9)
                | pynutil.add_weight(cardinal_graph, 1.1)
                | pynutil.add_weight(ordinal_graph, 1.05)
                | pynutil.add_weight(fraction_graph, 1.09)
                | pynutil.add_weight(money_graph, 1.05)
                | pynutil.add_weight(money_range, 1.06)
                | pynutil.add_weight(date_graph, 1.07)
                | pynutil.add_weight(telephone_graph, 1.08)
                | pynutil.add_weight(electronic_graph, 1.11)
                | pynutil.add_weight(cardinal.serial, 1.5)
                | pynutil.add_weight(word_graph, 100)
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
