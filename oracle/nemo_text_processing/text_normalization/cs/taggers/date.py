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
    NEMO_DIGIT,
    GraphFst,
)


class DateFst(GraphFst):
    """
    Finite state transducer for classifying Czech dates.
    Disambiguates dot ordinals before months, numeric dates, ISO dates, eras,
    and year ranges.
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        # Day numbers 1..31 to genitive ordinals
        day_gen_map = [
            ("1", "prvního"),
            ("01", "prvního"),
            ("2", "druhého"),
            ("02", "druhého"),
            ("3", "třetího"),
            ("03", "třetího"),
            ("4", "čtvrtého"),
            ("04", "čtvrtého"),
            ("5", "pátého"),
            ("05", "pátého"),
            ("6", "šestého"),
            ("06", "šestého"),
            ("7", "sedmého"),
            ("07", "sedmého"),
            ("8", "osmého"),
            ("08", "osmého"),
            ("9", "devátého"),
            ("09", "devátého"),
            ("10", "desátého"),
            ("11", "jedenáctého"),
            ("12", "dvanáctého"),
            ("13", "třináctého"),
            ("14", "čtrnáctého"),
            ("15", "patnáctého"),
            ("16", "šestnáctého"),
            ("17", "sedmnáctého"),
            ("18", "osmnáctého"),
            ("19", "devatenáctého"),
            ("20", "dvacátého"),
            ("21", "dvacátého prvního"),
            ("22", "dvacátého druhého"),
            ("23", "dvacátého třetího"),
            ("24", "dvacátého čtvrtého"),
            ("25", "dvacátého pátého"),
            ("26", "dvacátého šestého"),
            ("27", "dvacátého sedmého"),
            ("28", "dvacátého osmého"),
            ("29", "dvacátého devátého"),
            ("30", "třicátého"),
            ("31", "třicátého prvního"),
        ]
        day_gen = pynini.string_map(day_gen_map)

        # Months in written form (genitive for dates)
        months_written_map = [
            ("ledna", "ledna"),
            ("února", "února"),
            ("března", "března"),
            ("dubna", "dubna"),
            ("května", "května"),
            ("června", "června"),
            ("července", "července"),
            ("srpna", "srpna"),
            ("září", "září"),
            ("října", "října"),
            ("listopadu", "listopadu"),
            ("prosince", "prosince"),
            ("leden", "ledna"),
            ("únor", "února"),
            ("březen", "března"),
            ("duben", "dubna"),
            ("květen", "května"),
            ("červen", "června"),
            ("červenec", "července"),
            ("srpen", "srpna"),
            ("říjen", "října"),
            ("listopad", "listopadu"),
            ("prosinec", "prosince"),
            # Common abbreviations
            ("led.", "ledna"),
            ("led", "ledna"),
            ("úno.", "února"),
            ("úno", "února"),
            ("bře.", "března"),
            ("bře", "března"),
            ("dub.", "dubna"),
            ("dub", "dubna"),
            ("kvě.", "května"),
            ("kvě", "května"),
            ("čvn.", "června"),
            ("čvn", "června"),
            ("čvc.", "července"),
            ("čvc", "července"),
            ("srp.", "srpna"),
            ("srp", "srpna"),
            ("zář.", "září"),
            ("zář", "září"),
            ("říj.", "října"),
            ("říj", "října"),
            ("lis.", "listopadu"),
            ("lis", "listopadu"),
            ("pro.", "prosince"),
            ("pro", "prosince"),
            ("jan.", "ledna"),
            ("jan", "ledna"),
            ("januari", "ledna"),
        ]
        month_written = pynini.string_map(months_written_map)

        # Months in numeric form (1..12) -> spoken genitive
        months_num_map = [
            ("1", "ledna"),
            ("01", "ledna"),
            ("2", "února"),
            ("02", "února"),
            ("3", "března"),
            ("03", "března"),
            ("4", "dubna"),
            ("04", "dubna"),
            ("5", "května"),
            ("05", "května"),
            ("6", "června"),
            ("06", "června"),
            ("7", "července"),
            ("07", "července"),
            ("8", "srpna"),
            ("08", "srpna"),
            ("9", "září"),
            ("09", "září"),
            ("10", "října"),
            ("11", "listopadu"),
            ("12", "prosince"),
        ]
        month_num = pynini.string_map(months_num_map)

        # Year spoken: 4-digit or 2-digit
        # In Czech, years like 2024 -> "dva tisíce dvacet čtyři", 1990 -> "tisíc devět set devadesát", 2000 -> "dva tisíce"
        year_4 = cardinal.cardinal_numbers

        dot = pynutil.delete(".")
        slash = pynutil.delete("/")
        hyphen = pynutil.delete("-")
        sp = pynutil.delete(" ") | pynutil.delete(pynini.accep(" "))
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # 1. Day + dot + space + Month Name:
        # e.g. "1. ledna", "24. prosince", "15. března"
        # with optional year: "1. ledna 2024", "23. led. 2022"
        day_dot = day_gen + dot + opt_sp
        date_written_no_year = (day_dot + pynutil.insert(" ") + month_written).optimize()
        date_written_with_year = (
            date_written_no_year + pynutil.delete(pynini.closure(",", 0, 1)) + opt_sp + pynutil.insert(" ") + year_4
        ).optimize()
        date_written = (date_written_with_year | date_written_no_year).optimize()

        # 2. Numeric date: "07.03.2026", "7. 3. 2026", "1.1.2024", "1. 1. 2024", "25/12/2024"
        num_date_with_year_dot = (
            day_gen + dot + opt_sp + pynutil.insert(" ") + month_num + dot + opt_sp + pynutil.insert(" ") + year_4
        ).optimize()
        num_date_with_year_slash = (
            day_gen + slash + pynutil.insert(" ") + month_num + slash + pynutil.insert(" ") + year_4
        ).optimize()
        num_date_no_year = (
            day_gen + dot + opt_sp + pynutil.insert(" ") + month_num + opt_sp + dot
        ).optimize()

        self.iso_fst = (
            pynutil.insert('date { year: "')
            + year_4
            + pynutil.insert('" month: "')
            + pynutil.delete(pynini.union("-", "."))
            + (NEMO_DIGIT ** 2 @ month_num)
            + pynutil.insert('" day: "')
            + pynutil.delete(pynini.union("-", "."))
            + (NEMO_DIGIT ** 2 @ day_gen)
            + pynutil.insert('" }')
        ).optimize()

        # Eras:
        # "500 př. n. l." -> "pět set před naším letopočtem"
        # "500 př. Kr." -> "pět set před Kristem"
        # "100 n. l." -> "sto našeho letopočtu"
        # "500 BC" -> "pět set před naším letopočtem"
        # "100 AD" -> "sto našeho letopočtu"
        era_bc = pynini.string_map([
            ("př. n. l.", "před naším letopočtem"),
            ("př. n. l", "před naším letopočtem"),
            ("př. Kr.", "před Kristem"),
            ("př. Kr", "před Kristem"),
            ("BC", "před naším letopočtem"),
            ("B.C.", "před naším letopočtem"),
            ("BCE", "před naším letopočtem"),
            ("B.C.E.", "před naším letopočtem"),
            ("f.Kr.", "před Kristem"),
            ("f Kr", "před Kristem"),
        ])
        era_ad = pynini.string_map([
            ("n. l.", "našeho letopočtu"),
            ("n. l", "našeho letopočtu"),
            ("po Kr.", "po Kristu"),
            ("po Kr", "po Kristu"),
            ("AD", "našeho letopočtu"),
            ("A.D.", "našeho letopočtu"),
            ("CE", "našeho letopočtu"),
            ("C.E.", "našeho letopočtu"),
        ])
        era_all = era_bc | era_ad

        year_with_era = (
            cardinal.cardinal_numbers + opt_sp + pynutil.insert(" ") + era_all
        ).optimize()

        date_written_with_era = (
            date_written_with_year + opt_sp + pynutil.insert(" ") + era_all
        ).optimize()

        # Year ranges: "1990–1995", "1990-1995", "2020-2024"
        # "tisíc devět set devadesát až tisíc devět set devadesát pět"
        dash = pynini.cross("-", " až ") | pynini.cross("–", " až ") | pynini.cross("—", " až ")
        year_range = (
            year_4 + opt_sp + dash + opt_sp + year_4
        ).optimize()

        self.fst = (
            date_written_with_era
            | date_written
            | num_date_with_year_dot
            | num_date_with_year_slash
            | num_date_no_year
            | year_with_era
            | year_range
        ).optimize()
