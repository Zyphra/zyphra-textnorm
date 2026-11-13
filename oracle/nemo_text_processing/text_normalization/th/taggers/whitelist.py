# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
    NEMO_CHAR,
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying whitelisted symbols, abbreviations, titles,
    alphanumerics, and math powers in Thai (th).
    Supports:
    - Titles: Dr. Smith -> ดร. Smith
    - Number abbreviation: No. 5, #5 -> หมายเลขห้า
    - Latin abbreviations: etc. -> เป็นต้น
    - Symbols: & -> และ, © 2024 -> ลิขสิทธิ์สองพันยี่สิบสี่, § 12 -> มาตราสิบสอง
    - Alphanumerics: 5G -> ห้าจี, 4K -> สี่เค, CO2 -> CO สอง, COVID-19 -> COVID สิบเก้า
    - Versions: iOS 17.4.1 -> iOS สิบเจ็ดจุดสี่จุดหนึ่ง, v2.0 -> v สองจุดศูนย์
    - Serial codes: AB-123-CD -> AB หนึ่งสองสาม CD
    - Powers: x^2 -> x ยกกำลังสอง, y^3 -> y ยกกำลังสาม, 2^3 -> สองยกกำลังสาม
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True, input_file: str = None):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        thai_to_ascii = pynini.string_map(
            [
                ("๐", "0"),
                ("๑", "1"),
                ("๒", "2"),
                ("๓", "3"),
                ("๔", "4"),
                ("๕", "5"),
                ("๖", "6"),
                ("๗", "7"),
                ("๘", "8"),
                ("๙", "9"),
            ]
        )
        single_digit = thai_to_ascii | NEMO_DIGIT
        digit_words = pynini.string_map(
            [
                ("0", "ศูนย์"),
                ("1", "หนึ่ง"),
                ("2", "สอง"),
                ("3", "สาม"),
                ("4", "สี่"),
                ("5", "ห้า"),
                ("6", "หก"),
                ("7", "เจ็ด"),
                ("8", "แปด"),
                ("9", "เก้า"),
            ]
        )

        # 1. Titles
        titles = pynini.string_map(
            [
                ("Dr. ", "ดร. "),
                ("Dr.", "ดร."),
                ("dr. ", "ดร. "),
                ("dr.", "ดร."),
                ("ดร.", "ดอกเตอร์"),
                ("Mr. ", "นาย "),
                ("Mr.", "นาย"),
                ("Mrs. ", "นาง "),
                ("Mrs.", "นาง"),
                ("Miss ", "นางสาว "),
                ("Prof. ", "ศ. "),
                ("Prof.", "ศ."),
            ]
        )

        # 2. Number abbreviation: No. 5, #5 -> หมายเลขห้า
        no_prefix = (
            pynini.cross("No. ", "หมายเลข")
            | pynini.cross("No.", "หมายเลข")
            | pynini.cross("no. ", "หมายเลข")
            | pynini.cross("no.", "หมายเลข")
            | pynini.cross("Nr. ", "หมายเลข")
            | pynini.cross("Nr.", "หมายเลข")
            | pynini.cross("#", "หมายเลข")
        )
        number_label = (no_prefix + opt_sp + cardinal.all_positive).optimize()

        # 3. Common symbols and words
        symbols = pynini.string_map(
            [
                ("&", "และ"),
                ("etc.", "เป็นต้น"),
                ("ฯลฯ", "เป็นต้น"),
            ]
        )

        # Copyright & Section with following number
        copyright_expr = (
            pynini.cross("©", "ลิขสิทธิ์")
            + opt_sp
            + pynini.closure(pynutil.insert(" ") + cardinal.all_positive, 0, 1)
        )
        section_expr = (
            pynini.cross("§", "มาตรา")
            + opt_sp
            + pynini.closure(pynutil.insert(" ") + cardinal.all_positive, 0, 1)
        )

        # 4. Alphanumerics & Tech abbreviations
        alphanumeric_special = pynini.string_map(
            [
                ("5G", "ห้าจี"),
                ("5g", "ห้าจี"),
                ("4G", "สี่จี"),
                ("4g", "สี่จี"),
                ("3G", "สามจี"),
                ("3g", "สามจี"),
                ("4K", "สี่เค"),
                ("4k", "สี่เค"),
                ("8K", "แปดเค"),
                ("8k", "แปดเค"),
                ("CO2", "CO สอง"),
                ("co2", "co สอง"),
                ("H2O", "H สอง O"),
                ("h2o", "h สอง o"),
                ("COVID-19", "COVID สิบเก้า"),
                ("covid-19", "covid สิบเก้า"),
                ("Covid-19", "Covid สิบเก้า"),
                ("A4", "A สี่"),
                ("a4", "a สี่"),
            ]
        )

        # Multi-dot version strings: iOS 17.4.1 -> iOS สิบเจ็ดจุดสี่จุดหนึ่ง, v2.0 -> v สองจุดศูนย์
        version_num = (
            cardinal.all_positive
            + pynini.cross(".", "จุด")
            + (single_digit @ digit_words)
            + pynini.closure(pynini.cross(".", "จุด") + (single_digit @ digit_words))
        )
        version_prefix = (
            pynini.cross("iOS ", "iOS ")
            | pynini.cross("ios ", "ios ")
            | pynini.cross("v", "v ")
            | pynini.cross("V", "V ")
            | pynini.cross("ver ", "เวอร์ชัน ")
            | pynini.cross("Ver ", "เวอร์ชัน ")
        )
        version_expr = (version_prefix + version_num).optimize()

        # Serial dash codes: AB-123-CD -> AB หนึ่งสองสาม CD
        alpha_code = pynini.closure(NEMO_ALPHA, 1, 3)
        digit_code = pynini.closure(single_digit @ digit_words, 1, 4)
        serial_dash = (
            alpha_code
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + digit_code
            + pynutil.delete("-")
            + pynutil.insert(" ")
            + alpha_code
        ).optimize()

        # 5. Exponents / Powers: x^2 -> x ยกกำลังสอง, 2^3 -> สองยกกำลังสาม
        power_sym = pynini.cross("^", " ยกกำลัง")
        power_num = (
            pynini.cross("2", "สอง")
            | pynini.cross("3", "สาม")
            | cardinal.all_positive
        )
        base = NEMO_ALPHA | (cardinal.all_positive)
        power_expr = (base + power_sym + power_num).optimize()

        graph = (
            pynutil.add_weight(version_expr, 0.01)
            | pynutil.add_weight(serial_dash, 0.02)
            | pynutil.add_weight(power_expr, 0.02)
            | pynutil.add_weight(alphanumeric_special, 0.03)
            | pynutil.add_weight(number_label, 0.04)
            | pynutil.add_weight(copyright_expr, 0.04)
            | pynutil.add_weight(section_expr, 0.04)
            | pynutil.add_weight(titles, 0.05)
            | pynutil.add_weight(symbols, 0.06)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(graph)
            + pynutil.insert('"')
        ).optimize()
