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
    GraphFst,
    convert_space,
)


class FractionFst(GraphFst):
    """
    Finite state transducer for classifying Finnish fractions, e.g.
        "½" -> tokens { name: "puoli" }
        "⅓" -> tokens { name: "yksi kolmasosa" }
        "2½" -> tokens { name: "kaksi ja puoli" }
        "-2½" -> tokens { name: "miinus kaksi ja puoli" }
        "5/8" -> tokens { name: "viisi kahdeksasosaa" }
        "1/2 kg" -> tokens { name: "puoli kilogrammaa" }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="fraction", kind="classify", deterministic=deterministic)

        vulgar_map = [
            ("½", "puoli"),
            ("⅓", "yksi kolmasosa"),
            ("⅔", "kaksi kolmasosaa"),
            ("¼", "yksi neljäsosa"),
            ("¾", "kolme neljäsosaa"),
            ("⅕", "yksi viidesosa"),
            ("⅖", "kaksi viidesosaa"),
            ("⅗", "kolme viidesosaa"),
            ("⅘", "neljä viidesosaa"),
            ("⅙", "yksi kuudesosa"),
            ("⅚", "viisi kuudesosaa"),
            ("⅛", "yksi kahdeksasosa"),
            ("⅜", "kolme kahdeksasosaa"),
            ("⅝", "viisi kahdeksasosaa"),
            ("⅞", "seitsemän kahdeksasosaa"),
            ("⅐", "yksi seitsemäsosa"),
            ("⅑", "yksi yhdeksäsosa"),
            ("⅒", "yksi kymmenesosa"),
        ]
        vulgar = pynini.string_map(vulgar_map)

        slash_map = [
            ("1/2", "puoli"),
            ("1/3", "yksi kolmasosa"),
            ("2/3", "kaksi kolmasosaa"),
            ("1/4", "yksi neljäsosa"),
            ("2/4", "kaksi neljäsosaa"),
            ("3/4", "kolme neljäsosaa"),
            ("1/5", "yksi viidesosa"),
            ("2/5", "kaksi viidesosaa"),
            ("3/5", "kolme viidesosaa"),
            ("4/5", "neljä viidesosaa"),
            ("1/6", "yksi kuudesosa"),
            ("5/6", "viisi kuudesosaa"),
            ("1/8", "yksi kahdeksasosa"),
            ("3/8", "kolme kahdeksasosaa"),
            ("5/8", "viisi kahdeksasosaa"),
            ("7/8", "seitsemän kahdeksasosaa"),
            ("1/10", "yksi kymmenesosa"),
        ]
        slash = pynini.string_map(slash_map)

        fraction_base = vulgar | slash
        sign = pynini.cross(pynini.union("-", "−"), "miinus ")
        opt_sign = pynini.closure(sign, 0, 1)

        pure_fraction = opt_sign + fraction_base

        # Mixed fractions: "2½" -> "kaksi ja puoli", "2 1/2" -> "kaksi ja puoli", "-2½" -> "miinus kaksi ja puoli"
        cardinal_nums = cardinal.all_nums_no_tokens
        sp = pynini.closure(pynutil.delete(" "), 0, 1)
        mixed_fraction = (
            opt_sign
            + cardinal_nums
            + sp
            + pynutil.insert(" ja ")
            + fraction_base
        )

        # Mixed or pure fractions with units: e.g. "1/2 kg", "-1/2 kg", "2 1/2 kg"
        unit_kg = pynini.cross(pynini.union("kg", "kilogramma", "kilo"), "kilogrammaa")
        unit_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        fraction_unit = (
            (pure_fraction | mixed_fraction)
            + pynutil.insert(" ")
            + unit_sp
            + unit_kg
        )

        all_fractions = (fraction_unit | mixed_fraction | pure_fraction).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_fractions).optimize()
            + pynutil.insert('"')
        ).optimize()
