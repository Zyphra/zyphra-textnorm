"""Oracle internals for one or more texts (container only): the wrapper's NeMo calls with the tagged string, the
first verbalizable permutation, the verbalizer output and the final result.

    docker run --rm -v "$PWD":/repo -v "$HOME/.cache/zyphra-textnorm-oracle":/cache -w /repo zyphra-textnorm-oracle \
        python oracle/triage.py --lang en --text "Call me at 123 Main Street, please."
    ... triage.py --lang de --file /repo/some_texts.txt          # one text per line, batched in one grammar load
    ... triage.py --lang en --raw --text "5."                    # NeMo Normalizer.normalize only, no wrapper
    ... triage.py --lang en --tagged 'tokens { cardinal { integer: "5" } }'   # verbalizer only
    ... triage.py --lang fr --score ties.jsonl   # oracle f32 path costs of alternative taggings (see score_ties)
    ... triage.py --lang fr --score draft.jsonl --write tests/ties/fr.jsonl   # the committed tie list

Grammars are cached under /cache/<lang>_<case> (mount a host directory there; first load compiles them).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import struct
import sys

import pynini
import reference_textnorm as ref
from nemo_text_processing.text_normalization import normalize as nemo_normalize
from nemo_text_processing.text_normalization.en.graph_utils import NEMO_SIGMA
from nemo_text_processing.text_normalization.normalize import Normalizer

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True)
    ap.add_argument("--text", action="append", default=[])
    ap.add_argument("--file")
    ap.add_argument("--raw", action="store_true", help="call NeMo Normalizer.normalize directly (no wrapper)")
    ap.add_argument("--tagged", action="append", default=[], help="run the verbalizer on a tagged string")
    ap.add_argument(
        "--score", help="JSONL of {in, oracle_tags, rust_tags[, reason]}: the tagger's cost of each tagging"
    )
    ap.add_argument(
        "--write",
        help="with --score: write the rows the oracle confirms as ties (each needs a reason) to this tie list; "
        "exit 1 if any row is not a tie or lacks a reason",
    )
    ap.add_argument("--cache", default="/cache")
    args = ap.parse_args()
    texts = list(args.text)
    if args.file:
        texts += [l.rstrip("\n") for l in open(args.file, encoding="utf-8") if l.strip()]

    logging.getLogger("NeMo-text-processing").setLevel(logging.ERROR)
    tn = ref.TTSTextNormalizer(cache_root=args.cache)
    nemo = tn.get(args.lang)
    calls = []

    normalize = Normalizer.normalize
    select_tag = Normalizer.select_tag
    select_verbalizer = Normalizer.select_verbalizer
    generate_permutations = Normalizer.generate_permutations

    def normalize_rec(self, text, *a, **k):
        call = {"in": text, "tags": None, "perms_tried": 0, "perm": None, "verb": [], "out": None, "error": None}
        calls.append(call)
        try:
            call["out"] = normalize(self, text, *a, **k)
        except Exception as e:
            call["error"] = f"{type(e).__name__}: {e}"
            raise
        return call["out"]

    def select_tag_rec(lattice):
        t = select_tag(lattice)
        calls[-1]["tags"] = t
        return t

    def generate_permutations_rec(self, tokens):
        for p in generate_permutations(self, tokens):
            calls[-1]["perms_tried"] += 1
            calls[-1]["perm"] = p
            yield p

    def select_verbalizer_rec(lattice):
        out = select_verbalizer(lattice)
        calls[-1]["verb"].append(out)
        return out

    Normalizer.normalize = normalize_rec
    Normalizer.select_tag = staticmethod(select_tag_rec)
    Normalizer.select_verbalizer = staticmethod(select_verbalizer_rec)
    Normalizer.generate_permutations = generate_permutations_rec
    nemo_normalize.logger.setLevel(logging.ERROR)

    if args.score:
        score_ties(nemo, args.score, args.write)
    elif args.write:
        ap.error("--write needs --score")

    for tagged in args.tagged:
        lattice = pynini.escape(tagged) @ nemo.verbalizer.fst
        if lattice.num_states() == 0:
            print(json.dumps({"tagged": tagged, "verbalized": None}, ensure_ascii=False))
        else:
            out = pynini.shortestpath(lattice, nshortest=1, unique=True).string()
            print(json.dumps({"tagged": tagged, "verbalized": out}, ensure_ascii=False))

    for text in texts:
        calls.clear()
        try:
            if args.raw:
                out = nemo.normalize(text, punct_post_process=args.lang in ref._MOSES_POSTPROCESS_LANGS)
            else:
                out = tn.normalize(text, SERVER_CODE[args.lang])
        except Exception as e:  # noqa: BLE001
            out = f"<raised {type(e).__name__}: {e}>"
        print(json.dumps({"text": text, "out": out, "calls": calls}, ensure_ascii=False, indent=1))
        sys.stdout.flush()


def canonical_tags(tagged: str) -> str:
    """Tagged-string spacing the port's serializer and the tagger do not share, removed: runs of spaces become one, no
    space between `}` and the next `tokens`, none at either end."""
    return re.sub(r"\} tokens", "}tokens", re.sub(r" +", " ", tagged)).strip(" ")


def _canonical_fst() -> pynini.Fst:
    """`canonical_tags` as a transducer on the tagger's output."""
    squash = pynini.cdrewrite(pynini.cross(pynini.closure(" ", 2), " "), "", "", NEMO_SIGMA)
    join = pynini.cdrewrite(pynini.cross(" ", ""), "}", "tokens", NEMO_SIGMA)
    ends = pynini.cdrewrite(pynini.cross(" ", ""), "[BOS]", "", NEMO_SIGMA) @ pynini.cdrewrite(
        pynini.cross(" ", ""), "", "[EOS]", NEMO_SIGMA
    )
    return (squash @ join @ ends).optimize()


def path_cost(tagger: pynini.Fst, canonical: pynini.Fst, text: str, tagged: str) -> float | None:
    """The tagger's own (f32 tropical) cost of its cheapest path rewriting `text` (as `find_tags` composes it) to a string
    with the same `canonical_tags` form as `tagged`, or None when the tagger has no such path. Exactly the float32 the
    FST holds: `float(Weight)` parses its 9-significant-digit string, which round-trips only once rounded to float32."""
    lattice = pynini.escape(text) @ tagger @ canonical @ pynini.escape(canonical_tags(tagged))
    if lattice.num_states() == 0:
        return None
    weight = float(pynini.shortestdistance(lattice, reverse=True)[lattice.start()])
    return struct.unpack("<f", struct.pack("<f", weight))[0]


def f32_ulp(x: float) -> float:
    """The spacing of float32 values at |x| (OpenFst weights are float32)."""
    return 2.0 ** (math.frexp(abs(x))[1] - 24) if x else 2.0**-149


REASONS = ("number", "order", "f32")


def score_ties(nemo: Normalizer, path: str, write: str | None = None) -> None:
    """For each row: the oracle's cost of its own tagging and of the port's. `tie` means both paths exist at the same
    float32 cost up to one ulp (the summation order of a path's weights depends on how the lattice is composed), so
    the oracle's pick between them is its FST's arc order, not the grammar's weights.

    With `write`, the rows that are ties and carry a reason (PORTING.md, "Ties") become the tie list
    `tests/ties/<lang>.jsonl`, sorted by input; any other row fails the run."""
    canonical = _canonical_fst()
    keep, rejected = [], 0
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        text = row["in"].strip()
        oracle = path_cost(nemo.tagger.fst, canonical, text, row["oracle_tags"])
        rust = path_cost(nemo.tagger.fst, canonical, text, row["rust_tags"])
        tie = oracle is not None and rust is not None and abs(oracle - rust) <= f32_ulp(max(oracle, rust))
        print(json.dumps({"in": row["in"], "oracle_cost": oracle, "rust_cost": rust, "tie": tie}, ensure_ascii=False))
        sys.stdout.flush()
        if write is None:
            continue
        if not tie or row.get("reason") not in REASONS:
            rejected += 1
            print(f"REJECTED (tie={tie}, reason={row.get('reason')!r}): {row['in']!r}", file=sys.stderr)
            continue
        keep.append(
            {
                "in": row["in"],
                "reason": row["reason"],
                "cost": oracle,
                "oracle_tags": row["oracle_tags"],
                "rust_tags": row["rust_tags"],
            }
        )
    if write is None:
        return
    if rejected:
        sys.exit(f"{rejected} rows are not oracle ties with a reason; {write} not written")
    with open(write, "w", encoding="utf-8") as f:
        for row in sorted(keep, key=lambda r: r["in"]):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(keep)} ties to {write}", file=sys.stderr)


if __name__ == "__main__":
    main()
