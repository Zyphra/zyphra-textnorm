# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    generator_main,
)
from nemo_text_processing.utils.logging import logger
from nemo_text_processing.text_normalization.en.verbalizers.date_fields import DateFieldsFst


class VerbalizeFinalFst(GraphFst):
    """
    Finite state transducer that verbalizes tokenized sequences in Thai (th).
    Strips token boundaries and name wrappers, converts NBSP to spaces,
    and preserves unspaced continuity in native Thai text.
    """

    def __init__(self, deterministic: bool = True, cache_dir: str = None, overwrite_cache: bool = False):
        super().__init__(name="verbalize_final", kind="verbalize", deterministic=deterministic)

        far_file = None
        if cache_dir is not None and cache_dir != "None":
            os.makedirs(cache_dir, exist_ok=True)
            far_file = os.path.join(cache_dir, f"th_tn_{deterministic}_deterministic_verbalizer.far")

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["verbalize"]
            logger.info(f"VerbalizeFinalFst graph was restored from {far_file}.")
        else:
            chars = pynini.closure(NEMO_NOT_QUOTE, 1)
            char = pynutil.delete("name:") + delete_space + pynutil.delete('"') + chars + pynutil.delete('"')
            word_fst = (
                char @ pynini.cdrewrite(pynini.cross("\u00a0", " "), "", "", NEMO_SIGMA)
            ) | DateFieldsFst(deterministic=deterministic).fst

            token_verbalizer = (
                pynutil.delete("tokens")
                + delete_space
                + pynutil.delete("{")
                + delete_space
                + word_fst
                + delete_space
                + pynutil.delete("}")
            )

            verbalizer = pynini.closure(delete_space + token_verbalizer + delete_space)
            self.fst = verbalizer.optimize()

            if far_file:
                generator_main(far_file, {"verbalize": self.fst})
                logger.info(f"VerbalizeFinalFst grammars saved to {far_file}.")
