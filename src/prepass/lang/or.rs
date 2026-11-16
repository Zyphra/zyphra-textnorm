//! 'or' rules: the port of the workbench's `langrules/or.py` (ids `or.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
use super::hi::{ACRONYMS, ORYA, alt, ampm, half_scale, halves, has_digit, latin_number, minus, score, years};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("or.classifier-case", or_classifier_case),
    ("or.glued", or_glued),
    ("or.year", or_year),
    ("or.ampm", or_ampm),
    ("or.score", or_score),
    ("or.minus", or_minus),
    ("or.latin-number", or_latin_number),
    ("or.half-scale", or_half_scale),
];

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
