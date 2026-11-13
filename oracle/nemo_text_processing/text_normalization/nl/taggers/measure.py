# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.en.graph_utils import (
    NEMO_CHAR,
    NEMO_DIGIT,
    NEMO_SIGMA,
    GraphFst,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.nl.graph_utils import (
    NEMO_MINUS,
    wrap_name,
)


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Dutch units of measurement.
    Handles:
    - Glued and unglued standard units: 50kg, 100m, 250ml, 1,5km, 120km/h
    - Temperatures: 37°C, -15°C, 10 °C, -5 °C, 1 °C
    - Area & Volume superscripts: 100 m², 5 m³
    - Computing units: 64GB, 2,4GHz, 10 Gbps, 100 Mbps
    - Electrical & scientific units: 5000 mAh, 50 kWh, 1013 hPa, 250 kcal, 60 dB, 100 Ω, 50 µg, 10 µm
    - Percent & permille: 5%, 50%., 12,5%, 99.9%, -5%, 10-15%, 5‰, 25¢
    - Measure ranges: 5-10 kg
    """

    def __init__(self, cardinal: GraphFst, decimal: GraphFst, deterministic: bool = True):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)
        dash = pynini.union("-", "–", "—")

        # Standard units mapping (all singular in Dutch after numbers)
        unit_pairs = [
            ("km/h", "kilometer per uur"),
            ("kmh", "kilometer per uur"),
            ("km", "kilometer"),
            ("m", "meter"),
            ("cm", "centimeter"),
            ("mm", "millimeter"),
            ("µm", "micrometer"),
            ("μm", "micrometer"),
            ("kg", "kilogram"),
            ("g", "gram"),
            ("mg", "milligram"),
            ("µg", "microgram"),
            ("μg", "microgram"),
            ("l", "liter"),
            ("ml", "milliliter"),
            ("cl", "centiliter"),
            ("dl", "deciliter"),
            ("m²", "vierkante meter"),
            ("km²", "vierkante kilometer"),
            ("cm²", "vierkante centimeter"),
            ("mm²", "vierkante millimeter"),
            ("m³", "kubieke meter"),
            ("km³", "kubieke kilometer"),
            ("cm³", "kubieke centimeter"),
            ("mm³", "kubieke millimeter"),
            ("TB", "terabyte"),
            ("GB", "gigabyte"),
            ("MB", "megabyte"),
            ("KB", "kilobyte"),
            ("kB", "kilobyte"),
            ("GHz", "gigahertz"),
            ("MHz", "megahertz"),
            ("kHz", "kilohertz"),
            ("Hz", "hertz"),
            ("Gbps", "gigabit per seconde"),
            ("Mbps", "megabit per seconde"),
            ("kbps", "kilobit per seconde"),
            ("bps", "bit per seconde"),
            ("mAh", "milliampère-uur"),
            ("Ah", "ampère-uur"),
            ("kWh", "kilowattuur"),
            ("Wh", "wattuur"),
            ("kW", "kilowatt"),
            ("W", "watt"),
            ("MW", "megawatt"),
            ("GW", "gigawatt"),
            ("V", "volt"),
            ("mV", "millivolt"),
            ("kV", "kilovolt"),
            ("A", "ampère"),
            ("mA", "milliampère"),
            ("Ω", "ohm"),
            ("Ω", "ohm"),
            ("hPa", "hectopascal"),
            ("kPa", "kilopascal"),
            ("MPa", "megapascal"),
            ("Pa", "pascal"),
            ("bar", "bar"),
            ("mbar", "millibar"),
            ("kcal", "kilocalorieën"),
            ("cal", "calorieën"),
            ("kJ", "kilojoule"),
            ("J", "joule"),
            ("dB", "decibel"),
            ("sec", "seconden"),
            ("s", "seconden"),
            ("min", "minuten"),
            ("h", "uur"),
            ("uur", "uur"),
            ("¢", "cent"),
            ("‰", "promille"),
            ("%", "procent"),
        ]

        unit_map = pynini.string_map(unit_pairs).optimize()

        # Numbers for measures: integer or decimal, positive or negative
        measure_num = decimal.spoken_decimal | cardinal.cardinal_numbers
        neg_measure_num = pynini.cross(NEMO_MINUS, "min ") + measure_num
        all_measure_num = neg_measure_num | measure_num

        # Temperature: 1 graad Celsius vs N graden Celsius
        temp_1 = (
            pynini.cross("1", "een")
            + opt_space
            + pynini.cross("°C", " graad Celsius")
        )
        temp_1_f = (
            pynini.cross("1", "een")
            + opt_space
            + pynini.cross("°F", " graad Fahrenheit")
        )
        temp_other_c = (
            all_measure_num
            + opt_space
            + pynini.cross("°C", " graden Celsius")
        )
        temp_other_f = (
            all_measure_num
            + opt_space
            + pynini.cross("°F", " graden Fahrenheit")
        )
        temp_bare_deg = (
            all_measure_num
            + opt_space
            + pynini.cross("°", " graden")
        )
        temp_all = (
            pynutil.add_weight(temp_1, 0.95)
            | pynutil.add_weight(temp_1_f, 0.95)
            | pynutil.add_weight(temp_other_c, 0.98)
            | pynutil.add_weight(temp_other_f, 0.98)
            | pynutil.add_weight(temp_bare_deg, 1.0)
        )

        # Standard measures: number + unit (glued or spaced)
        std_measure = (
            all_measure_num
            + opt_space
            + pynutil.insert(" ")
            + unit_map
        )

        # Percent and permille
        percent_sym = pynini.cross("%", " procent") | pynini.cross("‰", " promille")
        percent_measure = all_measure_num + opt_space + percent_sym

        # Ranges: "5-10 kg" -> "vijf tot tien kilogram", "10-15%" -> "tien tot vijftien procent"
        range_measure = (
            measure_num
            + delete_space
            + pynini.cross(dash, " tot ")
            + delete_space
            + (std_measure | percent_measure)
        )

        # Approximations: "~10 km" -> "ongeveer tien kilometer", "±10%" -> "plusminus tien procent"
        approx_measure = (
            pynini.cross("~", "ongeveer ")
            + opt_space
            + (std_measure | temp_all | percent_measure)
        )
        plusminus_measure = (
            pynini.cross("±", "plusminus ")
            + opt_space
            + (std_measure | temp_all | percent_measure)
        )

        self.spoken_measure = (
            pynutil.add_weight(approx_measure, 0.94)
            | pynutil.add_weight(plusminus_measure, 0.94)
            | pynutil.add_weight(range_measure, 0.95)
            | pynutil.add_weight(temp_all, 0.97)
            | pynutil.add_weight(percent_measure, 0.98)
            | pynutil.add_weight(std_measure, 1.0)
        ).optimize()

        self.fst = wrap_name(self.spoken_measure)
