//! 'pa' rules: the port of the workbench's `langrules/pa.py` (ids `pa.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
use super::hi::{
    ACRONYMS, GURU, absorb_postposition, ampm, clock_hourword, glued, half_scale, halves, latin_number, minus,
    quarters, score, years,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("pa.glued", pa_glued),
    ("pa.year", pa_year),
    ("pa.ampm", pa_ampm),
    ("pa.score", pa_score),
    ("pa.clock-hourword", pa_clock),
    ("pa.minus", pa_minus),
    ("pa.latin-number", pa_latin_number),
    ("pa.half-scale", pa_half_scale),
];

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
