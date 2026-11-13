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

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, NEMO_SIGMA, GraphFst
from nemo_text_processing.text_normalization.ru.taggers.number_names import LETTERS, ordinal_resolver
from nemo_text_processing.text_normalization.ru.utils import get_abs_path, load_labels

# "год" after a year, as written -> the ordinal form of the year and the spoken word
_YEAR_WORDS = {
    "год": ("masc_nom", "год"),
    "года": ("masc_gen", "года"),
    "году": ("masc_prep", "году"),
    "годом": ("masc_ins", "годом"),
    "г.": ("masc_gen", "года"),
    "г": ("masc_gen", "года"),
}

_ERA_MAP = [
    ("до н.э.", "до нашей эры"),
    ("до н. э.", "до нашей эры"),
    ("н.э.", "нашей эры"),
    ("н. э.", "нашей эры"),
    ("BC", "до нашей эры"),
    ("B.C.", "до нашей эры"),
    ("BCE", "до нашей эры"),
    ("B.C.E.", "до нашей эры"),
    ("AD", "нашей эры"),
    ("A.D.", "нашей эры"),
    ("CE", "нашей эры"),
    ("C.E.", "нашей эры"),
]


class DateFst(GraphFst):
    """
    Finite state transducer for classifying date, e.g.
        "06.03.2006" -> tokens { date { day: "шестое марта две тысячи шестого" } }
        "6/3/1006г." -> "шестое марта тысяча шестого года", "2024-12-25" -> "двадцать пятое декабря две тысячи двадцать
        четвертого", "25 декабря 2024" -> "двадцать пятое декабря две тысячи двадцать четвертого", "01.05" -> "первое мая",
        "в 1999 году" -> "в тысяча девятьсот девяносто девятом году",
        "500 до н.э." -> "пятьсот до нашей эры", "500 г. до н.э." -> "пятисотого года до нашей эры"
    """

    def __init__(self, number_names: dict, deterministic: bool):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        ordinal = number_names['ordinal']
        stem = number_names['ordinal_stem']
        cardinal_masc = number_names['cardinal']['masc']
        not_zero = pynini.difference(NEMO_DIGIT, "0")

        day_digits = pynini.closure("0", 0, 1) + not_zero | pynini.union("1", "2") + NEMO_DIGIT | "30" | "31"
        day = pynini.compose(day_digits, ordinal['neut_nom']).optimize()

        genitive = {}
        for abbr, name, weight in load_labels(get_abs_path("data/months/abbr_to_name.tsv")):
            if float(weight) < 0:
                genitive[abbr] = name
        month_number = pynini.string_map(
            [(number, genitive[abbr]) for number, abbr in load_labels(get_abs_path("data/months/numbers.tsv"))]
        )
        month_word = pynini.string_map(
            [(abbr, name) for abbr, name in genitive.items()]
            + [(abbr + ".", name) for abbr, name in genitive.items()]
            + [(name, name) for name in genitive.values()]
        )

        # "2006" -> "две тысячи шестого"; "86" -> "восемьдесят шестого"; "06" -> "ноль шестого". The year is read as
        # an ordinal stem; the year word after it (or none) picks the ending.
        year_digits = (not_zero + NEMO_DIGIT**3) | (NEMO_DIGIT**2)
        year_stem = (
            pynini.compose(year_digits, stem) | pynini.cross("0", "ноль ") + pynini.compose(not_zero, stem)
        ).optimize()
        tags = {"": "masc_gen"}
        word_tags = []
        for i, (written, (form, spoken)) in enumerate(_YEAR_WORDS.items()):
            tag = chr(0xE051 + i)
            tags[tag] = form
            word_tags.append(pynini.cross(written, tag + " " + spoken))
        word_tag = pynini.union(*word_tags)
        resolve = ordinal_resolver(tags, pynini.closure(pynini.accep(" ") + pynini.closure(LETTERS, 1), 0, 1))
        year_word = pynini.compose(
            year_stem + pynini.closure(pynutil.delete(" "), 0, 1) + word_tag, resolve
        ).optimize()
        year = (year_word | pynini.compose(year_stem, ordinal_resolver({"": "masc_gen"}))).optimize()

        # Historical eras: "500 до н.э." -> "пятьсот до нашей эры", "500 г. до н.э." -> "пятисотого года до нашей эры"
        era_suffix = pynini.string_map(_ERA_MAP).optimize()
        era_digits = not_zero + pynini.closure(NEMO_DIGIT, 0, 3)
        era_bare = pynini.compose(era_digits, cardinal_masc) + pynini.accep(" ") + era_suffix
        era_with_year_word = (
            pynini.compose(era_digits + pynini.closure(NEMO_SIGMA), pynini.compose(pynini.compose(era_digits, stem) + pynini.closure(pynutil.delete(" "), 0, 1) + word_tag, resolve))
            + pynini.accep(" ")
            + era_suffix
        )
        era_graph = (era_bare | era_with_year_word).optimize()

        # Each part is its own field ("day", "month", "year"), so the big number graphs are not concatenated; the
        # verbalizer joins them in day month year order.
        def field(name, graph):
            return pynutil.insert(f"{name}: \"") + graph + pynutil.insert("\" ")

        day_f, month_f, month_word_f, year_f = (
            field("day", day),
            field("month", month_number),
            field("month", month_word),
            field("year", year),
        )
        order = pynutil.insert("preserve_order: true")
        numeric = None
        for sep in (".", "/", "-"):
            delete_sep = pynutil.delete(sep)
            dmy = day_f + delete_sep + month_f + delete_sep + year_f
            numeric = dmy if numeric is None else numeric | dmy
        two_digit_month = field("month", pynini.compose(pynini.union("0", "1") + NEMO_DIGIT, month_number))
        numeric |= field("day", pynini.compose(pynini.union("0", "1", "2") + NEMO_DIGIT | "30" | "31", day)) + pynutil.delete(".") + two_digit_month
        numeric |= day_f + pynutil.delete("-") + month_word_f + pynutil.delete("-") + year_f
        # ISO "2024-12-25" -> "двадцать пятое декабря две тысячи двадцать четвертого"
        iso_year = pynini.compose(not_zero + NEMO_DIGIT**3, year)
        two_digit_day = pynini.compose(pynini.union("0", "1", "2") + NEMO_DIGIT | "30" | "31", day)
        iso = (
            field("year", iso_year)
            + pynutil.delete("-")
            + field("month", pynini.compose(pynini.union("0", "1") + NEMO_DIGIT, month_number))
            + pynutil.delete("-")
            + field("day", two_digit_day)
        )
        # "25 декабря 2024", "25 декабря 2024 г.", "25 декабря"
        spelled = day_f + pynutil.delete(" ") + month_word_f + pynini.closure(pynutil.delete(" ") + year_f, 0, 1)
        # "в 1999 году", "1006 г.", "500 до н.э."
        year_only = field("year", pynini.compose(not_zero + NEMO_DIGIT**3 + pynini.closure(NEMO_SIGMA), year_word) | era_graph)

        graph = (numeric | spelled | year_only) + order | pynutil.add_weight(iso, -0.01)
        self.fst = self.add_tokens(graph).optimize()
