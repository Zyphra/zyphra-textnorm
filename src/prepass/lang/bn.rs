//! 'bn' rules: the port of the workbench's `langrules/bn.py` (ids `bn.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
use super::hi::{
    ACRONYMS, BENG, alt, ampm, big, codes, glued, half_scale, halves, has_digit, is_year, latin_number, minus,
    money_minus, money_range, per_unit, ranges, score, space_groups, year_words, years,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("bn.space-groups", bn_space_groups),
    ("bn.decade", bn_decade),
    ("bn.glued", bn_glued),
    ("bn.year", bn_year),
    ("bn.ampm", bn_ampm),
    ("bn.score", bn_score),
    ("bn.clock-case", bn_clock_case),
    ("bn.classifier-case", bn_classifier_case),
    ("bn.minus", bn_minus),
    ("bn.latin-number", bn_latin_number),
    ("bn.taka", bn_taka),
    ("bn.big", bn_big),
    ("bn.money-range", bn_money_range),
    ("bn.range", bn_range),
    ("bn.per", bn_per),
    ("bn.codes", bn_codes),
    ("bn.half-scale", bn_half_scale),
    ("bn.kg", bn_kg),
];

const MONTHS: &[&str] = &[
    "জানুয়ারি",
    "ফেব্রুয়ারি",
    "মার্চ",
    "এপ্রিল",
    "মে",
    "জুন",
    "জুলাই",
    "আগস্ট",
    "সেপ্টেম্বর",
    "অক্টোবর",
    "নভেম্বর",
    "ডিসেম্বর",
    "জানু",
    "ফেব",
    "এপ্রি",
    "জুল",
    "আগ",
    "সেপ",
    "সেপ্ট",
    "অক্টো",
    "নভে",
    "ডিসে",
];

const BN_SCALES: &[&str] = &["লাখ", "লক্ষ", "কোটি", "হাজার", "আরব", "খরব"];

fn bn_space_groups(t: String, c: &mut Ctx) -> String {
    space_groups(t, c)
}

fn bn_decade(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&[r"(?<![\w.,:/\-–])(\d{4})(-এর দশক| এর দশক|এর দশক)(", BENG, "*)"].concat()),
        &t,
        |m| {
            let said = words(&format!("{}-এর দশক", g(m, 1)), "bn");
            let card = words(g(m, 1), "bn");
            if !said.starts_with(&card) || has_digit(&said) || py_int(g(m, 1)).is_multiple_of(100) {
                return None;
            }
            let head = if is_year(g(m, 1)) { year_words(py_int(g(m, 1)), "bn", "শো") } else { card.clone() };
            Some(format!("{head}{}{}", &said[card.len()..], g(m, 3)))
        },
    )
}

fn bn_glued(t: String, c: &mut Ctx) -> String {
    glued(t, c, "bn", BENG, &["এ", "এর", "তে"], true)
}

fn bn_year(t: String, c: &mut Ctx) -> String {
    years(
        t,
        c,
        "bn",
        BENG,
        "শো",
        &["সাল", "সন"],
        &["এ", "খ্রি.", "খ্রিঃ"],
        &["সাল", "সন", "খ্রিস্টাব্দ", "খ্রিষ্টাব্দ", "এর দশক"],
        MONTHS,
    )
}

fn bn_ampm(t: String, c: &mut Ctx) -> String {
    ampm(t, c, "এ এম", "পি এম", false)
}

const LOCATIVE: &[&str] = &["টায়", "এ", "-এ"];
const GENITIVE: &[&str] = &["টার", "এর", "-এর"];

fn bn_clock_case(t: String, c: &mut Ctx) -> String {
    let ends: Vec<&str> = LOCATIVE.iter().chain(GENITIVE).chain(&["টা"]).copied().collect();
    c.sub(&rx(&[r"(?<![\d:.,])(\d{1,2}):(\d\d)(\s?)(", &alt(&ends), ")(?!", BENG, ")"].concat()), &t, |m| {
        let (h, mm, end) = (py_int(g(m, 1)), py_int(g(m, 2)), g(m, 4));
        if h > 23 || mm > 59 {
            return None;
        }
        let said = words(&format!("{h}:{mm:02}"), "bn");
        if has_digit(&said) {
            return None;
        }
        if end == "টা" {
            return Some(said);
        }
        let genitive = GENITIVE.contains(&end);
        if said.ends_with("মিনিট") {
            return Some(format!("{said}{}", if genitive { "ের" } else { "ে" }));
        }
        if said.ends_with("টা") {
            return Some(format!("{said}{}", if genitive { "র" } else { "য়" }));
        }
        None
    })
}

const CASE: &[&str] = &["য়", "র", "তে", "কে", "ই", "ও", "রই", "তেই", "কেই"];

fn bn_classifier_case(t: String, c: &mut Ctx) -> String {
    let pat = [r"(?<![\w.,:/\-–])(\d+)(", &alt(&["টা", "টি", "টে", "টো"]), ")(", &alt(CASE), ")(?!", BENG, ")"].concat();
    c.sub(&rx(&pat), &t, |m| {
        let said = words(&format!("{}{}", g(m, 1), g(m, 2)), "bn");
        if !said.ends_with(g(m, 2)) || said.contains(&format!(" {}", g(m, 2))) || has_digit(&said) {
            return None;
        }
        Some(format!("{said}{}", g(m, 3)))
    })
}

fn bn_minus(t: String, c: &mut Ctx) -> String {
    let t = money_minus(t, c, "মাইনাস", BENG);
    minus(
        t,
        c,
        "মাইনাস",
        BENG,
        &["ডিগ্রি", "ডিগ্রী", "কেজি", "কিলো", "কিলোগ্রাম", "গ্রাম", "মিটার", "কিমি", "কিলোমিটার", "সেমি", "লিটার", "টাকা", "শতাংশ"],
        &["তাপমাত্রা", "পারদ"],
        &["থেকে"],
    )
}

fn bn_latin_number(t: String, c: &mut Ctx) -> String {
    latin_number(t, c, ACRONYMS, &[("T20", "টি টোয়েন্টি"), ("T-20", "টি টোয়েন্টি")])
}

fn bn_taka(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![A-Za-z])(?:₹|Rs\.?)(?=\s?\d)"), &t, |_| Some("৳".to_string()))
}

fn bn_big(t: String, c: &mut Ctx) -> String {
    big(t, c, "bn", "মাইনাস")
}

fn bn_money_range(t: String, c: &mut Ctx) -> String {
    money_range(t, c, "bn", "থেকে", BENG, BN_SCALES)
}

fn bn_range(t: String, c: &mut Ctx) -> String {
    ranges(
        t,
        c,
        BENG,
        "থেকে",
        &["থেকে", "পর্যন্ত", "এর", "কে", "তে", "এ", "ও", "এবং", "বা", "গোলে", "ছিল", "হয়"],
        "[~～〜]",
    )
}

const BN_CODES: &[(&str, &str, &str)] = &[
    ("NPR", "নেপালি রুপি", "পয়সা"),
    ("LKR", "শ্রীলঙ্কান রুপি", "সেন্ট"),
    ("HKD", "হংকং ডলার", "সেন্ট"),
    ("SGD", "সিঙ্গাপুর ডলার", "সেন্ট"),
    ("MYR", "মালয়েশিয়ান রিংগিত", "সেন"),
];

fn bn_codes(t: String, c: &mut Ctx) -> String {
    codes(t, c, "bn", BENG, BN_CODES, BN_SCALES)
}

fn bn_per(t: String, c: &mut Ctx) -> String {
    per_unit(t, c, "bn", "প্রতি", BENG, &["টাকা"])
}

fn bn_half_scale(t: String, c: &mut Ctx) -> String {
    half_scale(
        t,
        c,
        "bn",
        BENG,
        &["লাখ", "লক্ষ", "কোটি", "হাজার"],
        &["৳", "Tk.", "Tk"],
        &|n| halves(n, "bn", "দেড়", "আড়াই", "সাড়ে", " "),
        false,
    )
}

fn bn_kg(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&["(?<!", BENG, ")কেজি(?!", BENG, ")"].concat()), &t, |_| {
        Some("\u{e000}কেজি\u{e001}".to_string())
    })
}

fn bn_score(t: String, c: &mut Ctx) -> String {
    score(t, c, "bn", BENG, &["গোলে", "ব্যবধানে"], &[])
}
