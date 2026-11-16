//! 'ur' rules: the port of the workbench's `langrules/ur.py` (ids `ur.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
use super::hi::{
    ACRONYMS, ARAB, absorb_postposition, alt, clock_hourword, glued, half_scale, halves, is_year, latin_number, ranges,
    regnal, score, year_words, years,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ur.glued", ur_glued),
    ("ur.year", ur_year),
    ("ur.clock-hourword", ur_clock),
    ("ur.latin-number", ur_latin_number),
    ("ur.score", ur_score),
    ("ur.range", ur_range),
    ("ur.money-scale", ur_money_scale),
    ("ur.page", ur_page),
    ("ur.regnal", ur_regnal),
];

const MONTHS: &[&str] =
    &["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"];
const ERA: &[(&str, &str)] = &[("ء", "عیسوی"), ("ھ", "ہجری")];

fn ur_glued(t: String, c: &mut Ctx) -> String {
    glued(t, c, "ur", ARAB, &["میں", "کا", "کی", "کے", "کو", "سے", "تک", "پر", "نے"], false)
}

fn ur_year(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = ERA.iter().map(|&(k, _)| k).collect();
    let t = c.sub(&rx(&[r"(?<![\w.,:/\-–])(\d{4})\s?(", &alt(&keys), ")(?!", ARAB, ")"].concat()), &t, |m| {
        if !is_year(g(m, 1)) {
            return None;
        }
        let era = ERA.iter().find(|&&(k, _)| k == g(m, 2))?.1;
        Some(format!("{} {era}", year_words(py_int(g(m, 1)), "ur", " سو")))
    });
    years(t, c, "ur", ARAB, " سو", &["سن", "سنہ", "سال"], &["میں", "سے", "تک", "عیسوی", "ہجری"], &["کی دہائی"], MONTHS)
}

fn ur_clock(t: String, c: &mut Ctx) -> String {
    clock_hourword(
        t,
        c,
        "ur",
        ARAB,
        &["بجے"],
        &["تک", "سے", "کی", "کا", "کے", "کو", "پر", "میں", "ہے", "ہیں", "تھا", "تھے", "تھی"],
        None,
        &|r, w, a| absorb_postposition(r, w, a, "منٹ", "بجے", "پر"),
    )
}

fn ur_latin_number(t: String, c: &mut Ctx) -> String {
    latin_number(t, c, ACRONYMS, &[("T20", "ٹی ٹوئنٹی"), ("T-20", "ٹی ٹوئنٹی")])
}

fn ur_score(t: String, c: &mut Ctx) -> String {
    score(t, c, "ur", ARAB, &["سے", "کی"], &["جیت", "ہار", "ہرا", "شکست", "مات", "برابر", "ڈرا", "برتری"])
}

fn ur_range(t: String, c: &mut Ctx) -> String {
    ranges(
        t,
        c,
        ARAB,
        "سے",
        &["سے", "تک", "کو", "کا", "کی", "کے", "میں", "پر", "نے", "ہے", "ہیں", "تھا", "تھی", "تھے", "اور", "یا"],
    )
}

fn ur_money_scale(t: String, c: &mut Ctx) -> String {
    half_scale(
        t,
        c,
        "ur",
        ARAB,
        &["ہزار", "لاکھ", "کروڑ", "ارب", "کھرب"],
        &["Rs.", "Rs", "₨", "₹", "PKR", "\\$", "€", "£"],
        &|n| halves(n, "ur", "ڈیڑھ", "ڈھائی", "ساڑھے", " "),
        true,
    )
}

fn ur_page(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&["(?<!", ARAB, r")(ص|ج)[.۔]?\s?(?=\d)"].concat()), &t, |m| {
        Some(if g(m, 1) == "ص" { "صفحہ " } else { "جلد " }.to_string())
    })
}

const UR_ORD: &[&str] = &["اول", "دوم", "سوم", "چہارم", "پنجم", "ششم", "ہفتم", "ہشتم", "نہم", "دہم"];

fn ur_regnal(t: String, c: &mut Ctx) -> String {
    regnal(
        t,
        c,
        ARAB,
        &["ملکہ", "بادشاہ", "شاہ", "پوپ", "شہنشاہ", "سلطان", "نواب", "کنگ", "کوئین", "شہزادہ", "شہزادی", "زار", "قیصر"],
        &["نے", "کا", "کی", "کے", "کو", "سے", "میں", "پر", "اور", "ہے", "تھا"],
        UR_ORD,
    )
}
