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

from nemo_text_processing.text_normalization.ar.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_preserve_order,
    delete_space,
)
from nemo_text_processing.text_normalization.ar.utils import get_abs_path


class ElectronicFst(GraphFst):
    """
    Finite state transducer for verbalizing electronic addresses: Latin words are kept, known top-level domains and
    symbols are spoken (data/electronic/domain.tsv, symbols.tsv, protocol.tsv) and digits are read one by one, e.g.
        electronic { username: "info" domain: "example.com" } -> "info آت example نقطة كوم"
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="verbalize", deterministic=deterministic)
        digit = pynini.string_file(get_abs_path("data/number/digit.tsv")) | pynini.string_file(
            get_abs_path("data/number/zero.tsv")
        )
        symbols = pynini.string_file(get_abs_path("data/electronic/symbols.tsv"))
        domains = pynini.string_file(get_abs_path("data/electronic/domain.tsv"))
        protocols = pynini.string_file(get_abs_path("data/electronic/protocol.tsv"))

        def spaced(fst):
            return pynutil.insert(" ") + fst + pynutil.insert(" ")

        speak = (
            pynini.cdrewrite(spaced(domains), "", pynini.union("[EOS]", "/", ":", "?", "#"), NEMO_SIGMA)
            @ pynini.cdrewrite(spaced(symbols), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(spaced(digit), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.delete(" "), " ", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.delete(" "), "[BOS]", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.delete(" "), "", "[EOS]", NEMO_SIGMA)
        )
        value = pynini.closure(NEMO_NOT_QUOTE, 1) @ speak

        user_name = pynutil.delete('username: "') + value + pynutil.delete('"')
        domain = pynutil.delete('domain: "') + value + pynutil.delete('"')
        protocol = pynutil.delete('protocol: "') + protocols + pynutil.delete('"')

        graph = (
            user_name + delete_space + pynutil.insert(" آت ") + domain
            | protocol + delete_space + pynutil.insert(" ") + domain
            | domain
        )
        self.fst = self.delete_tokens(graph + delete_preserve_order).optimize()
