//! The opt-in pre-pass (`--features prepass`, `Normalizer::with_prepass`).
//!
//! - `golden`: every golden row (`tests/golden/`) through a pre-pass normalizer with the oracle's markup tags. A row in
//!   `tests/prepass/golden.jsonl` must give its listed output (each is a reviewed verdict, a group verdict, or pinned
//!   while unreviewed: the `status` field); every other row must give exactly what the normalizer gives without the
//!   pre-pass (the oracle's output or a listed tie, which `golden.rs` checks).
//! - `cases`: the workbench cases (`tests/prepass/cases.jsonl`: chat and markdown text from the dogfood reports, the
//!   markup rules, breakages found in fineweb-edu) give their listed output.
//!
//! Both files are written by the workbench (`export_prepass_tests.py`) from the reviewed outputs; a rule change that
//! moves any golden row shows up here. `PREPASS_LANG=en` restricts `golden`, `GOLDEN_LIMIT=n` caps the mismatches
//! printed. `cargo test --release --features prepass --test prepass`.
#![cfg(feature = "prepass")]

mod common;

use std::collections::HashMap;

use serde::Deserialize;
use zyphra_textnorm::Normalizer;

const ORACLE_MARKUP_TAGS: [&str; 7] = ["laugh", "breath", "sigh", "cough", "panting", "shouting", "crying"];
const STATUSES: [&str; 3] = ["reviewed", "group", "unreviewed"];

#[derive(Deserialize)]
struct Golden {
    text: String,
}

#[derive(Deserialize)]
struct Expected {
    lang: String,
    text: String,
    out: String,
    status: String,
}

#[derive(Deserialize)]
struct Case {
    group: String,
    lang: String,
    text: String,
    out: String,
}

fn limit() -> usize {
    std::env::var("GOLDEN_LIMIT").ok().and_then(|s| s.parse().ok()).unwrap_or(20)
}

fn jsonl<T: for<'de> Deserialize<'de>>(name: &str) -> Vec<T> {
    let path = common::tests_dir().join("prepass").join(name);
    let src = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    src.lines().filter(|l| !l.trim().is_empty()).map(|l| serde_json::from_str(l).unwrap()).collect()
}

#[test]
fn golden() {
    let only = std::env::var("PREPASS_LANG").ok();
    let mut expected: HashMap<(String, String), Expected> = HashMap::new();
    for e in jsonl::<Expected>("golden.jsonl") {
        assert!(STATUSES.contains(&e.status.as_str()), "status {:?} of {:?}", e.status, e.text);
        expected.insert((e.lang.clone(), e.text.clone()), e);
    }
    let plain = Normalizer::with_markup_tags(ORACLE_MARKUP_TAGS);
    let pre = Normalizer::with_markup_tags(ORACLE_MARKUP_TAGS).with_prepass(true);
    let (mut total_bad, mut listed_seen) = (0usize, 0usize);
    for lang in zyphra_textnorm::LANGUAGES {
        if only.as_deref().is_some_and(|o| o != lang) || !zyphra_textnorm::supported(lang) {
            continue;
        }
        let (mut n, mut bad, mut listed) = (0usize, 0usize, 0usize);
        for line in common::golden_lines(lang) {
            let row: Golden = serde_json::from_str(&line).unwrap();
            n += 1;
            let got = pre.normalize(&row.text, lang);
            let want = match expected.get(&(lang.to_string(), row.text.clone())) {
                Some(e) => {
                    listed += 1;
                    e.out.clone()
                }
                None => plain.normalize(&row.text, lang),
            };
            if got != want {
                bad += 1;
                if bad <= limit() {
                    eprintln!("[{lang}] {:?}\n    want {want:?}\n    got  {got:?}", row.text);
                }
            }
        }
        eprintln!("[{lang}] {n} rows, {listed} with a listed pre-pass output, {bad} mismatches");
        total_bad += bad;
        listed_seen += listed;
    }
    assert_eq!(total_bad, 0, "pre-pass outputs differ from tests/prepass/golden.jsonl or change an unlisted row");
    if only.is_none() {
        assert!(listed_seen >= expected.len(), "tests/prepass/golden.jsonl lists rows that are not in the goldens");
    }
}

#[test]
fn cases() {
    let tn = Normalizer::new().with_prepass(true);
    let mut bad = 0usize;
    let cases = jsonl::<Case>("cases.jsonl");
    for c in &cases {
        let got = tn.normalize(&c.text, &c.lang);
        if got != c.out {
            bad += 1;
            eprintln!("[{} {}] {:?}\n    want {:?}\n    got  {got:?}", c.group, c.lang, c.text, c.out);
        }
    }
    assert_eq!(bad, 0, "{bad} of {} cases differ", cases.len());
}

#[test]
fn off_by_default() {
    let tn = Normalizer::new();
    assert!(!tn.prepass());
    assert_eq!(
        tn.normalize("This is **really** important.", "en"),
        "This is asterisk asterisk really asterisk asterisk important."
    );
    assert!(Normalizer::new().with_prepass(true).prepass());
}

#[test]
fn hits_name_the_rules() {
    let (out, hits) = zyphra_textnorm::prepass::apply("Loving it #blessed 😀", "en", &[] as &[&str]);
    assert_eq!(out, "Loving it blessed grinning face emoji");
    let rules: Vec<&str> = hits.iter().map(|h| h.rule).collect();
    assert_eq!(rules, ["ch.emoji", "md.hashtag"]);
    for id in zyphra_textnorm::prepass::ORDER {
        assert_eq!(zyphra_textnorm::prepass::ORDER.iter().filter(|x| **x == id).count(), 1, "{id} twice");
    }
}
