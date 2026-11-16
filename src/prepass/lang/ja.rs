//! 'ja' rules: the port of the workbench's `langrules/ja.py` (ids `ja.*`).
//!
//! The ja grammar gives up on a whole sentence when a space touches a digit (降水確率は 30 %です stays as typed), reads no
//! units, currencies or percent signs (五km, ¥五百, 五十%), reads N:M as a clock time with the minutes digit by digit
//! (九:零零), a comma-grouped number digit by digit (十四,零零零,零零零), drops the word for minus (-五度, even マイナス5 →
//! -五) and writes 荷 for と in a mixed fraction (an upstream typo). These rules rewrite the span into the form the grammar
//! reads right (30%, 5キロメートル, 500円, 9時, 1400万, 2対1, 2と1/2) or write the words (マイナス五).

use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, py_int_str, py_rstrip, rx, tpl};
use super::ko::{ROMAN_CHARS, alternation, roman_value};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ja.abbrev", ja_abbrev),
    ("ja.roman", ja_roman),
    ("ja.vs", ja_vs),
    ("ja.mixed-fraction", ja_mixed_fraction),
    ("ja.money", ja_money),
    ("ja.space", ja_space),
    ("ja.grouping", ja_grouping),
    ("ja.score", ja_score),
    ("ja.time", ja_time),
    ("ja.range", ja_range),
    ("ja.units", ja_units),
    ("ja.negative", ja_negative),
];

/// (written, spoken, said before the number)
const UNITS: &[(&str, &str, &str)] = &[
    ("km/h", "キロメートル", "時速"),
    ("m/s", "メートル", "秒速"),
    ("km²", "平方キロメートル", ""),
    ("cm²", "平方センチメートル", ""),
    ("m²", "平方メートル", ""),
    ("㎡", "平方メートル", ""),
    ("m³", "立方メートル", ""),
    ("㎥", "立方メートル", ""),
    ("cm³", "立方センチメートル", ""),
    ("km", "キロメートル", ""),
    ("㎞", "キロメートル", ""),
    ("cm", "センチメートル", ""),
    ("㎝", "センチメートル", ""),
    ("mm", "ミリメートル", ""),
    ("㎜", "ミリメートル", ""),
    ("m", "メートル", ""),
    ("kg", "キログラム", ""),
    ("㎏", "キログラム", ""),
    ("mg", "ミリグラム", ""),
    ("㎎", "ミリグラム", ""),
    ("g", "グラム", ""),
    ("mL", "ミリリットル", ""),
    ("ml", "ミリリットル", ""),
    ("㎖", "ミリリットル", ""),
    ("dL", "デシリットル", ""),
    ("dl", "デシリットル", ""),
    ("L", "リットル", ""),
    ("ℓ", "リットル", ""),
    ("cc", "シーシー", ""),
    ("㏄", "シーシー", ""),
    ("℃", "度", ""),
    ("°C", "度", ""),
    ("°F", "度", "華氏"),
    ("%", "パーセント", ""),
    ("％", "パーセント", ""),
    ("kWh", "キロワット時", ""),
    ("kW", "キロワット", ""),
    ("W", "ワット", ""),
    ("mAh", "ミリアンペア時", ""),
    ("V", "ボルト", ""),
    ("GHz", "ギガヘルツ", ""),
    ("MHz", "メガヘルツ", ""),
    ("kHz", "キロヘルツ", ""),
    ("Hz", "ヘルツ", ""),
    ("TB", "テラバイト", ""),
    ("GB", "ギガバイト", ""),
    ("MB", "メガバイト", ""),
    ("KB", "キロバイト", ""),
    ("kcal", "キロカロリー", ""),
    ("t", "トン", ""),
    ("ha", "ヘクタール", ""),
    ("dB", "デシベル", ""),
];
/// No unit has a regex metacharacter.
static UNIT_ALT: LazyLock<String> = LazyLock::new(|| alternation(&UNITS.iter().map(|u| u.0).collect::<Vec<_>>()));
/// A character of Japanese text (CJK punctuation, kana, kanji, full-width forms) or a sign read with the number.
const CJK: &str = concat!(
    r"[\x{3001}-\x{303F}\x{3040}-\x{30FF}\x{31F0}-\x{31FF}\x{3400}-\x{4DBF}\x{4E00}-\x{9FFF}\x{F900}-\x{FAFF}",
    r"\x{FF01}-\x{FF60}\x{FFE0}-\x{FFE6}%℃°㎞㎜㎝㎏㎎㎖㎡㎥㏄]"
);
const SPACE: &str = r"[ \t\x{A0}\x{3000}]+";
/// The end or start of a Latin word, a bracket, a quote or a backslash.
const LATIN: &str = r#"[A-Za-z()\[\]{}"'\\_`]"#;
/// A digit, or a fraction character the shared rule turns into digits.
const DIGIT: &str = r"[0-9½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]";
/// Not inside a verbatim span an earlier rule wrote (a spoken e-mail address).
const OUTSIDE: &str = r"(?![^\x{E000}\x{E001}]*\x{E001})";
const MONEY: &[(&str, &str)] =
    &[("¥", "円"), ("￥", "円"), ("$", "ドル"), ("＄", "ドル"), ("€", "ユーロ"), ("£", "ポンド"), ("₩", "ウォン")];
const SCORE_CUE: &str = concat!(
    r"[^。！？!?\n]{0,12}?(?:勝利|勝っ|勝ち|勝た|勝つ|勝と|負け|負か|敗れ|敗退|敗戦|下し|下す|破っ|破る|制し|制す|",
    r"引き分け|快勝|圧勝|完勝|惜敗|大勝|辛勝|逆転|リード)"
);
const COMPANY: &[(&str, &str)] = &[
    ("株", "株式会社"),
    ("有", "有限会社"),
    ("財", "財団法人"),
    ("社", "社団法人"),
    ("㈱", "株式会社"),
    ("㈲", "有限会社"),
    ("㈶", "財団法人"),
    ("㈳", "社団法人"),
];

fn lookup<'a>(table: &[(&str, &'a str)], key: &str) -> &'a str {
    table.iter().find(|(k, _)| *k == key).map_or("", |(_, v)| *v)
}

fn span(m: &Captures<'_, str>) -> (usize, usize) {
    let m0 = m.get(0).expect("group 0");
    (m0.start(), m0.end())
}

/// 14000000 → 1400万, 123456789 → 1億2345万6789: the grammar's own way of reading large numbers.
fn man(mut n: u128) -> String {
    let mut out = String::new();
    for (unit, size) in [("兆", 10u128.pow(12)), ("億", 10u128.pow(8)), ("万", 10u128.pow(4))] {
        if n >= size {
            out.push_str(&format!("{}{unit}", n / size));
            n %= size;
        }
    }
    if n != 0 {
        out.push_str(&n.to_string());
    }
    out
}

fn ja_abbrev(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"[(（]([株有財社])[)）]|([㈱㈲㈶㈳])"), &t, |m| {
        Some(lookup(COMPANY, if g(m, 1).is_empty() { g(m, 2) } else { g(m, 1) }).to_string())
    })
}

fn ja_roman(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"第\s?([IVXLC]+|[{ROMAN_CHARS}])(?=\s?(?:章|部|巻|編|話|幕|期|弾|回|代|条|項|節|版|世代|次|楽章|集|課|戦))"
    );
    c.sub(&rx(&pat), &t, |m| {
        let n = roman_value(g(m, 1));
        if n != 0 { Some(format!("第{n}")) } else { None }
    })
}

fn ja_vs(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<=\s)(?:vs|VS|Vs)\.?(?=\s)"), &t, "対");
    let pat = r"(?<=[\x{3040}-\x{30FF}\x{4E00}-\x{9FFF}])(?:vs|VS)\.?(?=[\x{3040}-\x{30FF}\x{4E00}-\x{9FFF}])";
    c.sub_tpl(&rx(pat), &t, "対")
}

fn ja_mixed_fraction(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\d/.,])(\d+)[ \x{A0}](\d+)/(\d+)(?![\d/])"), &t, r"\1と\2/\3")
}

fn ja_space(t: String, c: &mut Ctx) -> String {
    let keep = |m: &Captures<'_, str>| Some(format!("\u{e000}{}\u{e001}", &m[0]));
    let t = c.sub_tpl(&rx(&format!(r"(?<={DIGIT}){SPACE}(?={CJK}|(?:{})(?![A-Za-z])){OUTSIDE}", *UNIT_ALT)), &t, "");
    let t = c.sub_tpl(&rx(&format!(r"(?<={CJK}){SPACE}(?=[-－]?{DIGIT}){OUTSIDE}")), &t, "");
    let pat = format!(r"(?:(?<={LATIN}){SPACE}(?={DIGIT}|{CJK})|(?<={DIGIT}|{CJK}){SPACE}(?={LATIN})){OUTSIDE}");
    let t = c.sub(&rx(&pat), &t, keep);
    let pat = format!(
        r"(?:(?<={DIGIT}|{LATIN})[ \t\x{{A0}}\x{{3000}}]*\n\s*(?={DIGIT}|{LATIN}|{CJK})|(?<={CJK})[ \t\x{{A0}}\x{{3000}}]*\n\s*(?={DIGIT}|{LATIN})){OUTSIDE}"
    );
    c.sub(&rx(&pat), &t, keep)
}

fn ja_money(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![A-Za-z])([¥￥$＄€£₩])\s?(\d[\d,]*(?:\.\d+)?)(万|億|兆)?(?![\d.])"), &t, |m| {
        let mut num = g(m, 2).to_string();
        if let Ok(Some(mm)) = rx(r"^(?:([\d,]+)\.(\d)0)\z").captures(g(m, 2)) {
            num = format!("{}{}", g(&mm, 1), if g(&mm, 2) == "0" { String::new() } else { format!(".{}", g(&mm, 2)) });
        }
        Some(format!("{num}{}{}", g(m, 3), lookup(MONEY, g(m, 1))))
    })
}

fn ja_grouping(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d,.])\d{1,3}(?:,\d{3})+(?![\d,])"), &t, |m| {
        let digits = m[0].replace(',', "");
        let n: u128 = py_int_str(&digits).parse().unwrap_or(u128::MAX);
        Some(if !(10_000..10u128.pow(16)).contains(&n) { digits } else { man(n) })
    })
}

fn ja_score(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\d:.])(\d{1,3})[:：](\d{1,3})(?![\d:]|\.\d)"), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        let clock = b.chars().count() == 2 && py_int(a) <= 24 && py_int(b) <= 59;
        if clock && !matches_at_start(SCORE_CUE, &t[span(m).1..]) {
            return None;
        }
        Some(format!("{a}対{b}"))
    });
    c.sub(&rx(r"(?<![\d.:/-])(\d{1,3})[-－](\d{1,3})(?![\d:/-]|\.\d)"), &t, |m| {
        if matches_at_start(SCORE_CUE, &t[span(m).1..]) { Some(format!("{}対{}", g(m, 1), g(m, 2))) } else { None }
    })
}

fn ja_time(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d:.])([01]?\d|2[0-4]):([0-5]\d)(?::([0-5]\d))?(?![\d:]|\.\d)"), &t, |m| {
        let mut out = format!("{}時", py_int(g(m, 1)));
        if py_int(g(m, 2)) != 0 {
            out.push_str(&format!("{}分", py_int(g(m, 2))));
        }
        if !g(m, 3).is_empty() && py_int(g(m, 3)) != 0 {
            out.push_str(&format!("{}秒", py_int(g(m, 3))));
        }
        Some(out)
    })
}

fn ja_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<=\d[時分秒])\s?[-~～–—]\s?(?=\d)"), &t, "〜");
    let pat = concat!(
        r"(?<![\d.:/,=+*×÷-])([0-9]+(?:\.[0-9]+)?)\s?([-~～–—])\s?([0-9]+(?:\.[0-9]+)?)",
        r"(?![\d:/-]|\.\d|\s?[=＝+*×÷])"
    );
    let after = format!(r"{CJK}|(?:{})(?![A-Za-z])", *UNIT_ALT);
    c.sub(&rx(pat), &t, |m| {
        let (a, sep, b) = (g(m, 1), g(m, 2), g(m, 3));
        let num = |x: &str| x.parse::<f64>().unwrap_or(0.0);
        if sep == "-"
            && (num(a) >= num(b) || (a.starts_with('0') && a != "0") || !matches_at_start(&after, &t[span(m).1..]))
        {
            return None;
        }
        Some(format!("{a}〜{b}"))
    })
}

fn ja_units(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![0-9A-Za-z.,/])(\d+(?:\.\d+)?)({})(?![A-Za-z0-9²³/])", *UNIT_ALT);
    c.sub(&rx(&pat), &t, |m| {
        let &(_, w, p) = UNITS.iter().find(|u| u.0 == g(m, 2)).expect("unit");
        let p = if !p.is_empty() && py_rstrip(&t[..span(m).0]).ends_with(p) { "" } else { p }; // 時速100km/h
        Some(format!("{p}{}{w}", g(m, 1)))
    })
}

fn ja_negative(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![0-9A-Za-z)\]）}.,_/])(?:マイナス|[-－])(\d+(?:\.\d+)?)(?![\d.]|/\d)"), &t, |m| {
        Some(format!("マイナス{}", words(g(m, 1), "ja")))
    });
    // ja.units already wrote the unit said before the number (-12°F → -華氏十二度)
    c.sub(&rx(r"(?<![0-9A-Za-z)\]）}.,_/])[-－](?=華氏|時速|秒速)"), &t, |_| Some("マイナス".to_string()))
}
