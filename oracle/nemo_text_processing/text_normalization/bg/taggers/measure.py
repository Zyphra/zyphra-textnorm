# Copyright (c) 2026 Zyphra, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.bg.graph_utils import (
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.bg.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.bg.taggers.decimal import DecimalFst


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Bulgarian measurement units and percentages.
    Includes complete SI, computing, electrical, and scientific units,
    temperatures, rates, percentages, permille, and ranges.
    e.g. 50kg -> tokens { name: "петдесет килограма" }
         100m -> tokens { name: "сто метра" }
         1.5km -> tokens { name: "едно цяло и пет километра" }
         37°C -> tokens { name: "тридесет и седем градуса по Целзий" }
         -15°C -> tokens { name: "минус петнадесет градуса по Целзий" }
         120km/h -> tokens { name: "сто и двадесет километра в час" }
         10 Gbps -> tokens { name: "десет гигабита в секунда" }
         5000 mAh -> tokens { name: "пет хиляди милиамперчаса" }
         100 Ω -> tokens { name: "сто ома" }
         100 m² -> tokens { name: "сто квадратни метра" }
         10% -> tokens { name: "десет процента" }
         12.5% -> tokens { name: "дванадесет цяло и пет процента" }
         5-10 kg -> tokens { name: "пет до десет килограма" }
         ~10 km -> tokens { name: "около десет километра" }
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        decimal: DecimalFst = None,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)

        card_m = cardinal.cardinal_m
        card_f = cardinal.cardinal_f
        card_n = cardinal.cardinal_n
        dec_val = decimal.all_decimals

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # -------------------------------------------------------------
        # 1. UNITS MAPPING (MASCULINE COUNTING NOUNS)
        # -------------------------------------------------------------
        units_one_m = pynini.string_map([
            ("km", "километър"), ("км", "километър"),
            ("m", "метър"), ("м", "метър"),
            ("cm", "сантиметър"), ("см", "сантиметър"),
            ("mm", "милиметър"), ("мм", "милиметър"),
            ("µm", "микрометър"), ("μm", "микрометър"),
            ("kg", "килограм"), ("кг", "килограм"),
            ("g", "грам"), ("г", "грам"), ("гр", "грам"),
            ("mg", "милиграм"), ("мг", "милиграм"),
            ("µg", "микрограма"), ("μg", "микрограма"),
            ("l", "литър"), ("л", "литър"),
            ("ml", "милилитър"), ("мл", "милилитър"),
            ("km/h", "километър в час"), ("км/ч", "километър в час"),
            ("m/s", "метър в секунда"), ("м/с", "метър в секунда"),
            ("m²", "квадратен метър"), ("м²", "квадратен метър"),
            ("km²", "квадратен километър"), ("км²", "квадратен километър"),
            ("m³", "кубичен метър"), ("м³", "кубичен метър"),
            ("cm³", "кубичен сантиметър"),
            ("GB", "гигабайт"), ("ГБ", "гигабайт"),
            ("MB", "мегабайт"), ("МБ", "мегабайт"),
            ("KB", "килобайт"), ("kB", "килобайт"), ("КБ", "килобайт"),
            ("TB", "терабайт"), ("ТБ", "терабайт"),
            ("B", "байт"),
            ("Gbps", "гигабит в секунда"),
            ("Mbps", "мегабит в секунда"),
            ("kbps", "килобит в секунда"),
            ("GHz", "гигахерц"), ("ГХц", "гигахерц"),
            ("MHz", "мегахерц"), ("МХц", "мегахерц"),
            ("kHz", "килохерц"), ("кХц", "килохерц"),
            ("Hz", "херц"), ("Хц", "херц"),
            ("kWh", "киловатчас"),
            ("mAh", "милиамперчас"),
            ("W", "ват"), ("Вт", "ват"),
            ("kW", "киловат"), ("кВт", "киловат"),
            ("V", "волт"), ("В", "волт"),
            ("A", "ампер"), ("А", "ампер"),
            ("Ω", "ом"), ("Ω", "ом"),
            ("hPa", "хектопаскал"),
            ("Pa", "паскал"),
            ("bar", "бар"),
            ("dB", "децибел"),
            ("°C", "градус по Целзий"),
            ("°F", "градус по Фаренхайт"),
            ("°", "градус")
        ])

        units_plural_m = pynini.string_map([
            ("km", "километра"), ("км", "километра"),
            ("m", "метра"), ("м", "метра"),
            ("cm", "сантиметра"), ("см", "сантиметра"),
            ("mm", "милиметра"), ("мм", "милиметра"),
            ("µm", "микрометра"), ("μm", "микрометра"),
            ("kg", "килограма"), ("кг", "килограма"),
            ("g", "грама"), ("г", "грама"), ("гр", "грама"),
            ("mg", "милиграма"), ("мг", "милиграма"),
            ("µg", "микрограма"), ("μg", "микрограма"),
            ("l", "литра"), ("л", "литра"),
            ("ml", "милилитра"), ("мл", "милилитра"),
            ("km/h", "километра в час"), ("км/ч", "километра в час"),
            ("m/s", "метра в секунда"), ("м/с", "метра в секунда"),
            ("m²", "квадратни метра"), ("м²", "квадратни метра"),
            ("km²", "квадратни километра"), ("км²", "квадратни километра"),
            ("m³", "кубични метра"), ("м³", "кубични метра"),
            ("cm³", "кубични сантиметра"),
            ("GB", "гигабайта"), ("ГБ", "гигабайта"),
            ("MB", "мегабайта"), ("МБ", "мегабайта"),
            ("KB", "килобайта"), ("kB", "килобайта"), ("КБ", "килобайта"),
            ("TB", "терабайта"), ("ТБ", "терабайта"),
            ("B", "байта"),
            ("Gbps", "гигабита в секунда"),
            ("Mbps", "мегабита в секунда"),
            ("kbps", "килобита в секунда"),
            ("GHz", "гигахерца"), ("ГХц", "гигахерца"),
            ("MHz", "мегахерца"), ("МХц", "мегахерца"),
            ("kHz", "килохерца"), ("кХц", "килохерца"),
            ("Hz", "херца"), ("Хц", "херца"),
            ("kWh", "киловатчаса"),
            ("mAh", "милиамперчаса"),
            ("W", "вата"), ("Вт", "вата"),
            ("kW", "киловата"), ("кВт", "киловата"),
            ("V", "волта"), ("В", "волта"),
            ("A", "ампера"), ("А", "ампера"),
            ("Ω", "ома"), ("Ω", "ома"),
            ("hPa", "хектопаскала"),
            ("Pa", "паскала"),
            ("bar", "бара"),
            ("dB", "децибела"),
            ("°C", "градуса по Целзий"),
            ("°F", "градуса по Фаренхайт"),
            ("°", "градуса")
        ])

        # Feminine units: kcal, cal
        units_one_f = pynini.string_map([
            ("kcal", "килокалория"), ("ккал", "килокалория"),
            ("cal", "калория")
        ])
        units_plural_f = pynini.string_map([
            ("kcal", "килокалории"), ("ккал", "килокалории"),
            ("cal", "калории")
        ])

        # Combining numbers and units:
        # Masculine 1
        num_1_m = pynini.cross("1", "един") + opt_sp + pynutil.insert(" ") + units_one_m
        # Masculine 2+
        num_other_m = card_m + opt_sp + pynutil.insert(" ") + units_plural_m

        # Feminine 1
        num_1_f = pynini.cross("1", "една") + opt_sp + pynutil.insert(" ") + units_one_f
        # Feminine 2+
        num_other_f = card_f + opt_sp + pynutil.insert(" ") + units_plural_f

        # Decimals with units (e.g. 1.5km, 2.4GHz)
        dec_with_unit = dec_val + opt_sp + pynutil.insert(" ") + units_plural_m

        # Negative temperature (e.g. -15°C, −15 °C)
        neg_sign = pynini.cross(pynini.union("-", "−"), "минус ")
        neg_temp = neg_sign + (
            (card_m + opt_sp + pynutil.insert(" ") + units_plural_m)
            | (dec_val + opt_sp + pynutil.insert(" ") + units_plural_m)
        )

        all_base_measures = (
            neg_temp
            | dec_with_unit
            | num_1_m
            | num_other_m
            | num_1_f
            | num_other_f
        ).optimize()

        # -------------------------------------------------------------
        # 2. PERCENTAGES & PERMILLE
        # -------------------------------------------------------------
        pct_sym = pynutil.delete("%")
        pct_1 = pynini.cross("1", "един процент") + opt_sp + pct_sym
        pct_other = card_m + opt_sp + pct_sym + pynutil.insert(" процента")
        pct_dec = dec_val + opt_sp + pct_sym + pynutil.insert(" процента")
        pct_num = pct_1 | pct_other | pct_dec

        neg_pct = neg_sign + pct_num
        pm_pct = pynini.cross("±", "плюс-минус ") + pct_num

        # Quotes around percent: "100%"
        quoted_pct = (
            pynini.accep('"') + pct_num + pynini.accep('"')
        )

        # Permille: 5‰ -> пет промила
        permille_sym = pynutil.delete("‰")
        permille_1 = pynini.cross("1", "един промил") + opt_sp + permille_sym
        permille_other = card_m + opt_sp + permille_sym + pynutil.insert(" промила")
        permille = permille_1 | permille_other

        all_percentages = (
            pm_pct
            | neg_pct
            | quoted_pct
            | pct_num
            | permille
        ).optimize()

        # -------------------------------------------------------------
        # 3. MEASURE RANGES (5-10 kg, 10-15%)
        # -------------------------------------------------------------
        dash = pynini.cross(pynini.union("-", "–", "—"), " до ")
        measure_range = (
            card_m + opt_sp + dash + opt_sp + all_base_measures
            | card_m + opt_sp + dash + opt_sp + all_percentages
        ).optimize()

        # -------------------------------------------------------------
        # 4. APPROXIMATE MEASURE (~10 km)
        # -------------------------------------------------------------
        approx_sign = pynini.cross("~", "около ")
        approx_measure = approx_sign + all_base_measures

        all_measures = (
            pynutil.add_weight(approx_measure, 0.95)
            | pynutil.add_weight(measure_range, 0.96)
            | pynutil.add_weight(all_percentages, 1.0)
            | pynutil.add_weight(all_base_measures, 1.05)
        ).optimize()

        self.all_measures = all_measures

        graph = pynutil.insert('name: "') + convert_space(all_measures) + pynutil.insert('"')
        self.fst = graph.optimize()
