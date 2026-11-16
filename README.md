# zyphra-textnorm

Text normalization for text-to-speech: written text to its spoken form ("$5.32" → "five dollars thirty two cents"),
for 43 languages. The original nine packages are hand-written Rust ports of the
[NeMo-text-processing](https://github.com/NVIDIA/NeMo-text-processing) r1.2.0 grammars; the additional 34 port
ZONOS3's production locale grammars and Unicode CLDR release-49 data. There is no FST runtime and no pynini: every
grammar is Rust code, every table is embedded at compile time, and nothing is loaded at runtime. One library serves
Rust, Python and C, with a 1024-entry memo per normalizer.

The differential corpora contain 179,669 rows: 92,953 for the original nine languages and 86,716 for the added
locales, generated from vendored fixtures, lexical tables, and held-out rule boundaries (see [Parity](#parity)).

## Use

```rust
use zyphra_textnorm::Normalizer;

assert_eq!(zyphra_textnorm::normalize("It costs $5.32.", "en"), "It costs five dollars thirty two cents.");
let tn = Normalizer::with_markup_tags(["laugh", "shouting"]);
assert_eq!(tn.normalize("So I said <laugh/> no way, $5.", "en"), "So I said <laugh/> no way, five dollars.");
```

```python
import zyphra_textnorm

zyphra_textnorm.normalize("Am 3. Oktober kostete es 5,32 €.", "de")
# 'Am dritten Oktober kostete es fünf Euro zweiunddreißig.'
tn = zyphra_textnorm.Normalizer(markup_tags=["laugh"])
tn.normalize("So I said <laugh/> no way, $5.", "en")
```

```c
#include "zyphra_textnorm.h"

zyphra_textnorm *tn = zyphra_textnorm_new("laugh\nshouting", 14);
char *out = zyphra_textnorm_normalize(tn, text, text_len, "en", 2);
/* ... */
zyphra_textnorm_free(out);
zyphra_textnorm_delete(tn);
```

- **Languages**: `LANGUAGES` = `en de es fr it pt ja zh ko nl pl tr uk cs da fi el nb ro sk bg he th tl ms ka ta gu kn ml pa or ru sv hu ar vi id hi bn te mr ur`.
  `zh` is Mandarin, `nb` is Norwegian Bokmål, `tl` is Tagalog/Filipino, and `or` is Odia. `supported(lang)` says
  whether this build has a grammar. One cargo feature per language (`lang-en` …), all on by default.
- **Never fails**: a language without a grammar comes back with its line breaks collapsed, and a sentence the
  grammar fails on is kept as typed (the rest of the text is still normalized).
- **Line breaks**: every whitespace run holding a line break, tab or other non-space whitespace becomes one space
  first (`collapse_line_breaks`); runs of plain spaces are kept.
- **Markup** (`Normalizer::with_markup_tags`): the markup of the given tag names stays as typed: point tags
  (`<laugh/>`, `<laugh>`) and span tags (`<shouting>…</shouting>`, `\s*` allowed before `/` or `>`), and the text
  between markers is normalized piece by piece. Without tags, `<…>` is text like any other.
- **Verbatim spans**: anything between U+E000 and U+E001 (e.g. a pronunciation) is kept as typed.
- **Memo**: each `Normalizer` remembers its last 1024 results, shared by every thread that calls it;
  `normalize(text, lang)` uses one shared normalizer without markup tags.

### Pre-pass for chat and markdown text (on by default)

Since 0.3.0 every normalizer (`Normalizer::new()`, `normalize()`, `Normalizer()` in Python, `zyphra_textnorm_new`)
rewrites the text before the grammars run, for what a speech model is actually given: markdown (emphasis, bullets, headings, tables, links, code fences), HTML/SSML tags and
entities, emoji (named in the text's language from CLDR 46: “grinning face emoji”, “emoji cara sonriendo”), ohm units
in every language, look-alike characters, and readings the grammars get wrong in every language: number agreement
(gender, case, Korean native counters, Hebrew/Arabic reverse agreement), money, dates, times, years, ranges, units,
abbreviations, email addresses, phone numbers, suffixes glued to numbers, and English units, ranges, versions,
powers, decades, and equations (2 - 7 = -5 → es “dos menos siete es igual a menos cinco”). Turned off
(`Normalizer::with_prepass(false)`, `Normalizer(prepass=False)`, `zyphra_textnorm_new_parity`), every output is the
parity output, as in 0.2.0. The pre-pass is the `prepass` cargo feature, in the default features; a build without it
is dependency-free and has only the parity output.

```python
tn = zyphra_textnorm.Normalizer()
tn.normalize("This is **really** important 😀 — see https://www.zyphra.com/zonos", "en")
# 'This is really important grinning face emoji — see zyphra dot com slash zonos'
zyphra_textnorm.Normalizer(prepass=False).normalize("This is **really** important", "en")   # NeMo parity
# 'This is asterisk asterisk really asterisk asterisk important'
zyphra_textnorm.prepass("#VoiceAI rocks", "en")   # the pre-pass alone, with the rules that fired
# ('VoiceAI rocks', [('md.hashtag', '#VoiceAI', 'VoiceAI')])
```

The rules were prototyped in Python and reviewed against the golden files and NeMo's own tests; each is narrow on
purpose (configured markup tags and verbatim spans are never touched). The 61 markup, character and English rules are
in `src/prepass/` (in the order of `prepass::ORDER`); 410 per-language rules and 6 shared ones are in
`src/prepass/lang/` (`<lang>.rs`, `shared.rs`), each a port of its prototype module, checked against the prototype's
output by `tests/prepass/lang/<lang>.jsonl.zst`. `tests/prepass.rs` pins every golden row the pre-pass changes
(`tests/prepass/golden.jsonl.zst`, with whether its output was reviewed) and checks that it changes no other row. The
feature adds the crate's only dependencies, `fancy-regex` and `regex`.

With the pre-pass off, the output is the spoken form of the reference grammars, quirks included: parity is the
contract. The original packages retain the frozen NeMo wrapper behavior (`oracle/reference_textnorm.py`); new locale
packages use the locale-gated ZONOS3 wrapper (`oracle/new_locale_wrapper.py`). This covers sentence punctuation,
native symbol and operator words, ordinal periods, numeric conventions, bracket spacing, and markup/verbatim
preservation. Numeric dates follow locale conventions (`tl` uses month/day/year); ISO `YYYY-MM-DD` avoids ambiguity.
Dutch million and billion remainders use the corrected fixed-width source grammar, preventing omitted zero groups from
changing the number's scale.

## Install

| | |
| --- | --- |
| Rust | `cargo add zyphra-textnorm` (MSRV 1.88) |
| Python (≥ 3.9) | `pip install zyphra-textnorm`: abi3 wheels for Linux (manylinux, x86_64 and aarch64), macOS (x86_64, arm64) and Windows (x64, arm64); elsewhere pip builds the sdist, which needs cargo |
| C / C++ | `cargo rustc --release --lib --features capi --crate-type staticlib` → `target/release/libzyphra_textnorm.a` (`zyphra_textnorm.lib` on MSVC), header `include/zyphra_textnorm.h`. Link the platform's Rust std libraries (`-lpthread -ldl -lm` on Linux, `ws2_32 userenv ntdll bcrypt` on MSVC). |

The release profile keeps `panic = "unwind"`: a panic inside a grammar is a grammar failure (the sentence kept as
typed). A build with `panic = "abort"` aborts on one instead.

## Layout

| Path | Contents |
| --- | --- |
| `src/` | The library: `lib.rs` (API), `wrapper.rs` (line breaks, markup, verbatim spans, per-language passes, sentence retry, memo), `pipeline.rs` (NeMo's `Normalizer.normalize`), `lattice.rs` (the tagger's Viterbi), `tag.rs`, `permute.rs`, `moses.rs`, `punct_post.rs`, `ffi.rs` (C ABI), `prepass/` (the opt-in pre-pass; its tables in `data/prepass/`, written by `oracle/prepass_tables.py`) |
| `src/lang/<l>/` | One grammar package: `taggers/` and `verbalizers/` mirror the upstream files one to one |
| `data/` | The upstream `.tsv` tables verbatim, the sacremoses perluniprops tables, frozen Unicode 15.0 tables |
| `include/` | The C header |
| `python/` | The Python extension `zyphra_textnorm` (PyO3; `pyproject.toml` at the root) |
| `oracle/` | The differential-test oracle: vendored NeMo r1.2.0 and ZONOS3 locale packages, reference wrappers, corpus and golden dump scripts |
| `tests/` | Differential tests; the corpus (`corpus/`), the oracle's outputs (`golden/*.jsonl.zst`) and the oracle-confirmed equal-cost ties the port resolves differently (`ties/`) |
| `PORTING.md` | How a NeMo grammar becomes Rust, with the verified pynini semantics |

## Develop

```sh
cargo test --release --features capi       # unit tests, the goldens (pre-pass off) and the pre-pass (tests/prepass.rs)
cargo run --release --example normalize -- en 'Save $20k.'
cargo bench                                # median µs per call and per 100 chars, allocations
cargo bench --no-default-features --features lang-de   # one language, faster to build
uv venv && uv pip install -e . && .venv/bin/python -c 'import zyphra_textnorm'
```

The bench warms every case before timing it and reports the median of 101 calls on a cleared memo. Run it at load
below 4: medians swing by 1.5× on a busy machine. The target is ≤ 20 µs per 100 characters on every language's line.

## Release

The crate and the Python package share the version (`[workspace.package]` in `Cargo.toml`). Pushing a `v<version>`
tag runs `.github/workflows/release.yml`: it builds the wheels and the sdist and installs and runs each wheel on its
platform, then checks that the tag is `v` + the `Cargo.toml` version, runs `cargo publish -p zyphra-textnorm`, and
uploads the wheels and the sdist to PyPI. Both registries use trusted publishing (no tokens in the repository): the
crates.io and PyPI projects trust `Zyphra/zyphra-textnorm`, workflow `release.yml`, environments `crates-io` and
`pypi`. A failed publish job is re-run from the run page; `gh workflow run release.yml --ref v<version>` reruns the
whole release for an existing tag.

## Parity

The goldens in `tests/golden/` are outputs of the vendored reference grammars (pynini) behind the locale-gated wrapper
(`oracle/reference_textnorm.py`), committed `zstd -19`-compressed (the tests read the `.zst` directly; the plain
`.jsonl` the dump scripts write are gitignored). The corpus is generated from every table of each language
(`oracle/gen_corpus.py` for the original nine, `oracle/gen_new_corpus.py` for the added locales), upstream test cases,
and handcrafted lines. `oracle/dump_new_goldens.py` compiles one new locale at a time and writes compressed goldens.
The `calls` test checks every grammar call the wrapper made; the `golden` test checks every end-to-end row. The
original corpus has 735 calls where the oracle picks among paths of equal float32 cost by its compiled arc order
(`tests/ties/`, PORTING.md "Ties"); a listed call that no longer differs fails as stale. The English number-name FARs,
which have no source, are checked against a 457k-row dump of the FSTs (`tests/en_cardinal.rs`).

Use a native Python environment with pynini, or the linux/amd64 oracle container (Rosetta on Apple silicon):

```sh
colima start --vz-rosetta --cpu 4 --memory 8
docker build --platform linux/amd64 -f oracle/Dockerfile -t zyphra-textnorm-oracle .
docker run --rm -v "$PWD":/repo -v "$HOME/.cache/zyphra-textnorm-oracle":/cache -w /repo zyphra-textnorm-oracle \
    python oracle/dump_golden.py --cache /cache --lang en --corpus tests/corpus/en.jsonl --out tests/golden/en.jsonl
zstd -19 -f tests/golden/en.jsonl -o tests/golden/en.jsonl.zst
docker run --rm -v "$PWD":/repo -v "$HOME/.cache/zyphra-textnorm-oracle":/cache -w /repo zyphra-textnorm-oracle \
    python oracle/triage.py --lang en --text 'Call me at 123 Main Street, please.'
```

`zstd -d -k tests/golden/<l>.jsonl.zst` restores the plain file for inspection. `oracle/gen_corpus.py` (host Python)
regenerates `tests/corpus/`; `oracle/gen_unicode_tables.py` the Unicode tables (must run on CPython 3.12 / Unicode
15.0, like the oracle).

## License

MIT (`LICENSE`) for original code; NeMo-derived grammars and tables are Apache-2.0, CLDR-derived locale data is
Unicode-3.0, and the Moses detokenizer port is MIT (sacremoses). See `NOTICE` and `licenses/`.
