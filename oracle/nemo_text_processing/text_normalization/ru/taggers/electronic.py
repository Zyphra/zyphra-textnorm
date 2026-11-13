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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ru.alphabet import RU_ALPHA, TO_CYRILLIC
from nemo_text_processing.text_normalization.ru.utils import get_abs_path


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic: email addresses
        e.g. "ab@nd.ru" -> electronic { username: "эй би собака эн ди точка ру" }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        # tagger
        accepted_symbols = []
        with open(get_abs_path("data/electronic/symbols.tsv"), 'r', encoding='utf-8') as f:
            for line in f:
                symbol, _ = line.split('\t')
                accepted_symbols.append(pynini.accep(symbol))
        username = (
            pynutil.insert("username: \"")
            + NEMO_ALPHA
            + pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.union(*accepted_symbols))
            + pynutil.insert("\"")
            + pynini.cross('@', ' ')
        )
        domain_graph = (
            NEMO_ALPHA
            + (pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.accep('-') | pynini.accep('.')))
            + (NEMO_ALPHA | NEMO_DIGIT)
        )
        domain_graph = pynutil.insert("domain: \"") + domain_graph + pynutil.insert("\"")
        tagger_graph = (username + domain_graph).optimize()

        # verbalizer
        graph_digit = pynini.string_file(get_abs_path("data/numbers/digits_nominative_case.tsv")).optimize()
        graph_symbols = pynini.string_file(get_abs_path("data/electronic/symbols.tsv")).optimize()
        user_name = (
            pynutil.delete("username:")
            + delete_space
            + pynutil.delete("\"")
            + (
                pynini.closure(
                    pynutil.add_weight(graph_digit + insert_space, 1.09)
                    | pynutil.add_weight(pynini.closure(graph_symbols + pynutil.insert(" ")), 1.09)
                    | pynutil.add_weight(NEMO_NOT_QUOTE + insert_space, 1.1)
                )
            )
            + pynutil.delete("\"")
        )

        domain_default = (
            pynini.closure(NEMO_NOT_QUOTE + insert_space)
            + pynini.cross(".", "точка ")
            + NEMO_NOT_QUOTE
            + pynini.closure(insert_space + NEMO_NOT_QUOTE)
        )

        server_default = (
            pynini.closure((graph_digit | NEMO_ALPHA) + insert_space, 1)
            + pynini.closure(graph_symbols + insert_space)
            + pynini.closure((graph_digit | NEMO_ALPHA) + insert_space, 1)
        )
        server_common = pynini.string_file(get_abs_path("data/electronic/server_name.tsv")) + insert_space
        domain_common = pynini.cross(".", "точка ") + pynini.string_file(get_abs_path("data/electronic/domain.tsv"))
        domain = (
            pynutil.delete("domain:")
            + delete_space
            + pynutil.delete("\"")
            + (pynutil.add_weight(server_common, 1.09) | pynutil.add_weight(server_default, 1.1))
            + (pynutil.add_weight(domain_common, 1.09) | pynutil.add_weight(domain_default, 1.1))
            + delete_space
            + pynutil.delete("\"")
        )

        graph = user_name + delete_space + pynutil.insert("собака ") + delete_space + domain + delete_space
        # replace all latin letters with their Ru verbalization
        spell = pynini.closure(TO_CYRILLIC | RU_ALPHA | pynini.accep(" "))
        verbalizer_graph = (graph.optimize() @ spell).optimize()

        self.final_graph = (tagger_graph @ verbalizer_graph).optimize()

        # URLs: "https://example.com/page" -> "эйч ти ти пи эс двоеточие слэш слэш ... точка ком слэш пэйдж"
        protocol = pynini.cross("https://", "эйч ти ти пи эс двоеточие слэш слэш ") | pynini.cross(
            "http://", "эйч ти ти пи двоеточие слэш слэш "
        )
        www = pynini.cross("www.", "дабл ю дабл ю дабл ю точка ")
        url_symbols = pynini.string_map(
            [(".", "точка"), ("/", "слэш"), ("-", "дефис"), ("_", "нижнее подчеркивание"), ("?", "вопросительный знак"),
             ("=", "равно"), ("&", "амперсанд"), ("#", "решетка"), (":", "двоеточие"), ("%", "процент"), ("~", "тильда")]
        )
        server = pynini.string_file(get_abs_path("data/electronic/server_name.tsv"))
        domain_words = pynini.string_file(get_abs_path("data/electronic/domain.tsv"))
        alnum_char = (NEMO_ALPHA @ spell) | RU_ALPHA | graph_digit
        alnum_seq = alnum_char + pynini.closure(insert_space + alnum_char)
        url_word = (
            pynutil.add_weight(server, -0.1)
            | pynutil.add_weight(domain_words, -0.1)
            | pynutil.add_weight(alnum_seq, 0.01)
        ).optimize()
        sym_seq = url_symbols + pynini.closure(insert_space + url_symbols)
        url_body = url_word + pynini.closure(insert_space + sym_seq + insert_space + url_word)
        url_body += pynini.closure(insert_space + sym_seq, 0, 1)
        has_tld = pynini.closure(NEMO_ALPHA | NEMO_DIGIT | "-", 1) + "." + pynini.union(
            "com", "ru", "org", "net", "io", "ai", "dev", "app", "edu", "gov", "co", "me", "рф", "su", "info", "by", "kz", "ua"
        )
        bare = pynini.compose(
            has_tld
            + pynini.closure(
                pynini.union("/", "?") + pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.union(*"/.-_?=&#%~:"))
            ),
            url_body,
        )
        url = (protocol + pynini.closure(www, 0, 1) + url_body) | (www + url_body) | pynutil.add_weight(bare, 0.5)
        self.final_graph |= url.optimize()
        self.fst = self.add_tokens(pynutil.insert("username: \"") + self.final_graph + pynutil.insert("\"")).optimize()
