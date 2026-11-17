//! 'ja' rules: the port of the workbench's `langrules/ja.py` (ids `ja.*`).
//!
//! The ja grammar gives up on a whole sentence when a space touches a digit (降水確率は 30 %です stays as typed), reads no
//! units, currencies, currency codes or percent signs (五km, ¥五百, 五€, USD 五, 五十%), reads N:M as a clock time with the
//! minutes digit by digit (九:零零), a comma-grouped number digit by digit (十四,零零零,零零零), drops the word for minus
//! (-五度, even マイナス5 → -五) and writes 荷 for と in a mixed fraction (an upstream typo). These rules rewrite the span
//! into the form the grammar reads right (30%, 5キロメートル, 500円, 5ユーロ, 20米ドル, 9時, 1400万, 2対1, 2と1/2) or write
//! the words (マイナス五).

use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, py_int_str, py_rstrip, rx, search, tpl};
use super::ko::{ROMAN_CHARS, alternation, roman_value};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ja.abbrev", ja_abbrev),
    ("ja.roman", ja_roman),
    ("ja.vs", ja_vs),
    ("ja.mixed-fraction", ja_mixed_fraction),
    ("ja.groups", ja_groups),
    ("ja.money", ja_money),
    ("ja.money-code", ja_money_code),
    ("ja.money-after", ja_money_after),
    ("ja.money-range", ja_money_range),
    ("ja.per", ja_per),
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
/// Currency codes written after the amount (20 USD): each names its currency.
const CODES: &[(&str, &str)] = &[
    ("USD", "米ドル"),
    ("EUR", "ユーロ"),
    ("GBP", "英ポンド"),
    ("JPY", "円"),
    ("CNY", "人民元"),
    ("RMB", "人民元"),
    ("KRW", "ウォン"),
    ("HKD", "香港ドル"),
    ("TWD", "台湾ドル"),
    ("AUD", "豪ドル"),
    ("CAD", "カナダドル"),
    ("CHF", "スイスフラン"),
    ("SGD", "シンガポールドル"),
    ("NZD", "ニュージーランドドル"),
    ("BRL", "ブラジルレアル"),
    ("MXN", "メキシコペソ"),
    ("INR", "インドルピー"),
    ("THB", "タイバーツ"),
    ("PHP", "フィリピンペソ"),
    ("VND", "ベトナムドン"),
    ("IDR", "インドネシアルピア"),
    ("MYR", "マレーシアリンギット"),
    ("RUB", "ロシアルーブル"),
];
/// All three letters.
static CODE_ALT: LazyLock<String> = LazyLock::new(|| CODES.iter().map(|c| c.0).collect::<Vec<_>>().join("|"));
/// An amount with its sign before it (KRW 76,197$).
static SIGN_BEFORE: LazyLock<String> = LazyLock::new(|| format!(r"(?:[¥￥$＄€£₩]|(?<![A-Za-z])(?:{}))$", *CODE_ALT));
/// The currency words the money rules write after an amount (円, ドル, 米ドル, 香港ドル …), longest first.
static WORD_ALT: LazyLock<String> = LazyLock::new(|| {
    let mut ws: Vec<&str> = Vec::new();
    for &(_, w) in MONEY.iter().chain(CODES.iter()) {
        if !ws.contains(&w) {
            ws.push(w);
        }
    }
    alternation(&ws)
});
/// An amount as the money rules leave it (1,500, 5.5).
const AMT: &str = r"\d(?:[\d,]*\d)?(?:\.\d+)?";

fn value(num: &str) -> f64 {
    num.replace(',', "").parse::<f64>().unwrap_or(0.0)
}
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
    let pat = format!(
        r"(?:(?<={LATIN}){SPACE}(?={DIGIT}|{CJK})|(?<={DIGIT}|{CJK}){SPACE}(?={LATIN})|(?<=,)\s+(?={DIGIT})){OUTSIDE}"
    );
    let t = c.sub(&rx(&pat), &t, keep);
    let pat = format!(
        r"(?:(?<={DIGIT}|{LATIN})[ \t\r\x{{A0}}\x{{3000}}]*\n\s*(?={DIGIT}|{LATIN}|{CJK})|(?<={CJK})[ \t\r\x{{A0}}\x{{3000}}]*\n\s*(?={DIGIT}|{LATIN})){OUTSIDE}"
    );
    c.sub(&rx(&pat), &t, keep)
}

fn ja_money(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![A-Za-z])([¥￥$＄€£₩])\s?(\d(?:[\d,]*\d)?(?:\.\d+)?)(万|億|兆)?(?!\d|\.\d)"), &t, |m| {
        Some(format!("{}{}{}", cents(g(m, 2)), g(m, 3), lookup(MONEY, g(m, 1))))
    })
}

/// A two-decimal amount ending in 0 drops the 0 (1.50 → 1.5, 5.00 → 5).
fn cents(num: &str) -> String {
    if let Ok(Some(mm)) = rx(r"^(?:([\d,]+)\.(\d)0)\z").captures(num) {
        return format!("{}{}", g(&mm, 1), if g(&mm, 2) == "0" { String::new() } else { format!(".{}", g(&mm, 2)) });
    }
    num.to_string()
}

fn ja_money_code(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![A-Za-z])({})\s?(\d(?:[\d,]*\d)?(?:\.\d+)?)(万|億|兆)?(?!\d|\.\d)", *CODE_ALT);
    c.sub(&rx(&pat), &t, |m| Some(format!("{}{}{}", cents(g(m, 2)), g(m, 3), lookup(CODES, g(m, 1)))))
}

fn ja_money_after(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?<![0-9A-Za-z.,:/])(\d(?:[\d,]*\d)?(?:\.\d+)?)(万|億|兆)?\s?([¥￥$＄€£₩]|{})(?![A-Za-z0-9$＄€£¥￥₩￦])(?!\s?\d)",
        *CODE_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        if search(&SIGN_BEFORE, py_rstrip(&t[..span(m).0])) {
            return None;
        }
        let word =
            if MONEY.iter().any(|(k, _)| *k == g(m, 3)) { lookup(MONEY, g(m, 3)) } else { lookup(CODES, g(m, 3)) };
        Some(format!("{}{}{word}", cents(g(m, 1)), g(m, 2)))
    })
}

fn ja_grouping(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\d,.])(\d{1,3}(?:,\d{3})+)(\.\d+)?(?![\d,])"), &t, |m| {
        let digits = g(m, 1).replace(',', "");
        if !g(m, 2).is_empty() {
            return Some(format!("{digits}{}", g(m, 2))); // 2,000,000.5 → 2000000.5 (二百万点五), not 200万.5
        }
        let n: u128 = py_int_str(&digits).parse().unwrap_or(u128::MAX);
        Some(if !(10_000..10u128.pow(16)).contains(&n) { digits } else { man(n) })
    });
    // a plain amount of 10^12 and up before a currency word (the grammar read 2000000000000円 as 二千億零円)
    let pat = format!(r"(?<![\d,.])\d{{13,16}}(?![\d,]|\.\d)(?=(?:万|億|兆)?(?:{}))", *WORD_ALT);
    c.sub(&rx(&pat), &t, |m| Some(man(py_int(&m[0]))))
}

fn ja_groups(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?<![\dA-Za-z.,/:+\-–])(?<!\d[ \x{A0}\x{202F}])[1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+(?!\d|[.,]\d{3})",
        r"(?![ \x{A0}\x{202F}]\d)"
    );
    let after = format!(
        r"[ \x{{A0}}\x{{202F}}]?(?:[¥￥$＄€£₩]|(?:{}|{})(?![A-Za-z])|[\x{{3040}}-\x{{30FF}}\x{{4E00}}-\x{{9FFF}}])",
        *CODE_ALT, *UNIT_ALT
    );
    c.sub(&rx(pat), &t, |m| {
        let w = m.get(0).expect("group 0");
        let gaps = w.as_str().chars().filter(|&ch| matches!(ch, ' ' | '\u{a0}' | '\u{202f}')).count();
        if gaps < 2
            && !super::super::search(r"[$€£¥₩₱฿₫₹] ?$", &t[..w.start()])
            && !matches_at_start(&after, &t[w.end()..])
        {
            return None;
        }
        Some(w.as_str().chars().map(|ch| if matches!(ch, ' ' | '\u{a0}' | '\u{202f}') { ',' } else { ch }).collect())
    })
}

fn ja_money_range(t: String, c: &mut Ctx) -> String {
    let w = &*WORD_ALT;
    let pat = format!(r"(?<![\d.,])({AMT}(?:万|億|兆)?)({w})\s?([-~～–—〜])\s?({AMT}(万|億|兆)?)({w})");
    let t = c.sub(&rx(&pat), &t, |m| {
        if g(m, 2) != g(m, 6) || (g(m, 3) == "-" && value(g(m, 1)) >= value(g(m, 4))) {
            return None;
        }
        Some(format!("{}{}〜{}{}", g(m, 1), g(m, 2), g(m, 4), g(m, 6)))
    });
    let pat = format!(
        r"(?<![\d.,])({AMT}(?:万|億|兆)?)({w})\s?([-~～–—〜])\s?({AMT}(?:万|億|兆)?)(?![\d.,]|万|億|兆|[A-Za-z%％]|{}|{w})",
        *UNIT_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        if g(m, 3) == "-" && value(g(m, 1)) >= value(g(m, 4)) {
            return None;
        }
        Some(format!("{}〜{}{}", g(m, 1), g(m, 4), g(m, 2)))
    })
}

/// (written after the slash, said before あたり)
const PER: &[(&str, &str)] = &[
    ("月", "1か月"),
    ("ヶ月", "1か月"),
    ("か月", "1か月"),
    ("年", "1年"),
    ("日", "1日"),
    ("週", "1週間"),
    ("時間", "1時間"),
    ("人", "1人"),
    ("名", "1名"),
    ("泊", "1泊"),
    ("回", "1回"),
    ("個", "1個"),
    ("枚", "1枚"),
    ("本", "1本"),
    ("杯", "1杯"),
    ("台", "1台"),
    ("冊", "1冊"),
    ("件", "1件"),
    ("kg", "1キログラム"),
    ("㎏", "1キログラム"),
    ("g", "1グラム"),
    ("L", "1リットル"),
    ("m²", "1平方メートル"),
    ("㎡", "1平方メートル"),
    ("m", "1メートル"),
    ("km", "1キロメートル"),
    ("kWh", "1キロワット時"),
    ("m³", "1立方メートル"),
    ("㎥", "1立方メートル"),
];

fn ja_per(t: String, c: &mut Ctx) -> String {
    let per_alt = alternation(&PER.iter().map(|u| u.0).collect::<Vec<_>>());
    let pat = format!(
        r"(?<![\d.,])({AMT}(?:万|億|兆)?({}))\s?/\s?(\d+(?:\.\d+)?)?({per_alt})(?![A-Za-z0-9²³\x{{4E00}}-\x{{9FFF}}])",
        *WORD_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        let unit = lookup(PER, g(m, 4));
        let unit = if !g(m, 3).is_empty() {
            if !search(r"^[A-Za-z㎏㎡]", g(m, 4)) {
                return None; // /3月 is a date
            }
            format!("{}{}", g(m, 3), &unit[1..])
        } else {
            unit.to_string()
        };
        Some(format!("{unit}あたり{}", g(m, 1)))
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
