//! The layer around the grammars, ported literally from the Python wrapper the goldens were dumped with
//! (`oracle/reference_textnorm.py`): line-break collapsing, markup and verbatim spans kept out of the grammar, the
//! per-language pre/post passes, the sentence retry after a grammar failure and the LRU memo.
//!
//! The passes work around reproduced NeMo r1.2.0 grammar behaviour (the grammars are ported as they are, quirks
//! included): a digit directly followed by sentence punctuation (pt has no tagger path for it, de reads `1990.` as an
//! ordinal, es/fr/it/ko/en mis-tag or lose the mark), ja's ASCII space between CJK characters (no path) and two en
//! spoken-form conventions (`24/7`, `$20k`). Dropping any pass changes outputs (measured against the oracle).

use std::borrow::Cow;
use std::collections::HashMap;
use std::panic::AssertUnwindSafe;
use std::sync::{Arc, LazyLock, Mutex};

use crate::lang;
use crate::pipeline::{self, GrammarError};
use crate::text::{is_py_digit, is_py_space, py_leading_ws, py_strip, py_trailing_ws};

static WORD_RANGES: LazyLock<Vec<(u32, u32)>> = LazyLock::new(|| {
    include_str!("../data/unicode/word_ranges.txt")
        .lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .map(|l| {
            let (a, b) = l.split_once('\t').expect("range row");
            (u32::from_str_radix(a, 16).unwrap(), u32::from_str_radix(b, 16).unwrap())
        })
        .collect()
});

/// Python `re` `\w` for `str` patterns.
fn is_py_word(c: char) -> bool {
    if c.is_ascii() {
        return c.is_ascii_alphanumeric() || c == '_';
    }
    let cp = c as u32;
    let r = &*WORD_RANGES;
    let i = r.partition_point(|&(_, hi)| hi < cp);
    i < r.len() && r[i].0 <= cp
}

/// `_LINE_BREAK_RE = \s*[^\S ]\s*` → `" "`: every maximal whitespace run holding a non-`' '` whitespace char.
pub fn collapse_line_breaks(text: &str) -> Cow<'_, str> {
    if !text.chars().any(|c| c != ' ' && is_py_space(c)) {
        return Cow::Borrowed(text);
    }
    let mut out = String::with_capacity(text.len());
    let mut run_start: Option<usize> = None;
    let mut run_has_break = false;
    let flush = |out: &mut String, run: &str, has_break: bool| {
        out.push_str(if has_break { " " } else { run });
    };
    for (i, c) in text.char_indices() {
        if is_py_space(c) {
            run_start.get_or_insert(i);
            run_has_break |= c != ' ';
        } else {
            if let Some(s) = run_start.take() {
                flush(&mut out, &text[s..i], std::mem::take(&mut run_has_break));
            }
            out.push(c);
        }
    }
    if let Some(s) = run_start {
        flush(&mut out, &text[s..], run_has_break);
    }
    Cow::Owned(out)
}

// ------------------------------------------------------------------------------------------------ pre/post passes

fn followed_by_space_or_end(c: &[char], i: usize) -> bool {
    i >= c.len() || is_py_space(c[i])
}

/// Whether a char matching `a` is directly followed by one matching `b` (a pass's cheap precondition).
fn has_pair(text: &str, a: impl Fn(char) -> bool, b: impl Fn(char) -> bool) -> bool {
    let mut prev = false;
    text.chars().any(|c| {
        let hit = prev && b(c);
        prev = a(c);
        hit
    })
}

/// `pass` applied to the previous passes' output, still borrowing the input when none of them changed it.
fn then<'t>(text: Cow<'t, str>, pass: fn(&str) -> Cow<'_, str>) -> Cow<'t, str> {
    match text {
        Cow::Borrowed(s) => pass(s),
        Cow::Owned(s) => {
            let changed = match pass(&s) {
                Cow::Owned(n) => Some(n),
                Cow::Borrowed(_) => None,
            };
            Cow::Owned(changed.unwrap_or(s))
        }
    }
}

/// `re.sub(r"(\d)([<marks>])(?=\s|$)", r"\1 \2", text)`. Marks are ASCII, so every match is found from a mark's byte
/// position; unmatched stretches are copied as slices.
fn space_digit_punct<'t>(text: &'t str, marks: &str) -> Cow<'t, str> {
    let marks = marks.as_bytes();
    let mut out: Option<String> = None;
    let mut copied = 0;
    for (m, &b) in text.as_bytes().iter().enumerate() {
        if !marks.contains(&b) {
            continue;
        }
        let Some(d) = text[..m].chars().next_back() else { continue };
        if !is_py_digit(d) || !text[m + 1..].chars().next().is_none_or(is_py_space) {
            continue;
        }
        // a digit directly before a mark is never itself a mark, so matches never overlap
        let o = out.get_or_insert_with(|| String::with_capacity(text.len() + 8));
        o.push_str(&text[copied..m]);
        o.push(' ');
        copied = m;
    }
    match out {
        None => Cow::Borrowed(text),
        Some(mut o) => {
            o.push_str(&text[copied..]);
            Cow::Owned(o)
        }
    }
}

/// `_DE_FINAL_PERIOD_RE = (\d)(\.)(?=["'»“”)\]]*\s*$)` → `\1 \2`.
fn de_final_period(text: &str) -> Cow<'_, str> {
    if !has_pair(text, is_py_digit, |c| c == '.') {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len() + 4);
    let mut i = 0;
    while i < c.len() {
        if i + 1 < c.len() && is_py_digit(c[i]) && c[i + 1] == '.' && {
            let mut j = i + 2;
            while j < c.len() && matches!(c[j], '"' | '\'' | '»' | '“' | '”' | ')' | ']') {
                j += 1;
            }
            while j < c.len() && is_py_space(c[j]) {
                j += 1;
            }
            j == c.len()
        } {
            out.push(c[i]);
            out.push_str(" .");
            i += 2;
        } else {
            out.push(c[i]);
            i += 1;
        }
    }
    Cow::Owned(out)
}

/// `_DE_LONG_PERIOD_RE = (\d{3,})(\.)(?=\s|$)` → `\1 \2`.
fn de_long_period(text: &str) -> Cow<'_, str> {
    if !has_pair(text, is_py_digit, |c| c == '.') {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len() + 4);
    let mut i = 0;
    while i < c.len() {
        if is_py_digit(c[i]) {
            let mut j = i;
            while j < c.len() && is_py_digit(c[j]) {
                j += 1;
            }
            out.extend(&c[i..j]);
            if j - i >= 3 && j < c.len() && c[j] == '.' && followed_by_space_or_end(&c, j + 1) {
                out.push_str(" .");
                i = j + 1;
            } else {
                i = j;
            }
        } else {
            out.push(c[i]);
            i += 1;
        }
    }
    Cow::Owned(out)
}

/// `_CJK` of `textnorm.py`.
fn is_cjk(c: char) -> bool {
    matches!(c,
        '\u{3000}'..='\u{303F}' | '\u{3040}'..='\u{30FF}' | '\u{31F0}'..='\u{31FF}' | '\u{3400}'..='\u{4DBF}'
        | '\u{4E00}'..='\u{9FFF}' | '\u{F900}'..='\u{FAFF}' | '\u{FF00}'..='\u{FFEF}')
}

/// `_CJK_SPACE_RE = (?<=[_CJK])\s+(?=[_CJK])` → `""`, with the regex's backtracking (U+3000 is both).
fn cjk_space(text: &str) -> Cow<'_, str> {
    if !has_pair(text, is_cjk, is_py_space) {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len());
    let mut i = 0;
    while i < c.len() {
        if i > 0 && is_cjk(c[i - 1]) && is_py_space(c[i]) {
            let mut j = i;
            while j < c.len() && is_py_space(c[j]) {
                j += 1;
            }
            // greedy \s+ then backtrack until the lookahead holds
            let hit = (i + 1..=j).rev().find(|&e| e < c.len() && is_cjk(c[e]));
            if let Some(e) = hit {
                i = e;
                continue;
            }
        }
        out.push(c[i]);
        i += 1;
    }
    Cow::Owned(out)
}

/// `\b` between `c[p-1]` and `c[p]`.
fn word_boundary(c: &[char], p: usize) -> bool {
    let before = p > 0 && is_py_word(c[p - 1]);
    let after = p < c.len() && is_py_word(c[p]);
    before != after
}

/// Decimal value of a Unicode `Nd` character (blocks are runs of 10 starting at a code point ending in 0).
fn nd_value(c: char) -> u32 {
    if c.is_ascii_digit() {
        return c as u32 - '0' as u32;
    }
    // every Nd range in Unicode 15.0 is made of complete 0..9 runs aligned to their range start
    let cp = c as u32;
    let start = crate::text::nd_range_start(c).expect("is_py_digit");
    (cp - start) % 10
}

/// `_EN_SLASH_RE = \b(\d{1,2})/(\d{1,2})\b` with `_en_slash`. Every match holds one `/`, so the scan goes from slash
/// to slash. A start position fixes which slash it can match (two digits then `/`, or one digit then `/`), and `\b`
/// before a digit rules out a start right after another digit, so for each slash the only possible start is the first
/// of the 1–2 digits before it. Matches never overlap (`re.sub` resumes after a match, also an unchanged one).
fn en_slash(text: &str) -> Cow<'_, str> {
    const PAIRS: [(&str, &str); 3] = [("24", "7"), ("9", "11"), ("7", "11")];
    let not_word_before = |p: usize| !text[..p].chars().next_back().is_some_and(is_py_word);
    // value and length of a digit run
    let num = |s: &str| s.chars().fold((0u64, 0usize), |(v, n), d| (v * 10 + nd_value(d) as u64, n + 1));
    let mut out: Option<String> = None;
    // `text[..copied]` is in `out`; a match may not start before `from` (the previous match's end)
    let (mut copied, mut from) = (0, 0);
    for (s, _) in text.match_indices('/') {
        if s < from {
            continue;
        }
        let mut before = text[from..s].char_indices().rev();
        let Some((p1, _)) = before.next().filter(|&(_, c)| is_py_digit(c)) else { continue };
        let a = match before.next() {
            Some((p2, c)) if is_py_digit(c) => from + p2,
            _ => from + p1,
        };
        if !not_word_before(a) {
            continue;
        }
        // `\d{1,2}\b` after the slash: greedy two, then one
        let after = &text[s + 1..];
        let b_end = [2usize, 1].into_iter().find_map(|n| {
            let mut end = 0;
            for c in after.chars().take(n) {
                if !is_py_digit(c) {
                    return None;
                }
                end += c.len_utf8();
            }
            let complete = after[..end].chars().count() == n;
            (complete && !after[end..].chars().next().is_some_and(is_py_word)).then_some(s + 1 + end)
        });
        let Some(e) = b_end else { continue };
        from = e;
        let (a_s, b_s) = (&text[a..s], &text[s + 1..e]);
        let ((av, an), (bv, bn)) = (num(a_s), num(b_s));
        if PAIRS.iter().any(|&(x, y)| x == a_s && y == b_s) || (an == 2 && bn == 2 && av + bv == 100) {
            let o = out.get_or_insert_with(|| String::with_capacity(text.len()));
            o.push_str(&text[copied..s]);
            o.push(' ');
            copied = s + 1;
        }
    }
    match out {
        None => Cow::Borrowed(text),
        Some(mut o) => {
            o.push_str(&text[copied..]);
            Cow::Owned(o)
        }
    }
}

/// `f"{int(round(float(x) * 1000)):,}"`.
fn money_k_amount(digits: &[char]) -> String {
    let ascii: String =
        digits.iter().map(|&d| if d == '.' { '.' } else { char::from_digit(nd_value(d), 10).unwrap() }).collect();
    let x: f64 = ascii.parse().expect("digits");
    let v = (x * 1000.0).round_ties_even();
    let s = format!("{v:.0}");
    let mut out = String::with_capacity(s.len() + s.len() / 3);
    for (k, ch) in s.chars().enumerate() {
        if k > 0 && (s.len() - k) % 3 == 0 {
            out.push(',');
        }
        out.push(ch);
    }
    out
}

/// `_EN_MONEY_K_RE = ([$£€])(\d+(?:\.\d+)?)[kK]\b` with `_en_money_k`.
fn en_money_k(text: &str) -> Cow<'_, str> {
    // every match starts with a currency sign directly followed by a digit, and holds a `k`/`K`
    if !text.contains(['k', 'K']) || !has_pair(text, |c| matches!(c, '$' | '£' | '€'), is_py_digit) {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len() + 8);
    let mut i = 0;
    while i < c.len() {
        if matches!(c[i], '$' | '£' | '€') {
            let s = i + 1;
            let mut d1 = s;
            while d1 < c.len() && is_py_digit(c[d1]) {
                d1 += 1;
            }
            if d1 > s {
                let k_ok = |p: usize| p < c.len() && matches!(c[p], 'k' | 'K') && word_boundary(&c, p + 1);
                // (?:\.\d+)? greedy first
                let mut hit = None;
                if d1 < c.len() && c[d1] == '.' {
                    let mut d2 = d1 + 1;
                    while d2 < c.len() && is_py_digit(c[d2]) {
                        d2 += 1;
                    }
                    if d2 > d1 + 1 && k_ok(d2) {
                        hit = Some(d2);
                    }
                }
                if hit.is_none() && k_ok(d1) {
                    hit = Some(d1);
                }
                if let Some(e) = hit {
                    out.push(c[i]);
                    out.push_str(&money_k_amount(&c[s..e]));
                    i = e + 1;
                    continue;
                }
            }
        }
        out.push(c[i]);
        i += 1;
    }
    Cow::Owned(out)
}

/// `_PT_TRAIL_PUNCT_RE = (\S*[\d%ºª]\S*?)([.!?,;:)\]]+)(?=\s|$)` → `\1 \2`. A match lies inside one maximal
/// non-space run and must end at its end; the regex's backtracking puts the split at the start of the run's trailing
/// mark suffix (the class chars and the marks are disjoint), so: space off that suffix when the run before it holds a
/// digit, `%`, `º` or `ª`.
fn pt_trail_punct(text: &str) -> Cow<'_, str> {
    let is_mark = |ch: char| ".!?,;:)]".contains(ch);
    if !text.contains(is_mark) {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len() + 8);
    let mut i = 0;
    while i < c.len() {
        if is_py_space(c[i]) {
            out.push(c[i]);
            i += 1;
            continue;
        }
        let mut b = i;
        while b < c.len() && !is_py_space(c[b]) {
            b += 1;
        }
        let mut s = b;
        while s > i && is_mark(c[s - 1]) {
            s -= 1;
        }
        out.extend(&c[i..s]);
        if s < b && c[i..s].iter().any(|&ch| is_py_digit(ch) || matches!(ch, '%' | 'º' | 'ª')) {
            out.push(' ');
        }
        out.extend(&c[s..b]);
        i = b;
    }
    Cow::Owned(out)
}

/// `_PT_LEAD_BRACKET_RE = (^|\s)([(\[])(?=\S*\d)` → `\1\2 `.
fn pt_lead_bracket(text: &str) -> Cow<'_, str> {
    if !text.contains(['(', '[']) {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len() + 4);
    for (j, &ch) in c.iter().enumerate() {
        out.push(ch);
        if matches!(ch, '(' | '[') && (j == 0 || is_py_space(c[j - 1])) {
            let digit_ahead = c[j + 1..].iter().take_while(|&&x| !is_py_space(x)).any(|&x| is_py_digit(x));
            if digit_ahead {
                out.push(' ');
            }
        }
    }
    Cow::Owned(out)
}

/// `pre_normalize(text, lang)`: the rewrite applied right before the grammar (see the module docs).
pub fn pre_normalize<'t>(text: &'t str, nemo: &str) -> Cow<'t, str> {
    match nemo {
        "ja" | "zh" => cjk_space(text),
        "de" => then(then(space_digit_punct(text, "!?,;:"), de_final_period), de_long_period),
        "pt" => then(pt_trail_punct(text), pt_lead_bracket),
        "en" => then(then(space_digit_punct(text, ".!?,;:"), en_slash), en_money_k),
        _ => space_digit_punct(text, ".!?,;:"),
    }
}

/// `" +([<marks>]+?)(?=\s|$)"`-style removal of the spaces before a punctuation run followed by whitespace or end.
fn remove_space_before<'t>(text: &'t str, marks: &str, run: bool) -> Cow<'t, str> {
    if !has_pair(text, |c| c == ' ', |c| marks.contains(c)) {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len());
    let mut i = 0;
    while i < c.len() {
        if c[i] == ' ' {
            let mut j = i;
            while j < c.len() && c[j] == ' ' {
                j += 1;
            }
            let mut k = j;
            if run {
                while k < c.len() && marks.contains(c[k]) {
                    k += 1;
                }
                // `[...]+` then (?=\s|$): greedy, backtracking cannot help (a shorter run ends before a mark)
            } else if k < c.len() && marks.contains(c[k]) {
                k += 1;
            }
            if k > j && followed_by_space_or_end(&c, k) {
                out.extend(&c[j..k]);
                i = k;
                continue;
            }
            out.extend(&c[i..j]);
            i = j;
            continue;
        }
        out.push(c[i]);
        i += 1;
    }
    Cow::Owned(out)
}

/// `([(\[]) +` → `\1`.
fn remove_space_after_open(text: &str) -> Cow<'_, str> {
    if !has_pair(text, |c| matches!(c, '(' | '['), |c| c == ' ') {
        return Cow::Borrowed(text);
    }
    let c: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len());
    let mut i = 0;
    while i < c.len() {
        out.push(c[i]);
        if matches!(c[i], '(' | '[') {
            let mut j = i + 1;
            while j < c.len() && c[j] == ' ' {
                j += 1;
            }
            i = j;
        } else {
            i += 1;
        }
    }
    Cow::Owned(out)
}

/// `post_normalize(result, lang)`.
pub fn post_normalize<'t>(result: &'t str, nemo: &str) -> Cow<'t, str> {
    if nemo == "pt" {
        return then(remove_space_before(result, ".!?,;:)]", true), remove_space_after_open);
    }
    remove_space_before(result, ".!?,;:", false)
}

// ------------------------------------------------------------------------------------------------ markup / groups

/// `</?(?:<tag>|…)\s*/?>` at `c[i..]` for one of `tags`: the match end.
fn markup_at(c: &[char], i: usize, tags: &[Box<str>]) -> Option<usize> {
    if c.get(i) != Some(&'<') {
        return None;
    }
    let mut j = i + 1;
    if c.get(j) == Some(&'/') {
        j += 1;
    }
    let name_len = tags.iter().find_map(|t| crate::text::match_str(c, j, t))?;
    j += name_len;
    while j < c.len() && is_py_space(c[j]) {
        j += 1;
    }
    if c.get(j) == Some(&'/') {
        j += 1;
    }
    (c.get(j) == Some(&'>')).then_some(j + 1)
}

/// `split_nonverbal_markup`: alternating text / marker pieces (`None` without a marker).
fn split_markup(text: &str, tags: &[Box<str>]) -> Option<Vec<String>> {
    if tags.is_empty() || !text.contains('<') {
        return None;
    }
    let c: Vec<char> = text.chars().collect();
    let mut pieces = Vec::new();
    let mut last = 0;
    let mut i = 0;
    while i < c.len() {
        if let Some(e) = markup_at(&c, i, tags) {
            pieces.push(c[last..i].iter().collect());
            pieces.push(c[i..e].iter().collect());
            last = e;
            i = e;
        } else {
            i += 1;
        }
    }
    if pieces.is_empty() {
        return None;
    }
    pieces.push(c[last..].iter().collect());
    Some(pieces)
}

/// `_PHONEME_GROUP_RE.split`: alternating stretch / verbatim-span pieces (U+E000 … U+E001, the delimiters included).
fn split_groups(text: &str) -> Vec<String> {
    let c: Vec<char> = text.chars().collect();
    let mut pieces = Vec::new();
    let mut last = 0;
    let mut i = 0;
    while i < c.len() {
        if c[i] == '\u{e000}' {
            let close = c[i + 1..].iter().position(|&x| x == '\u{e000}' || x == '\u{e001}').map(|p| i + 1 + p);
            if let Some(e) = close.filter(|&e| c[e] == '\u{e001}') {
                pieces.push(c[last..i].iter().collect());
                pieces.push(c[i..=e].iter().collect());
                last = e + 1;
                i = e + 1;
                continue;
            }
        }
        i += 1;
    }
    pieces.push(c[last..].iter().collect());
    pieces
}

/// `_SENTENCE_RE.split(text)`: `(?<=[.!?;:])\s+|(?<=[。！？])`.
fn split_sentences(text: &str) -> Vec<String> {
    let c: Vec<char> = text.chars().collect();
    let mut pieces = Vec::new();
    let mut last = 0;
    let mut p = 0;
    let mut must_advance_at = usize::MAX;
    while p <= c.len() {
        if p > 0 && ".!?;:".contains(c[p - 1]) && p < c.len() && is_py_space(c[p]) {
            let mut j = p;
            while j < c.len() && is_py_space(c[j]) {
                j += 1;
            }
            pieces.push(c[last..p].iter().collect());
            last = j;
            p = j;
            must_advance_at = usize::MAX;
            continue;
        }
        if p > 0 && "。！？".contains(c[p - 1]) && must_advance_at != p {
            pieces.push(c[last..p].iter().collect());
            last = p;
            must_advance_at = p;
            continue;
        }
        p += 1;
    }
    pieces.push(c[last..].iter().collect());
    pieces
}

// ------------------------------------------------------------------------------------------------ normalize

fn moses_lang(nemo: &str) -> bool {
    matches!(nemo, "en" | "zh" | "ja" | "ko")
}

/// `_normalize_once`: one grammar call with the pre/post passes. A panic inside a grammar is a grammar failure, like any
/// exception the NeMo code raised under the Python wrapper (`except Exception`).
fn normalize_once(text: &str, nemo: &str) -> Result<String, GrammarError> {
    let Some(g) = lang::grammar(nemo) else { return Err(GrammarError::NoPath) };
    let input = pre_normalize(text, nemo);
    let result = std::panic::catch_unwind(AssertUnwindSafe(|| pipeline::normalize(g, &input, moses_lang(nemo))))
        .unwrap_or(Err(GrammarError::Panic))?;
    if py_strip(&result).is_empty() {
        return Err(GrammarError::Empty);
    }
    let changed = match post_normalize(&result, nemo) {
        Cow::Owned(s) => Some(s),
        Cow::Borrowed(_) => None,
    };
    Ok(changed.unwrap_or(result))
}

/// `_normalize_text`: whole text, then sentence by sentence after a failure.
fn normalize_text(text: &str, nemo: &str) -> String {
    let text = collapse_line_breaks(text);
    if py_strip(&text).is_empty() {
        return text.into_owned();
    }
    match normalize_once(&text, nemo) {
        Ok(s) => s,
        Err(_) => {
            let pieces: Vec<String> = split_sentences(&text)
                .into_iter()
                .filter(|p| !py_strip(p).is_empty())
                .map(|p| normalize_once(&p, nemo).unwrap_or(p))
                .collect();
            pieces.join(if matches!(nemo, "ja" | "zh") { "" } else { " " })
        }
    }
}

/// `_normalize_groups`: verbatim spans (U+E000 … U+E001) kept as typed.
fn normalize_groups(text: &str, nemo: &str) -> String {
    if !text.contains('\u{e000}') {
        return normalize_text(text, nemo);
    }
    let mut pieces = split_groups(text);
    for i in (0..pieces.len()).step_by(2) {
        let stretch = &pieces[i];
        if !py_strip(stretch).is_empty() {
            let lead = py_leading_ws(stretch);
            let trail = py_trailing_ws(stretch);
            pieces[i] = format!("{lead}{}{trail}", normalize_text(py_strip(stretch), nemo));
        }
    }
    pieces.concat()
}

/// `_normalize_uncached`: `language` a grammar language with a grammar in this build.
fn normalize_uncached(text: &str, nemo: &str, tags: &[Box<str>]) -> String {
    let text = collapse_line_breaks(text);
    let Some(pieces) = split_markup(&text, tags) else { return normalize_groups(&text, nemo) };
    let mut out = String::with_capacity(text.len() * 2);
    for (index, piece) in pieces.iter().enumerate() {
        let core = py_strip(piece);
        if index % 2 == 1 {
            out.push_str(piece);
        } else if core.is_empty() {
            if !piece.is_empty() {
                out.push(' ');
            }
        } else {
            if piece.starts_with(is_py_space) {
                out.push(' ');
            }
            out.push_str(&normalize_groups(core, nemo));
            if piece.ends_with(is_py_space) {
                out.push(' ');
            }
        }
    }
    py_strip(&out).to_string()
}

// ------------------------------------------------------------------------------------------------ memo

const MEMO_SIZE: usize = 1024;

struct Node {
    /// Index of the language in [`crate::LANGUAGES`].
    lang: usize,
    text: Arc<str>,
    value: String,
    prev: usize,
    next: usize,
}

/// LRU over `(text, language)` (move-to-end on hit, evict oldest), looked up without allocating; an insert stores the
/// text once, shared by the index and the node. Only languages with a grammar are memoized (others only collapse line
/// breaks).
struct Memo {
    /// Per language: text → node.
    index: Vec<HashMap<Arc<str>, usize>>,
    /// Sentinel at index 0 of a circular list: `nodes[0].next` is the oldest, `nodes[0].prev` the newest.
    nodes: Vec<Node>,
    free: Vec<usize>,
    len: usize,
}

impl Memo {
    fn new() -> Memo {
        let sentinel = Node { lang: 0, text: Arc::from(""), value: String::new(), prev: 0, next: 0 };
        Memo {
            index: crate::LANGUAGES.iter().map(|_| HashMap::new()).collect(),
            nodes: vec![sentinel],
            free: Vec::new(),
            len: 0,
        }
    }

    /// Empty, keeping the allocations.
    fn clear(&mut self) {
        self.index.iter_mut().for_each(HashMap::clear);
        self.nodes.truncate(1);
        self.nodes[0].prev = 0;
        self.nodes[0].next = 0;
        self.free.clear();
        self.len = 0;
    }

    fn unlink(&mut self, i: usize) {
        let (p, n) = (self.nodes[i].prev, self.nodes[i].next);
        self.nodes[p].next = n;
        self.nodes[n].prev = p;
    }

    fn push_newest(&mut self, i: usize) {
        let last = self.nodes[0].prev;
        self.nodes[i].prev = last;
        self.nodes[i].next = 0;
        self.nodes[last].next = i;
        self.nodes[0].prev = i;
    }

    fn get(&mut self, text: &str, lang: usize) -> Option<String> {
        let i = *self.index[lang].get(text)?;
        self.unlink(i);
        self.push_newest(i);
        Some(self.nodes[i].value.clone())
    }

    fn insert(&mut self, text: &str, lang: usize, value: String) {
        if let Some(&i) = self.index[lang].get(text) {
            self.nodes[i].value = value;
            self.unlink(i);
            self.push_newest(i);
            return;
        }
        let text: Arc<str> = Arc::from(text);
        let node = Node { lang, text: Arc::clone(&text), value, prev: 0, next: 0 };
        let i = match self.free.pop() {
            Some(i) => {
                self.nodes[i] = node;
                i
            }
            None => {
                self.nodes.push(node);
                self.nodes.len() - 1
            }
        };
        self.index[lang].insert(text, i);
        self.push_newest(i);
        self.len += 1;
        while self.len > MEMO_SIZE {
            let oldest = self.nodes[0].next;
            self.unlink(oldest);
            let node = &mut self.nodes[oldest];
            self.index[node.lang].remove(&*node.text);
            node.value = String::new();
            self.free.push(oldest);
            self.len -= 1;
        }
    }
}

/// A text normalizer: the markup it keeps as typed and its memo of the last 1024 results. `Send + Sync`; calls on one
/// normalizer from several threads share the memo.
pub struct Normalizer {
    tags: Vec<Box<str>>,
    memo: Mutex<Memo>,
}

impl Default for Normalizer {
    fn default() -> Self {
        Self::new()
    }
}

impl Normalizer {
    /// A normalizer that keeps no markup.
    pub fn new() -> Self {
        Self::with_markup_tags(std::iter::empty::<&str>())
    }

    /// A normalizer that keeps the markup of `tags` as typed: point tags (`<laugh/>`, `<laugh>`) and span tags
    /// (`<shouting>…</shouting>`), `\s*` allowed before the `/` or `>`. Tag names match literally and in order, as
    /// the alternatives of `</?(?:laugh|…)\s*/?>`; the text between markers is normalized piece by piece.
    pub fn with_markup_tags<I, S>(tags: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        Normalizer { tags: tags.into_iter().map(|t| t.as_ref().into()).collect(), memo: Mutex::new(Memo::new()) }
    }

    /// The markup tags this normalizer keeps, in order.
    pub fn markup_tags(&self) -> impl Iterator<Item = &str> {
        self.tags.iter().map(|t| &**t)
    }

    /// The spoken form of `text` in `language` (one of [`crate::LANGUAGES`]), memoized. Never fails: a language
    /// without a grammar in this build comes back with its line breaks collapsed
    /// ([`crate::collapse_line_breaks`]), and a sentence the grammar fails on is kept as typed. Line breaks are
    /// collapsed first; the markup tags and verbatim spans (U+E000 … U+E001, e.g. pronunciations) stay as typed.
    pub fn normalize(&self, text: &str, language: &str) -> String {
        let Some(lang) = crate::LANGUAGES.iter().position(|l| *l == language).filter(|_| crate::supported(language))
        else {
            return collapse_line_breaks(text).into_owned();
        };
        if let Some(hit) = self.memo.lock().unwrap_or_else(|e| e.into_inner()).get(text, lang) {
            return hit;
        }
        let result = normalize_uncached(text, language, &self.tags);
        self.memo.lock().unwrap_or_else(|e| e.into_inner()).insert(text, lang, result.clone());
        result
    }

    /// Empty the memo.
    pub fn clear_memo(&self) {
        self.memo.lock().unwrap_or_else(|e| e.into_inner()).clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn line_breaks() {
        assert_eq!(collapse_line_breaks("spend less.\n\nHunt’s Tolan"), "spend less. Hunt’s Tolan");
        assert_eq!(collapse_line_breaks("Line one.\r\nLine two."), "Line one. Line two.");
        assert_eq!(collapse_line_breaks("Tabbed.\tNext"), "Tabbed. Next");
        assert_eq!(collapse_line_breaks("Three\n\n\nbreaks"), "Three breaks");
        for s in ["one line", "two  spaces", "  lead", "trail  ", ""] {
            assert_eq!(collapse_line_breaks(s), s);
        }
    }

    #[test]
    fn pre_passes_match_textnorm_py() {
        assert_eq!(pre_normalize("We are open 24/7.", "en"), "We are open 24 7 .");
        assert_eq!(pre_normalize("a 50/50 call, an 80/20 split", "en"), "a 50 50 call, an 80 20 split");
        assert_eq!(pre_normalize("on 9/11", "en"), "on 9 11");
        assert_eq!(pre_normalize("3/4 of the cake on 10/19", "en"), "3/4 of the cake on 10/19");
        assert_eq!(pre_normalize("Save $20k or $1.5k or £2k.", "en"), "Save $20,000 or $1,500 or £2,000.");
        assert_eq!(pre_normalize("In 1990, he left.", "en"), "In 1990 , he left.");
        assert_eq!(pre_normalize("1/2/3 and 123/4", "en"), "1/2/3 and 123/4");
        assert_eq!(pre_normalize("Am 3. Oktober 2026 um 10 Uhr.", "de"), "Am 3. Oktober 2026 um 10 Uhr.");
        assert_eq!(pre_normalize("Seit 1990. Danach nichts.", "de"), "Seit 1990 . Danach nichts.");
        assert_eq!(pre_normalize("Ich zähle 1, 2, 3.", "de"), "Ich zähle 1 , 2 , 3 .");
        assert_eq!(pre_normalize("Es geschah am 19.10.2026.", "de"), "Es geschah am 19.10.2026 .");
        assert_eq!(pre_normalize("Er sagte „1990.“", "de"), "Er sagte „1990 .“");
        assert_eq!(pre_normalize("値段は5.5ドルです。 次。", "ja"), "値段は5.5ドルです。次。");
        assert_eq!(pre_normalize("3.5 km、100万 人。", "ja"), "3.5 km、100万人。");
        assert_eq!(pre_normalize("Hello 世界", "ja"), "Hello 世界");
        assert_eq!(pre_normalize("一 \u{3000}x", "zh"), "一\u{3000}x");
    }

    #[test]
    fn post_passes() {
        assert_eq!(post_normalize("dez por cento ; primeiro , segundo .", "pt"), "dez por cento; primeiro, segundo.");
        assert_eq!(post_normalize("( dez pessoas) vieram", "pt"), "(dez pessoas) vieram");
        assert_eq!(post_normalize("a , b .x .", "en"), "a, b .x.");
    }

    #[test]
    fn splitting() {
        assert_eq!(split_sentences("a. b!  c"), ["a.", "b!", "c"]);
        assert_eq!(split_sentences("一。二。 三"), ["一。", "二。", " 三"]);
        assert_eq!(split_groups("I paid 5 \u{e000}kæt\u{e001} for"), ["I paid 5 ", "\u{e000}kæt\u{e001}", " for"]);
        let tags: Vec<Box<str>> = ["laugh", "shouting"].map(Box::from).into();
        assert_eq!(
            split_markup("a <laugh/> b</shouting >", &tags).unwrap(),
            ["a ", "<laugh/>", " b", "</shouting >", ""]
        );
        assert!(split_markup("a <giggle/> b", &tags).is_none());
        assert!(split_markup("a <laugh/> b", &[]).is_none());
    }

    #[test]
    fn memo_evicts_oldest() {
        let mut m = Memo::new();
        for i in 0..1025 {
            m.insert(&i.to_string(), 0, i.to_string());
        }
        assert!(m.get("0", 0).is_none());
        assert_eq!(m.get("1", 0).as_deref(), Some("1"));
        m.insert("new", 0, "n".into());
        assert_eq!(m.get("1", 0).as_deref(), Some("1")); // moved to end by the get, so "2" was evicted
        assert!(m.get("2", 0).is_none());
        assert!(m.get("1", 1).is_none()); // per language
        m.clear();
        assert!(m.get("1", 0).is_none());
        m.insert("x", 1, "y".into());
        assert_eq!(m.get("x", 1).as_deref(), Some("y"));
    }
}
