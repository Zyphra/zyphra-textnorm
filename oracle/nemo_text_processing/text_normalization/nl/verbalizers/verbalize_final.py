# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import os

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
    delete_extra_space,
    delete_space,
    generator_main,
)
from nemo_text_processing.text_normalization.nl.verbalizers.verbalize import VerbalizeFst
from nemo_text_processing.text_normalization.nl.verbalizers.word import WordFst
from nemo_text_processing.utils.logging import logger
from nemo_text_processing.text_normalization.en.verbalizers.date_fields import DateFieldsFst


class VerbalizeFinalFst(GraphFst):
    """
    Finite state transducer that verbalizes an entire sentence for Dutch.
    Verbalizes tokens { name: "..." } into spoken Dutch text.

    Args:
        deterministic: True or False
        cache_dir: path to directory with FAR grammar files
        overwrite_cache: set to True to overwrite FAR files
    """

    def __init__(self, deterministic: bool = True, cache_dir: str = None, overwrite_cache: bool = False):
        super().__init__(name="verbalize_final", kind="verbalize", deterministic=deterministic)

        far_file = None
        if cache_dir is not None and cache_dir != "None":
            os.makedirs(cache_dir, exist_ok=True)
            far_file = os.path.join(cache_dir, f"nl_tn_{deterministic}_deterministic_verbalizer.far")

        if not overwrite_cache and far_file and os.path.exists(far_file):
            self.fst = pynini.Far(far_file, mode="r")["verbalize"]
            logger.info(f"VerbalizeFinalFst graph was restored from {far_file}.")
        else:
            verbalize = VerbalizeFst(deterministic=deterministic).fst
            word = WordFst(deterministic=deterministic).fst

            types = verbalize | word | DateFieldsFst(deterministic=deterministic).fst
            graph = (
                pynutil.delete("tokens")
                + delete_space
                + pynutil.delete("{")
                + delete_space
                + types
                + delete_space
                + pynutil.delete("}")
            )
            graph = delete_space + pynini.closure(graph + delete_extra_space) + graph + delete_space

            self.fst = graph.optimize()

            if far_file:
                generator_main(far_file, {"verbalize": self.fst})
