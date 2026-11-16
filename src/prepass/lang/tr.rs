//! 'tr' rules: the port of the workbench's `langrules/tr.py` (ids `tr.*`).
//!
//! The Turkish grammar reads a dot-grouped number (52.000) as a decimal, leaves times, percentages, currencies and
//! fractions with an apostrophe suffix unread (14.30'da, %20'si, 100 TL'ye, ¾'ü), glues a suffix to a number as
//! written (5'de → beşde) and reads speeds as “kilometre bölü saat”. These rules write the spoken words for those
//! spans, with the suffix re-derived by vowel harmony from the spoken word it is glued to.

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("tr.minus-percent", tr_minus_percent),
    ("tr.thousands", tr_thousands),
    ("tr.speed", tr_speed),
    ("tr.percent", tr_percent),
    ("tr.unit-suffix", tr_unit_suffix),
    ("tr.time", tr_time),
    ("tr.fraction", tr_fraction),
    ("tr.suffix", tr_suffix),
];

// ------------------------------------------------------------------------------------------------- vowel harmony

const VOWELS: &str = "aeıioöuü";
const BACK: &str = "aıou";
const VOICELESS: &str = "çfhkpsşt";
/// A suffix after an apostrophe: lowercase Turkish letters.
const SUFFIX: &str = r"['’]([a-zçğıöşü]+)(?![\w'’])";

fn four(v: char) -> char {
    match v {
        'a' | 'ı' => 'ı',
        'o' | 'u' => 'u',
        'e' | 'i' => 'i',
        _ => 'ü',
    }
}

fn last_vowel(w: &str) -> char {
    w.chars().rev().find(|ch| VOWELS.contains(*ch)).unwrap_or('e')
}

/// `suffix` as written after a number, re-derived for the spoken word `stem` it is glued to.
fn harmonize(stem: &str, suffix: &str) -> String {
    if stem.is_empty() {
        return suffix.to_string();
    }
    let mut suffix: Vec<char> = suffix.chars().collect();
    let mut tail = "";
    if suffix.len() > 2 && suffix.ends_with(&['k', 'i']) {
        suffix.truncate(suffix.len() - 2);
        tail = "ki";
    }
    let prev = stem.chars().next_back();
    let prev_vowel = prev.is_some_and(|p| VOWELS.contains(p));
    if !prev_vowel && suffix.len() >= 2 && "ynsş".contains(suffix[0]) && VOWELS.contains(suffix[1]) {
        suffix.remove(0);
    }
    let voiceless = prev.is_some_and(|p| VOICELESS.contains(p));
    let mut v = last_vowel(stem);
    let mut out = String::new();
    for (j, mut ch) in suffix.into_iter().enumerate() {
        if ch == 'a' || ch == 'e' {
            ch = if BACK.contains(v) { 'a' } else { 'e' };
            v = ch;
        } else if "ıiuü".contains(ch) {
            ch = four(v);
            v = ch;
        } else if VOWELS.contains(ch) {
            v = ch;
        } else if j == 0 && (ch == 'd' || ch == 't') {
            ch = if voiceless { 't' } else { 'd' };
        } else if j == 0 && (ch == 'c' || ch == 'ç') {
            ch = if voiceless { 'ç' } else { 'c' };
        }
        out.push(ch);
    }
    out.push_str(tail);
    out
}

/// The spoken words with `suffix` glued to the last one, harmonized; dört and çeyrek soften before a vowel.
fn attach(spoken: &str, suffix: &str) -> String {
    let (head, last) = spoken.rsplit_once(' ').unwrap_or(("", spoken));
    let h = harmonize(last, suffix);
    let mut last = last;
    if h.chars().next().is_some_and(|ch| VOWELS.contains(ch)) {
        if last == "dört" {
            last = "dörd";
        } else if last == "çeyrek" {
            last = "çeyreğ";
        }
    }
    if head.is_empty() { format!("{last}{h}") } else { format!("{head} {last}{h}") }
}

// ------------------------------------------------------------------------------------------------- rules

fn tr_thousands(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,])([1-9]\d{0,2}(?:\.\d{3})+)(?!\d|\.\d)"), &t, |m| {
        let groups: Vec<&str> = g(m, 1).split('.').collect();
        if groups.len() == 4 && groups.iter().all(|x| py_int(x) <= 255) && groups[1..].iter().any(|x| *x != "000") {
            return None;
        }
        Some(groups.concat())
    })
}

fn speed_word(unit: &str) -> &'static str {
    match unit {
        "sa" | "saat" | "h" => "saatte",
        _ => "saniyede",
    }
}

fn tr_speed(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.,])(\d+(?:,\d+)?) ?(km|m)/(saat|sa|sn|s|h)(?![\w/])(?:{SUFFIX})?")), &t, |m| {
        let unit = if g(m, 2) == "km" { "kilometre" } else { "metre" };
        let spoken = format!("{} {unit}", words(g(m, 1), "tr"));
        let spoken = if m.get(4).is_some() { attach(&spoken, g(m, 4)) } else { spoken };
        Some(format!("{} {spoken}", speed_word(g(m, 3))))
    })
}

fn tr_percent(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.,])%(\d+(?:,\d+)?){SUFFIX}")), &t, |m| {
        Some(format!("yüzde {}", attach(&words(g(m, 1), "tr"), g(m, 2))))
    })
}

fn currency_word(code: &str) -> Option<&'static str> {
    Some(match code {
        "TL" | "₺" | "TRY" => "lira",
        "$" | "USD" => "dolar",
        "€" | "EUR" => "euro",
        "£" | "GBP" => "sterlin",
        _ => return None,
    })
}

/// Time abbreviations the grammar leaves unread after a number.
fn abbr_word(a: &str) -> Option<&'static str> {
    Some(match a {
        "dk" | "dak" => "dakika",
        "sn" => "saniye",
        "sa" => "saat",
        _ => return None,
    })
}

fn tr_unit_suffix(t: String, c: &mut Ctx) -> String {
    let t =
        c.sub(&rx(r"(?<![\w.,])(\d+(?:,\d+)?) (dk|dak|sn|sa)(?:\.(?= [a-zçğıöşü]))?(?![\w/'’])"), &t, |m| {
            Some(format!("{} {}", g(m, 1), abbr_word(g(m, 2))?))
        });
    c.sub(&rx(&format!(r"(?<![\w.,])(\d+(?:,\d+)?)( ?)([^\s\d'’.,;:!?()\[\]/]+){SUFFIX}")), &t, |m| {
        let (num, sp, tok, suffix) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        if let Some(word) = currency_word(tok).or_else(|| abbr_word(tok)) {
            return Some(format!("{} {}", words(num, "tr"), attach(word, suffix)));
        }
        let base = words(num, "tr");
        let w = words(&format!("{num}{sp}{tok}"), "tr");
        if w == format!("{base}{sp}{tok}") || !w.starts_with(&format!("{base} ")) {
            return None;
        }
        Some(attach(&w, suffix))
    })
}

fn tr_time(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(r"(?<!\w)([Ss]aat(?:i|te|ler)?) ([01]?\d|2[0-3])\.([0-5]\d)(?: ?([-–]) ?([01]?\d|2[0-3])\.([0-5]\d))?(?!\d|[.,]\d)"),
        &t,
        |m| {
            let range =
                if m.get(4).is_some() { format!("{}{}:{}", g(m, 4), g(m, 5), g(m, 6)) } else { String::new() };
            Some(format!("{} {}:{}{range}", g(m, 1), g(m, 2), g(m, 3)))
        },
    );
    c.sub(&rx(&format!(r"(?<![\w.,:])([01]?\d|2[0-3])[:.]([0-5]\d){SUFFIX}")), &t, |m| {
        Some(attach(&words(&format!("{}:{}", g(m, 1), g(m, 2)), "tr"), g(m, 3)))
    })
}

fn vulgar(ch: &str) -> (u128, u128) {
    match ch {
        "½" => (1, 2),
        "⅓" => (1, 3),
        "⅔" => (2, 3),
        "¼" => (1, 4),
        "¾" => (3, 4),
        "⅕" => (1, 5),
        "⅖" => (2, 5),
        "⅗" => (3, 5),
        "⅘" => (4, 5),
        "⅙" => (1, 6),
        "⅚" => (5, 6),
        "⅛" => (1, 8),
        "⅜" => (3, 8),
        "⅝" => (5, 8),
        _ => (7, 8),
    }
}

/// a/b the Turkish way: the denominator in the locative, then the numerator (dörtte üç).
fn fraction(a: u128, b: u128, suffix: &str) -> String {
    if a == 1 && b == 2 {
        return if suffix.is_empty() { "yarım".into() } else { attach("yarı", suffix) };
    }
    if a == 1 && b == 4 {
        return if suffix.is_empty() { "çeyrek".into() } else { attach("çeyrek", suffix) };
    }
    let spoken = format!("{} {}", attach(&words(&b.to_string(), "tr"), "de"), words(&a.to_string(), "tr"));
    if suffix.is_empty() { spoken } else { attach(&spoken, suffix) }
}

fn tr_fraction(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"([½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]){SUFFIX}")), &t, |m| {
        let (a, b) = vulgar(g(m, 1));
        Some(fraction(a, b, g(m, 2)))
    });
    c.sub(&rx(&format!(r"(?<![\w.,/])(\d{{1,2}})/(\d{{1,3}})(?![\d/]|[.,]\d)(?:{SUFFIX})?")), &t, |m| {
        let (a, b) = (py_int(g(m, 1)), py_int(g(m, 2)));
        if !(1 <= a && a < b && (b <= 10 || b == 100)) {
            return None;
        }
        let out = fraction(a, b, g(m, 3));
        if m.get(3).is_none() && out == words(g(m, 0), "tr") { None } else { Some(out) }
    })
}

fn tr_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.,:])(\d+)(\.?){SUFFIX}")), &t, |m| {
        let (num, dot, suffix) = (g(m, 1), g(m, 2), g(m, 3));
        let ord = rx(r"^[ıiuü]?nc[ıiuü]").find(suffix).ok().flatten().map(|x| x.end());
        if !dot.is_empty() || ord.is_some() {
            let rest = &suffix[ord.unwrap_or(0)..];
            let ordw = words(&format!("{num}."), "tr");
            let out = if rest.is_empty() { ordw } else { attach(&ordw, rest) };
            return if out == words(g(m, 0), "tr") { None } else { Some(out) };
        }
        let spoken = words(num, "tr");
        let last = spoken.rsplit_once(' ').map_or(spoken.as_str(), |(_, l)| l);
        let h = harmonize(last, suffix);
        let apostrophe = g(m, 0)[num.len()..].starts_with('\'');
        if h == suffix && apostrophe { None } else { Some(format!("{num}'{h}")) }
    })
}

fn tr_minus_percent(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,)\]\-−+*/=^])[-−](?=\d+(?:,\d+)?\s?%)"), &t, |_| Some("eksi ".to_string()))
}
