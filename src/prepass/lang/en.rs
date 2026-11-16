//! 'en' rules: the port of the workbench's `langrules/en.py` (ids `en.*`). They run before the pre-pass's own
//! English rules (en.footnote … en.acronym-plural), right after the character rules.

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, g, matches_at_start, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] =
    &[("en.score", en_score), ("en.money-scale-t", en_money_scale_t), ("en.money-code", en_money_code)];

const SCORE_CUES: &str = r"(?i)\b(?:beat|beats|beating|won|win|wins|winning|lost|lose|loses|losing|defeated|defeats|defeating|edged|edges|edging|routed|thrashed|trounced|crushed|downed|drew|tied|ties|led|leads|leading|trailed|trails|trailing|scored?|scores|final|victory|defeat|loss|win)\b";
/// prepass.py's DETERMINERS (src/prepass/rules.rs).
const DETERMINERS: &str = "(?:a|an|the|this|that|each|every|one|its|his|her|their|our|my|your|whose)";

fn en_score(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,/:\-–])(\d{1,3})[-–](\d{1,3})(?![\w\-–]|[.,:]\d)"), &t, |m| {
        let w = m.get(0).expect("group 0");
        if !search(&format!(r"{SCORE_CUES}(?:\s+\S+){{0,3}}\s+$"), chars_before(&t, w.start(), 60)) {
            return None;
        }
        if matches_at_start(r"\s*=", &t[w.end()..]) {
            return None;
        }
        Some(format!("{} to {}", g(m, 1), g(m, 2)))
    })
}

fn en_money_scale_t(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\w.])([$€£¥]\d+(?:,\d{3})*(?:\.\d+)?) ?(?:T|tn|trn)(?![\w-])"), &t, r"\1 trillion")
}

/// code, symbol, plural name, singular name; a symbol alone means the grammar's own reading of the symbol is right.
const CODES: &[(&str, &str, &str, &str)] = &[
    ("USD", "$", "US dollars", "US dollar"),
    ("EUR", "€", "", ""),
    ("GBP", "£", "", ""),
    ("JPY", "¥", "", ""),
    ("INR", "₹", "", ""),
    ("CAD", "$", "Canadian dollars", "Canadian dollar"),
    ("AUD", "$", "Australian dollars", "Australian dollar"),
    ("NZD", "$", "New Zealand dollars", "New Zealand dollar"),
    ("HKD", "$", "Hong Kong dollars", "Hong Kong dollar"),
    ("SGD", "$", "Singapore dollars", "Singapore dollar"),
    ("CHF", "", "Swiss francs", "Swiss franc"),
    ("MXN", "", "Mexican pesos", "Mexican peso"),
    ("CNY", "", "yuan", "yuan"),
    ("RMB", "", "yuan", "yuan"),
];
const CODE_RX: &str = "USD|EUR|GBP|JPY|INR|CAD|AUD|NZD|HKD|SGD|CHF|MXN|CNY|RMB";
const AMOUNT: &str = r"\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?";

fn say_code(t: &str, start: usize, code: &str, amount: &str) -> Option<String> {
    let &(_, sym, pl, sg) = CODES.iter().find(|row| row.0 == code)?;
    let adjective = search(&format!(r"(?i)\b{DETERMINERS}\s+$"), &t[..start]);
    if !pl.is_empty() && !amount.contains('.') && !adjective {
        return Some(format!("{amount} {}", if amount == "1" { sg } else { pl }));
    }
    if sym.is_empty() { None } else { Some(format!("{sym}{amount}")) }
}

fn en_money_code(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w.$€£¥])({CODE_RX}) ?({AMOUNT})(?!\w|[.,]\d)")), &t, |m| {
        say_code(&t, m.get(0).expect("group 0").start(), g(m, 1), g(m, 2))
    });
    c.sub(&rx(&format!(r"(?<![\w.,$€£¥])({AMOUNT}) ?({CODE_RX})(?!\w)")), &t, |m| {
        say_code(&t, m.get(0).expect("group 0").start(), g(m, 2), g(m, 1))
    })
}
