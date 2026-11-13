# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    INPUT_CASED,
    INPUT_LOWER_CASED,
    NEMO_ALNUM,
    NEMO_ALPHA,
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_LOWER,
    NEMO_NOT_QUOTE,
    NEMO_NOT_SPACE,
    NEMO_SIGMA,
    NEMO_SPACE,
    NEMO_UPPER,
    NEMO_WHITE_SPACE,
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    generator_main,
    insert_space,
)

NEMO_MINUS = pynini.union("-", "\u2212").optimize()


def wrap_token(graph: pynini.FstLike) -> pynini.Fst:
    """Wraps spoken Dutch string into tokens { name: "..." }."""
    return (pynutil.insert('tokens { name: "') + convert_space(graph) + pynutil.insert('" }')).optimize()


def wrap_name(graph: pynini.FstLike) -> pynini.Fst:
    """Wraps spoken Dutch string into name: "..."."""
    return (pynutil.insert('name: "') + convert_space(graph) + pynutil.insert('"')).optimize()
