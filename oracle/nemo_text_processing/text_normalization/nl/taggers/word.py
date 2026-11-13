# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_NOT_SPACE,
    GraphFst,
)


class WordFst(GraphFst):
    """
    Finite state transducer for classifying ordinary words into tokens { name: "..." }.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)

        word = pynutil.insert('name: "') + pynini.closure(NEMO_NOT_SPACE, 1) + pynutil.insert('"')
        self.fst = word.optimize()
