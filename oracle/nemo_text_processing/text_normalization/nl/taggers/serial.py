"""Dutch alphanumeric identifiers, software versions and variable powers."""
import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name


class SerialFst(GraphFst):
    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="serial", kind="classify", deterministic=deterministic)
        digits = cardinal.digit + pynini.closure(insert_space + cardinal.digit)
        number = cardinal.raw_cardinal | pynutil.add_weight(digits, 0.1)
        version = number + pynini.closure(pynini.cross(".", " punt ") + number)
        alpha = pynini.closure(NEMO_ALPHA, 1)
        segment = (
            alpha | version
            | alpha + insert_space + version
            | version + insert_space + alpha
            | alpha + insert_space + version + insert_space + alpha
            | version + insert_space + alpha + insert_space + version
        )
        delimiter = pynini.cross(pynini.union("-", "/", ":", "_"), " ")
        body = segment + pynini.closure(delimiter + segment)
        serial = (NEMO_SIGMA + NEMO_DIGIT + NEMO_SIGMA) @ body
        exponent = (
            pynini.cross(pynini.union("^2", "²"), " kwadraat")
            | pynini.cross(pynini.union("^3", "³"), " tot de derde macht")
            | pynini.cross("^", " tot de macht ") + number
        )
        self.fst = wrap_name((serial | NEMO_ALPHA + exponent).optimize())
