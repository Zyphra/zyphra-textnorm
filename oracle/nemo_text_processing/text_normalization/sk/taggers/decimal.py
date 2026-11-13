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
)
from nemo_text_processing.text_normalization.sk.taggers.cardinal import CardinalFst


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Slovak decimal numbers, e.g.
        0,729 -> nula celých sedemsto dvadsaťdeväť tisícin
        3,02 -> tri celé dve stotiny
        -2,5 -> mínus dve celé päť desatín
        1,23 mld. -> jedna celá dvadsaťtri stotín miliardy
        5 mil. -> päť miliónov
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        digit = cardinal.digit
        digit_fem = cardinal.digit_fem
        two_digits = cardinal.two_digits
        three_digits = cardinal.three_digits

        # Integer part
        int_1 = pynini.cross("1", "jedna celá ")
        int_few = (pynini.cross("2", "dve") | pynini.cross("3", "tri") | pynini.cross("4", "štyri")) + pynutil.insert(
            " celé "
        )
        int_zero = pynini.cross("0", "nula celých ")
        int_other = (
            (pynini.union("5", "6", "7", "8", "9") @ digit)
            | two_digits
            | three_digits
            | cardinal.thousands
            | cardinal.millions
        ) + pynutil.insert(" celých ")
        int_part = int_1 | int_few | int_zero | int_other

        # Fractional 1 digit (tenths)
        frac_1 = (
            pynini.cross("1", "jedna desatina")
            | (pynini.union("2", "3", "4") @ digit_fem + pynutil.insert(" desatiny"))
            | (pynini.union("5", "6", "7", "8", "9") @ digit + pynutil.insert(" desatín"))
        )

        # Fractional 2 digits (hundredths)
        frac_2 = (
            pynini.cross("01", "jedna stotina")
            | (pynini.cross("02", "dve stotiny") | pynini.cross("03", "tri stotiny") | pynini.cross("04", "štyri stotiny"))
            | (
                pynini.cross("05", "päť stotín")
                | pynini.cross("06", "šesť stotín")
                | pynini.cross("07", "sedem stotín")
                | pynini.cross("08", "osem stotín")
                | pynini.cross("09", "deväť stotín")
            )
            | (two_digits + pynutil.insert(" stotín"))
        )

        # Fractional 3 digits (thousandths)
        frac_3 = (
            pynini.cross("001", "jedna tisícina")
            | (
                pynini.cross("002", "dve tisíciny")
                | pynini.cross("003", "tri tisíciny")
                | pynini.cross("004", "štyri tisíciny")
            )
            | (pynutil.delete("00") + (pynini.union("5", "6", "7", "8", "9") @ digit) + pynutil.insert(" tisícin"))
            | (pynutil.delete("0") + two_digits + pynutil.insert(" tisícin"))
            | (three_digits + pynutil.insert(" tisícin"))
        )

        # Fractional 4 digits (ten-thousandths)
        frac_4 = (
            pynini.cross("0001", "jedna desaťtisícina")
            | (
                pynini.cross("0002", "dve desaťtisíciny")
                | pynini.cross("0003", "tri desaťtisíciny")
                | pynini.cross("0004", "štyri desaťtisíciny")
            )
            | (pynutil.delete("000") + (pynini.union("5", "6", "7", "8", "9") @ digit) + pynutil.insert(" desaťtisícin"))
            | (pynutil.delete("00") + two_digits + pynutil.insert(" desaťtisícin"))
            | (pynutil.delete("0") + three_digits + pynutil.insert(" desaťtisícin"))
        )

        sep = pynutil.delete(pynini.union(",", "."))
        frac_all = frac_1 | frac_2 | frac_3 | frac_4

        dec_pos = int_part + sep + frac_all

        # Magnitude abbreviations
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        mld_suf = pynutil.delete(opt_sp + pynini.union("mld.", "mld", "miliardy", "miliárd", "млрд.", "млрд"))
        mil_suf = pynutil.delete(opt_sp + pynini.union("mil.", "mil", "mln", "milióny", "miliónov", "млн.", "млн"))

        dec_mld = dec_pos + mld_suf + pynutil.insert(" miliardy")
        dec_mil = dec_pos + mil_suf + pynutil.insert(" miliónov")

        card_mil = cardinal.plain_cardinal + mil_suf + pynutil.insert(" miliónov")
        card_mld = cardinal.plain_cardinal + mld_suf + pynutil.insert(" miliárd")

        neg = pynini.cross(pynini.union("-", "−"), "mínus ")
        dec_full = (
            (neg + dec_mld)
            | dec_mld
            | (neg + dec_mil)
            | dec_mil
            | card_mil
            | card_mld
            | (neg + dec_pos)
            | dec_pos
        )

        self.fst = dec_full.optimize()
