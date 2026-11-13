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
# Unit names from Unicode CLDR release-49 (Unicode-3.0 license).

"""Counted nouns (units of measure, currencies, quantity words) and their agreement with the number before them.

A counted noun takes the nominative singular after a number ending in 1 (not 11), the genitive singular after one ending
in 2-4 (not 12-14) and the genitive plural otherwise; after a decimal it takes the genitive singular, and after a
quantity word ("5 млн") the genitive plural. A feminine noun turns a final "один" / "два" into "одна" / "две", a neuter
one a final "один" into "одно".

Numbers are spoken once, in the masculine, followed by a marker of the form the next noun takes (marked_numbers); a
small resolver then reads the marker and the written noun and speaks both. Only the resolver depends on the nouns, so
the big number transducer is not copied per noun.
"""

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_NON_BREAKING_SPACE, NEMO_SIGMA
from nemo_text_processing.text_normalization.ru.taggers.number_names import (
    CATEGORIES,
    ENDS_IN,
    LETTERS,
    QUANTITY_WORDS,
    magnitude,
)
from nemo_text_processing.text_normalization.ru.utils import get_abs_path, load_labels

# form of the next noun -> marker (private use characters)
FORMS = ("one", "few", "many", "gen")
MARK = {"one": "\ue031", "few": "\ue032", "many": "\ue033", "gen": "\ue034"}
ANY_MARK = pynini.union(*MARK.values()).optimize()
# number words before a marker: lower-case Cyrillic and spaces
WORDS = pynini.closure(LETTERS | " ").optimize()

# what may stand between a number and its unit: nothing, a space or a no-break space; spoken as one space
UNIT_SPACE = (
    pynini.closure(pynutil.delete(pynini.union(" ", NEMO_NON_BREAKING_SPACE)), 0, 1) + pynutil.insert(" ")
).optimize()

# units of time take "в" in a rate ("километров в час"), every other unit "на" ("килограммов на квадратный метр")
_TIME_UNITS = {"ч", "h", "мин", "min", "сек", "сек.", "s", "sec", "мс", "ms"}
_DENOMINATOR_WORDS = pynini.union(
    "десятая",
    "десятых",
    "сотая",
    "сотых",
    "тысячная",
    "тысячных",
    "десятитысячная",
    "десятитысячных",
    "стотысячная",
    "стотысячных",
    "миллионная",
    "миллионных",
).optimize()


class Noun:
    """One counted noun: its written form, gender and spoken forms."""

    def __init__(self, written, gender, one, few, many, genitive, accusative=None):
        self.written = written
        self.gender = gender
        self.forms = {"one": one, "few": few, "many": many, "gen": genitive, "acc": accusative or one}


def load_units():
    """data/measure/units.tsv: written, gender, one, few, many, genitive singular, accusative singular."""
    return [Noun(*row) for row in load_labels(get_abs_path("data/measure/units.tsv"))]


def load_currencies():
    """(major, minor, written minor) currency nouns from data/currency/: major.tsv and minor_written.tsv carry
    written, gender, one, few, many, genitive singular; minor.tsv (the minor unit of a major currency symbol) has no
    genitive column (a minor unit never follows a decimal)."""
    major = [Noun(*row) for row in load_labels(get_abs_path("data/currency/major.tsv"))]
    minor = [Noun(*row, row[3]) for row in load_labels(get_abs_path("data/currency/minor.tsv"))]
    written_minor = [Noun(*row) for row in load_labels(get_abs_path("data/currency/minor_written.tsv"))]
    return major, minor, written_minor


def quantity_nouns():
    """Quantity words as counted nouns: "тыс" / "тысячи" (feminine), "млн" / "миллиона" (masculine), ..."""
    nouns = []
    for level, written in QUANTITY_WORDS.items():
        forms = magnitude(level)
        for w in written:
            nouns.append(Noun(w, forms["gender"], forms["one"], forms["few"], forms["many"], forms["gen"]))
    return nouns


def form_map(nouns, form: str, suffix: pynini.FstLike = None) -> pynini.Fst:
    """Written noun -> the given spoken form ("one", "few", "many", "gen", "acc"), optionally followed by suffix."""
    graph = pynini.string_map([(n.written, n.forms[form]) for n in nouns]).optimize()
    if suffix is not None:
        graph = (graph + suffix).optimize()
    return graph


def per_unit(nouns) -> pynini.Fst:
    """"/ч" -> " в час", "/м²" -> " на квадратный метр": the rate part of "км/ч", "кг/м²"."""
    pairs = [(n.written, ("в " if n.written in _TIME_UNITS else "на ") + n.forms["acc"]) for n in nouns]
    return (pynini.cross("/", " ") + pynini.string_map(pairs)).optimize()


def marked_numbers(numbers: pynini.Fst) -> pynini.Fst:
    """Digits -> masculine number words + the marker of the noun form the number takes ("5" -> "пять" + many)."""
    graph = None
    for category in CATEGORIES:
        part = pynini.compose(ENDS_IN[category], numbers) + pynutil.insert(MARK[category])
        graph = part if graph is None else graph | part
    return graph.optimize()


def agreement(nouns, space: pynini.FstLike, suffix: pynini.FstLike = None, tail_only: bool = False) -> pynini.Fst:
    """Resolver: number words + marker + space + written noun (+ suffix input) -> number words agreeing in gender + " "
    + the noun form the marker asks for (+ suffix output). With tail_only, the resolver reads only "marker + space + noun"
    and the last number word (for gender), for use after an already spoken prefix."""
    parts = []
    for gender in sorted({n.gender for n in nouns}):
        group = [n for n in nouns if n.gender == gender]
        for form in FORMS:
            tail = space + form_map(group, form, suffix)
            mark = MARK[form]
            if form == "one" and gender in ("fem", "neut"):
                parts.append(pynini.cross("один" + mark, "одна" if gender == "fem" else "одно") + tail)
            elif form == "few" and gender == "fem":
                parts.append(pynini.cross("два" + mark, "две") + tail)
                parts.append(pynini.union("три", "четыре") + pynutil.delete(mark) + tail)
            elif form == "gen" and gender == "fem":
                parts.append(pynini.cross("одного" + mark, "одной") + tail)
                parts.append(_DENOMINATOR_WORDS + pynutil.delete(mark) + tail)
            else:
                parts.append(pynutil.delete(mark) + tail)
    return (WORDS + pynini.union(*parts)).optimize()


def attach(marked: pynini.Fst, resolver: pynini.Fst) -> pynini.Fst:
    """Marked number followed by the written text the resolver reads (a unit, a currency, a quantity word)."""
    return pynini.compose(marked + NEMO_SIGMA, resolver).optimize()


def strip_mark() -> pynini.Fst:
    return (WORDS + pynutil.delete(ANY_MARK)).optimize()
