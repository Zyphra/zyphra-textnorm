# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

# Adapted from https://github.com/google/TextNormalizationCoveringGrammars
# Russian minimally supervised number grammar.


import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst
from nemo_text_processing.text_normalization.ru.taggers.number_names import (
    ORDINAL_CLASSES,
    ordinal_resolver,
)

_STRESSED, _HARD, _SOFT = ORDINAL_CLASSES


def _by_class(hard: str, soft: str) -> dict:
    return {_STRESSED: hard, _HARD: hard, _SOFT: soft}


# Written ordinal suffix -> form of the ordinal. The suffix gives the last letters of the word: "-й" первый / второй /
# третий, "-е" пятые / третье (the only forms ending in "е"; a hard stem reads the plural, as in "1990-е"), "-х" and
# "-м" the plural genitive and the masculine prepositional.
SUFFIXES = {
    "й": "masc_nom",
    "ый": "masc_nom",
    "ой": "masc_nom",
    "ий": "masc_nom",
    "я": "fem_nom",
    "ая": "fem_nom",
    "ья": "fem_nom",
    "е": _by_class("pl_nom", "neut_nom"),
    "ые": "pl_nom",
    "ое": "neut_nom",
    "ье": "neut_nom",
    "и": "pl_nom",
    "ьи": "pl_nom",
    "го": "masc_gen",
    "ого": "masc_gen",
    "его": "masc_gen",
    "ей": "fem_gen",
    "му": "masc_dat",
    "ому": "masc_dat",
    "ему": "masc_dat",
    "м": "masc_prep",
    "ом": "masc_prep",
    "ем": "masc_prep",
    "ым": "masc_ins",
    "им": "masc_ins",
    "х": "pl_gen",
    "ых": "pl_gen",
    "их": "pl_gen",
    "ми": "pl_ins",
    "ыми": "pl_ins",
    "ю": "fem_acc",
    "ую": "fem_acc",
}


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying ordinals written with a suffix, e.g.
        "2-й" -> ordinal { integer: "второй" }
        "1990-е" -> ordinal { integer: "тысяча девятьсот девяностые" }
        "2020s" -> ordinal { integer: "две тысячи двадцатые" }
        "20-х" -> ordinal { integer: "двадцатых" }
    Bare digits are cardinals. "-х" after a number not ending in 0 is the cardinal genitive ("3-х" -> "трех", see
    CardinalFst); after a round number it is the ordinal plural ("1960-х" -> "тысяча девятьсот шестидесятых").

    Args:
        number_names: number names built by number_names.get_number_names()
        alternative_formats: alternative format for cardinal and ordinal numbers
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, number_names: dict, alternative_formats: dict, deterministic=False):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        stem = number_names['ordinal_stem']
        self.ordinal_numbers = number_names['ordinal']

        suffixes = {k: v for k, v in SUFFIXES.items() if k != "х"}
        written = pynini.union(*suffixes)
        marked = stem + pynutil.delete("-") + written
        round_number = pynini.closure(NEMO_DIGIT) + "0"
        marked |= pynini.compose(round_number, stem) + pynutil.delete("-") + pynini.accep("х")
        graph = (marked @ ordinal_resolver(SUFFIXES)).optimize()

        # International decades: "2020s", "1990s", "2020's", "'90s" -> plural nominative ordinal ("две тысячи двадцатые")
        intl_decade_digits = (pynini.union("18", "19", "20") + NEMO_DIGIT + "0") | (
            pynutil.delete("'") + pynini.difference(NEMO_DIGIT, "0") + "0"
        )
        intl_decade = (
            pynini.compose(intl_decade_digits, self.ordinal_numbers["pl_nom"])
            + pynutil.delete(pynini.union("s", "'s"))
        ).optimize()
        graph |= pynutil.add_weight(intl_decade, -0.1)

        final_graph = pynutil.insert("integer: \"") + graph + pynutil.insert("\"")
        self.fst = self.add_tokens(final_graph).optimize()
