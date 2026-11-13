"""Czech local and international telephone numbers, spoken digit by digit."""
import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst, NEMO_DIGIT, convert_space,
)
from nemo_text_processing.text_normalization.en.taggers.telephone_digits import international_telephone


class TelephoneFst(GraphFst):
    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="telephone", kind="classify", deterministic=deterministic)
        digit = cardinal.digits
        separators = pynini.closure(pynutil.delete(pynini.union(" ", "-", ".")))
        local = digit + pynini.closure(separators + pynutil.insert(" ") + digit, 8, 8)
        digits = NEMO_DIGIT + pynini.closure(
            pynini.closure(pynini.union(" ", "-", ".")) + NEMO_DIGIT, 8, 8
        )
        local = digits @ local
        graph = international_telephone(digit, "plus") | local
        self.fst = graph.optimize()
