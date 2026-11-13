# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst
from nemo_text_processing.text_normalization.uk.verbalizers.word import WordFst


class VerbalizeFst(GraphFst):
    """
    Composes verbalizer grammars.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="verbalize", kind="verbalize", deterministic=deterministic)
        self.fst = WordFst(deterministic=deterministic).fst
