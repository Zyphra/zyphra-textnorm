# Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.cs.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Czech abbreviations,
    contextual titles, symbols, and mathematical operators.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        # Common Czech abbreviations
        abbrev_map = [
            ("např.", "například"),
            ("např", "například"),
            ("Např.", "Například"),
            ("Např", "Například"),
            ("atd.", "a tak dále"),
            ("atd", "a tak dále"),
            ("apod.", "a podobně"),
            ("apod", "a podobně"),
            ("tj.", "to jest"),
            ("tj", "to jest"),
            ("tzn.", "to znamená"),
            ("tzn", "to znamená"),
            ("tzv.", "tak zvaný"),
            ("tzv", "tak zvaný"),
            ("Tzv.", "Tak zvaný"),
            ("Tzv", "Tak zvaný"),
            ("resp.", "respektive"),
            ("resp", "respektive"),
            ("cca", "přibližně"),
            ("Cca", "Přibližně"),
            ("dr.", "doktor"),
            ("Dr.", "doktor"),
            ("Dr", "doktor"),
            ("ing.", "inženýr"),
            ("Ing.", "inženýr"),
            ("Ing", "inženýr"),
            ("prof.", "profesor"),
            ("Prof.", "profesor"),
            ("Prof", "profesor"),
            ("pan", "pan"),
            ("Pan", "Pan"),
            ("pí", "paní"),
            ("pí.", "paní"),
            ("p.", "pan"),
            ("odd.", "oddíl"),
            ("hod.", "hodin"),
            ("min.", "minut"),
            ("tis.", "tisíc"),
            ("mil.", "milionů"),
            ("mld.", "miliard"),
            ("bil.", "bilionů"),
        ]
        abbrevs = pynini.string_map(abbrev_map)

        # Symbols
        symbols_map = [
            ("&", "a"),
            ("©", "copyright"),
            ("§", "paragraf"),
            ("®", "registrovaná známka"),
            ("™", "ochranná známka"),
        ]
        symbols = pynini.string_map(symbols_map)

        # Contextual prefix before a number:
        # "č. 5" -> "číslo pět"
        # "No. 5" -> "číslo pět"
        # "#5" -> "číslo pět"
        # "str. 12" -> "strana dvanáct"
        # "§ 12" -> "paragraf dvanáct"
        # "© 2024" -> "copyright dva tisíce dvacet čtyři"
        # "A & B" -> "A a B"
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        num_prefix = pynini.string_map([
            ("č.", "číslo"),
            ("č", "číslo"),
            ("Č.", "Číslo"),
            ("Č", "Číslo"),
            ("čís.", "číslo"),
            ("No.", "číslo"),
            ("No", "číslo"),
            ("#", "číslo"),
            ("str.", "strana"),
            ("str", "strana"),
            ("s.", "strana"),
            ("§", "paragraf"),
        ])
        abbrev_with_number = (
            num_prefix
            + pynutil.insert(" ")
            + opt_sp
            + cardinal.cardinal_numbers
        ).optimize()

        # Copyright year: "© 2024" -> "copyright dva tisíce dvacet čtyři"
        copyright_year = (
            pynini.cross("©", "copyright")
            + opt_sp
            + pynutil.insert(" ")
            + cardinal.cardinal_numbers
        ).optimize()

        # Ampersand in "A & B"
        ampersand_context = pynini.cross("&", "a")

        # Titles with names: "Dr. Novák" -> "doktor Novák", "Ing. Svoboda" -> "inženýr Svoboda"
        titles_map = [
            ("Dr.", "doktor"),
            ("Dr", "doktor"),
            ("dr.", "doktor"),
            ("Ing.", "inženýr"),
            ("Ing", "inženýr"),
            ("ing.", "inženýr"),
            ("Prof.", "profesor"),
            ("Prof", "profesor"),
            ("prof.", "profesor"),
            ("Doc.", "docent"),
            ("doc.", "docent"),
            ("Mgr.", "magistr"),
            ("mgr.", "magistr"),
            ("Bc.", "bakalář"),
            ("bc.", "bakalář"),
        ]
        titles = pynini.string_map(titles_map)

        self.fst = (
            abbrev_with_number
            | copyright_year
            | titles
            | abbrevs
            | symbols
            | ampersand_context
        ).optimize()
