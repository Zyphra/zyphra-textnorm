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
    NEMO_ALPHA,
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_NOT_QUOTE,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    NEMO_SPACE,
    NEMO_WHITE_SPACE,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
    insert_space,
)

# Bulgarian Cyrillic letters
_bg_lower_chars = [chr(c) for c in range(0x0430, 0x0450)] + ["\u0450", "\u045c"]  # а-я, ѐ, ѝ
_bg_upper_chars = [chr(c) for c in range(0x0410, 0x0430)] + ["\u0400", "\u040c"]  # А-Я, Ѐ, Ѝ

BULGARIAN_LOWER = pynini.union(*_bg_lower_chars).optimize()
BULGARIAN_UPPER = pynini.union(*_bg_upper_chars).optimize()
BULGARIAN_ALPHA = pynini.union(BULGARIAN_LOWER, BULGARIAN_UPPER).optimize()
ANY_ALPHA = pynini.union(NEMO_ALPHA, BULGARIAN_ALPHA).optimize()
