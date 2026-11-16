"""prepass_tables.py: the tables of the opt-in pre-pass (src/prepass/), from Python's html module, the emoji package
and CLDR's emoji annotations.

The pre-pass was prototyped in Python (html.unescape for entities, emoji 2.14.1 for emoji names and shortcodes); the
Rust port reads the same data so both give the same output. Every key is written as hex code points, so tabs,
newlines and variation selectors survive the TSV.

The other languages' emoji names are CLDR 46's text-to-speech names (`tts`; CLDR 46 is Emoji 16.0, the same version
as emoji 2.14.1), from the cldr-annotations-full and cldr-annotations-derived-full npm packages. They are downloaded
into $CLDR_DIR (default ~/.cache/zyphra-textnorm/cldr-46) on first use.

    uv run --with emoji==2.14.1 python oracle/prepass_tables.py

writes data/prepass/{html5,html_charrefs,emoji,emoji_alias,emoji_names}.tsv.
"""
import html
import html.entities
import json
import os
import re
import urllib.request

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

# emoji_names.tsv: one row per emoji (no variation selectors, no skin tone: the pre-pass drops skin tones), one column
# per language other than English, the CLDR tts name or empty. The header row starts with "#".
LANGS = ["de", "es", "fr", "it", "pt", "ja", "zh", "ko", "nl", "pl", "tr", "uk", "cs", "da", "fi", "el", "nb", "ro", "sk",
         "bg", "he", "th", "tl", "ms", "ka", "ta", "gu", "kn", "ml", "pa", "or", "ru", "sv", "hu", "ar", "vi", "id", "hi",
         "bn", "te", "mr", "ur"]
CLDR_LOCALE = {"nb": "no", "tl": "fil"}
CLDR = os.environ.get("CLDR_DIR") or os.path.expanduser("~/.cache/zyphra-textnorm/cldr-46")
URL = "https://cdn.jsdelivr.net/npm/{pkg}@46.0.0/{dir}/{loc}/{file}"


def cldr(lang: str) -> dict:
    loc, names = CLDR_LOCALE.get(lang, lang), {}
    for pkg, d, file in (("cldr-annotations-full", "annotations", "annotations.json"),
                         ("cldr-annotations-derived-full", "annotationsDerived", "annotations.json")):
        path = os.path.join(CLDR, d, loc, file)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            urllib.request.urlretrieve(URL.format(pkg=pkg, dir=d, loc=loc, file=file), path)
        data = json.load(open(path, encoding="utf-8"))[d]["annotations"]
        for k, v in data.items():
            if "tts" in v:
                names.setdefault(k, v["tts"][0])
    return names


SKIN = re.compile("[\U0001F3FB-\U0001F3FF]")
keys = []
for e in unicode_codes.EMOJI_DATA:
    k = e.replace("\ufe0f", "").replace("\ufe0e", "")
    if not SKIN.search(k) and k not in keys:
        keys.append(k)
tables = {lang: cldr(lang) for lang in LANGS}
rows = [("#key", *LANGS)]
for k in keys:
    names = [tables[lang].get(k, "").replace("\t", " ") for lang in LANGS]
    if any(names):
        rows.append((hexs(k), *names))
write("emoji_names.tsv", rows)
print({lang: sum(1 for k in keys if k in tables[lang]) for lang in LANGS}, "of", len(keys))
print({f: sum(1 for _ in open(os.path.join(OUT, f), encoding="utf-8")) for f in sorted(os.listdir(OUT))})
