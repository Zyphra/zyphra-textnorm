# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)


class PunctuationFst(GraphFst):
    """
    Finite state transducer for classifying punctuation marks into tokens { name: "..." }.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="punctuation", kind="classify", deterministic=deterministic)

        s = "!#$%&\'()*+,-./:;<=>?@^_`{|}~\""
        typographic = "«»„“”‘’–—…"
        punct = pynini.union(*s, *typographic, r"\[", r"\]")

        graph = pynutil.insert('name: "') + punct + pynutil.insert('"')
        self.fst = graph.optimize()
