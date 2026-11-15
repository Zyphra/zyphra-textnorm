"""prepass_tables.py: the tables of the opt-in pre-pass (src/prepass.rs), from Python's html module and the emoji package.

The pre-pass was prototyped in Python (html.unescape for entities, emoji 2.14.1 for emoji names and shortcodes); the
Rust port reads the same data so both give the same output. Every value is written as hex code points, so tabs,
newlines and variation selectors survive the TSV.

    uv run --with emoji==2.14.1 python oracle/prepass_tables.py

writes data/prepass/{html5,html_charrefs,emoji,emoji_alias}.tsv.
"""
import html
import html.entities
import os
import re

import emoji
from emoji import unicode_codes

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "prepass")
assert emoji.__version__ == "2.14.1", emoji.__version__


def hexs(s: str) -> str:
    return " ".join(f"{ord(ch):X}" for ch in s)


def write(name: str, rows) -> None:
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        for row in rows:
            f.write("\t".join(row) + "\n")


os.makedirs(OUT, exist_ok=True)
# html.unescape: named references (with and without the semicolon) and the numeric-reference repairs
write("html5.tsv", sorted((k, hexs(v)) for k, v in html.entities.html5.items()))
write("html_charrefs.tsv", [("ref", f"{k:X}", hexs(v)) for k, v in sorted(html._invalid_charrefs.items())]
      + [("drop", f"{k:X}", "") for k in sorted(html._invalid_codepoints)])

# emoji: every EMOJI_DATA entry in its dict order (the tokenizer's search tree), its English name and its status
write("emoji.tsv", [(hexs(e), d["en"], str(d["status"])) for e, d in unicode_codes.EMOJI_DATA.items()])

# emojize(":name:", language="alias") for every shortcode the pre-pass can match (lowercase, 2-30 chars, or :+1: :-1:)
shortcode = re.compile(r":(?:(?=[a-z0-9_+\-]*[a-z])[a-z0-9_+\-]{2,30}|[+-]1):")
names = {n for d in unicode_codes.EMOJI_DATA.values() for n in [d["en"], *d.get("alias", [])]}
rows = []
for n in sorted(names):
    if shortcode.fullmatch(n):
        e = emoji.emojize(n, language="alias")
        if e != n:
            rows.append((n, hexs(e)))
write("emoji_alias.tsv", rows)
print({f: sum(1 for _ in open(os.path.join(OUT, f), encoding="utf-8")) for f in sorted(os.listdir(OUT))})
