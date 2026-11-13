# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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
from pynini.lib import pynutil, rewrite

from nemo_text_processing.text_normalization.en.graph_utils import NEMO_DIGIT, GraphFst
from nemo_text_processing.text_normalization.ru.taggers.number_names import (
    CATEGORIES,
    ENDS_IN,
    plural_category,
)

_HOUR = ("masc", ("час", "часа", "часов"))
_MINUTE = ("fem", ("минута", "минуты", "минут"))
_SECOND = ("fem", ("секунда", "секунды", "секунд"))

_HOUR_GEN = ("masc", ("часа", "часов", "часов"))
_MINUTE_GEN = ("fem", ("минуты", "минут", "минут"))


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time, e.g.
        "13:05" -> time { hours: "тринадцать часов пять минут" }
        "02:00" -> "два часа", "12:30:45" -> "двенадцать часов тридцать минут сорок пять секунд",
        "2:30 pm" -> "два часа тридцать минут дня",
        "9:00-17:00" -> "с девяти часов до семнадцати часов"
    A time from 1:01 to 11:59 (no seconds, no am / pm) is read the colloquial way, counting towards the next hour:
        "08:07" -> "семь минут девятого", "08:30" -> "половина девятого", "05:45" -> "без пятнадцати минут шесть"
    """

    def __init__(self, number_names: dict, deterministic: bool = True):
        super().__init__(name="time", kind="classify", deterministic=deterministic)

        cardinal = number_names['cardinal']
        cardinal_gen = number_names['cardinal_gen']

        def counted(digits, noun, case_dict=cardinal):
            gender, forms = noun
            graph = None
            for category, form in zip(CATEGORIES, forms):
                part = pynini.compose(pynini.compose(digits, ENDS_IN[category]), case_dict[gender])
                part += pynutil.insert(" " + form)
                graph = part if graph is None else graph | part
            return graph.optimize()

        def spell(fst, digits):
            return rewrite.top_rewrite(digits, fst)

        hour_digits = (pynini.closure("0", 0, 1) + NEMO_DIGIT) | ("1" + NEMO_DIGIT) | ("2" + pynini.union(*"0123"))
        sixty = pynini.union(*"012345") + NEMO_DIGIT
        sixty_not_zero = pynini.difference(sixty, "00")
        hours = counted(hour_digits, _HOUR)
        minutes = counted(sixty, _MINUTE)
        seconds = counted(sixty, _SECOND)
        colon = pynini.cross(":", " ")

        # "13:05", "02:00" -> "два часа", "12:30:45"
        plain = (hours + pynutil.delete(":00")) | (hours + colon + pynini.compose(sixty_not_zero, minutes))
        plain |= hours + colon + minutes + colon + seconds

        # Genitive time for ranges ("9:00-17:00" -> "с девяти часов до семнадцати часов", "9:30–18:30" -> "с девяти часов тридцати минут до восемнадцати часов тридцати минут")
        hours_gen = counted(hour_digits, _HOUR_GEN, case_dict=cardinal_gen)
        minutes_gen = counted(sixty_not_zero, _MINUTE_GEN, case_dict=cardinal_gen)
        plain_gen = ((hours_gen + pynutil.delete(":00")) | (hours_gen + colon + minutes_gen)).optimize()
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)
        range_sep = opt_sp + pynini.cross(pynini.union("-", "–"), " до ") + opt_sp
        time_range = pynutil.insert("с ") + plain_gen + range_sep + plain_gen

        # colloquial for 1:01 - 11:59
        past = pynini.union(*[f"{m:02d}" for m in range(1, 30)])
        colloquial = []
        for h in range(1, 12):
            next_ordinal = spell(number_names['ordinal']['masc_gen'], str(h + 1))
            next_cardinal = spell(cardinal['masc'], str(h + 1))
            written = pynini.union(*{str(h), f"{h:02d}"}) + ":"
            colloquial.append(
                pynutil.delete(written) + pynini.compose(past, minutes) + pynutil.insert(" " + next_ordinal)
            )
            colloquial.append(pynini.cross(written + "30", "половина " + next_ordinal))
            for m in range(31, 60):
                left = 60 - m
                noun = "минуты" if plural_category(left) == "one" else "минут"
                spoken = f"без {spell(number_names['cardinal_gen']['fem'], str(left))} {noun} {next_cardinal}"
                colloquial.append(pynini.cross(written + f"{m:02d}", spoken))
        colloquial = pynini.union(*colloquial).optimize()

        # "2:30 pm", "9 am", "11:15 a.m." -> the hour as written and the part of the day
        am = pynini.union("am", "AM", "a.m.", "A.M.")
        pm = pynini.union("pm", "PM", "p.m.", "P.M.")
        night = pynini.union("12", "1", "01", "2", "02", "3", "03", "4", "04")
        day = pynini.union("5", "05", "6", "06", "7", "07", "8", "08", "9", "09", "10", "11")
        period = {"ночи": (night, am), "утра": (day, am), "дня": (night, pm), "вечера": (day, pm)}
        clock = None
        for word, (hour_set, marker) in period.items():
            hour = pynini.compose(hour_set, hours)
            graph_c = (hour + pynini.closure(pynutil.delete(":00"), 0, 1)) | (
                hour + colon + pynini.compose(sixty_not_zero, minutes)
            )
            graph_c += pynini.cross(pynini.closure(" ", 0, 1) + marker, " " + word)
            clock = graph_c if clock is None else clock | graph_c

        # Optional "~" before time ("~14:30" -> "около четырнадцати часов тридцати минут")
        approx_time = pynini.cross("~", "около ") + opt_sp + plain_gen

        graph = plain | pynutil.add_weight(colloquial, -0.1) | clock | time_range | approx_time
        self.final_graph = (pynutil.insert("hours: \"") + graph + pynutil.insert("\"")).optimize()
        self.fst = self.add_tokens(self.final_graph).optimize()
