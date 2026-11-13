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
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    delete_space,
    insert_space,
)

TURKISH_LOWER_CHARS = "abcçdefgğhıijklmnoöprsştuüvyzâîû"
TURKISH_UPPER_CHARS = "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZÂÎÛ"

TURKISH_LOWER = pynini.union(*[c for c in TURKISH_LOWER_CHARS]).optimize()
TURKISH_UPPER = pynini.union(*[c for c in TURKISH_UPPER_CHARS]).optimize()
TURKISH_ALPHA = (TURKISH_LOWER | TURKISH_UPPER).optimize()

_APOSTROPHE = pynini.union("'", "’", "`", "´")
_SUFFIX_MARK = "+"
case_suffix = pynini.cross(_APOSTROPHE, _SUFFIX_MARK) + pynini.closure(TURKISH_LOWER, 1, 10)

_glue = (
    pynini.cdrewrite(pynini.cross("dört" + _SUFFIX_MARK + "e", "dörde"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("dört" + _SUFFIX_MARK + "ü", "dördü"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("dört" + _SUFFIX_MARK + "i", "dördi"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("dört" + _SUFFIX_MARK + "a", "dörda"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("iki" + _SUFFIX_MARK + "inci", "ikinci"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("iki" + _SUFFIX_MARK + "nci", "ikinci"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("altı" + _SUFFIX_MARK + "ıncı", "altıncı"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("altı" + _SUFFIX_MARK + "ncı", "altıncı"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("yedi" + _SUFFIX_MARK + "inci", "yedinci"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("yedi" + _SUFFIX_MARK + "nci", "yedinci"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynutil.delete(_SUFFIX_MARK), "", "", NEMO_SIGMA)
).optimize()


def glue_suffix(graph: "pynini.FstLike") -> "pynini.FstLike":
    """Composes graph (producing spoken text + suffix marked by '+') with phonological gluing."""
    return pynini.compose(graph, _glue)


def with_suffix(graph: "pynini.FstLike") -> "pynini.FstLike":
    """Graph followed by a written apostrophe + suffix, glued phonologically."""
    return glue_suffix(graph + case_suffix)
