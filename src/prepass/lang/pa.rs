//! 'pa' rules: the port of the workbench's `langrules/pa.py` (ids `pa.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
use super::hi::{
    ACRONYMS, GURU, absorb_postposition, alt, ampm, big, clock_hourword, codes, glued, half_scale, halves,
    latin_number, minus, money_minus, money_range, per_unit, quarters, ranges, score, space_groups, years,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("pa.space-groups", pa_space_groups),
    ("pa.big", pa_big),
    ("pa.glued", pa_glued),
    ("pa.year", pa_year),
    ("pa.ampm", pa_ampm),
    ("pa.score", pa_score),
    ("pa.clock-hourword", pa_clock),
    ("pa.money-range", pa_money_range),
    ("pa.minus", pa_minus),
    ("pa.latin-number", pa_latin_number),
    ("pa.range", pa_range),
    ("pa.per", pa_per),
    ("pa.codes", pa_codes),
    ("pa.half-scale", pa_half_scale),
    ("pa.units", pa_units),
];
const PA_SCALES: &[&str] = &["ਲੱਖ", "ਕਰੋੜ", "ਹਜ਼ਾਰ", "ਹਜਾਰ", "ਅਰਬ", "ਖਰਬ"];

fn pa_space_groups(t: String, c: &mut Ctx) -> String {
    space_groups(t, c)
}

fn pa_big(t: String, c: &mut Ctx) -> String {
    big(t, c, "pa", "ਮਾਈਨਸ")
}

fn pa_money_range(t: String, c: &mut Ctx) -> String {
    money_range(t, c, "pa", "ਤੋਂ", GURU, PA_SCALES)
}

fn pa_range(t: String, c: &mut Ctx) -> String {
    ranges(
        t,
        c,
        GURU,
        "ਤੋਂ",
        &["ਤੋਂ", "ਤੱਕ", "ਨੂੰ", "ਦਾ", "ਦੀ", "ਦੇ", "ਵਿੱਚ", "ਵਿਚ", "ਤੇ", "ਨੇ", "ਨਾਲ", "ਹੈ", "ਹਨ", "ਸੀ", "ਅਤੇ", "ਜਾਂ"],
        "[~～〜]",
    )
}

const PA_CODES: &[(&str, &str, &str)] = &[
    ("NPR", "ਨੇਪਾਲੀ ਰੁਪਏ", "ਪੈਸੇ"),
    ("LKR", "ਸ੍ਰੀਲੰਕਾਈ ਰੁਪਏ", "ਸੈਂਟ"),
    ("BDT", "ਬੰਗਲਾਦੇਸ਼ੀ ਟਕਾ", "ਪੈਸੇ"),
    ("Tk.", "ਬੰਗਲਾਦੇਸ਼ੀ ਟਕਾ", "ਪੈਸੇ"),
    ("Tk", "ਬੰਗਲਾਦੇਸ਼ੀ ਟਕਾ", "ਪੈਸੇ"),
    ("₨", "ਰੁਪਏ", "ਪੈਸੇ"),
    ("AED", "ਦਿਰਹਮ", ""),
    ("SAR", "ਸਾਊਦੀ ਰਿਆਲ", ""),
    ("HKD", "ਹਾਂਗ ਕਾਂਗ ਡਾਲਰ", "ਸੈਂਟ"),
    ("SGD", "ਸਿੰਗਾਪੁਰ ਡਾਲਰ", "ਸੈਂਟ"),
    ("MYR", "ਮਲੇਸ਼ੀਆਈ ਰਿੰਗਿਟ", "ਸੇਨ"),
    ("THB", "ਥਾਈ ਬਾਹਤ", "ਸਤਾਂਗ"),
];

fn pa_codes(t: String, c: &mut Ctx) -> String {
    codes(t, c, "pa", GURU, PA_CODES, PA_SCALES)
}

fn pa_per(t: String, c: &mut Ctx) -> String {
    per_unit(t, c, "pa", "ਪ੍ਰਤੀ", GURU, &["ਰੁਪਏ", "ਰੁਪਈਆ", "ਰੁਪਇਆ"])
}

const PA_UNITS: &[(&str, &str)] =
    &[("km²", "ਵਰਗ ਕਿਲੋਮੀਟਰ"), ("cm²", "ਵਰਗ ਸੈਂਟੀਮੀਟਰ"), ("mm²", "ਵਰਗ ਮਿਲੀਮੀਟਰ"), ("t", "ਟਨ"), ("m", "ਮੀਟਰ")];

fn pa_units(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = PA_UNITS.iter().map(|x| x.0).collect();
    let pat = [
        r"(?<![₹€$£¥৳₨\w.,])(?<![₹€$£¥৳₨] )(?<!Rs )(?<!Rs\.)(?<!Rs\. )(?<![A-Z][A-Z][A-Z] )(\d+(?:[.,]\d+)*)( ?)(",
        &alt(&keys),
        r")(?![A-Za-z0-9²³/])",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        if g(m, 3) == "m" && !g(m, 1).contains('.') {
            return None;
        }
        let &(_, word) = PA_UNITS.iter().find(|x| x.0 == g(m, 3))?;
        Some(format!("{} {word}", g(m, 1)))
    })
}

const MONTHS: &[&str] = &[
    "ਜਨਵਰੀ",
    "ਫ਼ਰਵਰੀ",
    "ਫਰਵਰੀ",
    "ਮਾਰਚ",
    "ਅਪ੍ਰੈਲ",
    "ਅਪਰੈਲ",
    "ਮਈ",
    "ਜੂਨ",
    "ਜੁਲਾਈ",
    "ਅਗਸਤ",
    "ਸਤੰਬਰ",
    "ਅਕਤੂਬਰ",
    "ਨਵੰਬਰ",
    "ਦਸੰਬਰ",
    "ਜਨ",
    "ਫ਼ਰ",
    "ਅਪ੍ਰੈ",
    "ਜੁਲਾ",
    "ਅਗ",
    "ਸਤੰ",
    "ਅਕਤੂ",
    "ਨਵੰ",
    "ਦਸੰ",
];

fn pa_glued(t: String, c: &mut Ctx) -> String {
    glued(t, c, "pa", GURU, &["ਵਿੱਚ", "ਵਿਚ", "ਦਾ", "ਦੀ", "ਦੇ", "ਦੀਆਂ", "ਨੂੰ", "ਤੋਂ", "ਤੱਕ", "ਤੇ", "ਨੇ", "ਵਿੱਚੋਂ"], false)
}

fn pa_year(t: String, c: &mut Ctx) -> String {
    years(
        t,
        c,
        "pa",
        GURU,
        " ਸੌ",
        &["ਸੰਨ", "ਸਨ", "ਸਾਲ", "ਵਰ੍ਹੇ"],
        &["ਵਿੱਚ", "ਵਿਚ", "ਤੋਂ", "ਤੱਕ", "ਈ.", "ਈਸਵੀ"],
        &["ਦੇ ਦਹਾਕੇ", "ਦਾ ਦਹਾਕਾ"],
        MONTHS,
    )
}

fn pa_ampm(t: String, c: &mut Ctx) -> String {
    ampm(t, c, "ਏ ਐੱਮ", "ਪੀ ਐੱਮ", false)
}

fn pa_clock(t: String, c: &mut Ctx) -> String {
    clock_hourword(
        t,
        c,
        "pa",
        GURU,
        &["ਵਜੇ", "ਵੱਜੇ"],
        &["ਤੱਕ", "ਤੋਂ", "ਦੀ", "ਦਾ", "ਦੇ", "ਨੂੰ", "ਤੇ", "ਹੈ", "ਹਨ", "ਸੀ"],
        Some(&|h, mm| quarters(h, mm, "pa", "ਡੇਢ", "ਢਾਈ", "ਸਾਢੇ", "ਸਵਾ", "ਪੌਣੇ", " ")),
        &|r, w, a| absorb_postposition(r, w, a, "ਮਿੰਟ", "ਵਜੇ", "ਤੇ"),
    )
}

fn pa_minus(t: String, c: &mut Ctx) -> String {
    let t = money_minus(t, c, "ਮਾਈਨਸ", GURU);
    minus(
        t,
        c,
        "ਮਾਈਨਸ",
        GURU,
        &["ਡਿਗਰੀ", "ਕਿਲੋ", "ਕਿਲੋਗ੍ਰਾਮ", "ਗ੍ਰਾਮ", "ਮੀਟਰ", "ਕਿਲੋਮੀਟਰ", "ਲਿਟਰ", "ਰੁਪਏ", "ਪ੍ਰਤੀਸ਼ਤ", "ਫ਼ੀਸਦੀ"],
        &["ਤਾਪਮਾਨ", "ਪਾਰਾ"],
        &["ਤੋਂ"],
    )
}

fn pa_latin_number(t: String, c: &mut Ctx) -> String {
    latin_number(t, c, ACRONYMS, &[("T20", "ਟੀ ਟਵੰਟੀ"), ("T-20", "ਟੀ ਟਵੰਟੀ")])
}

fn pa_half_scale(t: String, c: &mut Ctx) -> String {
    half_scale(
        t,
        c,
        "pa",
        GURU,
        &["ਲੱਖ", "ਕਰੋੜ", "ਹਜ਼ਾਰ", "ਹਜਾਰ", "ਅਰਬ"],
        &["₹", "Rs.", "Rs", "INR"],
        &|n| halves(n, "pa", "ਡੇਢ", "ਢਾਈ", "ਸਾਢੇ", " "),
        false,
    )
}

fn pa_score(t: String, c: &mut Ctx) -> String {
    score(t, c, "pa", GURU, &["ਨਾਲ"], &["ਜਿੱਤ", "ਹਾਰ", "ਹਰਾ", "ਬਰਾਬਰ", "ਮਾਤ", "ਬੜ੍ਹਤ", "ਲੀਡ"])
}
