//! Differential tests against the frozen reference pipeline (`tests/golden/<lang>.jsonl.zst`, dumped by
//! `oracle/dump_golden.py`, compressed with `zstd -19`).
//!
//! - `calls`: grammar parity. Every NeMo `Normalizer.normalize` call the reference wrapper made (`calls[].in`) must
//!   give the same result through `pipeline::normalize` (`calls[].out`, or an error where the oracle raised).
//! - `golden`: end to end through `Normalizer::normalize` with the oracle's markup tags (wrapper passes, markup,
//!   verbatim spans, sentence retry): every row equals the oracle's output.
//!
//! The one exception is `tests/ties/<lang>.jsonl`: calls where the oracle's tagging and the port's cost the same in
//! the oracle's own tagger (checked by `oracle/triage.py --score`) and the port picks differently (PORTING.md,
//! "Ties"). A listed call passes only while the port still produces the listed tagging; a listed call that no longer
//! differs fails as stale. A `golden` row passes when its only differing calls are listed ties.
//!
//! `GOLDEN_LANG=en` restricts the run, `GOLDEN_LIMIT=n` caps the mismatches printed, `GOLDEN_STAGE=tags` also
//! compares the tagged strings of every call (spacing-insensitive; a porting aid, not asserted),
//! `GOLDEN_TIES_DRAFT=<dir>` writes `<dir>/<lang>.jsonl` with every unexplained call whose tagging differs from the
//! oracle's (the input of `triage.py --score`; `reason` left null).
//! `cargo test --release --test golden`.

mod common;

use std::collections::{HashMap, HashSet};
use std::io::Write;
use std::path::PathBuf;

use serde::Deserialize;
use zyphra_textnorm::Normalizer;
use zyphra_textnorm::pipeline::{self, Grammar};

#[derive(Deserialize)]
struct Call {
    #[serde(rename = "in")]
    input: String,
    tags: Option<String>,
    out: Option<String>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct Row {
    text: String,
    out: String,
    #[serde(default)]
    calls: Vec<Call>,
}

const LANGS: [&str; 9] = ["en", "de", "es", "fr", "it", "pt", "ja", "zh", "ko"];

/// The markup the oracle keeps as typed (`oracle/reference_textnorm.py`).
const ORACLE_MARKUP_TAGS: [&str; 7] = ["laugh", "breath", "sigh", "cough", "panting", "shouting", "crying"];

fn root() -> PathBuf {
    common::tests_dir()
}

fn rows(lang: &str) -> Vec<Row> {
    common::golden_lines(lang).iter().map(|l| serde_json::from_str(l).unwrap()).collect()
}

fn selected() -> Vec<&'static str> {
    let only = std::env::var("GOLDEN_LANG").ok();
    LANGS.into_iter().filter(|l| only.as_deref().is_none_or(|o| o == *l)).collect()
}

fn limit() -> usize {
    std::env::var("GOLDEN_LIMIT").ok().and_then(|s| s.parse().ok()).unwrap_or(20)
}

/// Tagged-string spacing the port's serializer and the taggers do not share, removed (as `triage.py`'s
/// `canonical_tags`): runs of spaces become one, no space between `}` and the next `tokens`, none at either end.
fn canonical(s: &str) -> String {
    let squashed = s.split(' ').filter(|p| !p.is_empty()).collect::<Vec<_>>().join(" ");
    squashed.replace("} tokens", "}tokens")
}

fn moses(lang: &str) -> bool {
    matches!(lang, "en" | "zh" | "ja" | "ko")
}

#[derive(Deserialize)]
struct Tie {
    #[serde(rename = "in")]
    input: String,
    rust_tags: String,
    reason: String,
}

/// Why a listed call differs (PORTING.md, "Ties").
const REASONS: [&str; 3] = ["number", "order", "f32"];

/// The listed ties of a language: call input -> the port's tagged string (canonical).
fn ties(lang: &str) -> HashMap<String, String> {
    let path = root().join("ties").join(format!("{lang}.jsonl"));
    let Ok(src) = std::fs::read_to_string(&path) else { return HashMap::new() };
    let mut out = HashMap::new();
    for line in src.lines().filter(|l| !l.trim().is_empty()) {
        let t: Tie = serde_json::from_str(line).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        assert!(REASONS.contains(&t.reason.as_str()), "{}: reason {:?} of {:?}", path.display(), t.reason, t.input);
        assert!(
            out.insert(t.input.clone(), canonical(&t.rust_tags)).is_none(),
            "{}: {:?} twice",
            path.display(),
            t.input
        );
    }
    out
}

fn rust_tags(g: &dyn Grammar, input: &str) -> Option<String> {
    let chars: Vec<char> = zyphra_textnorm::text::py_strip(input).chars().collect();
    if chars.is_empty() { None } else { pipeline::tagged_string(g, &chars).ok() }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Verdict {
    Match,
    /// Differs, and is a listed tie the port still produces.
    Tie,
    Bad,
}

fn check(
    g: &dyn Grammar,
    lang: &str,
    call: &Call,
    ties: &HashMap<String, String>,
) -> (Verdict, Result<String, String>) {
    let got = pipeline::normalize(g, &call.input, moses(lang)).map_err(|e| format!("{e:?}"));
    let ok = match (&call.error, &got) {
        (Some(_), Err(_)) => true,
        (None, Ok(s)) => Some(s) == call.out.as_ref(),
        _ => false,
    };
    if ok {
        return (Verdict::Match, got);
    }
    let listed = ties.get(&call.input).is_some_and(|t| rust_tags(g, &call.input).is_some_and(|r| canonical(&r) == *t));
    (if listed { Verdict::Tie } else { Verdict::Bad }, got)
}

#[test]
fn calls() {
    let stage_tags = std::env::var("GOLDEN_STAGE").is_ok_and(|s| s == "tags");
    let draft_dir = std::env::var_os("GOLDEN_TIES_DRAFT").map(PathBuf::from);
    let mut total_bad = 0usize;
    for lang in selected() {
        let Some(g) = zyphra_textnorm::lang::grammar(lang) else { continue };
        let ties = ties(lang);
        let (mut n, mut bad, mut tied, mut tag_bad) = (0usize, 0usize, 0usize, 0usize);
        let mut used: HashSet<&str> = HashSet::new();
        let mut draft: Vec<String> = Vec::new();
        let mut drafted: HashSet<String> = HashSet::new();
        let rows = rows(lang);
        for row in &rows {
            for call in &row.calls {
                n += 1;
                if stage_tags {
                    let got = rust_tags(g, &call.input);
                    if got.as_deref().map(canonical) != call.tags.as_deref().map(canonical) {
                        tag_bad += 1;
                        if tag_bad <= limit() {
                            eprintln!("[{lang} tags] {:?}\n    want {:?}\n    got  {:?}", call.input, call.tags, got);
                        }
                    }
                }
                let (verdict, got) = check(g, lang, call, &ties);
                match verdict {
                    Verdict::Match => {}
                    Verdict::Tie => {
                        tied += 1;
                        used.insert(call.input.as_str());
                    }
                    Verdict::Bad => {
                        bad += 1;
                        if bad <= limit() {
                            let want = call.error.as_ref().map(|e| format!("<raises {e}>")).or(call.out.clone());
                            eprintln!("[{lang}] {:?}\n    want {:?}\n    got  {:?}", call.input, want, got);
                        }
                        let (Some(oracle), Some(port)) = (&call.tags, rust_tags(g, &call.input)) else { continue };
                        if canonical(oracle) != canonical(&port) && drafted.insert(call.input.clone()) {
                            let line = serde_json::json!({"in": call.input, "oracle_tags": oracle, "rust_tags": port,
                                "reason": null});
                            draft.push(line.to_string());
                        }
                    }
                }
            }
        }
        let stale: Vec<&String> = ties.keys().filter(|k| !used.contains(k.as_str())).collect();
        for k in stale.iter().take(limit()) {
            eprintln!("[{lang} stale tie] {k:?}: listed, but the call no longer differs (or its tagging changed)");
        }
        if let Some(dir) = &draft_dir {
            std::fs::create_dir_all(dir).unwrap();
            let mut f = std::fs::File::create(dir.join(format!("{lang}.jsonl"))).unwrap();
            for line in &draft {
                writeln!(f, "{line}").unwrap();
            }
        }
        let tags = if stage_tags { format!(", {tag_bad} tagged-string mismatches") } else { String::new() };
        eprintln!("[{lang}] {n} grammar calls, {bad} mismatches, {tied} listed ties, {} stale ties{tags}", stale.len());
        total_bad += bad + stale.len();
    }
    assert_eq!(total_bad, 0, "grammar calls differ from the oracle (or stale ties)");
}

#[test]
fn golden() {
    let mut total_bad = 0usize;
    let tn = Normalizer::with_markup_tags(ORACLE_MARKUP_TAGS);
    for lang in selected() {
        let Some(g) = zyphra_textnorm::lang::grammar(lang) else { continue };
        let ties = ties(lang);
        let (mut n, mut bad, mut tied) = (0usize, 0usize, 0usize);
        for row in rows(lang) {
            n += 1;
            let got = tn.normalize(&row.text, lang);
            if got == row.out {
                continue;
            }
            let verdicts: Vec<Verdict> = row.calls.iter().map(|c| check(g, lang, c, &ties).0).collect();
            if verdicts.contains(&Verdict::Tie) && !verdicts.contains(&Verdict::Bad) {
                tied += 1;
                continue;
            }
            bad += 1;
            if bad <= limit() {
                eprintln!("[{lang}] {:?}\n    want {:?}\n    got  {:?}", row.text, row.out, got);
            }
        }
        eprintln!("[{lang}] {n} rows, {bad} mismatches, {tied} explained by listed ties");
        total_bad += bad;
    }
    assert_eq!(total_bad, 0, "end-to-end outputs differ from the oracle");
}
