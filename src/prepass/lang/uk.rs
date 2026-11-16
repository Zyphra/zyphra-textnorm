//! 'uk' rules: the port of the workbench's `langrules/uk.py` (ids `uk.*`).
//!
//! The grammar reads every number in the nominative (masculine for 1 and 2) and has no oblique case at all, so these
//! rules write the words themselves where a preposition, the noun or the date asks for another form: a small
//! declension generator for cardinals and ordinals (all cases, three genders) and for the nouns the rules write after a
//! number (units, currencies, тисяча, мільйон…). Ukrainian clock time is a feminine ordinal (о чотирнадцятій тридцять).

use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, search};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::py_strip;

pub(super) const RULES: &[LangRule] = &[
    ("uk.city", uk_city),
    ("uk.date", uk_date),
    ("uk.year", uk_year),
    ("uk.roman", uk_roman),
    ("uk.time", uk_time),
    ("uk.hour", uk_hour),
    ("uk.half", uk_half),
    ("uk.ordinal", uk_ordinal),
    ("uk.ordinal-range", uk_ordinal_range),
    ("uk.range", uk_range),
    ("uk.case", uk_case),
    ("uk.count", uk_count),
    ("uk.thousand", uk_thousand),
];

// ------------------------------------------------------------------------------------------------- morphology
// cases: 0 nom, 1 gen, 2 dat, 3 acc, 4 ins, 5 loc (acc of a number = nom: inanimate)
const NOM: usize = 0;
const GEN: usize = 1;
const DAT: usize = 2;
const ACC: usize = 3;
const INS: usize = 4;
const LOC: usize = 5;
const NONE: usize = 99;

fn one(gender: &str) -> [&'static str; 6] {
    match gender {
        "f" => ["одна", "однієї", "одній", "одну", "однією", "одній"],
        "n" => ["одне", "одного", "одному", "одне", "одним", "одному"],
        _ => ["один", "одного", "одному", "один", "одним", "одному"],
    }
}

const ZERO: [&str; 6] = ["нуль", "нуля", "нулю", "нуль", "нулем", "нулі"];

/// A noun the rules write after a number: gender, singular forms, plural forms (six cases each).
type Noun = (&'static str, [&'static str; 6], [&'static str; 6]);

const SCALES: [(u64, &str); 4] =
    [(1_000_000_000_000, "трильйон"), (1_000_000_000, "мільярд"), (1_000_000, "мільйон"), (1000, "тисяча")];

/// Index into `card_forms`' five forms (acc = nom).
fn card_case(case: usize) -> usize {
    [0, 1, 2, 0, 3, 4][case]
}

/// 1..999 in `case`; `gender` picks один/одна/одне and два/дві.
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
        out.push("дві");
    } else if u != 0 {
        out.push(card_forms(u)[card_case(case)]);
    }
    out
}

/// (0 singular / 1 plural, case) of the noun counted by `n` when the number stands in `case` (2–4 take the nominative
/// plural: дві гривні).
fn agree(n: u64, case: usize) -> (usize, usize) {
    if n % 10 == 1 && n % 100 != 11 {
        return (0, case);
    }
    if case == NOM || case == ACC {
        return if (2..=4).contains(&(n % 10)) && !(12..=14).contains(&(n % 100)) { (1, case) } else { (1, GEN) };
    }
    (1, case)
}

/// The noun `name` counted by the integer `n` in `case`; after a round thousand or more it is always the genitive
/// plural (двом тисячам гривень).
fn noun_form(name: &str, n: u64, case: usize) -> &'static str {
    let (_, sg, pl) = noun(name);
    if n >= 1000 && n.is_multiple_of(1000) {
        return pl[GEN];
    }
    let (num, c) = agree(n, case);
    if num == 0 { sg[c] } else { pl[c] }
}

/// The cardinal `n` in `case`; a leading 1 000 is said тисяча (not одна тисяча).
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
        if !(k == 1 && name == "тисяча" && n / div == 1) {
            out.extend(group_words(k, case, noun(name).0));
        }
        out.push(noun_form(name, k, case));
    }
    if !n.is_multiple_of(1000) {
        out.extend(group_words(n % 1000, case, gender));
    }
    out.join(" ")
}

/// The genitive stems fused into a round ordinal (двохтисячний).
fn fused_part(k: u64) -> &'static str {
    match k {
        1 => "одно",
        100 => "сто",
        90 => "дев'яносто",
        _ => card_forms(k)[1],
    }
}

/// Endings by gender (m f n pl) and case: hard stems (перший) and the soft третій.
fn hard(gender: &str) -> [&'static str; 6] {
    match gender {
        "f" => ["а", "ої", "ій", "у", "ою", "ій"],
        "n" => ["е", "ого", "ому", "е", "им", "ому"],
        "pl" => ["і", "их", "им", "і", "ими", "их"],
        _ => ["ий", "ого", "ому", "ий", "им", "ому"],
    }
}

fn soft(gender: &str) -> [&'static str; 6] {
    match gender {
        "f" => ["я", "ьої", "ій", "ю", "ьою", "ій"],
        "n" => ["є", "ього", "ьому", "є", "ім", "ьому"],
        "pl" => ["і", "іх", "ім", "і", "іми", "іх"],
        _ => ["ій", "ього", "ьому", "ій", "ім", "ьому"],
    }
}

/// `s` without its last `k` characters.
fn cut_chars(s: &str, k: usize) -> &str {
    let end = s.char_indices().rev().nth(k - 1).map_or(0, |(i, _)| i);
    &s[..end]
}

fn inflect_ord(word: &str, case: usize, gender: &str) -> String {
    if word.ends_with("третій") {
        return format!("{}{}", cut_chars(word, 2), soft(gender)[case]);
    }
    format!("{}{}", cut_chars(word, 2), hard(gender)[case])
}

/// The genitive stem of 1..999 written as one word before -тисячний/-мільйонний.
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

/// The ordinal `n` in `case` and `gender` (m f n pl): дві тисячі двадцять четвертого.
fn ordinal(n: u64, case: usize, gender: &str) -> String {
    if n == 0 {
        return inflect_ord("нульовий", case, gender);
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
                    "тисяча" => "тисячний",
                    "мільйон" => "мільйонний",
                    "мільярд" => "мільярдний",
                    _ => "трильйонний",
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

const DENOM: [&str; 6] = ["десят", "сот", "тисячн", "десятитисячн", "стотисячн", "мільйонн"];

/// i,frac in `case`: дві цілих п'ять десятих, двох цілих п'яти десятих.
fn decimal(i: u64, frac: &str, case: usize) -> String {
    let f = py_int(frac) as u64;
    let (_, sg, pl) = noun("ціла");
    let whole = format!("{} {}", card(i, case, "f"), if i % 10 == 1 && i % 100 != 11 { sg[case] } else { pl[case] });
    let end = if f % 10 == 1 && f % 100 != 11 {
        hard("f")[case]
    } else if case == NOM || case == ACC {
        "их"
    } else {
        hard("pl")[case]
    };
    format!("{} {} {}{}", whole, card(f, case, "f"), DENOM[frac.chars().count() - 1], end)
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
const LB: &str = r"(?<![\w\-–—.,/:+'])";
const RB: &str = r"(?![\d]|[.,:/\-]\d|[^\W\d_]|')";
const SP: &str = r"[ \x{A0}]";
const SKIP: &str = "\u{e000}[^\u{e001}]*\u{e001}|";

const PREP_CASE: &[(&str, usize)] = &[
    ("до", GEN),
    ("від", GEN),
    ("близько", GEN),
    ("біля", GEN),
    ("після", GEN),
    ("без", GEN),
    ("для", GEN),
    ("крім", GEN),
    ("замість", GEN),
    ("серед", GEN),
    ("протягом", GEN),
    ("впродовж", GEN),
    ("навколо", GEN),
    ("більше", GEN),
    ("менше", GEN),
    ("старше", GEN),
    ("молодше", GEN),
    ("дорожче", GEN),
    ("дешевше", GEN),
    ("вище", GEN),
    ("нижче", GEN),
    ("понад", NONE),
    ("завдяки", DAT),
    ("всупереч", DAT),
    ("назустріч", DAT),
    ("з", NONE),
    ("із", NONE),
    ("зі", NONE),
    ("зо", NONE),
    ("в", NONE),
    ("у", NONE),
    ("на", NONE),
    ("о", NONE),
    ("об", NONE),
    ("при", NONE),
    ("по", NONE),
    ("за", NONE),
    ("під", NONE),
    ("над", NONE),
    ("перед", NONE),
    ("між", NONE),
];

fn lookup(table: &[(&str, usize)], key: &str) -> Option<usize> {
    table.iter().find(|(k, _)| *k == key).map(|&(_, v)| v)
}

fn find<'a>(table: &[(&str, &'a str)], key: &str) -> Option<&'a str> {
    table.iter().find(|(k, _)| *k == key).map(|&(_, v)| v)
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
fn noun_case(prep: &str, noun_w: &str, n: u64) -> usize {
    let p = prep.to_lowercase();
    let c = lookup(PREP_CASE, &p).unwrap();
    if c != NONE || p == "понад" {
        return c;
    }
    let one = n % 10 == 1 && n % 100 != 11;
    if ["з", "із", "зі", "зо"].contains(&p.as_str()) {
        if search(r"(?:ами|ями|ьми|ми)$", noun_w) || one && search(r"(?:ом|ем|єм|ою|ею|єю)$", noun_w)
        {
            return INS;
        }
        return GEN;
    }
    if ["в", "у", "на", "о", "об", "при", "по"].contains(&p.as_str()) {
        return if search(r"[ая]х$", noun_w) { LOC } else { NONE };
    }
    if search(r"(?:ами|ями|ьми)$", noun_w) { INS } else { NONE }
}

/// A word the grammar passes through after a number (друзями, людей.), not a unit or an abbreviation it reads.
fn plain_word(tok: &str) -> bool {
    let w = sub(r#"[.,;:!?)»\"]+$"#, tok, |_| String::new());
    w.is_empty() || search(r"^[^\W\d_]+$", &w) && words(&format!("5 {w}"), "uk") == format!("п'ять {w}")
}

fn counted_noun(rest: &str) -> String {
    let pat = format!(r"^{SP}+(?:(?:до|по){SP}+\d+{SP}+)?([^\W\d_]+(?:'[^\W\d_]+)?)(?:{SP}+([^\W\d_]+))?");
    let Some(m) = caps(&pat, rest) else { return String::new() };
    if !g(&m, 2).is_empty() && search(r"(?:их|им|ими)$", g(&m, 1)) {
        return g(&m, 2).to_string();
    }
    g(&m, 1).to_string()
}

/// The preposition (if any) before the words a rule wrote, with з → зі before a sibilant cluster (зі ста).
fn lead(prep: &str, spoken: &str) -> String {
    if prep.is_empty() {
        return spoken.to_string();
    }
    if prep.to_lowercase() == "з" && search(r"^[зсцчшщ][бвгґджзклмнпрстфхцчшщ]", spoken) {
        return format!("{prep}і {spoken}");
    }
    format!("{prep} {spoken}")
}

fn drop_dot(tok: &str, rest: &str) -> &'static str {
    if tok.ends_with('.') && (py_strip(rest).is_empty() || search(r"^[ \t]*\n|^\s+[А-ЯЄІЇҐA-Z]", rest)) {
        "."
    } else {
        ""
    }
}

fn card_forms(k: u64) -> [&'static str; 5] {
    match k {
        2 => ["два", "двох", "двом", "двома", "двох"],
        3 => ["три", "трьох", "трьом", "трьома", "трьох"],
        4 => ["чотири", "чотирьох", "чотирьом", "чотирма", "чотирьох"],
        5 => ["п'ять", "п'яти", "п'яти", "п'ятьма", "п'яти"],
        6 => ["шість", "шести", "шести", "шістьма", "шести"],
        7 => ["сім", "семи", "семи", "сьома", "семи"],
        8 => ["вісім", "восьми", "восьми", "вісьма", "восьми"],
        9 => ["дев'ять", "дев'яти", "дев'яти", "дев'ятьма", "дев'яти"],
        10 => ["десять", "десяти", "десяти", "десятьма", "десяти"],
        11 => ["одинадцять", "одинадцяти", "одинадцяти", "одинадцятьма", "одинадцяти"],
        12 => ["дванадцять", "дванадцяти", "дванадцяти", "дванадцятьма", "дванадцяти"],
        13 => ["тринадцять", "тринадцяти", "тринадцяти", "тринадцятьма", "тринадцяти"],
        14 => ["чотирнадцять", "чотирнадцяти", "чотирнадцяти", "чотирнадцятьма", "чотирнадцяти"],
        15 => ["п'ятнадцять", "п'ятнадцяти", "п'ятнадцяти", "п'ятнадцятьма", "п'ятнадцяти"],
        16 => ["шістнадцять", "шістнадцяти", "шістнадцяти", "шістнадцятьма", "шістнадцяти"],
        17 => ["сімнадцять", "сімнадцяти", "сімнадцяти", "сімнадцятьма", "сімнадцяти"],
        18 => ["вісімнадцять", "вісімнадцяти", "вісімнадцяти", "вісімнадцятьма", "вісімнадцяти"],
        19 => ["дев'ятнадцять", "дев'ятнадцяти", "дев'ятнадцяти", "дев'ятнадцятьма", "дев'ятнадцяти"],
        20 => ["двадцять", "двадцяти", "двадцяти", "двадцятьма", "двадцяти"],
        30 => ["тридцять", "тридцяти", "тридцяти", "тридцятьма", "тридцяти"],
        40 => ["сорок", "сорока", "сорока", "сорока", "сорока"],
        50 => ["п'ятдесят", "п'ятдесяти", "п'ятдесяти", "п'ятдесятьма", "п'ятдесяти"],
        60 => ["шістдесят", "шістдесяти", "шістдесяти", "шістдесятьма", "шістдесяти"],
        70 => ["сімдесят", "сімдесяти", "сімдесяти", "сімдесятьма", "сімдесяти"],
        80 => ["вісімдесят", "вісімдесяти", "вісімдесяти", "вісімдесятьма", "вісімдесяти"],
        90 => ["дев'яносто", "дев'яноста", "дев'яноста", "дев'яноста", "дев'яноста"],
        100 => ["сто", "ста", "ста", "ста", "ста"],
        200 => ["двісті", "двохсот", "двомстам", "двомастами", "двохстах"],
        300 => ["триста", "трьохсот", "трьомстам", "трьомастами", "трьохстах"],
        400 => ["чотириста", "чотирьохсот", "чотирьомстам", "чотирмастами", "чотирьохстах"],
        500 => ["п'ятсот", "п'ятисот", "п'ятистам", "п'ятьмастами", "п'ятистах"],
        600 => ["шістсот", "шестисот", "шестистам", "шістьмастами", "шестистах"],
        700 => ["сімсот", "семисот", "семистам", "сьомастами", "семистах"],
        800 => ["вісімсот", "восьмисот", "восьмистам", "вісьмастами", "восьмистах"],
        _ => ["дев'ятсот", "дев'ятисот", "дев'ятистам", "дев'ятьмастами", "дев'ятистах"],
    }
}

fn noun(name: &str) -> Noun {
    match name {
        "тисяча" => (
            "f",
            ["тисяча", "тисячі", "тисячі", "тисячу", "тисячею", "тисячі"],
            ["тисячі", "тисяч", "тисячам", "тисячі", "тисячами", "тисячах"],
        ),
        "мільйон" => (
            "m",
            ["мільйон", "мільйона", "мільйону", "мільйон", "мільйоном", "мільйоні"],
            ["мільйони", "мільйонів", "мільйонам", "мільйони", "мільйонами", "мільйонах"],
        ),
        "мільярд" => (
            "m",
            ["мільярд", "мільярда", "мільярду", "мільярд", "мільярдом", "мільярді"],
            ["мільярди", "мільярдів", "мільярдам", "мільярди", "мільярдами", "мільярдах"],
        ),
        "трильйон" => (
            "m",
            ["трильйон", "трильйона", "трильйону", "трильйон", "трильйоном", "трильйоні"],
            ["трильйони", "трильйонів", "трильйонам", "трильйони", "трильйонами", "трильйонах"],
        ),
        "гривня" => (
            "f",
            ["гривня", "гривні", "гривні", "гривню", "гривнею", "гривні"],
            ["гривні", "гривень", "гривням", "гривні", "гривнями", "гривнях"],
        ),
        "копійка" => (
            "f",
            ["копійка", "копійки", "копійці", "копійку", "копійкою", "копійці"],
            ["копійки", "копійок", "копійкам", "копійки", "копійками", "копійках"],
        ),
        "долар" => (
            "m",
            ["долар", "долара", "долару", "долар", "доларом", "доларі"],
            ["долари", "доларів", "доларам", "долари", "доларами", "доларах"],
        ),
        "цент" => (
            "m",
            ["цент", "цента", "центу", "цент", "центом", "центі"],
            ["центи", "центів", "центам", "центи", "центами", "центах"],
        ),
        "євро" => {
            ("n", ["євро", "євро", "євро", "євро", "євро", "євро"], ["євро", "євро", "євро", "євро", "євро", "євро"])
        }
        "відсоток" => (
            "m",
            ["відсоток", "відсотка", "відсотку", "відсоток", "відсотком", "відсотку"],
            ["відсотки", "відсотків", "відсоткам", "відсотки", "відсотками", "відсотках"],
        ),
        "градус" => (
            "m",
            ["градус", "градуса", "градусу", "градус", "градусом", "градусі"],
            ["градуси", "градусів", "градусам", "градуси", "градусами", "градусах"],
        ),
        "кілометр" => (
            "m",
            ["кілометр", "кілометра", "кілометру", "кілометр", "кілометром", "кілометрі"],
            ["кілометри", "кілометрів", "кілометрам", "кілометри", "кілометрами", "кілометрах"],
        ),
        "метр" => (
            "m",
            ["метр", "метра", "метру", "метр", "метром", "метрі"],
            ["метри", "метрів", "метрам", "метри", "метрами", "метрах"],
        ),
        "сантиметр" => (
            "m",
            ["сантиметр", "сантиметра", "сантиметру", "сантиметр", "сантиметром", "сантиметрі"],
            ["сантиметри", "сантиметрів", "сантиметрам", "сантиметри", "сантиметрами", "сантиметрах"],
        ),
        "міліметр" => (
            "m",
            ["міліметр", "міліметра", "міліметру", "міліметр", "міліметром", "міліметрі"],
            ["міліметри", "міліметрів", "міліметрам", "міліметри", "міліметрами", "міліметрах"],
        ),
        "кілограм" => (
            "m",
            ["кілограм", "кілограма", "кілограму", "кілограм", "кілограмом", "кілограмі"],
            ["кілограми", "кілограмів", "кілограмам", "кілограми", "кілограмами", "кілограмах"],
        ),
        "грам" => (
            "m",
            ["грам", "грама", "граму", "грам", "грамом", "грамі"],
            ["грами", "грамів", "грамам", "грами", "грамами", "грамах"],
        ),
        "літр" => (
            "m",
            ["літр", "літра", "літру", "літр", "літром", "літрі"],
            ["літри", "літрів", "літрам", "літри", "літрами", "літрах"],
        ),
        "мілілітр" => (
            "m",
            ["мілілітр", "мілілітра", "мілілітру", "мілілітр", "мілілітром", "мілілітрі"],
            ["мілілітри", "мілілітрів", "мілілітрам", "мілілітри", "мілілітрами", "мілілітрах"],
        ),
        "гектар" => (
            "m",
            ["гектар", "гектара", "гектару", "гектар", "гектаром", "гектарі"],
            ["гектари", "гектарів", "гектарам", "гектари", "гектарами", "гектарах"],
        ),
        "тонна" => (
            "f",
            ["тонна", "тонни", "тонні", "тонну", "тонною", "тонні"],
            ["тонни", "тонн", "тоннам", "тонни", "тоннами", "тоннах"],
        ),
        "година" => (
            "f",
            ["година", "години", "годині", "годину", "годиною", "годині"],
            ["години", "годин", "годинам", "години", "годинами", "годинах"],
        ),
        "хвилина" => (
            "f",
            ["хвилина", "хвилини", "хвилині", "хвилину", "хвилиною", "хвилині"],
            ["хвилини", "хвилин", "хвилинам", "хвилини", "хвилинами", "хвилинах"],
        ),
        "секунда" => (
            "f",
            ["секунда", "секунди", "секунді", "секунду", "секундою", "секунді"],
            ["секунди", "секунд", "секундам", "секунди", "секундами", "секундах"],
        ),
        "штука" => (
            "f",
            ["штука", "штуки", "штуці", "штуку", "штукою", "штуці"],
            ["штуки", "штук", "штукам", "штуки", "штуками", "штуках"],
        ),
        _ => (
            "f",
            ["ціла", "цілої", "цілій", "цілу", "цілою", "цілій"],
            ["цілих", "цілих", "цілим", "цілих", "цілими", "цілих"],
        ),
    }
}

fn ord_stem(k: u64) -> &'static str {
    match k {
        1 => "перший",
        2 => "другий",
        3 => "третій",
        4 => "четвертий",
        5 => "п'ятий",
        6 => "шостий",
        7 => "сьомий",
        8 => "восьмий",
        9 => "дев'ятий",
        10 => "десятий",
        11 => "одинадцятий",
        12 => "дванадцятий",
        13 => "тринадцятий",
        14 => "чотирнадцятий",
        15 => "п'ятнадцятий",
        16 => "шістнадцятий",
        17 => "сімнадцятий",
        18 => "вісімнадцятий",
        19 => "дев'ятнадцятий",
        20 => "двадцятий",
        30 => "тридцятий",
        40 => "сороковий",
        50 => "п'ятдесятий",
        60 => "шістдесятий",
        70 => "сімдесятий",
        80 => "вісімдесятий",
        90 => "дев'яностий",
        100 => "сотий",
        200 => "двохсотий",
        300 => "трьохсотий",
        400 => "чотирьохсотий",
        500 => "п'ятисотий",
        600 => "шестисотий",
        700 => "семисотий",
        800 => "восьмисотий",
        _ => "дев'ятисотий",
    }
}

// ------------------------------------------------------------------------------------------------- rules

const CITY: &[(&str, &str)] = &[
    ("в", "місті"),
    ("у", "місті"),
    ("на", "місті"),
    ("о", "місті"),
    ("при", "місті"),
    ("по", "місту"),
    ("з", "міста"),
    ("із", "міста"),
    ("зі", "міста"),
    ("від", "міста"),
    ("до", "міста"),
    ("біля", "міста"),
    ("для", "міста"),
    ("близько", "міста"),
    ("навколо", "міста"),
    ("поблизу", "міста"),
    ("за", "містом"),
    ("під", "містом"),
    ("над", "містом"),
    ("перед", "містом"),
    ("між", "містом"),
];

fn uk_city(t: String, c: &mut Ctx) -> String {
    let pat =
        format!(r"{SKIP}(?<![\w\-.'])(?:([А-Яа-яЄєІіЇїҐґ']+|\d+)[ \x{{A0}}]+)?м\.[ \x{{A0}}]?(?=[А-ЯЄІЇҐ][а-яєіїґ'])");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let word = g(m, 1);
        if word.is_empty() {
            if search(r"\d[ \x{A0}]*$", &t[..start(m)]) {
                return None;
            }
            return Some("місто ".into());
        }
        if search(r"^\d", word) {
            return None;
        }
        let city = find(CITY, &word.to_lowercase()).unwrap_or("місто");
        Some(format!("{word} {city} "))
    })
}

const MONTHS: [&str; 12] = [
    "січня",
    "лютого",
    "березня",
    "квітня",
    "травня",
    "червня",
    "липня",
    "серпня",
    "вересня",
    "жовтня",
    "листопада",
    "грудня",
];
const NOM_BEFORE: &[&str] = &[
    "сьогодні",
    "завтра",
    "вчора",
    "післязавтра",
    "позавчора",
    "настало",
    "настане",
    "наступило",
    "це",
    "дата",
    "число",
];
const DATE_PREP: &[(&str, usize)] = &[
    ("на", NOM),
    ("в", NOM),
    ("у", NOM),
    ("про", NOM),
    ("через", NOM),
    ("за", NOM),
    ("по", NOM),
    ("з", GEN),
    ("із", GEN),
    ("зі", GEN),
    ("до", GEN),
    ("від", GEN),
    ("після", GEN),
    ("близько", GEN),
    ("для", GEN),
    ("без", GEN),
    ("крім", GEN),
    ("замість", GEN),
    ("напередодні", GEN),
    ("протягом", GEN),
    ("середини", GEN),
    ("початку", GEN),
    ("кінця", GEN),
    ("завдяки", DAT),
];
static DATE_PREP_RX: LazyLock<String> = LazyLock::new(|| prep_rx(&keys(DATE_PREP)));
/// Any preposition right before a bare range (между 5–10 мая).
static BARE_PREP_RX: LazyLock<String> = LazyLock::new(|| {
    let mut ps = keys(PREP_CASE);
    ps.sort();
    format!("(?<![^\\s(«\\\"„“])(?:{}){SP}*$", ps.join("|"))
});

/// The case of the day of a date: from its preposition; with none, genitive after a word (підписано 1 вересня) and
/// nominative at the start of a sentence, after a comma or after сьогодні / це.
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
    format!("{} року", ordinal(y, GEN, "m"))
}

fn uk_date(t: String, c: &mut Ctx) -> String {
    let year_tail = format!(r"(?:{SP}+(\d{{4}})(?:{SP}?(р\.|р(?![\w.])|року(?![\w])))?)?");
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
            format!("з {} по {}", ordinal(a, GEN, "n"), ordinal(b, NOM, "n"))
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
        r"{SKIP}(?:{}{SP}+)?{LB}(?:(\d{{1,2}})([./])(\d{{1,2}})\3(\d{{4}})|(\d{{4}})-(\d{{2}})-(\d{{2}}))(?:{SP}?(р\.|р(?![\w.])|року(?![\w])))?(?![\w]|[.,/\-]\d)",
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

const YEAR_PREP: &[(&str, usize)] = &[
    ("в", LOC),
    ("у", LOC),
    ("о", LOC),
    ("при", LOC),
    ("по", NOM),
    ("на", NOM),
    ("за", NOM),
    ("через", NOM),
    ("про", NOM),
    ("перед", INS),
    ("між", INS),
    ("над", INS),
    ("під", NOM),
    ("з", GEN),
    ("із", GEN),
    ("зі", GEN),
    ("до", GEN),
    ("від", GEN),
    ("після", GEN),
    ("близько", GEN),
    ("для", GEN),
    ("без", GEN),
    ("крім", GEN),
    ("напередодні", GEN),
    ("середини", GEN),
    ("початку", GEN),
    ("кінця", GEN),
    ("протягом", GEN),
    ("завдяки", DAT),
];
static YEAR_PREP_RX: LazyLock<String> = LazyLock::new(|| prep_rx(&keys(YEAR_PREP)));
const YEAR_FORMS: [&str; 6] = ["рік", "року", "року", "рік", "роком", "році"];
const YEARS_FORMS: [&str; 6] = ["роки", "років", "рокам", "роки", "роками", "роках"];

fn year_case(prep: &str, word: &str) -> usize {
    match word {
        "року" => GEN,
        "рік" => NOM,
        "роком" => INS,
        "році" => LOC,
        _ => lookup(YEAR_PREP, &prep.to_lowercase()).unwrap_or(GEN),
    }
}

fn uk_year(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}(\d{{4}})(?:{SP}+(по|до){SP}+(\d{{4}}))?(?:-(?:му|го|й|м))?{SP}?(р\.|р(?![\w.])|рр\.|року|році|роком|рік)(?![\w])",
        *YEAR_PREP_RX
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, sep, b, word) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        let rest = &t[end(m)..];
        if !b.is_empty() {
            let p = prep.to_lowercase();
            if !["з", "із", "від"].contains(&p.as_str()) || !["р.", "р", "рр.", "рік", "року"].contains(&word)
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
        if word == "рр." {
            return None;
        }
        let case = year_case(prep, word);
        let yw = if word == "р." || word == "р" {
            format!("{}{}", YEAR_FORMS[case], drop_dot(word, rest))
        } else {
            word.to_string()
        };
        Some(format!("{} {}", lead(prep, &ordinal(py_int(a) as u64, case, "m")), yw))
    });
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?{LB}(\d{{4}}){SP}?[–—-]{SP}?(\d{{4}}){SP}?(рр\.|роки|років|рокам|роками|роках)(?![\w])",
        *YEAR_PREP_RX
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, b, word) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let case = if word == "рр." {
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

fn roman_digit(ch: char) -> u64 {
    match ch {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        _ => 100,
    }
}

/// The value of a Roman numeral (0 when it is not a well-formed one up to 100).
fn roman_value(s: &str) -> u64 {
    let cs: Vec<char> = s.chars().collect();
    let mut total: i64 = 0;
    for (i, &ch) in cs.iter().enumerate() {
        let v = roman_digit(ch) as i64;
        total += if i + 1 < cs.len() && roman_digit(cs[i + 1]) as i64 > v { -v } else { v };
    }
    if (1..=100).any(|v| roman_str(v) == s) { total as u64 } else { 0 }
}

fn roman_str(mut n: u64) -> String {
    let mut out = String::new();
    for (v, r) in [(100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")] {
        while n >= v {
            out.push_str(r);
            n -= v;
        }
    }
    out
}

fn century(base: &str) -> [&'static str; 6] {
    if base == "сторіччя" {
        ["сторіччя", "сторіччя", "сторіччю", "сторіччя", "сторіччям", "сторіччі"]
    } else {
        ["століття", "століття", "століттю", "століття", "століттям", "столітті"]
    }
}

fn uk_roman(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}(?:{}{SP}+)?(?<![\w\-.])([IVXLC]+){SP}?(столітті|століттям|століття|сторіччі|сторіччям|сторіччя|ст\.)(?![\w])",
        *YEAR_PREP_RX
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, num, word) = (g(m, 1), g(m, 2), g(m, 3));
        let n = roman_value(num);
        if n == 0 {
            return None;
        }
        let p = prep.to_lowercase();
        let (case, base) = if word == "столітті" || word == "сторіччі" {
            (LOC, if word == "столітті" { "століття" } else { "сторіччя" })
        } else if word == "століттям" || word == "сторіччям" {
            (INS, if word == "століттям" { "століття" } else { "сторіччя" })
        } else {
            let base = if word == "сторіччя" { "сторіччя" } else { "століття" };
            let mut case = if p.is_empty() { NOM } else { lookup(YEAR_PREP, &p).unwrap_or(GEN) };
            if word != "ст." && case != GEN && case != NOM {
                case = NOM;
            }
            (case, base)
        };
        let out = format!(
            "{}{}",
            lead(prep, &format!("{} {}", ordinal(n, case, "n"), century(base)[case])),
            drop_dot(word, &t[end(m)..])
        );
        if words(&m[0], "uk").trim_end_matches('.') == out.trim_end_matches('.') { None } else { Some(out) }
    })
}

const TIME_PREP: &[(&str, usize)] = &[
    ("о", LOC),
    ("об", LOC),
    ("на", ACC),
    ("з", GEN),
    ("із", GEN),
    ("зі", GEN),
    ("від", GEN),
    ("до", GEN),
    ("після", GEN),
    ("близько", GEN),
    ("між", INS),
    ("перед", INS),
];

/// The clock hour as a feminine ordinal (година): о чотирнадцятій, з дев'ятої.
fn hour_words(h: u64, case: usize) -> String {
    ordinal(h, case, "f")
}

fn uk_time(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{}{SP}+(\d{{1,2}}):(\d{{2}})(?![\d:]|[.,]\d)", prep_rx(&keys(TIME_PREP)));
    let t = c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, h, mi) = (g(m, 1), py_int(g(m, 2)) as u64, py_int(g(m, 3)) as u64);
        if h > 24 || mi > 59 {
            return None;
        }
        let case = lookup(TIME_PREP, &prep.to_lowercase()).unwrap();
        let mut out = hour_words(h, case);
        if mi != 0 {
            out += &format!(" {}{}", if mi < 10 { "нуль " } else { "" }, card(mi, NOM, "f"));
        }
        Some(lead(prep, &out))
    });
    let pat = format!(r"{SKIP}(?<=[Мм]іж )([а-яєіїґ' ]+?{SP}(?:та|і|й)){SP}+(\d{{1,2}}):(\d{{2}})(?![\d:]|[.,]\d)");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (h, mi) = (py_int(g(m, 2)) as u64, py_int(g(m, 3)) as u64);
        if h > 24 || mi > 59 {
            return None;
        }
        let mut out = hour_words(h, INS);
        if mi != 0 {
            out += &format!(" {}{}", if mi < 10 { "нуль " } else { "" }, card(mi, NOM, "f"));
        }
        Some(format!("{} {out}", g(m, 1)))
    })
}

fn uk_hour(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}{}{SP}+(\d{{1,2}}){SP}+до{SP}+(\d{{1,2}}){SP}+(години|год\.|год)(?![\w])",
        prep_rx(&["з", "із", "від"])
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, b, word) = (g(m, 1), py_int(g(m, 2)) as u64, py_int(g(m, 3)) as u64, g(m, 4));
        if a > 24 || b > 24 {
            return None;
        }
        let hw = if word.starts_with("год") { "години" } else { word };
        Some(format!(
            "{} до {} {hw}{}",
            lead(prep, &hour_words(a, GEN)),
            hour_words(b, GEN),
            drop_dot(word, &t[end(m)..])
        ))
    });
    let pat = format!(
        r"{SKIP}{}{SP}+(\d{{1,2}}){SP}+(години|годині)(?![\w])",
        prep_rx(&["о", "об", "до", "після", "з", "із", "від", "близько"])
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, h, word) = (g(m, 1), py_int(g(m, 2)) as u64, g(m, 3));
        let p = prep.to_lowercase();
        if p == "о" || p == "об" {
            if word != "годині" || h > 24 {
                return None;
            }
            return Some(format!("{prep} {} годині", hour_words(h, LOC)));
        }
        if word != "години" || !(2..=24).contains(&h) {
            return None;
        }
        Some(format!("{} години", lead(prep, &hour_words(h, GEN))))
    })
}

fn uk_half(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}(?:{}{SP}+)?{LB}(?:(\d{{1,9}}){SP}+)?1/2(?![\d/])", *PREP_RX);
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, whole) = (g(m, 1), g(m, 2));
        let nm = caps(&format!(r"^{SP}+([а-яєіїґ']+)"), &t[end(m)..])?;
        if !plain_word(g(&nm, 1)) {
            return None; // 1/2 млн: not a noun
        }
        let noun_w = g(&nm, 1);
        let p = prep.to_lowercase();
        let mut case;
        if ["в", "у", "на", "за", "через", "про"].contains(&p.as_str()) {
            case = ACC;
        } else if !prep.is_empty() {
            case = lookup(PREP_CASE, &p).unwrap_or(NONE);
            if case != GEN && case != DAT {
                return None;
            }
        } else {
            case = NOM;
        }
        let w = if !whole.is_empty() {
            let n = py_int(whole) as u64;
            let fem = gender_of(noun_w, 2, NOM) == "f";
            if n == 1 {
                if case != NOM && case != ACC {
                    return None;
                }
                if fem { "півтори" } else { "півтора" }.to_string()
            } else {
                format!("{} з половиною", card(n, case, if fem { "f" } else { "m" }))
            }
        } else {
            let before = &t[..start(m)];
            if case == NOM && !py_strip(before).is_empty() && !search(r"[.!?:;\n—–][ \x{A0}]*$", before) {
                case = ACC;
            }
            ["половина", "половини", "половині", "половину", "половиною", "половині"][case].to_string()
        };
        Some(lead(prep, &w))
    })
}

const ORD_END: &[(&str, (&str, usize))] = &[
    ("а", ("f", NOM)),
    ("я", ("f", NOM)),
    ("е", ("n", NOM)),
    ("є", ("n", NOM)),
    ("і", ("pl", NOM)),
    ("ий", ("m", NOM)),
    ("ій", ("m", NOM)),
    ("у", ("f", ACC)),
    ("ю", ("f", ACC)),
    ("ого", ("m", GEN)),
    ("ього", ("m", GEN)),
    ("ої", ("f", GEN)),
    ("ьої", ("f", GEN)),
    ("ому", ("m", DAT)),
    ("ьому", ("m", DAT)),
    ("ою", ("f", INS)),
    ("ьою", ("f", INS)),
    ("их", ("pl", GEN)),
    ("іх", ("pl", GEN)),
];

fn uk_ordinal(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}(\d{{1,9}})-([бвгджзклмнпрстфхцчшщ])([а-яєіїґ]{{1,4}})(?![\w'\-])");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (n, cons, ending) = (py_int(g(m, 1)) as u64, g(m, 2), g(m, 3));
        let &(_, (gnd, case)) = ORD_END.iter().find(|(k, _)| *k == ending)?;
        let w: Vec<char> = ordinal(n, NOM, "m").chars().collect();
        if w[w.len() - 3].to_string() != cons {
            return None;
        }
        if !words(&m[0], "uk").ends_with(&format!(" {cons}{ending}")) {
            return None; // the grammar reads this ending itself (1-ша, 2000-ні)
        }
        Some(ordinal(n, case, gnd))
    })
}

fn uk_ordinal_range(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}{}{SP}+(\d{{1,3}}){SP}+по{SP}+(\d{{1,3}})(?={SP}+([а-яєіїґ']+)(?![\w']))",
        prep_rx(&["з", "із", "зі"])
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, a, b, noun_w) = (g(m, 1), py_int(g(m, 2)) as u64, py_int(g(m, 3)) as u64, g(m, 4));
        let gnd = if search(r"[бвгґджзклмнпрстфхцчшщй]$", noun_w) {
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

fn uk_range(t: String, c: &mut Ctx) -> String {
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
            return Some(format!("від {a} до {b}{pct}"));
        }
        let p = prep.to_lowercase();
        let case = if ["в", "у", "на", "за", "через", "по", "про"].contains(&p.as_str()) {
            ACC
        } else if lookup(PREP_CASE, &p) == Some(GEN) {
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
        let mut out = format!("{}-{}", card(na, case, gnd), card(nb, case, gnd));
        if !pct.is_empty() {
            out += &format!(" {}", noun_form("відсоток", nb, case));
        }
        Some(lead(prep, &out))
    })
}

const SCALE_TOK: &[(&str, &str)] = &[
    ("тис.", "тисяча"),
    ("тис", "тисяча"),
    ("млн", "мільйон"),
    ("млн.", "мільйон"),
    ("млрд", "мільярд"),
    ("млрд.", "мільярд"),
    ("трлн", "трильйон"),
    ("трлн.", "трильйон"),
];
const UNIT_TOK: &[(&str, &str)] = &[
    ("₴", "гривня"),
    ("грн.", "гривня"),
    ("грн", "гривня"),
    ("$", "долар"),
    ("дол.", "долар"),
    ("€", "євро"),
    ("%", "відсоток"),
    ("°C", "градус"),
    ("°С", "градус"),
    ("°", "градус"),
    ("км", "кілометр"),
    ("м", "метр"),
    ("см", "сантиметр"),
    ("мм", "міліметр"),
    ("кг", "кілограм"),
    ("г", "грам"),
    ("л", "літр"),
    ("мл", "мілілітр"),
    ("т", "тонна"),
    ("га", "гектар"),
    ("год.", "година"),
    ("год", "година"),
    ("хв.", "хвилина"),
    ("хв", "хвилина"),
    ("сек.", "секунда"),
    ("сек", "секунда"),
    ("шт.", "штука"),
    ("шт", "штука"),
    ("коп.", "копійка"),
    ("коп", "копійка"),
];
const MINOR: &[(&str, &str)] = &[("гривня", "копійка"), ("долар", "цент"), ("євро", "цент")];
const SCALE_RX: &str = r"(тис\.?|млн\.?|млрд\.?|трлн\.?)";
const UNIT_RX: &str = r"(₴|грн\.?|\$|дол\.|€|%|°[CС]?|км|мм|мл|см|кг|га|год\.?|хв\.?|сек\.?|шт\.?|коп\.?|м|г|л|т)";

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
    if unit == "°C" || unit == "°С" { format!("{w} Цельсія") } else { w.to_string() }
}

fn sign_word(sign: &str) -> &'static str {
    match py_strip(sign) {
        "" => "",
        "+" | "плюс" => "плюс ",
        _ => "мінус ",
    }
}

fn number_part(sign: &str, whole: &str, frac: &str, case: usize, gender: &str) -> String {
    let out = sign_word(sign);
    if !frac.is_empty() {
        return format!("{out}{}", decimal(to_int(whole), frac, case));
    }
    format!("{out}{}", card(to_int(whole), case, gender))
}

/// The words for [prep] number [scale] [unit] in `case`.
#[allow(clippy::too_many_arguments)]
fn spoken(
    prep: &str,
    sign: &str,
    whole: &str,
    frac: &str,
    scale: &str,
    unit: &str,
    case: usize,
    rest: &str,
    noun_w: &str,
) -> String {
    if !prep.is_empty() {
        return lead(prep, &spoken("", sign, whole, frac, scale, unit, case, rest, noun_w));
    }
    let n = to_int(whole);
    if !scale.is_empty() {
        let name = find(SCALE_TOK, scale).unwrap();
        let mut out;
        if n == 1 && frac.is_empty() && sign.is_empty() && name == "тисяча" {
            out = noun_form(name, 1, case).to_string(); // тисяча, not одна тисяча
        } else {
            out = format!("{} ", number_part(sign, whole, frac, case, noun(name).0));
            out += if !frac.is_empty() { noun(name).1[GEN] } else { noun_form(name, n, case) };
        }
        if !unit.is_empty() {
            out += &format!(" {}", unit_words(unit, n, frac, case, true));
        }
        let tok = if unit.is_empty() { scale } else { unit };
        return format!("{out}{}", drop_dot(tok, rest));
    }
    if !unit.is_empty() {
        let name = find(UNIT_TOK, unit).unwrap();
        if let Some(mi) = find(MINOR, name).filter(|_| frac.chars().count() == 2) {
            // 49,50 грн: hryvnias and kopecks
            let mut out = format!("{}{} {}", sign_word(sign), card(n, case, noun(name).0), noun_form(name, n, case));
            let k = py_int(frac) as u64;
            if k != 0 {
                out += &format!(" {} {}", card(k, case, noun(mi).0), noun_form(mi, k, case));
            }
            return format!("{out}{}", drop_dot(unit, rest));
        }
        let out = format!(
            "{} {}",
            number_part(sign, whole, frac, case, noun(name).0),
            unit_words(unit, n, frac, case, false)
        );
        return format!("{out}{}", drop_dot(unit, rest));
    }
    let gender = if noun_w.is_empty() { "m" } else { gender_of(noun_w, n, case) };
    number_part(sign, whole, frac, case, gender)
}

static NUM_RX: LazyLock<String> = LazyLock::new(|| {
    format!(
        r"([-−+]{SP}?|(?:плюс|мінус){SP}+)?({NUM})(?:,(\d{{1,6}}))?{RB}(?:{SP}?{SCALE_RX}(?![\w]))?(?:{SP}?{UNIT_RX}(?![\w']))?"
    )
});

fn uk_case(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{}{SP}+{}", *PREP_RX, *NUM_RX);
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, sign, whole, frac, scale, unit) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
        let rest = &t[end(m)..];
        if scale.is_empty() && unit.is_empty() {
            let tok = caps(&format!(r"^{SP}*(\S*)"), rest).map_or(String::new(), |x| g(&x, 1).to_string());
            if tok == "по" && ["з", "із", "зі"].contains(&prep.to_lowercase().as_str()) {
                return None;
            }
            if !plain_word(&tok) {
                return None;
            }
        }
        if prep.chars().count() == 1
            && scale.is_empty()
            && unit.is_empty()
            && search(&format!(r"^{SP}*[^\s\w]*{SP}*$"), rest)
        {
            return None;
        }
        let noun_w = if !scale.is_empty() || !unit.is_empty() { String::new() } else { counted_noun(rest) };
        let case = noun_case(prep, &noun_w, to_int(whole));
        if case == NONE {
            return None;
        }
        Some(spoken(prep, sign, whole, frac, scale, unit, case, rest, &noun_w))
    })
}

/// Feminine nouns in the nominative plural after 2–4 (the ending does not tell them from masculine ones).
const FEM_PL: &[&str] = &[
    "книжки",
    "книги",
    "години",
    "хвилини",
    "секунди",
    "гривні",
    "копійки",
    "сторінки",
    "довідки",
    "особи",
    "людини",
    "частини",
    "доби",
    "чашки",
    "ложки",
    "склянки",
    "пляшки",
    "кімнати",
    "квартири",
    "машини",
    "сестри",
    "доньки",
    "дочки",
    "жінки",
    "дівчини",
    "подруги",
    "мови",
    "країни",
    "області",
    "школи",
    "групи",
    "команди",
    "статті",
    "задачі",
    "вправи",
    "теми",
    "речі",
    "ночі",
    "відповіді",
    "вулиці",
    "зміни",
    "порції",
    "таблетки",
    "ягоди",
    "сторони",
    "ролі",
    "причини",
    "картки",
    "тонни",
    "банки",
    "хвилинки",
    "пари",
    "сім'ї",
    "дитини",
    "ідеї",
    "станції",
    "лекції",
    "серії",
    "версії",
    "категорії",
    "упаковки",
    "пачки",
    "коробки",
    "сумки",
    "ручки",
    "тарілки",
    "пігулки",
    "дівчинки",
    "студентки",
    "оцінки",
    "зупинки",
    "спроби",
    "поїздки",
    "бригади",
    "кави",
    "тисячі",
];
/// Masculine words in -а/-я/-у/-ю (genitives after 1) and words after a number that are not its noun.
const MASC_A: &[&str] = &[
    "року",
    "часу",
    "дня",
    "тижня",
    "місяця",
    "разу",
    "кілометра",
    "метра",
    "долара",
    "відсотка",
    "градуса",
    "суддя",
    "староста",
    "колега",
    "тато",
    "батько",
    "дядько",
];
const FUNC: &[&str] = &[
    "і",
    "й",
    "та",
    "або",
    "чи",
    "на",
    "до",
    "з",
    "по",
    "за",
    "від",
    "у",
    "в",
    "також",
    "теж",
    "ще",
    "вже",
    "більше",
    "менше",
    "раз",
    "разів",
    "рази",
    "тисячі",
    "тисяча",
    "тисячу",
    "це",
    "то",
    "що",
];

/// The gender of the noun counted by n (only 1 and 2 have gender forms), from its ending (and, for the plural after
/// 2–4, a list of feminine nouns).
fn gender_of(noun_w: &str, n: u64, case: usize) -> &'static str {
    let w = noun_w.to_lowercase();
    if MASC_A.contains(&w.as_str()) || FUNC.contains(&w.as_str()) || n % 100 == 11 || n % 100 == 12 {
        return "m";
    }
    let last = n % 10;
    if case == NOM || case == ACC {
        if last == 1 {
            if search(r"(?:ння|ття|сся|лля|ззя|ччя|жжя|ддя|цця|шшя|нья|ім'я)$", &w) || search(r"[оеє]$", &w)
            {
                return "n";
            }
            if search(r"[аяую]$", &w) {
                return "f";
            }
            return "m";
        }
        if last == 2 {
            return if FEM_PL.contains(&w.as_str()) || search(r"(?:ії|еї|ості)$", &w) { "f" } else { "m" };
        }
        return "m";
    }
    if last != 1 {
        return "m";
    }
    if case == GEN {
        return if search(r"(?:[иії]|ої|еї)$", &w) && !search(r"(?:ння|ття)$", &w) { "f" } else { "m" };
    }
    if case == INS {
        return if search(r"(?:ою|ею|єю)$", &w) { "f" } else { "m" };
    }
    "m"
}

fn uk_count(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}(?:{}{SP}+)?{LB}{}", *PREP_RX, *NUM_RX);
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (prep, sign, whole, frac, scale, unit) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
        let rest = &t[end(m)..];
        if !prep.is_empty() && !["в", "у", "на", "за", "про", "через", "понад"].contains(&prep.to_lowercase().as_str())
        {
            return None;
        }
        if search(&LABEL_RX, &t[..start(m)]) {
            return None;
        }
        let n = to_int(whole);
        if scale.is_empty() && unit.is_empty() {
            if !frac.is_empty() || !sign.is_empty() || !(n % 10 == 1 || n % 10 == 2) || n % 100 == 11 || n % 100 == 12 {
                return None;
            }
            let nm = caps(&format!(r"^{SP}+([а-яєіїґ']+)(?:{SP}+([а-яєіїґ']+))?"), rest)?;
            let mut noun_w = g(&nm, 1);
            if !g(&nm, 2).is_empty() && search(r"(?:і|их)$", noun_w) && n % 10 == 2 {
                noun_w = g(&nm, 2);
            }
            if noun_w.chars().count() < 3 {
                return None;
            }
            if !prep.is_empty() && n % 10 == 1 && search(r"[ая]$", noun_w) {
                return None;
            }
            let gnd = gender_of(noun_w, n, NOM);
            if gnd == "m" {
                return None;
            }
            let acc = !prep.is_empty() || n % 10 == 1 && gnd == "f" && search(r"[ую]$", noun_w);
            return Some(lead(prep, &number_part(sign, whole, "", if acc { ACC } else { NOM }, gnd)));
        }
        let out = spoken(prep, sign, whole, frac, scale, unit, if prep.is_empty() { NOM } else { ACC }, rest, "");
        if words(&m[0], "uk").trim_end_matches('.') == out.trim_end_matches('.') {
            return None;
        }
        Some(out)
    })
}

static LABEL_RX: LazyLock<String> = LazyLock::new(|| {
    format!(
        r"(?i)(?:^|[^\w])(?:розділ[ау]?|стаття|статті|статтю|пункт[ау]?|частин[аиу]|том[ау]?|номер[ау]?|параграф[ау]?|додат(?:ок|ка|ку)|сторінк[аиу]|таблиц[яію]|рисун(?:ок|ка|ку)|варіант[ау]?|етап[ау]?|рів(?:ень|ня)|урок[ау]?|завдання|задач[аіу]|питання|крок[ау]?|сері[яії]|сезон[ау]?|епізод[ау]?|версі[яії]|[а-яєіїґ]{{1,4}}\.|№){SP}*$"
    )
});

/// A preposition that takes the accusative right before the number (понад тисячу).
static ACC_BEFORE: LazyLock<String> =
    LazyLock::new(|| format!("{}{SP}+$", prep_rx(&["на", "в", "у", "за", "про", "через", "понад"])));

fn uk_thousand(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}(1[ \x{{A0}}]?\d{{3}}){RB}(?:({SP}?)(\S+))?");
    let months = MONTHS.join("|");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (sp, tok) = (g(m, 2), g(m, 3));
        if tok.is_empty() || search(&format!(r"^(?:р\.?|рр\.|рок[а-яі]*|рік|році|{months})(?![\w])"), tok)
        {
            return None;
        }
        if !search(r"^[₴$€%°a-zа-яєіїґ]", tok) {
            return None;
        }
        let low = to_int(g(m, 1)) % 1000;
        let th = if search(&ACC_BEFORE, &t[..start(m)]) { "тисячу" } else { "тисяча" };
        if low != 0 {
            return Some(format!("{th} {low}{sp}{tok}"));
        }
        if plain_word(tok) {
            return Some(format!("{th}{sp}{tok}"));
        }
        let gw = words(&format!("5 {tok}"), "uk");
        if !gw.starts_with("п'ять ") || gw == format!("п'ять {tok}") {
            return None;
        }
        let tail: String = gw.chars().skip(6).collect();
        Some(format!("{th} {tail}"))
    })
}
