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
    NEMO_DIGIT,
    GraphFst,
    convert_space,
)
from nemo_text_processing.text_normalization.th.taggers.cardinal import CardinalFst


class DateFst(GraphFst):
    """
    Finite state transducer for classifying dates, eras, decades, and years in Thai (th).
    Supports:
    - Buddhist Era: พ.ศ. 2567, พ.ศ.๒๕๖๗, พุทธศักราช 2567 -> พุทธศักราชสองพันห้าร้อยหกสิบเจ็ด
    - Christian Era: ค.ศ. 2024, คริสต์ศักราช 2024 -> คริสต์ศักราชสองพันยี่สิบสี่
    - Historical eras: 500 BC -> ห้าร้อยปีก่อนคริสตกาล, 500 AD -> คริสต์ศักราชห้าร้อย
    - Full written dates: 25 ธันวาคม 2024, วันที่ 25 ธันวาคม 2024, 25 ธ.ค. 2567
    - Numeric dates: 2024-12-25, 25/12/2024, 07/03/2026, 07.03.2026
    - Decades: 2020s -> ทศวรรษ 2020, 1990s -> ทศวรรษ 1990 (must NOT match seconds)
    - Year ranges: 1990–1995 -> หนึ่งพันเก้าร้อยเก้าสิบถึงหนึ่งพันเก้าร้อยเก้าสิบห้า
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="date", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        sp = pynutil.delete(" ")

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

        # Months
        month_names = pynini.string_map(
            [
                ("มกราคม", "มกราคม"),
                ("ม.ค.", "มกราคม"),
                ("ม.ค", "มกราคม"),
                ("กุมภาพันธ์", "กุมภาพันธ์"),
                ("ก.พ.", "กุมภาพันธ์"),
                ("ก.พ", "กุมภาพันธ์"),
                ("มีนาคม", "มีนาคม"),
                ("มี.ค.", "มีนาคม"),
                ("มี.ค", "มีนาคม"),
                ("เมษายน", "เมษายน"),
                ("เม.ย.", "เมษายน"),
                ("เม.ย", "เมษายน"),
                ("พฤษภาคม", "พฤษภาคม"),
                ("พ.ค.", "พฤษภาคม"),
                ("พ.ค", "พฤษภาคม"),
                ("มิถุนายน", "มิถุนายน"),
                ("มิ.ย.", "มิถุนายน"),
                ("มิ.ย", "มิถุนายน"),
                ("กรกฎาคม", "กรกฎาคม"),
                ("ก.ค.", "กรกฎาคม"),
                ("ก.ค", "กรกฎาคม"),
                ("สิงหาคม", "สิงหาคม"),
                ("ส.ค.", "สิงหาคม"),
                ("ส.ค", "สิงหาคม"),
                ("กันยายน", "กันยายน"),
                ("ก.ย.", "กันยายน"),
                ("ก.ย", "กันยายน"),
                ("ตุลาคม", "ตุลาคม"),
                ("ต.ค.", "ตุลาคม"),
                ("ต.ค", "ตุลาคม"),
                ("พฤศจิกายน", "พฤศจิกายน"),
                ("พ.ย.", "พฤศจิกายน"),
                ("พ.ย", "พฤศจิกายน"),
                ("ธันวาคม", "ธันวาคม"),
                ("ธ.ค.", "ธันวาคม"),
                ("ธ.ค", "ธันวาคม"),
            ]
        )

        month_numbers = (
            pynini.cross("01", "มกราคม")
            | pynini.cross("1", "มกราคม")
            | pynini.cross("02", "กุมภาพันธ์")
            | pynini.cross("2", "กุมภาพันธ์")
            | pynini.cross("03", "มีนาคม")
            | pynini.cross("3", "มีนาคม")
            | pynini.cross("04", "เมษายน")
            | pynini.cross("4", "เมษายน")
            | pynini.cross("05", "พฤษภาคม")
            | pynini.cross("5", "พฤษภาคม")
            | pynini.cross("06", "มิถุนายน")
            | pynini.cross("6", "มิถุนายน")
            | pynini.cross("07", "กรกฎาคม")
            | pynini.cross("7", "กรกฎาคม")
            | pynini.cross("08", "สิงหาคม")
            | pynini.cross("8", "สิงหาคม")
            | pynini.cross("09", "กันยายน")
            | pynini.cross("9", "กันยายน")
            | pynini.cross("10", "ตุลาคม")
            | pynini.cross("11", "พฤศจิกายน")
            | pynini.cross("12", "ธันวาคม")
        )

        # Days 1 to 31
        day_num = (single_digit | (single_digit + single_digit)) @ (
            (pynutil.delete("0") + cardinal.all_positive) | cardinal.all_positive
        )

        # Years: 1-4 digits
        year_num = cardinal.all_positive

        # 1. Eras & Calendar explicitness
        # Buddhist Era: พ.ศ. 2567, พุทธศักราช 2567
        be_prefix = (
            pynini.cross("พ.ศ. ", "พุทธศักราช")
            | pynini.cross("พ.ศ.", "พุทธศักราช")
            | pynini.cross("พุทธศักราช ", "พุทธศักราช")
            | pynini.cross("พุทธศักราช", "พุทธศักราช")
        )
        be_year = (be_prefix + opt_sp + year_num).optimize()

        # Christian Era: ค.ศ. 2024, คริสต์ศักราช 2024
        ce_prefix = (
            pynini.cross("ค.ศ. ", "คริสต์ศักราช")
            | pynini.cross("ค.ศ.", "คริสต์ศักราช")
            | pynini.cross("คริสต์ศักราช ", "คริสต์ศักราช")
            | pynini.cross("คริสต์ศักราช", "คริสต์ศักราช")
        )
        ce_year = (ce_prefix + opt_sp + year_num).optimize()

        # BC / AD
        bc_suffix = pynini.union(" BC", " B.C.", " BCE", " B.C.E.", " ปีก่อนคริสตกาล")
        ad_suffix = pynini.union(" AD", " A.D.", " CE", " C.E.")
        bc_year = (year_num + pynutil.delete(bc_suffix) + pynutil.insert("ปีก่อนคริสตกาล")).optimize()
        ad_year = (pynutil.insert("คริสต์ศักราช") + year_num + pynutil.delete(ad_suffix)).optimize()

        # 2. Written Dates
        # "25 ธันวาคม 2024", "25 ธ.ค. 2567", "วันที่ 25 ธันวาคม 2024"
        # "25 ธันวาคม 2024", "25 ธ.ค. 2567", "วันที่ 25 ธันวาคม 2024", "วันที่10มกราคม"
        wan_thi_prefix = (
            pynutil.delete("วันที่") + opt_sp
            | pynutil.insert("")
        ) + pynutil.insert("วันที่")
        date_sp = pynini.cross(" ", " ") | pynutil.insert("")

        written_dmy = (
            wan_thi_prefix
            + day_num
            + date_sp
            + month_names
            + date_sp
            + (be_year | ce_year | year_num)
        ).optimize()

        written_dm = (
            wan_thi_prefix
            + day_num
            + date_sp
            + month_names
        ).optimize()
        wan_thi_day = (
            pynini.cross("วันที่ ", "วันที่")
            | pynini.cross("วันที่", "วันที่")
        ) + day_num

        # 3. Numeric Dates
        # ISO format: 2024-12-25
        four_digits = (single_digit**4) @ year_num
        two_digits = (single_digit**2)
        one_or_two_digits = (single_digit | two_digits)

        iso_date = (
            pynutil.insert('date { year: "')
            + four_digits
            + pynutil.insert('" month: "')
            + pynutil.delete("-")
            + (two_digits @ month_numbers)
            + pynutil.insert('" day: "วันที่')
            + pynutil.delete("-")
            + (two_digits @ ((pynutil.delete("0") + cardinal.all_positive) | cardinal.all_positive))
            + pynutil.insert('" }')
        ).optimize()

        # Slash format: 25/12/2024, 07/03/2026
        slash_date = (
            pynutil.insert("วันที่")
            + (one_or_two_digits @ ((pynutil.delete("0") + cardinal.all_positive) | cardinal.all_positive))
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + (one_or_two_digits @ month_numbers)
            + pynutil.delete("/")
            + pynutil.insert(" ")
            + four_digits
        ).optimize()

        # Dot format: 07.03.2026
        dot_date = (
            pynutil.insert("วันที่")
            + (one_or_two_digits @ ((pynutil.delete("0") + cardinal.all_positive) | cardinal.all_positive))
            + pynutil.delete(".")
            + pynutil.insert(" ")
            + (one_or_two_digits @ month_numbers)
            + pynutil.delete(".")
            + pynutil.insert(" ")
            + four_digits
        ).optimize()

        # 4. Decades: 2020s, 1990s -> ทศวรรษ 2020 (Must NOT read as seconds!)
        decade_s = (
            pynutil.insert("ทศวรรษ ")
            + (four_digits)
            + pynutil.delete("s")
        ).optimize()

        # 5. Year ranges: 1990–1995 -> หนึ่งพันเก้าร้อยเก้าสิบถึงหนึ่งพันเก้าร้อยเก้าสิบห้า
        dash = pynini.union("-", "–", "—")
        year_range = (
            four_digits
            + opt_sp
            + pynini.cross(dash, "ถึง")
            + opt_sp
            + four_digits
        ).optimize()

        all_dates = (
            pynutil.add_weight(slash_date, 1.01)
            | pynutil.add_weight(dot_date, 1.01)
            | pynutil.add_weight(written_dmy, 1.02)
            | pynutil.add_weight(written_dm, 1.03)
            | pynutil.add_weight(wan_thi_day, 1.03)
            | pynutil.add_weight(decade_s, 1.03)
            | pynutil.add_weight(be_year, 1.04)
            | pynutil.add_weight(ce_year, 1.04)
            | pynutil.add_weight(bc_year, 1.04)
            | pynutil.add_weight(ad_year, 1.04)
            | pynutil.add_weight(year_range, 1.05)
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_dates)
            + pynutil.insert('"')
        ) | iso_date
        self.fst = self.fst.optimize()
