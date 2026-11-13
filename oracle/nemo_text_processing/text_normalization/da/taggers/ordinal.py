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

from nemo_text_processing.text_normalization.da.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)


class OrdinalFst(GraphFst):
    """
    Finite state transducer for classifying Danish ordinals (Unicode CLDR da %spellout-ordinal).
    Handles:
      - Dot ordinals: "1.", "2.", "23.", "50.", "100.", "1000.", "1990."
      - Suffix ordinals: "1.ste", "1ste", "2.den", "2den", "2.det", "2det", "3.je", "3je", "4.de", "4de"
      - Words: første, anden/andet, tredje, fjerde, ..., enogtyvende, halvtredsindstyvende, hundredede, tusinde
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="ordinal", kind="classify", deterministic=deterministic)

        # 1-19
        ord_1_to_19 = (
            pynini.cross("1", "første")
            | pynini.cross("2", "anden")
            | pynini.cross("3", "tredje")
            | pynini.cross("4", "fjerde")
            | pynini.cross("5", "femte")
            | pynini.cross("6", "sjette")
            | pynini.cross("7", "syvende")
            | pynini.cross("8", "ottende")
            | pynini.cross("9", "niende")
            | pynini.cross("10", "tiende")
            | pynini.cross("11", "ellevte")
            | pynini.cross("12", "tolvte")
            | pynini.cross("13", "trettende")
            | pynini.cross("14", "fjortende")
            | pynini.cross("15", "femtende")
            | pynini.cross("16", "sekstende")
            | pynini.cross("17", "syttende")
            | pynini.cross("18", "attende")
            | pynini.cross("19", "nittende")
        )

        # Neuter 2: "andet"
        ord_2_neuter = pynini.cross("2", "andet")

        # Ties 20-90
        ord_exact_ties = (
            pynini.cross("20", "tyvende")
            | pynini.cross("30", "tredivte")
            | pynini.cross("40", "fyrrende")
            | pynini.cross("50", "halvtredsindstyvende")
            | pynini.cross("60", "tresindstyvende")
            | pynini.cross("70", "halvfjerdsindstyvende")
            | pynini.cross("80", "firsindstyvende")
            | pynini.cross("90", "halvfemsindstyvende")
        )

        # Alternate shorter Danish forms for 50-90 (halvtredsende, etc.)
        ord_exact_ties_alt = (
            pynini.cross("50", "halvtredsende")
            | pynini.cross("60", "tresende")
            | pynini.cross("70", "halvfjerdsende")
            | pynini.cross("80", "firsende")
            | pynini.cross("90", "halvfemsende")
        )

        # Unit prefixes for 21-99: "enog", "toog", "treog", ...
        unit_prefix_ord = [
            ("1", "enog"),
            ("2", "toog"),
            ("3", "treog"),
            ("4", "fireog"),
            ("5", "femog"),
            ("6", "seksog"),
            ("7", "syvog"),
            ("8", "otteog"),
            ("9", "niog"),
        ]

        tie_suffixes_ord = [
            ("2", "tyvende"),
            ("3", "tredivte"),
            ("4", "fyrrende"),
            ("5", "halvtredsindstyvende"),
            ("6", "tresindstyvende"),
            ("7", "halvfjerdsindstyvende"),
            ("8", "firsindstyvende"),
            ("9", "halvfemsindstyvende"),
        ]

        ord_compound_21_99 = pynini.union(
            *[
                pynini.cross(f"{t}{u}", f"{upfx}{tsfx}")
                for t, tsfx in tie_suffixes_ord
                for u, upfx in unit_prefix_ord
            ]
        )

        # Also support "etogtyvende" (common variant in CLDR RBNF)
        ord_compound_et = pynini.union(
            *[
                pynini.cross(f"{t}1", f"etog{tsfx}")
                for t, tsfx in tie_suffixes_ord
            ]
        )

        ord_1_to_99 = (
            ord_1_to_19
            | ord_exact_ties
            | pynutil.add_weight(ord_exact_ties_alt, 0.05)
            | ord_compound_21_99
            | pynutil.add_weight(ord_compound_et, 0.05)
        ).optimize()

        ord_1_to_99_lead_zero = (
            NEMO_DIGIT ** 2
            @ (ord_1_to_99 | (pynutil.delete("0") + ord_1_to_19))
        ).optimize()

        # Hundreds 100-999
        hundred_ord_names = [
            ("1", "hundredede"),
            ("2", "tohundredede"),
            ("3", "trehundredede"),
            ("4", "firehundredede"),
            ("5", "femhundredede"),
            ("6", "sekshundredede"),
            ("7", "syvhundredede"),
            ("8", "ottehundredede"),
            ("9", "nihundredede"),
        ]

        exact_hundreds_ord = pynini.union(
            *[pynini.cross(d + "00", name) for d, name in hundred_ord_names]
        )

        hundreds_with_rem_ord = pynini.union(
            *[
                pynini.cross(d, name[:-2] + " og ") + ord_1_to_99_lead_zero
                for d, name in hundred_ord_names
            ]
        )

        ord_1_to_999 = (
            exact_hundreds_ord
            | hundreds_with_rem_ord
            | ord_1_to_99
        ).optimize()

        # Thousands 1000-9999
        exact_thousands_ord = (
            pynini.cross("1000", "tusinde")
            | (cardinal.num_1_to_999_neuter + pynutil.insert(" tusinde") + pynutil.delete("000"))
        )

        thousand_prefix = (
            pynini.cross("1", "tusind")
            | ((pynini.difference(pynini.closure(NEMO_DIGIT, 1, 3), "1")
                @ cardinal.num_1_to_999_neuter) + pynutil.insert(" tusind"))
        )
        under_hundred_remainder = (
            pynutil.delete("00") + ((NEMO_DIGIT - "0") @ ord_1_to_19)
            | pynutil.delete("0") + ord_1_to_99_lead_zero
        )
        thousands_with_rem_ord = (
            thousand_prefix + pynutil.insert(" og ") + under_hundred_remainder
            | thousand_prefix + pynutil.insert(" ") + (NEMO_DIGIT ** 3 @ ord_1_to_999)
        )

        # Years as ordinals (e.g. 1990. -> nitten hundrede og halvfems.)
        year_ord = (
            pynini.cross("19", "nitten hundrede og ") + (NEMO_DIGIT ** 2 @ ord_1_to_99)
            | pynini.cross("20", "to tusind og ") + (NEMO_DIGIT ** 2 @ ord_1_to_99)
        )

        all_ords = (
            exact_thousands_ord
            | thousands_with_rem_ord
            | year_ord
            | ord_1_to_999
        ).optimize()

        # Ordinal with dot: e.g. "1.", "2.", "23.", "100."
        dot = pynutil.delete(".")
        dot_ordinal = all_ords + dot

        # Ordinal with letter suffix: e.g. "1.ste", "1ste", "2.den", "2den", "2.det", "3.je", "4.de"
        suffix_ste = pynini.cross("1", "første") + pynini.closure(pynutil.delete("."), 0, 1) + pynutil.delete("ste")
        suffix_den = pynini.cross("2", "anden") + pynini.closure(pynutil.delete("."), 0, 1) + pynutil.delete("den")
        suffix_det = pynini.cross("2", "andet") + pynini.closure(pynutil.delete("."), 0, 1) + pynutil.delete("det")
        suffix_je = pynini.cross("3", "tredje") + pynini.closure(pynutil.delete("."), 0, 1) + pynutil.delete("je")
        suffix_de = (
            pynini.cross("4", "fjerde")
            | pynini.cross("10", "tiende")
            | pynini.cross("20", "tyvende")
            | pynini.cross("30", "tredivte")
            | pynini.cross("40", "fyrrende")
            | pynini.cross("50", "halvtredsindstyvende")
        ) + pynini.closure(pynutil.delete("."), 0, 1) + pynutil.delete("de")
        suffix_te = (
            pynini.cross("5", "femte")
            | pynini.cross("6", "sjette")
        ) + pynini.closure(pynutil.delete("."), 0, 1) + pynutil.delete("te")
        suffix_ende = (
            pynini.cross("7", "syvende")
            | pynini.cross("8", "ottende")
            | pynini.cross("9", "niende")
        ) + pynini.closure(pynutil.delete("."), 0, 1) + pynutil.delete("ende")

        suffixed_ordinal = (
            suffix_ste
            | suffix_den
            | suffix_det
            | suffix_je
            | suffix_de
            | suffix_te
            | suffix_ende
        )

        self.words = all_ords
        self.graph = (dot_ordinal | suffixed_ordinal).optimize()

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
