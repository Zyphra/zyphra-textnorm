# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from nemo_text_processing.text_normalization.el.graph_utils import (
    MINUS,
    GraphFst,
)
from nemo_text_processing.text_normalization.el.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.el.taggers.decimal import DecimalFst
from nemo_text_processing.text_normalization.el.taggers.fraction import FractionFst


class MeasureFst(GraphFst):
    """
    Finite state transducer for classifying Greek measurement units, rates, percentages and temperatures:
        "50 kg" / "50kg" -> πενήντα κιλά
        "100 m" / "100m" -> εκατό μέτρα
        "250 ml" / "250ml" -> διακόσια πενήντα χιλιοστόλιτρα
        "1.5 km" / "1,5km" -> ένα κόμμα πέντε χιλιόμετρα
        "37°C" -> τριάντα επτά βαθμοί Κελσίου
        "-15°C" -> μείον δεκαπέντε βαθμοί Κελσίου
        "120 km/h" / "120km/h" -> εκατόν είκοσι χιλιόμετρα την ώρα
        "64 GB" / "64GB" -> εξήντα τέσσερα γιγαμπάιτ
        "2.4 GHz" / "2,4GHz" -> δύο κόμμα τέσσερα γιγαχέρτζ
        "10 Gbps" -> δέκα γιγαμπίτ το δευτερόλεπτο
        "100 Mbps" -> εκατό μεγαμπίτ το δευτερόλεπτο
        "5000 mAh" -> πέντε χιλιάδες μιλιαμπερώρες
        "50 kWh" -> πενήντα κιλοβατώρες
        "1013 hPa" -> χίλια δεκατρία εκατοπασκάλ
        "250 kcal" -> διακόσιες πενήντα χιλιοθερμίδες
        "60 dB" -> εξήντα ντεσιμπέλ
        "100 Ω" -> εκατό ωμ
        "50 µg" -> πενήντα μικρογραμμάρια
        "10 µm" -> δέκα μικρόμετρα
        "100 m²" -> εκατό τετραγωνικά μέτρα
        "5 m³" -> πέντε κυβικά μέτρα
        "5%" -> πέντε τοις εκατό
        "5‰" -> πέντε τοις χιλίοις
        "5-10 kg" -> πέντε έως δέκα κιλά
        "10-15%" -> δέκα έως δεκαπέντε τοις εκατό
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        decimal: DecimalFst = None,
        fraction: FractionFst = None,
        deterministic: bool = True,
    ):
        super().__init__(name="measure", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)
        if fraction is None:
            fraction = FractionFst(cardinal=cardinal, deterministic=deterministic)

        pure_cardinal = cardinal.pure_cardinal
        decimal_core = decimal.decimal_core
        vulgar_fractions = fraction.vulgar_graph

        num_graph = pure_cardinal | decimal_core | vulgar_fractions
        fem_num_graph = cardinal.fem_cardinal | decimal_core | vulgar_fractions
        masc_num_graph = cardinal.masc_cardinal | decimal_core | vulgar_fractions

        # Unit mapping table: (pattern, singular_reading, plural_reading)
        units_table = [
            # Length
            (["km", "χλμ.", "χλμ"], "χιλιόμετρο", "χιλιόμετρα"),
            (["m", "μ.", "μ"], "μέτρο", "μέτρα"),
            (["cm", "εκ.", "εκ"], "εκατοστό", "εκατοστά"),
            (["mm", "χιλ.", "χιλ"], "χιλιοστό", "χιλιοστά"),
            (["µm", "μm"], "μικρόμετρο", "μικρόμετρα"),
            (["in", "ίντσες"], "ίντσα", "ίντσες"),
            (["ft", "πόδια"], "πόδι", "πόδια"),
            # Mass
            (["kg", "κιλά", "κ."], "κιλό", "κιλά"),
            (["g", "γρ.", "γρ"], "γραμμάριο", "γραμμάρια"),
            (["mg"], "χιλιοστογραμμάριο", "χιλιοστογραμμάρια"),
            (["µg", "μg"], "μικρογραμμάριο", "μικρογραμμάρια"),
            (["t", "τόνοι"], "τόνος", "τόνοι"),
            (["lb", "λίβρες"], "λίβρα", "λίβρες"),
            # Volume
            (["l", "L", "lt", "λ.", "λ"], "λίτρο", "λίτρα"),
            (["ml", "mL", "μλ"], "χιλιοστόλιτρο", "χιλιοστόλιτρα"),
            # Speed
            (["km/h", "χλμ/ω", "χλμ/ώρα"], "χιλιόμετρο την ώρα", "χιλιόμετρα την ώρα"),
            (["m/s"], "μέτρο το δευτερόλεπτο", "μέτρα το δευτερόλεπτο"),
            (["mph"], "μίλι την ώρα", "μίλια την ώρα"),
            # Area & Volume
            (["m²", "τ.μ.", "τ.μ"], "τετραγωνικό μέτρο", "τετραγωνικά μέτρα"),
            (["km²", "τ.χλμ.", "τ.χλμ"], "τετραγωνικό χιλιόμετρο", "τετραγωνικά χιλιόμετρα"),
            (["cm²"], "τετραγωνικό εκατοστό", "τετραγωνικά εκατοστά"),
            (["m³", "κ.μ.", "κ.μ"], "κυβικό μέτρο", "κυβικά μέτρα"),
            (["cm³", "κ.εκ.", "κ.εκ"], "κυβικό εκατοστό", "κυβικά εκατοστά"),
            # Temperature
            (["°C", "℃"], "βαθμός Κελσίου", "βαθμοί Κελσίου"),
            (["°F", "℉"], "βαθμός Φαρενάιτ", "βαθμοί Φαρενάιτ"),
            (["°"], "βαθμός", "βαθμοί"),
            (["K"], "κέλβιν", "κέλβιν"),
            # Computing & Data
            (["B", "byte", "bytes"], "μπάιτ", "μπάιτ"),
            (["KB", "Kb"], "κιλομπάιτ", "κιλομπάιτ"),
            (["MB", "Mb"], "μεγαμπάιτ", "μεγαμπάιτ"),
            (["GB", "Gb"], "γιγαμπάιτ", "γιγαμπάιτ"),
            (["TB", "Tb"], "τεραμπάιτ", "τεραμπάιτ"),
            (["bps"], "μπιτ το δευτερόλεπτο", "μπιτ το δευτερόλεπτο"),
            (["kbps"], "κιλομπίτ το δευτερόλεπτο", "κιλομπίτ το δευτερόλεπτο"),
            (["Mbps"], "μεγαμπίτ το δευτερόλεπτο", "μεγαμπίτ το δευτερόλεπτο"),
            (["Gbps"], "γιγαμπίτ το δευτερόλεπτο", "γιγαμπίτ το δευτερόλεπτο"),
            # Frequency & Electrical & Physics
            (["Hz"], "χερτζ", "χερτζ"),
            (["kHz"], "κιλοχέρτζ", "κιλοχέρτζ"),
            (["MHz"], "μεγαχέρτζ", "μεγαχέρτζ"),
            (["GHz"], "γιγαχέρτζ", "γιγαχέρτζ"),
            (["W", "Watt", "βατ"], "βατ", "βατ"),
            (["kW"], "κιλοβάτ", "κιλοβάτ"),
            (["MW"], "μεγαβάτ", "μεγαβάτ"),
            (["kWh"], "κιλοβατώρες", "κιλοβατώρες"),
            (["V", "βολτ"], "βολτ", "βολτ"),
            (["A", "αμπέρ"], "αμπέρ", "αμπέρ"),
            (["mA"], "μιλιαμπέρ", "μιλιαμπέρ"),
            (["mAh"], "μιλιαμπερώρες", "μιλιαμπερώρες"),
            (["Ω", "Ω"], "ωμ", "ωμ"),
            (["Pa"], "πασκάλ", "πασκάλ"),
            (["hPa"], "εκατοπασκάλ", "εκατοπασκάλ"),
            (["bar", "μπαρ"], "μπαρ", "μπαρ"),
            (["cal"], "θερμίδα", "θερμίδες"),
            (["kcal"], "χιλιοθερμίδα", "χιλιοθερμίδες"),
            (["dB"], "ντεσιμπέλ", "ντεσιμπέλ"),
            # Time
            (["h", "ώ", "ωρ."], "ώρα", "ώρες"),
            (["min", "λεπ.", "λεπ"], "λεπτό", "λεπτά"),
            (["s", "sec", "δευτ.", "δευτ"], "δευτερόλεπτο", "δευτερόλεπτα"),
            (["ms"], "χιλιοστό του δευτερολέπτου", "χιλιοστά του δευτερολέπτου"),
        ]

        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        fem_unit_keys = {"cal", "kcal", "in", "ίντσες", "lb", "λίβρες", "h", "ώ", "ωρ.", "kWh", "mAh"}
        masc_unit_keys = {"t", "τόνοι", "°", "°C", "℃", "°F", "℉"}
        unit_graphs = []
        for symbols, sing, plur in units_table:
            sym_fst = pynini.union(*symbols)
            u_sing = pynutil.delete(sym_fst) + pynutil.insert(f" {sing}")
            u_plur = pynutil.delete(sym_fst) + pynutil.insert(f" {plur}")

            is_fem = any(s in fem_unit_keys for s in symbols)
            if is_fem:
                g_one = pynini.cross("1", "μία") + opt_space + u_sing
                num_other = pynini.difference(pynini.project(fem_num_graph, "input"), "1") @ fem_num_graph
            elif any(s in masc_unit_keys for s in symbols):
                g_one = pynini.cross("1", "ένας") + opt_space + u_sing
                num_other = pynini.difference(pynini.project(masc_num_graph, "input"), "1") @ masc_num_graph
            else:
                g_one = pynini.cross("1", "ένα") + opt_space + u_sing
                num_other = pynini.difference(pynini.project(num_graph, "input"), "1") @ num_graph
            g_other = num_other + opt_space + u_plur

            unit_graphs.append(g_one | g_other)

        units_fst = pynini.union(*unit_graphs).optimize()

        # Percent and Permille: "5%", "12,5%", "99.9%", "5‰"
        pct_sym = pynutil.delete("%") + pynutil.insert(" τοις εκατό")
        permille_sym = pynutil.delete("‰") + pynutil.insert(" τοις χιλίοις")
        pct_graph = num_graph + opt_space + (pct_sym | permille_sym)

        # Negatives for units / temperatures / percentages: "-15°C", "-5%", "-3 °C"
        neg_prefix = pynini.cross(MINUS, "μείον ")
        neg_measures = neg_prefix + (units_fst | pct_graph)

        # Modifiers: "~10 km", "±10%"
        approx_prefix = pynini.cross("~", "περίπου ")
        plus_minus_prefix = pynini.cross("±", "συν πλην ")
        mod_prefix = approx_prefix | plus_minus_prefix
        mod_measures = mod_prefix + (units_fst | pct_graph | neg_measures)

        # Ranges: "5-10 kg", "5–10 kg", "10-15%"
        range_dash = pynini.cross(pynini.union("-", "–", "—", " - ", " – ", " — "), " έως ")

        # Range for percentage: "10-15%" -> "δέκα έως δεκαπέντε τοις εκατό"
        range_pct = pure_cardinal + range_dash + pure_cardinal + opt_space + (pct_sym | permille_sym)

        # Range for units: "5-10 kg" -> "πέντε έως δέκα κιλά"
        range_unit_graphs = []
        for symbols, _, plur in units_table:
            sym_fst = pynini.union(*symbols)
            u_plur = pynutil.delete(sym_fst) + pynutil.insert(f" {plur}")
            count = cardinal.fem_cardinal if any(s in fem_unit_keys for s in symbols) else (
                cardinal.masc_cardinal if any(s in masc_unit_keys for s in symbols) else pure_cardinal
            )
            rg = count + range_dash + count + opt_space + u_plur
            range_unit_graphs.append(rg)
        range_units = pynini.union(*range_unit_graphs).optimize()

        measure_ranges = range_pct | range_units

        all_measures = (
            units_fst
            | pct_graph
            | neg_measures
            | mod_measures
            | measure_ranges
        ).optimize()

        self.fst = all_measures
