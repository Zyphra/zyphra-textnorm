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
    NEMO_DIGIT,
    GraphFst,
    insert_space,
)
from nemo_text_processing.text_normalization.ka.graph_utils import (
    glue_suffix,
    with_suffix,
)
from nemo_text_processing.text_normalization.ka.utils import get_abs_path


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Georgian ordinals, e.g.
        1-ელი -> ordinal { integer: "პირველი" }
        1-ლი -> ordinal { integer: "პირველი" }
        2-ე -> ordinal { integer: "მეორე" }
        3-ე -> ordinal { integer: "მესამე" }
        21-ე -> ordinal { integer: "ოცდამეერთე" }
        100-ე -> ordinal { integer: "მეასე" }
        1-ელს -> ordinal { integer: "პირველს" }
        2-ეს -> ordinal { integer: "მეორეს" }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        digits_ord = pynini.string_file(get_abs_path("data/ordinal/digit.tsv"))
        ord_1_standalone = pynini.cross("1", "პირველი")
        ord_1_compound = pynini.cross("1", "მეერთე")
        ord_2_9 = (NEMO_DIGIT - pynini.union("0", "1")) @ digits_ord
        ord_10_19 = (pynini.accep("1") + NEMO_DIGIT) @ digits_ord

        # In compounds, 1 becomes "მეერთე":
        ord_compound_1_9 = ord_1_compound | ord_2_9

        # Tens ordinals:
        exact_tens_ord = pynini.string_file(get_abs_path("data/ordinal/ties.tsv"))

        unit_11_19_ord = (NEMO_DIGIT - "0") @ (
            pynini.cross("1", "მეთერთმეტე")
            | pynini.cross("2", "მეთორმეტე")
            | pynini.cross("3", "მეცამეტე")
            | pynini.cross("4", "მეთოთხმეტე")
            | pynini.cross("5", "მეთხუთმეტე")
            | pynini.cross("6", "მეთექვსმეტე")
            | pynini.cross("7", "მეჩვიდმეტე")
            | pynini.cross("8", "მეთვრამეტე")
            | pynini.cross("9", "მეცხრამეტე")
        )

        compound_20_39_ord = (pynini.cross("2", "ოცდა") + ord_compound_1_9) | (pynini.cross("3", "ოცდა") + unit_11_19_ord)
        compound_40_59_ord = (pynini.cross("4", "ორმოცდა") + ord_compound_1_9) | (pynini.cross("5", "ორმოცდა") + unit_11_19_ord)
        compound_60_79_ord = (pynini.cross("6", "სამოცდა") + ord_compound_1_9) | (pynini.cross("7", "სამოცდა") + unit_11_19_ord)
        compound_80_99_ord = (pynini.cross("8", "ოთხმოცდა") + ord_compound_1_9) | (pynini.cross("9", "ოთხმოცდა") + unit_11_19_ord)

        double_digits_ord = (
            exact_tens_ord
            | compound_20_39_ord
            | compound_40_59_ord
            | compound_60_79_ord
            | compound_80_99_ord
        )

        # 1..99 ordinals:
        ord_1_to_99_standalone = ord_1_standalone | ord_2_9 | ord_10_19 | double_digits_ord
        ord_1_to_99_compound = ord_1_compound | ord_2_9 | ord_10_19 | double_digits_ord

        # Hundreds ordinals:
        exact_hundreds_ord = pynini.string_file(get_abs_path("data/ordinal/hundreds.tsv"))
        hundreds_stems = pynini.string_file(get_abs_path("data/numbers/hundreds_stem.tsv"))
        hundreds_ord_remainder = (
            (pynutil.delete("0") + insert_space + ord_compound_1_9)
            | (insert_space + (ord_10_19 | double_digits_ord))
        )
        compound_hundreds_ord = hundreds_stems + hundreds_ord_remainder
        all_hundreds_ord = exact_hundreds_ord | compound_hundreds_ord

        ord_1_to_999 = ord_1_to_99_standalone | all_hundreds_ord

        # Thousands ordinals:
        thousands_ord_remainder = (
            (pynutil.delete("00") + insert_space + ord_compound_1_9)
            | (pynutil.delete("0") + insert_space + (ord_10_19 | double_digits_ord))
            | (insert_space + all_hundreds_ord)
        )
        one_thousand_ord = pynini.cross("1000", "მეათასე") | (pynini.cross("1", "ათას") + thousands_ord_remainder)

        multi_thousands_prefix = (
            pynini.string_file(get_abs_path("data/numbers/digit.tsv"))
            | pynini.string_file(get_abs_path("data/numbers/ties.tsv"))
            | compound_20_39_ord  # tens
        )
        if cardinal is not None:
            multi_thousands_prefix = cardinal.one_to_999

        multi_thousands_ord = (
            (multi_thousands_prefix + pynutil.delete("000") + insert_space + pynutil.insert("მეათასე"))
            | (multi_thousands_prefix + insert_space + pynutil.insert("ათას") + thousands_ord_remainder)
        )

        all_thousands_ord = one_thousand_ord | multi_thousands_ord
        all_ordinals = ord_1_to_99_standalone | all_hundreds_ord | all_thousands_ord
        self.graph = all_ordinals.optimize()

        # Input written forms:
        # 1-ელი, 1-ელის, 1-ელმა, 1-ელს, 1-ელით, 1-ელად
        # 1-ლი, 1-ლის, 1-ლმა, 1-ლს, 1-ლით, 1-ლად
        hyphen = pynini.union("-", "–", "—", "֊")
        first_eli = pynutil.delete("1" + hyphen) + pynini.union(
            pynini.cross("ელი", "პირველი"),
            pynini.cross("ელს", "პირველს"),
            pynini.cross("ელმა", "პირველმა"),
            pynini.cross("ელის", "პირველის"),
            pynini.cross("ელით", "პირველით"),
            pynini.cross("ელად", "პირველად"),
            pynini.cross("ელში", "პირველში"),
            pynini.cross("ელზე", "პირველზე"),
            pynini.cross("ელამდე", "პირველამდე"),
            pynini.cross("ელიდან", "პირველიდან"),
            pynini.cross("ლი", "პირველი"),
            pynini.cross("ლს", "პირველს"),
            pynini.cross("ლმა", "პირველმა"),
            pynini.cross("ლის", "პირველის"),
            pynini.cross("ლით", "პირველით"),
            pynini.cross("ლად", "პირველად"),
            pynini.cross("ლში", "პირველში"),
            pynini.cross("ლზე", "პირველზე"),
            pynini.cross("ლამდე", "პირველამდე"),
            pynini.cross("ლიდან", "პირველიდან"),
        )
        first_suffixed = pynutil.delete("1" + hyphen) + pynini.union("ელი", "ლი")
        first_with_cases = with_suffix(pynini.cross(first_suffixed, "პირველი"))

        # Other numbers: "2-ე", "3-ე", "25-ე", "100-ე"
        num_part = (pynini.closure(NEMO_DIGIT, 1, 9) - "1") @ self.graph
        other_e = num_part + pynutil.delete(hyphen + "ე")
        other_suffixed = with_suffix(num_part + pynutil.delete(hyphen + "ე"))

        # E-marked endings distinguish ordinals from cardinal cases such as "5-ს".
        ordinal_case_inputs = (
            pynini.closure(NEMO_DIGIT, 1, 9)
            + hyphen
            + pynini.union("ეს", "ემ", "ედ")
        )
        other_cases = ordinal_case_inputs @ with_suffix(num_part)

        written_ordinals = (
            first_eli
            | first_with_cases
            | other_e
            | other_suffixed
            | other_cases
        )

        final_graph = pynutil.insert('integer: "') + written_ordinals + pynutil.insert('"')
        self.fst = self.add_tokens(final_graph).optimize()
