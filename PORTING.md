# Porting a NeMo grammar to `zyphra-textnorm`

How each `text_normalization/<lang>/` package of NeMo r1.2.0 becomes Rust under `src/lang/<lang>/`. The runtime
around the grammars (`pipeline.rs`, `lattice.rs`, `tag.rs`, `permute.rs`, `moses.rs`, `punct_post.rs`, `wrapper.rs`)
is finished; a port only supplies a `Grammar` (`pipeline.rs`). The upstream Python lives in
`oracle/nemo_text_processing/text_normalization/`; it is the specification. The oracle container answers any question
the source leaves open.

## Contract

```rust
pub trait Grammar: Send + Sync {
    fn code(&self) -> &'static str;                      // "en", "de", …
    fn shape(&self) -> Shape;                            // lattice.rs: En | De | Fr | Ko | Pt | Cjk
    fn classifiers(&self) -> &[Box<dyn Classifier>];     // the `classify` union, source order
    fn punct(&self) -> Option<&dyn Classifier>;          // the separately wrapped punct item (en-family)
    fn verbalize(&self, token: &Dict) -> Option<String>; // VerbalizeFinalFst on ONE token body, one field order
    fn verbalize_split(&self, split: &[Dict]) -> Option<String> { … } // default: token by token, joined
    fn token_join(&self) -> &'static str { " " }          // "" for zh/ja
    fn post_process(&self, text: String) -> String { text } // en PostProcessingFst only
}
pub trait Classifier: Send + Sync {
    fn candidates(&self, text: &[char], start: usize, out: &mut Vec<Candidate>);
    fn materialize(&self, text: &[char], start: usize, candidate: &mut Candidate) {} // fill a lazy tag
}
pub struct Candidate { pub end: usize, pub cost: Cost, pub rank: i32, pub tag: String }
// tag.rs: the parsed tagged string, borrowing from it
pub enum Value<'a> { Str(Cow<'a, str>), None, Dict(Dict<'a>), True }
pub type Field<'a> = (Cow<'a, str>, Value<'a>);
pub type Dict<'a> = Vec<Field<'a>>;
```

- `lang/mod.rs::grammar(code)` returns `&'static dyn Grammar` (a `static GRAMMAR: LazyLock<…>` in `lang/<l>/mod.rs`).
- `Candidate.tag` is the tagger's output for the span **exactly as the FST writes it** inside `tokens { … }`:
  `cardinal { integer: "one" }`, `name: "hello"`, `date { month: "january" day: "five" preserve_order: true }`.
  The pipeline wraps each in `tokens { ` … ` }`, joins with spaces and parses it with the ported `TokenParser`, so
  upstream quirks in the text (a missing space, a stray quote) are reproduced by writing the same text.
- `Candidate.cost` includes the classifier's top-level `add_weight` in `tokenize_and_classify.py` **and** every
  internal weight on the path (TSV third column, `add_weight` inside the sub-graphs). `text::cost(1.1)` etc.
- `Candidate.rank`: tie-break among equal-cost candidates of one classifier, lower wins. The lattice adds
  `classifier_index * 1000`. Start with source order of the union branch; triage adjusts.
- `verbalize(token)`: `token` is the body of one `tokens { … }`, e.g. `[("cardinal", Dict([("integer", Str("one"))]))]`
  or `[("name", Str("hello"))]`, in **one** field ordering (the pipeline calls it for every ordering `_permute` yields,
  first `Some` wins). Return `None` when the upstream verbalizer FST has no path for that ordering; when it has several
  outputs return the cheapest (ties: source union order). Use `common::Fields` to consume fields in the order the FST
  deletes them; `common::verbalize_name` is the shared `word`/`whitelist` verbalizer. Parsed keys and values borrow
  the tagged string; a verbalizer that re-splits a field builds owned ones (`Value::Str(s.to_string().into())`).
- `verbalize_split(split)`: override only when the verbalizer can read across token boundaries (de) or to write all
  tokens into one buffer; the result must equal the default's.
- The punctuation classifier is `common::Punctuation` (see `en/taggers/punctuation.py`); zh/ja/ko list theirs among
  `classifiers()` with its weight.

## The tagger: every span, every output

The FST accepts **all** spans; the Viterbi in `lattice.rs` picks the path. A classifier must therefore push every
span it accepts at `start` (not just the longest) and, where the FST is non-functional for a span, every output
with its own cost. Pruning is allowed only when a candidate provably can never be on a cheapest path (e.g. two
outputs of one span with different costs and identical tags: keep the cheaper).

The top-level `shape` enforces how tokens, punct items and whitespace runs may follow each other; whitespace never
reaches a classifier as a span start (a classifier may still consume spaces *inside* its span when the FST does).

Tag text is the expensive part: most candidates never reach the best path. A classifier may push candidates with an
empty `tag` and write it in `materialize`, which the lattice calls once per best-path item, on the classifier that
pushed it. `(start, end, cost, rank)` must then identify the candidate among those pushed at `start`. Wrapper
classifiers (a language's single union entry) forward `materialize` to the member that pushed the winner. Rather than
rerunning that member, record what the winning branch read during exploration (es: `Lazy::recall` + `Stash`, cleared
at position 0) and write only its tag.

## Weights and ties

- `Cost` is `i64` micro-units: `cost(1.1) == 1_100_000`. Every NeMo weight is a multiple of 0.00001.
- `pynutil.add_weight(g, w)`: add `w` to every path through `g`. `closure(x)` with weighted `x`: per repetition.
- TSV third column = weight of that row.
- `shortestpath(unique=True)` ties (verified): `cross("a","q") | cross("a","p")` picks `p` after `optimize()`
  and `q` before it; `string_map([("$","dollar"),("$","us dollar")])` picks `us dollar` in either order.
  When equal-cost outputs differ only in text, prefer what the oracle shows (query it) and pin the input in a
  unit test next to the rank.

## Ties

The oracle sums path weights in float32 and picks among equal-cost paths by its compiled FST's arc order, which no
rule in the grammar source states. The port sums exactly and breaks ties by `(digit items, rank)` in `lattice.rs`:
among equal-cost paths, the one with fewer items whose span holds a digit wins, so a number is read as one token
wherever the grammar allows it. Inside a classifier, rank equal-cost readings of the same digits so the numerically
correct one comes first. Where the oracle's choice follows a stable source-level rule, match it; never keep a fitted
order with no grammar meaning.

A call that still differs is allowed only in `tests/ties/<lang>.jsonl`, written by
`triage.py --score <draft> --write tests/ties/<lang>.jsonl`, which keeps a row only when the oracle's own
tagger gives both taggings the same float32 cost (±1 ulp). Each row has a `reason`:

- `number`: the port reads the digits as the right number (whole, or the numerically correct reading) where the
  oracle's pick does not;
- `order`: equal-cost alternatives with no grammar-level preference;
- `f32`: the oracle's own small weights decide in exact arithmetic but vanish in its float32 sum.

The `golden` test passes a listed call only while the port still produces the listed tagging, and fails on listed
calls that no longer differ (stale). `GOLDEN_TIES_DRAFT=<dir>` writes the draft (every unexplained call whose
tagging differs; fill in the reasons). Never hand-edit the tie files.

## pynini idioms → Rust

| pynini | Rust |
| --- | --- |
| `pynini.string_file(p)` | `tsv!(NAME, "<l>/<path>.tsv")` → `text::Table` (comment `#`, `\#`, trailing `\r` kept, 3rd col weight) |
| `load_labels(p)` (csv.reader) | `labels!(NAME, "<l>/<path>.tsv")` → `Vec<Vec<String>>` (`#` is **not** a comment; `"` quoting) |
| `string_map(list)` | `Table::from_pairs` |
| `pynini.invert(t)` | swap key/value when looking up |
| `a + b` | sequence: try every split |
| `a \| b` | union: push candidates of both |
| `pynutil.insert(s)` / `delete(s)` | write / consume |
| `closure(x, m, n)` | loop |
| `x @ y` | apply `y` to every output of `x` (both may be non-functional) |
| `plurals._priority_union(q, r, Σ*)` | if `q` accepts the input (any output) use `q`'s outputs, else `r`'s |
| `cdrewrite(τ, λ, ρ, Σ*)` | obligatory, simultaneous, **left-to-right**, contexts tested on the **input** of the rewrite (verified: `a→b / b _` on `baa` gives `bbb`, i.e. the left context sees already-rewritten output; `a→b / _ b` on `aab` gives `abb`). At one position a τ with several matching lengths gives all of them (non-functional: `{a→x, ab→y}` on `ab` → `xb` and `y`). Overlapping matches: `aa→x` on `aaa` → `xa`. `[BOS]`/`[EOS]` are position tests. |
| `NEMO_SIGMA` | any string |
| `NEMO_CHAR` | any char |
| `NEMO_WHITE_SPACE` | `text::is_nemo_space` (`' ' \t \n \r U+00A0`) |
| `NEMO_DIGIT`, `NEMO_ALPHA`, `NEMO_UPPER/LOWER` | ASCII only |
| `NEMO_NOT_SPACE`, `NEMO_NOT_QUOTE` | any char but those |
| `TO_LOWER`/`TO_UPPER` | single ASCII letter |
| `convert_space(g)` | spaces in `g`'s output → U+00A0 (`text::space_to_nbsp`) |
| `delete_space` / `delete_extra_space` | `closure(WS)` deleted / `WS+` → `" "` |
| `.project("input")` | accept the inputs only |

Upstream grammars cannot be "simplified": port each union branch, keep its weight, keep its quirks. Python-side
logic that builds lists (`for x in labels: …`) runs once at table-load time in Rust, same semantics (ASCII-only
`str.upper()` only where NeMo uses `TO_UPPER`; `str.lower()`/`capitalize()` are Unicode in Python — use Rust's
`to_lowercase`/`text::py_capitalize`).

## Verifying a port

1. Goldens: `tests/golden/<l>.jsonl.zst` (zstd; `zstd -d -k` for a plain copy) rows
   `{"text","out","fallback","calls":[{"in","tags","verb","out","error"}]}`. `calls[i].in` is the exact grammar input
   of the i-th NeMo call (after the wrapper's pre-pass); `tags` the tagger's shortest path (null when it raised);
   `verb` the verbalizer output per split.
2. `cargo test --release --test golden` with `GOLDEN_LANG=<l>`; `GOLDEN_STAGE=tags` also compares
   the tagged strings of every call (spacing-insensitive) — fix tagging first, then verbalizing.
3. The oracle (Docker, `colima` running):
   `docker run --rm -v "$PWD":/repo -v "$HOME/.cache/zyphra-textnorm-oracle":/cache -w /repo zyphra-textnorm-oracle python oracle/triage.py --lang <l> --raw --text "…"`
   (`--tagged 'tokens { … }'` runs only the verbalizer; `--file` batches; `--score` prices taggings; grammars are
   cached in `/cache`). Under Rosetta each container start costs ~5-20 s; batch queries with `--file`.
4. Parity: every grammar call (`calls` test) and every end-to-end row (`golden` test) equals the oracle, except the
   listed ties ("Ties"); 0 mismatches and 0 stale ties. Any other difference is a port bug.
5. Speed: `cargo bench` (all languages, at load < 4: timings swing 1.5× above it), median
   ≤ 20 µs per 100 chars on the language's line. `--no-default-features --features lang-<l>` builds one language for
   iteration. Build tag text only for the candidates that win (`materialize`), not on explored branches.

## Layout

`lang/<l>/mod.rs` (Grammar impl + union + shape), `lang/<l>/taggers/<file>.rs`, `lang/<l>/verbalizers/<file>.rs`, one
Rust file per upstream file, same base name. Shared helpers of a language (its `graph_utils.py`) in
`lang/<l>/graph_utils.rs`. Data: `data/<l>/…` (verbatim copies). No new crate dependencies.
