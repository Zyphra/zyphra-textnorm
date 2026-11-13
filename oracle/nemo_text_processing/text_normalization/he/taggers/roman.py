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
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class RomanFst(GraphFst):
    """
    Finite state transducer for classifying keyed Roman numerals in Hebrew.
    Requires context keywords (פרק, חלק, מאה, לואי, Chapter, Part) to avoid
    falsely interpreting acronyms or words like XL, MIX, CD as numbers.
    e.g. פרק IV -> פרק ארבע
         חלק II -> חלק שתיים
         מאה XXI -> מאה עשרים ואחת
         המאה ה-XXI -> המאה העשרים ואחת
         לואי XIV -> לואי הארבעה עשר
         Chapter IV -> Chapter ארבע
         Part II -> Part שתיים
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="roman", kind="classify", deterministic=deterministic)

        roman_cardinals = pynini.string_map([
            ("I", "אחת"),
            ("II", "שתיים"),
            ("III", "שלוש"),
            ("IV", "ארבע"),
            ("V", "חמש"),
            ("VI", "שש"),
            ("VII", "שבע"),
            ("VIII", "שמונה"),
            ("IX", "תשע"),
            ("X", "עשר"),
            ("XI", "אחת עשרה"),
            ("XII", "שתים עשרה"),
            ("XIII", "שלוש עשרה"),
            ("XIV", "ארבע עשרה"),
            ("XV", "חמש עשרה"),
            ("XVI", "שש עשרה"),
            ("XVII", "שבע עשרה"),
            ("XVIII", "שמונה עשרה"),
            ("XIX", "תשע עשרה"),
            ("XX", "עשרים"),
            ("XXI", "עשרים ואחת"),
        ])

        roman_monarch = pynini.string_map([
            ("I", "הראשון"),
            ("II", "השני"),
            ("III", "השלישי"),
            ("IV", "הרביעי"),
            ("V", "החמישי"),
            ("VI", "השישי"),
            ("VII", "השביעי"),
            ("VIII", "השמיני"),
            ("IX", "התשיעי"),
            ("X", "העשירי"),
            ("XI", "האחד עשר"),
            ("XII", "השנים עשר"),
            ("XIII", "השלושה עשר"),
            ("XIV", "הארבעה עשר"),
            ("XV", "החמישה עשר"),
            ("XVI", "השישה עשר"),
            ("XXI", "העשרים ואחד"),
        ])

        # Keywords for chapters / parts / sections
        chap_keywords = pynini.string_map([
            ("פרק", "פרק"),
            ("חלק", "חלק"),
            ("כרך", "כרך"),
            ("סעיף", "סעיף"),
            ("לוח", "לוח"),
            ("נספח", "נספח"),
            ("שער", "שער"),
            ("Chapter", "Chapter"),
            ("Part", "Part"),
            ("Section", "Section"),
            ("Volume", "Volume"),
            ("Book", "Book"),
        ])

        # Keywords for monarchs / rulers
        monarch_names = pynini.string_map([
            ("לואי", "לואי"),
            ("הנרי", "הנרי"),
            ("שלמה", "שלמה"),
            ("דוד", "דוד"),
            ("ג'ורג'", "ג'ורג'"),
            ("אליזבת", "אליזבת"),
            ("ויליאם", "ויליאם"),
            ("פיליפ", "פיליפ"),
            ("קרל", "קרל"),
            ("ניקולאי", "ניקולאי"),
            ("אלכסנדר", "אלכסנדר"),
            ("נפוליאון", "נפוליאון"),
            ("מלך", "מלך"),
            ("המלך", "המלך"),
            ("האפיפיור", "האפיפיור"),
            ("קיסר", "קיסר"),
            ("הקיסר", "הקיסר"),
            ("Louis", "Louis"),
            ("Henry", "Henry"),
            ("George", "George"),
            ("Elizabeth", "Elizabeth"),
            ("William", "William"),
            ("King", "King"),
            ("Pope", "Pope"),
        ])

        # Centuries (מאה XXI / המאה ה-XXI -> המאה העשרים ואחת)
        roman_century = pynini.string_map([
            ("I", "הראשונה"),
            ("II", "השנייה"),
            ("III", "השלישית"),
            ("IV", "הרביעית"),
            ("V", "החמישית"),
            ("VI", "השישית"),
            ("VII", "השביעית"),
            ("VIII", "השמינית"),
            ("IX", "התשיעית"),
            ("X", "העשירית"),
            ("XI", "האחת עשרה"),
            ("XII", "השתים עשרה"),
            ("XIII", "השלוש עשרה"),
            ("XIV", "הארבע עשרה"),
            ("XV", "החמש עשרה"),
            ("XVI", "השש עשרה"),
            ("XVII", "השבע עשרה"),
            ("XVIII", "השמונה עשרה"),
            ("XIX", "התשע עשרה"),
            ("XX", "העשרים"),
            ("XXI", "העשרים ואחת"),
        ])
        century_lead_def = pynini.string_map([
            ("המאה ה-", "המאה "),
            ("המאה ה־", "המאה "),
            ("המאה", "המאה "),
            ("במאה ה-", "במאה "),
            ("במאה ה־", "במאה "),
            ("במאה", "במאה "),
        ])

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        req_space = pynutil.delete(" ")

        chap_roman = chap_keywords + req_space + pynutil.insert(" ") + roman_cardinals
        monarch_roman = monarch_names + req_space + pynutil.insert(" ") + roman_monarch
        century_roman = (
            (century_lead_def + opt_space + roman_century)
            | (pynini.cross("מאה", "מאה") + req_space + pynutil.insert(" ") + roman_cardinals)
        )

        all_roman = chap_roman | monarch_roman | century_roman
        self.fst = (
            pynutil.insert('name: "') + convert_space(all_roman) + pynutil.insert('"')
        ).optimize()
