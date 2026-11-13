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

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_SIGMA

# Georgian script letters: Mkhedruli (U+10D0..U+10FA) and Mtavruli capitals (U+1C90..U+1CBA).
GEORGIAN_LOWER = pynini.union(*[chr(c) for c in range(0x10D0, 0x10FB)]).optimize()
GEORGIAN_UPPER = pynini.union(*[chr(c) for c in range(0x1C90, 0x1CBB)]).optimize()
GEORGIAN_ALPHA = pynini.union(GEORGIAN_LOWER, GEORGIAN_UPPER).optimize()

# A case ending or derivative suffix written after a number with a hyphen:
# "12:30-ზე", "25%-ით", "1990-იანები", "5-ს", "1-ლი", "2-ე".
_HYPHEN = pynini.union("-", "–", "—", "֊")
_SUFFIX_MARK = "+"
case_suffix = pynutil.delete(_HYPHEN) + pynutil.insert(_SUFFIX_MARK) + pynini.closure(GEORGIAN_LOWER, 1, 12)

# Gluing an ending to a spoken number or unit word:
# Regular Georgian inflection elides stem-final "ი" or "ა" before case endings and postpositions.
_glue = (
    # Words ending in "ი":
    pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "დან", "იდან"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "მდე", "ამდე"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "იდან", "იდან"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ამდე", "ამდე"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ით", "ით"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ის", "ის"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ად", "ად"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ს", "ს"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ზე", "ზე"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ში", "ში"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "მა", "მა"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "თან", "თან"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "კენ", "კენ"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "თვის", "თვის"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "ისთვის", "ისთვის"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "იანი", "იანი"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "იანები", "იანები"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "იანებში", "იანებში"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ი" + _SUFFIX_MARK + "იანების", "იანების"), "", "", NEMO_SIGMA)
    # Words ending in "ა" (რვა, ცხრა):
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "დან", "იდან"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "იდან", "იდან"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "მდე", "ამდე"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "ამდე", "ამდე"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "ით", "ით"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "ის", "ის"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "ს", "ს"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "ზე", "ზე"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "ში", "ში"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ა" + _SUFFIX_MARK + "მა", "მ"), "", "", NEMO_SIGMA)
    # Ordinal stems ending in "ე" (მეორე, მესამე, მეათე):
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ეს", "ეს"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ემ", "ემ"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ე", "ე"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ის", "ის"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ით", "ით"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ად", "ედ"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ედ", "ედ"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "მ", "მ"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "მა", "მ"), "", "", NEMO_SIGMA)
    @ pynini.cdrewrite(pynini.cross("ე" + _SUFFIX_MARK + "ს", "ს"), "", "", NEMO_SIGMA)
    # Stems ending in "ო" (ევრო):
    @ pynini.cdrewrite(pynini.cross("ო" + _SUFFIX_MARK + "ით", "ოთი"), "", "", NEMO_SIGMA)
    # General cleanup: delete suffix mark
    @ pynini.cdrewrite(pynutil.delete(_SUFFIX_MARK), "", "", NEMO_SIGMA)
).optimize()


def glue_suffix(graph: "pynini.FstLike") -> "pynini.FstLike":
    """``graph`` (whose output may hold one ``case_suffix`` mark) with the ending glued to the preceding word."""
    return pynini.compose(graph, _glue)


def with_suffix(graph: "pynini.FstLike") -> "pynini.FstLike":
    """``graph`` followed by a written "-<ending>", glued to its last spoken word (see ``glue_suffix``)."""
    return glue_suffix(graph + case_suffix)
