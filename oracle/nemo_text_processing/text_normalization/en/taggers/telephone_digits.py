"""Locale-neutral international phone shape; callers supply all spoken words."""
import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    convert_space,
)


def international_telephone(digit: pynini.Fst, plus: str) -> pynini.Fst:
    """Read +country numbers with 7–15 digits, retaining every digit.

    Separators are silent; neither English digit names nor English sign words are
    embedded here. Local phone formats remain the locale grammar's responsibility.
    """
    separators = pynini.closure(pynutil.delete(pynini.union(" ", "-", ".", "(", ")")))
    source_separators = pynini.closure(pynini.union(" ", "-", ".", "(", ")"))
    shape = "+" + source_separators + NEMO_DIGIT
    shape += (source_separators + NEMO_DIGIT) ** (6, 14) + source_separators
    reader = pynini.cross("+", plus + " ") + separators + digit
    reader += pynini.closure(separators + pynutil.insert(" ") + digit, 6, 14) + separators
    return (shape @ reader).optimize()


def international_telephone_token(digit: pynini.Fst, plus: str) -> pynini.Fst:
    """Wrap an international number as a spoken-name token."""
    return (
        pynutil.insert('name: "')
        + convert_space(international_telephone(digit, plus))
        + pynutil.insert('"')
    ).optimize()
