# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.kn.graph_utils import (
    MIN_NEG_WEIGHT,
    NEMO_NOT_QUOTE,
    NEMO_SPACE,
    GraphFst,
    delete_space,
    insert_space,
)


class TelephoneFst(GraphFst):
    """
    Finite state transducer for verbalizing telephone numbers, e.g.
        telephone { country_code: "ಪ್ಲಸ್ ಒಂಬತ್ತು ಒಂದು" number_part: "ಒಂಬತ್ತು ಎಂಟು ನಾಲ್ಕು ಎಂಟು ಸೊನ್ನೆ ಎರಡು ಎರಡು ಮೂರು ಮೂರು ಎಂಟು" }
            -> ಪ್ಲಸ್ ಒಂಬತ್ತು ಒಂದು ಒಂಬತ್ತು ಎಂಟು ನಾಲ್ಕು ಎಂಟು ಸೊನ್ನೆ ಎರಡು ಎರಡು ಮೂರು ಮೂರು ಎಂಟು
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="telephone", kind="verbalize", deterministic=deterministic)

        optional_country_code = pynini.closure(
            pynutil.delete("country_code: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\"")
            + delete_space
            + insert_space,
            0,
            1,
        )

        number_part = (
            pynutil.delete("number_part: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynini.closure(pynutil.add_weight(pynutil.delete(NEMO_SPACE), MIN_NEG_WEIGHT), 0, 1)
            + pynutil.delete("\"")
        )

        optional_extension = pynini.closure(
            delete_space
            + insert_space
            + pynutil.delete("extension: \"")
            + pynini.closure(NEMO_NOT_QUOTE, 1)
            + pynutil.delete("\""),
            0,
            1,
        )

        graph = optional_country_code + number_part + optional_extension
        delete_tokens = self.delete_tokens(graph)
        self.fst = delete_tokens.optimize()
