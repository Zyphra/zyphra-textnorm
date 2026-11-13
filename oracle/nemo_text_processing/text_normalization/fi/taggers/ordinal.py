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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Finnish ordinals, e.g.
        "1." -> tokens { name: "ensimmäinen" }
        "2." -> tokens { name: "toinen" }
        "3." -> tokens { name: "kolmas" }
        "3:s" -> tokens { name: "kolmas" }
        "3:e" -> tokens { name: "kolmas" }
        "3:tta" -> tokens { name: "kolmatta" }
        "3:nnen" -> tokens { name: "kolmannen" }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        ord_1_19_map = [
            ("1", "ensimmäinen"),
            ("2", "toinen"),
            ("3", "kolmas"),
            ("4", "neljäs"),
            ("5", "viides"),
            ("6", "kuudes"),
            ("7", "seitsemäs"),
            ("8", "kahdeksas"),
            ("9", "yhdeksäs"),
            ("10", "kymmenes"),
            ("11", "yhdestoista"),
            ("12", "kahdestoista"),
            ("13", "kolmestoista"),
            ("14", "neljästoista"),
            ("15", "viidestoista"),
            ("16", "kuudestoista"),
            ("17", "seitsemästoista"),
            ("18", "kahdeksastoista"),
            ("19", "yhdeksästoista"),
        ]
        ord_1_19 = pynini.string_map(ord_1_19_map)

        ord_ties_map = [
            ("20", "kahdeskymmenes"),
            ("30", "kolmaskymmenes"),
            ("40", "neljäskymmenes"),
            ("50", "viideskymmenes"),
            ("60", "kuudeskymmenes"),
            ("70", "seitsemäskymmenes"),
            ("80", "kahdeksaskymmenes"),
            ("90", "yhdeksäskymmenes"),
        ]
        ord_ties = pynini.string_map(ord_ties_map)

        ord_tie_prefix = pynini.string_map([
            ("2", "kahdeskymmenes"),
            ("3", "kolmaskymmenes"),
            ("4", "neljäskymmenes"),
            ("5", "viideskymmenes"),
            ("6", "kuudeskymmenes"),
            ("7", "seitsemäskymmenes"),
            ("8", "kahdeksaskymmenes"),
            ("9", "yhdeksäskymmenes"),
        ])
        digits_1_9 = pynini.string_map(ord_1_19_map[:9])
        ord_21_99 = ord_tie_prefix + digits_1_9

        ord_large = pynini.string_map([
            ("100", "sadas"),
            ("200", "kahdessadas"),
            ("1000", "tuhannes"),
            ("1000000", "miljoonas"),
        ])

        ord_all_nums = (ord_1_19 | ord_ties | ord_21_99 | ord_large).optimize()

        # Dot ordinals: "1.", "2.", "3.", etc.
        dot_ordinal = ord_all_nums + pynutil.delete(".")

        # Suffix ordinals: "1:nen", "1:s", "2:nen", "2:s", "3:s", "3:e", etc.
        colon_or_dash = pynini.union(":", "-")
        suffix_nom = colon_or_dash + pynini.union("nen", "s", "e", "st", "nd", "rd", "th")
        suffixed_nom_graph = ord_all_nums + pynutil.delete(suffix_nom)

        # Inflected suffix forms
        inflected_suffixes = pynini.string_map([
            ("1:nnen", "ensimmäisen"),
            ("1-nnen", "ensimmäisen"),
            ("1:stä", "ensimmäisestä"),
            ("1-stä", "ensimmäisestä"),
            ("1:een", "ensimmäiseen"),
            ("1-een", "ensimmäiseen"),
            ("1:llä", "ensimmäisellä"),
            ("1-llä", "ensimmäisellä"),
            ("1:lle", "ensimmäiselle"),
            ("1-lle", "ensimmäiselle"),
            ("1:ksi", "ensimmäiseksi"),
            ("1-ksi", "ensimmäiseksi"),
            ("1:ntä", "ensimmäistä"),
            ("1-ntä", "ensimmäistä"),
            ("2:sen", "toisen"),
            ("2-sen", "toisen"),
            ("2:sta", "toisesta"),
            ("2-sta", "toisesta"),
            ("2:een", "toiseen"),
            ("2-een", "toiseen"),
            ("2:lla", "toisella"),
            ("2-lla", "toisella"),
            ("2:lle", "toiselle"),
            ("2-lle", "toiselle"),
            ("2:ksi", "toiseksi"),
            ("2-ksi", "toiseksi"),
            ("3:nnen", "kolmannen"),
            ("3-nnen", "kolmannen"),
            ("3:tta", "kolmatta"),
            ("3-tta", "kolmatta"),
            ("3:teen", "kolmanteen"),
            ("3-teen", "kolmanteen"),
            ("3:ssa", "kolmannessa"),
            ("3-ssa", "kolmannessa"),
            ("3:sta", "kolmannesta"),
            ("3-sta", "kolmannesta"),
            ("3:lla", "kolmannella"),
            ("3-lla", "kolmannella"),
            ("3:lle", "kolmannelle"),
            ("3-lle", "kolmannelle"),
            ("3:ksi", "kolmanneksi"),
            ("3-ksi", "kolmanneksi"),
            ("3:ntena", "kolmantena"),
            ("3-ntena", "kolmantena"),
            ("4:nnen", "neljännen"),
            ("4-nnen", "neljännen"),
            ("4:ttä", "neljättä"),
            ("4-ttä", "neljättä"),
            ("5:nnen", "viidennen"),
            ("5-nnen", "viidennen"),
            ("5:ttä", "viidettä"),
            ("5-ttä", "viidettä"),
        ])

        # Contextual ordinals before words like "sija", "kerros", "palkinto", "luokka", "päivä"
        context_words = pynini.string_map([
            ("sija", "sija"),
            ("sijan", "sijan"),
            ("sijalle", "sijalle"),
            ("palkinto", "palkinto"),
            ("palkinnon", "palkinnon"),
            ("kerros", "kerros"),
            ("kerroksen", "kerroksen"),
            ("kerroksessa", "kerroksessa"),
            ("luokka", "luokka"),
            ("luokan", "luokan"),
            ("osa", "osa"),
            ("luku", "luku"),
            ("vuosisata", "vuosisata"),
            ("vuosisadan", "vuosisadan"),
            ("vuosisadalla", "vuosisadalla"),
            ("päivä", "päivä"),
            ("päivänä", "päivänä"),
        ])
        contextual_ord = (
            dot_ordinal + pynini.accep(" ") + context_words
        )

        all_ordinals = (
            contextual_ord
            | dot_ordinal
            | suffixed_nom_graph
            | inflected_suffixes
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_ordinals).optimize()
            + pynutil.insert('"')
        ).optimize()
