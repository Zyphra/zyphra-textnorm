# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0.
# Currency display names follow Unicode CLDR (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst


class MoneyFst(GraphFst):
    """Productive Slovak amounts, minor units, scales, rates and currency ranges."""

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="money", kind="classify", deterministic=deterministic)
        gap = pynini.closure(pynutil.delete(" "))
        separator = pynutil.delete(pynini.union(",", "."))
        grouped = (
            (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2)
            + pynini.closure(pynutil.delete(pynini.union(" ", "\u00a0", "\u202f", ".", ",")) + NEMO_DIGIT ** 3, 1)
        ) @ cardinal.all_positive
        number = (cardinal.all_positive | pynutil.add_weight(grouped, -0.02)).optimize()
        others = pynini.difference(pynini.project(number, "input"), pynini.union("1", "2", "3", "4")) @ number

        def agreement(one, few, many, gender="m"):
            one_word = {"m": "jeden", "f": "jedna", "n": "jedno"}[gender]
            two_word = "dva" if gender == "m" else "dve"
            return (
                pynini.cross("1", one_word + " " + one)
                | pynini.string_map([("2", two_word), ("3", "tri"), ("4", "štyri")]) + pynutil.insert(" " + few)
                | others + pynutil.insert(" " + many)
            ).optimize()

        fractional_digits = cardinal.zero | cardinal.digit
        digit_run = fractional_digits + pynini.closure(pynutil.insert(" ") + fractional_digits)
        decimal = number + pynini.cross(pynini.union(",", "."), " čiarka ") + digit_run
        minor_digits = (NEMO_DIGIT + pynutil.insert("0") | NEMO_DIGIT ** 2)
        trim_zero = pynini.closure(pynutil.delete("0")) + (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT)
        minor_digits = minor_digits @ trim_zero
        scales = [
            (['k', 'K', 'tis.'], 'tisíc', 'tisíc', 'tisíc', 'tisíca', 'm'),
            (['m', 'M', 'mil.', 'mil', 'mln', 'млн'], 'milión', 'milióny', 'miliónov', 'milióna', 'm'),
            (['b', 'B', 'mld.', 'mld', 'млрд'], 'miliarda', 'miliardy', 'miliárd', 'miliardy', 'f'),
            (['t', 'T', 'bil.'], 'bilión', 'bilióny', 'biliónov', 'bilióna', 'm'),
        ]
        currencies = [
            (['€', 'EUR', 'eur', 'euro'], 'euro', 'eurá', 'eur', 'eura', 'n', ('cent', 'centy', 'centov', 'm'), ['c', 'ct', 'cent', 'centy', 'centov']),
            (['$', 'USD', 'US$'], 'dolár', 'doláre', 'dolárov', 'dolára', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct', 'cent', 'centy', 'centov']),
            (['£', 'GBP'], 'libra', 'libry', 'libier', 'libry', 'f', ('penny', 'pence', 'pencí', 'f'), ['p', 'pence', 'penny']),
            (['¥', 'JPY'], 'jen', 'jeny', 'jenov', 'jenu', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['₽', 'RUB'], 'ruský rubeľ', 'ruské ruble', 'ruských rubľov', 'ruského rubľa', 'm', ('kopejka', 'kopejky', 'kopejok', 'f'), ['коп.', 'коп', 'kop.', 'kop']),
            (['руб.', 'руб', 'rub.', 'rub'], 'rubeľ', 'ruble', 'rubľov', 'rubľa', 'm', ('kopejka', 'kopejky', 'kopejok', 'f'), ['коп.', 'коп', 'kop.', 'kop']),
            (['CZK', 'Kč'], 'česká koruna', 'české koruny', 'českých korún', 'českej koruny', 'f', ('halier', 'haliere', 'halierov', 'm'), ['h', 'hal.', 'hal']),
            (['PLN', 'zł'], 'poľský zlotý', 'poľské zloté', 'poľských zlotých', 'poľského zlotého', 'm', ('cent', 'centy', 'centov', 'm'), ['gr', 'gr.']),
            (['CHF'], 'švajčiarsky frank', 'švajčiarske franky', 'švajčiarskych frankov', 'švajčiarskeho franku', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['CAD', 'CA$'], 'kanadský dolár', 'kanadské doláre', 'kanadských dolárov', 'kanadského dolára', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['AUD', 'A$'], 'austrálsky dolár', 'austrálske doláre', 'austrálskych dolárov', 'austrálskeho dolára', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['BRL', 'R$'], 'brazílsky real', 'brazílske realy', 'brazílskych realov', 'brazílskeho realu', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['MXN', 'MX$'], 'mexické peso', 'mexické pesos', 'mexických pesos', 'mexického pesa', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['KRW', '₩'], 'juhokórejský won', 'juhokórejské wony', 'juhokórejských wonov', 'juhokórejského wonu', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['ILS', '₪'], 'izraelský šekel', 'izraelské šekely', 'izraelských šekelov', 'izraelského šekela', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['UAH', '₴'], 'ukrajinská hrivna', 'ukrajinské hrivny', 'ukrajinských hrivien', 'ukrajinskej hrivny', 'f', ('cent', 'centy', 'centov', 'm'), ['коп.', 'коп']),
            (['VND', '₫'], 'vietnamský dong', 'vietnamské dongy', 'vietnamských dongov', 'vietnamského dongu', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['BDT', '৳'], 'bangladéšska taka', 'bangladéšske taky', 'bangladéšskych ták', 'bangladéšskej taky', 'f', ('cent', 'centy', 'centov', 'm'), ['p', 'poisha']),
            (['NGN', '₦'], 'nigérijská naira', 'nigérijské nairy', 'nigérijských nair', 'nigérijskej nairy', 'f', ('kobo', 'kobo', 'kobo', 'n'), ['k']),
            (['PHP', '₱'], 'filipínske peso', 'filipínske pesos', 'filipínskych pesos', 'filipínskeho pesa', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
            (['THB', '฿'], 'thajský baht', 'thajské bahty', 'thajských bahtov', 'thajského bahtu', 'm', ('satang', 'satangy', 'satangov', 'm'), ['satang']),
            (['AMD', '֏'], 'arménsky dram', 'arménske dramy', 'arménskych dramov', 'arménskeho dramu', 'm', ('luma', 'lumy', 'lum', 'f'), ['luma']),
            (['TRY', '₺'], 'turecká líra', 'turecké líry', 'tureckých lír', 'tureckej líry', 'f', ('kuruš', 'kuruše', 'kurušov', 'm'), ['kr']),
            (['INR', '₹', 'Rs.', 'Rs'], 'indická rupia', 'indické rupie', 'indických rupií', 'indickej rupie', 'f', ('paisa', 'paisy', 'páis', 'f'), ['p', 'paise']),
            (['¢'], 'cent', 'centy', 'centov', 'centa', 'm', ('cent', 'centy', 'centov', 'm'), ['c', 'ct']),
        ]
        amount_graphs = []
        for symbols, one, few, many, fractional, gender, minor, minor_symbols in currencies:
            symbol = pynutil.delete(pynini.union(*symbols))
            minor_sym = pynutil.delete(pynini.union(*minor_symbols))
            major = agreement(one, few, many, gender)
            minor_amount = minor_digits @ agreement(*minor)
            combined = major + separator + pynutil.insert(" ") + minor_amount
            zero_minor = major + separator + pynutil.delete(pynini.union("0", "00"))
            minor_only = pynutil.delete("0") + separator + minor_amount
            precise = (number + separator + pynutil.insert(" čiarka ") + (NEMO_DIGIT ** (3, 12) @ digit_run)
                       + pynutil.insert(" " + fractional))
            spoken = major | combined | zero_minor | pynutil.add_weight(minor_only, -0.01) | precise
            for markers, scale_one, scale_few, scale_many, scale_fractional, scale_gender in scales:
                marker = gap + pynutil.delete(pynini.union(*markers))
                whole_scale = agreement(scale_one, scale_few, scale_many, scale_gender) + marker
                decimal_scale = decimal + marker + pynutil.insert(" " + scale_fractional)
                scaled = (whole_scale | decimal_scale) + pynutil.insert(" " + many)
                spoken |= scaled
            amount_graphs.extend([symbol + gap + spoken, spoken + gap + symbol])
            split_compound = (
                (major + gap + symbol | symbol + gap + major)
                + pynini.accep(" ")
                + (minor_amount + gap + minor_sym | minor_sym + gap + minor_amount)
            )
            amount_graphs.append(split_compound)

        amount = pynini.union(*amount_graphs).optimize()
        dash = gap + pynini.cross(pynini.union("-", "–", "—"), " až ") + gap
        ranges = amount + dash + amount | number + dash + amount
        per_unit = gap + pynini.string_map([
            ('/h', ' za hodinu'), ('/hr', ' za hodinu'), ('/kg', ' za kilogram'),
            ('/day', ' za deň'), ('/month', ' za mesiac'), ('/year', ' za rok'),
        ])
        sign = pynini.closure(pynini.cross(pynini.union("-", "−"), "mínus "), 0, 1)
        self.fst = (sign + (amount | ranges) + pynini.closure(per_unit, 0, 1)).optimize()
