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

import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew abbreviations, titles,
    symbols, and contextual abbreviations before numbers.
    e.g. ד"ר כהן -> דוקטור כהן
         פרופ' לוי -> פרופסור לוי
         מס' 5 -> מספר חמש
         No. 5 -> מספר חמש
         #5 -> מספר חמש
         עמ' 5 -> עמוד חמש
         סע' 12 -> סעיף שתים עשרה
         © 2024 -> כל הזכויות שמורות אלפיים עשרים וארבע
         § 12 -> סעיף שתים עשרה
         A & B -> A וגם B
         5% -> חמישה אחוזים
         5‰ -> חמישה פרומיל
         25¢ -> עשרים וחמישה סנט
         5+3 -> חמש ועוד שלוש
         5 = 5 -> חמש שווה חמש
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True, input_file: str = None):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        req_space = pynutil.delete(" ")

        # ----------------- Hebrew Abbreviations -----------------
        abbrev_map = [
            # Titles & Roles
            ('ד"ר', "דוקטור"),
            ('ד״ר', "דוקטור"),
            ('דר.', "דוקטור"),
            ('Dr.', "דוקטור"),
            ('Dr', "דוקטור"),
            ("פרופ'", "פרופסור"),
            ("פרופ׳", "פרופסור"),
            ("פרופ.", "פרופסור"),
            ("Prof.", "פרופסור"),
            ("מר", "מר"),
            ("Mr.", "מר"),
            ("גב'", "גברת"),
            ("גב׳", "גברת"),
            ("גב.", "גברת"),
            ("Mrs.", "גברת"),
            ("Ms.", "גברת"),
            ('עו"ד', "עורך דין"),
            ('עו״ד', "עורך דין"),
            ('יו"ר', "יושב ראש"),
            ('יו״ר', "יושב ראש"),
            ('מנכ"ל', "מנהל כללי"),
            ('מנכ״ל', "מנהל כללי"),
            ('סמנכ"ל', "סגן מנהל כללי"),
            ('סמנכ״ל', "סגן מנהל כללי"),
            ('ח"כ', "חבר כנסת"),
            ('ח״כ', "חבר כנסת"),
            # Common text abbreviations
            ("וכו'", "וכולי"),
            ("וכו׳", "וכולי"),
            ("וכו.", "וכולי"),
            ("etc.", "וכולי"),
            ("וכד'", "וכדומה"),
            ("וכד׳", "וכדומה"),
            ("וכד.", "וכדומה"),
            ("וכיו\"ב", "וכיוצא בזה"),
            ("וכיו״ב", "וכיוצא בזה"),
            ("וגו'", "וגומר"),
            ("וגו׳", "וגומר"),
            ('ע"י', "על ידי"),
            ('ע״י', "על ידי"),
            ('ע"פ', "על פי"),
            ('ע״פ', "על פי"),
            ('בדר"כ', "בדרך כלל"),
            ('בדר״כ', "בדרך כלל"),
            ('אע"פ', "אף על פי"),
            ('אע״פ', "אף על פי"),
            ('בסה"כ', "בסך הכל"),
            ('בסה״כ', "בסך הכל"),
            ('כנ"ל', "כנזכר לעיל"),
            ('כנ״ל', "כנזכר לעיל"),
            ('חו"ל', "חוץ לארץ"),
            ('חו״ל', "חוץ לארץ"),
            ('ארה"ב', "ארצות הברית"),
            ('ארה״ב', "ארצות הברית"),
            ('ת"א', "תל אביב"),
            ('ת״א', "תל אביב"),
            ('צה"ל', "צהל"),
            ('צה״ל', "צהל"),
            ('ביה"ח', "בית החולים"),
            ('ביה״ח', "בית החולים"),
            ('ביה"ס', "בית הספר"),
            ('ביה״ס', "בית הספר"),
            ('מו"מ', "משא ומתן"),
            ('מו״מ', "משא ומתן"),
            ('אחה"צ', "אחר הצהריים"),
            ('אחה״צ', "אחר הצהריים"),
            ('לפנה"צ', "לפני הצהריים"),
            ('לפנה״צ', "לפני הצהריים"),
            ('בע"מ', "בערבון מוגבל"),
            ('בע״מ', "בערבון מוגבל"),
            ('קופ"ח', "קופת חולים"),
            ('קופ״ח', "קופת חולים"),
            ('ז"ל', "זכרונו לברכה"),
            ('ז״ל', "זכרונו לברכה"),
            ('הי"ד', "השם יקום דמו"),
            ('הי״ד', "השם יקום דמו"),
            ('שליט"א', "שליטא"),
            ('שליט״א', "שליטא"),
            ('רמטכ"ל', "ראש המטה הכללי"),
            ('רמטכ״ל', "ראש המטה הכללי"),
            # Measures in text
            ('ש"ח', "שקלים חדשים"),
            ('ש״ח', "שקלים חדשים"),
            ('קמ"ש', "קילומטר לשעה"),
            ('קמ״ש', "קילומטר לשעה"),
            ('מ"ר', "מטר רבוע"),
            ('מ״ר', "מטר רבוע"),
            ('מ"ק', "מטר מעוקב"),
            ('מ״ק', "מטר מעוקב"),
            ('ס"מ', "סנטימטר"),
            ('ס״מ', "סנטימטר"),
            ('ק"ג', "קילוגרם"),
            ('ק״ג', "קילוגרם"),
            ('ק"מ', "קילומטר"),
            ('ק״מ', "קילומטר"),
            ('מ"מ', "מילימטר"),
            ('מ״מ', "מילימטר"),
            ("טל'", "טלפון"),
            ("טל׳", "טלפון"),
            ("טל.", "טלפון"),
            ("tel.", "טלפון"),
        ]
        base_abbrevs = pynini.string_map(abbrev_map)

        # ----------------- Contextual Abbreviations before Numbers -----------------
        # מס' 5, No. 5, #5 -> מספר חמש
        no_lead = pynini.string_map([
            ("מס'", "מספר"),
            ("מס׳", "מספר"),
            ("מס.", "מספר"),
            ("מס", "מספר"),
            ("מספר", "מספר"),
            ("No.", "מספר"),
            ("No", "מספר"),
            ("no.", "מספר"),
            ("#", "מספר"),
        ])
        abbrev_number = no_lead + opt_space + pynutil.insert(" ") + cardinal.base_num_f

        # עמ' 5 -> עמוד חמש
        page_lead = pynini.string_map([
            ("עמ'", "עמוד"),
            ("עמ׳", "עמוד"),
            ("עמ.", "עמוד"),
            ("עמוד", "עמוד"),
            ("p.", "עמוד"),
            ("pp.", "עמודים"),
        ])
        abbrev_page = page_lead + opt_space + pynutil.insert(" ") + cardinal.base_num_f

        # סע' 12, § 12 -> סעיף שתים עשרה
        sec_lead = pynini.string_map([
            ("סע'", "סעיף"),
            ("סע׳", "סעיף"),
            ("סע.", "סעיף"),
            ("סעיף", "סעיף"),
            ("§", "סעיף"),
        ])
        abbrev_section = sec_lead + opt_space + pynutil.insert(" ") + cardinal.base_num_f

        # © 2024 -> כל הזכויות שמורות אלפיים עשרים וארבע
        copyright_expr = (
            pynini.cross("©", "כל הזכויות שמורות")
            + opt_space
            + pynutil.insert(" ")
            + cardinal.base_num_f
        )

        # ----------------- Symbols -----------------
        # Standalone symbols: &, ©, §, ‰, ¢, ~, ±
        lone_symbols = pynini.string_map([
            ("&", "וגם"),
            ("©", "כל הזכויות שמורות"),
            ("§", "סעיף"),
            ("®", "סימן רשום"),
            ("™", "סימן מסחרי"),
            ("~", "בערך"),
            ("±", "פלוס מינוס"),
        ])

        # Percent: 5% -> חמישה אחוזים / חמש אחוז
        pct_sign = pynini.cross("%", " אחוזים")
        pct_sign_alt = pynini.cross("%", " אחוז")
        percent_expr = (
            pynutil.add_weight(cardinal.base_num_m + pct_sign, -0.05)
            | pynutil.add_weight(cardinal.base_num_f + pct_sign_alt, 0.5)
        )
        # Decimal percent: 99.9% -> תשעים ותשע נקודה תשע אחוז
        pct_dec = (
            cardinal.base_num_f
            + pynini.cross(".", " נקודה ")
            + cardinal.digit_f
            + pynutil.insert(" אחוז")
            + pynutil.delete("%")
        )
        # Percent range: 10-15% -> עשרה עד חמישה עשר אחוזים
        dash = pynini.union("-", "–", "—", "־")
        percent_range = (
            cardinal.base_num_m
            + opt_space
            + pynini.cross(dash, " עד ")
            + opt_space
            + cardinal.base_num_m
            + pct_sign
        )
        percent_total = (
            pynutil.add_weight(percent_range, 0.9)
            | pynutil.add_weight(pct_dec, 0.92)
            | pynutil.add_weight(percent_expr, 0.95)
        ).optimize()

        # Permille: 5‰ -> חמישה פרומיל
        permille_expr = (
            pynutil.add_weight(cardinal.base_num_m, -0.05) + pynutil.delete(opt_space) + pynini.cross("‰", " פרומיל")
            | pynutil.add_weight(cardinal.base_num_f, 0.5) + pynutil.delete(opt_space) + pynini.cross("‰", " פרומיל")
        )

        # Cents: 25¢ -> עשרים וחמישה סנט
        cents_expr = (
            pynutil.add_weight(cardinal.base_num_m, -0.05) + pynutil.delete(opt_space) + pynini.cross("¢", " סנט")
            | pynutil.add_weight(cardinal.base_num_f, 0.5) + pynutil.delete(opt_space) + pynini.cross("¢", " סנט")
        )

        # Latin letters with & (A & B -> איי וגם בי)
        letter_map = [
            ("a", "איי"), ("A", "איי"),
            ("b", "בי"), ("B", "בי"),
            ("c", "סי"), ("C", "סי"),
            ("d", "די"), ("D", "די"),
            ("e", "אי"), ("E", "אי"),
            ("f", "אף"), ("F", "אף"),
            ("g", "ג'י"), ("G", "ג'י"),
            ("h", "אייץ'"), ("H", "אייץ'"),
            ("i", "איי"), ("I", "איי"),
            ("j", "ג'יי"), ("J", "ג'יי"),
            ("k", "קיי"), ("K", "קיי"),
            ("l", "אל"), ("L", "אל"),
            ("m", "אם"), ("M", "אם"),
            ("n", "אן"), ("N", "אן"),
            ("o", "או"), ("O", "או"),
            ("p", "פי"), ("P", "פי"),
            ("q", "קיו"), ("Q", "קיו"),
            ("r", "אר"), ("R", "אר"),
            ("s", "אס"), ("S", "אס"),
            ("t", "טי"), ("T", "טי"),
            ("u", "יו"), ("U", "יו"),
            ("v", "וי"), ("V", "וי"),
            ("w", "דבליו"), ("W", "דבליו"),
            ("x", "איקס"), ("X", "איקס"),
            ("y", "וואי"), ("Y", "וואי"),
            ("z", "זד"), ("Z", "זד"),
        ]
        letter_fst = pynini.string_map(letter_map)
        amp_letters = letter_fst + opt_space + pynini.cross("&", " וגם ") + opt_space + letter_fst

        # ----------------- Math Expressions -----------------
        # 5+3 -> חמש ועוד שלוש
        math_plus = (
            cardinal.base_num_f
            + opt_space
            + pynini.cross("+", " ועוד ")
            + opt_space
            + cardinal.base_num_f
        )
        # 5 = 5 -> חמש שווה חמש
        math_equals = (
            cardinal.base_num_f
            + opt_space
            + pynini.cross("=", " שווה ")
            + opt_space
            + cardinal.base_num_f
        )
        # Equation: 5 + 3 = 8 -> חמש ועוד שלוש שווה שמונה
        math_eq_full = (
            cardinal.base_num_f
            + opt_space
            + pynini.cross("+", " ועוד ")
            + opt_space
            + cardinal.base_num_f
            + opt_space
            + pynini.cross("=", " שווה ")
            + opt_space
            + cardinal.base_num_f
        )
        # Powers: 2^3 -> שתיים בחזקת שלוש (or שתיים בשלישית)
        math_power = (
            cardinal.base_num_f
            + opt_space
            + pynini.cross("^", " בחזקת ")
            + opt_space
            + cardinal.base_num_f
        )

        math_all = (
            pynutil.add_weight(math_eq_full, 0.88)
            | pynutil.add_weight(math_plus, 0.9)
            | pynutil.add_weight(math_equals, 0.9)
            | pynutil.add_weight(math_power, 0.92)
        ).optimize()

        all_whitelist = (
            pynutil.add_weight(amp_letters, 0.85)
            | pynutil.add_weight(abbrev_number, 0.88)
            | pynutil.add_weight(abbrev_page, 0.88)
            | pynutil.add_weight(abbrev_section, 0.88)
            | pynutil.add_weight(copyright_expr, 0.88)
            | pynutil.add_weight(percent_total, 0.89)
            | pynutil.add_weight(permille_expr, 0.89)
            | pynutil.add_weight(cents_expr, 0.89)
            | pynutil.add_weight(math_all, 0.90)
            | pynutil.add_weight(base_abbrevs, 0.92)
            | pynutil.add_weight(lone_symbols, 1.0)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_whitelist) + pynutil.insert('"')
        ).optimize()
