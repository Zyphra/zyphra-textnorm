# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.sk.taggers.decimal import DecimalFst


class MeasureFst(GraphFst):
    """Productive Slovak unit agreement, decimal measures, ranges and modifiers."""

    def __init__(self, cardinal: CardinalFst, decimal: DecimalFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)
        gap = pynini.closure(pynutil.delete(" "))
        number = cardinal.all_positive
        other = pynini.difference(pynini.project(number, "input"), pynini.union("1", "2", "3", "4")) @ number
        units = [
            (['kg'], 'kilogram', 'kilogramy', 'kilogramov', 'kilogramu', 'm'),
            (['g'], 'gram', 'gramy', 'gramov', 'gramu', 'm'),
            (['mg'], 'miligram', 'miligramy', 'miligramov', 'miligramu', 'm'),
            (['µg', 'μg'], 'mikrogram', 'mikrogramy', 'mikrogramov', 'mikrogramu', 'm'),
            (['t'], 'tona', 'tony', 'ton', 'tony', 'f'),
            (['m'], 'meter', 'metre', 'metrov', 'metra', 'm'),
            (['km'], 'kilometer', 'kilometre', 'kilometrov', 'kilometra', 'm'),
            (['cm'], 'centimeter', 'centimetre', 'centimetrov', 'centimetra', 'm'),
            (['mm'], 'milimeter', 'milimetre', 'milimetrov', 'milimetra', 'm'),
            (['µm', 'μm'], 'mikrometer', 'mikrometre', 'mikrometrov', 'mikrometra', 'm'),
            (['l', 'L'], 'liter', 'litre', 'litrov', 'litra', 'm'),
            (['ml', 'mL'], 'mililiter', 'mililitre', 'mililitrov', 'mililitra', 'm'),
            (['m²', 'm2'], 'štvorcový meter', 'štvorcové metre', 'štvorcových metrov', 'štvorcového metra', 'm'),
            (['m³', 'm3'], 'kubický meter', 'kubické metre', 'kubických metrov', 'kubického metra', 'm'),
            (['km/h', 'km/hr'], 'kilometer za hodinu', 'kilometre za hodinu', 'kilometrov za hodinu', 'kilometra za hodinu', 'm'),
            (['m/s'], 'meter za sekundu', 'metre za sekundu', 'metrov za sekundu', 'metra za sekundu', 'm'),
            (['°C', '℃'], 'stupeň Celzia', 'stupne Celzia', 'stupňov Celzia', 'stupňa Celzia', 'm'),
            (['°F', '℉'], 'stupeň Fahrenheita', 'stupne Fahrenheita', 'stupňov Fahrenheita', 'stupňa Fahrenheita', 'm'),
            (['°'], 'stupeň', 'stupne', 'stupňov', 'stupňa', 'm'),
            (['%'], 'percento', 'percentá', 'percent', 'percenta', 'n'),
            (['‰'], 'promile', 'promile', 'promile', 'promile', 'n'),
            (['GB'], 'gigabajt', 'gigabajty', 'gigabajtov', 'gigabajtu', 'm'),
            (['MB'], 'megabajt', 'megabajty', 'megabajtov', 'megabajtu', 'm'),
            (['TB'], 'terabajt', 'terabajty', 'terabajtov', 'terabajtu', 'm'),
            (['Hz'], 'hertz', 'hertze', 'hertzov', 'hertza', 'm'),
            (['GHz'], 'gigahertz', 'gigahertze', 'gigahertzov', 'gigahertza', 'm'),
            (['Gbps'], 'gigabit za sekundu', 'gigabity za sekundu', 'gigabitov za sekundu', 'gigabitu za sekundu', 'm'),
            (['Mbps'], 'megabit za sekundu', 'megabity za sekundu', 'megabitov za sekundu', 'megabitu za sekundu', 'm'),
            (['mAh'], 'miliampérhodina', 'miliampérhodiny', 'miliampérhodín', 'miliampérhodiny', 'f'),
            (['kWh'], 'kilowatthodina', 'kilowatthodiny', 'kilowatthodín', 'kilowatthodiny', 'f'),
            (['hPa'], 'hektopascal', 'hektopascaly', 'hektopascalov', 'hektopascalu', 'm'),
            (['kcal'], 'kilokalória', 'kilokalórie', 'kilokalórií', 'kilokalórie', 'f'),
            (['dB'], 'decibel', 'decibely', 'decibelov', 'decibelu', 'm'),
            (['Ω', 'Ω'], 'ohm', 'ohmy', 'ohmov', 'ohmu', 'm'),
        ]
        graphs = []
        gen_prep = pynini.cross(pynini.union("okolo", "Okolo"), "okolo") + (pynini.accep(" ") | pynutil.insert(" "))
        gen_graphs = []
        for symbols, one, few, many, fractional, gender in units:
            one_word = {'m': 'jeden', 'f': 'jedna', 'n': 'jedno'}[gender]
            one_gen = {'m': 'jedného', 'f': 'jednej', 'n': 'jedného'}[gender]
            two_word = 'dva' if gender == 'm' else 'dve'
            symbol = gap + pynutil.delete(pynini.union(*symbols))
            integer = (
                pynini.cross('1', one_word + ' ' + one)
                | pynini.string_map([('2', two_word), ('3', 'tri'), ('4', 'štyri')]) + pynutil.insert(' ' + few)
                | other + pynutil.insert(' ' + many)
            ) + symbol
            fractional_amount = decimal.fst + symbol + pynutil.insert(' ' + fractional)
            graphs.append(integer | fractional_amount)
            gen_integer = (
                pynini.cross('1', one_gen + ' ' + fractional)
                | pynini.string_map([('2', two_word), ('3', 'tri'), ('4', 'štyri')]) + pynutil.insert(' ' + few)
                | other + pynutil.insert(' ' + many)
            ) + symbol
            gen_graphs.append(gen_integer | fractional_amount)
        core = pynini.union(*graphs).optimize()
        gen_measure = (gen_prep + pynini.union(*gen_graphs)).optimize()
        endpoint = number | decimal.fst
        ranges = endpoint + gap + pynini.cross(pynini.union('-', '–', '—'), ' až ') + gap + core
        prefix = pynini.closure(
            (pynini.cross(pynini.union('-', '−'), 'mínus ') | pynini.cross('~', 'približne ') | pynini.cross('±', 'plus-mínus ')) + gap,
            0, 1,
        )
        isolated = pynini.string_map([('°', 'stupeň'), ('%', 'percento'), ('‰', 'promile')])
        self.fst = (prefix + (core | ranges) | isolated | gen_measure).optimize()
