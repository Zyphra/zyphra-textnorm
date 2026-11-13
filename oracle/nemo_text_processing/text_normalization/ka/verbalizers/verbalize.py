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

from nemo_text_processing.text_normalization.en.graph_utils import GraphFst
from nemo_text_processing.text_normalization.ka.verbalizers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.ka.verbalizers.date import DateFst
from nemo_text_processing.text_normalization.ka.verbalizers.decimal import DecimalFst
from nemo_text_processing.text_normalization.ka.verbalizers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.ka.verbalizers.fraction import FractionFst
from nemo_text_processing.text_normalization.ka.verbalizers.measure import MeasureFst
from nemo_text_processing.text_normalization.ka.verbalizers.money import MoneyFst
from nemo_text_processing.text_normalization.ka.verbalizers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.ka.verbalizers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.ka.verbalizers.time import TimeFst
from nemo_text_processing.text_normalization.ka.verbalizers.whitelist import WhiteListFst


class VerbalizeFst(GraphFst):
    """
    Composes other verbalizer grammars for Georgian.
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="verbalize", kind="verbalize")
        cardinal = CardinalFst(deterministic=deterministic)
        cardinal_graph = cardinal.fst
        ordinal_graph = OrdinalFst(deterministic=deterministic).fst
        decimal = DecimalFst(deterministic=deterministic)
        decimal_graph = decimal.fst
        fraction = FractionFst()
        fraction_graph = fraction.fst
        measure_graph = MeasureFst(decimal=decimal, cardinal=cardinal).fst
        money_graph = MoneyFst(deterministic=deterministic).fst
        time_graph = TimeFst().fst
        whitelist_graph = WhiteListFst().fst
        date_graph = DateFst(deterministic=deterministic).fst
        telephone_graph = TelephoneFst(deterministic=deterministic).fst
        electronic_graph = ElectronicFst(deterministic=deterministic).fst

        graph = (
            time_graph
            | fraction_graph
            | measure_graph
            | money_graph
            | ordinal_graph
            | decimal_graph
            | cardinal_graph
            | whitelist_graph
            | date_graph
            | telephone_graph
            | electronic_graph
        )
        self.fst = graph.optimize()
