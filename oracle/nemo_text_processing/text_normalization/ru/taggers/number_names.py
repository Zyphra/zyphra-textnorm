# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
# Copyright 2017 Google Inc.
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

# Russian number names.
#
# Upstream composed a universal factorization transducer with a lexicon that emitted every case and gender of every
# word, so the shortest path mixed forms ("тысяч" for 1000, "две триста" for 2 300, "одно доллар"). The names are
# built here from the digits instead, three digits at a time, with one reading per number: the gender of the last
# word is chosen by the caller, "тысяча / тысячи / тысяч" (and миллион, миллиард) agree with their multiplier
# (CLDR release-49 rbnf ru %spellout-cardinal-*), and ordinals inflect only their last word ("две тысячи шестой",
# "двухтысячный").

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT
from nemo_text_processing.text_normalization.ru.utils import get_abs_path, load_labels

GENDERS = ("masc", "fem", "neut")
CATEGORIES = ("one", "few", "many")

# Ordinal forms and their endings for the three stem classes: hard with stressed "-ой" in the masculine nominative
# (второй), hard (первый) and soft (третий).
ORDINAL_FORMS = (
    "masc_nom",
    "fem_nom",
    "neut_nom",
    "pl_nom",
    "masc_gen",
    "fem_gen",
    "masc_dat",
    "masc_ins",
    "masc_prep",
    "pl_gen",
    "pl_ins",
    "fem_acc",
)
_HARD = ("ый", "ая", "ое", "ые", "ого", "ой", "ому", "ым", "ом", "ых", "ыми", "ую")
_SOFT = ("ий", "ья", "ье", "ьи", "ьего", "ьей", "ьему", "ьим", "ьем", "ьих", "ьими", "ью")
# stem class markers (private use characters) left after the stem by ordinal_stem
_STRESSED, _HARD_CLASS, _SOFT_CLASS = "\ue021", "\ue022", "\ue023"
ORDINAL_CLASSES = (_STRESSED, _HARD_CLASS, _SOFT_CLASS)


def ordinal_ending(cls: str, form: str) -> str:
    i = ORDINAL_FORMS.index(form)
    if cls == _SOFT_CLASS:
        return _SOFT[i]
    if cls == _STRESSED and form == "masc_nom":
        return "ой"
    return _HARD[i]


# per power of 1000: nominative one / few / many, genitive one / other, gender of the multiplier, ordinal stem
_MAGNITUDES = {
    1: (("тысяча", "тысячи", "тысяч"), ("тысячи", "тысяч"), "fem", "тысячн"),
    2: (("миллион", "миллиона", "миллионов"), ("миллиона", "миллионов"), "masc", "миллионн"),
    3: (("миллиард", "миллиарда", "миллиардов"), ("миллиарда", "миллиардов"), "masc", "миллиардн"),
}
# Written quantity words after a number ("5 млн", "2,5 тыс", "3 миллиона"): level, then the word as typed.
QUANTITY_WORDS = {
    1: ("тыс", "тыс.", "тысяча", "тысячи", "тысяч"),
    2: ("млн", "млн.", "миллион", "миллиона", "миллионов"),
    3: ("млрд", "млрд.", "миллиард", "миллиарда", "миллиардов"),
}


def magnitude(level: int) -> dict:
    """Forms of a magnitude word: {"one", "few", "many", "gen" (genitive singular, after a decimal), "gender"}."""
    nominative, genitive, gender, _ = _MAGNITUDES[level]
    return dict(zip(CATEGORIES, nominative), gen=genitive[0], gender=gender)


_ONE = {"nom": {"masc": "один", "fem": "одна", "neut": "одно"}, "gen": {"masc": "одного", "fem": "одной", "neut": "одного"}}
_TWO = {"masc": "два", "fem": "две", "neut": "два"}

LETTERS = pynini.union(*"абвгдеёжзийклмнопрстуфхцчшщъыьэюя").optimize()
WORDS_SIGMA = pynini.closure(LETTERS | " ").optimize()
_STRIP_SPACE = (pynutil.delete(" ") + WORDS_SIGMA).optimize()
_PAD = pynini.union(*[pynutil.insert("0" * (12 - k)) + NEMO_DIGIT**k for k in range(1, 13)]).optimize()
_ZEROS = pynini.closure("0", 1).optimize()


def plural_category(value: int) -> str:
    """Russian count category of a whole number: "one" (21), "few" (22-24) or "many" (25, 11-14, 0)."""
    if 11 <= value % 100 <= 14:
        return "many"
    if value % 10 == 1:
        return "one"
    if 2 <= value % 10 <= 4:
        return "few"
    return "many"


def _ending_condition():
    """Digit strings (with optional space / dot / no-break-space thousands separators) by their count category."""
    any_number = pynini.closure(NEMO_DIGIT | " " | "." | "\u00a0")
    not_one = pynini.difference(NEMO_DIGIT, "1")
    one = (any_number + not_one + "1") | "1"
    few_digit = pynini.union("2", "3", "4")
    few = (any_number + not_one + few_digit) | few_digit
    many = pynini.difference(any_number + NEMO_DIGIT, one | few)
    return {"one": one.optimize(), "few": few.optimize(), "many": many.optimize()}


ENDS_IN = _ending_condition()


def _components(value: int):
    """1..999 -> the values of its number words: 245 -> [200, 40, 5], 213 -> [200, 13]."""
    out = []
    if value >= 100:
        out.append(value // 100 * 100)
    rest = value % 100
    if 10 <= rest <= 19:
        out.append(rest)
    else:
        if rest >= 20:
            out.append(rest // 10 * 10)
        if rest % 10:
            out.append(rest % 10)
    return out


class _Lexicon:
    def __init__(self):
        self.nom = {int(k): v for k, v in load_labels(get_abs_path("data/numbers/cardinals_nominative_case.tsv"))}
        self.gen = {}
        for k, v in load_labels(get_abs_path("data/numbers/2_cardinals_genitive.tsv")):
            self.gen.setdefault(int(k), v)
        words = {}
        for row in load_labels(get_abs_path("data/numbers/ordinals.tsv")):
            words.setdefault(int(row[0]), set()).add(row[1])
        # value -> (stem, class): 2 -> ("втор", stressed), 1 -> ("перв", hard), 3 -> ("трет", soft)
        self.ordinal = {}
        for value, forms in words.items():
            fem = next(w for w in forms if w.endswith("ая") or w.endswith("ья"))
            if fem.endswith("ья"):
                self.ordinal[value] = (fem[:-2], _SOFT_CLASS)
            else:
                stem = fem[:-2]
                self.ordinal[value] = (stem, _HARD_CLASS if stem + "ый" in forms else _STRESSED)

    def word(self, value: int, gender: str, case: str) -> str:
        if value == 1:
            return _ONE[case][gender]
        if value == 2 and case == "nom":
            return _TWO[gender]
        return (self.nom if case == "nom" else self.gen)[value]

    def words_dict(self, gender: str, case: str) -> dict:
        keys = list(range(1, 20)) + list(range(20, 100, 10)) + list(range(100, 1000, 100))
        return {v: self.word(v, gender, case) for v in keys}


def _group_by_category(lex: _Lexicon, gender: str, case: str) -> dict:
    """Three-digit blocks 001..999 split by Russian count category ("one", "few", "many"), factored by hundreds/tens/units."""
    d = lex.words_dict(gender, case)
    u1 = pynini.cross("1", " " + d[1])
    u_few = pynini.string_map([(str(v), " " + d[v]) for v in (2, 3, 4)])
    u_many = pynini.string_map([(str(v), " " + d[v]) for v in range(5, 10)])
    teens = pynini.string_map([(str(v), " " + d[v]) for v in range(10, 20)])
    tens = pynini.string_map([(str(v // 10), " " + d[v]) for v in range(20, 100, 10)])
    hunds = pynini.string_map([(str(v // 100), " " + d[v]) for v in range(100, 1000, 100)])

    two_one = (pynutil.delete("0") | tens) + u1
    two_few = (pynutil.delete("0") | tens) + u_few
    two_many = teens | tens + pynutil.delete("0") | (pynutil.delete("0") | tens) + u_many

    one = (pynutil.delete("0") | hunds) + two_one
    few = (pynutil.delete("0") | hunds) + two_few
    many = hunds + pynutil.delete("00") | (pynutil.delete("0") | hunds) + two_many
    return {"one": one.optimize(), "few": few.optimize(), "many": many.optimize()}


def _magnitude_map(lex: _Lexicon, level: int, case: str, with_one: bool) -> pynini.Fst:
    nominative, genitive, gender, _ = _MAGNITUDES[level]
    cats = _group_by_category(lex, gender, case)
    forms = (
        dict(zip(CATEGORIES, nominative))
        if case == "nom"
        else {"one": genitive[0], "few": genitive[1], "many": genitive[1]}
    )
    if not with_one:
        one_gt1 = pynini.compose(pynini.difference(pynini.project(cats["one"], "input"), "001"), cats["one"])
        graph = pynini.cross("001", " " + forms["one"]) | (one_gt1 + pynutil.insert(" " + forms["one"]))
    else:
        graph = cats["one"] + pynutil.insert(" " + forms["one"])
    graph |= cats["few"] + pynutil.insert(" " + forms["few"])
    graph |= cats["many"] + pynutil.insert(" " + forms["many"])
    graph |= pynutil.delete("000")
    return graph.optimize()


def _cardinal(lex: _Lexicon, gender: str, case: str) -> pynini.Fst:
    cats = _group_by_category(lex, gender, case)
    units = (cats["one"] | cats["few"] | cats["many"] | pynutil.delete("000")).optimize()
    body = (
        _magnitude_map(lex, 3, case, True)
        + _magnitude_map(lex, 2, case, True)
        + _magnitude_map(lex, 1, case, True)
        + units
    )
    zero = pynini.cross(_ZEROS, "ноль" if case == "nom" else "нуля")
    return (pynini.compose(pynini.compose(_PAD, body), _STRIP_SPACE) | zero).optimize()


def _ordinal_group(lex: _Lexicon) -> pynini.Fst:
    d = lex.words_dict("masc", "nom")
    keys = list(range(1, 20)) + list(range(20, 100, 10)) + list(range(100, 1000, 100))
    o = {v: lex.ordinal[v][0] + lex.ordinal[v][1] for v in keys}
    u_ord = pynini.string_map([(str(v), " " + o[v]) for v in range(1, 10)])
    teens_ord = pynini.string_map([(str(v), " " + o[v]) for v in range(10, 20)])
    tens_ord = pynini.string_map([(str(v // 10), " " + o[v]) for v in range(20, 100, 10)])
    tens_card = pynini.string_map([(str(v // 10), " " + d[v]) for v in range(20, 100, 10)])
    hunds_ord = pynini.string_map([(str(v // 100), " " + o[v]) for v in range(100, 1000, 100)])
    hunds_card = pynini.string_map([(str(v // 100), " " + d[v]) for v in range(100, 1000, 100)])

    two_ord = pynutil.delete("0") + u_ord | teens_ord | tens_ord + pynutil.delete("0") | tens_card + u_ord
    three_ord = pynutil.delete("0") + two_ord | hunds_ord + pynutil.delete("00") | hunds_card + two_ord
    return three_ord.optimize()


def _fused_magnitude(lex: _Lexicon, level: int) -> pynini.Fst:
    """Multiplier glued to an ordinal magnitude: 002 -> " двухтысячн"+H, 001 -> " тысячн"+H."""
    stem = _MAGNITUDES[level][3] + _HARD_CLASS
    special = {1: "одно", 90: "девяносто", 100: "сто"}
    keys = list(range(1, 20)) + list(range(20, 100, 10)) + list(range(100, 1000, 100))
    f = {v: special.get(v, lex.gen.get(v)) for v in keys}
    u = pynini.string_map([(str(v), f[v]) for v in range(1, 10)])
    u_gt1 = pynini.string_map([(str(v), f[v]) for v in range(2, 10)])
    teens = pynini.string_map([(str(v), f[v]) for v in range(10, 20)])
    tens = pynini.string_map([(str(v // 10), f[v]) for v in range(20, 100, 10)])
    hunds = pynini.string_map([(str(v // 100), f[v]) for v in range(100, 1000, 100)])

    two_any = pynutil.delete("0") + u | teens | tens + (pynutil.delete("0") | u)
    two_gt1 = pynutil.delete("0") + u_gt1 | teens | tens + (pynutil.delete("0") | u)
    prefix = pynini.cross("001", "") | pynutil.delete("0") + two_gt1 | hunds + (pynutil.delete("00") | two_any)
    return (pynutil.insert(" ") + prefix + pynutil.insert(stem)).optimize()


def _ordinal_stem(lex: _Lexicon) -> pynini.Fst:
    """Digits -> ordinal words whose last word is a stem followed by its class marker: "2006" -> "две тысячи шест"+M."""
    billions, millions, thousands = [_magnitude_map(lex, level, "nom", with_one=False) for level in (3, 2, 1)]
    units = _ordinal_group(lex)
    body = (
        (billions + millions + thousands + units)
        | (billions + millions + _fused_magnitude(lex, 1) + pynutil.delete("000"))
        | (billions + _fused_magnitude(lex, 2) + pynutil.delete("0" * 6))
        | (_fused_magnitude(lex, 3) + pynutil.delete("0" * 9))
    )
    stem, cls = lex.ordinal[0]
    zero = pynini.cross(_ZEROS, stem + cls)
    sigma = pynini.closure(LETTERS | " " | pynini.union(*ORDINAL_CLASSES))
    strip = pynutil.delete(" ") + sigma
    return (pynini.compose(pynini.compose(_PAD, body.optimize()), strip) | zero).optimize()

def ordinal_resolver(form_of_tag: dict, tail: pynini.FstLike = "") -> pynini.Fst:
    """Replaces the class marker after the last ordinal stem (+ an optional form tag) with the ending: form_of_tag maps
    a tag string ("" for none) to the form the ending takes, or to a dict class marker -> form. tail: what may follow
    (accepted unchanged)."""
    pairs = []
    for tag, form in form_of_tag.items():
        for cls in ORDINAL_CLASSES:
            f = form[cls] if isinstance(form, dict) else form
            pairs.append((cls + tag, ordinal_ending(cls, f)))
    return (WORDS_SIGMA + pynini.string_map(pairs) + tail).optimize()


def get_number_names() -> dict:
    """
    Number names, all taking a digit string of up to 12 digits (leading zeros allowed):
        cardinal[gender]      nominative, last word of the given gender: "21" -> "двадцать одна" (fem)
        cardinal_gen[gender]  genitive: "25" -> "двадцати пяти"
        ordinal_stem          ordinal words ending in a stem + class marker, see ordinal_resolver
        ordinal[form]         one of ORDINAL_FORMS: "2006" -> "две тысячи шестой" (masc_nom)
    """
    lex = _Lexicon()
    stem = _ordinal_stem(lex)
    return {
        "cardinal": {g: _cardinal(lex, g, "nom") for g in GENDERS},
        "cardinal_gen": {g: _cardinal(lex, g, "gen") for g in GENDERS},
        "ordinal_stem": stem,
        "ordinal": {form: (stem @ ordinal_resolver({"": form})).optimize() for form in ORDINAL_FORMS},
    }


def get_alternative_formats():
    """
    Digit strings with thousands separators ("2 300", "2.300", "1 000 000") without them.
    """
    # Adapted from
    # https://github.com/google/TextNormalizationCoveringGrammars/blob/master/src/universal/thousands_punct.grm
    # Specifies common ways of delimiting thousands in digit strings.
    t = pynini.Far(get_abs_path('data/utils/universal_thousands_punct.far'))
    separators = pynutil.add_weight(t['dot_thousands'], 0.1) | t['space_thousands']
    nbsp_thousands = NEMO_DIGIT**(1, 3) + pynini.closure(pynutil.delete("\u00a0") + NEMO_DIGIT**3, 1)
    return {'separators': (separators | nbsp_thousands).optimize()}
