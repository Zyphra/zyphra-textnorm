# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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
    INPUT_CASED,
    INPUT_LOWER_CASED,
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

GREEK_LOWER = pynini.union(
    "α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ", "ν", "ξ", "ο", "π", "ρ", "σ", "ς", "τ", "υ",
    "φ", "χ", "ψ", "ω", "ά", "έ", "ή", "ί", "ό", "ύ", "ώ", "ϊ", "ϋ", "ΐ", "ΰ"
).optimize()

GREEK_UPPER = pynini.union(
    "Α", "Β", "Γ", "Δ", "Ε", "Ζ", "Η", "Θ", "Ι", "Κ", "Λ", "Μ", "Ν", "Ξ", "Ο", "Π", "Ρ", "Σ", "Τ", "Υ",
    "Φ", "Χ", "Ψ", "Ω", "Ά", "Έ", "Ή", "Ί", "Ό", "Ύ", "Ώ", "Ϊ", "Ϋ"
).optimize()

GREEK_ALPHA = pynini.union(GREEK_LOWER, GREEK_UPPER).optimize()
ALL_ALPHA = pynini.union(NEMO_ALPHA, GREEK_ALPHA).optimize()

GREEK_PUNCT = pynini.union(
    "!", "\"", "#", "$", "%", "&", "'", "(", ")", "*", "+", ",", "-", ".", "/", ":", ";", "<", "=", ">", "?", "@",
    pynini.escape("["), pynini.escape("\\"), pynini.escape("]"), "^", "_", "`", "{", "|", "}", "~",
    "·", "·", ";", "«", "»", "„", "“", "”", "‘", "’", "–", "—", "…", "‰", "°", "±", "×", "÷"
).optimize()

MINUS = pynini.union("-", "−").optimize()
