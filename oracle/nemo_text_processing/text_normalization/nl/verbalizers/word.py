# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_CHAR,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
)


class WordFst(GraphFst):
    """
    Finite state transducer for verbalizing Dutch tokens with name field.
    e.g. tokens { name: "honderd\u00a0euro" } -> honderd euro
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="word", kind="verbalize", deterministic=deterministic)
        chars = pynini.closure(NEMO_CHAR - " ", 1)
        char = pynutil.delete("name:") + delete_space + pynutil.delete('"') + chars + pynutil.delete('"')
        graph = char @ pynini.cdrewrite(pynini.cross("\u00a0", " "), "", "", NEMO_SIGMA)

        self.fst = graph.optimize()
