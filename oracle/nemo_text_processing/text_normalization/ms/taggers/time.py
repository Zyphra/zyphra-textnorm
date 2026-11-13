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
from nemo_text_processing.text_normalization.ms.utils import get_abs_path


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Malay time (":" or "." between hours and minutes, plus ranges), e.g.
        "10:30" -> time { hours: "sepuluh" minutes: "tiga puluh" preserve_order: true }
        "pukul 10.30" -> time { hours: "sepuluh" minutes: "tiga puluh" preserve_order: true }
        "pukul 08:00 MYT" -> time { hours: "lapan" zone: "M Y T" preserve_order: true }
        "jam 7" -> time { prefix: "jam" hours: "tujuh" preserve_order: true }
        "10:30:15" -> time { hours: "sepuluh" minutes: "tiga puluh" seconds: "lima belas" preserve_order: true }
        "9:00-17:00" -> time { hours: "sembilan hingga pukul tujuh belas" preserve_order: true }

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

        colon_separator = pynutil.delete(":")
        dot_separator = pynutil.delete(".")

        hm_colon = hours + colon_separator + (pynutil.delete("00") | minutes)
        hms_colon = hours + colon_separator + (pynutil.delete("00") | minutes) + colon_separator + seconds

        # Dot separator is allowed with ".00" or when prefixed by pukul/jam
        hm_dot_zero = hours + dot_separator + pynutil.delete("00")

        # Time ranges: "9:00-17:00", "09:00–17:00"
        plain_hm = hour_padded + colon_separator + (
            pynutil.delete("00") | (pynutil.insert(" ") + minute + pynutil.insert(" minit"))
        )
        plain_hm |= hour_padded + dot_separator + (
            pynutil.delete("00") | (pynutil.insert(" ") + minute + pynutil.insert(" minit"))
        )
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        range_sep = opt_sp + pynini.cross(pynini.union("-", "–"), " hingga pukul ") + opt_sp
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

        # Prefixed forms allow dot separator freely: "pukul 10.30", "pukul 14.00"
        prefixed_dot = prefix + hours + dot_separator + (pynutil.delete("00") | minutes)

        bare_times = hm_colon | hms_colon | hm_dot_zero | hm_range
        graph = pynini.closure(prefix, 0, 1) + bare_times + zone
        graph |= prefixed_dot + zone
        graph |= prefix + hours + zone
        graph += pynutil.insert(" preserve_order: true")
        self.fst = self.add_tokens(graph).optimize()
