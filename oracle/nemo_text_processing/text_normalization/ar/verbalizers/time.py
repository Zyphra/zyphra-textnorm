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

from nemo_text_processing.text_normalization.ar.graph_utils import (
    NEMO_NOT_QUOTE,
    GraphFst,
    delete_preserve_order,
    delete_space,
)


class TimeFst(GraphFst):
    """
    Finite state transducer for verbalizing time, e.g.
        time { hours: "العاشرة" minutes: "والنصف" preserve_order: true } -> "الساعة العاشرة والنصف"
        time { hours: "الثانية" minutes: "وخمس دقائق" suffix: "مساءً" preserve_order: true }
            -> "الساعة الثانية وخمس دقائق مساءً"
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="time", kind="verbalize", deterministic=deterministic)

        def field(name):
            return (
                delete_space
                + pynutil.delete(f'{name}: "')
                + pynini.closure(NEMO_NOT_QUOTE, 1)
                + pynutil.delete('"')
            )

        def optional(name):
            return pynini.closure(pynutil.insert(" ") + field(name), 0, 1)

        graph = (
            pynutil.insert("الساعة ")
            + field("hours")
            + optional("minutes")
            + optional("seconds")
            + optional("suffix")
            + optional("zone")
        )
        self.fst = self.delete_tokens(graph + delete_preserve_order).optimize()
