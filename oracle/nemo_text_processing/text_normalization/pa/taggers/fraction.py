# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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

from nemo_text_processing.text_normalization.pa.graph_utils import NEMO_SPACE, GraphFst
from nemo_text_processing.text_normalization.pa.utils import get_abs_path

PA_DEDH = "ਡੇਢ"  # 1 1/2
PA_DHAI = "ਢਾਈ"  # 2 1/2
PA_SAVA = "ਸਵਾ"  # n 1/4
PA_SADHE = "ਸਾਢੇ"  # n 1/2
PA_PAUNE = "ਪੌਣੇ"  # n 3/4, read with the next number

ONE_HALF = pynini.union("1/2", "੧/੨")
ONE_QUARTER = pynini.union("1/4", "੧/੪")
THREE_QUARTERS = pynini.union("3/4", "੩/੪")


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying fraction in Punjabi, e.g.
        "੨੩ ੪/੬" -> fraction { integer_part: "ਤੇਈ" numerator: "ਚਾਰ" denominator: "ਛੇ" }
        "੪/੬" -> fraction { numerator: "ਚਾਰ" denominator: "ਛੇ" }
        "੩ ੧/੨" -> fraction { morphosyntactic_features: "ਸਾਢੇ ਤਿੰਨ" }

    Args:
        cardinal: cardinal GraphFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        cardinal_graph = cardinal.final_graph

        self.optional_graph_negative = pynini.closure(
            pynutil.insert("negative: ") + pynini.cross(pynini.union("-", "−"), "\"true\"") + pynutil.insert(NEMO_SPACE), 0, 1
        )

        self.integer = pynutil.insert("integer_part: \"") + cardinal_graph + pynutil.insert("\"")

        self.numerator = (
            pynutil.insert("numerator: \"")
            + cardinal_graph
            + pynini.cross(pynini.union("/", NEMO_SPACE + "/" + NEMO_SPACE), "\"")
            + pynutil.insert(NEMO_SPACE)
        )

        self.denominator = pynutil.insert("denominator: \"") + cardinal_graph + pynutil.insert("\"")

        optional_space = pynini.closure(pynini.accep(NEMO_SPACE), 0, 1)
        half_suffix = (pynini.accep(NEMO_SPACE) + ONE_HALF) | (optional_space + pynini.accep("½"))
        quarter_suffix = (pynini.accep(NEMO_SPACE) + ONE_QUARTER) | (optional_space + pynini.accep("¼"))
        three_quarters_suffix = (pynini.accep(NEMO_SPACE) + THREE_QUARTERS) | (optional_space + pynini.accep("¾"))

        dedh_dhai_graph = pynini.union(
            pynini.cross(pynini.union("1", "੧") + half_suffix, PA_DEDH),
            pynini.cross(pynini.union("2", "੨") + half_suffix, PA_DHAI),
        )

        sava_graph = pynutil.insert(PA_SAVA + NEMO_SPACE) + cardinal_graph + pynutil.delete(quarter_suffix)
        sadhe_graph = pynutil.insert(PA_SADHE + NEMO_SPACE) + cardinal_graph + pynutil.delete(half_suffix)

        next_number = pynini.string_file(get_abs_path("data/fraction/next_number.tsv"))
        paune_graph = pynutil.insert(PA_PAUNE + NEMO_SPACE) + next_number + pynutil.delete(three_quarters_suffix)

        common_fraction_map = pynini.string_file(get_abs_path("data/fraction/common_fractions.tsv"))

        morphosyntactic_features = (
            pynutil.insert("morphosyntactic_features: \"")
            + (common_fraction_map | dedh_dhai_graph | sava_graph | sadhe_graph | paune_graph)
            + pynutil.insert("\"")
        )

        # Standard simple and mixed fraction
        standard_fraction = self.numerator + self.denominator
        mixed_fraction = self.integer + pynini.closure(pynutil.delete(NEMO_SPACE), 1) + pynutil.insert(NEMO_SPACE) + standard_fraction
        vulgar = pynini.string_map([
            ("¼", "1/4"), ("½", "1/2"), ("¾", "3/4"),
            ("⅐", "1/7"), ("⅑", "1/9"), ("⅒", "1/10"),
            ("⅓", "1/3"), ("⅔", "2/3"), ("⅕", "1/5"), ("⅖", "2/5"),
            ("⅗", "3/5"), ("⅘", "4/5"), ("⅙", "1/6"), ("⅚", "5/6"),
            ("⅛", "1/8"), ("⅜", "3/8"), ("⅝", "5/8"), ("⅞", "7/8"),
        ]) @ standard_fraction
        unicode_fraction = vulgar | self.integer + pynini.closure(pynutil.delete(" ")) + pynutil.insert(" ") + vulgar

        final_graph = (
            self.optional_graph_negative
            + (mixed_fraction | pynutil.add_weight(morphosyntactic_features, -0.1) | standard_fraction | unicode_fraction)
        )

        self.fst = self.add_tokens(final_graph).optimize()
