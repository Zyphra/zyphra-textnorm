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

# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_NON_BREAKING_SPACE,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.ms.utils import get_abs_path, load_labels

# Units that collide with decades ("2020s", "90s") or serial/room codes ("4K", "10A", "5J") when glued without space
_SPACED_ONLY_UNITS = {"s", "t", "A", "J", "N", "cd"}


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Malay measure (CLDR ms long unit names, invariant), e.g.
        "5 km" -> measure { cardinal { integer: "lima" } units: "kilometer" preserve_order: true }
        "~10 km" -> measure { cardinal { negative: "sekitar" integer: "sepuluh" } units: "kilometer" preserve_order: true }
        "±10%" -> measure { cardinal { negative: "lebih kurang" integer: "sepuluh" } units: "peratus" preserve_order: true }
        "60 km/jam" -> measure { cardinal { integer: "enam puluh" } units: "kilometer per jam" preserve_order: true }

    Args:
        cardinal: CardinalFst
        decimal: DecimalFst
        fraction: FractionFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, fraction: GraphFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)
        rows = load_labels(get_abs_path("data/measure/measurements.tsv"))
        unit_all = convert_space(pynini.string_map(rows))
        unit_glued = convert_space(pynini.string_map([r for r in rows if r[0] not in _SPACED_ONLY_UNITS]))

        denominator = convert_space(pynini.string_file(get_abs_path("data/measure/denominators.tsv")))
        per = pynini.cross("/", f"{NEMO_NON_BREAKING_SPACE}per{NEMO_NON_BREAKING_SPACE}")

        units_spaced = (
            pynutil.delete(pynini.union(" ", "\u00a0", "\u202f"))
            + pynutil.insert(' units: "')
            + unit_all
            + pynini.closure(per + denominator, 0, 1)
            + pynutil.insert('"')
        )
        units_glued = (
            pynutil.insert(' units: "')
            + (unit_glued + pynini.closure(per + denominator, 0, 1) | unit_all + per + denominator)
            + pynutil.insert('"')
        )
        number = cardinal.fst | decimal.fst | fraction.fst
        graph = number + (units_spaced | units_glued) + pynutil.insert(" preserve_order: true")
        # a unit must not be read off the start of a following word
        graph = pynutil.add_weight(graph, 0.01)
        self.fst = self.add_tokens(graph).optimize()
