# Porting a NeMo grammar to `zyphra-textnorm`

How each reference `text_normalization/<lang>/` package becomes Rust under `src/lang/<lang>/`. The original nine
packages use NeMo r1.2.0; the additional 34 use ZONOS3's production locale grammars and Unicode CLDR release-49 data.
The runtime around the grammars (`pipeline.rs`, `lattice.rs`, `tag.rs`, `permute.rs`, `moses.rs`, `punct_post.rs`,
`wrapper.rs`) is shared; a port supplies a `Grammar` (`pipeline.rs`). The Python under
`oracle/nemo_text_processing/text_normalization/` is the specification. New locale wrapper rules are frozen in
`oracle/new_locale_wrapper.py`, gated so original locale behavior stays unchanged.

## Contract

```rust
pub trait Grammar: Send + Sync {
    fn code(&self) -> &'static str;                      // "en", "de", …
    fn shape(&self) -> Shape;                            // lattice.rs: exact token/punctuation/whitespace automaton
    fn classifiers(&self) -> &[Box<dyn Classifier>];     // the `classify` union, source order
    fn punct(&self) -> Option<&dyn Classifier>;          // the separately wrapped punct item (en-family)
    fn pre_classify<'t>(&self, text: &'t [char]) -> Cow<'t, [char]> { Cow::Borrowed(text) }
    fn verbalize(&self, token: &Dict) -> Option<String>; // VerbalizeFinalFst on ONE token body, one field order
    fn verbalize_split(&self, split: &[Dict]) -> Option<String> { … } // default: token by token, joined
    fn token_join(&self) -> &'static str { " " }          // "" for zh/ja
    fn post_process(&self, text: String) -> String { text } // en/hi/vi PostProcessingFst
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

The added locale packages also use `Shape::Separated` (exactly one token-bearing item per whitespace-delimited
chunk), `SeparatedWeighted` (the same topology, with a source weight on each internal whitespace separator),
`SeparatedOrPunct` (a chunk can instead be one punctuation item), `SeparatedWithPunct` (a punctuation
item run is also a chunk), and `Thai` (adjacent tokens with ASCII-space-only separators). Leading and trailing
whitespace remains free in `SeparatedWeighted`. Choose the source graph's shape, not the closest older language shape.

## The tagger: every span, every output

The FST accepts **all** spans; the Viterbi in `lattice.rs` picks the path. A classifier must therefore push every
span it accepts at `start` (not just the longest) and, where the FST is non-functional for a span, every output
with its own cost. Pruning is allowed only when a candidate provably can never be on a cheapest path (e.g. two
outputs of one span with different costs and identical tags: keep the cheaper).
Different tags can also be dominated when their candidates have the same start, end, and lattice transition kind
but strictly higher cost. To skip a recognizer, prove its complete minimum cost, including every internal negative
weight and range composition; preserve equal-cost paths and never compare token and punctuation transitions.

The top-level `shape` enforces how tokens, punct items and whitespace runs may follow each other.
The lattice skips recognition for an item kind only when no reachable automaton state can consume it.
For example, a separated chunk cannot consume a second token before whitespace; this does not restrict
spaces *inside* a single candidate span.

A successful parser must account for its entire candidate span, not silently ignore unparsed fields. For example,
Russian `1 мая 2024 г. важный текст` ends the date after `г.` and retains the following prose; recognizing the valid
date prefix does not authorize swallowing the rest of the sentence.

Character and lattice scratch buffers are thread-local; reusing their storage does not cache grammar results.
The pipeline collapses repeated ASCII spaces in its owned output buffer rather than allocating a second copy.
The first verbalized split becomes the result buffer directly; later splits append to it. A single split needs
neither a second output allocation nor a copy of its complete spoken text.
After tag serialization the lattice keeps the emptied path vector for reuse, dropping every candidate and tag.
Reused storage also avoids recounting the back-pointer chain solely to preallocate the next result.
Punctuation membership is indexed from the complete frozen mark set: a small low-code-point bitmap and a sorted
table for higher code points. The bitmap boundary chooses storage, never the accepted character domain.

Tag text is the expensive part: most candidates never reach the best path. A classifier may push candidates with an
empty `tag` and write it in `materialize`, which the lattice calls once per best-path item, on the classifier that
pushed it. `(start, end, cost, rank)` must then identify the candidate among those pushed at `start`. Wrapper
classifiers (a language's single union entry) forward `materialize` to the member that pushed the winner. Rather than
rerunning that member, record what the winning branch read during exploration (es: `Lazy::recall` + `Stash`, cleared
at position 0) and write only its tag.
`materialize` is called for every winning candidate, including candidates whose tag was already written: preserve
nonempty tags, especially compound tokens. Recognition prefilters must conservatively include the frozen lexical
input keys (including exceptional suffixes), rather than guessing script ranges or unit-ending characters.
Compound paths must materialize their selected children before embedding them: Vietnamese `~1.5` and `~1/2` retain
the decimal/fraction child after `khoảng`, rather than constructing a nonempty wrapper around an empty lazy tag.
Russian `time.hours` and `measure.cardinal.integer` already hold the complete spoken phrase, including units.
Their exact-shape split writers normalize typed NBSP without adding another unit or allocating a token-sized string.
The Russian union checks complete currency/preposition starters once and can apply first-space family-death rules
ahead of time only for digit-free words; a shorter serial span containing a digit must remain eligible.
Input digits follow the source maps: Unicode `Nd` is not interchangeable with NeMo's ASCII `NEMO_DIGIT`.
Indonesian clock recognition keeps validated integer values, not spoken strings; selected clock, grouped-money, and
grouped-measure paths write their fields directly into one tag buffer. Fast selected renderers must preserve the
original source-row and branch order, including an earlier non-integer money witness at the same cost. Lexical lookup
indexes may reject impossible first bytes or byte lengths only when built from all frozen keys. Indonesian money
starter eligibility is checked once per lattice start: every accepted amount shares its initial digit with the full
remaining input. Selected-span materialization reuses the union's UTF-8 scratch buffer, not a stored output.
Date eligibility can be retired after the first word only when that word is neither a numeric/quoted starter,
a source date prefix, nor a frozen month name or abbreviation; later digits cannot revive such a path.

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

Pynini's method-form `project()` and other mutating FST operations can change an object shared by later graph
branches. Port the resulting graph, not the variable's earlier definition. Hindi and Urdu date ranges accept
projected spoken single-digit words rather than written single digits; Swedish ordinal magnitudes compose with
the cardinal's exposed unpadded component. Confirm such domains with the actual component FST.

An unwrapped `name` does not imply one universal verbalizer. Some source word graphs retain NBSP while
class wrappers convert it to ASCII space; Vietnamese's range verbalizer additionally accepts non-whitespace names
containing literal quotes. Preserve the complete verbalizer union and intentional no-path errors.

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
   After editing oracle grammar sources, use a fresh `--cache` directory: the standalone oracle reuses existing
   FAR archives without the production normalizer's source fingerprint.
4. Parity: every grammar call (`calls` test) and every end-to-end row (`golden` test) equals the oracle, except the
   listed ties ("Ties"); 0 mismatches and 0 stale ties. Any other difference is a port bug.
5. Speed: `cargo bench` (all languages, at load < 4: timings swing 1.5× above it), median
   ≤ 20 µs per 100 chars on the language's line. `--no-default-features --features lang-<l>` builds one language for
   iteration. Build tag text only for the candidates that win (`materialize`), not on explored branches.

## Layout

`lang/<l>/mod.rs` (Grammar impl + union + shape), `lang/<l>/taggers/<file>.rs`, `lang/<l>/verbalizers/<file>.rs`, one
Rust file per upstream file, same base name. Shared helpers of a language (its `graph_utils.py`) in
`lang/<l>/graph_utils.rs`. Data: `data/<l>/…` (verbatim copies). No new crate dependencies.
