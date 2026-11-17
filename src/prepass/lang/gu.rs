//! 'gu' rules: the port of the workbench's `langrules/gu.py` (ids `gu.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
use super::hi::{
    ACRONYMS, GUJR, ampm, big, clock_hourword, codes, glued, half_scale, halves, latin_number, minus, money_minus,
    money_range, per_unit, quarters, ranges, regnal, score, space_groups, unit_groups, years,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("gu.space-groups", gu_space_groups),
    ("gu.big", gu_big),
    ("gu.glued", gu_glued),
    ("gu.year", gu_year),
    ("gu.ampm", gu_ampm),
    ("gu.clock-hourword", gu_clock),
    ("gu.money-range", gu_money_range),
    ("gu.minus", gu_minus),
    ("gu.latin-number", gu_latin_number),
    ("gu.score", gu_score),
    ("gu.range", gu_range),
    ("gu.per", gu_per),
    ("gu.codes", gu_codes),
    ("gu.half-scale", gu_half_scale),
    ("gu.unit-groups", gu_unit_groups),
    ("gu.regnal", gu_regnal),
];
const GU_SCALES: &[&str] = &["લાખ", "કરોડ", "હજાર", "અબજ", "ખરબ"];

fn gu_space_groups(t: String, c: &mut Ctx) -> String {
    space_groups(t, c)
}

fn gu_big(t: String, c: &mut Ctx) -> String {
    big(t, c, "gu", "માઇનસ")
}

fn gu_money_range(t: String, c: &mut Ctx) -> String {
    money_range(t, c, "gu", "થી", GUJR, GU_SCALES)
}

const MONTHS: &[&str] = &[
    "જાન્યુઆરી",
    "ફેબ્રુઆરી",
    "માર્ચ",
    "એપ્રિલ",
    "મે",
    "જૂન",
    "જુલાઈ",
    "ઑગસ્ટ",
    "ઓગસ્ટ",
    "સપ્ટેમ્બર",
    "ઑક્ટોબર",
    "ઓક્ટોબર",
    "નવેમ્બર",
    "ડિસેમ્બર",
    "જાન્યુ",
    "ફેબ્રુ",
    "ઑગ",
    "ઓગ",
    "સપ્ટે",
    "ઑક્ટો",
    "ઓક્ટો",
    "નવે",
    "ડિસે",
];
const POST: &[&str] = &["માં", "ના", "ની", "નું", "નો", "ને", "થી", "એ", "સુધી", "પર", "માંથી"];

fn gu_glued(t: String, c: &mut Ctx) -> String {
    glued(t, c, "gu", GUJR, POST, false)
}

fn gu_year(t: String, c: &mut Ctx) -> String {
    years(
        t,
        c,
        "gu",
        GUJR,
        "સો",
        &["સન", "સન્", "સાલ", "વર્ષ", "ઈ.સ.", "ઈસવીસન"],
        &["માં", "થી", "સુધી", "ઈ.સ.", "ઈસવીસન"],
        &["ના દાયકા", "ની સાલ"],
        MONTHS,
    )
}

fn gu_ampm(t: String, c: &mut Ctx) -> String {
    ampm(t, c, "એ એમ", "પી એમ", false)
}

fn gu_absorb(reading: &str, word: &str, _after: &str) -> Option<String> {
    if word != "વાગ્યે" || !reading.ends_with(" મિનિટ") {
        return None;
    }
    Some(format!("{reading}ે"))
}

fn gu_clock(t: String, c: &mut Ctx) -> String {
    clock_hourword(
        t,
        c,
        "gu",
        GUJR,
        &["વાગ્યે", "વાગ્યા", "વાગ્યાથી", "વાગે"],
        &[],
        Some(&|h, mm| quarters(h, mm, "gu", "દોઢ", "અઢી", "સાડા", "સવા", "પોણા", " ")),
        &gu_absorb,
    )
}

fn gu_minus(t: String, c: &mut Ctx) -> String {
    let t = money_minus(t, c, "માઇનસ", GUJR);
    minus(
        t,
        c,
        "માઇનસ",
        GUJR,
        &[
            "ડિગ્રી",
            "અંશ",
            "કિલો",
            "કિગ્રા",
            "કિલોગ્રામ",
            "ગ્રામ",
            "મીટર",
            "કિમી",
            "કિલોમીટર",
            "સેમી",
            "લિટર",
            "રૂપિયા",
            "ટકા",
        ],
        &["તાપમાન", "પારો"],
        &["થી"],
    )
}

fn gu_latin_number(t: String, c: &mut Ctx) -> String {
    latin_number(t, c, ACRONYMS, &[("T20", "ટી ટ્વેન્ટી"), ("T-20", "ટી ટ્વેન્ટી")])
}

fn gu_range(t: String, c: &mut Ctx) -> String {
    ranges(
        t,
        c,
        GUJR,
        "થી",
        &["થી", "માં", "ના", "ની", "નું", "નો", "ને", "એ", "છે", "હતા", "હતી", "હતો", "અને", "કે", "સુધી"],
        "[-–~～〜]",
    )
}

fn gu_codes(t: String, c: &mut Ctx) -> String {
    codes(t, c, "gu", GUJR, &[("Tk.", "ટાકા", "પૈસા"), ("Tk", "ટાકા", "પૈસા")], GU_SCALES)
}

fn gu_per(t: String, c: &mut Ctx) -> String {
    per_unit(t, c, "gu", "પ્રતિ", GUJR, &["રૂપિયા", "રૂપિયો"])
}

fn gu_half_scale(t: String, c: &mut Ctx) -> String {
    half_scale(
        t,
        c,
        "gu",
        GUJR,
        &["લાખ", "કરોડ", "હજાર", "અબજ"],
        &["₹", "Rs.", "Rs", "INR"],
        &|n| halves(n, "gu", "દોઢ", "અઢી", "સાડા", " "),
        false,
    )
}

fn gu_unit_groups(t: String, c: &mut Ctx) -> String {
    unit_groups(t, c, "gu")
}

const GU_ORD: &[&str] = &["પ્રથમ", "દ્વિતીય", "તૃતીય", "ચતુર્થ", "પંચમ", "ષષ્ઠ", "સપ્તમ", "અષ્ટમ", "નવમ", "દશમ"];

fn gu_regnal(t: String, c: &mut Ctx) -> String {
    regnal(
        t,
        c,
        GUJR,
        &[
            "મહારાણી",
            "રાણી",
            "રાજા",
            "મહારાજા",
            "મહારાજ",
            "સમ્રાટ",
            "પોપ",
            "કિંગ",
            "ક્વીન",
            "પ્રિન્સ",
            "રાજકુમાર",
            "ઝાર",
            "સુલતાન",
            "શાહ",
            "બાદશાહ",
            "નવાબ",
        ],
        &["નું", "ના", "ની", "નો", "ને", "એ", "અને", "છે", "હતા"],
        GU_ORD,
    )
}

fn gu_score(t: String, c: &mut Ctx) -> String {
    score(t, c, "gu", GUJR, &["થી"], &["જીત", "હાર", "હરાવ", "પરાજય", "બરાબરી", "લીડ", "માત"])
}
