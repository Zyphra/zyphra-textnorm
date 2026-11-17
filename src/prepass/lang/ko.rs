//! 'ko' rules: the port of the workbench's `langrules/ko.py` (ids `ko.*`).
//!
//! The ko grammar reads a number before a counter in the native system only when nothing follows the counter (우유 2개
//! → 두개, but 우유 2개. / 2개를 → 이 개), splits particles off times, money, units and decimals (삼십분 에), and does
//! not read ℃, m², GB, a % before a particle, a comma-grouped number, a currency after the amount (5 €), £, the codes
//! USD/GBP/CNY/HKD, or a two-decimal amount of money ($1.25 → 일 달러이십오). These rules write the spoken words themselves
//! for those spans (the grammar passes Hangul through), using the grammar's own Sino-Korean reading of the digits, and
//! leave a span alone where the grammar already says the same words.
//!
//! The grammar reads a lone 일 (and 월 화 수 목 금 토, and 일월) as a weekday, so a written 일 that stands alone
//! (일 킬로그램, 이 대 일) is kept verbatim (U+E000 … U+E001).

use std::cmp::Reverse;
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{
    Ctx, after, before, g, matches_at_start, py_int, py_int_str, py_rstrip, rx, search, sub_plain, tpl,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::is_py_space;

pub(super) const RULES: &[LangRule] = &[
    ("ko.abbrev", ko_abbrev),
    ("ko.roman", ko_roman),
    ("ko.vs", ko_vs),
    ("ko.groups", ko_groups),
    ("ko.grouping", ko_grouping),
    ("ko.per", ko_per),
    ("ko.money", ko_money),
    ("ko.date-dots", ko_date_dots),
    ("ko.score", ko_score),
    ("ko.time", ko_time),
    ("ko.money-range", ko_money_range),
    ("ko.range", ko_range),
    ("ko.money-after", ko_money_after),
    ("ko.money-before", ko_money_before),
    ("ko.minus-temp", ko_minus_temp),
    ("ko.units", ko_units),
    ("ko.scale", ko_scale),
    ("ko.counter", ko_counter),
    ("ko.times", ko_times),
    ("ko.month", ko_month),
    ("ko.weekday", ko_weekday),
    ("ko.decimal", ko_decimal),
];

const ONES: [&str; 10] = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"];
const TENS: [&str; 10] = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"];

/// 1–99 in native Korean, in the form used before a counter: 한, 두, 세, 네, 스무, 스물한 … 아흔아홉.
fn native(n: u128) -> String {
    let (t, u) = ((n / 10) as usize, (n % 10) as usize);
    if u == 0 {
        return if t == 2 { "스무".to_string() } else { TENS[t].to_string() };
    }
    format!("{}{}", TENS[t], ONES[u])
}

/// The grammar's Sino-Korean reading of a plain number (1234 → 천이백삼십사, 3.5 → 삼점오).
fn sino(n: &str) -> String {
    words(n, "ko")
}

fn hangul(ch: char) -> bool {
    ('가'..='힣').contains(&ch)
}

fn name_char(ch: char) -> bool {
    hangul(ch) || ch.is_ascii_alphanumeric()
}

/// Longest first, ties in table order.
pub(super) fn alternation(items: &[&str]) -> String {
    let mut v = items.to_vec();
    v.sort_by_key(|x| Reverse(x.chars().count()));
    v.join("|")
}

/// A lone 일 (or 월 … 토, or 일월) in written words, kept verbatim: the grammar would read it as a weekday.
fn guard(s: &str) -> String {
    sub_plain(&rx(r"(?<![가-힣])일월|(?<![가-힣])[일월화수목금토](?![가-힣])"), s, |m| {
        Some(format!("\u{e000}{}\u{e001}", &m[0]))
    })
}

/// True when the grammar already says `mine` for `span` (spaces aside): the span is followed by a space, the end or
/// punctuation, and the grammar's reading of it (with that punctuation) is the same words.
fn kept(s: &str, end: usize, span: &str, mine: &str) -> bool {
    let p = match s[end..].chars().next() {
        None => String::new(),
        Some(ch) if is_py_space(ch) => String::new(),
        Some(ch) if ".,!?;:)]".contains(ch) => ch.to_string(),
        Some(_) => return false,
    };
    words(&format!("{span}{p}"), "ko").replace(' ', "") == format!("{mine}{p}").replace(' ', "")
}

/// `mine` for the match at `start`, with a space before it when it is glued to a Hangul word (우유2개 → 우유 두 개).
fn put(s: &str, start: usize, mine: &str) -> String {
    let lead = if start > 0 && hangul(before(s, start, ' ')) { " " } else { "" };
    format!("{lead}{}", guard(mine))
}

fn span(m: &Captures<'_, str>) -> (usize, usize) {
    let m0 = m.get(0).expect("group 0");
    (m0.start(), m0.end())
}

/// Group 1 of `^(?:pat)` on `s`, when it matches.
fn lead_group(pat: &str, s: &str) -> Option<String> {
    match rx(&format!("^(?:{pat})")).captures(s) {
        Ok(Some(m)) => Some(g(&m, 1).to_string()),
        _ => None,
    }
}

/// Counters read with native numbers (1–99), each with the syllables that may not follow it (개월, 개국, 달러, 시즌 and
/// 배속 are other words). 시 (an hour) also needs n <= 23, 대 a particle or the end after it, 장 no verse after it.
const NATIVE: &[(&str, &str)] = &[
    ("번째", ""),
    ("시간", ""),
    ("가지", ""),
    ("마리", ""),
    ("그릇", ""),
    ("켤레", ""),
    ("송이", ""),
    ("자루", ""),
    ("군데", ""),
    ("사람", ""),
    ("차례", ""),
    ("바퀴", ""),
    ("봉지", ""),
    ("상자", ""),
    ("접시", ""),
    ("모금", ""),
    ("걸음", ""),
    ("그루", ""),
    ("개", "월|국|년|소|교|조|항|사|관"),
    ("명", ""),
    ("살", ""),
    ("달", "러"),
    ("병", "동|원"),
    ("권", ""),
    ("잔", ""),
    ("장", "관|군|교|기|면|소|점|학|님"),
    ("벌", ""),
    ("척", ""),
    ("채", ""),
    ("통", "화|계|신|장|일|합|령|증"),
    ("곳", ""),
    ("줄", ""),
    ("쌍", ""),
    ("끼", ""),
    ("배", "속|수|율|송|달|포|우|구|추"),
    ("알", ""),
    ("갑", ""),
    ("컵", ""),
    ("시", "간|즌|리즈|청|장|민|내|외|대|점|기|각|군|험|작|설"),
    ("대", ""),
];
/// Counters read with Sino numbers that the grammar spaces or splits inconsistently (삼십분 에) or misreads (3개월 →
/// 세개 월요일): written here too.
const SINO: &[(&str, &str)] = &[("개월", ""), ("분", "의|기|야|량|할|류|석|당|배"), ("초", "등|과|반|점|기|안|대")];
static NATIVE_IN_RANGE: LazyLock<Vec<&str>> =
    LazyLock::new(|| NATIVE.iter().map(|(w, _)| *w).filter(|w| *w != "대").collect());

fn counter_alt(table: &[(&str, &str)]) -> String {
    let mut items = table.to_vec();
    items.sort_by_key(|x| Reverse(x.0.chars().count()));
    items
        .iter()
        .map(|(w, g)| if g.is_empty() { w.to_string() } else { format!("{w}(?!{g})") })
        .collect::<Vec<_>>()
        .join("|")
}

/// What may follow 대 for it to be the native counter (자동차 2대를, 2대.); before a space it is as often an ordinal
/// or a group (19대 대통령, 3대 영화제), so it is left to the grammar there.
const DAE_NEXT: &str = r"[가를는은의와과도만씩나이에로]|[.,!?)\]]|$";
const COPULA: &str = r"(?:입니다|입니까|이었|이다|이며|이고|이라|이에요|예요|이지|이면|이므로|이니)";
const PARTICLE: &str = r"(?:으로|에서|에게|부터|까지|보다|처럼|만큼|이나|은|는|이|가|을|를|에|의|와|과|도|만|로|쯤)";
/// (written, spoken, said before the number)
const UNITS: &[(&str, &str, &str)] = &[
    ("km/h", "킬로미터", "시속"),
    ("m/s", "미터", "초속"),
    ("km²", "제곱킬로미터", ""),
    ("cm²", "제곱센티미터", ""),
    ("m²", "제곱미터", ""),
    ("㎡", "제곱미터", ""),
    ("m³", "세제곱미터", ""),
    ("㎥", "세제곱미터", ""),
    ("km", "킬로미터", ""),
    ("㎞", "킬로미터", ""),
    ("cm", "센티미터", ""),
    ("㎝", "센티미터", ""),
    ("mm", "밀리미터", ""),
    ("㎜", "밀리미터", ""),
    ("m", "미터", ""),
    ("kg", "킬로그램", ""),
    ("㎏", "킬로그램", ""),
    ("mg", "밀리그램", ""),
    ("g", "그램", ""),
    ("ml", "밀리리터", ""),
    ("mL", "밀리리터", ""),
    ("㎖", "밀리리터", ""),
    ("L", "리터", ""),
    ("ℓ", "리터", ""),
    ("℃", "도", ""),
    ("°C", "도", ""),
    ("°F", "도", "화씨"),
    ("%p", "퍼센트포인트", ""),
    ("%", "퍼센트", ""),
    ("％", "퍼센트", ""),
    ("kWh", "킬로와트시", ""),
    ("kW", "킬로와트", ""),
    ("W", "와트", ""),
    ("mAh", "밀리암페어시", ""),
    ("GHz", "기가헤르츠", ""),
    ("MHz", "메가헤르츠", ""),
    ("kHz", "킬로헤르츠", ""),
    ("Hz", "헤르츠", ""),
    ("TB", "테라바이트", ""),
    ("GB", "기가바이트", ""),
    ("MB", "메가바이트", ""),
    ("KB", "킬로바이트", ""),
    ("kcal", "킬로칼로리", ""),
    ("ha", "헥타르", ""),
    ("t", "톤", ""),
];
/// No unit has a regex metacharacter.
static UNIT_ALT: LazyLock<String> = LazyLock::new(|| alternation(&UNITS.iter().map(|u| u.0).collect::<Vec<_>>()));
/// Signs and codes written after the amount (5 €, 20 USD), with the grammar's word for each (its sign-first reading of
/// € $ ¥ ₩ and of EUR 5, JPY 5, CAD 5, CHF 5 …; £, GBP, USD, CNY, HKD … are not in its table).
const MONEY_AFTER: &[(&str, &str)] = &[
    ("€", "유로"),
    ("$", "달러"),
    ("＄", "달러"),
    ("£", "파운드"),
    ("¥", "엔"),
    ("￥", "엔"),
    ("₩", "원"),
    ("￦", "원"),
    ("USD", "달러"),
    ("EUR", "유로"),
    ("GBP", "파운드"),
    ("JPY", "엔"),
    ("CNY", "위안"),
    ("RMB", "위안"),
    ("KRW", "원"),
    ("HKD", "홍콩 달러"),
    ("TWD", "대만 달러"),
    ("AUD", "호주 달러"),
    ("CAD", "캐나다 달러"),
    ("CHF", "스위스 프랑"),
    ("SGD", "싱가포르 달러"),
    ("NZD", "뉴질랜드 달러"),
    ("BRL", "브라질 헤알"),
    ("MXN", "멕시코 페소"),
    ("INR", "인도 루피"),
    ("THB", "태국 바트"),
    ("PHP", "필리핀 페소"),
    ("VND", "베트남 동"),
    ("IDR", "인도네시아 루피아"),
    ("MYR", "말레이시아 링깃"),
    ("RUB", "러시아 루블"),
];
/// A scale word after the digits of an amount.
const SCALE_ALT: &str = "천만|백만|십만|만(?!큼)|억|조|천|백";
/// Currency words written after the amount (5달러-10달러).
const WORD_AFTER: &str = "원|달러|유로|엔|파운드|위안";
/// All three letters.
static CODE_ALT: LazyLock<String> = LazyLock::new(|| {
    MONEY_AFTER.iter().map(|m| m.0).filter(|k| k.chars().all(char::is_alphabetic)).collect::<Vec<_>>().join("|")
});
static MONEY_ALT: LazyLock<String> = LazyLock::new(|| format!(r"[€$＄£¥￥₩￦]|{}", *CODE_ALT));
/// An amount with its sign before it.
static SIGN_BEFORE: LazyLock<String> = LazyLock::new(|| format!(r"(?:[€$＄£¥￥₩￦]|(?<![A-Za-z])(?:{}))$", *CODE_ALT));
/// What may follow an amount of money glued: 5 €입니다, 5 €를.
static AFTER_MONEY: LazyLock<String> = LazyLock::new(|| format!(r"{COPULA}|였|{PARTICLE}+(?![가-힣])"));
static RANGE_AFTER: LazyLock<String> = LazyLock::new(|| {
    let mut items = NATIVE_IN_RANGE.clone();
    items.extend(["분", "초", "일", "주", "개월", "년", "층", "회", "세", "도", "원", "학년", "퍼센트"]);
    format!("{}|{}|{}", alternation(&items), *UNIT_ALT, *MONEY_ALT)
});
const TEMP_CUE: &str = r"기온|온도|최저|최고|체감|수온|영하|영상|추위|한파|날씨|섭씨";
const SCORE_CUE: &str = concat!(
    r"[^.!?\n]{0,15}?(?:이겼|이기|이긴|졌|지고|패배|패했|패하|승리|비겼|비기|무승부|꺾|제압|격파|역전|대승|완승|완패|",
    r"석패|신승|앞서|뒤져)"
);
pub(super) const ROMAN_CHARS: &str = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ";
const MONTHS: [&str; 13] =
    ["", "일월", "이월", "삼월", "사월", "오월", "유월", "칠월", "팔월", "구월", "시월", "십일월", "십이월"];
const COMPANY: &[(&str, &str)] = &[
    ("주", "주식회사"),
    ("유", "유한회사"),
    ("재", "재단법인"),
    ("㈜", "주식회사"),
    ("㈲", "유한회사"),
    ("㈶", "재단법인"),
];

fn lookup<'a>(table: &[(&str, &'a str)], key: &str) -> &'a str {
    table.iter().find(|(k, _)| *k == key).map_or("", |(_, v)| *v)
}

fn roman_digit(c: char) -> i64 {
    match c {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        'C' => 100,
        _ => 0,
    }
}

/// II → 2, XIV → 14, Ⅲ → 3; 0 when s is not a well-formed numeral below 90.
pub(super) fn roman_value(s: &str) -> i64 {
    let cs: Vec<char> = s.chars().collect();
    if cs.len() == 1
        && let Some(i) = ROMAN_CHARS.chars().position(|x| x == cs[0])
    {
        return i as i64 + 1;
    }
    let mut total: i64 = 0;
    for (i, &ch) in cs.iter().enumerate() {
        let v = roman_digit(ch);
        total += if i + 1 < cs.len() && roman_digit(cs[i + 1]) > v { -v } else { v };
    }
    if 0 < total && total < 90 && roman(total) == s { total } else { 0 }
}

fn roman(mut n: i64) -> String {
    let mut out = String::new();
    for (v, r) in [(50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")] {
        while n >= v {
            out.push_str(r);
            n -= v;
        }
    }
    out
}

fn ko_abbrev(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"[(（]([주유재])[)）]|([㈜㈲㈶])"), &t, |m| {
        let word = lookup(COMPANY, if g(m, 1).is_empty() { g(m, 2) } else { g(m, 1) });
        let (s, e) = span(m);
        if s > 0 && name_char(before(&t, s, ' ')) {
            return Some(format!(" {word}"));
        }
        if e < t.len() && name_char(after(&t, e, ' ')) {
            return Some(format!("{word} "));
        }
        Some(word.to_string())
    })
}

fn ko_roman(t: String, c: &mut Ctx) -> String {
    let pat =
        format!(r"제\s?([IVXLC]+|[{ROMAN_CHARS}])(?=\s?(?:부|장|편|권|막|차|회|기|대|조|항|과|절|화|탄|시즌|세대))");
    c.sub(&rx(&pat), &t, |m| {
        let n = roman_value(g(m, 1));
        if n != 0 { Some(format!("제{n}")) } else { None }
    })
}

fn ko_vs(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<=\s)(?:vs|VS|Vs)\.?(?=\s)"), &t, "대");
    c.sub_tpl(&rx(r"(?<=[가-힣])(?:vs|VS)\.?(?=[가-힣])"), &t, " 대 ")
}

fn ko_grouping(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d,.])\d{1,3}(?:,\d{3})+(?![\d,])"), &t, |m| Some(m[0].replace(',', "")))
}

fn ko_money(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"[₩￦]\s?(\d+(?:\.\d+)?)(?=[가-힣])(?![십백천만억조])"), &t, r"\1원")
}

fn ko_date_dots(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.])([12]\d{3})\.\s?(\d{1,2})\.\s?(\d{1,2})\.?(?=[가-힣(（])"), &t, |m| {
        let (mo, d) = (py_int(g(m, 2)), py_int(g(m, 3)));
        if !((1..=12).contains(&mo) && (1..=31).contains(&d)) {
            return None;
        }
        Some(format!("{}년 {mo}월 {d}일", g(m, 1)))
    })
}

fn ko_score(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\d:.])(\d{1,3}):(\d{1,3})(?![\d:]|\.\d)"), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        let clock = b.chars().count() == 2 && py_int(a) <= 23 && py_int(b) <= 59;
        let (s, e) = span(m);
        if clock && !matches_at_start(SCORE_CUE, &t[e..]) {
            return None;
        }
        Some(put(&t, s, &format!("{} 대 {}", sino(a), sino(b))))
    });
    c.sub(&rx(r"(?<![\d.:/-])(\d{1,3})-(\d{1,3})(?![\d:/-]|\.\d)"), &t, |m| {
        let (s, e) = span(m);
        if !matches_at_start(SCORE_CUE, &t[e..]) {
            return None;
        }
        Some(put(&t, s, &format!("{} 대 {}", sino(g(m, 1)), sino(g(m, 2)))))
    })
}

fn ko_time(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d:.])([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?![\d:]|\.\d)"), &t, |m| {
        let (h, mi, sec) = (py_int(g(m, 1)), py_int(g(m, 2)), g(m, 3));
        let mut out = format!("{} 시", if h == 0 { "영".to_string() } else { native(h) });
        if mi != 0 {
            out.push_str(&format!(" {} 분", sino(&mi.to_string())));
        }
        if !sec.is_empty() && py_int(sec) != 0 {
            out.push_str(&format!(" {} 초", sino(&py_int(sec).to_string())));
        }
        let (s, e) = span(m);
        if kept(&t, e, &m[0], &out) { None } else { Some(put(&t, s, &out)) }
    })
}

fn ko_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<=\s[시분초])\s*[~～∼〜]\s*(?=[가-힣])"), &t, "에서 ");
    let pat = r"(?<![\d.:/,제월-])([0-9]+(?:\.[0-9]+)?)\s?([~～∼〜-])\s?([0-9]+(?:\.[0-9]+)?)(?![\d:/-]|\.\d)";
    c.sub(&rx(pat), &t, |m| {
        let (a, sep, b) = (g(m, 1), g(m, 2), g(m, 3));
        let (s, e) = span(m);
        let rest = &t[e..];
        let num = |x: &str| x.parse::<f64>().unwrap_or(0.0);
        let range_ok = matches_at_start(&format!(r"\s?(?:{})", *RANGE_AFTER), rest)
            && num(a) < num(b)
            && !a.starts_with('0')
            && !matches_at_start(r"\s?(?:번지|번|호|동)", rest);
        if sep == "-" && !range_ok {
            return None;
        }
        // not 달 in 달러
        let no_dae: Vec<(&str, &str)> = NATIVE.iter().copied().filter(|x| x.0 != "대").collect();
        let cm = lead_group(&format!(r"\s?({})", counter_alt(&no_dae)), rest);
        if let Some(ctr) = cm
            && !a.contains('.')
            && !b.contains('.')
            && (1..=99).contains(&py_int(a))
            && (ctr != "시" || py_int(a) <= 23)
        {
            return Some(put(&t, s, &format!("{} {ctr}에서 ", native(py_int(a)))) + b);
        }
        if sep == "〜" {
            return None; // the grammar reads 〜 itself (5〜10분 → 오 부터 십분)
        }
        Some(put(&t, s, &format!("{}에서 ", sino(a))) + b)
    })
}

/// The Sino-Korean reading of an amount: a two-decimal amount ending in 0 drops the 0 (5.50 → 오점오), and a 1 before
/// 만, 천 or 백 is not said (1만 → 만), as in the scale rule.
fn amount(s: &str, start: usize, num: &str, scale: &str) -> String {
    let num = match rx(r"^(?:(\d+)\.(\d)0)\z").captures(num) {
        Ok(Some(mm)) => {
            format!("{}{}", g(&mm, 1), if g(&mm, 2) == "0" { String::new() } else { format!(".{}", g(&mm, 2)) })
        }
        _ => num.to_string(),
    };
    if num == "1" && !scale.is_empty() && !scale.ends_with(['억', '조']) {
        let head = py_rstrip(&s[..start]);
        if !(head.ends_with('억') || head.ends_with('조')) {
            return scale.to_string();
        }
    }
    format!("{}{scale}", sino(&num))
}

fn ko_money_range(t: String, c: &mut Ctx) -> String {
    let low = |a: &str, b: &str, sep: &str| {
        "-–—".contains(sep) && a.parse::<f64>().unwrap_or(0.0) >= b.parse::<f64>().unwrap_or(0.0)
    };
    let hangul_next = |rest: &str| matches_at_start(r"[가-힣]", rest) && !matches_at_start(&AFTER_MONEY, rest);
    let code = &*CODE_ALT;
    let pat = format!(
        r"(?<![0-9A-Za-z.,])([€$＄£¥￥₩￦]|(?<![A-Za-z])(?:{code}) ?)(\d+(?:\.\d+)?)({SCALE_ALT})?\s?([~～∼〜\-–—])\s?([€$＄£¥￥₩￦]|(?:{code}) ?)?(\d+(?:\.\d+)?)({SCALE_ALT})?(?!\d|\.\d)"
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        let (cur, a, sa, sep, cur2, b, sb) =
            (g(m, 1).trim(), g(m, 2), g(m, 3), g(m, 4), g(m, 5).trim(), g(m, 6), g(m, 7));
        let (s0, e0) = span(m);
        let rest = &t[e0..];
        if (!cur2.is_empty() && cur2 != cur) || low(a, b, sep) || matches_at_start(r"[%％]", rest) || hangul_next(rest)
        {
            return None;
        }
        let word = lookup(MONEY_AFTER, cur);
        let first =
            format!("{}{}", amount(&t, s0, a, sa), if cur2.is_empty() { String::new() } else { format!(" {word}") });
        Some(put(&t, s0, &format!("{first}에서 {} {word}", amount(&t, s0, b, sb))))
    });
    let pat = format!(
        r"(?<![0-9A-Za-z.,:/])(\d+(?:\.\d+)?)({SCALE_ALT})?\s?({}|{WORD_AFTER})\s?([~～∼〜\-–—])\s?(\d+(?:\.\d+)?)({SCALE_ALT})?\s?(?:\3)(?![A-Za-z0-9$＄€£¥￥₩￦])",
        *MONEY_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        let (a, sa, cur, sep, b, sb) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
        let (s0, e0) = span(m);
        if low(a, b, sep) || hangul_next(&t[e0..]) {
            return None;
        }
        let word = MONEY_AFTER.iter().find(|(k, _)| *k == cur).map_or(cur, |(_, v)| *v);
        Some(put(&t, s0, &format!("{} {word}에서 {} {word}", amount(&t, s0, a, sa), amount(&t, s0, b, sb))))
    })
}

/// (written after the slash, said before the amount)
const PER: &[(&str, &str)] = &[
    ("시간", "시간당"),
    ("월", "월"),
    ("달", "한 달에"),
    ("년", "연"),
    ("연", "연"),
    ("일", "하루"),
    ("주", "주"),
    ("명", "일 인당"),
    ("인", "일 인당"),
    ("개", "개당"),
    ("회", "회당"),
    ("박", "일 박당"),
    ("kg", "킬로그램당"),
    ("g", "그램당"),
    ("L", "리터당"),
    ("m²", "제곱미터당"),
    ("㎡", "제곱미터당"),
    ("m", "미터당"),
    ("km", "킬로미터당"),
    ("kWh", "킬로와트시당"),
    ("m³", "세제곱미터당"),
    ("㎥", "세제곱미터당"),
];

fn ko_per(t: String, c: &mut Ctx) -> String {
    let per_alt = alternation(&PER.iter().map(|u| u.0).collect::<Vec<_>>());
    let money = format!(
        r"(?:(?:[€$＄£¥￥₩￦]|(?<![A-Za-z])(?:{}) ?)\s?\d+(?:\.\d+)?(?:{SCALE_ALT})?|\d+(?:\.\d+)?(?:{SCALE_ALT})?\s?(?:{}|{WORD_AFTER}))",
        *CODE_ALT, *MONEY_ALT
    );
    let pat = format!(r"(?<![0-9A-Za-z.,:/])({money})\s?/\s?({per_alt})(?={}|[^가-힣A-Za-z0-9²³]|$)", *AFTER_MONEY);
    c.sub(&rx(&pat), &t, |m| Some(format!("{} {}", put(&t, span(m).0, lookup(PER, g(m, 2))), g(m, 1))))
}

fn ko_groups(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?<![\dA-Za-z.,/:+\-–])(?<!\d[ \x{A0}\x{202F}])[1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+(?!\d|[.,]\d{3})",
        r"(?![ \x{A0}\x{202F}]\d)"
    );
    let after = format!(r"[ \x{{A0}}\x{{202F}}]?(?:{}|(?:{})(?![A-Za-z])|[가-힣])", *MONEY_ALT, *UNIT_ALT);
    c.sub(&rx(pat), &t, |m| {
        let w = m.get(0).expect("group 0");
        let gaps = w.as_str().chars().filter(|&ch| matches!(ch, ' ' | '\u{a0}' | '\u{202f}')).count();
        if gaps < 2
            && !super::super::search(r"[$€£¥₩₱฿₫₹] ?$", &t[..w.start()])
            && !matches_at_start(&after, &t[w.end()..])
        {
            return None;
        }
        Some(w.as_str().chars().filter(|&ch| !matches!(ch, ' ' | '\u{a0}' | '\u{202f}')).collect())
    })
}

fn ko_money_after(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?:(?<![0-9A-Za-z.,)\]])(-))?(?<![0-9A-Za-z.,:/])(\d+(?:\.\d+)?)(천만|백만|십만|만|억|조|천|백)?\s?({})(?![A-Za-z0-9$＄€£¥￥₩￦])(?!\s?\d)",
        *MONEY_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        let (s, e) = span(m);
        if search(&SIGN_BEFORE, py_rstrip(&t[..s])) {
            return None; // KRW 76,197$, $ 215 $: the grammar reads the sign before the amount
        }
        let rest = &t[e..];
        let sign_at = m.get(4).expect("group 4").start();
        if is_py_space(before(&t, sign_at, 'x'))
            && matches_at_start(r"[가-힣]", rest)
            && !matches_at_start(&AFTER_MONEY, rest)
        {
            return None; // 1623186501 $오늘: a spaced sign glued to the next word is not the amount's
        }
        let out = amount(&t, s, g(m, 2), g(m, 3));
        let minus = if g(m, 1).is_empty() { "" } else { "마이너스 " };
        Some(put(&t, s, &format!("{minus}{out} {}", lookup(MONEY_AFTER, g(m, 4)))))
    })
}

fn ko_money_before(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?:(?<![0-9A-Za-z.,)\]])(-))?(?<![A-Za-z])({})\s?(\d+(?:\.\d+)?)(천만|백만|십만|만(?!큼)|억|조|천|백)?(?!\d|\.\d)",
        *MONEY_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        let (s, e) = span(m);
        let rest = &t[e..];
        if matches_at_start(r"[%％]", rest)
            || (matches_at_start(r"[가-힣]", rest) && !matches_at_start(&AFTER_MONEY, rest))
        {
            return None; // $ 6월 15일, NZD39%: not an amount of money
        }
        let out = amount(&t, s, g(m, 3), g(m, 4));
        let minus = if g(m, 1).is_empty() { "" } else { "마이너스 " };
        let out = format!("{minus}{out} {}", lookup(MONEY_AFTER, g(m, 2)));
        if kept(&t, e, &m[0], &out) { None } else { Some(put(&t, s, &out)) }
    })
}

fn ko_minus_temp(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![0-9A-Za-z.)\]])-\s?(\d+(?:\.\d+)?)(\s?)(℃|°C|도)"), &t, |m| {
        if g(m, 3) == "도" && !search(TEMP_CUE, &t) {
            return None;
        }
        Some(format!("영하 {}{}{}", g(m, 1), g(m, 2), g(m, 3)))
    })
}

fn ko_units(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![0-9A-Za-z.,/-])(\d+(?:\.\d+)?)\s?({})(?![A-Za-z0-9²³/])", *UNIT_ALT);
    c.sub(&rx(&pat), &t, |m| {
        let &(_, w, p) = UNITS.iter().find(|u| u.0 == g(m, 2)).expect("unit");
        let (s, e) = span(m);
        let p = if !p.is_empty() && py_rstrip(&t[..s]).ends_with(p) { "" } else { p }; // 시속 100km/h
        let out = format!("{}{} {w}", if p.is_empty() { String::new() } else { format!("{p} ") }, sino(g(m, 1)));
        if kept(&t, e, &m[0], &out) { None } else { Some(put(&t, s, &out)) }
    })
}

fn ko_scale(t: String, c: &mut Ctx) -> String {
    let pat = r"(?<![\d.,$€¥£₩￦])(?<![$€¥£₩￦]\s)(\d{1,4}(?:\.\d+)?)(천만|백만|십만|만(?!큼)|억|조|천|백)";
    c.sub(&rx(pat), &t, |m| {
        let (n, scale) = (g(m, 1), g(m, 2));
        let (s, e) = span(m);
        let mut out = format!("{}{scale}", sino(n));
        if n == "1" && !scale.ends_with(['억', '조']) {
            let head = py_rstrip(&t[..s]);
            if !(head.ends_with('억') || head.ends_with('조')) {
                out = scale.to_string();
            }
        }
        if kept(&t, e, &m[0], &out) { None } else { Some(put(&t, s, &out)) }
    })
}

static COUNTER_PAT: LazyLock<String> = LazyLock::new(|| {
    let mut table = NATIVE.to_vec();
    table.extend_from_slice(SINO);
    format!(r"(?<![0-9A-Za-z.,:/~～제시분초년월일-])(\d+)({})", counter_alt(&table))
});

fn ko_counter(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&COUNTER_PAT), &t, |m| {
        let (n, ctr) = (py_int(g(m, 1)), g(m, 2));
        let (s, e) = span(m);
        let rest = &t[e..];
        if ctr == "시" && n > 23 {
            return None;
        }
        if ctr == "대" && (n % 10 == 0 || !matches_at_start(DAE_NEXT, rest)) {
            return None;
        }
        if ctr == "장" && matches_at_start(r"\s?\d+\s?절|에서", rest) {
            return None;
        }
        if matches_at_start(r"\d", rest) {
            return None;
        }
        let out = if ["개월", "분", "초"].contains(&ctr) || n == 0 || n > 99 {
            format!("{} {ctr}", sino(&py_int_str(g(m, 1))))
        } else if ctr == "번째" && n == 1 {
            "첫 번째".to_string()
        } else {
            format!("{} {ctr}", native(n))
        };
        if kept(&t, e, &m[0], &out) { None } else { Some(put(&t, s, &out)) }
    })
}

fn ko_times(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"((?<![가-힣])(?:하루|일주일|한\s?주|주|한\s?달|달|일\s?년|년|해|시간|분|매일|매주|매달|매년|총|모두|평생)",
        r"(?:에|에는|에도|동안|간)?\s*)([1-9]\d?)번(?!째|지|호|길|선|출구|버스|방)"
    );
    let t = c.sub(&rx(pat), &t, |m| Some(format!("{}{} 번", g(m, 1), native(py_int(g(m, 2))))));
    let pat = concat!(
        r"(?<![0-9A-Za-z.,:/~～제-])([1-9]\d?)번(?=씩|이나|정도|쯤|가량|이상|이하|넘게|만에|밖에|연속|",
        r"\s(?:더|정도|이상|넘게|연속)(?![가-힣]))"
    );
    c.sub(&rx(pat), &t, |m| Some(put(&t, span(m).0, &format!("{} 번", native(py_int(g(m, 1)))))))
}

fn ko_month(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![0-9A-Za-z.,:/~～-])(1[0-2]|0?[1-9])월(?=[가-힣])"), &t, |m| {
        Some(put(&t, span(m).0, MONTHS[py_int(g(m, 1)) as usize]))
    })
}

fn ko_weekday(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<=\d일)\s?[(（]([월화수목금토일])[)）](?=[가-힣.,!?])"), &t, r" \1요일")
}

fn ko_decimal(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![0-9.,])(\d+\.\d+)(?={COPULA}|{PARTICLE}+(?![가-힣]))");
    c.sub(&rx(&pat), &t, |m| Some(put(&t, span(m).0, &sino(g(m, 1)))))
}
