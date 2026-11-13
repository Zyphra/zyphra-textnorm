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

# Number names from Unicode CLDR release-49 (fil locale, Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_preserve_order,
)
from nemo_text_processing.text_normalization.tl.utils import get_abs_path


class ElectronicFst(GraphFst):
    """
    Finite state transducer for verbalizing Tagalog electronic; letter runs stay words, digits and symbols are named, e.g.
        electronic { username: "info" domain: "domain.com" } -> info at domain tuldok com

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="verbalize", deterministic=deterministic)
        digit = pynini.string_file(get_abs_path("data/numbers/digit.tsv")) | pynini.string_file(
            get_abs_path("data/numbers/zero.tsv")
        )
        symbols = pynini.string_file(get_abs_path("data/electronic/symbols.tsv"))
        domain_common = pynini.string_file(get_abs_path("data/electronic/domain.tsv"))

        def padded(fst):
            return pynutil.insert(" ") + fst + pynutil.insert(" ")

        tld_end = pynini.union(".", "/", ":", "[EOS]")
        read_tlds = pynini.cdrewrite(padded(domain_common), "", tld_end, NEMO_SIGMA)
        read_chars = pynini.cdrewrite(padded(symbols | digit), "", "", NEMO_SIGMA)
        cleanup = (
            pynini.cdrewrite(pynini.cross(pynini.closure(" ", 2), " "), "", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.delete(" "), "[BOS]", "", NEMO_SIGMA)
            @ pynini.cdrewrite(pynutil.delete(" "), "", "[EOS]", NEMO_SIGMA)
        )
        value = pynini.closure(NEMO_NOT_QUOTE, 1)
        user_name = pynutil.delete('username: "') + value @ read_chars @ cleanup + pynutil.delete('"')
        domain = pynutil.delete('domain: "') + value @ read_tlds @ read_chars @ cleanup + pynutil.delete('"')
        spell = pynini.closure(NEMO_NOT_QUOTE + pynutil.insert(" ")) + NEMO_NOT_QUOTE
        protocol = pynutil.delete('protocol: "') + value @ spell @ read_chars @ cleanup + pynutil.delete('"')

        graph = pynini.closure(protocol + pynini.accep(" "), 0, 1) + domain
        graph |= user_name + pynini.accep(" ") + pynutil.insert("at ") + domain
        self.fst = self.delete_tokens(graph + delete_preserve_order).optimize()
