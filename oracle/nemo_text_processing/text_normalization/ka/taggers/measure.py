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

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_SIGMA,
    TO_LOWER,
    GraphFst,
    delete_extra_space,
    delete_space,
)
from nemo_text_processing.text_normalization.ka.graph_utils import with_suffix
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying measure, e.g.
        52 კგ -> measure { cardinal { integer: "ორმოცდათორმეტი" } units: "კილოგრამი" }
        50kg -> measure { cardinal { integer: "ორმოცდაათი" } units: "კილოგრამი" }
        1.5 km -> measure { decimal { integer_part: "ერთი" fractional_part: "ხუთი" } units: "კილომეტრი" }
        25%-ით -> measure { cardinal { integer: "ოცდახუთი" } units: "პროცენტით" }
        37°C -> measure { cardinal { integer: "ოცდაჩვიდმეტი" } units: "გრადუსი ცელსიუსით" }
        -15°C -> measure { cardinal { negative: "true" integer: "თხუთმეტი" } units: "გრადუსი ცელსიუსით" }
        5-10 kg -> measure { cardinal { integer: "ხუთიდან ათამდე" } units: "კილოგრამი" }
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst):
        super().__init__(name="measure", kind="classify")

        cardinal_graph = cardinal.all_nums_no_tokens
        range_graph = cardinal.range_graph
        casing_graph = pynini.closure(TO_LOWER | NEMO_SIGMA)

        graph_measurements_unit = pynini.string_file(get_abs_path("data/measurements.tsv"))
        graph_measurements_unit = pynini.compose(casing_graph, graph_measurements_unit)
        graph_measurements_unit |= pynini.string_file(get_abs_path("data/measurements_latin.tsv"))
        graph_measurements_unit = (graph_measurements_unit | with_suffix(graph_measurements_unit)).optimize()

        graph_measurements_dates_unit = pynini.string_file(get_abs_path("data/measurement_dates.tsv"))
        graph_measurements_dates_unit = pynini.compose(casing_graph, graph_measurements_dates_unit)
        graph_measurements_dates_unit = (graph_measurements_dates_unit | with_suffix(graph_measurements_dates_unit)).optimize()

        measurements_unit = pynutil.insert('units: "') + graph_measurements_unit + pynutil.insert('"')
        measurements_dates_unit = pynutil.insert('units: "') + graph_measurements_dates_unit + pynutil.insert('"')

        optional_negative = pynini.closure(
            pynini.cross("-", 'negative: "true" ') | pynini.cross("−", 'negative: "true" '),
            0,
            1,
        )

        subgraph_decimal = (
            pynutil.insert("decimal { ")
            + decimal.final_graph
            + pynutil.insert(" }")
            + pynini.closure(delete_space, 0, 1)
            + measurements_unit
        )

        card_num = (
            optional_negative
            + pynutil.insert('integer: "')
            + (cardinal_graph | range_graph)
            + pynutil.insert('"')
        )
        subgraph_cardinal = (
            pynutil.insert("cardinal { ")
            + card_num
            + pynutil.insert(" }")
            + pynini.closure(delete_space, 0, 1)
            + (measurements_unit | measurements_dates_unit)
        )

        final_graph = subgraph_cardinal | subgraph_decimal
        self.fst = self.add_tokens(final_graph).optimize()
