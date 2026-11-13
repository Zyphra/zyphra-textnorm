# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
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
# Number names from Unicode CLDR release-49 (Unicode-3.0 license).

import pynini
from pynini.lib import pynutil

from nemo_text_processing.text_normalization.ur.graph_utils import (
    NEMO_ALPHA,
    NEMO_SIGMA,
    GraphFst,
    capitalized_input_graph,
    delete_space,
    insert_space,
)
from nemo_text_processing.text_normalization.ur.utils import get_abs_path


class ElectronicFst(GraphFst):
    """
    Finite state transducer for verbalizing electronic addresses.
    English words and letters are kept verbatim (Latin script); only digits and
    symbols are read out in Urdu.

    Examples:
        electronic { username: "kumar" domain: "gmail.com" } -> "kumar ایٹ gmail ڈاٹ com"
        electronic { protocol: "https" domain: "google.com/" } -> "https کولن سلیش سلیش google ڈاٹ com سلیش"
        electronic { path: "C:\\Users\\HP\\Desktop" } -> "C کولن بیک سلیش Users بیک سلیش HP بیک سلیش Desktop"
        electronic { domain: "192.168.1.1" } -> "ایک نو دو ڈاٹ ایک چھ آٹھ ڈاٹ ایک ڈاٹ ایک"
        electronic { fragment_id: "C₂H₄" } -> "سی دو ایچ چار"

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transductions are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="verbalize", deterministic=deterministic)

        symbols_graph = pynini.string_file(get_abs_path("data/electronic/symbols.tsv")).optimize()

        ascii_digit_graph = pynini.string_file(get_abs_path("data/telephone/number.tsv")).optimize()
        urdu_digit_graph = pynini.string_file(get_abs_path("data/numbers/digit.tsv")).optimize()
        urdu_zero_graph = pynini.string_file(get_abs_path("data/numbers/zero.tsv")).optimize()
        subscript_digit_graph = pynini.string_file(get_abs_path("data/electronic/subscript_digit.tsv")).optimize()
        digit_verbalization = ascii_digit_graph | urdu_digit_graph | urdu_zero_graph | subscript_digit_graph

        protocol_graph = pynini.string_file(get_abs_path("data/electronic/protocols.tsv")).optimize()

        single_digit = digit_verbalization + insert_space
        single_symbol = symbols_graph + insert_space

        single_non_alpha = pynutil.add_weight(single_symbol, 1.0) | pynutil.add_weight(single_digit, 1.0)

        # A run of Latin letters is preserved verbatim; digits and symbols verbalize in Urdu.
        alpha_run = pynini.closure(NEMO_ALPHA, 1) + insert_space

        # Chemical formulas are spelled out letter-by-letter (element symbols are
        # abbreviations, not words), while digits and symbols verbalize in Urdu.
        latin_to_urdu_graph = capitalized_input_graph(
            pynini.string_file(get_abs_path("data/address/letters.tsv"))
        ).optimize()
        chem_char = (latin_to_urdu_graph + insert_space) | single_digit | single_symbol
        chem_content = pynini.closure(chem_char, 1)

        def make_content(non_alpha_sep=None):
            if non_alpha_sep is None:
                non_alpha_sep = single_non_alpha
            mandatory_sep = pynini.closure(non_alpha_sep, 1)
            return (
                pynini.closure(non_alpha_sep, 0)
                + pynini.closure(alpha_run + mandatory_sep, 0)
                + pynini.closure(alpha_run, 0, 1)
                + pynini.closure(non_alpha_sep, 0)
            )

        delete_username_tag = pynutil.delete("username: \"")
        delete_domain_tag = pynutil.delete("domain: \"")
        delete_protocol_tag = pynutil.delete("protocol: \"")
        delete_path_tag = pynutil.delete("path: \"")
        delete_fragment_id_tag = pynutil.delete("fragment_id: \"")
        delete_quote = pynutil.delete("\"")

        general_content = make_content()

        username_graph = delete_username_tag + general_content + delete_quote + delete_space + pynutil.insert("ایٹ ")
        domain_only_graph = delete_domain_tag + general_content + delete_quote
        protocol_only_graph = delete_protocol_tag + protocol_graph + insert_space + delete_quote + delete_space
        path_graph = delete_path_tag + general_content + delete_quote

        chem_graph = delete_fragment_id_tag + chem_content + delete_quote

        ip_char = single_symbol | single_digit
        ip_content = pynini.closure(ip_char, 1)
        ip_graph = delete_domain_tag + ip_content + delete_quote

        email_full = username_graph + domain_only_graph
        url_full = protocol_only_graph + domain_only_graph

        graph = (
            pynutil.add_weight(url_full, 1.0)
            | pynutil.add_weight(email_full, 1.01)
            | pynutil.add_weight(path_graph, 1.02)
            | pynutil.add_weight(ip_graph, 1.03)
            | pynutil.add_weight(domain_only_graph, 1.04)
            | pynutil.add_weight(chem_graph, 1.04)
        )

        # Every symbol / digit / letter run inserts a trailing space; without hi's post-processor it would survive.
        strip_final_space = pynini.cdrewrite(pynutil.delete(" "), "", "[EOS]", NEMO_SIGMA)
        delete_tokens = self.delete_tokens(graph) @ strip_final_space
        self.fst = delete_tokens.optimize()
