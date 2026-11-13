"""Golden outputs of the frozen reference pipeline (native pynini or oracle container).

    python oracle/dump_golden.py --lang en --corpus tests/corpus/en.jsonl --out tests/golden/en.jsonl
    python oracle/dump_golden.py --all

The tests read `tests/golden/<lang>.jsonl.zst`: compress each new dump on the host with
`zstd -19 -f <file>.jsonl -o <file>.jsonl.zst` (the plain .jsonl is gitignored).

Rows: {"text", "out", "fallback", "calls"}. fallback is true when the whole-text grammar call raised (sentence retry
ran) or NeMo's `normalize` swallowed an exception and returned its input. calls: every NeMo `Normalizer.normalize`
call the wrapper made for the row, in order: {"in": grammar input, "tags": tagger shortest path (null when the
tagger had no path), "verb": verbalizer output per split, "out": return value (null when it raised), "error":
exception class name or null}.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import reference_textnorm as ref
from nemo_text_processing.text_normalization import normalize as nemo_normalize
from nemo_text_processing.text_normalization.normalize import Normalizer

ROOT = Path(__file__).resolve().parents[1]
SERVER_CODE = {
    "en": "en_us",
    "de": "de",
    "es": "es",
    "fr": "fr_fr",
    "it": "it",
    "pt": "pt_br",
    "ja": "ja",
    "zh": "cmn",
    "ko": "ko",
}
SERVER_CODE.update({lang: lang for lang in ref.NEW_LANGS})
LANGS = ["en", "de", "es", "fr", "it", "pt", "ja", "zh", "ko"]

_state = {"fallback": False, "calls": []}


def _instrument(tn: ref.TTSTextNormalizer) -> None:
    once = tn._normalize_once

    def wrapped(text, lang):
        try:
            return once(text, lang)
        except Exception:
            _state["fallback"] = True
            raise

    tn._normalize_once = wrapped

    normalize = Normalizer.normalize
    select_tag = Normalizer.select_tag
    select_verbalizer = Normalizer.select_verbalizer

    def normalize_rec(self, text, *args, **kwargs):
        call = {"in": text, "tags": None, "verb": [], "out": None, "error": None}
        _state["calls"].append(call)
        try:
            call["out"] = normalize(self, text, *args, **kwargs)
        except Exception as e:
            call["error"] = type(e).__name__
            raise
        return call["out"]

    def select_tag_rec(lattice):
        tags = select_tag(lattice)
        _state["calls"][-1]["tags"] = tags
        return tags

    def select_verbalizer_rec(lattice):
        out = select_verbalizer(lattice)
        _state["calls"][-1]["verb"].append(out)
        return out

    Normalizer.normalize = normalize_rec
    Normalizer.select_tag = staticmethod(select_tag_rec)
    Normalizer.select_verbalizer = staticmethod(select_verbalizer_rec)

    logger = nemo_normalize.logger
    warning = logger.warning

    def warn(msg, *args, **kwargs):
        if isinstance(msg, str) and (msg.startswith("Failed text:") or msg.startswith("No permutations")):
            _state["fallback"] = True
        return warning(msg, *args, **kwargs)

    logger.warning = warn
    logger.setLevel(logging.ERROR)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logging.getLogger("reference_textnorm").setLevel(logging.CRITICAL)


def dump(tn: ref.TTSTextNormalizer, lang: str, corpus: Path, out: Path) -> None:
    rows = [json.loads(l)["text"] for l in corpus.read_text(encoding="utf-8").splitlines() if l.strip()]
    out.parent.mkdir(parents=True, exist_ok=True)
    code = SERVER_CODE[lang]
    t0 = time.perf_counter()
    tn.get(lang)
    print(f"[{lang}] grammar ready in {time.perf_counter() - t0:.1f}s; {len(rows)} rows", file=sys.stderr, flush=True)
    t0 = time.perf_counter()
    n_fb = 0
    tmp = out.with_suffix(".jsonl.partial")
    with open(tmp, "w", encoding="utf-8") as f:
        for i, text in enumerate(rows):
            _state["fallback"] = False
            _state["calls"] = []
            result = tn.normalize(text, code)
            n_fb += _state["fallback"]
            row = {"text": text, "out": result, "fallback": _state["fallback"], "calls": _state["calls"]}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if (i + 1) % 1000 == 0:
                print(f"[{lang}] {i + 1}/{len(rows)} ({time.perf_counter() - t0:.0f}s)", file=sys.stderr, flush=True)
    tmp.replace(out)
    print(
        f"[{lang}] done: {len(rows)} rows, {n_fb} fallbacks, {time.perf_counter() - t0:.0f}s",
        file=sys.stderr,
        flush=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang")
    ap.add_argument("--corpus")
    ap.add_argument("--out")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--cache", default="/tmp/zonos3-tts-norm")
    args = ap.parse_args()
    tn = ref.TTSTextNormalizer(cache_root=args.cache)
    _instrument(tn)
    if args.all:
        for lang in LANGS:
            dump(tn, lang, ROOT / "tests" / "corpus" / f"{lang}.jsonl", ROOT / "tests" / "golden" / f"{lang}.jsonl")
    else:
        dump(tn, args.lang, Path(args.corpus), Path(args.out))


if __name__ == "__main__":
    main()
