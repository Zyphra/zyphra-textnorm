//! 'hi' rules: the port of the workbench's `langrules/hi.py` (ids `hi.*`).
//!
//! The first half holds the helpers the Indic modules share (mr, gu, pa, bn, or and ur call them with their own
//! tables): am/pm, clock times before a written hour word, years, the spoken minus, Latin words glued to a number,
//! ranges, scores, halves before lakh/crore, regnal numerals and numbers glued to a postposition.

use std::collections::HashMap;
use std::sync::{LazyLock, Mutex};

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("hi.glued", hi_glued),
    ("hi.iso-date", hi_iso_date),
    ("hi.ampm", hi_ampm),
    ("hi.clock-hourword", hi_clock),
    ("hi.minus", hi_minus),
    ("hi.latin-number", hi_latin_number),
    ("hi.score", hi_score),
    ("hi.range", hi_range),
    ("hi.half-scale", hi_half_scale),
    ("hi.units", hi_units),
    ("hi.regnal", hi_regnal),
];

// ================================================================================================= Indic helpers

/// Letters and signs of each script, without its digits, dandas or currency signs.
pub(super) const DEVA: &str = "[\u{0900}-\u{0963}\u{0971}-\u{097f}]";
pub(super) const BENG: &str = "[\u{0980}-\u{09e5}\u{09f0}\u{09f1}]";
pub(super) const GURU: &str = "[\u{0a00}-\u{0a65}\u{0a70}-\u{0a7f}]";
pub(super) const GUJR: &str = "[\u{0a80}-\u{0ae5}]";
pub(super) const ORYA: &str = "[\u{0b00}-\u{0b65}\u{0b71}]";
pub(super) const ARAB: &str = "[\u{0621}-\u{065f}\u{0670}-\u{06d3}\u{06d5}-\u{06ef}\u{06fa}-\u{06ff}]";

/// Nukta letters: precomposed and decomposed spellings of the same letter (text comes in either).
const NUKTA: &[(&str, &str)] = &[
    ("\u{0958}", "\u{0915}\u{093c}"),
    ("\u{0959}", "\u{0916}\u{093c}"),
    ("\u{095a}", "\u{0917}\u{093c}"),
    ("\u{095b}", "\u{091c}\u{093c}"),
    ("\u{095c}", "\u{0921}\u{093c}"),
    ("\u{095d}", "\u{0922}\u{093c}"),
    ("\u{095e}", "\u{092b}\u{093c}"),
    ("\u{095f}", "\u{092f}\u{093c}"),
    ("\u{09dc}", "\u{09a1}\u{09bc}"),
    ("\u{09dd}", "\u{09a2}\u{09bc}"),
    ("\u{09df}", "\u{09af}\u{09bc}"),
    ("\u{0a59}", "\u{0a16}\u{0a3c}"),
    ("\u{0a5a}", "\u{0a17}\u{0a3c}"),
    ("\u{0a5b}", "\u{0a1c}\u{0a3c}"),
    ("\u{0a5e}", "\u{0a2b}\u{0a3c}"),
    ("\u{0a33}", "\u{0a32}\u{0a3c}"),
    ("\u{0a36}", "\u{0a38}\u{0a3c}"),
    ("\u{0b5c}", "\u{0b21}\u{0b3c}"),
    ("\u{0b5d}", "\u{0b22}\u{0b3c}"),
];

/// `s`, then its all-precomposed and all-decomposed nukta spellings when they differ.
fn spellings(s: &str) -> Vec<String> {
    let mut out = vec![s.to_string()];
    let (mut comp, mut dec) = (s.to_string(), s.to_string());
    for &(p, d) in NUKTA {
        comp = comp.replace(d, p);
        dec = dec.replace(p, d);
    }
    for x in [comp, dec] {
        if !out.contains(&x) {
            out.push(x);
        }
    }
    out
}

/// Alternation of plain-text `keys` in every nukta spelling ('.' matches a dot), longest first, ties in order
/// (memoized: the rules build their patterns from the same tables on every text).
pub(super) fn alt(keys: &[&str]) -> String {
    static MEMO: LazyLock<Mutex<HashMap<String, String>>> = LazyLock::new(|| Mutex::new(HashMap::new()));
    let id = keys.join("\u{1}");
    if let Some(s) = MEMO.lock().unwrap_or_else(|e| e.into_inner()).get(&id) {
        return s.clone();
    }
    let mut ks: Vec<String> = keys.iter().flat_map(|k| spellings(k)).collect();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    let out = ks.iter().map(|k| k.replace('.', "\\.")).collect::<Vec<_>>().join("|");
    MEMO.lock().unwrap_or_else(|e| e.into_inner()).insert(id, out.clone());
    out
}

pub(super) const NOT_NUM_BEFORE: &str = r"(?<![\w.,:/\-–])";
pub(super) const NOT_NUM_AFTER: &str = r"(?![\w]|[.,:/\-–]\d)";

/// `re.search(r"\d", s)`.
pub(super) fn has_digit(s: &str) -> bool {
    search(r"\d", s)
}

// --------------------------------------------------------------------------- am / pm

const AMPM: &str = r"(?<![\d:.,])(\d{1,2})(?::(\d\d))?\s?(a\.m\.|p\.m\.|A\.M\.|P\.M\.|am|pm|AM|PM)(?![A-Za-z])";

/// `5 pm` -> `5 पी एम` (the marker in the script's letters). With `minutes`, also `5:30 pm` and `5:00 pm` -> the
/// bare hour.
pub(super) fn ampm(t: String, c: &mut Ctx, am: &str, pm: &str, minutes: bool) -> String {
    c.sub(&rx(AMPM), &t, |m| {
        let h = py_int(g(m, 1));
        if !(1..=12).contains(&h) {
            return None;
        }
        let say = if g(m, 3).starts_with(['p', 'P']) { pm } else { am };
        if g(m, 2).is_empty() {
            return Some(format!("{h} {say}"));
        }
        if !minutes || py_int(g(m, 2)) > 59 {
            return None;
        }
        if py_int(g(m, 2)) == 0 {
            return Some(format!("{h} {say}"));
        }
        Some(format!("{h}:{} {say}", g(m, 2)))
    })
}

// --------------------------------------------------------------------------- H:MM before a written hour word

/// `colloquial(h, mm)`: a quarter/half form that keeps the hour word.
pub(super) type Colloquial<'a> = Option<&'a dyn Fn(u128, u128) -> Option<String>>;
/// `absorb(reading, hour word, following postposition)`.
pub(super) type Absorb<'a> = &'a dyn Fn(&str, &str, &str) -> Option<String>;

/// `H:MM <hour word>`: :00 -> the bare hour; a colloquial form (1–12 o'clock) keeps the hour word; otherwise `absorb`
/// rewrites the grammar's reading of H:MM so the hour word is said once.
#[allow(clippy::too_many_arguments)]
pub(super) fn clock_hourword(
    t: String,
    c: &mut Ctx,
    lang: &str,
    w: &str,
    hourwords: &[&str],
    after: &[&str],
    colloquial: Colloquial<'_>,
    absorb: Absorb<'_>,
) -> String {
    let mut pat = [r"(?<![\d:.,])(\d{1,2}):(\d\d)(\s?)(", &alt(hourwords), ")(?!", w, ")"].concat();
    if !after.is_empty() {
        pat.push_str(&[r"(?:(\s)(", &alt(after), ")(?!", w, "))?"].concat());
    }
    let has_after = !after.is_empty();
    c.sub(&rx(&pat), &t, |m| {
        let (h, mm) = (py_int(g(m, 1)), py_int(g(m, 2)));
        if h > 23 || mm > 59 {
            return None;
        }
        let tail = if has_after { format!("{}{}", g(m, 5), g(m, 6)) } else { String::new() };
        if mm == 0 {
            return Some(format!("{h}{}{}{tail}", g(m, 3), g(m, 4)));
        }
        let say = match colloquial {
            Some(f) if (1..=12).contains(&h) => f(h, mm),
            _ => None,
        };
        if let Some(say) = say {
            return Some(format!("{say} {}{tail}", g(m, 4)));
        }
        absorb(&words(&format!("{h}:{mm:02}"), lang), g(m, 4), if has_after { g(m, 6) } else { "" })
    })
}

/// The quarter-hour forms: 1:30 `one_half`, 2:30 `two_half`, H:30 `half`+H, H:15 `quarter`+H, H:45 `to`+(H+1)
/// (`sep` between the word and the number; 1:15 and 12:45 keep the full reading).
#[allow(clippy::too_many_arguments)]
pub(super) fn quarters(
    h: u128,
    mm: u128,
    lang: &str,
    one_half: &str,
    two_half: &str,
    half: &str,
    quarter: &str,
    to: &str,
    sep: &str,
) -> Option<String> {
    if mm == 30 {
        return Some(match h {
            1 => one_half.to_string(),
            2 => two_half.to_string(),
            _ => format!("{half}{sep}{}", words(&h.to_string(), lang)),
        });
    }
    if mm == 15 && h > 1 {
        return Some(format!("{quarter}{sep}{}", words(&h.to_string(), lang)));
    }
    if mm == 45 && h < 12 {
        return Some(format!("{to}{sep}{}", words(&(h + 1).to_string(), lang)));
    }
    None
}

/// hi/pa/ur: `तीन बजकर बीस मिनट बजे` -> `तीन बजकर बीस मिनट पर` (or the postposition that follows).
pub(super) fn absorb_postposition(
    reading: &str,
    word: &str,
    after: &str,
    minute: &str,
    at: &str,
    default: &str,
) -> Option<String> {
    if word != at || !reading.ends_with(&format!(" {minute}")) {
        return None;
    }
    Some(format!("{reading} {}", if after.is_empty() { default } else { after }))
}

// --------------------------------------------------------------------------- years 1100–1999

/// 1960 -> `<19><hundred> <60>` (उन्नीस सौ साठ, एकोणीसशे साठ, উনিশশো ষাট).
pub(super) fn year_words(n: u128, lang: &str, hundred: &str) -> String {
    let s = format!("{}{hundred}", words(&(n / 100).to_string(), lang));
    if !n.is_multiple_of(100) { format!("{s} {}", words(&(n % 100).to_string(), lang)) } else { s }
}

pub(super) fn is_year(digits: &str) -> bool {
    (1100..=1999).contains(&py_int(digits))
}

/// A 4-digit 1100–1999 read the way years are said: in a numeric date, a decade (1990s), after a month name, after a
/// year word (`pre`) or before one (`post`: whole words; `post_stems`: the start of a word).
#[allow(clippy::too_many_arguments)]
pub(super) fn years(
    t: String,
    c: &mut Ctx,
    lang: &str,
    w: &str,
    hundred: &str,
    pre: &[&str],
    post: &[&str],
    post_stems: &[&str],
    months: &[&str],
) -> String {
    let t = c.sub(&rx(&[NOT_NUM_BEFORE, r"(\d{1,2}([/.\-])\d{1,2}\2(\d{4}))(?!\d|[.,:/\-–]\d)"].concat()), &t, |m| {
        if !is_year(g(m, 3)) {
            return None;
        }
        let (reading, card) = (words(g(m, 1), lang), words(g(m, 3), lang));
        if !reading.ends_with(&format!(" {card}")) || has_digit(&reading) {
            return None;
        }
        Some(format!("{}{}", &reading[..reading.len() - card.len()], year_words(py_int(g(m, 3)), lang, hundred)))
    });
    let t = c.sub(&rx(&[NOT_NUM_BEFORE, r"(\d{4})'?s(?![A-Za-z])"].concat()), &t, |m| {
        let (said, card) = (words(&m[0], lang), words(g(m, 1), lang));
        if !is_year(g(m, 1)) || !said.starts_with(&card) || has_digit(&said) {
            return None;
        }
        Some(format!("{}{}", year_words(py_int(g(m, 1)), lang, hundred), &said[card.len()..]))
    });
    let cue_before = |m: &Captures<'_, str>| {
        is_year(g(m, 2)).then(|| format!("{}{}", g(m, 1), year_words(py_int(g(m, 2)), lang, hundred)))
    };
    let t =
        c.sub(&rx(&["((?<!", w, ")(?:", &alt(months), r")\.?,?\s)(\d{4})(?!\d|[.,:/\-–]\d)"].concat()), &t, cue_before);
    let t = c.sub(&rx(&["((?<!", w, ")(?:", &alt(pre), r")\s?)(\d{4})(?!\d|[.,:/\-–]\d)"].concat()), &t, cue_before);
    let mut cue = ["(?:", &alt(post), ")(?!", w, ")"].concat();
    if !post_stems.is_empty() {
        cue = ["(?:", &cue, "|", &alt(post_stems), ")"].concat();
    }
    c.sub(&rx(&[NOT_NUM_BEFORE, r"(\d{4})(?=\s?", &cue, ")"].concat()), &t, |m| {
        is_year(g(m, 1)).then(|| year_words(py_int(g(m, 1)), lang, hundred))
    })
}

// --------------------------------------------------------------------------- minus

/// `-3 डिग्री` -> `माइनस 3 डिग्री`: the spoken minus before a temperature, unit, percent or amount, or after a
/// temperature word; a bare negative number keeps the grammar's formal word.
pub(super) fn minus(
    t: String,
    c: &mut Ctx,
    word: &str,
    w: &str,
    units: &[&str],
    cues: &[&str],
    connectors: &[&str],
) -> String {
    let num = r"\d+(?:\.\d+)?";
    let unit = [r"(?:[°℃℉%]|", &alt(units), r"|(?:kg|km|cm|mm|mg|ml|m|g|l|L)(?![A-Za-z]))"].concat();
    let lead = [r"(?<![\w.,)\]\-−+*/=^])(?<!", w, ")"].concat();
    let t = c.sub(&rx(&["((?<!", w, ")(?:", &alt(cues), r")\s(?:", w, r"+\s){0,2})[-−](?=\d)"].concat()), &t, |m| {
        Some(format!("{}{word} ", g(m, 1)))
    });
    let rng = [r"(?:\s?(?:", &alt(connectors), r"|-|–)\s?[-−]?", num, ")?"].concat();
    let t =
        c.sub(&rx(&[&lead, r"[-−](?=", num, &rng, r"\s?", &unit, ")"].concat()), &t, |_| Some(format!("{word} ")));
    c.sub(&rx(&[&lead, r"[-−](?=\d)"].concat()), &t, |_| Some(format!("{word} ")))
}

// --------------------------------------------------------------------------- Latin words glued to a number

const LATIN_NUM: &str = r"(?<![\w@/.\-])([A-Za-z]{2,})-?(\d+)(?![\w@/]|[.,:\-][\w@/])";

pub(super) const ACRONYMS: &[&str] = &["COVID", "NASA", "ISRO", "NATO", "UNESCO", "UNICEF", "SARS", "MERS", "AIIMS"];

/// `COVID-19` -> `COVID 19`: a pronounceable Latin word glued to a number stays a word and the number is read;
/// `said` holds words with their own reading (T20 -> टी ट्वेंटी).
pub(super) fn latin_number(t: String, c: &mut Ctx, acronyms: &[&str], said: &[(&str, &str)]) -> String {
    let mut t = t;
    if !said.is_empty() {
        let keys: Vec<&str> = said.iter().map(|&(k, _)| k).collect();
        t = c.sub(&rx(&[r"(?<![\w@/.\-])(", &alt(&keys), r")(?![\w@/]|[.,:\-][\w@/])"].concat()), &t, |m| {
            said.iter().find(|&&(k, _)| k == g(m, 1)).map(|&(_, v)| v.to_string())
        });
    }
    c.sub(&rx(LATIN_NUM), &t, |m| {
        let letters = g(m, 1);
        let upper = letters.chars().all(|ch| ch.is_ascii_uppercase());
        let word = acronyms.contains(&letters.to_ascii_uppercase().as_str())
            || (!upper && letters.chars().count() >= 4 && letters.chars().any(|ch| "aeiouyAEIOUY".contains(ch)));
        word.then(|| format!("{letters} {}", g(m, 2)))
    })
}

// --------------------------------------------------------------------------- N-M ranges

fn leading_zero(s: &str) -> bool {
    s.chars().next().is_some_and(|ch| py_int(&ch.to_string()) == 0)
}

/// `5-10 साल` -> `5 से 10 साल`: two plain ascending numbers joined by a hyphen or en dash, followed by a word
/// (not a postposition or verb) or %, are a range.
pub(super) fn ranges(t: String, c: &mut Ctx, w: &str, connector: &str, stop: &[&str]) -> String {
    let pat = [
        NOT_NUM_BEFORE,
        r"(\d{1,7})(\s?)[-–](\s?)(\d{1,7})",
        NOT_NUM_AFTER,
        r"(?=\s?%|\s(?!(?:",
        &alt(stop),
        ")(?!",
        w,
        "))(?:",
        w,
        "|[A-Za-z]))",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 4));
        if (a.chars().count() > 1 && leading_zero(a)) || leading_zero(b) || py_int(a) >= py_int(b) {
            return None;
        }
        Some(format!("{a} {connector} {b}"))
    })
}

// --------------------------------------------------------------------------- match scores

/// `3-1 से जीता` -> `तीन-एक से जीता`: N-M or N:M before a postposition (`links`) and a win/loss/draw word (`cues`,
/// word starts; none: the link word alone, `3-1 গোলে`) is a score, kept from the date, time and range readings (a
/// verbatim span).
pub(super) fn score(t: String, c: &mut Ctx, lang: &str, w: &str, links: &[&str], cues: &[&str]) -> String {
    let cue = if cues.is_empty() { ["(?!", w, ")"].concat() } else { [r"\s(?:", &alt(cues), ")"].concat() };
    let pat =
        [NOT_NUM_BEFORE, r"(\d{1,2})[-:](\d{1,2})", NOT_NUM_AFTER, r"(?=\s(?:", &alt(links), ")", &cue, ")"].concat();
    c.sub(&rx(&pat), &t, |m| Some(format!("\u{e000}{}-{}\u{e001}", words(g(m, 1), lang), words(g(m, 2), lang))))
}

// --------------------------------------------------------------------------- halves before lakh / crore

/// The grammar's word for a currency sign before 2 (₹ -> रुपए), or None.
fn currency_word(cur: &str, lang: &str) -> Option<String> {
    let two = words("2", lang);
    let sep = if cur.chars().next().is_some_and(char::is_alphabetic) { " 2" } else { "2" };
    let said = words(&format!("{cur}{sep}"), lang);
    let head = format!("{two} ");
    (said.starts_with(&head) && !has_digit(&said)).then(|| said[head.len()..].to_string())
}

/// `2.5 करोड़` -> `ढाई करोड़`; a currency sign before the amount moves after its scale words when the grammar would
/// put it after the first one (`₹2.5 लाख करोड़`, `₹2 लाख 50 हज़ार`; with `move_currency` for any amount).
#[allow(clippy::too_many_arguments)]
pub(super) fn half_scale(
    t: String,
    c: &mut Ctx,
    lang: &str,
    w: &str,
    scales: &[&str],
    curs: &[&str],
    half: &dyn Fn(u128) -> String,
    move_currency: bool,
) -> String {
    let sc = ["(?:", &alt(scales), ")(?!", w, ")"].concat();
    let run = [sc.as_str(), r"(?:\s", &sc, ")*"].concat();
    let pat = [
        r"(?<![\w.,])(?:(",
        &alt(curs),
        r")\s?)?(\d+(?:\.\d+)?)(\s?)(",
        &run,
        r")((?:\s\d+(?:\.\d+)?\s?",
        &run,
        r")*)(?!\s?\d)",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        let (cur, num, rest) = (g(m, 1), g(m, 2), g(m, 5));
        let (ip, frac) = num.split_once('.').unwrap_or((num, ""));
        let simple =
            rest.is_empty() && frac.chars().count() == 1 && py_int(frac) == 5 && (1..=99).contains(&py_int(ip));
        let say = simple.then(|| half(py_int(ip)));
        if say.is_none() && !(!cur.is_empty() && (move_currency || !rest.is_empty())) {
            return None;
        }
        if !cur.is_empty() {
            let cw = currency_word(cur, lang).filter(|s| !s.is_empty())?;
            return Some(format!("{} {}{rest} {cw}", say.as_deref().unwrap_or(num), g(m, 4)));
        }
        Some(format!("{}{}{}", say.unwrap_or_default(), g(m, 3), g(m, 4)))
    })
}

/// 1 -> `one`, 2 -> `two`, N -> `more` + `sep` + N (डेढ़, ढाई, साढ़े N).
pub(super) fn halves(n: u128, lang: &str, one: &str, two: &str, more: &str, sep: &str) -> String {
    match n {
        1 => one.to_string(),
        2 => two.to_string(),
        _ => format!("{more}{sep}{}", words(&n.to_string(), lang)),
    }
}

// --------------------------------------------------------------------------- regnal numerals

const ROMAN_1_10: [&str; 10] = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];

/// `महारानी एलिज़ाबेथ II` -> `महारानी एलिज़ाबेथ द्वितीय`: a Roman I–X after a royal or papal title and one or two
/// name words is the ruler's ordinal.
pub(super) fn regnal(t: String, c: &mut Ctx, w: &str, titles: &[&str], stop: &[&str], ordinals: &[&str]) -> String {
    let name = ["(?:", w, r"+|[A-Z][a-z]+)"].concat();
    let mut roman = ROMAN_1_10.to_vec();
    roman.sort_by_key(|k| std::cmp::Reverse(k.len()));
    let pat = [
        "((?<!",
        w,
        ")(?:",
        &alt(titles),
        r")(?:\s(?!(?:",
        &alt(stop),
        ")(?!",
        w,
        "))",
        &name,
        r"){1,2}\s)(",
        &roman.join("|"),
        r")(?![\w\-]|\.\w)",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        let i = ROMAN_1_10.iter().position(|&r| r == g(m, 2))?;
        Some(format!("{}{}", g(m, 1), ordinals[i]))
    })
}

// --------------------------------------------------------------------------- numbers glued to a postposition

/// `2024में` -> `2024 में`: a 4+ digit, grouped or decimal number glued to a postposition that the grammar reads
/// digit by digit (or not at all: its reading of the glued form does not start with its reading of the number) gets
/// a space before the postposition (`hyphen`: also `2024-এ`).
pub(super) fn glued(t: String, c: &mut Ctx, lang: &str, w: &str, postpositions: &[&str], hyphen: bool) -> String {
    let pat = [
        r"(?<![\w.,:/\-–])(\d{4,}(?:[.,]\d+)*|\d{1,3}(?:[.,]\d+)+)",
        if hyphen { "-?" } else { "" },
        "(",
        &alt(postpositions),
        ")(?!",
        w,
        ")",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        (!words(&m[0], lang).starts_with(&words(g(m, 1), lang))).then(|| format!("{} {}", g(m, 1), g(m, 2)))
    })
}

// ================================================================================================= hi

const HI_POST: &[&str] = &["में", "का", "की", "के", "को", "से", "तक", "पर", "ने"];

fn hi_glued(t: String, c: &mut Ctx) -> String {
    glued(t, c, "hi", DEVA, HI_POST, false)
}

fn hi_iso_date(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&[NOT_NUM_BEFORE, r"(\d{4})([/\-])(\d{1,2})\2(\d{1,2})(?!\d|[.,:/\-–]\d)"].concat()), &t, |m| {
        if !((1..=12).contains(&py_int(g(m, 3))) && (1..=31).contains(&py_int(g(m, 4)))) {
            return None;
        }
        Some(format!("{}{}{}{}{}", g(m, 4), g(m, 2), g(m, 3), g(m, 2), g(m, 1)))
    })
}

fn hi_ampm(t: String, c: &mut Ctx) -> String {
    ampm(t, c, "ए एम", "पी एम", true)
}

fn hi_clock(t: String, c: &mut Ctx) -> String {
    clock_hourword(
        t,
        c,
        "hi",
        DEVA,
        &["बजे"],
        &["तक", "से", "के", "की", "का", "को", "पर", "में", "है", "हैं", "था", "थे", "थी"],
        None,
        &|r, w, a| absorb_postposition(r, w, a, "मिनट", "बजे", "पर"),
    )
}

fn hi_minus(t: String, c: &mut Ctx) -> String {
    minus(
        t,
        c,
        "माइनस",
        DEVA,
        &[
            "डिग्री",
            "किलो",
            "किलोग्राम",
            "किग्रा",
            "ग्राम",
            "मीटर",
            "किमी",
            "किलोमीटर",
            "सेमी",
            "मिमी",
            "लीटर",
            "रुपये",
            "रुपए",
            "प्रतिशत",
            "फ़ीसदी",
            "फीसदी",
            "अंक",
        ],
        &["तापमान", "पारा", "पारे"],
        &["से"],
    )
}

fn hi_latin_number(t: String, c: &mut Ctx) -> String {
    latin_number(t, c, ACRONYMS, &[("T20", "टी ट्वेंटी"), ("T-20", "टी ट्वेंटी")])
}

fn hi_score(t: String, c: &mut Ctx) -> String {
    score(
        t,
        c,
        "hi",
        DEVA,
        &["से", "की"],
        &["जीत", "हार", "हरा", "मात", "ड्रॉ", "ड्रा", "बढ़त", "बराबर", "शिकस्त", "पराजित", "आगे", "पीछे"],
    )
}

fn hi_range(t: String, c: &mut Ctx) -> String {
    ranges(t, c, DEVA, "से", &["से", "तक", "को", "का", "की", "के", "में", "पर", "ने", "है", "हैं", "था", "थी", "थे", "और", "या"])
}

fn hi_half_scale(t: String, c: &mut Ctx) -> String {
    half_scale(
        t,
        c,
        "hi",
        DEVA,
        &["लाख", "करोड़", "हज़ार", "हजार", "अरब", "खरब"],
        &["₹", "Rs.", "Rs", "INR"],
        &|n| halves(n, "hi", "डेढ़", "ढाई", "साढ़े", " "),
        false,
    )
}

const HI_UNITS: &[(&str, &str)] = &[
    ("किमी/घंटा", "km/h"),
    ("किमी/घं.", "km/h"),
    ("किमी/घं", "km/h"),
    ("किमी", "km"),
    ("कि.मी.", "km"),
    ("कि॰मी॰", "km"),
    ("सेमी", "cm"),
    ("से.मी.", "cm"),
    ("सें.मी.", "cm"),
    ("मिमी", "mm"),
    ("मि.मी.", "mm"),
    ("किग्रा", "kg"),
    ("कि.ग्रा.", "kg"),
    ("मि.ली.", "ml"),
];

fn hi_units(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = HI_UNITS.iter().map(|&(k, _)| k).collect();
    c.sub(&rx(&[r"(?<=\d)(\s?)(", &alt(&keys), r")(?![\w/]|", DEVA, ")"].concat()), &t, |m| {
        HI_UNITS.iter().find(|&&(k, _)| k == g(m, 2)).map(|&(_, v)| format!("{}{v}", g(m, 1)))
    })
}

pub(super) const SANSKRIT_ORD: &[&str] =
    &["प्रथम", "द्वितीय", "तृतीय", "चतुर्थ", "पंचम", "षष्ठ", "सप्तम", "अष्टम", "नवम", "दशम"];

fn hi_regnal(t: String, c: &mut Ctx) -> String {
    regnal(
        t,
        c,
        DEVA,
        &[
            "महारानी",
            "रानी",
            "राजा",
            "महाराजा",
            "महाराज",
            "सम्राट",
            "सम्राज्ञी",
            "पोप",
            "किंग",
            "क्वीन",
            "प्रिंस",
            "राजकुमार",
            "राजकुमारी",
            "ज़ार",
            "सुल्तान",
            "शाह",
            "बादशाह",
            "नवाब",
            "कैसर",
        ],
        &["ने", "का", "की", "के", "को", "से", "में", "पर", "और", "है", "था"],
        SANSKRIT_ORD,
    )
}
