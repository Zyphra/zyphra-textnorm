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

from nemo_text_processing.text_normalization.ar.graph_utils import GraphFst, convert_space
from nemo_text_processing.text_normalization.ar.utils import get_abs_path, load_labels


def _int_to_roman(n: int) -> str:
    vals = [
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
    out = []
    for val, sym in vals:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def _fem_ordinal(n: int) -> str:
    ones_1_10 = {
        1: "الأولى",
        2: "الثانية",
        3: "الثالثة",
        4: "الرابعة",
        5: "الخامسة",
        6: "السادسة",
        7: "السابعة",
        8: "الثامنة",
        9: "التاسعة",
        10: "العاشرة",
    }
    compound_ones = {
        1: "الحادية",
        2: "الثانية",
        3: "الثالثة",
        4: "الرابعة",
        5: "الخامسة",
        6: "السادسة",
        7: "السابعة",
        8: "الثامنة",
        9: "التاسعة",
    }
    tens = {
        20: "العشرون",
        30: "الثلاثون",
        40: "الأربعون",
        50: "الخمسون",
        60: "الستون",
        70: "السبعون",
        80: "الثمانون",
        90: "التسعون",
    }
    if n <= 10:
        return ones_1_10[n]
    if n < 20:
        return f"{compound_ones[n - 10]} عشرة"
    t, u = (n // 10) * 10, n % 10
    if u == 0:
        return tens[t]
    return f"{compound_ones[u]} و{tens[t]}"


_MASC_DEF_KEYWORDS = [
    "الفصل",
    "القرن",
    "الجزء",
    "المجلد",
    "الباب",
    "القسم",
    "الكتاب",
    "البند",
    "الملحق",
    "المستوى",
    "الصف",
    "الطابق",
    "الدور",
    "الموسم",
    "النوع",
    "النمط",
    "العصر",
    "الأسطول",
    "الجيش",
    "الفيلق",
    "المجمع",
    "المؤتمر",
    "العهد",
    "الجيل",
    # Masculine monarchs, popes, pharaohs, and royal titles
    "لويس",
    "هنري",
    "تشارلز",
    "شارل",
    "فيليب",
    "جورج",
    "إدوارد",
    "ويليام",
    "وليام",
    "فيلهلم",
    "ريتشارد",
    "جيمس",
    "فرانسيس",
    "فرنسيس",
    "بندكت",
    "بنديكت",
    "بندكتس",
    "يوحنا",
    "يوحنا بولس",
    "بولس",
    "بيوس",
    "ليو",
    "لاون",
    "غريغوري",
    "غريغوريوس",
    "رمسيس",
    "تحتمس",
    "أمنحتب",
    "بطليموس",
    "محمد",
    "الحسن",
    "عبد الله",
    "قابوس",
    "فؤاد",
    "فاروق",
    "فيصل",
    "حسين",
    "سليمان",
    "سليم",
    "مراد",
    "بايزيد",
    "عبد الحميد",
    "بطرس",
    "إيفان",
    "نيكولاس",
    "نيقولا",
    "ألكسندر",
    "الإسكندر",
    "نابليون",
    "قسطنطين",
    "كارل",
    "خوان كارلوس",
    "فيليبي",
    "الملك",
    "البابا",
    "السلطان",
    "الإمبراطور",
    "القيصر",
    "الخليفة",
    "الأمير",
]

_FEM_DEF_KEYWORDS = [
    "المادة",
    "الفقرة",
    "المرحلة",
    "الطبعة",
    "الحرب العالمية",
    "الحلقة",
    "المجموعة",
    "الدرجة",
    "الآية",
    "السورة",
    "الفرقة",
    "السيمفونية",
    "السمفونية",
    "الجمهورية",
    # Feminine monarchs and queens
    "إليزابيث",
    "اليزابيث",
    "كاثرين",
    "كاترين",
    "ماري",
    "ماريا",
    "فيكتوريا",
    "مارغريت",
    "مارغريتا",
    "آن",
    "آنا",
    "كليوباترا",
    "الملكة",
]

_INDEF_CARDINAL_KEYWORDS = [
    "فصل",
    "جزء",
    "مجلد",
    "باب",
    "قسم",
    "ملحق",
    "بند",
    "فقرة",
    "مادة",
    "طبعة",
    "رقم",
    "قرن",
]


class RomanFst(GraphFst):
    """
    Finite state transducer for keyed Roman numerals in Modern Standard Arabic, e.g.
        "الفصل IV" -> name: "الفصل الرابع"
        "القرن XXI" -> name: "القرن الحادي والعشرون"
        "لويس XIV" -> name: "لويس الرابع عشر"
        "الحرب العالمية II" -> name: "الحرب العالمية الثانية"
    Bare uppercase tokens ("XL", "MIX", "CD") are deliberately left untouched.
    """

    def __init__(self, cardinal: GraphFst):
        super().__init__(name="roman", kind="classify")

        ord_rows = dict(load_labels(get_abs_path("data/ordinal/ordinals.tsv")))
        roman_masc_ord = pynini.string_map(
            [(_int_to_roman(n), ord_rows[str(n)]) for n in range(1, 1000) if str(n) in ord_rows]
        ).optimize()
        roman_fem_ord = pynini.string_map([(_int_to_roman(n), _fem_ordinal(n)) for n in range(1, 100)]).optimize()
        roman_to_digits = pynini.string_map([(_int_to_roman(n), str(n)) for n in range(1, 1000)]).optimize()
        roman_card = (roman_to_digits @ cardinal.cardinal_numbers).optimize()

        sp = pynini.accep(" ")
        masc_graph = pynini.union(*_MASC_DEF_KEYWORDS) + sp + roman_masc_ord
        fem_graph = pynini.union(*_FEM_DEF_KEYWORDS) + sp + roman_fem_ord
        indef_graph = pynini.union(*_INDEF_CARDINAL_KEYWORDS) + sp + roman_card

        graph = (masc_graph | fem_graph | indef_graph).optimize()
        self.graph = convert_space(graph).optimize()
        self.fst = (pynutil.insert('name: "') + self.graph + pynutil.insert('"')).optimize()
