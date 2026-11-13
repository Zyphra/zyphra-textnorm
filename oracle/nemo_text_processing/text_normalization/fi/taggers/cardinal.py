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
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    convert_space,
    insert_space,
)
from nemo_text_processing.text_normalization.fi.graph_utils import (
    FINNISH_ALPHA,
)


class CardinalFst(GraphFst):
    """
    Finite state transducer for classifying Finnish cardinals, e.g.
        "100" -> tokens { name: "sata" }
        "21" -> tokens { name: "kaksikymmentäyksi" }
        "1020" -> tokens { name: "tuhatkaksikymmentä" }
        "-12" -> tokens { name: "miinus kaksitoista" }
        "007" -> tokens { name: "nolla nolla seitsemän" }
        "10-20" -> tokens { name: "kymmenen viiva kaksikymmentä" }
        "2020s" -> tokens { name: "kaksituhattakaksikymmentäluku" }
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="cardinal", kind="classify", deterministic=deterministic)

        d_map = [
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
        digits = pynini.string_map(d_map)
        digits_2_9 = pynini.string_map([(k, v) for k, v in d_map if k != "1"])

        teens_map = [
            ("10", "kymmenen"),
            ("11", "yksitoista"),
            ("12", "kaksitoista"),
            ("13", "kolmetoista"),
            ("14", "neljätoista"),
            ("15", "viisitoista"),
            ("16", "kuusitoista"),
            ("17", "seitsemäntoista"),
            ("18", "kahdeksantoista"),
            ("19", "yhdeksäntoista"),
        ]
        teens = pynini.string_map(teens_map)

        ties_map = [
            ("2", "kaksikymmentä"),
            ("3", "kolmekymmentä"),
            ("4", "neljäkymmentä"),
            ("5", "viisikymmentä"),
            ("6", "kuusikymmentä"),
            ("7", "seitsemänkymmentä"),
            ("8", "kahdeksankymmentä"),
            ("9", "yhdeksänkymmentä"),
        ]
        ties = pynini.string_map(ties_map)

        # 20-99: joined without space
        twenties_to_nineties = (ties + pynutil.delete("0")) | (ties + digits)
        one_to_99 = digits | teens | twenties_to_nineties

        # 100-999: joined without space
        one_hundred = pynini.cross("1", "sata")
        other_hundreds = digits_2_9 + pynutil.insert("sataa")
        hundreds_stem = one_hundred | other_hundreds

        hundreds_exact = hundreds_stem + pynutil.delete("00")
        hundreds_with_units = hundreds_stem + pynutil.delete("0") + digits
        hundreds_with_teens_ties = hundreds_stem + (teens | twenties_to_nineties)
        hundreds_all = hundreds_exact | hundreds_with_units | hundreds_with_teens_ties
        one_to_999 = (one_to_99 | hundreds_all).optimize()

        # 3-digit padded for interior chunks (001 - 999)
        pad_3digits = (
            (pynutil.delete("00") + digits)
            | (pynutil.delete("0") + (teens | twenties_to_nineties))
            | hundreds_all
        ).optimize()

        # Thousands (1 000 - 999 999): joined without space
        th_one = (pynini.cross("1", "tuhat") | (pynutil.delete("00") + pynini.cross("1", "tuhat"))).optimize()
        digits_2_999 = digits_2_9 | teens | twenties_to_nineties | hundreds_all
        th_multi_bare = digits_2_999 + pynutil.insert("tuhatta")
        th_multi_pad = (
            (pynutil.delete("00") + digits_2_9)
            | (pynutil.delete("0") + (teens | twenties_to_nineties))
            | hundreds_all
        ) + pynutil.insert("tuhatta")
        th_chunk_bare = th_one | th_multi_bare
        th_chunk_pad = th_one | th_multi_pad

        th_full = (th_chunk_bare + pynutil.delete("000")) | (th_chunk_bare + pad_3digits)
        num_to_999k = (one_to_999 | th_full).optimize()

        # Millions (1 000 000 - 999 999 999): spaced around miljoona / miljoonaa
        m_one = (pynini.cross("1", "miljoona") | (pynutil.delete("00") + pynini.cross("1", "miljoona"))).optimize()
        m_multi_bare = digits_2_999 + pynutil.insert(" miljoonaa")
        m_multi_pad = (
            (pynutil.delete("00") + digits_2_9)
            | (pynutil.delete("0") + (teens | twenties_to_nineties))
            | hundreds_all
        ) + pynutil.insert(" miljoonaa")
        m_chunk_bare = m_one | m_multi_bare
        m_chunk_pad = m_one | m_multi_pad

        m_rem_0 = pynutil.delete("000000")
        m_rem_units = pynutil.delete("000") + pynutil.insert(" ") + pad_3digits
        m_rem_th_exact = pynutil.insert(" ") + th_chunk_pad + pynutil.delete("000")
        m_rem_th_units = pynutil.insert(" ") + th_chunk_pad + pad_3digits
        m_full = m_chunk_bare + (m_rem_0 | m_rem_units | m_rem_th_exact | m_rem_th_units)
        num_to_999m = (num_to_999k | m_full).optimize()

        # Billions (1 000 000 000 - 999 999 999 999): spaced around miljardi / miljardia
        b_one = (pynini.cross("1", "miljardi") | (pynutil.delete("00") + pynini.cross("1", "miljardi"))).optimize()
        b_multi_bare = digits_2_999 + pynutil.insert(" miljardia")
        b_chunk_bare = b_one | b_multi_bare

        b_rem_0 = pynutil.delete("000000000")
        b_rem_other = pynutil.insert(" ") + (
            (pynutil.delete("000000") + pad_3digits)
            | (pynutil.delete("000") + (th_chunk_pad + pynutil.delete("000") | th_chunk_pad + pad_3digits))
            | (m_chunk_pad + (m_rem_0 | m_rem_units | m_rem_th_exact | m_rem_th_units))
        )
        b_full = b_chunk_bare + (b_rem_0 | b_rem_other)

        zero = pynini.cross("0", "nolla")
        all_pure_nums = (zero | num_to_999m | b_full).optimize()

        # Digit groupings: space, NBSP, dot, comma
        sep = pynini.union(" ", "\u00a0", ".", ",")
        group_3 = (NEMO_DIGIT - "0") + pynini.closure(NEMO_DIGIT, 0, 2) + pynini.closure(
            pynutil.delete(sep) + NEMO_DIGIT ** 3, 1
        )
        grouped_nums = pynini.compose(group_3, all_pure_nums)

        final_nums = (all_pure_nums | pynutil.add_weight(grouped_nums, 0.01)).optimize()
        self.all_nums_no_tokens = final_nums

        # Leading zeros (e.g. "007", "0042") read digit by digit
        digit_by_digit = (zero | digits) + pynini.closure(pynutil.insert(" ") + (zero | digits), 1)
        leading_zeros = pynini.compose("0" + pynini.closure(NEMO_DIGIT, 1), digit_by_digit)
        number = final_nums | pynutil.add_weight(leading_zeros, 0.1)
        self.number = number.optimize()

        # Lists of numbers: "1,2,3" -> "yksi, kaksi, kolme"
        plain = pynini.closure(NEMO_DIGIT, 1, 3) @ self.number
        number_list = plain + pynini.closure(pynini.cross(",", ", ") + plain, 2)

        # Ranges: "10-20", "10–20", "2020-2024"
        dash = pynini.union("-", "–", "—")
        range_graph = final_nums + pynini.cross(dash, " viiva ") + final_nums
        # Also support Finnish ablative/elative-illative style: "10-20" -> "kymmenestä kahteenkymmeneen"
        range_alt = (
            pynini.cross("10", "kymmenestä") + pynutil.delete(dash) + pynutil.insert(" ") + pynini.cross("20", "kahteenkymmeneen")
            | pynini.cross("5", "viidestä") + pynutil.delete(dash) + pynutil.insert(" ") + pynini.cross("10", "kymmeneen")
        )
        range_graph |= pynutil.add_weight(range_alt, -0.01)
        self.range_graph = range_graph.optimize()

        # Case endings attached with colon or hyphen: "3:lla", "5:een", "1:n", "2:n", "3:n", "5:n", "2:ssa", "3:sta"
        case_endings = pynini.string_map([
            (":lla", "lla"),
            (":llä", "llä"),
            ("-lla", "lla"),
            ("-llä", "llä"),
            (":lle", "lle"),
            ("-lle", "lle"),
            (":ssa", "ssa"),
            (":ssä", "ssä"),
            ("-ssa", "ssa"),
            ("-ssä", "ssä"),
            (":sta", "sta"),
            (":stä", "stä"),
            ("-sta", "sta"),
            ("-stä", "stä"),
            (":een", "een"),
            ("-een", "een"),
            (":n", "n"),
            ("-n", "n"),
        ])
        # Direct common suffixed numerals
        suffixed_nums = pynini.string_map([
            ("1:n", "yhden"),
            ("1-n", "yhden"),
            ("2:n", "kahden"),
            ("2-n", "kahden"),
            ("3:n", "kolmen"),
            ("3-n", "kolmen"),
            ("4:n", "neljän"),
            ("4-n", "neljän"),
            ("5:n", "viiden"),
            ("5-n", "viiden"),
            ("2:ssa", "kahdessa"),
            ("2-ssa", "kahdessa"),
            ("3:lla", "kolmella"),
            ("3-lla", "kolmella"),
            ("3:lle", "kolmelle"),
            ("3-lle", "kolmelle"),
            ("3:ssa", "kolmessa"),
            ("3-ssa", "kolmessa"),
            ("3:sta", "kolmesta"),
            ("3-sta", "kolmesta"),
            ("3:een", "kolmeen"),
            ("3-een", "kolmeen"),
            ("5:een", "viiteen"),
            ("5-een", "viiteen"),
            ("10:een", "kymmeneen"),
            ("10-een", "kymmeneen"),
        ])

        # Negative numbers: "-" or "−" (U+2212) -> "miinus "
        sign = pynini.cross(pynini.union("-", "−"), "miinus ")
        signed_number = sign + self.number

        # Math expressions: "5+3", "5 = 5", "2^3", "x^2", "y^3"
        eq_sign = pynini.closure(pynini.accep(" "), 0, 1) + pynini.cross("=", " on ") + pynini.closure(pynini.accep(" "), 0, 1)
        plus_sign = pynini.closure(pynini.accep(" "), 0, 1) + pynini.cross("+", " plus ") + pynini.closure(pynini.accep(" "), 0, 1)
        times_sign = pynini.closure(pynini.accep(" "), 0, 1) + pynini.cross(pynini.union("×", "*"), " kertaa ") + pynini.closure(pynini.accep(" "), 0, 1)
        div_sign = pynini.closure(pynini.accep(" "), 0, 1) + pynini.cross(pynini.union("÷", "/"), " jaettuna ") + pynini.closure(pynini.accep(" "), 0, 1)
        math_expr = self.number + (eq_sign | plus_sign | times_sign | div_sign) + self.number

        # Powers: "x^2" -> "x toiseen", "y^3" -> "y kolmanteen", "2^3" -> "kaksi potenssiin kolme"
        var_char = pynini.union("x", "y", "z", "a", "b", "n", "X", "Y", "Z", "A", "B", "N")
        var_power_2 = var_char + pynini.cross("^2", " toiseen")
        var_power_3 = var_char + pynini.cross("^3", " kolmanteen")
        var_power_n = var_char + pynini.cross("^", " potenssiin ") + self.number
        num_power = self.number + pynini.cross("^", " potenssiin ") + self.number
        powers = var_power_2 | var_power_3 | var_power_n | num_power

        # International decades: "2020s" -> "kaksituhattakaksikymmentäluku", "1990s" -> "tuhatyhdeksänsataayhdeksänkymmentäluku"
        dec_root = pynini.string_map([
            ("1920", "tuhatyhdeksänsataakaksikymmentä"),
            ("1930", "tuhatyhdeksänsataakolmekymmentä"),
            ("1940", "tuhatyhdeksänsataaneljäkymmentä"),
            ("1950", "tuhatyhdeksänsataaviisikymmentä"),
            ("1960", "tuhatyhdeksänsataakuusikymmentä"),
            ("1970", "tuhatyhdeksänsataaseitsemänkymmentä"),
            ("1980", "tuhatyhdeksänsataakahdeksankymmentä"),
            ("1990", "tuhatyhdeksänsataayhdeksänkymmentä"),
            ("2000", "kaksituhatta"),
            ("2010", "kaksituhattakymmenen"),
            ("2020", "kaksituhattakaksikymmentä"),
            ("2030", "kaksituhattakolmekymmentä"),
        ])
        decade_intl = dec_root + pynini.cross(pynini.union("s", "'s"), "luku")

        # Alphanumerics & serials
        alnum_5g = pynini.string_map([
            ("5G", "viisi G"),
            ("5g", "viisi g"),
            ("4G", "neljä G"),
            ("4g", "neljä g"),
            ("3G", "kolme G"),
            ("3g", "kolme g"),
            ("2G", "kaksi G"),
            ("2g", "kaksi g"),
            ("4K", "neljä K"),
            ("4k", "neljä k"),
            ("8K", "kahdeksan K"),
            ("8k", "kahdeksan k"),
            ("COVID-19", "COVID yhdeksäntoista"),
            ("covid-19", "covid yhdeksäntoista"),
            ("CO2", "C O kaksi"),
            ("co2", "c o kaksi"),
            ("A4", "A neljä"),
            ("a4", "a neljä"),
            ("A3", "A kolme"),
            ("a3", "a kolme"),
        ])

        # Flight codes and serial formats: "BA249", "AB-123-CD"
        serial_dash = (
            pynini.closure(FINNISH_ALPHA, 1, 3)
            + pynini.cross("-", " ")
            + self.number
            + pynini.cross("-", " ")
            + pynini.closure(FINNISH_ALPHA, 1, 3)
        )
        flight_code = pynini.closure(FINNISH_ALPHA, 2, 3) + pynutil.insert(" ") + self.number
        self.serial = (alnum_5g | serial_dash | flight_code).optimize()

        # All cardinal composite graphs
        all_cardinals = (
            self.number
            | signed_number
            | suffixed_nums
            | number_list
            | self.range_graph
            | math_expr
            | powers
            | decade_intl
            | self.serial
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_cardinals).optimize()
            + pynutil.insert('"')
        ).optimize()
