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
    NEMO_ALPHA,
    NEMO_ALNUM,
    NEMO_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.vi.utils import get_abs_path

class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying Vietnamese electronic addresses (e-mail addresses and URLs), e.g.
        "abc@gmail.com" -> electronic { username: "abc" domain: "gmail.com" }
        "https://vnexpress.net/the-thao" -> electronic { protocol: "https://" domain: "vnexpress.net/the-thao" }
        "www.google.com.vn" -> electronic { protocol: "www." domain: "google.com.vn" }
        "dantri.com.vn" -> electronic { domain: "dantri.com.vn" }

    URLs need a protocol ("http://", "https://"), a "www." prefix, or a host ending in a domain listed in
    data/electronic/domain.tsv. Addresses end in a letter, a digit or "/", so trailing sentence punctuation
    stays a separate token.

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        known_domain = pynini.project(pynini.string_file(get_abs_path("data/electronic/domain.tsv")), "input")

        label = NEMO_ALNUM + pynini.closure(pynini.closure(pynini.union(NEMO_ALNUM, "-")) + NEMO_ALNUM, 0, 1)
        host = label + pynini.closure("." + label, 1)
        known_host = label + pynini.closure("." + label) + known_domain

        path_char = pynini.union(NEMO_ALNUM, "/", "-", "_", ".", "?", "=", "&", "#", "%", "~", ":", "+")
        path = "/" + pynini.closure(pynini.closure(path_char) + pynini.union(NEMO_ALNUM, "/"), 0, 1)

        username = NEMO_ALNUM + pynini.closure(
            pynini.closure(pynini.union(NEMO_ALNUM, ".", "_", "-", "+")) + NEMO_ALNUM, 0, 1
        )
        email = (
            pynutil.insert("username: \"")
            + username
            + pynutil.insert("\"")
            + pynutil.delete("@")
            + insert_space
            + pynutil.insert("domain: \"")
            + host
            + pynutil.insert("\"")
        )

        protocol = (pynini.union("http://", "https://") + pynini.closure("www.", 0, 1)) | "www."
        port = ":" + pynini.closure(NEMO_DIGIT, 1, 5)
        url_with_protocol = (
            pynutil.insert("protocol: \"")
            + protocol
            + pynutil.insert("\"")
            + insert_space
            + pynutil.insert("domain: \"")
            + (label + pynini.closure("." + label))
            + pynini.closure(port, 0, 1)
            + pynini.closure(path, 0, 1)
            + pynutil.insert("\"")
        )
        url_bare = (
            pynutil.insert("domain: \"")
            + known_host
            + pynini.closure(port, 0, 1)
            + pynini.closure(path, 0, 1)
            + pynutil.insert("\"")
        )

        # IPv4 addresses ("192.168.1.1") and multi-dot software versions ("3.11.2", "v2.0", "v3.11.2"):
        # exclude 3-digit segments on bare 2-dot/3-dot runs so thousands-grouped integers ("1.000.000") stay cardinals.
        octet = pynini.union(*[str(i) for i in range(256)])
        ipv4 = pynini.difference(
            octet + "." + octet + "." + octet + "." + octet,
            (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2) + ("." + NEMO_DIGIT**3) ** 3,
        )

        ver_seg_non3 = pynini.closure(NEMO_DIGIT, 1, 2) | pynini.closure(NEMO_DIGIT, 4, 5)
        ver_seg_any = pynini.closure(NEMO_DIGIT, 1, 5)
        v_prefix = pynini.union("v", "V")
        version_prefixed = v_prefix + ver_seg_any + pynini.closure("." + ver_seg_any, 1, 3)
        version_bare = ver_seg_non3 + "." + ver_seg_non3 + "." + ver_seg_non3

        # Hyphenated alphanumeric model/code tokens ("COVID-19", "GPT-4", "B-52") so "-19" is not read "âm mười chín"
        if cardinal is not None:
            alpha_part = pynini.closure(NEMO_ALPHA, 1)
            num_part = pynini.compose(pynini.closure(NEMO_DIGIT, 1, 4), cardinal.graph)
            model_code = (
                pynutil.insert("value: \"")
                + alpha_part
                + pynini.cross("-", " ")
                + num_part
                + pynini.closure(pynini.cross("-", " ") + (num_part | alpha_part), 0, 1)
                + pynutil.insert("\"")
            )
            dotted_code = (
                pynutil.insert("value: \"")
                + pynini.compose(
                    ipv4 | version_bare,
                    num_part + pynini.closure(pynini.cross(".", " chấm ") + num_part, 2, 3),
                )
                + pynutil.insert("\"")
            ) | (
                pynutil.insert("value: \"")
                + v_prefix
                + pynutil.insert(" ")
                + pynini.compose(
                    ver_seg_any + pynini.closure("." + ver_seg_any, 1, 3),
                    num_part + pynini.closure(pynini.cross(".", " chấm ") + num_part, 1, 3),
                )
                + pynutil.insert("\"")
            )
            extra = model_code | dotted_code
        else:
            extra = pynutil.insert("domain: \"") + (ipv4 | version_prefixed | version_bare) + pynutil.insert("\"")

        graph = email | url_with_protocol | url_bare | extra
        self.fst = self.add_tokens(graph).optimize()
