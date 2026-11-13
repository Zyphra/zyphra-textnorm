# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_NOT_SPACE, GraphFst


class WordFst(GraphFst):
    """
    Finite state transducer for classifying ordinary words:
        sleep -> tokens { name: "sleep" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="word", kind="classify", deterministic=deterministic)
        word = pynutil.insert('name: "') + pynini.closure(NEMO_NOT_SPACE, 1) + pynutil.insert('"')
        self.fst = word.optimize()
