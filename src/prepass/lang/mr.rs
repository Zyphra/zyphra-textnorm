//! 'mr' rules: the port of the workbench's `langrules/mr.py` (ids `mr.*`); the helpers are shared with the other
//! Indic modules (`hi.rs`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
use super::hi::{
    ACRONYMS, DEVA, SANSKRIT_ORD, alt, ampm, big, clock_hourword, codes, glued, half_scale, halves, has_digit,
    latin_number, money_minus, money_range, per_unit, quarters, ranges, regnal, score, space_groups, unit_groups,
    years,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("mr.space-groups", mr_space_groups),
    ("mr.big", mr_big),
    ("mr.glued", mr_glued),
    ("mr.year", mr_year),
    ("mr.ampm", mr_ampm),
    ("mr.clock-hourword", mr_clock),
    ("mr.money-range", mr_money_range),
    ("mr.minus", mr_minus),
    ("mr.latin-number", mr_latin_number),
    ("mr.score", mr_score),
    ("mr.range", mr_range),
    ("mr.per", mr_per),
    ("mr.codes", mr_codes),
    ("mr.half-scale", mr_half_scale),
    ("mr.unit-groups", mr_unit_groups),
    ("mr.units", mr_units),
    ("mr.ordinal-oblique", mr_ordinal_oblique),
    ("mr.title-shri", mr_title_shri),
    ("mr.regnal", mr_regnal),
];

const MONTHS: &[&str] = &[
    "जानेवारी",
    "फेब्रुवारी",
    "मार्च",
    "एप्रिल",
    "मे",
    "जून",
    "जुलै",
    "ऑगस्ट",
    "सप्टेंबर",
    "ऑक्टोबर",
    "नोव्हेंबर",
    "डिसेंबर",
    "जाने",
    "फेब्रु",
    "एप्रि",
    "ऑग",
    "सप्टें",
    "ऑक्टो",
    "नोव्हें",
    "डिसें",
];

const MR_SCALES: &[&str] = &["लाख", "कोटी", "हजार", "अब्ज", "खर्व"];

fn mr_space_groups(t: String, c: &mut Ctx) -> String {
    space_groups(t, c)
}

fn mr_big(t: String, c: &mut Ctx) -> String {
    big(t, c, "mr", "उणे")
}

fn mr_money_range(t: String, c: &mut Ctx) -> String {
    money_range(t, c, "mr", "ते", DEVA, MR_SCALES)
}

fn mr_minus(t: String, c: &mut Ctx) -> String {
    money_minus(t, c, "उणे", DEVA)
}

fn mr_glued(t: String, c: &mut Ctx) -> String {
    glued(
        t,
        c,
        "mr",
        DEVA,
        &["मध्ये", "ला", "चा", "ची", "चे", "च्या", "पासून", "पर्यंत", "ने", "साली", "पेक्षा", "नंतर", "पूर्वी"],
        false,
    )
}

fn mr_year(t: String, c: &mut Ctx) -> String {
    years(
        t,
        c,
        "mr",
        DEVA,
        "शे",
        &["सन्", "सन", "साल", "वर्ष", "इ.स.", "इ. स.", "ई.स.", "इसवी"],
        &["मध्ये", "साली", "साल", "इ.स.", "इ. स.", "ई.स.", "इसवी", "पासून", "पर्यंत"],
        &["च्या दशक", "चे दशक", "चा दशक"],
        MONTHS,
    )
}

fn mr_ampm(t: String, c: &mut Ctx) -> String {
    ampm(t, c, "ए एम", "पी एम", false)
}

fn mr_absorb(reading: &str, word: &str, _after: &str) -> Option<String> {
    if word != "वाजता" {
        return None;
    }
    if let Some(head) = reading.strip_suffix("मिनिटे").filter(|h| h.ends_with(' ')) {
        return Some(format!("{head}मिनिटांनी"));
    }
    if let Some(head) = reading.strip_suffix("मिनिट").filter(|h| h.ends_with(' ')) {
        return Some(format!("{head}मिनिटाने"));
    }
    None
}

fn mr_clock(t: String, c: &mut Ctx) -> String {
    clock_hourword(
        t,
        c,
        "mr",
        DEVA,
        &["वाजता", "वाजले", "वाजेपर्यंत", "वाजल्यापासून"],
        &[],
        Some(&|h, mm| quarters(h, mm, "mr", "दीड", "अडीच", "साडे", "सव्वा", "पावणे", "")),
        &mr_absorb,
    )
}

fn mr_latin_number(t: String, c: &mut Ctx) -> String {
    latin_number(t, c, ACRONYMS, &[("T20", "टी ट्वेंटी"), ("T-20", "टी ट्वेंटी")])
}

fn mr_range(t: String, c: &mut Ctx) -> String {
    ranges(
        t,
        c,
        DEVA,
        "ते",
        &["ने", "ला", "ते", "चा", "ची", "चे", "च्या", "मध्ये", "पर्यंत", "पासून", "आहे", "आहेत", "होते", "होता", "आणि", "किंवा"],
        "[-–~～〜]",
    )
}

fn mr_codes(t: String, c: &mut Ctx) -> String {
    codes(t, c, "mr", DEVA, &[("Tk.", "टका", "पैसे"), ("Tk", "टका", "पैसे")], MR_SCALES)
}

fn mr_per(t: String, c: &mut Ctx) -> String {
    per_unit(t, c, "mr", "प्रति", DEVA, &["रुपये", "रुपया"])
}

fn mr_half_scale(t: String, c: &mut Ctx) -> String {
    half_scale(
        t,
        c,
        "mr",
        DEVA,
        &["लाख", "कोटी", "हजार", "अब्ज"],
        &["₹", "Rs.", "Rs", "INR"],
        &|n| halves(n, "mr", "दीड", "अडीच", "साडे", ""),
        false,
    )
}

fn mr_unit_groups(t: String, c: &mut Ctx) -> String {
    unit_groups(t, c, "mr")
}

fn mr_units(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<=\d)( ?)L(?![A-Za-z0-9²³/])"), &t, r"\1l")
}

const OBLIQUE: &[(&str, &str)] = &[("व्या", "वा"), ("ल्या", "ला"), ("ऱ्या", "रा"), ("थ्या", "था")];

fn mr_ordinal_oblique(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = OBLIQUE.iter().map(|&(k, _)| k).collect();
    c.sub(&rx(&[r"(?<![\w.,])(\d+)(", &alt(&keys), ")(?!", DEVA, ")"].concat()), &t, |m| {
        let nom = OBLIQUE.iter().find(|&&(k, _)| k == g(m, 2))?.1;
        let said = words(&format!("{}{nom}", g(m, 1)), "mr");
        let stem = said.strip_suffix(nom)?;
        if stem.ends_with(' ') || stem.is_empty() || has_digit(&said) {
            return None;
        }
        // एकवीस -> एकविसाव्या: -ईस shortens before the ordinal ending
        let stem = match stem.strip_suffix("ीसा") {
            Some(head) => format!("{head}िसा"),
            None => stem.to_string(),
        };
        Some(format!("{stem}{}", g(m, 2)))
    })
}

fn mr_title_shri(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&["(?<!", DEVA, r")श्री\.(?=\s)"].concat()), &t, |_| Some("श्री".to_string()))
}

fn mr_regnal(t: String, c: &mut Ctx) -> String {
    regnal(
        t,
        c,
        DEVA,
        &[
            "राणी",
            "महाराणी",
            "राजा",
            "महाराजा",
            "महाराज",
            "सम्राट",
            "सम्राज्ञी",
            "पोप",
            "किंग",
            "क्वीन",
            "प्रिन्स",
            "प्रिंस",
            "सुलतान",
            "शाह",
            "बादशहा",
            "नवाब",
            "झार",
        ],
        &["ने", "चा", "ची", "चे", "च्या", "ला", "ते", "आणि", "हे", "होते", "यांचे", "यांनी"],
        SANSKRIT_ORD,
    )
}

fn mr_score(t: String, c: &mut Ctx) -> String {
    score(
        t,
        c,
        "mr",
        DEVA,
        &["ने", "अशा", "असा", "अशी", "च्या"],
        &["जिंक", "हरव", "पराभव", "विजय", "बरोबरी", "आघाडी", "मात", "फरका"],
    )
}
