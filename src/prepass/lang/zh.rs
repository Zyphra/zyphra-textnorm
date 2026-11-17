//! 'zh' rules: the port of the workbench's `langrules/zh.py` (ids `zh.*`).
//!
//! The zh grammar reads every 2 as 二 (二个苹果), every N号 as N日 (3号线 → 三日线), N:M as a clock time (3:1 → 三点一分),
//! N-M as a minus, ¥ as 圆, 12.50元 as 十二点五零元, and leaves m, L, t, W, km/h, a comma-grouped number, a currency sign
//! after the amount (5 €) and a currency code after a space (USD 20, 20 USD) unread. These rules rewrite the span into a
//! form the grammar reads right (3比1, 30到60, 12元5角, 25公里, 1200万, 5欧元) or write the words.

use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, py_int_str, py_rstrip, rx, search, tpl};
use super::ko::{ROMAN_CHARS, alternation, roman_value};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::is_py_space;

pub(super) const RULES: &[LangRule] = &[
    ("zh.roman", zh_roman),
    ("zh.vs", zh_vs),
    ("zh.groups", zh_groups),
    ("zh.big", zh_big),
    ("zh.grouping", zh_grouping),
    ("zh.money-code", zh_money_code),
    ("zh.money-scale", zh_money_scale),
    ("zh.money-after", zh_money_after),
    ("zh.money", zh_money),
    ("zh.money-range", zh_money_range),
    ("zh.money-minus", zh_money_minus),
    ("zh.per", zh_per),
    ("zh.cents", zh_cents),
    ("zh.score", zh_score),
    ("zh.range", zh_range),
    ("zh.minus-temp", zh_minus_temp),
    ("zh.units", zh_units),
    ("zh.hours", zh_hours),
    ("zh.liang", zh_liang),
    ("zh.hao", zh_hao),
];

/// Measure words and units that take 两 for a lone 2 (两个, 两本, 两公里, 两万); 月 号 日 楼 层 点 分 秒 级 班 路 are
/// ordinal or the grammar's (二月, 二号, 二楼, 两点), 角/毛 after 元 stay 二.
const LIANG: &[&str] = &[
    "个月",
    "小时",
    "分钟",
    "秒钟",
    "星期",
    "礼拜",
    "公里",
    "公斤",
    "千克",
    "千米",
    "厘米",
    "毫米",
    "毫升",
    "平方米",
    "个",
    "位",
    "名",
    "本",
    "支",
    "只",
    "条",
    "张",
    "件",
    "次",
    "天",
    "周",
    "岁",
    "种",
    "家",
    "台",
    "辆",
    "双",
    "对(?!\\d)",
    "块",
    "元",
    "杯",
    "瓶",
    "碗",
    "份",
    "场",
    "部",
    "首",
    "把",
    "根",
    "颗",
    "头",
    "匹",
    "架",
    "间",
    "套",
    "片",
    "节",
    "遍",
    "趟",
    "回",
    "倍",
    "斤",
    "克",
    "米",
    "升",
    "吨",
    "人",
    "口",
    "句",
    "段",
    "篇",
    "封",
    "盒",
    "袋",
    "包",
    "箱",
    "桶",
    "盘",
    "顿",
    "粒",
    "枚",
    "座",
    "栋",
    "所",
    "艘",
    "棵",
    "朵",
    "群",
    "批",
    "门",
    "千",
    "万",
    "亿",
    "年(?!级|代)",
];
/// (written, spoken, said before the number)
const UNITS: &[(&str, &str, &str)] = &[
    ("km/h", "公里", "每小时"),
    ("m/s", "米", "每秒"),
    ("km", "公里", ""),
    ("㎞", "公里", ""),
    ("kg", "千克", ""),
    ("㎏", "千克", ""),
    ("m", "米", ""),
    ("㎡", "平方米", ""),
    ("㎥", "立方米", ""),
    ("L", "升", ""),
    ("ℓ", "升", ""),
    ("t", "吨", ""),
    ("kWh", "千瓦时", ""),
    ("kW", "千瓦", ""),
    ("W", "瓦", ""),
    ("kHz", "千赫", ""),
    ("MHz", "兆赫", ""),
    ("Hz", "赫兹", ""),
    ("mAh", "毫安时", ""),
    ("V", "伏", ""),
    ("％", "%", ""),
    ("%", "%", ""),
    ("ha", "公顷", ""),
];
/// No unit has a regex metacharacter.
static UNIT_ALT: LazyLock<String> = LazyLock::new(|| alternation(&UNITS.iter().map(|u| u.0).collect::<Vec<_>>()));
/// The other way of saying the prefix, already written before the number.
const SAID: &[(&str, &str)] = &[("每小时", "时速"), ("每秒", "秒速")];
const CURRENCY: &str = r"美元|欧元|英镑|港元|港币|日元|韩元|卢布|澳元|加元";
/// Signs and codes written after the amount (5 €, 20 USD), with the grammar's word for each (its sign-first reading of
/// € $ £ ₩ and of USD5, GBP5 …); ¥ is 元 as in zh.money, and so are CNY and RMB (the grammar says 人民币).
const MONEY_AFTER: &[(&str, &str)] = &[
    ("¥", "元"),
    ("￥", "元"),
    ("$", "美元"),
    ("＄", "美元"),
    ("€", "欧元"),
    ("£", "英镑"),
    ("₩", "韩元"),
    ("USD", "美元"),
    ("EUR", "欧元"),
    ("GBP", "英镑"),
    ("JPY", "日元"),
    ("CNY", "元"),
    ("RMB", "元"),
    ("KRW", "韩元"),
    ("HKD", "港元"),
    ("TWD", "新台币"),
    ("AUD", "澳元"),
    ("CAD", "加元"),
    ("CHF", "瑞士法郎"),
    ("SGD", "新加坡元"),
    ("NZD", "新西兰元"),
    ("BRL", "巴西雷亚尔"),
    ("MXN", "墨西哥比索"),
    ("INR", "印度卢比"),
    ("THB", "泰铢"),
    ("PHP", "菲律宾比索"),
    ("VND", "越南盾"),
    ("IDR", "印尼盾"),
    ("MYR", "马来西亚令吉"),
    ("RUB", "俄罗斯卢布"),
]; // the grammar's own words for these codes before the amount (VND: 越南盾, not its 越南东)
/// All three letters.
static CODE_ALT: LazyLock<String> = LazyLock::new(|| {
    MONEY_AFTER.iter().map(|m| m.0).filter(|k| k.chars().all(char::is_alphabetic)).collect::<Vec<_>>().join("|")
});
/// An amount with its sign before it (KRW 76,197$).
static SIGN_BEFORE: LazyLock<String> = LazyLock::new(|| format!(r"(?:[¥￥$＄€£₩]|(?<![A-Za-z])(?:{}))$", *CODE_ALT));
/// The currency words an amount may carry once the money rules have run (元, 美元, 欧元 …), longest first.
static WORD_ALT: LazyLock<String> = LazyLock::new(|| {
    let mut ws: Vec<&str> = Vec::new();
    for w in MONEY_AFTER.iter().map(|m| m.1).chain(CURRENCY.split('|')) {
        if !ws.contains(&w) {
            ws.push(w);
        }
    }
    alternation(&ws)
});
const AMT: &str = r"\d+(?:\.\d+)?";

fn value(num: &str, scale: &str) -> f64 {
    num.parse::<f64>().unwrap_or(0.0)
        * match scale {
            "千" => 1e3,
            "万" => 1e4,
            "亿" => 1e8,
            _ => 1.0,
        }
}

/// 10^12 and up in words, in 亿 groups as the grammar reads them below 10^12 (2000000000000 → 两万亿; the grammar said
/// 两千亿零).
fn big(n: u128) -> String {
    let (a, b) = (n / 100_000_000, n % 100_000_000);
    format!(
        "{}亿{}{}",
        words(&a.to_string(), "zh"),
        if b > 0 && b < 10_000_000 { "零" } else { "" },
        if b > 0 { words(&b.to_string(), "zh") } else { String::new() }
    )
}
const TEMP_CUE: &str = r"气温|温度|最低|最高|零下|降温|体感|水温|室外|室内|低温|高温|天气|寒|冷|冻";
const SCORE_CUE: &str = concat!(
    r"[^。！？!?\n]{0,12}?(?:战胜|击败|打败|赢|输|负于|胜|获胜|落败|战平|打平|逼平|大胜|逆转|取胜|夺冠|领先|落后|败给|",
    r"小胜|完胜|惨败|险胜|告负|击溃)"
);

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).expect("group 0").end()
}

fn zh_roman(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"第\s?([IVXLC]+|[{ROMAN_CHARS}])(?=\s?(?:章|部分|部|卷|篇|回|集|季|期|册|编|节|条|款|届|次|代|世|幕|课|单元|阶段|版))"
    );
    c.sub(&rx(&pat), &t, |m| {
        let n = roman_value(g(m, 1));
        if n != 0 { Some(format!("第{n}")) } else { None }
    })
}

fn zh_vs(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<=\s)(?:vs|VS|Vs)\.?(?=\s)"), &t, "对");
    c.sub_tpl(&rx(r"(?<=[\x{4E00}-\x{9FFF}])(?:vs|VS)\.?(?=[\x{4E00}-\x{9FFF}])"), &t, "对")
}

fn zh_groups(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?<![\dA-Za-z.,/:+\-–])(?<!\d[ \x{A0}\x{202F}])[1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+(?!\d|[.,]\d{3})",
        r"(?![ \x{A0}\x{202F}]\d)"
    );
    let after = format!(
        r"[ \x{{A0}}\x{{202F}}]?(?:[¥￥$＄€£₩]|(?:{}|{})(?![A-Za-z])|[\x{{4E00}}-\x{{9FFF}}])",
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

fn zh_big(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?:(?<![0-9A-Za-z.,)\]])(-))?(?<![\dA-Za-z.,])(?:([$＄€£₩¥￥])\s?|(?<![A-Za-z])({code})\s?)?([1-9]\d{{0,2}}(?:,\d{{3}}){{4,}}|[1-9]\d{{12,15}})(?![\d,]|\.\d)(?:\s?([$＄€£₩¥￥]|{code})(?![A-Za-z0-9]))?",
        code = *CODE_ALT
    );
    let word_after = format!(r"\s?(?:{})", *WORD_ALT);
    c.sub(&rx(&pat), &t, |m| {
        let digits = g(m, 4).replace(',', "");
        let n = py_int(&digits);
        let cur = [g(m, 2), g(m, 3), g(m, 5)].into_iter().find(|x| !x.is_empty()).unwrap_or("");
        if !(10u128.pow(12)..10u128.pow(16)).contains(&n)
            || (!g(m, 4).contains(',') && cur.is_empty() && !matches_at_start(&word_after, &t[end(m)..]))
        {
            return None;
        }
        Some(format!(
            "{}{}{}",
            if g(m, 1).is_empty() { "" } else { "负" },
            big(n),
            if cur.is_empty() { "" } else { lookup(MONEY_AFTER, cur) }
        ))
    })
}

fn zh_grouping(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d,.])(?<!--)\d{1,3}(?:,\d{3})+(?![\d,])"), &t, |m| Some(m[0].replace(',', "")))
}

fn lookup<'a>(table: &[(&str, &'a str)], key: &str) -> &'a str {
    table.iter().find(|(k, _)| *k == key).map_or("", |(_, v)| *v)
}

/// A two-decimal amount ending in 0 drops the 0 (5.50 → 5.5, 5.00 → 5).
fn drop_zero(num: &str) -> String {
    if let Ok(Some(mm)) = rx(r"^(?:(\d+)\.(\d)0)\z").captures(num) {
        return format!("{}{}", g(&mm, 1), if g(&mm, 2) == "0" { String::new() } else { format!(".{}", g(&mm, 2)) });
    }
    num.to_string()
}

fn zh_money_code(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![A-Za-z])({})\s?(\d+(?:\.\d+)?)(万|亿)?(?!\d|\.\d)", *CODE_ALT);
    c.sub(&rx(&pat), &t, |m| Some(format!("{}{}{}", drop_zero(g(m, 2)), g(m, 3), lookup(MONEY_AFTER, g(m, 1)))))
}

fn zh_money_scale(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![A-Za-z])([$＄€£₩])\s?(\d+(?:\.\d+)?)(万|亿|千)(?!\d)"), &t, |m| {
        let word = lookup(MONEY_AFTER, g(m, 1));
        let twice = t[m.get(0).expect("group 0").end()..].trim_start_matches(is_py_space).starts_with(word);
        Some(format!("{}{}{}", g(m, 2), g(m, 3), if twice { "" } else { word }))
    })
}

fn zh_money_after(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?:(?<![0-9A-Za-z.,)\]])(-))?(?<![0-9A-Za-z.,:/])(\d+(?:\.\d+)?)(万|亿)?\s?([¥￥$＄€£₩]|{})(?![A-Za-z0-9$＄€£¥￥₩￦])(?!\s?\d)",
        *CODE_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        if search(&SIGN_BEFORE, py_rstrip(&t[..m.get(0).expect("group 0").start()])) {
            return None;
        }
        let minus = if g(m, 1).is_empty() { "" } else { "负 " };
        Some(format!("{minus}{}{}{}", drop_zero(g(m, 2)), g(m, 3), lookup(MONEY_AFTER, g(m, 4))))
    })
}

fn zh_money(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<![A-Za-z])[¥￥]\s?(\d+(?:\.\d+)?(?:万|亿)?)(?!\d|\.\d)"), &t, r"\1元");
    let zero = |m: &Captures<'_, str>| {
        Some(format!("{}{}", g(m, 1), if g(m, 2) == "0" { String::new() } else { format!(".{}", g(m, 2)) }))
    };
    let t = c.sub(&rx(r"(?<=[$€£])(\d+)\.(\d)0(?!\d)"), &t, zero);
    c.sub(&rx(&format!(r"(?<![\d.])(\d+)\.(\d)0(?=\s?(?:{CURRENCY}))")), &t, zero)
}

fn zh_money_range(t: String, c: &mut Ctx) -> String {
    let pat =
        format!(r"(?<![\dA-Za-z.,])([$＄€£₩])\s?({AMT})(万|亿)?\s?([-~～—–〜])\s?(\1)?\s?({AMT})(万|亿)?(?!\d|\.\d)");
    let t = c.sub(&rx(&pat), &t, |m| {
        if g(m, 4) == "-" && value(g(m, 2), g(m, 3)) >= value(g(m, 6), g(m, 7)) {
            return None;
        }
        let word = lookup(MONEY_AFTER, g(m, 1));
        let first = format!("{}{}{}", drop_zero(g(m, 2)), g(m, 3), if g(m, 5).is_empty() { "" } else { word });
        Some(format!("{first}到{}{}{word}", drop_zero(g(m, 6)), g(m, 7)))
    });
    let w = &*WORD_ALT;
    let pat = format!(
        r"(?<![\d.,])({AMT})(千|万|亿)?({w})\s?([-~～—–〜])\s?({AMT})(千|万|亿)?(?:({w})|(?![\d.]|万|亿|千|[A-Za-z%％]|{}))",
        *UNIT_ALT
    );
    c.sub(&rx(&pat), &t, |m| {
        if g(m, 4) == "-" && value(g(m, 1), g(m, 2)) >= value(g(m, 5), g(m, 6)) {
            return None;
        }
        if !g(m, 7).is_empty() && g(m, 7) != g(m, 3) {
            return None;
        }
        Some(format!(
            "{}{}{}到{}{}{}",
            g(m, 1),
            g(m, 2),
            if g(m, 7).is_empty() { "" } else { g(m, 3) },
            g(m, 5),
            g(m, 6),
            g(m, 3)
        ))
    })
}

fn zh_money_minus(t: String, c: &mut Ctx) -> String {
    let w = &*WORD_ALT;
    let before = format!(r"(?:{w})\s?$");
    let pat = format!(r"(?<![0-9A-Za-z.,)\]])-\s?(?=[$＄€£₩]\s?\d|{AMT}(?:万|亿)?\s?(?:{w}))");
    c.sub(&rx(&pat), &t, |m| {
        if search(&before, &t[..m.get(0).expect("group 0").start()]) {
            return None; // 10元-5元: a difference of two amounts
        }
        Some("负 ".to_string())
    })
}

const PER: &[(&str, &str)] = &[
    ("月", "月"),
    ("年", "年"),
    ("天", "天"),
    ("日", "日"),
    ("周", "周"),
    ("晚", "晚"),
    ("次", "次"),
    ("人", "人"),
    ("位", "位"),
    ("小时", "小时"),
    ("个", "个"),
    ("件", "件"),
    ("张", "张"),
    ("斤", "斤"),
    ("公斤", "公斤"),
    ("千克", "千克"),
    ("克", "克"),
    ("平方米", "平方米"),
    ("份", "份"),
    ("台", "台"),
    ("kg", "千克"),
    ("g", "克"),
    ("㎡", "平方米"),
    ("m²", "平方米"),
    ("m", "米"),
    ("km", "公里"),
    ("L", "升"),
    ("kWh", "千瓦时"),
    ("m³", "立方米"),
    ("㎥", "立方米"),
];

fn zh_per(t: String, c: &mut Ctx) -> String {
    let per_alt = alternation(&PER.iter().map(|u| u.0).collect::<Vec<_>>());
    let pat = format!(
        r"((?<![\dA-Za-z.,])[$＄€£₩]\s?{AMT}(?:万|亿)?|(?<![\d.,]){AMT}(?:万|亿)?(?:{}))\s?/\s?({per_alt})(?![A-Za-z0-9²³\x{{4E00}}-\x{{9FFF}}])",
        *WORD_ALT
    );
    c.sub(&rx(&pat), &t, |m| Some(format!("{}每{}", g(m, 1), lookup(PER, g(m, 2)))))
}

fn zh_cents(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.])(\d+)\.(\d)(\d)?元"), &t, |m| {
        let (n, j) = (g(m, 1), g(m, 2));
        let fen = if g(m, 3).is_empty() { "0" } else { g(m, 3) };
        let head = if n == "0" && (j != "0" || fen != "0") { String::new() } else { format!("{n}元") };
        if j == "0" && fen == "0" {
            return Some(head);
        }
        if j == "0" {
            return Some(format!("{head}{}{fen}分", if head.is_empty() { "" } else { "零" }));
        }
        Some(format!("{head}{j}角{}", if fen == "0" { String::new() } else { format!("{fen}分") }))
    })
}

fn zh_score(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\d:.])(\d{1,3})[:：](\d{1,3})(?![\d:]|\.\d)"), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        let clock = b.chars().count() == 2 && py_int(a) <= 23 && py_int(b) <= 59;
        if clock && !matches_at_start(SCORE_CUE, &t[end(m)..]) {
            return None;
        }
        Some(format!("{a}比{b}"))
    });
    c.sub(&rx(r"(?<![\d.:/-])(\d{1,3})-(\d{1,3})(?![\d:/-]|\.\d)"), &t, |m| {
        if matches_at_start(SCORE_CUE, &t[end(m)..]) { Some(format!("{}比{}", g(m, 1), g(m, 2))) } else { None }
    })
}

fn zh_range(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?<![\d.:/,=+*×÷-])([0-9]+(?:\.[0-9]+)?)(%?)\s?([-~～—–])\s?([0-9]+(?:\.[0-9]+)?)(%?)",
        r"(?![\d:/-]|\.\d|\s?[=＝+*×÷])"
    );
    c.sub(&rx(pat), &t, |m| {
        let (a, pa, sep, b, pb) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        let num = |x: &str| x.parse::<f64>().unwrap_or(0.0);
        if sep == "-" && (num(a) >= num(b) || (a.starts_with('0') && a != "0")) {
            return None;
        }
        let rest = &t[end(m)..];
        let a = if a.chars().count() == 4
            && b.chars().count() == 4
            && !a.contains('.')
            && !b.contains('.')
            && rest.starts_with('年')
        {
            digit_words(a, "zh", "")
        } else {
            a.to_string()
        };
        Some(format!("{a}{}到{b}{pb}", if pa.is_empty() { pb } else { pa }))
    })
}

fn zh_minus_temp(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![0-9A-Za-z.)\]])-\s?(\d+(?:\.\d+)?)(\s?)(℃|°C|度)"), &t, |m| {
        if g(m, 3) == "度" && !search(TEMP_CUE, &t) {
            return None;
        }
        Some(format!("零下{}{}{}", g(m, 1), g(m, 2), g(m, 3)))
    })
}

fn zh_units(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![0-9A-Za-z.,/-])(\d+(?:\.\d+)?)\s?({})(?![A-Za-z0-9²³/])", *UNIT_ALT);
    c.sub(&rx(&pat), &t, |m| {
        let &(_, w, p) = UNITS.iter().find(|u| u.0 == g(m, 2)).expect("unit");
        let head = py_rstrip(&t[..m.get(0).expect("group 0").start()]);
        let said = SAID.iter().find(|(k, _)| *k == p).map_or("", |(_, v)| *v);
        let p = if !p.is_empty() && (head.ends_with(p) || head.ends_with(said)) { "" } else { p }; // 时速120km/h
        Some(format!("{p}{}{w}", g(m, 1)))
    })
}

fn zh_hours(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.])(\d+\.\d+)(?=个?小时)"), &t, |m| Some(words(g(m, 1), "zh")))
}

static LIANG_PAT: LazyLock<String> = LazyLock::new(|| {
    let meas = alternation(LIANG);
    format!(r"(?<![\d.,:/第\-+~～$＄€£₩])2(?![\d.])(?=\s?(?:{meas})|(?:到|至)\d+\s?(?:{meas}))")
});

fn zh_liang(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&LIANG_PAT), &t, "两")
}

fn zh_hao(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.,])(\d+)号"), &t, |m| Some(format!("{}号", words(&py_int_str(g(m, 1)), "zh"))))
}
