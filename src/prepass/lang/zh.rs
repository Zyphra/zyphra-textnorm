//! 'zh' rules: the port of the workbench's `langrules/zh.py` (ids `zh.*`).
//!
//! The zh grammar reads every 2 as 二 (二个苹果), every N号 as N日 (3号线 → 三日线), N:M as a clock time (3:1 → 三点一分),
//! N-M as a minus, ¥ as 圆, 12.50元 as 十二点五零元, and leaves m, L, t, W, km/h and a comma-grouped number unread. These
//! rules rewrite the span into a form the grammar reads right (3比1, 30到60, 12元5角, 25公里, 1200万) or write the words.

use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, py_int_str, py_rstrip, rx, search, tpl};
use super::ko::{ROMAN_CHARS, alternation, roman_value};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("zh.roman", zh_roman),
    ("zh.vs", zh_vs),
    ("zh.grouping", zh_grouping),
    ("zh.money", zh_money),
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
];
/// No unit has a regex metacharacter.
static UNIT_ALT: LazyLock<String> = LazyLock::new(|| alternation(&UNITS.iter().map(|u| u.0).collect::<Vec<_>>()));
/// The other way of saying the prefix, already written before the number.
const SAID: &[(&str, &str)] = &[("每小时", "时速"), ("每秒", "秒速")];
const CURRENCY: &str = r"美元|欧元|英镑|港元|港币|日元|韩元|卢布|澳元|加元";
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

fn zh_grouping(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d,.])(?<!--)\d{1,3}(?:,\d{3})+(?![\d,])"), &t, |m| Some(m[0].replace(',', "")))
}

fn zh_money(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<![A-Za-z])[¥￥]\s?(\d+(?:\.\d+)?(?:万|亿)?)(?![\d.])"), &t, r"\1元");
    let zero = |m: &Captures<'_, str>| {
        Some(format!("{}{}", g(m, 1), if g(m, 2) == "0" { String::new() } else { format!(".{}", g(m, 2)) }))
    };
    let t = c.sub(&rx(r"(?<=[$€£])(\d+)\.(\d)0(?!\d)"), &t, zero);
    c.sub(&rx(&format!(r"(?<![\d.])(\d+)\.(\d)0(?=\s?(?:{CURRENCY}))")), &t, zero)
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
    format!(r"(?<![\d.,:/第\-+~～])2(?![\d.])(?=\s?(?:{meas})|(?:到|至)\d+\s?(?:{meas}))")
});

fn zh_liang(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&LIANG_PAT), &t, "两")
}

fn zh_hao(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.,])(\d+)号"), &t, |m| Some(format!("{}号", words(&py_int_str(g(m, 1)), "zh"))))
}
