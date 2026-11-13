# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst
from nemo_text_processing.text_normalization.en.taggers.punctuation import (
    PunctuationFst as EnPunctuationFst,
)


class PunctuationFst(GraphFst):
    """
    Finite state transducer for classifying punctuation.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="punctuation", kind="classify", deterministic=deterministic)
        self.fst = EnPunctuationFst(deterministic=deterministic).fst
