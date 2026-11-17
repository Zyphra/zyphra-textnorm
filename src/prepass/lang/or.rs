//! 'or' rules: the port of the workbench's `langrules/or.py` (ids `or.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, search, tpl};
use super::hi::{ACRONYMS, ORYA, alt, ampm, half_scale, halves, has_digit, latin_number, minus, score, years};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("or.big", or_big),
    ("or.money-range", or_money_range),
    ("or.money", or_money),
    ("or.per", or_per),
    ("or.units", or_units),
    ("or.classifier-case", or_classifier_case),
    ("or.glued", or_glued),
    ("or.year", or_year),
    ("or.ampm", or_ampm),
    ("or.score", or_score),
    ("or.minus", or_minus),
    ("or.latin-number", or_latin_number),
    ("or.half-scale", or_half_scale),
];

/// Currency signs and codes the grammar reads (before or after the amount), and what may stand for the rupee.
const OR_SIGN: &str = r"(?:[₹€$£] ?|(?<![A-Za-z])(?:Rs\.|Rs|INR|USD|EUR|GBP)(?![A-Za-z]) ?)";
const OR_CUR_AFTER: &str = r"(?:[₹€$£]|(?:INR|USD|EUR|GBP)(?![A-Za-z]))";
const OR_AMOUNT: &str = r"\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?";
/// Not 2.5 କୋଟି (or.half-scale) or ₹2.5M.
const OR_SCALE: &str = r"(?! ?(?:ଲକ୍ଷ|କୋଟି|ହଜାର|ଶହ|ଅରବ|ଖରବ|[A-Za-z]))";
/// Codes the grammar leaves unread: the currency words and the minor unit.
const OR_CODES: &[(&str, &str, &str)] = &[
    ("HKD", "ହଂକଂ ଡଲାର୍", "ସେଣ୍ଟ"),
    ("SGD", "ସିଙ୍ଗାପୁର ଡଲାର୍", "ସେଣ୍ଟ"),
    ("NZD", "ନ୍ୟୁଜିଲାଣ୍ଡ ଡଲାର୍", "ସେଣ୍ଟ"),
    ("NPR", "ନେପାଳୀ ଟଙ୍କା", "ପଇସା"),
    ("PKR", "ପାକିସ୍ତାନୀ ଟଙ୍କା", "ପଇସା"),
    ("LKR", "ଶ୍ରୀଲଙ୍କା ଟଙ୍କା", "ସେଣ୍ଟ"),
    ("CNY", "ଚାଇନିଜ୍ ୟୁଆନ୍", ""),
    ("AED", "ଦିରହାମ୍", ""),
    ("SAR", "ସାଉଦି ରିୟାଲ୍", ""),
    ("MYR", "ମାଲେସିଆନ୍ ରିଙ୍ଗିଟ୍", ""),
];
const OR_CODE_ALT: &str = "HKD|SGD|NZD|NPR|PKR|LKR|CNY|AED|SAR|MYR";

/// The grammar leaves part of `s` unread or misreads it (a sign, a code, a digit, a dash, ~ or a slash is left).
fn or_wrong(s: &str) -> bool {
    search(r"[₹€$£¥~～\-–—/0-9A-Za-z]", &words(s, "or"))
}

fn num(x: &str) -> f64 {
    x.replace(',', "").parse::<f64>().unwrap_or(0.0)
}

/// The grammar's word for a currency sign or code next to an amount (₹ → ଟଙ୍କା, € → ୟୁରୋ, $ → ଡଲାର୍).
fn or_cur_word(cur: &str, after: bool) -> String {
    let base = words("1000", "or");
    let said = words(&if after { format!("1000 {cur}") } else { format!("{cur}1000") }, "or");
    said.strip_prefix(base.as_str()).map_or(String::new(), |r| r.trim_matches(crate::text::is_py_space).to_string())
}

fn or_big(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?:(?<![\w.,)\]])(-))?(?<![\w.,])(?:([₹€$£]) ?|(?<![A-Za-z])(Rs\.|Rs|INR|USD|EUR|GBP) ?)?([1-9]\d{0,2}",
        r"(?:[, \x{A0}\x{202F}]\d{3}){4}|[1-9]\d{13,14})(?![\d,]|\.\d|[ \x{A0}\x{202F}]\d)(?: ?([₹€$£]|(?:INR|USD|EUR|GBP)",
        r"(?![A-Za-z])))?"
    );
    c.sub(&rx(pat), &t, |m| {
        let digits: String = g(m, 4)
            .chars()
            .filter(|ch| ch.is_ascii_digit() || !matches!(ch, ',' | ' ' | '\u{a0}' | '\u{202f}'))
            .collect();
        let n = py_int(&digits);
        if !(10u128.pow(13)..10u128.pow(16)).contains(&n) {
            return None;
        }
        let (k, rest) = (n / 10u128.pow(11), n % 10u128.pow(11));
        let mut out = format!("{} ଖରବ", words(&k.to_string(), "or"));
        if rest != 0 {
            out = format!("{out} {}", words(&rest.to_string(), "or"));
        }
        let cur = [g(m, 2), g(m, 3), g(m, 5)].into_iter().find(|x| !x.is_empty()).unwrap_or("");
        if !cur.is_empty() {
            out = format!("{out} {}", or_cur_word(cur.trim(), !g(m, 5).is_empty()));
        }
        Some(format!("{}{out}", if g(m, 1).is_empty() { "" } else { "ମାଇନସ " }))
    })
}

fn or_money_range(t: String, c: &mut Ctx) -> String {
    let pat =
        format!(r"(?<![\w.,])({OR_SIGN})({OR_AMOUNT}) ?[-–—~～〜] ?({OR_SIGN})?({OR_AMOUNT})(?![\d.,]\d|\d){OR_SCALE}");
    let t = c.sub(&rx(&pat), &t, |m| {
        if num(g(m, 2)) >= num(g(m, 4)) || !or_wrong(&m[0]) {
            return None;
        }
        let sg = g(m, 1).trim();
        let space = sg.chars().next_back().is_some_and(|ch| ch.is_alphabetic()) || sg.ends_with('.');
        Some(format!("{} ରୁ {sg}{}{}", g(m, 2), if space { " " } else { "" }, g(m, 4)))
    });
    let pat = format!(r"(?<![\w.,\-–—~～〜])({OR_AMOUNT}) ?[-–—~～〜] ?({OR_AMOUNT}) ?({OR_CUR_AFTER}|ଟଙ୍କା)");
    c.sub(&rx(&pat), &t, |m| {
        if num(g(m, 1)) >= num(g(m, 2)) || !or_wrong(&m[0]) {
            return None;
        }
        Some(format!("{} ରୁ {} {}", g(m, 1), g(m, 2), g(m, 3)))
    })
}

fn or_money(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,])({OR_SIGN}\d{{1,3}}(?:,\d{{2,3}})+|{OR_SIGN}\d+)\.(\d)(?![\d.,]\d|\d){OR_SCALE}");
    let t = c.sub(&rx(&pat), &t, |m| Some(format!("{}.{}0", g(m, 1), g(m, 2))));
    let pat = format!(
        r"(?<![\w.,])(?<!\d[\-–—~～〜])(?<!\d [\-–—~～〜])(\d{{1,3}}(?:,\d{{2,3}})+|\d+)\.(\d)( ?{OR_CUR_AFTER})"
    );
    let t = c.sub(&rx(&pat), &t, |m| Some(format!("{}.{}0{}", g(m, 1), g(m, 2), g(m, 3))));
    let pat = format!(
        r"(?<![\w.,])(?:({OR_CODE_ALT}) ?({OR_AMOUNT})(?![\d.,]\d|\d)|({OR_AMOUNT}) ?({OR_CODE_ALT}))(?![A-Za-z])"
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        let amount = if g(m, 2).is_empty() { g(m, 3) } else { g(m, 2) };
        let cur = if g(m, 1).is_empty() { g(m, 4) } else { g(m, 1) };
        let &(_, word, minor) = OR_CODES.iter().find(|x| x.0 == cur)?;
        let (head, dec) = amount.split_once('.').unwrap_or((amount, ""));
        if !dec.is_empty() && !minor.is_empty() {
            let d: String = format!("{dec}0").chars().take(2).collect();
            let cents = py_int(&d);
            return Some(format!(
                "{head} {word}{}",
                if cents != 0 { format!(" {cents} {minor}") } else { String::new() }
            ));
        }
        Some(format!("{amount} {word}"))
    });
    c.sub(&rx(r"(?<![\w.,)\]\-−+*/=^])[-−](?=[₹€$£]\s?\d)"), &t, |_| Some("ମାଇନସ ".to_string()))
}

const OR_PER_UNITS: &[(&str, &str)] =
    &[("kg", "କିଲୋଗ୍ରାମ୍"), ("km", "କିଲୋମିଟର"), ("m²", "ବର୍ଗ ମିଟର"), ("m", "ମିଟର"), ("L", "ଲିଟର"), ("g", "ଗ୍ରାମ")];

fn or_per(t: String, c: &mut Ctx) -> String {
    let money = format!(r"(?<![\w.,])({OR_SIGN}(?:{OR_AMOUNT})|(?:{OR_AMOUNT}) ?(?:{OR_CUR_AFTER}|ଟଙ୍କା))");
    let pat = format!(r"{money} ?/ ?(m²|[^\W\d_]+)(?![\w²³])");
    c.sub(&rx(&pat), &t, |m| {
        if !words(&m[0], "or").contains('/') {
            return None;
        }
        let unit = OR_PER_UNITS.iter().find(|(k, _)| *k == g(m, 2)).map_or(g(m, 2), |(_, v)| *v);
        Some(format!("{} ପ୍ରତି {unit}", g(m, 1)))
    })
}

fn or_units(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<=\d)( ?)(ha|t)(?![A-Za-z0-9²³/])"), &t, |m| {
        let unit = if g(m, 2) == "t" { "ଟନ" } else { "ହେକ୍ଟର" };
        Some(format!("{}{unit}", if g(m, 1).is_empty() { " " } else { g(m, 1) }))
    })
}

const MONTHS: &[&str] = &[
    "ଜାନୁଆରୀ",
    "ଜାନୁୟାରୀ",
    "ଫେବୃଆରୀ",
    "ଫେବ୍ରୁଆରୀ",
    "ମାର୍ଚ୍ଚ",
    "ମାର୍ଚ",
    "ଅପ୍ରେଲ",
    "ଏପ୍ରିଲ",
    "ମଇ",
    "ମେ",
    "ଜୁନ",
    "ଜୁଲାଇ",
    "ଅଗଷ୍ଟ",
    "ସେପ୍ଟେମ୍ବର",
    "ଅକ୍ଟୋବର",
    "ନଭେମ୍ବର",
    "ଡିସେମ୍ବର",
];

const CLASSIFIERS: &[&str] = &["ଟା", "ଟି", "ଜଣ", "ମ", "ୟ", "ର୍ଥ", "ଷ୍ଠ", "ତମ"];
const CASE: &[&str] = &["ରେ", "ରୁ", "କୁ", "ର", "ଠାରୁ", "ଠୁ", "ଙ୍କୁ", "ଙ୍କର", "ଙ୍କ", "ପାଇଁ"];

fn or_classifier_case(t: String, c: &mut Ctx) -> String {
    let pat = [r"(?<![\w.,:/\-–])(\d+)(", &alt(CLASSIFIERS), ")(", &alt(CASE), ")(?!", ORYA, ")"].concat();
    c.sub(&rx(&pat), &t, |m| {
        let said = words(&format!("{}{}", g(m, 1), g(m, 2)), "or");
        if !said.ends_with(g(m, 2)) || has_digit(&said) {
            return None;
        }
        Some(format!("{said}{}", g(m, 3)))
    })
}

fn or_glued(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&[r"(?<![\w.,:/\-–])(\d+(?:[.,:]\d+)*%?)(", ORYA, "+)"].concat()), &t, |m| {
        has_digit(&words(&m[0], "or")).then(|| format!("{} {}", g(m, 1), g(m, 2)))
    })
}

fn or_year(t: String, c: &mut Ctx) -> String {
    years(t, c, "or", ORYA, " ଶହ", &["ସନ", "ସାଲ"], &["ରେ", "ରୁ"], &["ମସିହା", "ଖ୍ରୀଷ୍ଟାବ୍ଦ", "ସାଲ"], MONTHS)
}

fn or_ampm(t: String, c: &mut Ctx) -> String {
    ampm(t, c, "ଏ ଏମ", "ପି ଏମ", true)
}

fn or_minus(t: String, c: &mut Ctx) -> String {
    minus(
        t,
        c,
        "ମାଇନସ",
        ORYA,
        &["ଡିଗ୍ରୀ", "ଡିଗ୍ରି", "କିଲୋ", "କିଲୋଗ୍ରାମ", "ଗ୍ରାମ", "ମିଟର", "କିମି", "କିଲୋମିଟର", "ଲିଟର", "ଟଙ୍କା", "ପ୍ରତିଶତ"],
        &["ତାପମାତ୍ରା", "ପାରଦ"],
        &["ରୁ"],
    )
}

fn or_latin_number(t: String, c: &mut Ctx) -> String {
    latin_number(t, c, ACRONYMS, &[("T20", "ଟି ଟ୍ୱେଣ୍ଟି"), ("T-20", "ଟି ଟ୍ୱେଣ୍ଟି")])
}

fn or_half_scale(t: String, c: &mut Ctx) -> String {
    half_scale(
        t,
        c,
        "or",
        ORYA,
        &["ଲକ୍ଷ", "କୋଟି", "ହଜାର"],
        &["₹", "Rs.", "Rs", "INR"],
        &|n| halves(n, "or", "ଦେଢ଼", "ଅଢ଼େଇ", "ସାଢ଼େ", " "),
        false,
    )
}

fn or_score(t: String, c: &mut Ctx) -> String {
    score(t, c, "or", ORYA, &["ଗୋଲରେ", "ବ୍ୟବଧାନରେ"], &[])
}
