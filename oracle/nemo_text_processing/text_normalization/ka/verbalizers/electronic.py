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
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_preserve_order,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class ElectronicFst(GraphFst):
    """
    Finite state transducer for verbalizing electronic in Georgian, e.g.
        electronic { username: "jo" domain: "example.com" } -> "j o ეთ ეგზამპლ წერტილი კომ"
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="verbalize", deterministic=deterministic)
        graph_digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv")) | pynini.cross("0", "ნული")
        graph_symbols = pynini.string_file(get_abs_path("data/electronic/symbols.tsv")).optimize()
        words = pynini.string_file(get_abs_path("data/electronic/words.tsv"))
        domain_common = pynini.string_file(get_abs_path("data/electronic/domain.tsv"))

        verbalize_characters = pynini.cdrewrite(graph_symbols | graph_digit, "", "", NEMO_SIGMA)
        char = pynutil.add_weight(NEMO_NOT_QUOTE - " ", 1) @ verbalize_characters
        chunk = char | pynutil.add_weight(words | domain_common, 1)
        spelled = chunk + pynini.closure(insert_space + chunk)

        user_name = pynutil.delete('username: "') + spelled + pynutil.delete('"')
        domain = pynutil.delete('domain: "') + spelled + pynutil.delete('"')
        protocol = pynutil.delete('protocol: "') + spelled + pynutil.delete('"')

        self.graph = (pynini.closure(protocol + delete_space + insert_space, 0, 1) + domain) | (
            user_name + delete_space + pynutil.insert(" ეთ ") + domain
        )
        self.fst = self.delete_tokens(self.graph + delete_space + delete_preserve_order).optimize()
