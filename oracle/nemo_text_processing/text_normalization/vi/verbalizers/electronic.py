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

from nemo_text_processing.text_normalization.vi.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    NEMO_WHITE_SPACE,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.vi.utils import get_abs_path, load_labels


class ElectronicFst(GraphFst):
    """
    Finite state transducer for verbalizing Vietnamese electronic addresses, e.g.
        electronic { username: "abc" domain: "gmail.com" } -> abc a còng gmail chấm com
        electronic { protocol: "https://" domain: "vnexpress.net/the-thao" }
        -> h t t p s hai chấm gạch chéo gạch chéo vnexpress chấm nét gạch chéo the gạch ngang thao

    Reading rule: runs of letters are kept as written words (the speech model reads them), digits are read one by one
    (data/numbers/digit.tsv, zero.tsv), symbols use data/electronic/symbols.tsv, domain suffixes followed by "/", ".",
    ":" or the end use data/electronic/domain.tsv, and the protocol prefixes use data/electronic/protocol.tsv.

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="verbalize", deterministic=deterministic)

        def spaced(path: str) -> "pynini.FstLike":
            return pynini.string_map([(k, f" {v} ") for k, v in load_labels(get_abs_path(path))])

        digits = pynini.union(spaced("data/numbers/digit.tsv"), spaced("data/numbers/zero.tsv"))
        symbols = spaced("data/electronic/symbols.tsv")
        domains = spaced("data/electronic/domain.tsv")

        rewrite_symbols = pynini.cdrewrite(symbols, "", "", NEMO_SIGMA)
        rewrite_digits = pynini.cdrewrite(digits, "", "", NEMO_SIGMA)
        rewrite_domains = pynini.cdrewrite(domains, "", pynini.union("/", ".", ":", "[EOS]"), NEMO_SIGMA)

        words = pynini.closure(NEMO_NOT_SPACE, 1)
        squeeze = (
            pynutil.delete(pynini.closure(NEMO_WHITE_SPACE))
            + words
            + pynini.closure(pynini.cross(pynini.closure(NEMO_WHITE_SPACE, 1), " ") + words)
            + pynutil.delete(pynini.closure(NEMO_WHITE_SPACE))
        )

        spell_text = (rewrite_symbols @ rewrite_digits @ squeeze).optimize()
        spell_domain = (rewrite_domains @ spell_text).optimize()

        protocols = load_labels(get_abs_path("data/electronic/protocol.tsv"))
        http = pynini.string_map([row for row in protocols if row[0].startswith("http")])
        www = pynini.string_map([row for row in protocols if not row[0].startswith("http")])
        protocol_words = (http + pynini.closure(insert_space + www, 0, 1)) | www

        def field(name: str, graph: "pynini.FstLike") -> "pynini.FstLike":
            return (
                pynutil.delete(f"{name}: \"")
                + pynini.compose(pynini.closure(NEMO_NOT_QUOTE, 1), graph)
                + pynutil.delete("\"")
            )

        at = dict(load_labels(get_abs_path("data/electronic/symbols.tsv")))["@"]
        email = (
            field("username", spell_text)
            + delete_space
            + pynutil.insert(f" {at} ")
            + field("domain", spell_domain)
        )
        url = pynini.closure(field("protocol", protocol_words) + delete_space + insert_space, 0, 1) + field(
            "domain", spell_domain
        )
        value = pynutil.delete("value: \"") + pynini.closure(NEMO_NOT_QUOTE, 1) + pynutil.delete("\"")

        self.fst = self.delete_tokens(email | url | value).optimize()
