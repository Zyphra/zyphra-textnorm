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

from ..graph_utils import (
    GraphFst,
    NEMO_ALL_DIGIT,
    NORMALIZE_DIGITS,
    convert_space,
)
from .cardinal import CardinalFst
from .decimal import DecimalFst
from .fraction import FractionFst

UNITS_LIST = [
    # Length
    ("km", "କିଲୋମିଟର"),
    ("କିମି", "କିଲୋମିଟର"),
    ("m", "ମିଟର"),
    ("cm", "ସେଣ୍ଟିମିଟର"),
    ("mm", "ମିଲିମିଟର"),
    ("µm", "ମାଇକ୍ରୋମିଟର"),
    ("um", "ମାଇକ୍ରୋମିଟର"),
    ("mi", "ମାଇଲ୍"),
    ("ft", "ଫୁଟ୍"),
    ("in", "ଇଞ୍ଚ୍"),
    # Mass
    ("kg", "କିଲୋଗ୍ରାମ"),
    ("କେଜି", "କିଲୋଗ୍ରାମ"),
    ("g", "ଗ୍ରାମ"),
    ("mg", "ମିଲିଗ୍ରାମ"),
    ("µg", "ମାଇକ୍ରୋଗ୍ରାମ"),
    ("ug", "ମାଇକ୍ରୋଗ୍ରାମ"),
    ("lb", "ପାଉଣ୍ଡ୍"),
    ("oz", "ଆଉନ୍ସ"),
    # Volume
    ("l", "ଲିଟର"),
    ("L", "ଲିଟର"),
    ("ml", "ମିଲିଲିଟର"),
    ("mL", "ମିଲିଲିଟର"),
    # Speed & Rates
    ("km/h", "କିଲୋମିଟର ପ୍ରତି ଘଣ୍ଟା"),
    ("km/hr", "କିଲୋମିଟର ପ୍ରତି ଘଣ୍ଟା"),
    ("m/s", "ମିଟର ପ୍ରତି ସେକେଣ୍ଡ"),
    ("mph", "ମାଇଲ୍ ପ୍ରତି ଘଣ୍ଟା"),
    # Area & Volume powers
    ("m²", "ବର୍ଗ ମିଟର"),
    ("m^2", "ବର୍ଗ ମିଟର"),
    ("km²", "ବର୍ଗ କିଲୋମିଟର"),
    ("km^2", "ବର୍ଗ କିଲୋମିଟର"),
    ("cm²", "ବର୍ଗ ସେଣ୍ଟିମିଟର"),
    ("m³", "ଘନ ମିଟର"),
    ("m^3", "ଘନ ମିଟର"),
    # Temperature
    ("°C", "ଡିଗ୍ରୀ ସେଲସିୟସ୍"),
    ("℃", "ଡିଗ୍ରୀ ସେଲସିୟସ୍"),
    ("°F", "ଡିଗ୍ରୀ ଫାରେନହାଇଟ୍"),
    ("℉", "ଡିଗ୍ରୀ ଫାରେନହାଇଟ୍"),
    ("K", "କେଲଭିନ୍"),
    ("°", "ଡିଗ୍ରୀ"),
    # Electrical & Scientific
    ("V", "ଭୋଲ୍ଟ"),
    ("A", "ଏମ୍ପିୟର୍"),
    ("W", "ୱାଟ୍"),
    ("kW", "କିଲୋୱାଟ୍"),
    ("kWh", "କିଲୋୱାଟ୍-ଘଣ୍ଟା"),
    ("mAh", "ମିଲି-ଏମ୍ପିୟର୍ ଘଣ୍ଟା"),
    ("Ah", "ଏମ୍ପିୟର୍ ଘଣ୍ଟା"),
    ("Ω", "ଓହମ୍"),
    ("Ω", "ଓହମ୍"),
    ("Hz", "ହର୍ଟ୍ଜ୍"),
    ("kHz", "କିଲୋହର୍ଟ୍ଜ୍"),
    ("MHz", "ମେଗାହର୍ଟ୍ଜ୍"),
    ("GHz", "ଗିଗାହର୍ଟ୍ଜ୍"),
    ("B", "ବାଇଟ୍"),
    ("KB", "କିଲୋବାଇଟ୍"),
    ("MB", "ମେଗାବାଇଟ୍"),
    ("GB", "ଗିଗାବାଇଟ୍"),
    ("TB", "ଟେରାବାଇଟ୍"),
    ("bps", "ବିଟ୍ ପ୍ରତି ସେକେଣ୍ଡ"),
    ("kbps", "କିଲୋବିଟ୍ ପ୍ରତି ସେକେଣ୍ଡ"),
    ("Mbps", "ମେଗାବିଟ୍ ପ୍ରତି ସେକେଣ୍ଡ"),
    ("Gbps", "ଗିଗାବିଟ୍ ପ୍ରତି ସେକେଣ୍ଡ"),
    ("hPa", "ହେକ୍ଟୋପାସ୍କାଲ୍"),
    ("Pa", "ପାସ୍କାଲ୍"),
    ("bar", "ବାର୍"),
    ("cal", "କ୍ୟାଲୋରୀ"),
    ("kcal", "କିଲୋକ୍ୟାଲୋରୀ"),
    ("J", "ଜୁଲ୍"),
    ("kJ", "କିଲୋଜୁଲ୍"),
    ("dB", "ଡେସିବେଲ୍"),
    # Percentage & Permille
    ("%", "ପ୍ରତିଶତ"),
    ("‰", "ପ୍ରତି ହଜାର"),
]


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measurement units in Odia:
        ୫ kg or 5kg -> tokens { name: "ପାଞ୍ଚ କିଲୋଗ୍ରାମ" }
        ୨.୫ km or 2.5km -> tokens { name: "ଦୁଇ ଦଶମିକ ପାଞ୍ଚ କିଲୋମିଟର" }
        ୫୦% -> tokens { name: "ପଚାଶ ପ୍ରତିଶତ" }
        ୩୭°C -> tokens { name: "ସାଁଇତିରିଶ ଡିଗ୍ରୀ ସେଲସିୟସ୍" }
        -୧୫°C -> tokens { name: "ଋଣ ପନ୍ଦର ଡିଗ୍ରୀ ସେଲସିୟସ୍" }
        ୫-୧୦ kg -> tokens { name: "ପାଞ୍ଚ ରୁ ଦଶ କିଲୋଗ୍ରାମ" }
        ୧୦-୧୫% -> tokens { name: "ଦଶ ରୁ ପନ୍ଦର ପ୍ରତିଶତ" }
        ୧୦x୨୦ -> tokens { name: "ଦଶ ବାଇ କୋଡ଼ିଏ" }
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        decimal: DecimalFst = None,
        fraction: FractionFst = None,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
        if fraction is None:
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)

        self.cardinal = cardinal
        self.decimal = decimal
        self.fraction = fraction

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Numbers acceptable before units (cardinal, decimal, fraction, negative)
        neg_prefix = pynini.cross("-", "ଋଣ ") | pynini.cross("−", "ଋଣ ")
        num_val = (
            cardinal.cardinal_numbers
            | decimal.decimal_numbers
            | fraction.fraction_numbers
        ).optimize()
        num_with_neg = (num_val | (neg_prefix + num_val)).optimize()

        units_map = pynini.string_map(UNITS_LIST).optimize()

        # Single measure: 5 kg, 5kg, 37°C, -15°C
        single_measure = (num_with_neg + opt_sp + pynutil.insert(" ") + units_map).optimize()

        # Approximate (~) and Plus-Minus (±)
        approx_prefix = pynini.cross("~", "ପ୍ରାୟ ")
        pm_prefix = pynini.cross("±", "ପ୍ଲସ୍ ମାଇନସ୍ ")
        approx_measure = (approx_prefix + single_measure).optimize()
        pm_measure = (pm_prefix + single_measure).optimize()

        # Ranges with units:
        # e.g. 5-10 kg, 5-10kg, 5—10kg -> ପାଞ୍ଚ ରୁ ଦଶ କିଲୋଗ୍ରାମ
        # e.g. 10-15% -> ଦଶ ରୁ ପନ୍ଦର ପ୍ରତିଶତ
        dash = pynini.union("-", "–", "—", " to ")
        range_sep = opt_sp + pynutil.delete(dash) + pynutil.insert(" ରୁ ") + opt_sp

        unit_range_shared = (
            num_with_neg
            + range_sep
            + num_with_neg
            + opt_sp
            + pynutil.insert(" ")
            + units_map
        ).optimize()

        unit_range_repeated = (
            single_measure
            + range_sep
            + single_measure
        ).optimize()

        # Dimensions: 10x20 -> ଦଶ ବାଇ କୋଡ଼ିଏ
        by_sym = pynini.cross("x", " ବାଇ ") | pynini.cross("X", " ବାଇ ") | pynini.cross("×", " ବାଇ ")
        dimensions = (
            num_with_neg + opt_sp + by_sym + opt_sp + num_with_neg
        ).optimize()

        all_measures = (
            single_measure
            | approx_measure
            | pm_measure
            | unit_range_shared
            | unit_range_repeated
            | dimensions
        ).optimize()

        self.measure_graph = all_measures

        graph = pynutil.insert('name: "') + convert_space(all_measures) + pynutil.insert('"')
        self.fst = graph.optimize()
