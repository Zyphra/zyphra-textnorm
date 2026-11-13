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
from nemo_text_processing.text_normalization.id.utils import get_abs_path


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time ("." or ":" between hours and minutes, plus ranges), e.g.
        "10.30" -> time { hours: "sepuluh" minutes: "tiga puluh" preserve_order: true }
        "pukul 08:00 WIB" -> time { hours: "delapan" zone: "W I B" preserve_order: true }
        "jam 7" -> time { prefix: "jam" hours: "tujuh" preserve_order: true }
        "10:30:15" -> time { hours: "sepuluh" minutes: "tiga puluh" seconds: "lima belas" preserve_order: true }
        "9:00-17:00" -> time { hours: "sembilan sampai pukul tujuh belas" preserve_order: true }

    Args:
        cardinal: CardinalFst
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, cardinal: GraphFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)
        number = cardinal.graph
        optional_zero = pynini.closure(pynutil.delete("0"), 0, 1)
        hour_digits = pynini.union(*[str(x) for x in range(0, 25)])
        hour_padded = (optional_zero + hour_digits) @ number
        minute = (pynutil.delete("0") + (NEMO_DIGIT - "0") | pynini.union(*[str(x) for x in range(10, 60)])) @ number

        hours = pynutil.insert('hours: "') + hour_padded + pynutil.insert('"')
        minutes = pynutil.insert(' minutes: "') + minute + pynutil.insert('"')
        seconds = pynutil.insert(' seconds: "') + minute + pynutil.insert('"')
        separator = pynutil.delete(pynini.union(":", "."))

        hm = hours + separator + (pynutil.delete("00") | minutes)
        hms = hours + pynutil.delete(":") + (pynutil.delete("00") | minutes) + pynutil.delete(":") + seconds

        # Time ranges: "9:00-17:00", "09:00–17:00", "09.00-17.00"
        plain_hm = hour_padded + separator + (
            pynutil.delete("00") | (pynutil.insert(" lewat ") + minute + pynutil.insert(" menit"))
        )
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        range_sep = opt_sp + pynini.cross(pynini.union("-", "–"), " sampai pukul ") + opt_sp
        hm_range = pynutil.insert('hours: "') + plain_hm + range_sep + plain_hm + pynutil.insert('"')

        zone = pynini.closure(
            pynini.accep(" ")
            + pynutil.insert('zone: "')
            + convert_space(pynini.string_file(get_abs_path("data/time/time_zone.tsv")))
            + pynutil.insert('"'),
            0,
            1,
        )
        pukul = pynutil.delete(pynini.union("pukul ", "Pukul ", "pkl. ", "pkl "))
        jam = pynutil.insert('prefix: "') + pynini.union("jam", "Jam") + pynutil.insert('"') + pynini.accep(" ")
        prefix = pukul | jam
        graph = pynini.closure(prefix, 0, 1) + (hm | hms | hm_range) + zone
        graph |= prefix + hours + zone
        graph += pynutil.insert(" preserve_order: true")
        self.fst = self.add_tokens(graph).optimize()
