//! Per-language rules (the fixes for the workbench's Language tests suggestions), one module per language plus
//! [`shared`]. The prototype is the workbench's `langrules/` package, module for module: `<lang>.rs` ports
//! `langrules/<lang>.py` and `shared.rs` ports `langrules/shared.py`.
//!
//! A language's [`rules`] run right after the character rules (`ch.midbullet`); the shared [`EARLY`] rules run right
//! after `en.url` and the shared [`LATE`] rules after the language's own. Every rule id starts with its language code
//! (`de.money`) or `all.` (shared).
//!
//! `tests/prepass/lang/<lang>.jsonl.zst` holds the prototype's pre-pass text and hits for each language's cases and for
//! every corpus row its rules change (`shared.jsonl.zst`: the shared rules, every language); `tests::parity` checks this
//! port against them (`PREPASS_LANG=de` or `PREPASS_LANG=shared` for one file).

use super::{Ctx, RuleFn};

/// One rule: its id and its function.
pub(super) type LangRule = (&'static str, RuleFn);

mod ar;
mod bg;
mod bn;
mod cs;
mod da;
mod de;
mod el;
mod en;
mod es;
mod fi;
mod fr;
mod gu;
mod he;
mod hi;
mod hu;
mod id;
mod it;
mod ja;
mod ka;
mod kn;
mod ko;
mod ml;
mod mr;
mod ms;
mod nb;
mod nl;
#[path = "or.rs"]
mod or_;
mod pa;
mod pl;
mod pt;
mod ro;
mod ru;
mod shared;
mod sk;
mod sv;
mod ta;
mod te;
mod th;
mod tl;
mod tr;
mod uk;
mod ur;
mod vi;
mod zh;

pub(super) use shared::{EARLY, LATE};

/// The grammar's reading of `s` without the pre-pass (`words("21", "es") == "veintiuno"`): prototype `common.words`.
#[allow(dead_code)]
pub(super) fn words(s: &str, lang: &str) -> String {
    crate::normalize_plain(s, lang)
}

/// Each digit of `s` read alone, joined by `sep`: prototype `common.digit_words`.
#[allow(dead_code)]
pub(super) fn digit_words(s: &str, lang: &str, sep: &str) -> String {
    s.chars().map(|d| words(&d.to_string(), lang)).collect::<Vec<_>>().join(sep)
}

/// The rules of `lang`, in the order they run.
pub(super) fn rules(lang: &str) -> &'static [LangRule] {
    match lang {
        "ar" => ar::RULES,
        "bg" => bg::RULES,
        "bn" => bn::RULES,
        "cs" => cs::RULES,
        "da" => da::RULES,
        "de" => de::RULES,
        "el" => el::RULES,
        "en" => en::RULES,
        "es" => es::RULES,
        "fi" => fi::RULES,
        "fr" => fr::RULES,
        "gu" => gu::RULES,
        "he" => he::RULES,
        "hi" => hi::RULES,
        "hu" => hu::RULES,
        "id" => id::RULES,
        "it" => it::RULES,
        "ja" => ja::RULES,
        "ka" => ka::RULES,
        "kn" => kn::RULES,
        "ko" => ko::RULES,
        "ml" => ml::RULES,
        "mr" => mr::RULES,
        "ms" => ms::RULES,
        "nb" => nb::RULES,
        "nl" => nl::RULES,
        "or" => or_::RULES,
        "pa" => pa::RULES,
        "pl" => pl::RULES,
        "pt" => pt::RULES,
        "ro" => ro::RULES,
        "ru" => ru::RULES,
        "sk" => sk::RULES,
        "sv" => sv::RULES,
        "ta" => ta::RULES,
        "te" => te::RULES,
        "th" => th::RULES,
        "tl" => tl::RULES,
        "tr" => tr::RULES,
        "uk" => uk::RULES,
        "ur" => ur::RULES,
        "vi" => vi::RULES,
        "zh" => zh::RULES,
        _ => &[],
    }
}

/// Runs `rules` on `t`, each under its own id.
pub(super) fn run(rules: &[LangRule], mut t: String, c: &mut Ctx) -> String {
    for &(id, f) in rules {
        c.rid = id;
        t = f(t, c);
    }
    t
}

#[cfg(test)]
mod tests {
    use serde::Deserialize;

    #[derive(Deserialize)]
    struct Row {
        lang: String,
        text: String,
        #[serde(default)]
        tags: Vec<String>,
        out: String,
        hits: Vec<(String, String, String)>,
    }

    /// The port gives the prototype's pre-pass text and hits on every row of `tests/prepass/lang/<lang>.jsonl.zst`.
    #[test]
    fn parity() {
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/prepass/lang");
        let only = std::env::var("PREPASS_LANG").ok();
        let mut bad = Vec::new();
        let mut n = 0;
        for name in crate::LANGUAGES.into_iter().chain(["shared"]) {
            if only.as_deref().is_some_and(|o| !o.split(',').any(|x| x == name)) {
                continue;
            }
            let Ok(file) = std::fs::File::open(dir.join(format!("{name}.jsonl.zst"))) else { continue };
            let mut src = String::new();
            std::io::Read::read_to_string(
                &mut ruzstd::decoding::StreamingDecoder::new(std::io::BufReader::new(file)).expect("zstd"),
                &mut src,
            )
            .expect("zstd");
            for line in src.lines().filter(|l| !l.trim().is_empty()) {
                let r: Row = serde_json::from_str(line).expect("row");
                n += 1;
                let (out, hits) = super::super::apply(&r.text, &r.lang, &r.tags);
                let hits: Vec<_> = hits.into_iter().map(|h| (h.rule.to_string(), h.before, h.after)).collect();
                if out != r.out || hits != r.hits {
                    bad.push(format!(
                        "{} {:?}\n  want {:?} {:?}\n  got  {:?} {:?}",
                        r.lang, r.text, r.out, r.hits, out, hits
                    ));
                }
            }
        }
        // the packaged crate ships no fixtures; in the repository every file must have been read
        assert!(n > 0 || !dir.exists(), "no parity rows read from {}", dir.display());
        let shown: Vec<_> = bad.iter().take(30).cloned().collect();
        assert!(bad.is_empty(), "{} of {n} rows differ:\n{}", bad.len(), shown.join("\n"));
    }
}
