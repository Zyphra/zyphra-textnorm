//! Opt-in pre-pass (feature `prepass`, [`crate::Normalizer::with_prepass`]): narrow rewrites of chat and markdown text
//! before the grammars see it, for what a speech model is given in practice and the NeMo grammars were not written for:
//! markdown (emphasis, bullets, headings, tables, links, code fences), HTML/SSML tags and entities, emoji, typographic
//! look-alikes, and English readings the grammars get wrong (units, ranges, versions, powers, decades, abbreviations, …).
//!
//! Off by default: with it off every output is the NeMo-parity output the goldens pin. Each rule rewrites the written
//! text only (the grammars are untouched) and is deliberately narrow, with guards for what it must not touch. The
//! rules were prototyped in Python (a workbench next to this repository) and reviewed case by case against the golden
//! files and NeMo's own tests; this module is a line-for-line port of that prototype, and `tests/prepass.rs` pins
//! every golden row whose output the pre-pass changes.
//!
//! The rule order is [`ORDER`]. A rule runs in all languages, in all but ja/zh/ko, or in English only.

mod rules;
mod tables;

use std::collections::HashMap;
use std::sync::{Arc, LazyLock, Mutex};

use fancy_regex::{Captures, RegexBuilder};

/// One rewrite: the rule, the text it matched and what it wrote instead.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Hit {
    pub rule: &'static str,
    pub before: String,
    pub after: String,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Langs {
    All,
    NonCjk,
    En,
}

/// The rules in the order they run: markup first (fences, tables, headings, tags, links, emphasis), then characters,
/// then the English context rules.
pub const ORDER: [&str; 59] = [
    "md.fence",
    "md.rule",
    "md.table",
    "md.heading",
    "md.quote",
    "md.bullet",
    "html.tag",
    "html.entity",
    "md.link",
    "en.url",
    "md.emphasis",
    "en.approx",
    "md.strike",
    "en.power",
    "en.math",
    "md.asterisk",
    "md.blank",
    "md.code-scope",
    "md.shortcode",
    "ch.emoji",
    "md.pipe",
    "en.symbols",
    "md.hashtag",
    "ch.mojibake",
    "ch.backtick",
    "ch.quote",
    "ch.dash",
    "ch.endash-pause",
    "ch.ellipsis",
    "ch.invisible",
    "ch.fullwidth",
    "ch.ligature",
    "ch.lookalike",
    "ch.fracslash",
    "ch.bang",
    "ch.subscript",
    "ch.midbullet",
    "en.footnote",
    "en.arrow",
    "en.lakh",
    "en.space-after-period",
    "en.list",
    "en.compound-number",
    "en.coordinates",
    "en.version",
    "en.times-sign",
    "en.feet",
    "en.range",
    "en.ratio",
    "en.units",
    "en.money-adj",
    "en.money-after",
    "en.abbrev",
    "en.slash-words",
    "en.roman",
    "en.decades",
    "en.dates-slash",
    "en.reading-style",
    "en.acronym-plural",
];

type RuleFn = fn(String, &mut Ctx) -> String;

fn rule(id: &str) -> (Langs, RuleFn) {
    use Langs::*;
    use rules::*;
    match id {
        "md.fence" => (All, md_fence),
        "md.rule" => (All, md_rule),
        "md.table" => (All, md_table),
        "md.heading" => (All, md_heading),
        "md.quote" => (All, md_quote),
        "md.bullet" => (All, md_bullet),
        "html.tag" => (All, html_tag),
        "html.entity" => (All, html_entity),
        "md.link" => (All, md_link),
        "md.emphasis" => (All, md_emphasis),
        "md.strike" => (All, md_strike),
        "md.asterisk" => (En, md_asterisk),
        "md.blank" => (All, md_blank),
        "md.code-scope" => (All, md_code_scope),
        "md.shortcode" => (All, md_shortcode),
        "ch.emoji" => (All, ch_emoji),
        "md.pipe" => (En, md_pipe),
        "md.hashtag" => (All, md_hashtag),
        "ch.backtick" => (All, ch_backtick),
        "ch.quote" => (En, ch_quote),
        "ch.dash" => (All, ch_dash),
        "ch.endash-pause" => (En, ch_endash_pause),
        "ch.ellipsis" => (En, ch_ellipsis),
        "ch.invisible" => (All, ch_invisible),
        "ch.fullwidth" => (All, ch_fullwidth),
        "ch.ligature" => (All, ch_ligature),
        "ch.lookalike" => (All, ch_lookalike),
        "ch.fracslash" => (All, ch_fracslash),
        "ch.bang" => (NonCjk, ch_bang),
        "ch.subscript" => (En, ch_subscript),
        "ch.mojibake" => (All, ch_mojibake),
        "ch.midbullet" => (All, ch_midbullet),
        "en.footnote" => (En, en_footnote),
        "en.power" => (En, en_power),
        "en.approx" => (En, en_approx),
        "en.math" => (En, en_math),
        "en.times-sign" => (En, en_times_sign),
        "en.arrow" => (En, en_arrow),
        "en.lakh" => (En, en_lakh),
        "en.list" => (En, en_list),
        "en.version" => (En, en_version),
        "en.range" => (En, en_range),
        "en.ratio" => (En, en_ratio),
        "en.feet" => (En, en_feet),
        "en.units" => (En, en_units),
        "en.compound-number" => (En, en_compound_number),
        "en.money-adj" => (En, en_money_adj),
        "en.money-after" => (En, en_money_after),
        "en.abbrev" => (En, en_abbrev),
        "en.slash-words" => (En, en_slash_words),
        "en.reading-style" => (En, en_reading_style),
        "en.coordinates" => (En, en_coordinates),
        "en.symbols" => (En, en_symbols),
        "en.roman" => (En, en_roman),
        "en.decades" => (En, en_decades),
        "en.space-after-period" => (En, en_space_after_period),
        "en.url" => (En, en_url),
        "en.acronym-plural" => (En, en_acronym_plural),
        "en.dates-slash" => (En, en_dates_slash),
        _ => unreachable!("unknown pre-pass rule {id}"),
    }
}

/// Rewrites `text` for `language` and says what changed. The markup tags (as on the [`crate::Normalizer`]) and verbatim
/// spans (U+E000 … U+E001) are set aside first and never touched.
pub fn apply<S: AsRef<str>>(text: &str, language: &str, markup_tags: &[S]) -> (String, Vec<Hit>) {
    let (t, hits, _) = apply_spans(text, language, markup_tags);
    (t, hits)
}

/// [`apply`], and for each verbatim span (U+E000 … U+E001) of the result in order, whether the pre-pass added it
/// (a plural acronym kept as typed) rather than the caller.
pub(crate) fn apply_spans<S: AsRef<str>>(
    text: &str,
    language: &str,
    markup_tags: &[S],
) -> (String, Vec<Hit>, Vec<bool>) {
    let cjk = matches!(language, "ja" | "zh" | "ko");
    let mut ctx = Ctx { lang: language.to_string(), hits: Vec::new(), rid: "" };
    let (mut t, saved) = protect(text, markup_tags);
    for id in ORDER {
        let (langs, f) = rule(id);
        let runs = match langs {
            Langs::All => true,
            Langs::NonCjk => !cjk,
            Langs::En => language == "en",
        };
        if runs {
            ctx.rid = id;
            t = f(t, &mut ctx);
        }
    }
    if !ctx.hits.is_empty() {
        t = sub_plain(&rx(r"[ \t]+([,.;:!?])(?=\s|$)"), &t, |c| Some(tpl(c, r"\1")));
        t = sub_plain(&rx(r"[ \t]{2,}"), &t, |_| Some(" ".into()));
        t = sub_plain(&rx(r"\n{3,}"), &t, |_| Some("\n\n".into()));
        t = py_strip(&t).to_string();
    }
    let added = t
        .chars()
        .filter_map(|c| match c as u32 {
            0xE000 => Some(true),
            cp @ 0xF0000..=0xFFFFD => {
                saved.get((cp - 0xF0000) as usize).filter(|s| s.starts_with('\u{e000}')).map(|_| false)
            }
            _ => None,
        })
        .collect();
    (restore(&t, &saved), ctx.hits, added)
}

/// `out` (a normalizer output for the pre-passed text) without the verbatim marks the pre-pass added; the caller's
/// own verbatim spans keep theirs.
pub(crate) fn strip_added_marks(out: &str, added: &[bool]) -> String {
    if !added.contains(&true) {
        return out.to_string();
    }
    if out.matches('\u{e000}').count() != added.len() {
        // the spans did not come back one for one (a malformed span in the input): drop marks only when all were added
        return if added.iter().all(|&a| a) { out.replace(['\u{e000}', '\u{e001}'], "") } else { out.to_string() };
    }
    let mut res = String::with_capacity(out.len());
    let (mut i, mut strip_close) = (0usize, false);
    for ch in out.chars() {
        match ch {
            '\u{e000}' => {
                strip_close = added[i];
                i += 1;
                if !strip_close {
                    res.push(ch);
                }
            }
            '\u{e001}' if strip_close => strip_close = false,
            _ => res.push(ch),
        }
    }
    res
}

/// The verbatim spans and the configured markup tags, swapped for private-use code points (U+F0000 + i).
fn protect<S: AsRef<str>>(text: &str, tags: &[S]) -> (String, Vec<String>) {
    let mut saved = Vec::new();
    let mut keep = |c: &Captures<'_, str>| {
        saved.push(c[0].to_string());
        Some(char::from_u32(0xF0000 + saved.len() as u32 - 1).expect("private-use code point").to_string())
    };
    let t = sub_plain(&rx(r"(?s)\x{E000}.*?\x{E001}"), text, &mut keep);
    let names: Vec<String> = tags.iter().map(|x| x.as_ref()).filter(|x| !x.is_empty()).map(re_escape).collect();
    if names.is_empty() {
        return (t, saved);
    }
    let pat = format!(r"<\s*/?\s*(?:{})\s*/?\s*>", names.join("|"));
    let t = sub_plain(&rx(&pat), &t, &mut keep);
    (t, saved)
}

fn restore(text: &str, saved: &[String]) -> String {
    text.chars()
        .map(|c| match c as u32 {
            cp @ 0xF0000..=0xFFFFD => saved.get((cp - 0xF0000) as usize).cloned().unwrap_or_else(|| c.to_string()),
            _ => c.to_string(),
        })
        .collect()
}

// ------------------------------------------------------------------------------------------------- re.sub

/// The rule being run and what the rules have changed so far.
pub(crate) struct Ctx {
    lang: String,
    hits: Vec<Hit>,
    rid: &'static str,
}

impl Ctx {
    /// `re.sub` that records each changed match under the current rule; `f` returning `None` keeps the match.
    fn sub(&mut self, re: &Regex, text: &str, mut f: impl FnMut(&Captures<'_, str>) -> Option<String>) -> String {
        let rid = self.rid;
        let hits = &mut self.hits;
        sub_plain(re, text, |c| {
            let new = f(c)?;
            if new != c[0] {
                hits.push(Hit { rule: rid, before: c[0].to_string(), after: new.clone() });
            }
            Some(new)
        })
    }

    /// [`Ctx::sub`] with a replacement template (`\1` … `\9`).
    fn sub_tpl(&mut self, re: &Regex, text: &str, template: &str) -> String {
        self.sub(re, text, |c| Some(tpl(c, template)))
    }

    fn lang(&self) -> &str {
        &self.lang
    }
}

/// Python's `re.sub` with a function: leftmost non-overlapping matches, an empty match allowed right after a
/// non-empty one but never twice at the same position.
fn sub_plain(re: &Regex, text: &str, mut f: impl FnMut(&Captures<'_, str>) -> Option<String>) -> String {
    if !re.may_match(text) {
        return text.to_string();
    }
    let mut out = String::with_capacity(text.len());
    let (mut last, mut pos) = (0usize, 0usize);
    let mut empty_at: Option<usize> = None;
    while pos <= text.len() {
        let Ok(Some(c)) = re.captures_from_pos(text, pos) else { break };
        let m = c.get(0).expect("group 0");
        if m.start() == m.end() && empty_at == Some(m.start()) {
            match text[m.start()..].chars().next() {
                Some(ch) => {
                    pos = m.start() + ch.len_utf8();
                    continue;
                }
                None => break,
            }
        }
        out.push_str(&text[last..m.start()]);
        match f(&c) {
            Some(new) => out.push_str(&new),
            None => out.push_str(m.as_str()),
        }
        last = m.end();
        pos = m.end();
        empty_at = (m.start() == m.end()).then_some(m.end());
    }
    out.push_str(&text[last..]);
    out
}

/// Python's replacement template: `\N` is group N (empty when it did not take part).
fn tpl(c: &Captures<'_, str>, template: &str) -> String {
    let mut out = String::new();
    let mut it = template.chars().peekable();
    while let Some(ch) = it.next() {
        if ch == '\\'
            && let Some(d) = it.peek().and_then(|d| d.to_digit(10))
        {
            it.next();
            out.push_str(g(c, d as usize));
            continue;
        }
        out.push(ch);
    }
    out
}

/// Group `i`, or `""` when it did not take part (Python's `m.group(i) or ""`).
fn g<'t>(c: &Captures<'t, str>, i: usize) -> &'t str {
    c.get(i).map_or("", |m| m.as_str())
}

// ------------------------------------------------------------------------------------------------- Python regexes

fn load_ranges(src: &str) -> Vec<(u32, u32)> {
    src.lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .map(|l| match l.split_once('\t') {
            Some((a, b)) => (u32::from_str_radix(a, 16).unwrap(), u32::from_str_radix(b, 16).unwrap()),
            None => {
                let a = u32::from_str_radix(l.trim(), 16).unwrap();
                (a, a)
            }
        })
        .collect()
}

fn class_body(ranges: &[(u32, u32)]) -> String {
    ranges
        .iter()
        .map(|&(a, b)| if a == b { format!(r"\x{{{a:X}}}") } else { format!(r"\x{{{a:X}}}-\x{{{b:X}}}") })
        .collect()
}

/// `ranges` minus `minus` (both sorted, inclusive).
fn subtract(ranges: &[(u32, u32)], minus: &[(u32, u32)]) -> Vec<(u32, u32)> {
    let mut out = Vec::new();
    for &(mut a, b) in ranges {
        for &(x, y) in minus {
            if y < a || x > b {
                continue;
            }
            if x > a {
                out.push((a, x - 1));
            }
            a = y.saturating_add(1);
            if a > b {
                break;
            }
        }
        if a <= b {
            out.push((a, b));
        }
    }
    out
}

/// CPython 3.12's `\w`, `\s`, `\d` and `[^\W\d_]` (the same tables as the wrapper), as class bodies.
struct Classes {
    word: String,
    space: String,
    digit: String,
    letter: String,
}

static CLASSES: LazyLock<Classes> = LazyLock::new(|| {
    let word = load_ranges(include_str!("../../data/unicode/word_ranges.txt"));
    let digit = load_ranges(include_str!("../../data/unicode/nd_ranges.txt"));
    let space = load_ranges(include_str!("../../data/unicode/isspace.txt"));
    let letter = subtract(&subtract(&word, &digit), &[(0x5F, 0x5F)]);
    Classes {
        word: class_body(&word),
        space: class_body(&space),
        digit: class_body(&digit),
        letter: class_body(&letter),
    }
});

/// A Python `re` pattern as a fancy-regex pattern with Python's semantics: `\w \W \s \S \d \D \b` with CPython's
/// Unicode tables, `$` outside multiline mode matching only at the end or before a final newline, and the class syntax
/// fancy-regex reads differently (`[` `&&` `--` `~~` inside a class) escaped.
pub(crate) fn py(pat: &str) -> String {
    let k = &*CLASSES;
    let multiline = pat.starts_with("(?") && pat[2..].split(')').next().is_some_and(|f| f.contains('m'));
    let word = &k.word;
    let boundary = format!(r"(?:(?<=[{word}])(?![{word}])|(?<![{word}])(?=[{word}]))");
    let c: Vec<char> = pat.chars().collect();
    let mut out = String::with_capacity(pat.len() * 2);
    let mut i = 0;
    let mut in_class = false;
    let mut class_start = 0;
    while i < c.len() {
        let ch = c[i];
        if !in_class {
            if c[i..].starts_with(&['[', '^', '\\', 'W', '\\', 'd', '_', ']']) {
                out.push_str(&format!("[{}]", k.letter));
                i += 8;
                continue;
            }
            match ch {
                '\\' if i + 1 < c.len() => {
                    let e = c[i + 1];
                    match e {
                        'w' => out.push_str(&format!("[{word}]")),
                        'W' => out.push_str(&format!("[^{word}]")),
                        's' => out.push_str(&format!("[{}]", k.space)),
                        'S' => out.push_str(&format!("[^{}]", k.space)),
                        'd' => out.push_str(&format!("[{}]", k.digit)),
                        'D' => out.push_str(&format!("[^{}]", k.digit)),
                        'b' => out.push_str(&boundary),
                        'B' | 'Z' | 'A' | '<' | '>' => panic!("unsupported escape \\{e} in {pat}"),
                        _ => {
                            out.push('\\');
                            out.push(e);
                        }
                    }
                    i += 2;
                }
                '[' => {
                    in_class = true;
                    out.push('[');
                    i += 1;
                    if c.get(i) == Some(&'^') {
                        out.push('^');
                        i += 1;
                    }
                    class_start = i;
                }
                '$' if !multiline => {
                    out.push_str(r"(?=\n?\z)");
                    i += 1;
                }
                _ => {
                    out.push(ch);
                    i += 1;
                }
            }
            continue;
        }
        match ch {
            '\\' if i + 1 < c.len() => {
                let e = c[i + 1];
                match e {
                    'w' => out.push_str(word),
                    's' => out.push_str(&k.space),
                    'd' => out.push_str(&k.digit),
                    'W' | 'S' | 'D' | 'b' => panic!("unsupported class escape \\{e} in {pat}"),
                    _ => {
                        out.push('\\');
                        out.push(e);
                    }
                }
                i += 2;
            }
            ']' if i > class_start => {
                in_class = false;
                out.push(']');
                i += 1;
            }
            '[' | '&' | '~' => {
                out.push('\\');
                out.push(ch);
                i += 1;
            }
            '-' if c.get(i + 1) == Some(&'-') => {
                out.push_str(r"\-");
                i += 1;
            }
            _ => {
                out.push(ch);
                i += 1;
            }
        }
    }
    out
}

/// A compiled pattern: the fancy-regex that does the work, and a plain `regex` prefilter (the pattern with its
/// lookarounds dropped and its backreferences widened to `.*?`) that matches wherever the pattern could. Most rules
/// do not apply to most texts; the prefilter's linear scan says so without the backtracking engine.
pub(crate) struct Regex {
    fancy: fancy_regex::Regex,
    pre: Option<regex::Regex>,
}

impl Regex {
    /// False only when the pattern cannot match anywhere in `s`.
    fn may_match(&self, s: &str) -> bool {
        self.pre.as_ref().is_none_or(|p| p.is_match(s))
    }
}

impl std::ops::Deref for Regex {
    type Target = fancy_regex::Regex;

    fn deref(&self) -> &fancy_regex::Regex {
        &self.fancy
    }
}

/// The end of the character class that starts at `c[i] == '['` (one past its `]`).
fn class_end(c: &[char], mut i: usize) -> usize {
    i += 1;
    if c.get(i) == Some(&'^') {
        i += 1;
    }
    if c.get(i) == Some(&']') {
        i += 1;
    }
    while i < c.len() && c[i] != ']' {
        i += if c[i] == '\\' { 2 } else { 1 };
    }
    i + 1
}

/// The end of the group that starts at `c[i] == '('` (one past its `)`).
fn group_end(c: &[char], mut i: usize) -> usize {
    let mut depth = 0usize;
    while i < c.len() {
        match c[i] {
            '\\' => i += 2,
            '[' => i = class_end(c, i),
            '(' => {
                depth += 1;
                i += 1;
            }
            ')' => {
                depth -= 1;
                i += 1;
                if depth == 0 {
                    return i;
                }
            }
            _ => i += 1,
        }
    }
    i
}

/// A translated pattern ([`py`]) with every lookaround dropped and every backreference widened to `(?s:.*?)`: it
/// matches wherever the pattern does (and more), and the `regex` crate runs it.
fn relax(p: &str) -> String {
    let c: Vec<char> = p.chars().collect();
    let mut out = String::with_capacity(p.len());
    let mut i = 0;
    while i < c.len() {
        match c[i] {
            '\\' if c.get(i + 1).is_some_and(|d| d.is_ascii_digit()) => {
                out.push_str("(?s:.*?)");
                i += 2;
                while c.get(i).is_some_and(|d| d.is_ascii_digit()) {
                    i += 1;
                }
            }
            '\\' => {
                out.extend(&c[i..(i + 2).min(c.len())]);
                i += 2;
            }
            '[' => {
                let end = class_end(&c, i).min(c.len());
                out.extend(&c[i..end]);
                i = end;
            }
            '(' if c[i..].starts_with(&['(', '?', '='])
                || c[i..].starts_with(&['(', '?', '!'])
                || c[i..].starts_with(&['(', '?', '<', '='])
                || c[i..].starts_with(&['(', '?', '<', '!']) =>
            {
                i = group_end(&c, i);
            }
            ch => {
                out.push(ch);
                i += 1;
            }
        }
    }
    out
}

static CACHE: LazyLock<Mutex<HashMap<String, Arc<Regex>>>> = LazyLock::new(|| Mutex::new(HashMap::new()));

/// The compiled form of a Python pattern (see [`py`]), cached.
pub(crate) fn rx(pat: &str) -> Arc<Regex> {
    if let Some(r) = CACHE.lock().unwrap_or_else(|e| e.into_inner()).get(pat) {
        return r.clone();
    }
    let translated = py(pat);
    let fancy = RegexBuilder::new(&translated)
        .backtrack_limit(100_000_000)
        .build()
        .unwrap_or_else(|e| panic!("pre-pass pattern {pat:?}: {e}"));
    let relaxed = relax(&translated);
    let pre = (relaxed != translated)
        .then(|| regex::RegexBuilder::new(&relaxed).size_limit(1 << 26).dfa_size_limit(1 << 24).build().ok())
        .flatten();
    let r = Arc::new(Regex { fancy, pre });
    CACHE.lock().unwrap_or_else(|e| e.into_inner()).insert(pat.to_string(), r.clone());
    r
}

/// `re.search(pat, s)`.
fn search(pat: &str, s: &str) -> bool {
    let r = rx(pat);
    r.may_match(s) && r.is_match(s).unwrap_or(false)
}

/// `re.match(pat, s)` (anchored at the start).
fn matches_at_start(pat: &str, s: &str) -> bool {
    search(&format!("^(?:{pat})"), s)
}

/// `re.fullmatch(pat, s)`.
fn full(pat: &str, s: &str) -> bool {
    search(&format!(r"^(?:{pat})\z"), s)
}

/// `re.escape`.
fn re_escape(s: &str) -> String {
    let mut out = String::new();
    for ch in s.chars() {
        if ch.is_ascii_alphanumeric() || ch == '_' || !ch.is_ascii() {
            out.push(ch);
        } else {
            out.push('\\');
            out.push(ch);
        }
    }
    out
}

// ------------------------------------------------------------------------------------------------- Python str

use crate::text::{is_py_digit, is_py_space, nd_range_start};

fn py_strip(s: &str) -> &str {
    s.trim_matches(is_py_space)
}

fn py_rstrip(s: &str) -> &str {
    s.trim_end_matches(is_py_space)
}

/// `str.isalnum()` for one character: Python's `\w` without `_`.
fn is_alnum(c: char) -> bool {
    c != '_' && is_word(c)
}

fn is_word(c: char) -> bool {
    static WORD: LazyLock<Vec<(u32, u32)>> =
        LazyLock::new(|| load_ranges(include_str!("../../data/unicode/word_ranges.txt")));
    let cp = c as u32;
    let i = WORD.partition_point(|&(_, hi)| hi < cp);
    i < WORD.len() && WORD[i].0 <= cp
}

/// `int(s)` for a string of `\d` digits, as decimal ASCII without leading zeros.
fn py_int_str(s: &str) -> String {
    let digits: String = s
        .chars()
        .filter_map(|c| {
            if c.is_ascii_digit() {
                Some(c)
            } else if is_py_digit(c) {
                char::from_digit((c as u32 - nd_range_start(c)?) % 10, 10)
            } else {
                None
            }
        })
        .collect();
    let t = digits.trim_start_matches('0');
    if t.is_empty() { "0".into() } else { t.to_string() }
}

/// `int(s)` when it fits (all the pre-pass compares are small numbers; a longer one saturates).
fn py_int(s: &str) -> u128 {
    py_int_str(s).parse().unwrap_or(u128::MAX)
}

/// The character before byte offset `i` (`t[i - 1]`), or `default` at the start.
fn before(t: &str, i: usize, default: char) -> char {
    t[..i].chars().next_back().unwrap_or(default)
}

/// The character at byte offset `i` (`t[i]`), or `default` at the end.
fn after(t: &str, i: usize, default: char) -> char {
    t[i..].chars().next().unwrap_or(default)
}

/// `t[max(0, i - n): i]` in characters.
fn chars_before(t: &str, i: usize, n: usize) -> &str {
    let head = &t[..i];
    let start = head.char_indices().rev().nth(n.saturating_sub(1)).map_or(0, |(p, _)| p);
    if n == 0 { "" } else { &head[start..] }
}

/// `t[i: i + n]` in characters.
fn chars_after(t: &str, i: usize, n: usize) -> &str {
    let tail = &t[i..];
    let end = tail.char_indices().nth(n).map_or(tail.len(), |(p, _)| p);
    &tail[..end]
}

/// `456159 -> 456,159` for a 5+ digit number (with an optional sign and decimals); anything else as given.
fn commas(n: &str) -> String {
    let c = rx(r"(-?)(\d{5,})(\.\d+)?");
    match c.captures(n) {
        Ok(Some(m)) if m.get(0).is_some_and(|x| x.start() == 0 && x.end() == n.len()) => {
            let digits = py_int_str(&m[2]);
            let mut grouped = String::new();
            for (i, ch) in digits.chars().enumerate() {
                if i > 0 && (digits.len() - i).is_multiple_of(3) {
                    grouped.push(',');
                }
                grouped.push(ch);
            }
            format!("{}{}{}", g(&m, 1), grouped, g(&m, 3))
        }
        _ => n.to_string(),
    }
}

/// Every whole-string `\d+` value with an ordinal suffix: 1st, 2nd, 13th.
fn ordinal_digits(n: &str) -> String {
    let i = py_int(n);
    if (10..=20).contains(&(i % 100)) {
        return format!("{n}th");
    }
    let suffix = match i % 10 {
        1 => "st",
        2 => "nd",
        3 => "rd",
        _ => "th",
    };
    format!("{n}{suffix}")
}

/// The English grammar's reading of a short string (rules that spell a number need its words).
fn english(s: &str) -> String {
    crate::normalize(s, "en")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn python_classes() {
        // \w is CPython's (² and ½ are word characters, a combining mark is not), $ outside multiline mode matches
        // before a final newline, and class syntax fancy-regex reads differently is escaped
        assert!(search(r"^\w$", "²") && search(r"^\w$", "½") && !search(r"^\w$", "\u{93e}"));
        assert!(search(r"a$", "a\n") && !search(r"a$", "a\nb"));
        assert!(search(r"[\w~&]", "~") && search(r"[(\[]", "["));
        assert!(search(r"\bcat\b", "a cat.") && !search(r"\bcat\b", "concatenate"));
        assert_eq!(py(r"[^\W\d_]"), format!("[{}]", CLASSES.letter));
    }

    #[test]
    fn sub_like_python() {
        // an empty match is taken once per position, also right after a non-empty one
        assert_eq!(sub_plain(&rx(r"x*"), "abxd", |_| Some("-".into())), "-a-b--d-");
        assert_eq!(sub_plain(&rx(r"(?<=[^\s|])(?=\|+(?:\s|$))"), "a|| b|", |_| Some(" ".into())), "a || b |");
        assert_eq!(commas("456159"), "456,159");
        assert_eq!(commas("-0012345.5"), "-12,345.5");
        assert_eq!(commas("1234"), "1234");
        assert_eq!(ordinal_digits("11"), "11th");
        assert_eq!(ordinal_digits("22"), "22nd");
    }

    #[test]
    fn prefilter_is_a_superset() {
        assert_eq!(relax(r"(?<![a-z.])(\d+)(?=x)y\1(?!z)[(?=]"), r"(\d+)y(?s:.*?)[(?=]");
        let r = rx(r"(?<![\w.])(\d+(?:\.\d+)?)\s?π");
        assert!(r.pre.is_some() && r.may_match("a3 π") && !r.may_match("no pi here"));
        assert_eq!(sub_plain(&r, "a3 π and 4π", |c| Some(tpl(c, r"\1 pi"))), "a3 π and 4 pi");
    }

    #[test]
    fn html_references() {
        use tables::html_unescape;
        assert_eq!(html_unescape("&amp;"), "&");
        assert_eq!(html_unescape("&ampfoo;"), "&foo;");
        assert_eq!(html_unescape("&#128;"), "€");
        assert_eq!(html_unescape("&#x1F600;"), "😀");
        assert_eq!(html_unescape("&#55296;"), "\u{FFFD}");
        assert_eq!(html_unescape("&nosuch;"), "&nosuch;");
    }

    #[test]
    fn emoji() {
        use tables::{emoji_list, emoji_name};
        assert_eq!(emoji_name("👍🏽").as_deref(), Some("thumbs up emoji"));
        assert_eq!(emoji_name("🇯🇵").as_deref(), Some("Japan flag emoji"));
        assert_eq!(emoji_name("©"), None);
        let spans = emoji_list("a 👨‍💻 b 1️⃣");
        assert_eq!(spans.iter().map(|s| s.2.as_str()).collect::<Vec<_>>(), ["👨‍💻", "1️⃣"]);
    }

    #[test]
    fn verbatim_marks() {
        let (t, _, added) = apply_spans("\u{e000}kæt\u{e001} for GPUs", "en", &[] as &[&str]);
        assert_eq!(t, "\u{e000}kæt\u{e001} for \u{e000}GPUs\u{e001}");
        assert_eq!(added, [false, true]);
        assert_eq!(strip_added_marks(&t, &added), "\u{e000}kæt\u{e001} for GPUs");
    }

    #[test]
    fn every_rule_runs() {
        // every pattern compiles: English runs all rules but the non-English branches
        for lang in ["en", "de", "ja"] {
            let (_, hits) = apply(
                "# Hi\n- **a** <b>x</b> &amp; [l](u) 25.5* 😀 #tag `c` – … ７ ﬁ µ 1⁄2 ‼ CO₂ · x² ~5 2*3",
                lang,
                &["laugh"],
            );
            assert!(!hits.is_empty(), "{lang}");
        }
    }
}
