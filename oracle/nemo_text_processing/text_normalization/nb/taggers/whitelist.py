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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)
from nemo_text_processing.text_normalization.nb.taggers.cardinal import (
    CardinalFst,
)


class WhiteListFst(GraphFst):
    """
    Finite state transducer for Norwegian Bokmål abbreviations, titles, and symbols.
    e.g. f.eks. -> for eksempel
         bl.a. -> blant annet
         osv. -> og så videre
         ca. -> cirka
         dr Lindqvist -> doktor Lindqvist
         nr 5 -> nummer fem
         & -> og
         © -> copyright
         § 12 -> paragraf tolv
    """

    def __init__(self, cardinal: CardinalFst = None, deterministic: bool = True):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        abbrev_map = [
            ("f.eks.", "for eksempel"),
            ("f. eks.", "for eksempel"),
            ("F.eks.", "for eksempel"),
            ("bl.a.", "blant annet"),
            ("bl. a.", "blant annet"),
            ("Bl.a.", "blant annet"),
            ("osv.", "og så videre"),
            ("Osv.", "og så videre"),
            ("ca.", "cirka"),
            ("Ca.", "cirka"),
            ("dvs.", "det vil si"),
            ("Dvs.", "det vil si"),
            ("mfl.", "med flere"),
            ("m.fl.", "med flere"),
            ("pga.", "på grunn av"),
            ("p.g.a.", "på grunn av"),
            ("Pga.", "på grunn av"),
            ("m.m.", "med mer"),
            ("jf.", "jamfør"),
            ("jfr.", "jamfør"),
            ("AS", "aksjeselskap"),
            ("A/S", "aksjeselskap"),
            ("t.o.m.", "til og med"),
            ("f.o.m.", "fra og med"),
            ("e.Kr.", "etter Kristus"),
            ("f.Kr.", "før Kristus"),
        ]
        abbrevs = pynini.string_map(abbrev_map)

        # Titles followed by space: dr Lindqvist -> doktor Lindqvist
        titles_map = [
            ("dr.", "doktor"),
            ("dr", "doktor"),
            ("Dr.", "doktor"),
            ("Dr", "doktor"),
            ("prof.", "professor"),
            ("Prof.", "professor"),
            ("mr.", "mister"),
            ("Mr.", "mister"),
            ("fru", "fru"),
            ("frk.", "frøken"),
            ("cand.", "kandidat"),
            ("mag.", "magister"),
        ]
        titles = pynini.string_map(titles_map)

        # Number abbreviation: nr 5 / nr. 5 / Nr. 5 -> nummer fem
        nr_word = (
            pynini.cross("nr.", "nummer")
            | pynini.cross("nr", "nummer")
            | pynini.cross("Nr.", "nummer")
            | pynini.cross("Nr", "nummer")
            | pynini.cross("No.", "nummer")
            | pynini.cross("no.", "nummer")
        )

        card_graph = cardinal.cardinal_masculine if cardinal else pynini.cross("5", "fem")
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        req_space = pynutil.delete(" ")

        nr_num = nr_word + req_space + pynutil.insert(" ") + card_graph

        # Section symbol: § 12 -> paragraf tolv
        section_sym = (
            pynini.cross("§", "paragraf")
            + opt_space
            + pynutil.insert(" ")
            + card_graph
        )

        # Copyright symbol: © 2024 -> copyright to tusen og tjuefire
        year_graph = cardinal.cardinal_masculine if cardinal else pynini.cross("2024", "to tusen og tjuefire")
        copyright_sym = (
            pynini.cross("©", "copyright")
            + opt_space
            + pynutil.insert(" ")
            + year_graph
        )

        # Standalone symbols
        symbols_map = [
            ("&", "og"),
            ("©", "copyright"),
            ("§", "paragraf"),
            ("¢", "cent"),
            ("~", "omtrent"),
            ("±", "pluss minus"),
        ]
        symbols = pynini.string_map(symbols_map)

        all_whitelist = (
            abbrevs
            | titles
            | nr_num
            | section_sym
            | copyright_sym
            | symbols
        )

        self.graph = all_whitelist.optimize()
        self.fst = self.graph
