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

import string

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.he.taggers.cardinal import CardinalFst


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Hebrew electronic addresses:
    URLs, emails, bare domains, and IPv4 addresses.
    e.g. info@example.com -> אינפו שטרודל אגזמפל נקודה קום
         ab3.sdd.3@gmail.com -> אי בי שלוש נקודה אס די די נקודה שלוש שטרודל ג'ימייל נקודה קום
         https://example.com/a?b=1 -> אייץ' טי טי פי אס נקודתיים סלאש סלאש אגזמפל נקודה קום סלאש איי סימן שאלה בי שווה אחת
         app.dev -> אפ נקודה דב
         model.ai -> מודל נקודה איי איי
         tool.io -> טול נקודה איי או
         192.168.1.1 -> מאה תשעים ושתיים נקודה מאה שישים ושמונה נקודה אחת נקודה אחת
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        # Latin letters to Hebrew phonetics
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
            ("x", "אקס"), ("X", "אקס"),
            ("y", "וואי"), ("Y", "וואי"),
            ("z", "זד"), ("Z", "זד"),
        ]
        letter_fst = pynini.string_map(letter_map)

        digit_fst = cardinal.digit_f

        char_fst = letter_fst | digit_fst

        # Common domains / words pronounced as words
        domain_word_map = [
            ("example", "אגזמפל"),
            ("gmail", "ג'ימייל"),
            ("google", "גוגל"),
            ("yahoo", "יאהו"),
            ("hotmail", "הוטמייל"),
            ("outlook", "אאוטלוק"),
            ("localhost", "לוקלהוסט"),
            ("app", "אפ"),
            ("model", "מודל"),
            ("tool", "טול"),
            ("info", "אינפו"),
            ("admin", "אדמין"),
            ("support", "ספורט"),
            ("api", "איי פי איי"),
            ("test", "טסט"),
            ("com", "קום"),
            ("org", "אורג"),
            ("net", "נט"),
            ("edu", "אדו"),
            ("gov", "גוב"),
            ("mil", "מיל"),
            ("io", "איי או"),
            ("ai", "איי איי"),
            ("dev", "דב"),
            ("co", "קו"),
            ("il", "איי אל"),
            ("uk", "יו קיי"),
            ("de", "די אי"),
            ("fr", "אף אר"),
        ]
        domain_words = pynini.string_map(domain_word_map)

        word_or_chars = (
            pynutil.add_weight(domain_words, 0.9)
            | pynutil.add_weight(
                char_fst + pynini.closure(insert_space + char_fst), 1.1
            )
        )

        # Electronic symbols
        dot = pynini.cross(".", " נקודה ")
        slash = pynini.cross("/", " סלאש ")
        colon = pynini.cross(":", " נקודתיים ")
        at = pynini.cross("@", " שטרודל ")
        question = pynini.cross("?", " סימן שאלה ")
        equals = pynini.cross("=", " שווה ")
        amp = pynini.cross("&", " וגם ")
        hyphen = pynini.cross("-", " מקף ")
        underscore = pynini.cross("_", " קו תחתון ")

        elem_sep = dot | slash | colon | question | equals | amp | hyphen | underscore

        # ----------------- Protocol -----------------
        proto_https = pynini.cross("https://", "אייץ' טי טי פי אס נקודתיים סלאש סלאש ")
        proto_http = pynini.cross("http://", "אייץ' טי טי פי נקודתיים סלאש סלאש ")
        proto_ftp = pynini.cross("ftp://", "אף טי פי נקודתיים סלאש סלאש ")
        protocol = proto_https | proto_http | proto_ftp

        # ----------------- Bare Domains -----------------
        # app.dev, model.ai, tool.io, example.com, test.co.il
        tld_map = [
            (".dev", " נקודה דב"),
            (".ai", " נקודה איי איי"),
            (".io", " נקודה איי או"),
            (".com", " נקודה קום"),
            (".org", " נקודה אורג"),
            (".net", " נקודה נט"),
            (".co.il", " נקודה קו נקודה איי אל"),
            (".org.il", " נקודה אורג נקודה איי אל"),
            (".gov.il", " נקודה גוב נקודה איי אל"),
            (".ac.il", " נקודה איי סי נקודה איי אל"),
        ]
        tld_fst = pynini.string_map(tld_map)

        domain_name = (
            domain_words
            | (pynini.closure(NEMO_ALPHA, 1) @ (letter_fst + pynini.closure(insert_space + letter_fst)))
        )
        bare_domain = domain_name + tld_fst

        # ----------------- Full URL -----------------
        url_chunk = word_or_chars
        url_tail = pynini.closure(elem_sep + url_chunk)
        full_url = (
            protocol
            + url_chunk
            + url_tail
        )

        # ----------------- Email -----------------
        email_chunk = word_or_chars
        email_user = email_chunk + pynini.closure((dot | hyphen | underscore) + email_chunk)
        email_domain = bare_domain | (domain_name + pynini.closure(dot + domain_name))
        email = email_user + at + email_domain

        # ----------------- IPv4 -----------------
        # 192.168.1.1
        octet = cardinal.base_num_f
        ipv4 = octet + dot + octet + dot + octet + dot + octet

        all_electronic = (
            pynutil.add_weight(full_url, 0.9)
            | pynutil.add_weight(email, 0.92)
            | pynutil.add_weight(bare_domain, 0.94)
            | pynutil.add_weight(ipv4, 0.95)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "') + convert_space(all_electronic) + pynutil.insert('"')
        ).optimize()
