//! 'ru' rules: the port of the workbench's `langrules/ru.py` (ids `ru.*`).
//!
//! The grammar reads every number in the nominative (masculine for 1 and 2), so these rules write the words themselves
//! where a preposition, the noun or the date asks for another form: a small declension generator for cardinals and
//! ordinals (all six cases, three genders) and for the few nouns the rules write after a number (рубль, копейка,
//! процент, градус, грамм, час, тысяча, миллион…). Number words are written with ё (трёх, четвёртого).

use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, search};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::py_strip;

pub(super) const RULES: &[LangRule] = &[
    ("ru.latin", ru_latin),
    ("ru.city", ru_city),
    ("ru.address", ru_address),
    ("ru.grouped-decimal", ru_grouped_decimal),
    ("ru.money-range", ru_money_range),
    ("ru.cents", ru_cents),
    ("ru.date", ru_date),
    ("ru.year", ru_year),
    ("ru.time", ru_time),
    ("ru.half", ru_half),
    ("ru.ordinal-e", ru_ordinal_e),
    ("ru.ordinal-range", ru_ordinal_range),
    ("ru.range", ru_range),
    ("ru.case", ru_case),
    ("ru.case-unit", ru_case_unit),
    ("ru.gender", ru_gender),
    ("ru.thousand", ru_thousand),
    ("ru.trillion", ru_trillion),
    ("ru.per-unit", ru_per_unit),
    ("ru.abbr-dot", ru_abbr_dot),
];

// ------------------------------------------------------------------------------------------------- morphology
// cases: 0 nom, 1 gen, 2 dat, 3 acc, 4 ins, 5 prep (acc of a number = nom: inanimate)
const NOM: usize = 0;
const GEN: usize = 1;
const DAT: usize = 2;
const ACC: usize = 3;
const INS: usize = 4;
const PREP: usize = 5;
/// "No case": the number stays as it is.
const NONE: usize = 99;

fn one(gender: &str) -> [&'static str; 6] {
    match gender {
        "f" => ["одна", "одной", "одной", "одну", "одной", "одной"],
        "n" => ["одно", "одного", "одному", "одно", "одним", "одном"],
        _ => ["один", "одного", "одному", "один", "одним", "одном"],
    }
}

/// 2–19, tens and hundreds: (nom, gen, dat, ins, prep).
fn card_forms(k: u64) -> [&'static str; 5] {
    match k {
        2 => ["два", "двух", "двум", "двумя", "двух"],
        3 => ["три", "трёх", "трём", "тремя", "трёх"],
        4 => ["четыре", "четырёх", "четырём", "четырьмя", "четырёх"],
        5 => ["пять", "пяти", "пяти", "пятью", "пяти"],
        6 => ["шесть", "шести", "шести", "шестью", "шести"],
        7 => ["семь", "семи", "семи", "семью", "семи"],
        8 => ["восемь", "восьми", "восьми", "восемью", "восьми"],
        9 => ["девять", "девяти", "девяти", "девятью", "девяти"],
        10 => ["десять", "десяти", "десяти", "десятью", "десяти"],
        11 => ["одиннадцать", "одиннадцати", "одиннадцати", "одиннадцатью", "одиннадцати"],
        12 => ["двенадцать", "двенадцати", "двенадцати", "двенадцатью", "двенадцати"],
        13 => ["тринадцать", "тринадцати", "тринадцати", "тринадцатью", "тринадцати"],
        14 => ["четырнадцать", "четырнадцати", "четырнадцати", "четырнадцатью", "четырнадцати"],
        15 => ["пятнадцать", "пятнадцати", "пятнадцати", "пятнадцатью", "пятнадцати"],
        16 => ["шестнадцать", "шестнадцати", "шестнадцати", "шестнадцатью", "шестнадцати"],
        17 => ["семнадцать", "семнадцати", "семнадцати", "семнадцатью", "семнадцати"],
        18 => ["восемнадцать", "восемнадцати", "восемнадцати", "восемнадцатью", "восемнадцати"],
        19 => ["девятнадцать", "девятнадцати", "девятнадцати", "девятнадцатью", "девятнадцати"],
        20 => ["двадцать", "двадцати", "двадцати", "двадцатью", "двадцати"],
        30 => ["тридцать", "тридцати", "тридцати", "тридцатью", "тридцати"],
        40 => ["сорок", "сорока", "сорока", "сорока", "сорока"],
        50 => ["пятьдесят", "пятидесяти", "пятидесяти", "пятьюдесятью", "пятидесяти"],
        60 => ["шестьдесят", "шестидесяти", "шестидесяти", "шестьюдесятью", "шестидесяти"],
        70 => ["семьдесят", "семидесяти", "семидесяти", "семьюдесятью", "семидесяти"],
        80 => ["восемьдесят", "восьмидесяти", "восьмидесяти", "восемьюдесятью", "восьмидесяти"],
        90 => ["девяносто", "девяноста", "девяноста", "девяноста", "девяноста"],
        100 => ["сто", "ста", "ста", "ста", "ста"],
        200 => ["двести", "двухсот", "двумстам", "двумястами", "двухстах"],
        300 => ["триста", "трёхсот", "трёмстам", "тремястами", "трёхстах"],
        400 => ["четыреста", "четырёхсот", "четырёмстам", "четырьмястами", "четырёхстах"],
        500 => ["пятьсот", "пятисот", "пятистам", "пятьюстами", "пятистах"],
        600 => ["шестьсот", "шестисот", "шестистам", "шестьюстами", "шестистах"],
        700 => ["семьсот", "семисот", "семистам", "семьюстами", "семистах"],
        800 => ["восемьсот", "восьмисот", "восьмистам", "восемьюстами", "восьмистах"],
        _ => ["девятьсот", "девятисот", "девятистам", "девятьюстами", "девятистах"],
    }
}

const ZERO: [&str; 6] = ["ноль", "ноля", "нолю", "ноль", "нолём", "ноле"];

/// A noun the rules write after a number: gender, singular forms, plural forms (six cases each).
type Noun = (&'static str, [&'static str; 6], [&'static str; 6]);

fn noun(name: &str) -> Noun {
    match name {
        "тысяча" => (
            "f",
            ["тысяча", "тысячи", "тысяче", "тысячу", "тысячей", "тысяче"],
            ["тысячи", "тысяч", "тысячам", "тысячи", "тысячами", "тысячах"],
        ),
        "миллион" => (
            "m",
            ["миллион", "миллиона", "миллиону", "миллион", "миллионом", "миллионе"],
            ["миллионы", "миллионов", "миллионам", "миллионы", "миллионами", "миллионах"],
        ),
        "миллиард" => (
            "m",
            ["миллиард", "миллиарда", "миллиарду", "миллиард", "миллиардом", "миллиарде"],
            ["миллиарды", "миллиардов", "миллиардам", "миллиарды", "миллиардами", "миллиардах"],
        ),
        "триллион" => (
            "m",
            ["триллион", "триллиона", "триллиону", "триллион", "триллионом", "триллионе"],
            ["триллионы", "триллионов", "триллионам", "триллионы", "триллионами", "триллионах"],
        ),
        "рубль" => (
            "m",
            ["рубль", "рубля", "рублю", "рубль", "рублём", "рубле"],
            ["рубли", "рублей", "рублям", "рубли", "рублями", "рублях"],
        ),
        "копейка" => (
            "f",
            ["копейка", "копейки", "копейке", "копейку", "копейкой", "копейке"],
            ["копейки", "копеек", "копейкам", "копейки", "копейками", "копейках"],
        ),
        "доллар" => (
            "m",
            ["доллар", "доллара", "доллару", "доллар", "долларом", "долларе"],
            ["доллары", "долларов", "долларам", "доллары", "долларами", "долларах"],
        ),
        "цент" => (
            "m",
            ["цент", "цента", "центу", "цент", "центом", "центе"],
            ["центы", "центов", "центам", "центы", "центами", "центах"],
        ),
        "евро" => ("n", ["евро"; 6], ["евро"; 6]),
        "гривна" => (
            "f",
            ["гривна", "гривны", "гривне", "гривну", "гривной", "гривне"],
            ["гривны", "гривен", "гривнам", "гривны", "гривнами", "гривнах"],
        ),
        "фунт" => (
            "m",
            ["фунт", "фунта", "фунту", "фунт", "фунтом", "фунте"],
            ["фунты", "фунтов", "фунтам", "фунты", "фунтами", "фунтах"],
        ),
        "пенс" => (
            "m",
            ["пенс", "пенса", "пенсу", "пенс", "пенсом", "пенсе"],
            ["пенсы", "пенсов", "пенсам", "пенсы", "пенсами", "пенсах"],
        ),
        "процент" => (
            "m",
            ["процент", "процента", "проценту", "процент", "процентом", "проценте"],
            ["проценты", "процентов", "процентам", "проценты", "процентами", "процентах"],
        ),
        "градус" => (
            "m",
            ["градус", "градуса", "градусу", "градус", "градусом", "градусе"],
            ["градусы", "градусов", "градусам", "градусы", "градусами", "градусах"],
        ),
        "грамм" => (
            "m",
            ["грамм", "грамма", "грамму", "грамм", "граммом", "грамме"],
            ["граммы", "граммов", "граммам", "граммы", "граммами", "граммах"],
        ),
        "штука" => (
            "f",
            ["штука", "штуки", "штуке", "штуку", "штукой", "штуке"],
            ["штуки", "штук", "штукам", "штуки", "штуками", "штуках"],
        ),
        "час" => (
            "m",
            ["час", "часа", "часу", "час", "часом", "часе"],
            ["часы", "часов", "часам", "часы", "часами", "часах"],
        ),
        _ => (
            "f",
            ["целая", "целой", "целой", "целую", "целой", "целой"],
            ["целых", "целых", "целым", "целых", "целыми", "целых"],
        ),
    }
}

const SCALES: [(u64, &str); 4] =
    [(1_000_000_000_000, "триллион"), (1_000_000_000, "миллиард"), (1_000_000, "миллион"), (1000, "тысяча")];

/// Index into `card_forms`' five forms (acc = nom).
fn card_case(case: usize) -> usize {
    [0, 1, 2, 0, 3, 4][case]
}

/// 1..999 in `case`; `gender` picks один/одна/одно and два/две.
fn group_words(k: u64, case: usize, gender: &str) -> Vec<&'static str> {
    let mut out = Vec::new();
    let (h, r) = (k / 100 * 100, k % 100);
    if h != 0 {
        out.push(card_forms(h)[card_case(case)]);
    }
    if (10..=19).contains(&r) {
        out.push(card_forms(r)[card_case(case)]);
        return out;
    }
    let (t, u) = (r / 10 * 10, r % 10);
    if t != 0 {
        out.push(card_forms(t)[card_case(case)]);
    }
    if u == 1 {
        out.push(one(gender)[case]);
    } else if u == 2 && gender == "f" && (case == NOM || case == ACC) {
        out.push("две");
    } else if u != 0 {
        out.push(card_forms(u)[card_case(case)]);
    }
    out
}

/// (0 singular / 1 plural, case) of the noun counted by `n` when the number stands in `case`.
fn agree(n: u64, case: usize) -> (usize, usize) {
    if n % 10 == 1 && n % 100 != 11 {
        return (0, case);
    }
    if case == NOM || case == ACC {
        return if (2..=4).contains(&(n % 10)) && !(12..=14).contains(&(n % 100)) { (0, GEN) } else { (1, GEN) };
    }
    (1, case)
}

/// The noun `name` counted by the integer `n` in `case`; after a round thousand or more it is always the genitive
/// plural (пяти тысячам рублей).
fn noun_form(name: &str, n: u64, case: usize) -> &'static str {
    let (_, sg, pl) = noun(name);
    if n >= 1000 && n.is_multiple_of(1000) {
        return pl[GEN];
    }
    let (num, c) = agree(n, case);
    if num == 0 { sg[c] } else { pl[c] }
}

/// The cardinal `n` in `case`; a leading 1 000 is said тысяча (not одна тысяча).
fn card(n: u64, case: usize, gender: &str) -> String {
    if n == 0 {
        return ZERO[case].to_string();
    }
    let mut out: Vec<&str> = Vec::new();
    for (div, name) in SCALES {
        let k = if div < 1_000_000_000_000 { n / div % 1000 } else { n / div };
        if k == 0 {
            continue;
        }
        let g = noun(name).0;
        if !(k == 1 && name == "тысяча" && n / div == 1) {
            out.extend(group_words(k, case, g));
        }
        out.push(noun_form(name, k, case));
    }
    if !n.is_multiple_of(1000) {
        out.extend(group_words(n % 1000, case, gender));
    }
    out.join(" ")
}

/// Ordinal stems (masculine nominative of the last word).
fn ord_stem(k: u64) -> &'static str {
    match k {
        1 => "первый",
        2 => "второй",
        3 => "третий",
        4 => "четвёртый",
        5 => "пятый",
        6 => "шестой",
        7 => "седьмой",
        8 => "восьмой",
        9 => "девятый",
        10 => "десятый",
        11 => "одиннадцатый",
        12 => "двенадцатый",
        13 => "тринадцатый",
        14 => "четырнадцатый",
        15 => "пятнадцатый",
        16 => "шестнадцатый",
        17 => "семнадцатый",
        18 => "восемнадцатый",
        19 => "девятнадцатый",
        20 => "двадцатый",
        30 => "тридцатый",
        40 => "сороковой",
        50 => "пятидесятый",
        60 => "шестидесятый",
        70 => "семидесятый",
        80 => "восьмидесятый",
        90 => "девяностый",
        100 => "сотый",
        200 => "двухсотый",
        300 => "трёхсотый",
        400 => "четырёхсотый",
        500 => "пятисотый",
        600 => "шестисотый",
        700 => "семисотый",
        800 => "восьмисотый",
        _ => "девятисотый",
    }
}

/// The genitive stems fused into a round ordinal (двухтысячный, пятисотмиллионный).
fn fused_part(k: u64) -> &'static str {
    match k {
        1 => "одно",
        100 => "сто",
        90 => "девяносто",
        _ => card_forms(k)[1],
    }
}

/// Endings by gender (m f n pl) and case: hard stems (первый/второй) and the soft третий.
fn hard(gender: &str) -> [&'static str; 6] {
    match gender {
        "f" => ["ая", "ой", "ой", "ую", "ой", "ой"],
        "n" => ["ое", "ого", "ому", "ое", "ым", "ом"],
        "pl" => ["ые", "ых", "ым", "ые", "ыми", "ых"],
        _ => ["ый", "ого", "ому", "ый", "ым", "ом"],
    }
}

fn soft(gender: &str) -> [&'static str; 6] {
    match gender {
        "f" => ["ья", "ьей", "ьей", "ью", "ьей", "ьей"],
        "n" => ["ье", "ьего", "ьему", "ье", "ьим", "ьем"],
        "pl" => ["ьи", "ьих", "ьим", "ьи", "ьими", "ьих"],
        _ => ["ий", "ьего", "ьему", "ий", "ьим", "ьем"],
    }
}

/// `word` without its last two characters.
fn cut2(word: &str) -> &str {
    let end = word.char_indices().rev().nth(1).map_or(0, |(i, _)| i);
    &word[..end]
}

fn inflect_ord(word: &str, case: usize, gender: &str) -> String {
    if word.ends_with("третий") {
        return format!("{}{}", cut2(word), soft(gender)[case]);
    }
    if word.ends_with("ой") && gender == "m" && (case == NOM || case == ACC) {
        return word.to_string();
    }
    format!("{}{}", cut2(word), hard(gender)[case])
}

/// The genitive stem of 1..999 written as one word before -тысячный/-миллионный.
fn fused(k: u64) -> String {
    let mut out = String::new();
    let (h, r) = (k / 100 * 100, k % 100);
    if h != 0 {
        out.push_str(fused_part(h));
    }
    if (10..=19).contains(&r) {
        out.push_str(card_forms(r)[1]);
        return out;
    }
    let (t, u) = (r / 10 * 10, r % 10);
    if t != 0 {
        out.push_str(fused_part(t));
    }
    if u != 0 {
        out.push_str(fused_part(u));
    }
    out
}

/// The ordinal `n` in `case` and `gender` (m f n pl): две тысячи двадцать четвёртого.
fn ordinal(n: u64, case: usize, gender: &str) -> String {
    if n == 0 {
        return inflect_ord("нулевой", case, gender);
    }
    let low = n % 1000;
    let (last, rest): (String, u64) = if low != 0 {
        let (h, r) = (low / 100 * 100, low % 100);
        if r == 0 {
            (ord_stem(h).to_string(), n - h)
        } else if r < 20 || r % 10 == 0 {
            (ord_stem(r).to_string(), n - r)
        } else {
            (ord_stem(r % 10).to_string(), n - r % 10)
        }
    } else {
        let mut found = (String::new(), 0);
        for (div, name) in SCALES {
            if n.is_multiple_of(div) {
                let k = n / div % 1000;
                let tail = match name {
                    "тысяча" => "тысячный",
                    "миллион" => "миллионный",
                    "миллиард" => "миллиардный",
                    _ => "триллионный",
                };
                found = (format!("{}{}", if k == 1 { String::new() } else { fused(k) }, tail), n - k * div);
                break;
            }
        }
        found
    };
    let prefix = if rest != 0 { card(rest, NOM, "m") } else { String::new() };
    let word = inflect_ord(&last, case, gender);
    if prefix.is_empty() { word } else { format!("{prefix} {word}") }
}

const DENOM: [&str; 6] = ["десят", "сот", "тысячн", "десятитысячн", "стотысячн", "миллионн"];

/// i,frac in `case`: две целых пять десятых, двух целых пяти десятых.
fn decimal(i: u64, frac: &str, case: usize) -> String {
    let f = py_int(frac) as u64;
    let (_, sg, pl) = noun("целая");
    let one_i = i % 10 == 1 && i % 100 != 11;
    let whole = format!("{} {}", card(i, case, "f"), if one_i { sg[case] } else { pl[case] });
    let end = if f % 10 == 1 && f % 100 != 11 {
        hard("f")[case]
    } else if case == NOM || case == ACC {
        "ых"
    } else {
        hard("pl")[case]
    };
    format!("{} {} {}{}", whole, card(f, case, "f"), DENOM[frac.chars().count() - 1], end)
}

/// ё in the number words the grammar writes with е (трехсот, четвертого).
fn yo(s: &str) -> String {
    let s = sub(r"(?<![^\W\d_])(тр|четыр)ех", s, |m| format!("{}ёх", g(m, 1)));
    let s = sub(r"(?<![^\W\d_])(тр|четыр)ем(?!я)", &s, |m| format!("{}ём", g(m, 1)));
    sub(r"четверт(?=[ыоау])", &s, |_| "четвёрт".to_string())
}

/// `re.sub` without hits (for the rules' own helpers).
fn sub(pat: &str, s: &str, mut f: impl FnMut(&Captures<'_, str>) -> String) -> String {
    super::super::sub_plain(&rx(pat), s, |m| Some(f(m)))
}

fn to_int(s: &str) -> u64 {
    py_int(s) as u64
}

// ------------------------------------------------------------------------------------------------- shared patterns
const NUM: &str = r"\d{1,3}(?:[ \x{A0}]\d{3}){1,4}|\d{1,15}";
/// A number that is not part of a longer token (a code, a phone number, a version, a time).
const LB: &str = r"(?<![\w\-–—.,/:+])";
const RB: &str = r"(?![\d]|[.,:/\-]\d|[^\W\d_])";
const SP: &str = r"[ \x{A0}]";
/// A span an earlier rule set aside (U+E000 … U+E001) is skipped: every pattern starts with this alternative.
const SKIP: &str = "\u{e000}[^\u{e001}]*\u{e001}|";

/// The preposition before a number, and the case it gives it (NONE: depends on the noun after the number).
const PREP_CASE: &[(&str, usize)] = &[
    ("около", GEN),
    ("более", GEN),
    ("менее", GEN),
    ("больше", GEN),
    ("меньше", GEN),
    ("свыше", GEN),
    ("порядка", GEN),
    ("до", GEN),
    ("от", GEN),
    ("из", GEN),
    ("для", GEN),
    ("без", GEN),
    ("после", GEN),
    ("кроме", GEN),
    ("вместо", GEN),
    ("среди", GEN),
    ("возле", GEN),
    ("против", GEN),
    ("у", GEN),
    ("старше", GEN),
    ("моложе", GEN),
    ("младше", GEN),
    ("дороже", GEN),
    ("дешевле", GEN),
    ("выше", GEN),
    ("ниже", GEN),
    ("течение", GEN),
    ("протяжении", GEN),
    ("ради", GEN),
    ("к", DAT),
    ("ко", DAT),
    ("благодаря", DAT),
    ("согласно", DAT),
    ("вопреки", DAT),
    ("с", NONE),
    ("со", NONE),
    ("по", NONE),
    ("в", NONE),
    ("во", NONE),
    ("на", NONE),
    ("о", NONE),
    ("об", NONE),
    ("обо", NONE),
    ("при", NONE),
    ("за", NONE),
    ("под", NONE),
    ("над", NONE),
    ("перед", NONE),
    ("между", NONE),
];

fn lookup(table: &[(&str, usize)], key: &str) -> Option<usize> {
    table.iter().find(|(k, _)| *k == key).map(|&(_, v)| v)
}

fn prep_case(p: &str) -> Option<usize> {
    lookup(PREP_CASE, p)
}

/// A group matching any of `preps` as a whole word, lowercase or capitalised (longest first).
fn prep_rx(preps: &[&str]) -> String {
    let mut ps: Vec<&str> = preps.to_vec();
    ps.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    let alts: Vec<String> = ps
        .iter()
        .map(|p| {
            let mut it = p.chars();
            let first = it.next().unwrap();
            format!("[{}{}]{}", first.to_uppercase(), first, it.as_str())
        })
        .collect();
    format!("(?<![^\\s(«\\\"„“])({})", alts.join("|"))
}

fn keys(table: &[(&'static str, usize)]) -> Vec<&'static str> {
    table.iter().map(|&(k, _)| k).collect()
}

static PREP_RX: LazyLock<String> = LazyLock::new(|| prep_rx(&keys(PREP_CASE)));

fn skipped(m: &Captures<'_, str>) -> bool {
    m[0].starts_with('\u{e000}')
}

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).unwrap().start()
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).unwrap().end()
}

/// `re.match(pat, s)`: the captures of a pattern anchored with `^`.
fn caps<'t>(pat: &str, s: &'t str) -> Option<Captures<'t, str>> {
    rx(pat).captures(s).ok().flatten()
}

/// The case the number n takes after `prep` given the word after it (NONE: leave the number as it is).
fn noun_case(prep: &str, noun: &str, n: u64) -> usize {
    let p = prep.to_lowercase();
    let c = prep_case(&p).unwrap();
    if c != NONE {
        return c;
    }
    let one = n % 10 == 1 && n % 100 != 11;
    if p == "с" || p == "со" {
        if search(r"(?:ами|ями|ьми)$", noun) || one && search(r"(?:ом|ем|ём|ой|ей|ью)$", noun) {
            return INS;
        }
        return GEN;
    }
    if ["в", "во", "на", "о", "об", "обо", "при"].contains(&p.as_str()) {
        return if search(r"[ая]х$", noun) { PREP } else { NONE };
    }
    if p == "по" {
        return if search(r"[ая]м$", noun) { DAT } else { NONE };
    }
    if search(r"(?:ами|ями|ьми)$", noun) { INS } else { NONE }
}

/// A word the grammar passes through after a number (детьми, часа.), not a unit or an abbreviation it reads (кг,
/// мин., мая).
fn plain_word(tok: &str) -> bool {
    let w = sub(r#"[.,;:!?)»\"]+$"#, tok, |_| String::new());
    w.is_empty() || search(r"^[^\W\d_]+$", &w) && words(&format!("5 {w}"), "ru") == format!("пять {w}")
}

/// The noun after a number (an adjective in -ых/-ым/-ыми before it is looked through; in a range N до M the noun after
/// M).
fn counted_noun(rest: &str) -> String {
    let pat = format!(r"^{SP}+(?:(?:до|по){SP}+\d+{SP}+)?([^\W\d_]+)(?:{SP}+([^\W\d_]+))?");
    let Some(m) = caps(&pat, rest) else { return String::new() };
    if !g(&m, 2).is_empty() && search(r"(?:ых|их|ым|им|ыми|ими)$", g(&m, 1)) {
        return g(&m, 2).to_string();
    }
    g(&m, 1).to_string()
}

/// The sentence period an abbreviation's dot doubled as: kept when the abbreviation ends the text, a line or a
/// sentence.
fn drop_dot(tok: &str, rest: &str) -> &'static str {
    if tok.ends_with('.') && (py_strip(rest).is_empty() || search(r"^[ \t]*\n|^\s+[А-ЯЁA-Z]", rest)) {
        "."
    } else {
        ""
    }
}

fn head(prep: &str) -> String {
    if prep.is_empty() { String::new() } else { format!("{prep} ") }
}

/// The preposition (if any) before the words a rule wrote, with с/к/в vocalized before a cluster (со ста, со
/// второго, ко второму, во втором).
fn lead(prep: &str, spoken: &str) -> String {
    if prep.is_empty() {
        return spoken.to_string();
    }
    let p = prep.to_lowercase();
    let vocal = p == "с" && search(r"^(?:[сзшж][бвгджзклмнпрстфхцчшщ]|вт|вс|мн)", spoken)
        || p == "к" && search(r"^(?:вт|вс|мн)", spoken)
        || p == "в" && search(r"^[вф][бвгджзклмнпрстфхцчшщ]", spoken);
    if vocal { format!("{prep}о {spoken}") } else { format!("{prep} {spoken}") }
}

// ------------------------------------------------------------------------------------------------- rules

/// Acronyms said as words: left as typed for the voice, like the pronounceable Latin words.
const ACRONYMS: &[&str] =
    &["NASA", "NATO", "UNESCO", "UNICEF", "FIFA", "UEFA", "COVID", "OPEC", "IKEA", "NASDAQ", "ISRO", "CERN"];
const ONSETS: &[&str] = &[
    "bl", "br", "ch", "cl", "cr", "dr", "dw", "fl", "fr", "gl", "gn", "gr", "kl", "kn", "kr", "ph", "pl", "pr", "ps",
    "qu", "sc", "sh", "sk", "sl", "sm", "sn", "sp", "st", "sw", "th", "tr", "tw", "wh", "wr", "chr", "sch", "scr",
    "shr", "spl", "spr", "squ", "str", "thr",
];

/// A Latin word a reader says as a word: three or more letters, not all capitals, with a vowel, an English onset and no
/// run of four consonants (iPhone, YouTube, python, web; not Mbit, Gbps).
fn pronounceable(w: &str) -> bool {
    let low = w.to_lowercase();
    let onset: String = low.chars().take_while(|c| !"aeiouy".contains(*c)).collect();
    if onset == low || onset.chars().count() > 1 && !ONSETS.contains(&onset.as_str()) || search(r"[^aeiouy]{4}", &low) {
        return false;
    }
    w != w.to_uppercase() && w.chars().count() >= 3
}

fn ru_latin(t: String, c: &mut Ctx) -> String {
    if !search(r"[а-яёА-ЯЁ]", &t) {
        return t;
    }
    let pat = format!(r"{SKIP}(?<![\w@./:\-])([A-Za-z]+)(?![\w@/]|[.:][A-Za-z\d]|-[^\d])(-(?=\d))?");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (w, dash) = (g(m, 1), g(m, 2));
        if ACRONYMS.contains(&w) {
            return Some(format!("\u{e000}{w}\u{e001}{}", if dash.is_empty() { "" } else { " " }));
        }
        if !dash.is_empty() || !pronounceable(w) {
            return None;
        }
        if search(r"\d[ \x{A0}]?$", &t[..start(m)])
            && words(&format!("5 {w}"), "ru") != format!("пять {}", words(w, "ru"))
        {
            return None; // a unit after a number (100 Mbit), read by the grammar
        }
        Some(format!("\u{e000}{w}\u{e001}"))
    })
}

const CITY: &[(&str, &str)] = &[
    ("в", "городе"),
    ("во", "городе"),
    ("на", "городе"),
    ("о", "городе"),
    ("об", "городе"),
    ("при", "городе"),
    ("из", "города"),
    ("от", "города"),
    ("до", "города"),
    ("около", "города"),
    ("для", "города"),
    ("у", "города"),
    ("возле", "города"),
    ("близ", "города"),
    ("вблизи", "города"),
    ("к", "городу"),
    ("ко", "городу"),
    ("по", "городу"),
    ("с", "городом"),
    ("со", "городом"),
    ("над", "городом"),
    ("под", "городом"),
    ("за", "городом"),
    ("перед", "городом"),
    ("между", "городом"),
];

fn ru_city(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}(?<![\w\-.])(?:([А-Яа-яЁё]+|\d+)[ \x{{A0}}]+)?г\.[ \x{{A0}}]?(?=[А-ЯЁ][а-яё])");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let word = g(m, 1);
        if word.is_empty() {
            if search(r"\d[ \x{A0}]*$", &t[..start(m)]) {
                return None;
            }
            return Some("город ".into());
        }
        if search(r"^\d", word) {
            return None;
        }
        let low = word.to_lowercase();
        let city = CITY.iter().find(|(k, _)| *k == low).map_or("город", |&(_, v)| v);
        Some(format!("{word} {city} "))
    })
}

const CUR_TOK: &[(&str, &str)] = &[
    ("₽", "рубль"),
    ("руб.", "рубль"),
    ("руб", "рубль"),
    ("р.", "рубль"),
    ("$", "доллар"),
    ("USD", "доллар"),
    ("€", "евро"),
    ("EUR", "евро"),
    ("RUB", "рубль"),
    ("грн.", "гривна"),
    ("грн", "гривна"),
    ("UAH", "гривна"),
    ("₴", "гривна"),
    ("£", "фунт"),
    ("GBP", "фунт"),
];

fn find<'a>(table: &[(&str, &'a str)], key: &str) -> Option<&'a str> {
    table.iter().find(|(k, _)| *k == key).map(|&(_, v)| v)
}

fn minor(major: &str) -> &'static str {
    match major {
        "рубль" | "гривна" => "копейка",
        "фунт" => "пенс",
        _ => "цент",
    }
}

fn ru_cents(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}({NUM}),(\d{{2}}){SP}?(₽|руб\.?|р\.|\$|USD|€|EUR|RUB|грн\.?|UAH|₴|£|GBP)(?![\w])",
        *PREP_RX
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, whole, cents, cur) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let mut case = if prep.is_empty() { NOM } else { prep_case(&prep.to_lowercase()).unwrap_or(NONE) };
        if case == NONE {
            case = NOM;
        }
        let (n, k) = (to_int(whole), py_int(cents) as u64);
        let major = find(CUR_TOK, cur).unwrap();
        let mut out = format!("{} {}", card(n, case, noun(major).0), noun_form(major, n, case));
        if k != 0 {
            let mi = minor(major);
            out += &format!(" {} {}", card(k, case, noun(mi).0), noun_form(mi, k, case));
        }
        Some(format!("{}{}", lead(prep, &out), drop_dot(cur, &t[end(m)..])))
    })
}

const MONTHS: [&str; 12] = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
];
/// Words before a date that keep it in the nominative (Сегодня 3 мая).
const NOM_BEFORE: &[&str] = &[
    "сегодня",
    "завтра",
    "вчера",
    "послезавтра",
    "позавчера",
    "наступило",
    "наступит",
    "настало",
    "настанет",
    "наступает",
    "это",
    "есть",
    "дата",
    "число",
];
const DATE_PREP: &[(&str, usize)] = &[
    ("к", DAT),
    ("ко", DAT),
    ("на", NOM),
    ("в", NOM),
    ("во", NOM),
    ("про", NOM),
    ("через", NOM),
    ("за", NOM),
    ("по", NOM),
    ("о", PREP),
    ("об", PREP),
    ("при", PREP),
    ("с", GEN),
    ("со", GEN),
    ("до", GEN),
    ("от", GEN),
    ("после", GEN),
    ("около", GEN),
    ("из", GEN),
    ("для", GEN),
    ("без", GEN),
    ("кроме", GEN),
    ("вместо", GEN),
    ("накануне", GEN),
    ("ранее", GEN),
    ("позднее", GEN),
    ("позже", GEN),
    ("раньше", GEN),
    ("середины", GEN),
    ("начала", GEN),
    ("конца", GEN),
    ("течение", GEN),
];
static DATE_PREP_RX: LazyLock<String> = LazyLock::new(|| prep_rx(&keys(DATE_PREP)));
/// Any preposition right before a bare range (между 5–10 мая).
static BARE_PREP_RX: LazyLock<String> = LazyLock::new(|| {
    let mut ps = keys(PREP_CASE);
    ps.sort();
    format!("(?<![^\\s(«\\\"„“])(?:{}){SP}*$", ps.join("|"))
});

/// The case of the day of a date: from its preposition; with none, genitive after a word (подписан 3 мая) and
/// nominative at the start of a sentence, after a comma or after сегодня / это.
fn date_case(prep: &str, before: &str) -> usize {
    if !prep.is_empty() {
        return lookup(DATE_PREP, &prep.to_lowercase()).unwrap();
    }
    let m = caps(r"([^\W\d_]+)[ \x{A0}]*$", before);
    let Some(m) = m.filter(|_| !py_strip(before).is_empty() && !search(r#"[.!?:;,—–(\"«\n][ \x{A0}]*$"#, before))
    else {
        return NOM;
    };
    let w = g(&m, 1).to_lowercase();
    if let Some(c) = lookup(DATE_PREP, &w) {
        return c; // a preposition the pattern did not take (after a stray mark: **в 5 мая)
    }
    if NOM_BEFORE.contains(&w.as_str()) { NOM } else { GEN }
}

fn year_words(y: u64) -> String {
    format!("{} года", ordinal(y, GEN, "m"))
}

fn ru_date(t: String, c: &mut Ctx) -> String {
    let year_tail = format!(r"(?:{SP}+(\d{{4}})(?:{SP}?(г\.|г(?![\w.])|года(?![\w])))?)?");
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}(\d{{1,2}})(?:({SP}*[-–—]{SP}*|{SP}+(?:до|по){SP}+)(\d{{1,2}}))?{SP}+({})(?![\w]){year_tail}",
        *DATE_PREP_RX,
        MONTHS.join("|")
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, d1, sep, d2, month, year, yw) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6), g(m, 7));
        let (a, b) = (py_int(d1) as u64, if d2.is_empty() { 0 } else { py_int(d2) as u64 });
        if !(1..=31).contains(&a) || !d2.is_empty() && !(1..=31).contains(&b) {
            return None;
        }
        let case = date_case(prep, &t[..start(m)]);
        let s = py_strip(sep).to_lowercase();
        let mut out = if !d2.is_empty() && (s == "до" || s == "по") {
            format!(
                "{} {} {}",
                ordinal(a, if case == NOM { GEN } else { case }, "n"),
                s,
                ordinal(b, if s == "до" { GEN } else { NOM }, "n")
            )
        } else if !d2.is_empty() && search(&BARE_PREP_RX, &t[..start(m)].to_lowercase()) {
            return None; // между 5–10 …: a preposition the pattern did not take
        } else if !d2.is_empty() {
            if !prep.is_empty() {
                return None;
            }
            format!("с {} по {}", ordinal(a, GEN, "n"), ordinal(b, NOM, "n"))
        } else {
            ordinal(a, case, "n")
        };
        out += &format!(" {month}");
        if !year.is_empty() {
            out += &format!(" {}{}", year_words(py_int(year) as u64), drop_dot(yw, &t[end(m)..]));
        }
        Some(lead(prep, &out))
    });
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}(?:(\d{{1,2}})([./])(\d{{1,2}})\3(\d{{4}})|(\d{{4}})-(\d{{2}})-(\d{{2}}))(?:{SP}?(г\.|г(?![\w.])|года(?![\w])))?(?![\w]|[.,/\-]\d)",
        *DATE_PREP_RX
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, yw) = (g(m, 1), g(m, 9));
        let (d, mo, y) = if !g(m, 2).is_empty() {
            (py_int(g(m, 2)) as u64, py_int(g(m, 4)) as u64, py_int(g(m, 5)) as u64)
        } else {
            (py_int(g(m, 8)) as u64, py_int(g(m, 7)) as u64, py_int(g(m, 6)) as u64)
        };
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) {
            return None;
        }
        let case = date_case(prep, &t[..start(m)]);
        let spoken = format!("{} {} {}", ordinal(d, case, "n"), MONTHS[(mo - 1) as usize], year_words(y));
        Some(format!("{}{}", lead(prep, &spoken), drop_dot(yw, &t[end(m)..])))
    })
}

/// The case of the year after a preposition when the year word is г. (году: prepositional, or dative after к/по).
const YEAR_PREP: &[(&str, usize)] = &[
    ("в", PREP),
    ("во", PREP),
    ("о", PREP),
    ("об", PREP),
    ("при", PREP),
    ("к", DAT),
    ("ко", DAT),
    ("по", NOM),
    ("на", NOM),
    ("за", NOM),
    ("через", NOM),
    ("про", NOM),
    ("перед", INS),
    ("между", INS),
    ("над", INS),
    ("под", NOM),
    ("с", GEN),
    ("со", GEN),
    ("до", GEN),
    ("от", GEN),
    ("после", GEN),
    ("около", GEN),
    ("из", GEN),
    ("для", GEN),
    ("без", GEN),
    ("кроме", GEN),
    ("накануне", GEN),
    ("середины", GEN),
    ("начала", GEN),
    ("конца", GEN),
    ("течение", GEN),
];
static YEAR_PREP_RX: LazyLock<String> = LazyLock::new(|| prep_rx(&keys(YEAR_PREP)));
const YEAR_FORMS: [&str; 6] = ["год", "года", "году", "год", "годом", "году"];
const YEARS_FORMS: [&str; 6] = ["годы", "годов", "годам", "годы", "годами", "годах"];

fn year_case(prep: &str, word: &str) -> usize {
    let p = prep.to_lowercase();
    match word {
        "года" => GEN,
        "год" => NOM,
        "годом" => INS,
        "годе" => PREP,
        "году" => {
            if ["к", "ко", "по"].contains(&p.as_str()) {
                DAT
            } else {
                PREP
            }
        }
        _ => lookup(YEAR_PREP, &p).unwrap_or(GEN),
    }
}

fn ru_year(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}(\d{{3,4}})(?:{SP}+(по|до){SP}+(\d{{4}}))?(?:-(?:м|го|й))?{SP}?(г\.|г(?![\w.])|гг\.|года|году|годом|годе|год)(?![\w])",
        *YEAR_PREP_RX
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, sep, b, word) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        let rest = &t[end(m)..];
        let p = prep.to_lowercase();
        if a.chars().count() == 3 && !((p == "в" || p == "во") && word == "г." && b.is_empty()) {
            return None;
        }
        if !b.is_empty() {
            if !["с", "со", "от"].contains(&p.as_str()) || !["г.", "г", "гг.", "год", "года"].contains(&word)
            {
                return None;
            }
            let case = if sep == "по" { NOM } else { GEN };
            return Some(format!(
                "{} {} {} {}{}",
                lead(prep, &ordinal(py_int(a) as u64, GEN, "m")),
                sep,
                ordinal(py_int(b) as u64, case, "m"),
                YEAR_FORMS[case],
                drop_dot(word, rest)
            ));
        }
        if word == "гг." {
            return None;
        }
        let case = year_case(prep, word);
        let yw = if word == "г." || word == "г" {
            format!("{}{}", YEAR_FORMS[case], drop_dot(word, rest))
        } else {
            word.to_string()
        };
        Some(format!("{} {}", lead(prep, &ordinal(py_int(a) as u64, case, "m")), yw))
    });
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}(\d{{4}}){SP}?[–—-]{SP}?(\d{{4}}){SP}?(гг\.|годы|годов|годам|годами|годах)(?![\w])",
        *YEAR_PREP_RX
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, b, word) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let case = if word == "гг." {
            if prep.is_empty() { NOM } else { lookup(YEAR_PREP, &prep.to_lowercase()).unwrap_or(GEN) }
        } else {
            YEARS_FORMS.iter().position(|&w| w == word).unwrap()
        };
        Some(format!(
            "{} – {} {}{}",
            lead(prep, &ordinal(py_int(a) as u64, case, "m")),
            ordinal(py_int(b) as u64, case, "m"),
            YEARS_FORMS[case],
            drop_dot(word, &t[end(m)..])
        ))
    })
}

const TIME_PREP: &[(&str, usize)] =
    &[("к", DAT), ("ко", DAT), ("до", GEN), ("с", GEN), ("со", GEN), ("от", GEN), ("после", GEN), ("около", GEN)];

fn ru_time(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{}{SP}+(\d{{1,2}}):(\d{{2}})(?![\d:]|[.,]\d)", prep_rx(&keys(TIME_PREP)));
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, h, mi) = (g(m, 1), py_int(g(m, 2)) as u64, py_int(g(m, 3)) as u64);
        if h > 24 || mi > 59 {
            return None;
        }
        let case = lookup(TIME_PREP, &prep.to_lowercase()).unwrap();
        let mut out = card(h, case, "m");
        if mi == 0 {
            out += &format!(" {}", noun_form("час", h, case));
        } else {
            out += &format!(" {}{}", if mi < 10 { "ноль " } else { "" }, card(mi, case, "f"));
        }
        Some(lead(prep, &out))
    })
}

fn ru_half(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}(?:{}{SP}+)?{LB}(?:(\d{{1,9}}){SP}+)?1/2(?![\d/])", *PREP_RX);
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, whole) = (g(m, 1), g(m, 2));
        let nm = caps(&format!(r"^{SP}+([а-яё]+)"), &t[end(m)..])?;
        if !plain_word(g(&nm, 1)) {
            return None; // 1/2 млн: not a noun
        }
        let noun = g(&nm, 1);
        let p = prep.to_lowercase();
        let mut case;
        if ["в", "во", "на", "за", "через", "про"].contains(&p.as_str()) {
            case = ACC;
        } else if !prep.is_empty() {
            case = prep_case(&p).unwrap_or(NONE);
            if case == NONE || case == INS {
                return None;
            }
        } else {
            case = NOM;
        }
        let w = if !whole.is_empty() {
            let n = py_int(whole) as u64;
            let fem = search(r"[ыи]$", noun);
            if n == 1 {
                if case == NOM || case == ACC {
                    if fem { "полторы" } else { "полтора" }.to_string()
                } else {
                    "полутора".to_string()
                }
            } else {
                format!("{} с половиной", card(n, case, if fem { "f" } else { "m" }))
            }
        } else {
            let before = &t[..start(m)];
            if case == NOM && !py_strip(before).is_empty() && !search(r"[.!?:;\n—–][ \x{A0}]*$", before) {
                case = ACC;
            }
            ["половина", "половины", "половине", "половину", "половиной", "половине"][case].to_string()
        };
        Some(lead(prep, &w))
    })
}

fn ru_ordinal_e(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}(\d{{1,12}})-е(?![\w\-])");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let nm = caps(&format!(r"^{SP}+([а-яё]+)"), &t[end(m)..])?;
        let w = g(&nm, 1);
        if !MONTHS.contains(&w) && !search(r"(?:о|ие|ье|мя|ое|ее|це|ле|ре|ще)$", w) {
            return None;
        }
        Some(ordinal(py_int(g(m, 1)) as u64, NOM, "n"))
    })
}

fn ru_ordinal_range(t: String, c: &mut Ctx) -> String {
    let pat =
        format!(r"{SKIP}{}{SP}+(\d{{1,3}}){SP}+по{SP}+(\d{{1,3}})(?={SP}+([а-яё]+)(?![\w]))", prep_rx(&["с", "со"]));
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, b, noun_w) = (g(m, 1), py_int(g(m, 2)) as u64, py_int(g(m, 3)) as u64, g(m, 4));
        let gnd = if search(r"[бвгджзклмнпрстфхцчшщй]$", noun_w) {
            "m"
        } else if search(r"[ую]$", noun_w) {
            "f"
        } else if search(r"[ое]$", noun_w) {
            "n"
        } else {
            return None;
        };
        Some(format!("{} по {}", lead(prep, &ordinal(a, GEN, gnd)), ordinal(b, ACC, gnd)))
    })
}

fn ru_range(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}(?:{}{SP}+)?{LB}({NUM}){SP}?[–—]{SP}?({NUM}){RB}(?:({SP}?%)|(?={SP}?\S))", *PREP_RX);
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, b, pct) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let (na, nb) = (to_int(a), to_int(b));
        if na >= nb || (1000..=2100).contains(&na) && (1000..=2100).contains(&nb) {
            return None; // a score (2–1) or a range of years
        }
        if prep.is_empty() {
            return Some(format!("от {a} до {b}{pct}"));
        }
        let p = prep.to_lowercase();
        let case = if ["в", "во", "на", "за", "через", "по", "про"].contains(&p.as_str()) {
            ACC
        } else if prep_case(&p) == Some(GEN) {
            GEN
        } else {
            return None;
        };
        let rest = &t[end(m)..];
        let gnd = if !pct.is_empty() {
            "m"
        } else {
            let tok = caps(&format!(r"^{SP}*(\S*)"), rest).map_or(String::new(), |x| g(&x, 1).to_string());
            let noun_w = counted_noun(rest);
            if tok.is_empty() || !plain_word(&tok) || noun_w.is_empty() {
                return None;
            }
            if case == ACC { gender_of(&noun_w, 2, NOM) } else { gender_of(&noun_w, 1, GEN) }
        };
        let cs = if gnd == "f" && case == ACC { ACC } else { case };
        let mut out = format!("{}-{}", card(na, cs, gnd), card(nb, cs, gnd));
        if !pct.is_empty() {
            out += &format!(" {}", noun_form("процент", nb, case));
        }
        Some(lead(prep, &out))
    })
}

const SCALE_TOK: &[(&str, &str)] = &[
    ("тыс.", "тысяча"),
    ("тыс", "тысяча"),
    ("млн", "миллион"),
    ("млн.", "миллион"),
    ("млрд", "миллиард"),
    ("млрд.", "миллиард"),
    ("трлн", "триллион"),
    ("трлн.", "триллион"),
];
const UNIT_TOK: &[(&str, &str)] = &[
    ("₽", "рубль"),
    ("руб.", "рубль"),
    ("руб", "рубль"),
    ("р.", "рубль"),
    ("$", "доллар"),
    ("€", "евро"),
    ("%", "процент"),
    ("°C", "градус"),
    ("°С", "градус"),
    ("°", "градус"),
    ("г", "грамм"),
    ("г.", "грамм"),
    ("шт.", "штука"),
    ("шт", "штука"),
];
const SCALE_RX: &str = r"(тыс\.?|млн\.?|млрд\.?|трлн\.?)";
const UNIT_RX: &str = r"(₽|руб\.?|р\.|\$|€|%|°[CС]?|г(?![.\w])|г\.(?=\s|$)|шт\.?)";

/// The unit word after the number: genitive plural after a scale word, genitive singular after a decimal.
fn unit_words(unit: &str, n: u64, frac: &str, case: usize, after_scale: bool) -> String {
    let name = find(UNIT_TOK, unit).unwrap();
    let (_, sg, pl) = noun(name);
    let w = if after_scale {
        pl[GEN]
    } else if !frac.is_empty() {
        sg[GEN]
    } else {
        noun_form(name, n, case)
    };
    if unit == "°C" || unit == "°С" { format!("{w} Цельсия") } else { w.to_string() }
}

fn sign_word(sign: &str) -> &'static str {
    match py_strip(sign) {
        "" => "",
        "+" | "плюс" => "плюс ",
        _ => "минус ",
    }
}

/// A sign before the number (a shared rule may already have written + as плюс).
static SIGN_RX: LazyLock<String> = LazyLock::new(|| format!(r"([-−+]{SP}?|(?:плюс|минус){SP}+)?"));

fn number_part(sign: &str, whole: &str, frac: &str, case: usize, gender: &str) -> String {
    let out = sign_word(sign);
    if !frac.is_empty() {
        return format!("{out}{}", decimal(to_int(whole), frac, case));
    }
    format!("{out}{}", card(to_int(whole), case, gender))
}

fn ru_case(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}{}{SP}+{}({NUM})(?:,(\d{{1,6}}))?{RB}(?:{SP}?{SCALE_RX}(?![\w]))?(?:{SP}?{UNIT_RX}(?![\w]))?",
        *PREP_RX, *SIGN_RX
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, sign, whole, frac, scale, unit) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
        let rest = &t[end(m)..];
        if scale.is_empty() && unit.is_empty() {
            let tok = caps(&format!(r"^{SP}*(\S*)"), rest).map_or(String::new(), |x| g(&x, 1).to_string());
            if tok == "по" && ["с", "со"].contains(&prep.to_lowercase().as_str()) {
                return None; // с 1 по 5 класс: often ordinals, left to the grammar
            }
            if !plain_word(&tok) {
                return None; // a unit or a date the grammar reads: ru.case-unit / the grammar
            }
        }
        if prep.chars().count() == 1
            && scale.is_empty()
            && unit.is_empty()
            && search(&format!(r"^{SP}*[^\s\w]*{SP}*$"), rest)
        {
            return None; // К 123 alone: a one-letter preposition with nothing after the number may be a label
        }
        if unit == "г." && frac.is_empty() && to_int(whole) >= 100 {
            return None; // до 988 г.: maybe a year
        }
        let noun_w = if !scale.is_empty() || !unit.is_empty() { String::new() } else { counted_noun(rest) };
        let mut case = noun_case(prep, &noun_w, to_int(whole));
        if case == NONE
            && ["на", "в", "во", "за", "про", "через"].contains(&prep.to_lowercase().as_str())
            && (!frac.is_empty() || !scale.is_empty())
        {
            case = ACC; // на 1,5 млрд → на одну целую пять десятых миллиарда
        }
        if case == NONE {
            return None;
        }
        let n = to_int(whole);
        if !scale.is_empty() {
            let name = find(SCALE_TOK, scale).unwrap();
            let mut out;
            if n == 1 && frac.is_empty() && sign.is_empty() && name == "тысяча" {
                out = noun_form(name, 1, case).to_string(); // тысяча, not одна тысяча
            } else {
                out = format!("{} ", number_part(sign, whole, frac, case, noun(name).0));
                out += if !frac.is_empty() { noun(name).1[GEN] } else { noun_form(name, n, case) };
            }
            if !unit.is_empty() {
                out += &format!(" {}", unit_words(unit, n, frac, case, true));
            }
            let tok = if unit.is_empty() { scale } else { unit };
            return Some(format!("{}{}", lead(prep, &out), drop_dot(tok, rest)));
        }
        if !unit.is_empty() {
            let name = find(UNIT_TOK, unit).unwrap();
            let out = format!(
                "{} {}",
                number_part(sign, whole, frac, case, noun(name).0),
                unit_words(unit, n, frac, case, false)
            );
            return Some(format!("{}{}", lead(prep, &out), drop_dot(unit, rest)));
        }
        let gender = if noun_w.is_empty() { "m" } else { gender_of(&noun_w, n, case) };
        Some(lead(prep, &number_part(sign, whole, frac, case, gender)))
    })
}

fn ru_case_unit(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{}{SP}+{}({NUM})(?:,(\d{{1,6}}))?{RB}{SP}?([^\s\d][^\s]*)", *PREP_RX, *SIGN_RX);
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, sign, whole, frac, unit) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        let p = prep.to_lowercase();
        if !(prep_case(&p) == Some(GEN) || p == "с" || p == "со") || plain_word(unit) {
            return None;
        }
        let n = to_int(whole);
        if !frac.is_empty() {
            let gw = words(&format!("около 1 {unit}"), "ru");
            let mm = caps(r"^около одн(?:ого|ой) (.+)$", &gw)?;
            return Some(lead(prep, &format!("{} {}", number_part(sign, whole, frac, GEN, "m"), g(&mm, 1))));
        }
        let gw = words(&format!("около {n} {unit}"), "ru");
        if !gw.starts_with("около ") || gw.ends_with(&format!(" {unit}")) {
            return None;
        }
        let tail: String = gw.chars().skip(6).collect();
        Some(lead(prep, &format!("{}{}", sign_word(sign), yo(&tail))))
    })
}

/// Masculine nouns in -а/-я, and the masculine and neuter genitive (or animate accusative) forms after 1.
const MASC_A: &[&str] = &[
    "мужчина",
    "папа",
    "дедушка",
    "дядя",
    "юноша",
    "судья",
    "слуга",
    "староста",
    "коллега",
    "сирота",
    "человека",
    "ребёнка",
    "ребенка",
    "часа",
    "года",
    "дня",
    "месяца",
    "раза",
    "века",
    "рубля",
    "доллара",
    "процента",
    "балла",
    "градуса",
    "метра",
    "километра",
    "литра",
    "килограмма",
    "грамма",
    "этажа",
    "номера",
    "пункта",
    "раунда",
    "гола",
    "матча",
    "сезона",
    "урока",
    "класса",
    "курса",
    "тома",
    "брата",
    "сына",
    "друга",
    "мужа",
    "отца",
    "деда",
    "внука",
    "сотрудника",
    "участника",
    "студента",
    "ученика",
    "игрока",
    "гостя",
    "пользователя",
    "клиента",
    "жителя",
    "пассажира",
    "пациента",
    "работника",
    "солдата",
    "врача",
    "места",
    "окна",
    "слова",
    "дела",
    "письма",
    "яйца",
    "лица",
    "числа",
    "села",
    "утра",
    "вечера",
    "дерева",
    "кофе",
];
/// Words after a number that are not the counted noun.
const FUNC: &[&str] = &[
    "тоже",
    "также",
    "уже",
    "еще",
    "ещё",
    "все",
    "всё",
    "где",
    "мне",
    "тебе",
    "себе",
    "вне",
    "после",
    "около",
    "вместе",
    "только",
    "очень",
    "всего",
    "почти",
    "ровно",
    "именно",
    "сразу",
    "снова",
    "просто",
    "нужно",
    "можно",
    "было",
    "это",
    "его",
    "него",
    "чего",
    "того",
    "кого",
    "этого",
    "более",
    "менее",
    "больше",
    "меньше",
    "лучше",
    "хуже",
    "раньше",
    "позже",
    "позднее",
    "ранее",
    "дальше",
    "ближе",
    "выше",
    "ниже",
    "дороже",
    "дешевле",
    "чаще",
    "реже",
    "или",
    "ли",
    "бы",
    "мы",
    "вы",
    "ты",
    "они",
    "при",
    "ни",
    "и",
    "а",
    "но",
    "да",
    "когда",
    "тогда",
    "всегда",
    "иногда",
    "никогда",
    "сюда",
    "туда",
    "куда",
    "пока",
    "она",
    "оно",
    "была",
    "либо",
    "тысячи",
    "тысяча",
    "тысячу",
    "раза",
    "до",
    "по",
    "из",
    "на",
    "за",
    "под",
    "над",
    "про",
    "через",
];

/// The gender of the noun counted by n (only 1 and 2 have gender forms), from its ending in the form the number asks
/// for (a following adjective's ending counts too).
fn gender_of(noun_w: &str, n: u64, case: usize) -> &'static str {
    let w = noun_w.to_lowercase();
    if MASC_A.contains(&w.as_str()) || FUNC.contains(&w.as_str()) || n % 100 == 11 || n % 100 == 12 {
        return "m";
    }
    let last = n % 10;
    if case == NOM || case == ACC {
        if last == 1 {
            if search(r"(?:ая|яя|[ая]|ую|юю|у|ю)$", &w) {
                return "f";
            }
            if search(r"(?:ое|ее|о|ё|мя|ие|ье|це|ще|ле|ре|не|те|се|ке|фе)$", &w) {
                return "n";
            }
            return "m";
        }
        if last == 2 {
            return if search(r"[ыи]$", &w) { "f" } else { "m" };
        }
        return "m";
    }
    if last != 1 {
        return "m";
    }
    let fem = match case {
        GEN => search(r"(?:[ыи]|ой|ей)$", &w),
        DAT => search(r"(?:[еи]|ой|ей)$", &w),
        INS => search(r"(?:ой|ей|ью)$", &w),
        _ => search(r"(?:[еи]|ой|ей)$", &w) && !search(r"(?:ом|ем)$", &w),
    };
    if fem { "f" } else { "m" }
}

/// Animate masculine nouns whose accusative after 1 is одного (задержали 1 человека).
const ANIM: &[&str] = &[
    "человека",
    "ребёнка",
    "ребенка",
    "брата",
    "сына",
    "друга",
    "мужа",
    "отца",
    "деда",
    "внука",
    "сотрудника",
    "участника",
    "студента",
    "ученика",
    "игрока",
    "гостя",
    "пользователя",
    "клиента",
    "жителя",
    "пассажира",
    "пациента",
    "работника",
    "солдата",
    "врача",
];
/// A label before the number (глава 2 книги, п. 1 статьи): the number is a name, not a count.
static LABEL_RX: LazyLock<String> = LazyLock::new(|| {
    format!(
        r"(?i)(?:^|[^\w])(?:глав[аеуы]|стать[яиюе]|пункт[ауе]?|част[ьи]|раздел[ауе]?|том[ау]?|номер[ау]?|параграф[ау]?|приложени[еяю]|страниц[аеуы]|таблиц[аеуы]|рисун(?:ок|ка|ке)|вариант[ау]?|этап[ау]?|уров(?:ень|ня|не)|урок[ау]?|задани[еяю]|задач[аеиу]|вопрос[ау]?|шаг[ау]?|сери[яию]|сезон[ау]?|эпизод[ау]?|верси[яию]|[а-яё]{{1,4}}\.|№){SP}*$"
    )
});

fn ru_gender(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}({NUM})(?:,(\d{{1,6}}))?{RB}(?:{SP}?(г(?![.\w])|г\.(?=\s|$)|шт\.?)(?![\w]))?",
        *PREP_RX
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, whole, frac, unit) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let n = to_int(whole);
        let rest = &t[end(m)..];
        if !prep.is_empty() && !["в", "во", "на", "за", "про", "через"].contains(&prep.to_lowercase().as_str())
        {
            return None;
        }
        let hd = head(prep);
        if !unit.is_empty() {
            if unit == "г" && (1000..=2100).contains(&n) && frac.is_empty()
                || unit == "г." && frac.is_empty() && n >= 1000
            {
                return None; // a year
            }
            let key = if unit.starts_with('г') { unit.trim_end_matches('.') } else { unit };
            let name = find(UNIT_TOK, key).unwrap();
            if !frac.is_empty() {
                return Some(format!("{hd}{} {}{}", decimal(n, frac, NOM), noun(name).1[GEN], drop_dot(unit, rest)));
            }
            return Some(format!(
                "{hd}{} {}{}",
                card(n, NOM, noun(name).0),
                noun_form(name, n, NOM),
                drop_dot(unit, rest)
            ));
        }
        if !frac.is_empty() || !(n % 10 == 1 || n % 10 == 2) || n % 100 == 11 || n % 100 == 12 {
            return None;
        }
        if search(&LABEL_RX, &t[..start(m)]) {
            return None; // глава 2 книги: a label, not a count
        }
        let nm = caps(&format!(r"^{SP}+([а-яё]+)(?:{SP}+([а-яё]+))?"), rest)?;
        let mut noun_w = g(&nm, 1);
        if super::shared::is_op_word("ru", noun_w) {
            return None; // 4 плюс 71 равно 75: an equation, not a count
        }
        if !g(&nm, 2).is_empty() && search(r"(?:ые|ие|ых|их)$", noun_w) {
            noun_w = g(&nm, 2);
        }
        if noun_w.chars().count() < 3 {
            return None;
        }
        if n % 10 == 1 && ANIM.contains(&noun_w) {
            let words_n = card(n, NOM, "m");
            return Some(format!("{hd}{}одного", cut_chars(&words_n, 4)));
        }
        if !prep.is_empty() && (search(r"е$", noun_w) || n % 10 == 1 && search(r"[ая]$", noun_w)) {
            return None;
        }
        let gnd = gender_of(noun_w, n, NOM);
        if gnd == "m" {
            return None;
        }
        let acc = n % 10 == 1 && gnd == "f" && search(r"[ую]$", noun_w);
        Some(format!("{hd}{}", card(n, if acc { ACC } else { NOM }, gnd)))
    })
}

/// `s` without its last `k` characters.
fn cut_chars(s: &str, k: usize) -> &str {
    let end = s.char_indices().rev().nth(k - 1).map_or(0, |(i, _)| i);
    &s[..end]
}

/// A preposition that takes the accusative right before the number (на тысячу).
static ACC_BEFORE: LazyLock<String> =
    LazyLock::new(|| format!("{}{SP}+$", prep_rx(&["на", "в", "во", "за", "про", "через", "под"])));

fn ru_thousand(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}(1[ \x{{A0}}]?\d{{3}}){RB}(?:({SP}?)(\S+))?");
    let months = MONTHS.join("|");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (sp, tok) = (g(m, 2), g(m, 3));
        if tok.is_empty() || search(&format!(r"^(?:г\.?|гг\.|год[а-я]*|{months})(?![\w])"), tok) {
            return None;
        }
        if !search(r"^[₽$€%°a-zа-яё]", tok) {
            return None;
        }
        let low = to_int(g(m, 1)) % 1000;
        let th = if search(&ACC_BEFORE, &t[..start(m)]) { "тысячу" } else { "тысяча" };
        if low != 0 {
            return Some(format!("{th} {low}{sp}{tok}"));
        }
        if plain_word(tok) {
            return Some(format!("{th}{sp}{tok}"));
        }
        let gw = words(&format!("5 {tok}"), "ru");
        if !gw.starts_with("пять ") || gw == format!("пять {tok}") {
            return None;
        }
        let tail: String = gw.chars().skip(5).collect();
        Some(format!("{th} {tail}"))
    })
}

fn ru_address(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}(?<![\w\-.])(д\.|кв\.|корп\.)(?={SP}?\d)");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        Some(
            match g(m, 1) {
                "д." => "дом",
                "кв." => "квартира",
                _ => "корпус",
            }
            .to_string(),
        )
    })
}

// ============================================================================== money and big numbers (Nov 16 b)

const MONEY_CUR: &str = r"₽|руб\.?|RUB|\$|USD|€|EUR|£|GBP|грн\.?|UAH|₴";
const MONEY_SIGN: &str = r"[€$£¥₽₴]";

fn ru_money_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&format!(
            r"(?<=\d)[ \xa0]?({MONEY_CUR})[ \xa0]?[-–~][ \xa0]?(\d[\d \xa0]*(?:,\d{{1,2}})?)[ \xa0]?\1(?![\w])"
        )),
        &t,
        |m| Some(format!("–{} {}", g(m, 2), g(m, 1))),
    );
    let t = c.sub_tpl(&rx(r"(?<=\d) ?~ ?(?=\d)"), &t, "–");
    c.sub_tpl(&rx(&format!(r"(?<![\w.,])({MONEY_SIGN}\d+(?:,\d{{1,2}})?) ?~ ?(?={MONEY_SIGN}?\d)")), &t, r"\1-")
}

/// 12345678 -> "12 345 678".
fn group3(n: u64) -> String {
    let digits = n.to_string();
    let mut out = String::new();
    for (i, ch) in digits.chars().enumerate() {
        if i > 0 && (digits.len() - i).is_multiple_of(3) {
            out.push(' ');
        }
        out.push(ch);
    }
    out
}

fn ru_trillion(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}(?<![\w\-–—.,/:+])([€$£₽] ?)?(\d{{1,3}}(?:[ \xa0]\d{{3}}){{4}}|[1-9]\d{{0,2}}0{{12}}){RB}(?![ \xa0]\d)(?:{SP}?({MONEY_CUR})(?![\w]))?"
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (sign, num) = (py_strip(g(m, 1)), g(m, 2));
        if !sign.is_empty() && !g(m, 3).is_empty() {
            return None;
        }
        let tok = if g(m, 3).is_empty() { sign } else { g(m, 3) };
        let n = to_int(num);
        if !(1_000_000_000_000..1_000_000_000_000_000).contains(&n) {
            return None;
        }
        let rest = n % 1_000_000_000_000;
        if tok.is_empty() {
            return Some(card(n, NOM, "m"));
        }
        let out = if rest > 0 {
            let tail =
                if sign.is_empty() { format!("{} {tok}", group3(rest)) } else { format!("{sign}{}", group3(rest)) };
            format!("{} {}", card(n - rest, NOM, "m"), words(&tail, "ru"))
        } else {
            let gw = words(&format!("5 {tok}"), "ru");
            let tail = gw.strip_prefix("пять ")?;
            if tail == tok {
                return None;
            }
            format!("{} {tail}", card(n, NOM, "m"))
        };
        if search(r"\d", &out) {
            return None;
        }
        Some(format!("{out}{}", drop_dot(tok, &t[end(m)..])))
    })
}

fn ru_grouped_decimal(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"{SKIP}{LB}(\d{{1,3}}(?:[ \xa0]\d{{3}})+),(\d+)(?![\d])")), &t, |m| {
        if skipped(m) {
            return None;
        }
        Some(format!("{},{}", g(m, 1).replace([' ', '\u{a0}'], ""), g(m, 2)))
    })
}

/// A slash after an amount: the denominators the grammar leaves unread.
const PER_UNIT: &[(&str, &str)] = &[
    ("месяц", "в месяц"),
    ("неделю", "в неделю"),
    ("неделя", "в неделю"),
    ("ночь", "за ночь"),
    ("человека", "на человека"),
    ("чел.", "на человека"),
    ("упак.", "за упаковку"),
    ("упак", "за упаковку"),
    ("пачку", "за пачку"),
    ("кв. м", "за квадратный метр"),
    ("сотку", "за сотку"),
    ("год", "в год"),
    ("день", "в день"),
    ("час", "в час"),
    ("сутки", "в сутки"),
    ("кг", "за килограмм"),
    ("шт.", "за штуку"),
];

/// `|`-joined escaped keys, longest first (ties in table order).
fn alternation(keys: &[&str]) -> String {
    let mut ks: Vec<&str> = keys.to_vec();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    ks.iter().map(|k| super::super::re_escape(k)).collect::<Vec<_>>().join("|")
}

fn ru_per_unit(t: String, c: &mut Ctx) -> String {
    let dens = alternation(&PER_UNIT.iter().map(|kv| kv.0).collect::<Vec<_>>());
    let t = c.sub(
        &rx(&format!(
            r"{SKIP}(?<![\w.,])({MONEY_SIGN})(\d{{1,3}}(?:[ \x{{A0}}]\d{{3}})+|\d+)(,\d{{1,2}})?/(?=[^\W\d_])"
        )),
        &t,
        |m| if skipped(m) { None } else { Some(format!("{}{} {}/", g(m, 2), g(m, 3), g(m, 1))) },
    );
    let s: &str = &t;
    c.sub(&rx(&format!(r"{SKIP}(?<=\d)({SP}?(?:{MONEY_CUR}))/({dens})(?![\w])")), &t, |m| {
        if skipped(m) {
            return None;
        }
        let den = g(m, 2);
        let plain = words(&format!("5 {}/{den}", py_strip(g(m, 1))), "ru");
        if plain.starts_with("пять ") && !plain.contains('/') {
            return None;
        }
        let per = PER_UNIT.iter().find(|kv| kv.0 == den)?.1;
        Some(format!("{} {per}{}", g(m, 1), drop_dot(den, &s[end(m)..])))
    })
}

fn ru_abbr_dot(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}{LB}((?:\d{{1,3}}(?:[ \x{{A0}}]\d{{3}})+|\d+)(?:,\d{{1,2}})?(?:{SP}?(?:тыс\.|млн\.?|млрд\.?))?{SP}?(?:руб|коп))\."
    );
    let s: &str = &t;
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let rest = &s[end(m)..];
        if search(r"^[,;:!?)]", rest) {
            return Some(g(m, 1).to_string());
        }
        if !py_strip(rest).is_empty() && !drop_dot(".", rest).is_empty() {
            let out = words(g(m, 1), "ru");
            return if search(r"\d", &out) { None } else { Some(format!("{out}.")) };
        }
        None
    })
}
