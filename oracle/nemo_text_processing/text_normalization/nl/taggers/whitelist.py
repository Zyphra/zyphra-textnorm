# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    GraphFst,
)
from nemo_text_processing.text_normalization.nl.graph_utils import wrap_name


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Dutch abbreviations, titles, and common symbols.
    """

    def __init__(self, input_case: str = "cased", deterministic: bool = True):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        abbreviations = [
            ("Dr.", "dokter"),
            ("dr.", "dokter"),
            ("Dr", "dokter"),
            ("dr", "dokter"),
            ("Dhr.", "de heer"),
            ("dhr.", "de heer"),
            ("Dhr", "de heer"),
            ("dhr", "de heer"),
            ("Mevr.", "mevrouw"),
            ("mevr.", "mevrouw"),
            ("Mevr", "mevrouw"),
            ("mevr", "mevrouw"),
            ("Prof.", "professor"),
            ("prof.", "professor"),
            ("Prof", "professor"),
            ("prof", "professor"),
            ("Ir.", "ingenieur"),
            ("ir.", "ingenieur"),
            ("Drs.", "doctorandus"),
            ("drs.", "doctorandus"),
            ("Nr.", "nummer"),
            ("nr.", "nummer"),
            ("No.", "nummer"),
            ("no.", "nummer"),
            ("blz.", "bladzijde"),
            ("p.", "pagina"),
            ("art.", "artikel"),
            ("par.", "paragraaf"),
            ("fig.", "figuur"),
            ("tab.", "tabel"),
            ("bijv.", "bijvoorbeeld"),
            ("bv.", "bijvoorbeeld"),
            ("d.w.z.", "dat wil zeggen"),
            ("o.a.", "onder andere"),
            ("m.b.t.", "met betrekking tot"),
            ("t.a.v.", "ter attentie van"),
            ("z.g.a.n.", "zo goed als nieuw"),
            ("z.s.m.", "zo snel mogelijk"),
            ("a.u.b.", "alstublieft"),
            ("etc.", "enzovoort"),
            ("enz.", "enzovoort"),
            ("i.v.m.", "in verband met"),
            ("t.o.v.", "ten opzichte van"),
            ("m.a.w.", "met andere woorden"),
            ("n.v.t.", "niet van toepassing"),
            ("ca.", "circa"),
            ("nl.", "namelijk"),
            ("resp.", "respectievelijk"),
            ("&", "en"),
            ("©", "copyright"),
            ("§", "paragraaf"),
            ("±", "plusminus"),
            ("~", "ongeveer"),
            ("CO2", "C O twee"),
            ("5G", "vijf g"),
            ("A4", "A vier"),
        ]

        whitelist_map = pynini.string_map(abbreviations).optimize()

        self.spoken_whitelist = whitelist_map
        self.fst = wrap_name(self.spoken_whitelist)
