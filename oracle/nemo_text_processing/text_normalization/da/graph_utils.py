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
from pynini.lib import byte, pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_LOWER,
    NEMO_NON_BREAKING_SPACE,
    NEMO_NOT_QUOTE,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    NEMO_SPACE,
    NEMO_UPPER,
    NEMO_WHITE_SPACE,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
    insert_space,
)

_ALPHA_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅÉ"
_ALPHA_LOWER = "abcdefghijklmnopqrstuvwxyzæøåé"

TO_LOWER = pynini.union(*[pynini.cross(x, y) for x, y in zip(_ALPHA_UPPER, _ALPHA_LOWER)])
TO_UPPER = pynini.invert(TO_LOWER)

DA_LOWER = pynini.union(*_ALPHA_LOWER).optimize()
DA_UPPER = pynini.union(*_ALPHA_UPPER).optimize()
DA_ALPHA = pynini.union(DA_LOWER, DA_UPPER).optimize()
DA_ALNUM = pynini.union(NEMO_DIGIT, DA_ALPHA).optimize()

ensure_space = pynini.cross(pynini.closure(delete_space, 0, 1), " ")
