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


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying Danish clock times.
    Handles:
      - 24h & 12h clock times: "12:30" -> "tolv tredive", "14:00" -> "fjorten", "14:05" -> "fjorten nul fem"
      - Times with seconds: "08:15:30" -> "otte femten og tredive sekunder", "12:30:45"
      - Prefixed "kl." / "klokken": "kl. 14:30", "kl. 8"
      - Timezones: "14:30 UTC" -> "fjorten tredive u t c", "09:00 GMT"
      - Time ranges: "9:00-17:00" -> "ni til sytten", "9:30-18:15"
    """

    def __init__(self, cardinal: CardinalFst, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        # Hours 0-23
        hours_map = [
            ("0", "nul"),
            ("00", "nul"),
            ("1", "et"),
            ("01", "et"),
            ("2", "to"),
            ("02", "to"),
            ("3", "tre"),
            ("03", "tre"),
            ("4", "fire"),
            ("04", "fire"),
            ("5", "fem"),
            ("05", "fem"),
            ("6", "seks"),
            ("06", "seks"),
            ("7", "syv"),
            ("07", "syv"),
            ("8", "otte"),
            ("08", "otte"),
            ("9", "ni"),
            ("09", "ni"),
            ("10", "ti"),
            ("11", "elleve"),
            ("12", "tolv"),
            ("13", "tretten"),
            ("14", "fjorten"),
            ("15", "femten"),
            ("16", "seksten"),
            ("17", "sytten"),
            ("18", "atten"),
            ("19", "nitten"),
            ("20", "tyve"),
            ("21", "enogtyve"),
            ("22", "toogtyve"),
            ("23", "treogtyve"),
        ]

        hour_graph = pynini.union(*[pynini.cross(h, spoken) for h, spoken in hours_map])

        # Minutes 00-59
        # "00" can be deleted after hour (14:00 -> fjorten) or read as "nul nul"
        minute_00 = pynutil.delete("00")
        minute_00_spoken = pynini.cross("00", " nul nul")

        minute_single = pynini.union(
            *[
                pynini.cross(f"0{d}", f" nul {name}")
                for d, name in [
                    ("1", "et"),
                    ("2", "to"),
                    ("3", "tre"),
                    ("4", "fire"),
                    ("5", "fem"),
                    ("6", "seks"),
                    ("7", "syv"),
                    ("8", "otte"),
                    ("9", "ni"),
                ]
            ]
        )

        minute_tens = pynutil.insert(" ") + (
            pynini.union(*[str(n) for n in range(10, 60)]) @ cardinal.num_1_to_999_neuter
        )

        # Seconds 00-59
        seconds_graph = (
            pynutil.insert(" og ")
            + (
                pynini.cross("00", "nul")
                | pynini.union(
                    *[
                        pynini.cross(f"0{d}", name)
                        for d, name in [
                            ("1", "et"),
                            ("2", "to"),
                            ("3", "tre"),
                            ("4", "fire"),
                            ("5", "fem"),
                            ("6", "seks"),
                            ("7", "syv"),
                            ("8", "otte"),
                            ("9", "ni"),
                        ]
                    ]
                )
                | cardinal.num_1_to_999_neuter
            )
            + pynutil.insert(" sekunder")
        )

        colon = pynutil.delete(":")
        dot_time = pynutil.delete(".")

        # Prefix "kl." or "klokken"
        kl_prefix = (
            pynini.cross(pynini.union("kl.", "Kl.", "kl", "Kl"), "klokken ")
            | pynini.cross(pynini.union("klokken", "Klokken"), "klokken ")
        )
        opt_kl = pynini.closure(kl_prefix + opt_sp, 0, 1)

        # Timezones
        timezones = pynini.string_map(
            [
                ("UTC", " u t c"),
                ("GMT", " g m t"),
                ("CET", " c e t"),
                ("CEST", " c e s t"),
                ("EST", " e s t"),
                ("EDT", " e d t"),
                ("PST", " p s t"),
                ("PDT", " p d t"),
            ]
        )
        opt_tz = pynini.closure(pynutil.delete(" ") + timezones, 0, 1)

        # Hour + minute combinations:
        # 14:00 -> fjorten (or klokken fjorten)
        h_exact_colon = hour_graph + colon + minute_00
        h_exact_spoken = hour_graph + colon + minute_00_spoken
        h_with_minutes = hour_graph + colon + (minute_single | minute_tens)

        # With seconds: e.g. 08:15:30 -> otte femten og tredive sekunder
        # 10:00:05 -> ti nul nul og fem sekunder
        hms = (
            hour_graph
            + colon
            + (minute_00_spoken | minute_single | minute_tens)
            + colon
            + seconds_graph
        )

        # Bare hour with kl. prefix: "kl. 8" -> "klokken otte", "kl. 14" -> "klokken fjorten"
        bare_h = kl_prefix + opt_sp + hour_graph

        core_time = (hms | h_with_minutes | h_exact_colon | h_exact_spoken | bare_h) + opt_tz
        core_time_with_opt_kl = opt_kl + core_time

        # Time ranges: "9:00-17:00", "09:00–17:00", "9:30-18:15"
        range_dash = pynini.cross(pynini.union("-", "–", "—"), " til ")
        time_range = (
            (core_time_with_opt_kl | hour_graph)
            + opt_sp
            + range_dash
            + opt_sp
            + (core_time_with_opt_kl | hour_graph)
        )

        all_times = (time_range | core_time_with_opt_kl).optimize()

        self.graph = all_times

        final_graph = (
            pynutil.insert('name: "')
            + convert_space(self.graph)
            + pynutil.insert('"')
        ).optimize()

        self.fst = final_graph
