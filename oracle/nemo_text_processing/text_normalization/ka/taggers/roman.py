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
from nemo_text_processing.text_normalization.ka.graph_utils import with_suffix


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


_PRE_KEYWORDS = [
    "თავი", "თავის", "თავში",
    "ნაწილი", "ნაწილის", "ნაწილში",
    "ტომი", "ტომის", "ტომში",
    "წიგნი", "წიგნის", "წიგნში",
    "მუხლი", "მუხლის", "მუხლში",
    "კლასი", "კლასის", "კლასში",
    "აქტი", "აქტის", "აქტში",
    "სურათი", "სურათის",
    "პარაგრაფი",
    "კარი",
    "ეტაპი",
    "დონე",
    "Chapter", "chapter",
    "Section", "section",
    "Book", "book",
    "Volume", "volume",
    "Part", "part",
    "Act", "act",
    "Scene", "scene",
    "Class", "class",
]

_POST_KEYWORDS = [
    "საუკუნე",
    "საუკუნის",
    "საუკუნეს",
    "საუკუნეში",
    "საუკუნით",
    "საუკუნეები",
    "საუკუნეების",
    "საუკუნეებს",
    "საუკუნეებში",
    "ათასწლეული",
    "ათასწლეულის",
    "ათასწლეულში",
    "კლასი",
    "კლასის",
    "კლასში",
    "ტომი",
    "ტომის",
    "ნაწილი",
    "ნაწილის",
    "თავი",
    "თავის",
]

_POST_ABBREV = [
    ("ს.", "საუკუნე"),
    ("სს.", "საუკუნეები"),
]

_MONARCH_NAMES = [
    "დავით",
    "დავითის",
    "გიორგი",
    "გიორგის",
    "ერეკლე",
    "ერეკლეს",
    "ვახტანგ",
    "ვახტანგის",
    "თამარ",
    "თამარის",
    "ბაგრატ",
    "ბაგრატის",
    "დემეტრე",
    "დემეტრეს",
    "ლაშა",
    "რუსუდან",
    "ალექსანდრე",
    "ალექსანდრეს",
    "სოლომონ",
    "სოლომონის",
    "როსტომ",
    "როსტომის",
    "თეიმურაზ",
    "თეიმურაზის",
    "არჩილ",
    "არჩილის",
    "ლევან",
    "ლევანის",
    "კონსტანტინე",
    "კონსტანტინეს",
    "სიმონ",
    "სიმონის",
    "ლუარსაბ",
    "ლუარსაბის",
    "მირიან",
    "ფარნავაზ",
    "ნიკოლოზ",
    "ნიკოლოზის",
    "პეტრე",
    "პეტრეს",
    "ნაპოლეონ",
    "ნაპოლეონის",
    "ლუი",
    "ლუის",
    "ჰენრი",
    "ჰენრის",
    "ჩარლზ",
    "ჩარლზის",
    "კარლ",
    "კარლის",
    "ფილიპ",
    "ფილიპის",
    "ფრიდრიხ",
    "ვილჰელმ",
    "ედუარდ",
    "ედუარდის",
    "ელიზაბეტ",
    "ელიზაბეტის",
    "ეკატერინე",
    "ეკატერინეს",
    "Louis",
    "Elizabeth",
    "Charles",
    "Henry",
    "George",
    "Edward",
    "Philip",
    "Wilhelm",
    "Karl",
    "Alexander",
    "Peter",
    "Nicholas",
]


class RomanFst(GraphFst):
    """
    Keyed Roman numerals for Georgian:
        "თავი IV" -> "თავი ოთხი"
        "Chapter IV" -> "Chapter ოთხი"
        "XXI საუკუნე" -> "ოცდამეერთე საუკუნე"
        "დავით IV" -> "დავით მეოთხე"
        "Louis XIV" -> "Louis მეთოთხმეტე"
    Safety controls: isolated "XL", "MIX", "CD" remain unchanged.
    """

    def __init__(self, cardinal: GraphFst, ordinal: GraphFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_pairs_100 = [(_int_to_roman(n), str(n)) for n in range(1, 101)]
        roman_pairs_post_kw = [
            (_int_to_roman(n), str(n)) for n in range(1, 101) if _int_to_roman(n) not in ("C", "D", "L", "M")
        ]
        roman_card = (pynini.string_map(roman_pairs_post_kw) @ cardinal.all_nums_no_tokens).optimize()

        def to_ord_input(n: int) -> str:
            return str(n)

        roman_ord_pairs_100 = [(_int_to_roman(n), to_ord_input(n)) for n in range(1, 101)]
        roman_ord_100 = (pynini.string_map(roman_ord_pairs_100) @ ordinal.graph).optimize()

        roman_ord_pairs_30 = [(_int_to_roman(n), to_ord_input(n)) for n in range(1, 31)]
        roman_ord_30 = (pynini.string_map(roman_ord_pairs_30) @ ordinal.graph).optimize()
        roman_ord_30_suffixed = (roman_ord_30 | with_suffix(roman_ord_30)).optimize()

        opt_dot = pynini.closure(pynutil.delete("."), 0, 1)
        opt_ord_mark = pynini.closure(pynutil.delete(pynini.union("-ე", "–ე", "—ე", "-ელი", "-ლი")), 0, 1)

        pre_kw_all = set(_PRE_KEYWORDS) | {w.capitalize() for w in _PRE_KEYWORDS}
        pre_kw_fst = pynini.union(*sorted(pre_kw_all)).optimize()
        section_sym = pynini.cross("§", "პარაგრაფი")

        post_kw_all = set(_POST_KEYWORDS) | {w.capitalize() for w in _POST_KEYWORDS}
        post_kw_fst = pynini.union(*sorted(post_kw_all)) | pynini.string_map(_POST_ABBREV)
        post_kw_fst = post_kw_fst.optimize()

        monarch_fst = pynini.union(*sorted(set(_MONARCH_NAMES))).optimize()

        # 1. Keyword + Roman numeral: "თავი IV" -> "თავი ოთხი", "Chapter IV" -> "Chapter ოთხი"
        kw_then_roman = (pre_kw_fst | section_sym) + pynini.accep(" ") + (
            (roman_card + opt_dot) | pynutil.add_weight(roman_ord_100 + opt_ord_mark, 0.05)
        )

        # 2. Roman numeral + postposed keyword: "XXI საუკუნე" -> "ოცდამეერთე საუკუნე", "XXI ს." -> "ოცდამეერთე საუკუნე"
        roman_then_kw = roman_ord_100 + opt_ord_mark + opt_dot + pynini.accep(" ") + post_kw_fst

        # 3. Monarch + Roman numeral: "დავით IV" -> "დავით მეოთხე", "დავით IV-ის" -> "დავით მეოთხის"
        monarch_then_roman = monarch_fst + pynini.accep(" ") + (roman_ord_30_suffixed + opt_ord_mark + opt_dot)

        graph = (kw_then_roman | roman_then_kw | monarch_then_roman).optimize()
        self.graph = convert_space(graph).optimize()
        self.fst = (pynutil.insert('name: "') + self.graph + pynutil.insert('"')).optimize()
