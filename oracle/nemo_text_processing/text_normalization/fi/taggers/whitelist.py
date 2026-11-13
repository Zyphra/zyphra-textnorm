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
    GraphFst,
    convert_space,
)


class WhiteListFst(GraphFst):
    """
    Finite state transducer for classifying Finnish whitelist symbols and abbreviations, e.g.
        "~50" -> tokens { name: "noin viisikymmentä" }
        "±5" -> tokens { name: "plus-miinus viisi" }
        "A & B" -> tokens { name: "A ja B" }
        "© 2024" -> tokens { name: "tekijänoikeus kaksituhattakaksikymmentäneljä" }
        "§ 12" -> tokens { name: "pykälä kaksitoista" }
        "tri Lindqvist" -> tokens { name: "tohtori Lindqvist" }
        "nro 5" -> tokens { name: "numero viisi" }
        "esim." -> tokens { name: "esimerkiksi" }
        "jne." -> tokens { name: "ja niin edelleen" }
    """

    def __init__(self, cardinal: GraphFst = None, deterministic: bool = True):
        super().__init__(name="whitelist", kind="classify", deterministic=deterministic)

        cardinal_nums = cardinal.all_nums_no_tokens if cardinal else pynini.accep("")

        # 1. Standalone symbols
        symbols_map = [
            ("&", "ja"),
            ("©", "tekijänoikeus"),
            ("§", "pykälä"),
            ("®", "rekisteröity tavaramerkki"),
            ("™", "tavaramerkki"),
        ]
        standalone_symbols = pynini.string_map(symbols_map)

        # 2. Prefixes "~" (noin) and "±" (plus-miinus) before numbers/measures
        approx_sign = pynini.cross("~", "noin ")
        pm_sign = pynini.cross("±", "plus-miinus ")
        opt_sp = pynini.closure(pynutil.delete(" "), 0, 1)

        approx_num = approx_sign + opt_sp + cardinal_nums
        pm_num = pm_sign + opt_sp + cardinal_nums

        # Approximate measure: "~10 km" -> "noin kymmenen kilometriä"
        approx_measure = (
            approx_sign
            + opt_sp
            + cardinal_nums
            + opt_sp
            + pynini.string_map([
                ("km", " kilometriä"),
                ("m", " metriä"),
                ("kg", " kilogrammaa"),
                ("g", " grammaa"),
                ("l", " litraa"),
            ])
        )

        # 3. Copyright year: "© 2024" -> "tekijänoikeus kaksituhattakaksikymmentäneljä"
        copyright_year = pynini.cross("©", "tekijänoikeus") + pynini.accep(" ") + cardinal_nums

        # 4. Section number: "§ 12" -> "pykälä kaksitoista"
        section_num = pynini.cross("§", "pykälä") + pynini.accep(" ") + cardinal_nums

        # 5. Number symbol: "#5" -> "numero viisi"
        hash_num = pynini.cross("#", "numero ") + cardinal_nums

        # 6. Cents symbol: "25¢" -> "kaksikymmentäviisi senttiä"
        cents_sym = cardinal_nums + opt_sp + pynini.cross("¢", " senttiä")

        # 7. Common abbreviations
        abbrevs_data = [
            ("esim.", "esimerkiksi"),
            ("esim", "esimerkiksi"),
            ("jne.", "ja niin edelleen"),
            ("jne", "ja niin edelleen"),
            ("tms.", "tai muuta sellaista"),
            ("tms", "tai muuta sellaista"),
            ("ns.", "niin sanottu"),
            ("ns", "niin sanottu"),
            ("v.", "vuonna"),
            ("s.", "sivu"),
            ("klo.", "kello"),
            ("klo", "kello"),
            ("kl.", "kello"),
            ("etc.", "ja niin edelleen"),
            ("etc", "ja niin edelleen"),
        ]
        abbrevs = pynini.string_map(abbrevs_data)

        # 8. Titles before names: "tri Lindqvist", "Dr. Smith", "Dr. Jones", "prof. Virtanen"
        titles_data = [
            ("tri.", "tohtori"),
            ("tri", "tohtori"),
            ("Tri.", "tohtori"),
            ("Tri", "tohtori"),
            ("Dr.", "tohtori"),
            ("Dr", "tohtori"),
            ("prof.", "professori"),
            ("Prof.", "professori"),
            ("prof", "professori"),
            ("Prof", "professori"),
            ("dos.", "dosentti"),
            ("Dos.", "dosentti"),
            ("maist.", "maisteri"),
            ("Maist.", "maisteri"),
            ("ins.", "insinööri"),
            ("Ins.", "insinööri"),
        ]
        titles = pynini.string_map(titles_data)

        # 9. Number abbreviation before number: "nro 5", "No. 5", "Nr. 5", "n:o 5" -> "numero viisi"
        no_abbrevs = pynini.string_map([
            ("nro", "numero"),
            ("Nro", "numero"),
            ("nro.", "numero"),
            ("Nro.", "numero"),
            ("n:o", "numero"),
            ("N:o", "numero"),
            ("No.", "numero"),
            ("No", "numero"),
            ("Nr.", "numero"),
            ("Nr", "numero"),
        ])
        no_num = no_abbrevs + opt_sp + pynutil.insert(" ") + cardinal_nums

        all_whitelist = (
            copyright_year
            | section_num
            | hash_num
            | approx_measure
            | approx_num
            | pm_num
            | cents_sym
            | no_num
            | titles
            | abbrevs
            | standalone_symbols
        ).optimize()

        self.fst = (
            pynutil.insert('name: "')
            + convert_space(all_whitelist).optimize()
            + pynutil.insert('"')
        ).optimize()
