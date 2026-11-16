//! 'da' rules: the port of the workbench's `langrules/da.py` (ids `da.*`).
//!
//! The year rule's logic ([`nordic_year`]), [`abbrev_rule`] and [`prev_words`] are shared with `nb.rs` and `sv.rs`,
//! each with its own tables.

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

use fancy_regex::Captures;

use super::super::{Ctx, g, matches_at_start, py_int, rx};
use super::{LangRule, words};

pub(super) const RULES: &[LangRule] = &[
    ("da.dash-price", da_dash_price),
    ("da.money-groups", da_money_groups),
    ("da.scale", da_scale),
    ("da.units", da_units),
    ("da.abbrev", da_abbrev),
    ("da.time", da_time),
    ("da.date", da_date),
    ("da.decade", da_decade),
    ("da.year", da_year),
];

const MONTHS: [&str; 12] = [
    "januar",
    "februar",
    "marts",
    "april",
    "maj",
    "juni",
    "juli",
    "august",
    "september",
    "oktober",
    "november",
    "december",
];

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.start())
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

pub(super) fn set(words: &'static str) -> HashSet<&'static str> {
    words.split_whitespace().collect()
}

/// `s[0].upper() + s[1:]`.
fn cap(s: &str) -> String {
    let mut it = s.chars();
    match it.next() {
        Some(f) => f.to_uppercase().collect::<String>() + it.as_str(),
        None => String::new(),
    }
}

/// Up to two words before a position, nearest first, without quotes or brackets around them; '' stands for a
/// sentence start (the text start, a line break, or a token ending in . ! ? :), after which nothing is looked at.
pub(super) fn prev_words(head: &str) -> Vec<String> {
    let mut out = Vec::new();
    let h = head.replace('\n', " \n ");
    for tok in h.split(' ').rev() {
        if out.len() == 2 {
            return out;
        }
        if tok.is_empty() {
            continue;
        }
        if tok == "\n" || tok.ends_with(['.', '!', '?', ':']) {
            out.push(String::new());
            return out;
        }
        out.push(tok.trim_matches(|ch| "(„\"'»«“”".contains(ch)).to_string());
    }
    out.push(String::new());
    out
}

/// 'f. eks.' -> '[fF]\.\s?eks\.': the parts with or without the space, the first letter in either case.
fn abbrev_pattern(a: &str) -> String {
    let parts: Vec<&str> = a.split('.').map(str::trim).filter(|p| !p.is_empty()).collect();
    let mut chars = parts[0].chars();
    let f = chars.next().expect("a part");
    let lead = format!("[{}{}]{}", f.to_lowercase(), f.to_uppercase(), chars.as_str());
    let mut ps = vec![lead];
    ps.extend(parts[1..].iter().map(|p| p.to_string()));
    format!(r"{}\.", ps.join(r"\.\s?"))
}

/// Expands the abbreviations of `table` [(written, spoken)]: as a whole word, with or without the spaces, the first
/// letter in either case (a capitalised one gives a capitalised expansion); the period stays as a sentence end at
/// the end of the text or a line. A written form in `keep` is left to the grammar (it reads it).
pub(super) fn abbrev_rule(t: String, c: &mut Ctx, table: &[(&str, &str)], keep: &[&str]) -> String {
    let keys: HashMap<String, &str> = table.iter().map(|&(a, w)| (a.replace(' ', ""), w)).collect();
    let mut sorted: Vec<&(&str, &str)> = table.iter().collect();
    sorted.sort_by_key(|x| std::cmp::Reverse(x.0.replace(' ', "").chars().count()));
    let alt: Vec<String> = sorted.iter().map(|x| abbrev_pattern(x.0)).collect();
    let p = format!(r"(?<![\w.])({})(?!\w)", alt.join("|"));
    c.sub(&rx(&p), &t, |m| {
        let s = g(m, 1);
        if keep.contains(&s) {
            return None;
        }
        let mut key = s.replace(' ', "");
        if !keys.contains_key(&key) {
            let mut it = key.chars();
            key = match it.next() {
                Some(f) => f.to_lowercase().collect::<String>() + it.as_str(),
                None => String::new(),
            };
        }
        let spoken = *keys.get(&key)?;
        let spoken = if s.chars().next().is_some_and(char::is_uppercase) { cap(spoken) } else { spoken.to_string() };
        let dot = if matches_at_start(r"[ \t]*(?:\n|$)", &t[end(m)..]) { "." } else { "" };
        Some(format!("{spoken}{dot}"))
    })
}

/// Group `i` of `re.match(pat, s)` (anchored at the start), if it matches.
fn group_at_start(pat: &str, s: &str, i: usize) -> Option<String> {
    match rx(&format!("^(?:{pat})")).captures(s) {
        Ok(Some(m)) => Some(g(&m, i).to_string()),
        _ => None,
    }
}

/// The tables of a language's year rule (see [`nordic_year`]).
pub(super) struct YearCues {
    pub say: fn(u128) -> String,
    pub strong: &'static LazyLock<HashSet<&'static str>>,
    pub weak: &'static LazyLock<HashSet<&'static str>>,
    pub amount: &'static LazyLock<HashSet<&'static str>>,
    pub after_ok: &'static LazyLock<HashSet<&'static str>>,
    pub not_after: &'static LazyLock<HashSet<&'static str>>,
    pub span_words: &'static str,
    pub to_word: &'static str,
}

/// The year rule of da/nb/sv: a 4-digit 1100-1999 is said as a year (say(y)) after a year word (strong); after a
/// preposition (weak) before the end, punctuation, a capitalised name, a word of after_ok, or (the preposition
/// starting the sentence, so the verb follows) any word not in not_after; after a verb (a lowercase word not in
/// amount) before the end; at a sentence start before a word of after_ok. Two years joined by a span word or a dash
/// (1939 til 1945, 1939–1945; the dash said as to_word) are both years unless an amount word comes before. Never
/// before a unit, a currency or a word of not_after (år, kr, personer …); a number standing alone as a sentence
/// stays a cardinal.
pub(super) fn nordic_year(t: String, c: &mut Ctx, k: &YearCues) -> String {
    let p = format!(
        r"(?<![\w.,:/–-])(1[1-9]\d\d)(?:(\s+(?:{})\s+| ?[–-] ?)(1[1-9]\d\d))?(?![\w]|[.,:/]\d|[–-]\d)",
        k.span_words
    );
    c.sub(&rx(&p), &t, |m| {
        let (head, rest) = (&t[..start(m)], &t[end(m)..]);
        let pw = prev_words(head);
        let raw = &pw[0];
        let p = raw.to_lowercase();
        if matches_at_start(r"\s?[%€$£°/‰]", rest) {
            return None;
        }
        let nxt = group_at_start(r"\s+([a-zæøåäöé]+)(?![\w/²³])", rest, 1).unwrap_or_default();
        if k.not_after.contains(nxt.as_str()) {
            return None;
        }
        let (y, sep, y2) = (py_int(g(m, 1)), g(m, 2), g(m, 3));
        if !y2.is_empty() {
            if k.amount.contains(p.as_str()) {
                return None;
            }
            let joint = if ["–", "-"].contains(&sep.trim()) { format!(" {} ", k.to_word) } else { sep.to_string() };
            return Some(format!("{}{joint}{}", (k.say)(y), (k.say)(py_int(y2))));
        }
        if k.strong.contains(p.as_str()) {
            return Some((k.say)(y));
        }
        let at_end = matches_at_start(r#"\s*(?:$|[.,;:!?)\]"»”])"#, rest);
        let capital = matches_at_start(r"\s+[A-ZÆØÅÄÖ]", rest);
        if k.weak.contains(p.as_str()) {
            let initial = pw.len() > 1 && pw[1].is_empty();
            if at_end || capital || k.after_ok.contains(nxt.as_str()) || (initial && !nxt.is_empty()) {
                return Some((k.say)(y));
            }
            return None;
        }
        if p.is_empty() {
            // a number alone is a count as often as a year
            return k.after_ok.contains(nxt.as_str()).then(|| (k.say)(y));
        }
        let is_alpha = raw.chars().all(char::is_alphabetic);
        let is_lower = raw.chars().any(char::is_lowercase) && !raw.chars().any(char::is_uppercase);
        if is_alpha && is_lower && !k.amount.contains(p.as_str()) && at_end {
            return Some((k.say)(y));
        }
        None
    })
}

/// 1864 -> 'atten hundrede og fireogtres', 1900 -> 'nitten hundrede'.
fn da_year_words(y: u128) -> String {
    let out = format!("{} hundrede", words(&(y / 100).to_string(), "da"));
    if !y.is_multiple_of(100) { format!("{out} og {}", words(&(y % 100).to_string(), "da")) } else { out }
}

// ------------------------------------------------------------------------------------------------- prices (S12, S04)

fn da_dash_price(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(\d),(?:--?|–|—)(?![\w])"), &t, r"\1")
}

fn da_money_groups(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<!\w)(kr\.?|DKK|€) ?([1-9]\d{0,2}(?:\.\d{3})+)(?=(?:,\d\d)?(?![\w.]|,\d))"), &t, |m| {
        Some(format!("{} {}", g(m, 1), g(m, 2).replace('.', "")))
    });
    c.sub(&rx(r"(?<![\w.,])([1-9]\d{0,2}(?:\.\d{3})+)(?=(?:,\d\d)? ?(?:kr\b|kroner\b|DKK\b|€|euro\b))"), &t, |m| {
        Some(g(m, 1).replace('.', ""))
    })
}

fn da_scale(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<![\w.,])(\d+(?:,\d+)?) ?mill(?:\.|(?![\w-]))"), &t, r"\1 mio.");
    c.sub(&rx(r"(?<![\w.,])(\d+) ?(?:mdr|mnd)(?:\.|(?![\w-]))"), &t, |m| {
        Some(format!("{}{}", g(m, 1), if g(m, 1) == "1" { " måned" } else { " måneder" }))
    })
}

fn da_units(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(\d ?)kvm\b\.?"), &t, r"\1m²");
    c.sub(&rx(r"(\d ?)(km|dm|cm|mm|m)([23])(?![\w²³/])"), &t, |m| {
        Some(format!("{}{}{}", g(m, 1), g(m, 2), if g(m, 3) == "2" { "²" } else { "³" }))
    })
}

const DA_ABBREV: [(&str, &str); 9] = [
    ("evt.", "eventuelt"),
    ("mht.", "med hensyn til"),
    ("ift.", "i forhold til"),
    ("iflg.", "ifølge"),
    ("inkl.", "inklusive"),
    ("ekskl.", "eksklusive"),
    ("vha.", "ved hjælp af"),
    ("mv.", "med videre"),
    ("ifm.", "i forbindelse med"),
];

fn da_abbrev(t: String, c: &mut Ctx) -> String {
    abbrev_rule(t, c, &DA_ABBREV, &[])
}

// ----------------------------------------------------------------------------------------------------- times (S09)

fn hm(h: &str, mm: &str) -> String {
    if mm == "00" { h.to_string() } else { format!("{h}:{mm}") }
}

fn da_time(t: String, c: &mut Ctx) -> String {
    let p = r"\b([Kk]l\.?|[Kk]lokken) (\d{1,2})[.:]([0-5]\d)(?:\s?[–-]\s?(\d{1,2})[.:]([0-5]\d))?(?![\d]|[.,:]\d)";
    c.sub(&rx(p), &t, |m| {
        if py_int(g(m, 2)) > 24 || (!g(m, 4).is_empty() && py_int(g(m, 4)) > 24) {
            return None;
        }
        let mut out = format!("{} {}", g(m, 1), hm(g(m, 2), g(m, 3)));
        if !g(m, 4).is_empty() {
            out = format!("{out}-{}", hm(g(m, 4), g(m, 5)));
        }
        Some(out)
    })
}

// ------------------------------------------------------------------------------------------- dates, years (S07, S10)

fn da_date(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,/-])(\d{1,2})([./-])(\d{1,2})\2(1[1-9]\d\d)(?![\w]|[.,/-]\d)"), &t, |m| {
        let (d, mo) = (py_int(g(m, 1)), py_int(g(m, 3)));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) {
            return None;
        }
        Some(format!("{d}. {} {}", MONTHS[(mo - 1) as usize], g(m, 4)))
    })
}

fn da_decade_word(n: &str) -> &'static str {
    match n {
        "00" => "nullerne",
        "20" => "tyverne",
        "30" => "trediverne",
        "40" => "fyrrerne",
        "50" => "halvtredserne",
        "60" => "tresserne",
        "70" => "halvfjerdserne",
        "80" => "firserne",
        _ => "halvfemserne",
    }
}

fn da_decade(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,'’])(00|[2-9]0)['’]?erne\b"), &t, |m| Some(da_decade_word(g(m, 1)).to_string()));
    c.sub(&rx(r"(?<![\w.,])(1[1-9])00-tal(let|lets)\b"), &t, |m| {
        Some(format!("{}hundredetal{}", words(g(m, 1), "da"), g(m, 2)))
    })
}

static DA_YEAR_STRONG: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("år året anno januar februar marts april maj juni juli august september oktober november december jan feb \
         mar apr jun jul aug sep sept okt nov dec")
});
static DA_YEAR_WEAK: LazyLock<HashSet<&str>> =
    LazyLock::new(|| set("i fra til siden før efter omkring ved indtil mellem og eller inden frem"));
static DA_AMOUNT: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("koster kostede betaler betalte betalt har havde ca cirka over under mere end kun næsten knap godt nummer nr \
         side værelse plus minus vejer tæller på med af alle")
});
static DA_AFTER_OK: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("i og til på med for da men eller som efter før blev var er har havde kom fik gik under ved fra hvor tabte \
         vandt døde startede begyndte sluttede åbnede lukkede flyttede udkom skete fødtes opstod fandt kunne skulle \
         ville måtte boede levede")
});
static DA_NOT_AFTER: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("år års dage dag timer time minutter sekunder uger måneder meter m km kilometer kg kilo gram g liter l kr \
         kroner euro dollar procent personer mennesker stk gange styk sider ord elever indbyggere ansatte medlemmer \
         deltagere biler huse point mål kalorier kcal mio mia millioner milliarder tusind hundrede børn voksne \
         studerende soldater")
});

static DA_CUES: YearCues = YearCues {
    say: da_year_words,
    strong: &DA_YEAR_STRONG,
    weak: &DA_YEAR_WEAK,
    amount: &DA_AMOUNT,
    after_ok: &DA_AFTER_OK,
    not_after: &DA_NOT_AFTER,
    span_words: "og|til|eller",
    to_word: "til",
};

fn da_year(t: String, c: &mut Ctx) -> String {
    nordic_year(t, c, &DA_CUES)
}
