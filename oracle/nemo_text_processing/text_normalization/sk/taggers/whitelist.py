# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst, NEMO_ALPHA


class WhiteListFst(GraphFst):
    """Slovak abbreviations and productive symbol, identifier and power readings."""

    def __init__(self, cardinal: GraphFst, input_file: str = None, deterministic: bool = True):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)
        abbreviations = pynini.string_map([
            ("&", "a"), ("©", "autorské práva"), ("§", "paragraf"), ("№", "číslo"),
            ("č.", "číslo"), ("p.", "pán"), ("pani", "pani"),
            ("Dr.", "doktor"), ("Dr", "doktor"), ("dr.", "doktor"), ("dr", "doktor"),
            ("Doc.", "docent"), ("doc.", "docent"), ("Prof.", "profesor"), ("prof.", "profesor"),
            ("Ing.", "inžinier"), ("Mgr.", "magister"), ("Bc.", "bakalár"),
            ("MUDr.", "doktor"), ("JUDr.", "doktor"), ("PhDr.", "doktor"), ("PhD.", "pé há dé"),
            ("napr.", "napríklad"), ("atď.", "a tak ďalej"), ("resp.", "respektíve"),
            ("t. j.", "to jest"), ("t.j.", "to jest"), ("tzv.", "takzvaný"),
            ("str.", "strana"), ("v.", "verzia"),
        ])
        if input_file is not None:
            abbreviations |= pynini.string_file(input_file)
        gap = pynini.closure(pynutil.delete(" "))
        number = cardinal.all_positive
        number_prefix = pynini.string_map([
            ("©", "autorské práva"), ("§", "paragraf"), ("№", "číslo"),
            ("č.", "číslo"), ("str.", "strana"),
        ]) + gap + pynutil.insert(" ") + number
        native_letters = "áäčďéíĺľňóôŕšťúýž"
        letter = NEMO_ALPHA | pynini.union(*(native_letters + native_letters.upper()))
        letters = pynini.closure(letter, 1)
        digit = cardinal.digit | cardinal.zero
        digits = digit + pynini.closure(pynutil.insert(" ") + digit)
        identifier = (
            letters + pynutil.insert(" ") + digits
            + pynini.closure(pynutil.insert(" ") + letters, 0, 1)
            | number + pynutil.insert(" ") + pynini.union("G", "K")
        )
        hyphenated = letters + pynini.cross("-", " ") + number + pynini.closure(pynini.cross("-", " ") + letters, 0, 1)
        exponent_other = pynini.difference(pynini.project(number, "input"), pynini.union("2", "3")) @ number
        exponent = (
            pynini.cross(pynini.union("^2", "²"), " na druhú")
            | pynini.cross(pynini.union("^3", "³"), " na tretiu")
            | pynini.cross("^", " na ") + exponent_other
        )
        power = (letters | number) + exponent
        self.fst = (abbreviations | number_prefix | identifier | hyphenated | power).optimize()
