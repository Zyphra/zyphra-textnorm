//! 'kn' rules: the port of the workbench's `langrules/kn.py` (ids `kn.*`).

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, rx, tpl};
#[allow(unused_imports)]
use super::ta::{
    DR_CODES_MINUS, dr_alt, dr_big, dr_code, dr_cur_word, dr_half_scale, dr_money, dr_money_range, dr_pad, dr_per,
    dr_scale_case,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("kn.money-abbrev", kn_money_abbrev),
    ("kn.minus", kn_minus),
    ("kn.big", kn_big),
    ("kn.money-code", kn_money_code),
    ("kn.per", kn_per),
    ("kn.money-range", kn_money_range),
    ("kn.money-scale", kn_money_scale),
    ("kn.money-scale-case", kn_money_scale_case),
    ("kn.half-scale", kn_half_scale),
    ("kn.units", kn_units),
    ("kn.percent", kn_percent),
    ("kn.range", kn_range),
    ("kn.ordinal-hyphen", kn_ordinal_hyphen),
    ("kn.first", kn_first),
    ("kn.month-words", kn_month_words),
    ("kn.pm-period", kn_pm_period),
    ("kn.pm-suffix", kn_pm_suffix),
    ("kn.suffix", kn_suffix),
    ("kn.doctor", kn_doctor),
];

/// Kannada letters and vowel signs (not the Kannada digits).
const KN: &str = "\u{0C80}-\u{0CE3}";
/// 1947, 1,500, 6,50,00,000 (10+ bare digits: a phone number).
const NUM: &str = r"[0-9]{1,3}(?:,[0-9]{2,3})*,[0-9]{3}|[0-9]{1,9}";
/// Endings written after a number with the oblique augment ರ (1947ರಲ್ಲಿ, 2024ರಂದು, 1990ರ ದಶಕ, 5ರಿಂದ, 40ರಷ್ಟು).
const TAIL_R: &[&str] = &[
    "ರಲ್ಲಿನ",
    "ರಲ್ಲೇ",
    "ರಲ್ಲೂ",
    "ರಲ್ಲಿ",
    "ರಂದೇ",
    "ರಂದು",
    "ರಿಂದಲೂ",
    "ರಿಂದಲೇ",
    "ರಿಂದಾಗಿ",
    "ರಿಂದ",
    "ರವರೆಗಿನ",
    "ರವರೆಗೂ",
    "ರವರೆಗೆ",
    "ರಷ್ಟು",
    "ರೊಳಗಾಗಿ",
    "ರೊಳಗೆ",
    "ರ",
];
/// The dative and its forms: after -u and -a it is ಕ್ಕೆ (ನೂರಕ್ಕೆ, ಸಾವಿರಕ್ಕೆ), after -i and -e ಗೆ (ಕೋಟಿಗೆ, ಗಂಟೆಗೆ).
const DATIVES: &[(&str, &str)] = &[("ಕ್ಕಿಂತಲೂ", "ಗಿಂತಲೂ"), ("ಕ್ಕಿಂತ", "ಗಿಂತ"), ("ಕ್ಕೆ", "ಗೆ"), ("ಕ್ಕೇ", "ಗೇ"), ("ಕ್ಕೂ", "ಗೂ")];
const PERIODS: &[&str] = &["ಬೆಳಗ್ಗೆ", "ಬೆಳಿಗ್ಗೆ", "ಮಧ್ಯಾಹ್ನ", "ಸಂಜೆ", "ರಾತ್ರಿ"];

fn tails() -> String {
    let mut out: Vec<&str> = TAIL_R.to_vec();
    out.extend(DATIVES.iter().map(|d| d.0));
    out.extend(DATIVES.iter().map(|d| d.1));
    out.join("|")
}

fn end0(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

/// `s[:-1]` in characters.
fn drop_last(s: &str) -> String {
    let mut out = s.to_string();
    out.pop();
    out
}

/// A written number as the grammar reads it, or None for a leading zero (codes are not numbers).
fn plain(n: &str) -> Option<String> {
    let d = n.replace(',', "");
    let b = d.as_bytes();
    if b.len() > 1 && b[0] == b'0' && b[1] != b'.' {
        return None;
    }
    Some(words(&d, "kn"))
}

/// The grammar's reading, without the leading ಒಂದು of 1000–1999 (1947 -> “ಸಾವಿರದ ಒಂಬೈನೂರ ನಲವತ್ತೇಳು”, as years
/// and amounts are said).
fn year(n: &str) -> Option<String> {
    let sp = plain(n)?;
    if n.replace(',', "").chars().count() == 4 && !n.contains('.') && sp.starts_with("ಒಂದು ಸಾವಿರ") {
        return Some(sp["ಒಂದು ".len()..].to_string());
    }
    Some(sp)
}

/// A number word and the ending glued to it as one word: ನಲವತ್ತೇಳು + ರಲ್ಲಿ -> ನಲವತ್ತೇಳರಲ್ಲಿ, ಸಾವಿರ + ರಲ್ಲಿ ->
/// ಸಾವಿರದಲ್ಲಿ, ಕೋಟಿ + ರಿಂದ -> ಕೋಟಿಯಿಂದ, ನೂರು + ಕ್ಕೆ -> ನೂರಕ್ಕೆ, ಗಂಟೆ + ಕ್ಕೆ -> ಗಂಟೆಗೆ.
fn join(w: &str, tail: &str) -> String {
    let vowel = w.ends_with('\u{0CBF}') || w.ends_with('\u{0CC6}'); // ಕೋಟಿ, ಗಂಟೆ, ಸೊನ್ನೆ
    let u = w.ends_with('\u{0CC1}'); // ಏಳು, ನೂರು
    for &(k, gg) in DATIVES {
        if tail == k || tail == gg {
            if vowel {
                return format!("{w}{gg}");
            }
            return format!("{}{k}", if u { drop_last(w) } else { w.to_string() });
        }
    }
    let rest = tail.strip_prefix('ರ').unwrap_or(tail); // after the augment ರ
    if u {
        return format!("{}ರ{rest}", drop_last(w));
    }
    if vowel {
        return format!("{w}ಯ{rest}");
    }
    format!("{w}ದ{rest}") // ಸಾವಿರ, ಲಕ್ಷ
}

fn inflect(spoken: &str, tail: &str) -> String {
    let mut ws: Vec<String> = spoken.split_whitespace().map(str::to_string).collect();
    let n = ws.len();
    ws[n - 1] = join(&ws[n - 1], tail);
    ws.join(" ")
}

fn kn_minus(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,])([₹$€£¥]) ?-(?=[0-9])"), &t, |m| Some(format!("ಮೈನಸ್ {}", g(m, 1))));
    c.sub_tpl(&rx(&format!(r"(?<![\w.,)\]{KN}-])(?<![0-9] )-(?=[0-9]|{DR_CODES_MINUS})")), &t, "ಮೈನಸ್ ")
}

fn kn_money_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<![{KN}\w])ರೂ\.? ?(?=[0-9])")), &t, "₹");
    c.sub_tpl(&rx(&format!(r"(₹ ?(?:{NUM})(?:\.[0-9]{{1,2}})?)/-")), &t, r"\1")
}

fn kn_money_scale(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?:₹|(?<![\w.])Rs\.?|(?<!\w)INR) ?((?:{NUM})(?:\.[0-9]+)?) ?(ಸಾವಿರ|ಲಕ್ಷ|ಕೋಟಿ)(?![{KN}])");
    c.sub_tpl(&rx(&pat), &t, r"\1 \2 ರೂಪಾಯಿ")
}

fn kn_percent(t: String, c: &mut Ctx) -> String {
    let n = format!(r"(?:{NUM})(?:\.[0-9]+)?");
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,±+])({n}(?:[-–]{n})?) ?%")), &t, r"ಶೇಕಡಾ \1");
    c.sub_tpl(&rx(&format!(r"(?<![{KN}\w])ಶೇ\.? ?(?=[0-9])")), &t, "ಶೇಕಡಾ ")
}

fn kn_range(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/+-])([0-9]{1,9})(?:-|–| – )([0-9]{1,9})(?![0-9A-Za-z_,:/]|[.-][0-9])"), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        if (a.len() > 1 && a.starts_with('0')) || (b.len() > 1 && b.starts_with('0')) || py_int(a) >= py_int(b) {
            return None;
        }
        Some(format!("{a}ರಿಂದ {b}"))
    })
}

fn kn_ordinal_hyphen(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&format!(r"(?<![\w.,:/-])([0-9]+)-(?=ನೇ(?![{KN}]))")), &t, r"\1")
}

fn kn_first(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&format!(r"(?<![\w.,:/-])1ನೇ(?![{KN}])")), &t, "ಮೊದಲನೇ")
}

fn kn_month_words(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<=[0-9]) ಜನ(?![{KN}.])(?! ?[0-9])")), &t, " \u{e000}ಜನ\u{e001}");
    c.sub_tpl(&rx(&format!(r"(?<=[0-9]) ಆಗ(?= [{KN}])")), &t, " \u{e000}ಆಗ\u{e001}")
}

fn kn_pm_period(t: String, c: &mut Ctx) -> String {
    let pat =
        format!(r"([{KN}]+) (0?[1-9]|1[0-2])(?::([0-5][0-9]))? ?(?:pm|PM|p\.m\.|P\.M\.|am|AM|a\.m\.|A\.M\.)(?!\w)");
    c.sub(&rx(&pat), &t, |m| {
        if !PERIODS.contains(&g(m, 1)) {
            return None;
        }
        let hm = if g(m, 3).is_empty() { " ಗಂಟೆ".to_string() } else { format!(":{}", g(m, 3)) };
        Some(format!("{} {}{hm}", g(m, 1), py_int(g(m, 2))))
    })
}

fn kn_pm_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<=[0-9]) ?(pm|PM|am|AM)(?=[{KN}])")), &t, |m| {
        Some(format!(" {}", if matches!(g(m, 1), "pm" | "PM") { "ಪಿಎಂ" } else { "ಎಎಂ" }))
    })
}

fn kn_suffix(t: String, c: &mut Ctx) -> String {
    let pat =
        format!(r"(?<![\w.,:/–-])(?:([0-9]{{1,2}}):([0-5][0-9])|((?:{NUM})(?:\.[0-9]+)?))({})(?![{KN}])", tails());
    let src = t.clone();
    let after = format!(r" [{KN}]");
    c.sub(&rx(&pat), &t, |m| {
        let tail = g(m, 4);
        if tail == "ರ" && !matches_at_start(&after, &src[end0(m)..]) {
            return None;
        }
        if m.get(1).is_some() {
            let (h, mm) = (g(m, 1), g(m, 2));
            if py_int(h) > 23 || (mm.starts_with('0') && mm != "00") {
                return None;
            }
            let hw = words(&py_int(h).to_string(), "kn");
            if mm == "00" {
                return Some(format!("{hw} {}", inflect("ಗಂಟೆ", tail)));
            }
            return Some(format!("{hw} {}", inflect(&words(mm, "kn"), tail)));
        }
        Some(inflect(&year(g(m, 3))?, tail))
    })
}

fn kn_doctor(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&format!(r"(?<!\w)Dr\.? (?=[{KN}])")), &t, "ಡಾಕ್ಟರ್ ")
}

// ------------------------------------------------------------------------------------------------- money (see ta.rs)

const KN_SCALES: &[&str] = &["ಸಾವಿರ", "ಲಕ್ಷ", "ಕೋಟಿ"];
const KN_HALF_SCALES: &[&str] = &["ಸಾವಿರ", "ಲಕ್ಷ", "ಕೋಟಿ", "ಮಿಲಿಯನ್", "ಬಿಲಿಯನ್"];
/// Codes the grammar leaves unread (or misreads with decimals): (code, currency, the same, minor unit).
const KN_CODES: &[(&str, &str, &str, &str)] = &[
    ("LKR", "ಶ್ರೀಲಂಕಾ ರೂಪಾಯಿ", "ಶ್ರೀಲಂಕಾ ರೂಪಾಯಿ", "ಸೆಂಟ್"),
    ("QAR", "ಕತಾರ್ ರಿಯಾಲ್", "ಕತಾರ್ ರಿಯಾಲ್", "ದಿರ್ಹಾಮ್"),
    ("KWD", "ಕುವೈತ್ ದಿನಾರ್", "ಕುವೈತ್ ದಿನಾರ್", ""),
    ("BHD", "ಬಹ್ರೇನ್ ದಿನಾರ್", "ಬಹ್ರೇನ್ ದಿನಾರ್", ""),
    ("USD", "ಯುಎಸ್ ಡಾಲರ್", "ಯುಎಸ್ ಡಾಲರ್", "ಸೆಂಟ್"),
    ("JPY", "ಯೆನ್", "ಯೆನ್", ""),
    ("CNY", "ಯುವಾನ್", "ಯುವಾನ್", ""),
    ("KRW", "ವಾನ್", "ವಾನ್", ""),
    ("IDR", "ಇಂಡೋನೇಷಿಯನ್ ರೂಪಾಯಿ", "ಇಂಡೋನೇಷಿಯನ್ ರೂಪಾಯಿ", ""),
];
const KN_SIGNS: &[(&str, &str)] = &[("¥", "JPY"), ("₩", "KRW")];
const KN_PER: &[(&str, &str)] = &[
    ("ತಿಂಗಳು", "ತಿಂಗಳಿಗೆ"),
    ("ವರ್ಷ", "ವರ್ಷಕ್ಕೆ"),
    ("ದಿನ", "ದಿನಕ್ಕೆ"),
    ("ವಾರ", "ವಾರಕ್ಕೆ"),
    ("ಗಂಟೆ", "ಗಂಟೆಗೆ"),
    ("ಕೆಜಿ", "ಕೆಜಿಗೆ"),
    ("ಕಿಲೋ", "ಕಿಲೋಗೆ"),
    ("ಗ್ರಾಂ", "ಗ್ರಾಂಗೆ"),
    ("ಲೀಟರ್", "ಲೀಟರ್\u{200c}ಗೆ"),
    ("ಮೀಟರ್", "ಮೀಟರ್\u{200c}ಗೆ"),
    ("ವ್ಯಕ್ತಿ", "ವ್ಯಕ್ತಿಗೆ"),
    ("ರಾತ್ರಿ", "ರಾತ್ರಿಗೆ"),
    ("ಯೂನಿಟ್", "ಯೂನಿಟ್\u{200c}ಗೆ"),
    ("ಚದರ ಅಡಿ", "ಚದರ ಅಡಿಗೆ"),
    ("ಎಕರೆ", "ಎಕರೆಗೆ"),
    ("ಟನ್", "ಟನ್\u{200c}ಗೆ"),
    ("ಕ್ವಿಂಟಲ್", "ಕ್ವಿಂಟಲ್\u{200c}ಗೆ"),
    ("L", "ಲೀಟರ್\u{200c}ಗೆ"),
    ("kWh", "ಕಿಲೋವ್ಯಾಟ್ ಗಂಟೆಗೆ"),
    ("unit", "ಯೂನಿಟ್\u{200c}ಗೆ"),
    ("sqft", "ಚದರ ಅಡಿಗೆ"),
    ("sq ft", "ಚದರ ಅಡಿಗೆ"),
    ("sq.ft", "ಚದರ ಅಡಿಗೆ"),
    ("sq. ft", "ಚದರ ಅಡಿಗೆ"),
    ("m²", "ಚದರ ಮೀಟರ್\u{200c}ಗೆ"),
    ("t", "ಟನ್\u{200c}ಗೆ"),
    ("qtl", "ಕ್ವಿಂಟಲ್\u{200c}ಗೆ"),
    ("acre", "ಎಕರೆಗೆ"),
    ("piece", "ಒಂದಕ್ಕೆ"),
    ("pc", "ಒಂದಕ್ಕೆ"),
    ("person", "ವ್ಯಕ್ತಿಗೆ"),
    ("night", "ರಾತ್ರಿಗೆ"),
    ("week", "ವಾರಕ್ಕೆ"),
    ("kg", "ಕಿಲೋಗ್ರಾಂಗೆ"),
    ("km", "ಕಿಲೋಮೀಟರ್\u{200c}ಗೆ"),
    ("m", "ಮೀಟರ್\u{200c}ಗೆ"),
    ("hr", "ಗಂಟೆಗೆ"),
    ("h", "ಗಂಟೆಗೆ"),
    ("day", "ದಿನಕ್ಕೆ"),
    ("month", "ತಿಂಗಳಿಗೆ"),
    ("year", "ವರ್ಷಕ್ಕೆ"),
    ("l", "ಲೀಟರ್\u{200c}ಗೆ"),
    ("g", "ಗ್ರಾಂಗೆ"),
];
const KN_UNITS: &[(&str, &str)] = &[
    ("sq ft", "ಚದರ ಅಡಿ"),
    ("sq.ft", "ಚದರ ಅಡಿ"),
    ("sq. ft", "ಚದರ ಅಡಿ"),
    ("sqft", "ಚದರ ಅಡಿ"),
    ("acres", "ಎಕರೆ"),
    ("acre", "ಎಕರೆ"),
];
const KN_ARAB: &[&str] = &["ಅರಬ್", "ಖರಬ್"];

/// N and a half: 2 -> ಎರಡೂವರೆ, 25 -> ಇಪ್ಪತ್ತೈದೂವರೆ.
fn kn_and_half(n: u128) -> Option<String> {
    let sp = plain(&n.to_string())?;
    if !sp.ends_with('\u{0CC1}') {
        return None;
    }
    Some(format!("{}\u{0CC2}ವರೆ", drop_last(&sp)))
}

fn kn_amount(x: &str, scale: bool) -> Option<String> {
    if scale && full(r"[1-9][0-9]?\.5", x) {
        return kn_and_half(py_int(&x[..x.len() - 2]));
    }
    plain(x)
}

/// The ablative on the last word: ಐದು -> ಐದರಿಂದ, ಸಾವಿರ -> ಸಾವಿರದಿಂದ, ಪೈಸೆ -> ಪೈಸೆಯಿಂದ, a loanword ending in a consonant
/// with ನಿಂದ (ಸೆಂಟ್ -> ಸೆಂಟ್\u{200c}ನಿಂದ).
fn kn_from(sp: &str) -> String {
    if sp.ends_with('\u{0CCD}') {
        return format!("{sp}\u{200c}ನಿಂದ");
    }
    inflect(sp, "ರಿಂದ")
}

/// The first amount takes the ablative ರಿಂದ (ಐದರಿಂದ ಹತ್ತು ಡಾಲರ್), as kn.range reads 5-10.
fn kn_compose(a: &str, b: &str, cur: &str, after: bool, scale: &str) -> Option<String> {
    if !scale.is_empty() {
        let (aw, bw, cw) = (kn_amount(a, true)?, kn_amount(b, true)?, dr_cur_word(cur, after, "kn")?);
        return Some(format!("{} {bw} {scale} {cw}", kn_from(&aw)));
    }
    let aw = if a.contains('.') { words(&dr_money(cur, &dr_pad(a), after), "kn") } else { plain(a)? };
    Some(format!("{} {}", kn_from(&aw), words(&dr_money(cur, &dr_pad(b), after), "kn")))
}

fn kn_big(t: String, c: &mut Ctx) -> String {
    dr_big(t, c, "kn", |_| "ಕೋಟಿ", "ಕೋಟಿ", "ಕೋಟಿ", ("ಲಕ್ಷ", "ಲಕ್ಷ"), KN_ARAB)
}

fn kn_money_code(t: String, c: &mut Ctx) -> String {
    dr_code(t, c, "kn", KN_CODES, KN_SIGNS, &["ರೂಪಾಯಿ"], "ಪೈಸೆ", plain, |s| s.to_string())
}

fn kn_per(t: String, c: &mut Ctx) -> String {
    dr_per(t, c, KN_PER, KN_SCALES, &["ರೂಪಾಯಿ"], KN)
}

fn kn_money_range(t: String, c: &mut Ctx) -> String {
    dr_money_range(t, c, KN_SCALES, KN, kn_compose)
}

fn kn_half_scale(t: String, c: &mut Ctx) -> String {
    dr_half_scale(t, c, KN_HALF_SCALES, kn_and_half)
}

fn kn_units(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = KN_UNITS.iter().map(|&(k, _)| k).collect();
    let pat = format!(r"(?<=[0-9]) ?({})(?:\.(?= [^\W\d_]))?(?![A-Za-z])", dr_alt(&keys));
    c.sub(&rx(&pat), &t, |m| KN_UNITS.iter().find(|&&(k, _)| k == g(m, 1)).map(|&(_, w)| format!(" {w}")))
}

/// A scale word with a case ending after a rupee amount: (as written, the bare scale word, the rupee word with the ending).
const KN_SCALE_CASE: &[(&str, &str, &str)] = &[
    ("ಕೋಟಿಗೆ", "ಕೋಟಿ", "ರೂಪಾಯಿಗೆ"),
    ("ಕೋಟಿಯ", "ಕೋಟಿ", "ರೂಪಾಯಿಯ"),
    ("ಕೋಟಿಯಲ್ಲಿ", "ಕೋಟಿ", "ರೂಪಾಯಿಯಲ್ಲಿ"),
    ("ಕೋಟಿಯಿಂದ", "ಕೋಟಿ", "ರೂಪಾಯಿಯಿಂದ"),
    ("ಕೋಟಿಯಷ್ಟು", "ಕೋಟಿ", "ರೂಪಾಯಿಯಷ್ಟು"),
    ("ಕೋಟಿಯವರೆಗೆ", "ಕೋಟಿ", "ರೂಪಾಯಿಯವರೆಗೆ"),
    ("ಕೋಟಿಗಿಂತ", "ಕೋಟಿ", "ರೂಪಾಯಿಗಿಂತ"),
    ("ಕೋಟಿಗೂ", "ಕೋಟಿ", "ರೂಪಾಯಿಗೂ"),
    ("ಲಕ್ಷಕ್ಕೆ", "ಲಕ್ಷ", "ರೂಪಾಯಿಗೆ"),
    ("ಲಕ್ಷದ", "ಲಕ್ಷ", "ರೂಪಾಯಿಯ"),
    ("ಲಕ್ಷದಲ್ಲಿ", "ಲಕ್ಷ", "ರೂಪಾಯಿಯಲ್ಲಿ"),
    ("ಲಕ್ಷದಿಂದ", "ಲಕ್ಷ", "ರೂಪಾಯಿಯಿಂದ"),
    ("ಲಕ್ಷದಷ್ಟು", "ಲಕ್ಷ", "ರೂಪಾಯಿಯಷ್ಟು"),
    ("ಲಕ್ಷದವರೆಗೆ", "ಲಕ್ಷ", "ರೂಪಾಯಿಯವರೆಗೆ"),
    ("ಲಕ್ಷಕ್ಕಿಂತ", "ಲಕ್ಷ", "ರೂಪಾಯಿಗಿಂತ"),
    ("ಲಕ್ಷಕ್ಕೂ", "ಲಕ್ಷ", "ರೂಪಾಯಿಗೂ"),
    ("ಸಾವಿರಕ್ಕೆ", "ಸಾವಿರ", "ರೂಪಾಯಿಗೆ"),
    ("ಸಾವಿರದ", "ಸಾವಿರ", "ರೂಪಾಯಿಯ"),
    ("ಸಾವಿರದಲ್ಲಿ", "ಸಾವಿರ", "ರೂಪಾಯಿಯಲ್ಲಿ"),
    ("ಸಾವಿರದಿಂದ", "ಸಾವಿರ", "ರೂಪಾಯಿಯಿಂದ"),
    ("ಸಾವಿರದಷ್ಟು", "ಸಾವಿರ", "ರೂಪಾಯಿಯಷ್ಟು"),
    ("ಸಾವಿರದವರೆಗೆ", "ಸಾವಿರ", "ರೂಪಾಯಿಯವರೆಗೆ"),
    ("ಸಾವಿರಕ್ಕಿಂತ", "ಸಾವಿರ", "ರೂಪಾಯಿಗಿಂತ"),
    ("ಸಾವಿರಕ್ಕೂ", "ಸಾವಿರ", "ರೂಪಾಯಿಗೂ"),
];

fn kn_money_scale_case(t: String, c: &mut Ctx) -> String {
    dr_scale_case(t, c, KN_SCALE_CASE, KN)
}
