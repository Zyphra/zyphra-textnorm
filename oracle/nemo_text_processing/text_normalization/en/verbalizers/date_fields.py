"""Structural day-month-year verbalizer for already localized date fields.

The classifier supplies native day, month and year words (including case endings).
Keeping them separate lets Normalizer reorder ISO input without losing the year.
"""
import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_NOT_QUOTE,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    insert_space,
)


class DateFieldsFst(GraphFst):
    def __init__(self, deterministic: bool = True):
        super().__init__(name="date", kind="verbalize", deterministic=deterministic)

        def field(name):
            return (
                pynutil.delete(f'{name}: "')
                + pynini.closure(NEMO_NOT_QUOTE, 1)
                + pynutil.delete('"')
            )

        graph = field("day") + delete_space + insert_space + field("month")
        graph += delete_space + insert_space + field("year")
        self.fst = (
            self.delete_tokens(graph)
            @ pynini.cdrewrite(pynini.cross("\u00a0", " "), "", "", NEMO_SIGMA)
        ).optimize()
