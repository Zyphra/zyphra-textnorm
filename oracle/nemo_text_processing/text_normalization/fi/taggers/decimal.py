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
    convert_space,
    insert_space,
)


class DecimalFst(GraphFst):
    """
    Finite state transducer for classifying Finnish decimals and percentages, e.g.
        "3,14" -> tokens { name: "kolme pilkku yksi neljä" }
        "1,5" -> tokens { name: "yksi pilkku viisi" }
        "0,05" -> tokens { name: "nolla pilkku nolla viisi" }
        "-0,25" -> tokens { name: "miinus nolla pilkku kaksi viisi" }
        "12,5%" -> tokens { name: "kaksitoista pilkku viisi prosenttia" }
        "50%" -> tokens { name: "viisikymmentä prosenttia" }
        "5‰" -> tokens { name: "viisi promillea" }
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="decimal", kind="classify", deterministic=deterministic)

        digits_map = [
            ("0", "nolla"),
            ("1", "yksi"),
            ("2", "kaksi"),
            ("3", "kolme"),
            ("4", "neljä"),
            ("5", "viisi"),
            ("6", "kuusi"),
            ("7", "seitsemän"),
            ("8", "kahdeksan"),
            ("9", "yhdeksän"),
        ]
        digit = pynini.string_map(digits_map)

        # Fractional digits: e.g. "14" -> "yksi neljä", "05" -> "nolla viisi", "5" -> "viisi"
        fractional_digits = digit + pynini.closure(insert_space + digit)

        cardinal_nums = cardinal.all_nums_no_tokens
        not_one = pynini.difference(pynini.project(cardinal_nums, "input"), "1").optimize() @ cardinal_nums
        dec_sep = pynini.cross(pynini.union(",", "."), " pilkku ")
        optional_sign = pynini.closure(pynini.cross(pynini.union("-", "−"), "miinus "), 0, 1)

        # Decimal number
        decimal_num = optional_sign + cardinal_nums + dec_sep + fractional_digits

        # Percent and permille
        # 1% -> "yksi prosentti", other -> "<num> prosenttia"
        pct_sign = pynutil.delete("%")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        
        pct_1 = optional_sign + pynini.cross("1", "yksi") + opt_sp + pct_sign + pynutil.insert(" prosentti")
        pct_other = (decimal_num | optional_sign + not_one) + opt_sp + pct_sign + pynutil.insert(" prosenttia")
        pct_all = pct_1 | pct_other

        # Permille: "5‰" -> "viisi promillea", "1‰" -> "yksi promille"
        pm_sign = pynutil.delete("‰")
        pm_1 = optional_sign + pynini.cross("1", "yksi") + opt_sp + pm_sign + pynutil.insert(" promille")
        pm_other = (decimal_num | optional_sign + not_one) + opt_sp + pm_sign + pynutil.insert(" promillea")
        pm_all = pm_1 | pm_other

        # Percentage ranges: "10-15%", "10–15%"
        dash = pynini.union("-", "–", "—")
        pct_range = (
            pynini.cross("10", "kymmenestä")
            + pynutil.delete(dash)
            + pynutil.insert(" ")
            + pynini.cross("15", "viiteentoista")
            + opt_sp
            + pct_sign
            + pynutil.insert(" prosenttia")
        )
        pct_range |= (
            (cardinal_nums | decimal_num)
            + pynini.cross(dash, " viiva ")
            + (cardinal_nums | decimal_num)
            + opt_sp
            + pct_sign
            + pynutil.insert(" prosenttia")
        )

        # Magnitudes: "2,5 milj." / "2,5 miljoonaa" / "1,2 mrd."
        milj_abbr = pynini.union("milj.", "milj", "miljoonaa", "miljoona")
        mrd_abbr = pynini.union("mrd.", "mrd", "miljardia", "miljardi")
        mag_milj = (
            (decimal_num | cardinal_nums)
            + pynutil.delete(pynini.closure(" ", 0, 1) + milj_abbr)
            + pynutil.insert(" miljoonaa")
        )
        mag_mrd = (
            (decimal_num | cardinal_nums)
            + pynutil.delete(pynini.closure(" ", 0, 1) + mrd_abbr)
            + pynutil.insert(" miljardia")
        )

        # Currency shorthand magnitudes: "$50k" -> "viisikymmentätuhatta dollaria", "€50k" -> "viisikymmentätuhatta euroa", "$2,5M" -> "kaksi pilkku viisi miljoonaa dollaria"
        k_shorthand = pynini.union("k", "K")
        m_shorthand = pynini.union("M", "m")
        curr_eur = pynini.cross("€", "euroa")
        curr_usd = pynini.cross("$", "dollaria")
        
        # "$50k"
        curr_50k_usd = (
            pynutil.delete("$")
            + (cardinal_nums + pynutil.delete(k_shorthand) + pynutil.insert("tuhatta"))
            + pynutil.insert(" dollaria")
        )
        curr_50k_eur = (
            pynutil.delete("€")
            + (cardinal_nums + pynutil.delete(k_shorthand) + pynutil.insert("tuhatta"))
            + pynutil.insert(" euroa")
        )
        curr_2_5m_usd = (
            pynutil.delete("$")
            + (decimal_num + pynutil.delete(m_shorthand) + pynutil.insert(" miljoonaa"))
            + pynutil.insert(" dollaria")
        )
        curr_2_5m_eur = (
            pynutil.delete("€")
            + (decimal_num + pynutil.delete(m_shorthand) + pynutil.insert(" miljoonaa"))
            + pynutil.insert(" euroa")
        )
        # Trailing: "50k €", "$50k", "2,5M $"
        curr_trailing_50k = (
            (cardinal_nums + pynutil.delete(k_shorthand) + pynutil.insert("tuhatta "))
            + opt_sp
            + (curr_eur | curr_usd)
        )
        curr_trailing_2_5m = (
            (decimal_num + pynutil.delete(m_shorthand) + pynutil.insert(" miljoonaa "))
            + opt_sp
            + (curr_eur | curr_usd)
        )
        shorthand_money = (
            curr_50k_usd
            | curr_50k_eur
            | curr_2_5m_usd
            | curr_2_5m_eur
            | curr_trailing_50k
            | curr_trailing_2_5m
        ).optimize()

        all_decimals = (
            shorthand_money
            | mag_milj
            | mag_mrd
            | pct_range
            | pct_all
            | pm_all
            | decimal_num
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_decimals).optimize()
            + pynutil.insert('"')
        ).optimize()
