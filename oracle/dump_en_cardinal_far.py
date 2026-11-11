"""Specification dump of the two prebuilt English number-name FARs and the assembled CardinalFst (container only).

    python oracle/dump_en_cardinal_far.py  ->  tests/golden/en_cardinal_far.jsonl
    zstd -19 -f tests/golden/en_cardinal_far.jsonl -o tests/golden/en_cardinal_far.jsonl.zst

Rows: {"digits", "graph", "graph_au", "final"}; each output is the shortest-path string through the FST, or null when
the FST rejects the input.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pynini
from nemo_text_processing.text_normalization.en.taggers.cardinal import CardinalFst
from nemo_text_processing.text_normalization.en.utils import get_abs_path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "golden" / "en_cardinal_far.jsonl"
GROUP_PATTERNS = ["000", "001", "007", "010", "011", "020", "021", "100", "101", "110", "111", "999"]


def shortest(s: str, fst) -> str | None:
    try:
        lattice = pynini.escape(s) @ fst
        if lattice.num_states() == 0:
            return None
        return pynini.shortestpath(lattice, nshortest=1, unique=True).string()
    except Exception:
        return None


def with_commas(digits: str) -> str | None:
    n = len(digits)
    if n <= 3:
        return None
    head = n % 3 or 3
    return ",".join([digits[:head]] + [digits[i : i + 3] for i in range(head, n, 3)])


def inputs():
    rng = random.Random(0)
    for i in range(100_000):
        yield str(i)
    for k in range(1, 25):  # powers of ten and their neighbours
        yield "1" + "0" * k
        yield "1" + "0" * (k - 1) + "1"
        yield "9" * k
    # 9..24-digit numbers whose 3-digit groups come from GROUP_PATTERNS (sampled: 12^8 combinations do not fit)
    for _ in range(100_000):
        groups = rng.randint(3, 8)
        yield "".join(rng.choice(GROUP_PATTERNS) for _ in range(groups))
    # 7-8 digit numbers (two full groups plus a 1-2 digit head)
    for _ in range(10_000):
        yield str(rng.randint(10**6, 10**8 - 1))
    for _ in range(50_000):
        n = rng.randint(1, 24)
        yield "".join(rng.choice("0123456789") for _ in range(n))


def main() -> None:
    graph = pynini.Far(get_abs_path("data/number/cardinal_number_name.far")).get_fst()
    graph_au = pynini.Far(get_abs_path("data/number/cardinal_number_name_au.far")).get_fst()
    final = CardinalFst().final_graph
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for digits in inputs():
            for s in (digits, with_commas(digits)):
                if s is None or s in seen:
                    continue
                seen.add(s)
                row = {
                    "digits": s,
                    "graph": shortest(s, graph),
                    "graph_au": shortest(s, graph_au),
                    "final": shortest(s, final),
                }
                f.write(json.dumps(row) + "\n")
                n += 1
                if n % 20000 == 0:
                    print(f"{n} rows", file=sys.stderr, flush=True)
    print(f"done: {n} rows -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
