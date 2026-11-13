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
from nemo_text_processing.text_normalization.tl.verbalizers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.tl.verbalizers.date import DateFst
from nemo_text_processing.text_normalization.tl.verbalizers.decimal import DecimalFst
from nemo_text_processing.text_normalization.tl.verbalizers.electronic import ElectronicFst
from nemo_text_processing.text_normalization.tl.verbalizers.fraction import FractionFst
from nemo_text_processing.text_normalization.tl.verbalizers.measure import MeasureFst
from nemo_text_processing.text_normalization.tl.verbalizers.money import MoneyFst
from nemo_text_processing.text_normalization.tl.verbalizers.ordinal import OrdinalFst
from nemo_text_processing.text_normalization.tl.verbalizers.telephone import TelephoneFst
from nemo_text_processing.text_normalization.tl.verbalizers.time import TimeFst
from nemo_text_processing.text_normalization.tl.verbalizers.whitelist import WhiteListFst


class VerbalizeFst(GraphFst):
    """
    Composes other Tagalog verbalizer grammars.

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="verbalize", kind="verbalize", deterministic=deterministic)
        cardinal = CardinalFst(deterministic=deterministic)
        decimal = DecimalFst(deterministic=deterministic)
        fraction = FractionFst(deterministic=deterministic)
        measure = MeasureFst(cardinal=cardinal, decimal=decimal, fraction=fraction, deterministic=deterministic)
        graph = (
            cardinal.fst
            | decimal.fst
            | fraction.fst
            | measure.fst
            | OrdinalFst(deterministic=deterministic).fst
            | DateFst(deterministic=deterministic).fst
            | TimeFst(deterministic=deterministic).fst
            | MoneyFst(deterministic=deterministic).fst
            | TelephoneFst(deterministic=deterministic).fst
            | ElectronicFst(deterministic=deterministic).fst
            | WhiteListFst(deterministic=deterministic).fst
        )
        self.fst = graph
