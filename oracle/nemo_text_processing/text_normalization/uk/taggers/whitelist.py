# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.uk.taggers.cardinal import CardinalFst


WHITELIST_ITEMS = [
    ("і т. д.", "і так далі"),
    ("і т.д.", "і так далі"),
    ("і т. п.", "і тому подібне"),
    ("і т.п.", "і тому подібне"),
    ("тощо", "тощо"),
    ("напр.", "наприклад"),
    ("див.", "дивіться"),
    ("вул.", "вулиця"),
    ("буд.", "будинок"),
    ("кв.", "квартира"),
    ("д-р", "доктор"),
    ("д-р.", "доктор"),
    ("проф.", "професор"),
    ("проф", "професор"),
    ("пан", "пан"),
    ("пані", "пані"),
    ("г-н", "пан"),
    ("гр-н", "громадянин"),
]


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Ukrainian abbreviations and special symbols:
        № 5 -> номер п'ять
        д-р Петров -> доктор Петров
        A & B -> ей і бі
        © 2024 -> копірайт дві тисячі двадцять чотири
        § 12 -> параграф дванадцять
        ~50 -> приблизно п'ятдесят
        ±5 -> плюс-мінус п'ять
        25¢ -> двадцять п'ять центів
        і т. д. -> і так далі
    """

    def __init__(self, cardinal: CardinalFst = None, input_case: str = "cased"):
        super().__init__(name="whitelist", kind="classify")
        cardinal = cardinal or CardinalFst()

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        # 1. Standard abbreviations
        abbrevs = pynini.string_map(WHITELIST_ITEMS)

        # Titles before proper names: "д-р Петров" -> "доктор Петров", "г-н Иванов" -> "господин Иванов"
        title_dr = (pynini.cross("д-р", "доктор") | pynini.cross("д-р.", "доктор"))
        title_mr = (pynini.cross("г-н", "господин") | pynini.cross("пан", "пан"))

        # 2. Number sign: "№ 5" -> "номер п'ять", "№5" -> "номер п'ять"
        num_sign = (
            pynini.cross("№", "номер")
            + opt_space
            + pynutil.insert(" ")
            + (pynini.closure(NEMO_DIGIT, 1) @ cardinal.graph)
        )

        # 3. Section sign: "§ 12" -> "параграф дванадцять"
        section_sign = (
            pynini.cross("§", "параграф")
            + opt_space
            + pynutil.insert(" ")
            + (pynini.closure(NEMO_DIGIT, 1) @ cardinal.graph)
        )

        # 4. Copyright symbol: "© 2024" -> "копірайт дві тисячі двадцять чотири"
        copyright_sym = (
            pynini.cross("©", "копірайт")
            + opt_space
            + pynutil.insert(" ")
            + (pynini.closure(NEMO_DIGIT, 1) @ cardinal.graph)
        )

        # 5. Ampersand: "A & B" -> "ей і бі", "A & C" -> "ей і сі", "B & D" -> "бі і ді"
        from nemo_text_processing.text_normalization.uk.alphabet import TO_CYRILLIC
        ampersand_letters = (
            TO_CYRILLIC
            + opt_space
            + pynini.cross("&", " і")
            + opt_space
            + pynutil.insert(" ")
            + TO_CYRILLIC
        )
        ampersand_general = pynini.cross("&", "і")

        # 6. Approximate with number alone: "~50" -> "приблизно п'ятдесят"
        approx_num = (
            pynini.cross("~", "приблизно ")
            + opt_space
            + (pynini.closure(NEMO_DIGIT, 1) @ cardinal.graph)
        )

        # 7. Plus-minus with number alone: "±5" -> "плюс-мінус п'ять"
        plus_minus_num = (
            pynini.cross("±", "плюс-мінус ")
            + opt_space
            + (pynini.closure(NEMO_DIGIT, 1) @ cardinal.graph)
        )

        # 8. Cents alone: "25¢" -> "двадцять п'ять центів"
        cents_sym = (
            (pynini.closure(NEMO_DIGIT, 1) @ cardinal.graph)
            + opt_space
            + pynutil.delete("¢")
            + pynutil.insert(" центів")
        )

        all_whitelist = (
            pynutil.add_weight(ampersand_letters, 0.01)
            | pynutil.add_weight(num_sign, 0.02)
            | pynutil.add_weight(section_sign, 0.02)
            | pynutil.add_weight(copyright_sym, 0.02)
            | pynutil.add_weight(approx_num, 0.03)
            | pynutil.add_weight(plus_minus_num, 0.03)
            | pynutil.add_weight(cents_sym, 0.03)
            | pynutil.add_weight(title_dr, 0.04)
            | pynutil.add_weight(title_mr, 0.04)
            | pynutil.add_weight(abbrevs, 0.05)
            | pynutil.add_weight(ampersand_general, 0.1)
        )

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_whitelist)
            + pynutil.insert('"')
        ).optimize()
