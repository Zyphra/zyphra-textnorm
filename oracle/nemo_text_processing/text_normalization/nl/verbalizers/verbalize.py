# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst
from nemo_text_processing.text_normalization.nl.verbalizers.word import WordFst


class VerbalizeFst(GraphFst):
    """
    Finite state transducer for verbalizing Dutch tokens.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="verbalize", kind="verbalize", deterministic=deterministic)
        self.fst = WordFst(deterministic=deterministic).fst
