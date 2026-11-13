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

# Finnish alphabet: Latin plus ä, ö, å, and uppercase versions
FINNISH_SPECIAL_LOWER = pynini.union("ä", "ö", "å", "š", "ž")
FINNISH_SPECIAL_UPPER = pynini.union("Ä", "Ö", "Å", "Š", "Ž")
FINNISH_LOWER = (NEMO_LOWER | FINNISH_SPECIAL_LOWER).optimize()
FINNISH_UPPER = (NEMO_UPPER | FINNISH_SPECIAL_UPPER).optimize()
FINNISH_ALPHA = (FINNISH_LOWER | FINNISH_UPPER).optimize()

FINNISH_VOWELS = pynini.union("a", "e", "i", "o", "u", "y", "ä", "ö", "å",
                              "A", "E", "I", "O", "U", "Y", "Ä", "Ö", "Å")
