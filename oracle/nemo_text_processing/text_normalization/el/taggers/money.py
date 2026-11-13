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
    NEMO_DIGIT,
    GraphFst,
)
from nemo_text_processing.text_normalization.el.taggers.cardinal import (
    CardinalFst,
    _build_cardinal_maps,
)
from nemo_text_processing.text_normalization.el.taggers.decimal import DecimalFst


class MoneyFst(GraphFst):
    """
    Finite state transducer for classifying Greek currency expressions:
        "€50" / "50 €" -> πενήντα ευρώ
        "€1" / "1 €" -> ένα ευρώ
        "€1.50" / "1,50 €" -> ένα ευρώ και πενήντα λεπτά
        "€99.95" / "99,95 €" -> ενενήντα εννέα ευρώ και ενενήντα πέντε λεπτά
        "€10.00" -> δέκα ευρώ
        "€0.99" -> ενενήντα εννέα λεπτά
        "€0.01" -> ένα λεπτό
        "€50k" -> πενήντα χιλιάδες ευρώ
        "€2.5M" -> δύο κόμμα πέντε εκατομμύρια ευρώ
        "-$12.50" -> μείον δώδεκα δολάρια και πενήντα σεντ
        "$15/h" -> δεκαπέντε δολάρια την ώρα
        "€20/kg" -> είκοσι ευρώ ανά κιλό
        "25¢" -> είκοσι πέντε σεντ
        "10-20 €" -> δέκα έως είκοσι ευρώ
        "€10 - €20" -> δέκα έως είκοσι ευρώ
        "€10-$20" -> δέκα ευρώ έως είκοσι δολάρια
    """

    def __init__(
        self,
        cardinal: CardinalFst = None,
        decimal: DecimalFst = None,
        deterministic: bool = True,
    ):
        super().__init__(name="money", kind="classify", deterministic=deterministic)

        if cardinal is None:
            cardinal = CardinalFst(deterministic=deterministic)
        if decimal is None:
            decimal = DecimalFst(cardinal=cardinal, deterministic=deterministic)

        pure_cardinal = (cardinal.pure_cardinal | decimal.grouped_integers).optimize()
        decimal_core = decimal.decimal_core
        pure_cardinal_all = (pure_cardinal | decimal.grouped_integers).optimize()
        fem_cardinal_all = (
            cardinal.fem_cardinal
            | (decimal.ungroup_numbers @ cardinal.fem_cardinal)
        ).optimize()

        pairs, _ = _build_cardinal_maps()
        pairs_0_99 = [p for p in pairs if len(p[0]) <= 2]
        two_digit_map = pynini.string_map(pairs_0_99)

        # Minor units:
        # For cents/lepta:
        # "01" -> "ένα"
        # "1" -> "ένα"
        # 2..99 -> two_digit_map
        minor_one = pynini.cross(pynini.union("01", "1"), "ένα")
        minor_zero = pynini.cross(pynini.union("00", "0"), "")
        minor_other = pynini.difference(pynini.closure(NEMO_DIGIT, 1, 2), pynini.union("0", "00", "1", "01")) @ two_digit_map

        del_dec = pynutil.delete(pynini.union(",", "."))
        opt_space = pynini.closure(pynutil.delete(" "), 0, 1)

        # Euro definitions
        eur_sym = pynini.union("€", "EUR", "eur")
        euro_maj = pynutil.insert(" ευρώ")

        # Euro integer alone: 50 € -> πενήντα ευρώ
        eur_lead_int = pynutil.delete(eur_sym) + opt_space + pure_cardinal + euro_maj
        eur_trail_int = pure_cardinal + opt_space + pynutil.delete(eur_sym) + euro_maj

        # Euro with zero cents: "10,00 €", "€10.00" -> "δέκα ευρώ"
        eur_zero_cents = (
            (pynutil.delete(eur_sym) + opt_space + pure_cardinal + del_dec + minor_zero + euro_maj)
            | (pure_cardinal + del_dec + minor_zero + opt_space + pynutil.delete(eur_sym) + euro_maj)
        )

        # Euro with minor: "1,50 €", "€1.50" -> "ένα ευρώ και πενήντα λεπτά"
        eur_lead_maj_min_1 = (
            pynutil.delete(eur_sym) + opt_space + pure_cardinal + euro_maj + del_dec + pynutil.insert(" και ") + minor_one + pynutil.insert(" λεπτό")
        )
        eur_lead_maj_min_other = (
            pynutil.delete(eur_sym) + opt_space + pure_cardinal + euro_maj + del_dec + pynutil.insert(" και ") + minor_other + pynutil.insert(" λεπτά")
        )
        eur_trail_maj_min_1 = (
            pure_cardinal + euro_maj + del_dec + pynutil.insert(" και ") + minor_one + pynutil.insert(" λεπτό") + opt_space + pynutil.delete(eur_sym)
        )
        eur_trail_maj_min_other = (
            pure_cardinal + euro_maj + del_dec + pynutil.insert(" και ") + minor_other + pynutil.insert(" λεπτά") + opt_space + pynutil.delete(eur_sym)
        )

        # Euro minor only: "0,99 €", "€0.99" -> "ενενήντα εννέα λεπτά", "0,01 €" -> "ένα λεπτό"
        del_zero = pynutil.delete(pynini.union("0", "00"))
        eur_cents_only_1 = (
            (pynutil.delete(eur_sym) + opt_space + del_zero + del_dec + minor_one + pynutil.insert(" λεπτό"))
            | (del_zero + del_dec + minor_one + pynutil.insert(" λεπτό") + opt_space + pynutil.delete(eur_sym))
        )
        eur_cents_only_other = (
            (pynutil.delete(eur_sym) + opt_space + del_zero + del_dec + minor_other + pynutil.insert(" λεπτά"))
            | (del_zero + del_dec + minor_other + pynutil.insert(" λεπτά") + opt_space + pynutil.delete(eur_sym))
        )

        euro_all = (
            eur_zero_cents
            | eur_lead_maj_min_1
            | eur_lead_maj_min_other
            | eur_trail_maj_min_1
            | eur_trail_maj_min_other
            | eur_cents_only_1
            | eur_cents_only_other
            | eur_lead_int
            | eur_trail_int
        ).optimize()

        # Dollar definitions
        usd_sym = pynini.union("$", "USD", "usd", "US$")
        usd_maj_one = pynutil.insert(" δολάριο")
        usd_maj_other = pynutil.insert(" δολάρια")

        usd_card_one = pynini.cross("1", "ένα") + usd_maj_one
        usd_card_other = (pynini.difference(pynini.project(pure_cardinal_all, "input"), "1") @ pure_cardinal_all) + usd_maj_other
        usd_pure_card = usd_card_one | usd_card_other

        usd_lead_int = pynutil.delete(usd_sym) + opt_space + usd_pure_card
        usd_trail_int = usd_pure_card + opt_space + pynutil.delete(usd_sym)

        # USD zero cents
        usd_zero_cents = (
            (pynutil.delete(usd_sym) + opt_space + usd_pure_card + del_dec + minor_zero)
            | (usd_pure_card + del_dec + minor_zero + opt_space + pynutil.delete(usd_sym))
        )

        # USD with minor (σεντ): "$1.50" -> "ένα δολάριο και πενήντα σεντ"
        usd_lead_maj_min = (
            pynutil.delete(usd_sym) + opt_space + usd_pure_card + del_dec + pynutil.insert(" και ") + (minor_one | minor_other) + pynutil.insert(" σεντ")
        )
        usd_trail_maj_min = (
            usd_pure_card + del_dec + pynutil.insert(" και ") + (minor_one | minor_other) + pynutil.insert(" σεντ") + opt_space + pynutil.delete(usd_sym)
        )

        # USD cents only: "$0.99" -> "ενενήντα εννέα σεντ"
        usd_cents_only = (
            (pynutil.delete(usd_sym) + opt_space + del_zero + del_dec + (minor_one | minor_other) + pynutil.insert(" σεντ"))
            | (del_zero + del_dec + (minor_one | minor_other) + pynutil.insert(" σεντ") + opt_space + pynutil.delete(usd_sym))
        )

        # Cent symbol: 25¢ -> είκοσι πέντε σεντ
        cent_sym = pynutil.delete("¢")
        cent_graph = (minor_one | minor_other) + opt_space + cent_sym + pynutil.insert(" σεντ")

        usd_all = (
            usd_zero_cents
            | usd_lead_maj_min
            | usd_trail_maj_min
            | usd_cents_only
            | usd_lead_int
            | usd_trail_int
            | cent_graph
        ).optimize()

        # Other world currencies table
        # (symbol, name_singular, name_plural)
        other_curr_data = [
            ("£", "λίρα", "λίρες"),
            ("GBP", "λίρα", "λίρες"),
            ("¥", "γιεν", "γιεν"),
            ("JPY", "γιεν", "γιεν"),
            ("CHF", "ελβετικό φράγκο", "ελβετικά φράγκα"),
            ("CAD", "δολάριο Καναδά", "δολάρια Καναδά"),
            ("CA$", "δολάριο Καναδά", "δολάρια Καναδά"),
            ("A$", "δολάριο Αυστραλίας", "δολάρια Αυστραλίας"),
            ("AUD", "δολάριο Αυστραλίας", "δολάρια Αυστραλίας"),
            ("R$", "ρεάλ Βραζιλίας", "ρεάλ Βραζιλίας"),
            ("BRL", "ρεάλ Βραζιλίας", "ρεάλ Βραζιλίας"),
            ("MX$", "πέσο Μεξικού", "πέσο Μεξικού"),
            ("MXN", "πέσο Μεξικού", "πέσο Μεξικού"),
            ("₹", "ρουπία", "ρουπίες"),
            ("INR", "ινδική ρουπία", "ινδικές ρουπίες"),
            ("Rs.", "ρουπία", "ρουπίες"),
            ("Rs", "ρουπία", "ρουπίες"),
            ("₽", "ρούβλι", "ρούβλια"),
            ("RUB", "ρούβλι", "ρούβλια"),
            ("₩", "γουόν", "γουόν"),
            ("KRW", "γουόν", "γουόν"),
            ("₺", "τουρκική λίρα", "τουρκικές λίρες"),
            ("TRY", "τουρκική λίρα", "τουρκικές λίρες"),
            ("₪", "νέο ισραηλινό σέκελ", "νέα ισραηλινά σέκελ"),
            ("ILS", "νέο ισραηλινό σέκελ", "νέα ισραηλινά σέκελ"),
            ("₴", "γρίβνα", "γρίβνα"),
            ("UAH", "γρίβνα", "γρίβνα"),
            ("₫", "ντονγκ", "ντονγκ"),
            ("VND", "ντονγκ", "ντονγκ"),
            ("৳", "τάκα", "τάκα"),
            ("BDT", "τάκα", "τάκα"),
            ("₦", "νάιρα", "νάιρα"),
            ("NGN", "νάιρα", "νάιρα"),
            ("₱", "πέσο Φιλιππίνων", "πέσο Φιλιππίνων"),
            ("PHP", "πέσο Φιλιππίνων", "πέσο Φιλιππίνων"),
            ("฿", "μπατ", "μπατ"),
            ("THB", "μπατ", "μπατ"),
            ("֏", "ντραμ", "ντραμ"),
            ("AMD", "ντραμ", "ντραμ"),
            ("₿", "μπιτκόιν", "μπιτκόιν"),
            ("BTC", "μπιτκόιν", "μπιτκόιν"),
        ]

        fem_curr_symbols = {"£", "GBP", "₹", "INR", "Rs.", "Rs", "₺", "TRY", "₴", "UAH"}
        other_graphs = []
        for sym, sing, plur in other_curr_data:
            s_fst = pynutil.delete(sym)
            if sym in fem_curr_symbols:
                c_one = pynini.cross("1", "μία") + pynutil.insert(f" {sing}")
                c_other = (pynini.difference(pynini.project(fem_cardinal_all, "input"), "1") @ fem_cardinal_all) + pynutil.insert(f" {plur}")
            else:
                c_one = pynini.cross("1", "ένα") + pynutil.insert(f" {sing}")
                c_other = (pynini.difference(pynini.project(pure_cardinal_all, "input"), "1") @ pure_cardinal_all) + pynutil.insert(f" {plur}")
            c_all = c_one | c_other
            # leading or trailing symbol
            g_lead = s_fst + opt_space + c_all
            g_trail = c_all + opt_space + s_fst
            other_graphs.append(g_lead | g_trail)

        other_currencies = pynini.union(*other_graphs).optimize()

        # Shorthand money: $50k -> πενήντα χιλιάδες δολάρια, €50k -> πενήντα χιλιάδες ευρώ, €2.5M -> δύο κόμμα πέντε εκατομμύρια ευρώ
        shorthand_k = pynutil.delete(pynini.union("k", "K")) + pynutil.insert(" χιλιάδες")
        shorthand_m = pynutil.delete(pynini.union("M", "m")) + pynutil.insert(" εκατομμύρια")
        shorthand_b = pynutil.delete(pynini.union("B", "b")) + pynutil.insert(" δισεκατομμύρια")
        mag = shorthand_k | shorthand_m | shorthand_b

        num_mag = (pure_cardinal | decimal_core) + mag
        eur_shorthand = (
            (pynutil.delete(eur_sym) + opt_space + num_mag + pynutil.insert(" ευρώ"))
            | (num_mag + opt_space + pynutil.delete(eur_sym) + pynutil.insert(" ευρώ"))
        )
        usd_shorthand = (
            (pynutil.delete(usd_sym) + opt_space + num_mag + pynutil.insert(" δολάρια"))
            | (num_mag + opt_space + pynutil.delete(usd_sym) + pynutil.insert(" δολάρια"))
        )

        # Per unit money: $15/h -> δεκαπέντε δολάρια την ώρα, €20/kg -> είκοσι ευρώ ανά κιλό
        per_unit_map = pynini.string_map(
            [
                ("/h", " την ώρα"),
                ("/hr", " την ώρα"),
                ("/ώρα", " την ώρα"),
                ("/kg", " ανά κιλό"),
                ("/κιλό", " ανά κιλό"),
                ("/m", " ανά μέτρο"),
                ("/τεμ", " το τεμάχιο"),
                ("/τεμάχιο", " το τεμάχιο"),
            ]
        )
        per_unit_money = (euro_all | usd_all | other_currencies) + per_unit_map

        # Negative money: -$12.50, -12,50 €
        neg_prefix = pynini.cross(MINUS, "μείον ")
        neg_money = (
            neg_prefix + (euro_all | usd_all | other_currencies | eur_shorthand | usd_shorthand)
            | (pynutil.delete(eur_sym) + opt_space + neg_prefix + pure_cardinal + euro_maj)
            | (pynutil.delete(usd_sym) + opt_space + neg_prefix + usd_pure_card)
        )

        single_money = (
            euro_all
            | usd_all
            | other_currencies
            | eur_shorthand
            | usd_shorthand
            | per_unit_money
            | neg_money
        ).optimize()

        # Money ranges:
        # 1. Trailing currency: "10-20 €" / "10 - 20 €" -> "δέκα έως είκοσι ευρώ"
        # 2. Both currencies identical: "€10 - €20", "€10-€20" -> "δέκα έως είκοσι ευρώ"
        # 3. Mixed currencies: "€10-$20" -> "δέκα ευρώ έως είκοσι δολάρια", "$10-€20" -> "δέκα δολάρια έως είκοσι ευρώ"
        range_dash = pynini.cross(pynini.union("-", "–", "—", " - ", " – ", " — "), " έως ")

        range_trailing_eur = pure_cardinal + range_dash + pure_cardinal + opt_space + pynutil.delete(eur_sym) + euro_maj
        range_trailing_usd = pure_cardinal + range_dash + pure_cardinal + opt_space + pynutil.delete(usd_sym) + usd_maj_other
        range_leading_eur = pynutil.delete(eur_sym) + opt_space + pure_cardinal + range_dash + pynutil.delete(eur_sym) + opt_space + pure_cardinal + euro_maj
        range_leading_usd = pynutil.delete(usd_sym) + opt_space + pure_cardinal + range_dash + pynutil.delete(usd_sym) + opt_space + pure_cardinal + usd_maj_other

        # Mixed currency range: retains both units
        range_mixed = single_money + range_dash + single_money

        money_ranges = (
            range_trailing_eur
            | range_trailing_usd
            | range_leading_eur
            | range_leading_usd
            | range_mixed
        ).optimize()

        all_money = (single_money | money_ranges).optimize()

        self.single_money = single_money
        self.all_money = all_money
        self.fst = all_money
