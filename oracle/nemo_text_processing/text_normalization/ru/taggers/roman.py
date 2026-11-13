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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst, convert_space

_ROMAN_VALS = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def _int_to_roman(n: int) -> str:
    out = []
    for val, sym in _ROMAN_VALS:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


# Structural keywords BEFORE a Roman numeral -> ordinal form
_STRUCTURAL_BEFORE = [
    ("глава", "fem_nom"),
    ("главы", "fem_gen"),
    ("главе", "fem_gen"),
    ("главу", "fem_acc"),
    ("часть", "fem_nom"),
    ("части", "fem_gen"),
    ("книга", "fem_nom"),
    ("книги", "fem_gen"),
    ("статья", "fem_nom"),
    ("статьи", "fem_gen"),
    ("сцена", "fem_nom"),
    ("сцены", "fem_gen"),
    ("ступени", "fem_gen"),
    ("ступень", "fem_nom"),
    ("том", "masc_nom"),
    ("тома", "masc_gen"),
    ("тому", "masc_dat"),
    ("томе", "masc_prep"),
    ("раздел", "masc_nom"),
    ("раздела", "masc_gen"),
    ("разделе", "masc_prep"),
    ("параграф", "masc_nom"),
    ("параграфа", "masc_gen"),
    ("пункт", "masc_nom"),
    ("пункта", "masc_gen"),
    ("акт", "masc_nom"),
    ("акта", "masc_gen"),
    ("выпуск", "masc_nom"),
    ("выпуска", "masc_gen"),
    ("этап", "masc_nom"),
    ("этапа", "masc_gen"),
    ("уровень", "masc_nom"),
    ("уровня", "masc_gen"),
    ("тип", "masc_nom"),
    ("типа", "masc_gen"),
    ("класс", "masc_nom"),
    ("класса", "masc_gen"),
    ("действие", "neut_nom"),
    ("приложение", "neut_nom"),
]

# Nouns AFTER a Roman numeral -> ordinal form ("XXI век", "в XXI веке", "XX века", "II тысячелетие", "I квартал")
_NOUNS_AFTER = [
    ("век", "masc_nom", "век"),
    ("века", "masc_gen", "века"),
    ("веку", "masc_dat", "веку"),
    ("веке", "masc_prep", "веке"),
    ("веком", "masc_ins", "веком"),
    ("веков", "pl_gen", "веков"),
    ("векам", "pl_nom", "векам"),
    ("веках", "pl_gen", "веках"),
    ("в.", "masc_gen", "века"),
    ("вв.", "pl_gen", "веков"),
    ("столетие", "neut_nom", "столетие"),
    ("столетия", "masc_gen", "столетия"),
    ("столетии", "masc_prep", "столетии"),
    ("тысячелетие", "neut_nom", "тысячелетие"),
    ("тысячелетия", "masc_gen", "тысячелетия"),
    ("тысячелетии", "masc_prep", "тысячелетии"),
    ("съезд", "masc_nom", "съезд"),
    ("съезда", "masc_gen", "съезда"),
    ("созыв", "masc_nom", "созыв"),
    ("созыва", "masc_gen", "созыва"),
    ("квартал", "masc_nom", "квартал"),
    ("квартала", "masc_gen", "квартала"),
    ("квартале", "masc_prep", "квартале"),
    ("степени", "fem_gen", "степени"),
    ("степень", "fem_nom", "степень"),
    ("мировая", "fem_nom", "мировая"),
    ("мировой", "fem_gen", "мировой"),
]

_MASC_MONARCHS = [
    "Пётр",
    "Петр",
    "Александр",
    "Николай",
    "Павел",
    "Иван",
    "Иоанн",
    "Фёдор",
    "Федор",
    "Алексей",
    "Василий",
    "Дмитрий",
    "Лжедмитрий",
    "Людовик",
    "Карл",
    "Генрих",
    "Георг",
    "Эдуард",
    "Филипп",
    "Фридрих",
    "Вильгельм",
    "Франц",
    "Франциск",
    "Фердинанд",
    "Альфонсо",
    "Яков",
    "Ричард",
    "Наполеон",
    "Густав",
    "Харальд",
    "Олаф",
    "Кристиан",
    "Леопольд",
    "Альберт",
    "Константин",
    "Иоанн Павел",
    "Бенедикт",
    "Пий",
    "Лев",
    "Григорий",
    "Климент",
    "Иннокентий",
    "Урбан",
    "Сикст",
    "Бонифаций",
    "Рамсес",
    "Рамзес",
    "Птолемей",
    "Дарий",
    "Ксеркс",
    "Соломон",
    "Тигран",
    "Вахтанг",
    "Ираклий",
]

_FEM_MONARCHS = [
    "Екатерина",
    "Елизавета",
    "Анна",
    "Мария",
    "Маргарита",
    "Виктория",
    "Изабелла",
    "Кристина",
    "Жанна",
    "Софья",
]


class RomanFst(GraphFst):
    """
    Keyed-only Russian Roman numeral tagger:
      - Structural keywords before numeral: "Глава IV" -> "Глава четвертая", "Том II" -> "Том второй"
      - Century / structural nouns after numeral: "XXI век" -> "двадцать первый век", "в XX веке" -> "в двадцатом веке"
      - Monarchs & popes: "Пётр I" -> "Пётр первый", "Екатерина II" -> "Екатерина вторая", "Людовик XIV" -> "Людовик четырнадцатый"
    Bare uppercase tokens ("XL", "MIX", "CD") are untouched so they spell as letters.
    """

    def __init__(self, number_names: dict, deterministic: bool = False):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        ordinal = number_names["ordinal"]

        def _ord_map(max_n: int, form: str, exclude_cdlm: bool = False) -> pynini.Fst:
            pairs = []
            for n in range(1, max_n + 1):
                rom = _int_to_roman(n)
                if exclude_cdlm and rom in {"C", "D", "L", "M"}:
                    continue
                spoken = pynini.shortestpath(str(n) @ ordinal[form]).string()
                pairs.append((rom, spoken))
            return pynini.string_map(pairs).optimize()

        # Cache ordinal maps by (max_n, form, exclude_cdlm)
        cache = {}

        def get_ord(max_n: int, form: str, exclude_cdlm: bool = False) -> pynini.Fst:
            key = (max_n, form, exclude_cdlm)
            if key not in cache:
                cache[key] = _ord_map(max_n, form, exclude_cdlm)
            return cache[key]

        # 1. Structural keywords BEFORE Roman numeral (1..100, excluding lone C, D, L, M)
        before_parts = []
        by_form = {}
        for kw, form in _STRUCTURAL_BEFORE:
            variants = {kw, kw[0].upper() + kw[1:], kw.upper()}
            by_form.setdefault(form, set()).update(variants)
        for form, kws in by_form.items():
            kw_fst = pynini.union(*sorted(kws)).optimize()
            before_parts.append(kw_fst + pynini.accep(" ") + get_ord(100, form, exclude_cdlm=True))
        keyed_before = pynini.union(*before_parts).optimize()

        # Also support "§ IV" -> "параграф четвертый"
        keyed_section = pynini.cross("§", "параграф") + (pynini.accep(" ") | pynutil.insert(" ")) + get_ord(
            100, "masc_nom", exclude_cdlm=True
        )

        # 2. Nouns AFTER Roman numeral (1..50): "XXI век" -> "двадцать первый век", "XIX–XX вв." -> ...
        after_parts = []
        for written, form, spoken_noun in _NOUNS_AFTER:
            variants = [(written, spoken_noun)]
            if written[0].isalpha():
                cap_w = written[0].upper() + written[1:]
                cap_s = spoken_noun[0].upper() + spoken_noun[1:]
                variants.append((cap_w, cap_s))
                variants.append((written.upper(), spoken_noun.upper()))
            noun_fst = pynini.string_map(variants).optimize()
            after_parts.append(get_ord(50, form, exclude_cdlm=False) + pynini.accep(" ") + noun_fst)
        keyed_after = pynini.union(*after_parts).optimize()

        # Century ranges: "XIX-XX вв." / "XX–XXI века" -> "девятнадцатого двадцатого веков"
        range_sep = pynini.cross(pynini.union("-", "–"), " ")
        century_range_nouns = pynini.string_map(
            [("вв.", "веков"), ("веков", "веков"), ("века", "века"), ("веках", "веках")]
        ).optimize()
        ord_gen_30 = get_ord(30, "masc_gen", exclude_cdlm=False)
        keyed_century_range = ord_gen_30 + range_sep + ord_gen_30 + pynini.accep(" ") + century_range_nouns

        # 3. Monarchs & popes (1..39): nominative + common oblique endings on Russian first names
        masc_names = pynini.union(*(set(_MASC_MONARCHS) | {m.upper() for m in _MASC_MONARCHS})).optimize()
        fem_names = pynini.union(*(set(_FEM_MONARCHS) | {f.upper() for f in _FEM_MONARCHS})).optimize()
        keyed_monarch = (masc_names + pynini.accep(" ") + get_ord(39, "masc_nom", exclude_cdlm=False)) | (
            fem_names + pynini.accep(" ") + get_ord(39, "fem_nom", exclude_cdlm=False)
        )

        graph = (keyed_before | keyed_section | keyed_after | keyed_century_range | keyed_monarch).optimize()
        self.graph = convert_space(graph).optimize()
        self.fst = (pynutil.insert('name: "') + self.graph + pynutil.insert('"')).optimize()
