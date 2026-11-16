//! 'bg' rules: the port of the workbench's `langrules/bg.py` (ids `bg.*`).
//!
//! Bulgarian has no case, but the grammar reads every number in its neuter/feminine counting form (едно, две) whatever
//! noun follows, leaves the definite ordinal endings (2-рата), the scale abbreviations (хил., млн., млрд.) and several
//! units (ч., мин., кв. м) unread, and takes г after a number for a year. These rules start from the grammar's own
//! reading of the number and change only the word that depends on the noun.

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, search};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::py_strip;

pub(super) const RULES: &[LangRule] = &[
    ("bg.decade", bg_decade),
    ("bg.date-range", bg_date_range),
    ("bg.ordinal-def", bg_ordinal_def),
    ("bg.range", bg_range),
    ("bg.scale", bg_scale),
    ("bg.units", bg_units),
    ("bg.half", bg_half),
    ("bg.gender", bg_gender),
];

const NUM: &str = r"\d{1,3}(?:[ \x{A0}]\d{3}){1,4}|\d{1,15}";
const LB: &str = r"(?<![\w\-–—.,/:+])";
const RB: &str = r"(?![\d]|[.,:/\-]\d|[^\W\d_])";
const SP: &str = r"[ \x{A0}]";
const SKIP: &str = "\u{e000}[^\u{e001}]*\u{e001}|";

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

fn to_int(s: &str) -> u64 {
    py_int(s) as u64
}

/// The counting form of the last word for each gender (the grammar writes the neuter/feminine one).
fn gender_form(gender: &str, w: &str) -> Option<&'static str> {
    match (gender, w) {
        ("m", "едно") => Some("един"),
        ("m", "две") => Some("два"),
        ("f", "едно") => Some("една"),
        ("mp", "две") => Some("двама"),
        ("mp", "три") => Some("трима"),
        ("mp", "четири") => Some("четирима"),
        ("mp", "пет") => Some("петима"),
        ("mp", "шест") => Some("шестима"),
        _ => None,
    }
}

/// The cardinal n with the counting form of its last word for `gender` (m, f, n, mp: masculine persons).
fn card(n: u64, gender: &str) -> String {
    let w = words(&n.to_string(), "bg");
    let mut parts: Vec<&str> = w.split(' ').collect();
    let last = parts.len() - 1;
    if let Some(f) = gender_form(gender, parts[last]) {
        parts[last] = f;
    }
    parts.join(" ")
}

/// (the words before the last one, the stem of the last word, the last word): 21 → ("двадесет и", "първ", "първи"),
/// 100 → ("", "стотн", "стотен").
fn ordinal_stem(n: u64) -> (String, String, String) {
    let w = words(&format!("{n}-ти"), "bg");
    let (head, last) = match w.rsplit_once(' ') {
        Some((h, l)) => (h.to_string(), l.to_string()),
        None => (String::new(), w.clone()),
    };
    let cut = |k: usize| -> String {
        let chars: Vec<char> = last.chars().collect();
        chars[..chars.len() - k].iter().collect()
    };
    if last.ends_with("ен") {
        let stem = format!("{}н", cut(2));
        return (head, stem, last);
    }
    let stem = cut(1);
    (head, stem, last)
}

const ORD_END: [&str; 5] = ["ият", "ия", "ата", "ото", "ите"];

/// The ordinal n with `ending` on its stem: и (the masculine: първи, стотен), ият, ия, ата, ото, ите.
fn ordinal(n: u64, ending: &str) -> String {
    let (head, stem, last) = ordinal_stem(n);
    let word = if ending == "и" { last } else { format!("{stem}{ending}") };
    if head.is_empty() { word } else { format!("{head} {word}") }
}

fn bg_decade(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}(\d{{0,2}}[1-9]0-те){SP}+(години|год\.|г\.)(?![\w])");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let rest = &t[end(m)..];
        let dot = if g(m, 2).ends_with('.') && (py_strip(rest).is_empty() || search(r"^[ \t]*\n|^\s+[А-ЯA-Z]", rest))
        {
            "."
        } else {
            ""
        };
        Some(format!("{}{dot}", g(m, 1)))
    })
}

const MONTHS: [&str; 12] = [
    "януари",
    "февруари",
    "март",
    "април",
    "май",
    "юни",
    "юли",
    "август",
    "септември",
    "октомври",
    "ноември",
    "декември",
];

fn bg_date_range(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}(?:(?<![\w\-])([Оо]т|[Мм]ежду){SP}+)?{LB}(\d{{1,2}})({SP}*[-–—]{SP}*|{SP}+(?:до|и){SP}+)(\d{{1,2}}){SP}+({})(?![\w])",
        MONTHS.join("|")
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (mut prep, a, sep, b, month) =
            (g(m, 1).to_string(), py_int(g(m, 2)) as u64, g(m, 3), py_int(g(m, 4)) as u64, g(m, 5));
        if !((1..=31).contains(&a) && (1..=31).contains(&b)) {
            return None;
        }
        let mut s = py_strip(sep).to_lowercase();
        let p = prep.to_lowercase();
        if s == "и" && p != "между" || s == "до" && !(p == "от" || p.is_empty()) {
            return None;
        }
        if s == "-" || s == "–" || s == "—" {
            s = "до".to_string();
            if !(p.is_empty() || p == "от") {
                return None;
            }
            if prep.is_empty() {
                prep = "от".to_string();
            }
        }
        Some(format!("{prep} {} {s} {} {month}", ordinal(a, "и"), ordinal(b, "и")))
    })
}

fn bg_ordinal_def(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}(\d{{1,9}})-([а-я]{{1,6}})(?![\w\-])");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (n, suffix) = (py_int(g(m, 1)) as u64, g(m, 2));
        if !search(r"\d", &words(&m[0], "bg")) {
            return None; // the grammar reads it
        }
        for e in ORD_END {
            if let Some(pre) = suffix.strip_suffix(e) {
                let stem = ordinal_stem(n).1;
                if !pre.is_empty() && !stem.ends_with(pre) {
                    return None;
                }
                return Some(ordinal(n, e));
            }
        }
        None
    })
}

fn scale(tok: &str) -> (&'static str, &'static str, &'static str) {
    match tok {
        "хил." | "хил" => ("f", "хиляда", "хиляди"),
        "млн." | "млн" => ("m", "милион", "милиона"),
        "млрд." | "млрд" => ("m", "милиард", "милиарда"),
        _ => ("m", "трилион", "трилиона"),
    }
}

fn currency(tok: &str) -> &'static str {
    match tok {
        "лв." | "лв" => "лева",
        "€" | "евро" | "EUR" => "евро",
        _ => "долара",
    }
}

const DENOM: [&str; 3] = ["десет", "стотн", "хилядн"];

/// i,frac: два цяло и пет десети (the whole part agrees with the noun after the number).
fn decimal(i: u64, frac: &str, gender: &str) -> String {
    let f = py_int(frac) as u64;
    let num = card(f, "f");
    let den = format!("{}{}", DENOM[frac.chars().count() - 1], if f % 10 == 1 && f % 100 != 11 { "а" } else { "и" });
    format!("{} цяло и {num} {den}", card(i, gender))
}

fn drop_dot(tok: &str, rest: &str) -> &'static str {
    if tok.ends_with('.') && (py_strip(rest).is_empty() || search(r"^[ \t]*\n|^\s+[А-ЯA-Z]", rest)) {
        "."
    } else {
        ""
    }
}

fn bg_scale(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"{SKIP}{LB}({NUM})(?:,(\d{{1,3}}))?{RB}{SP}?(хил\.?|млн\.?|млрд\.?|трлн\.?)(?![\w])(?:{SP}?(лв\.?|€|евро|EUR|\$|USD)(?![\w]))?"
    );
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (whole, frac, sc, cur) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let (gnd, one, many) = scale(sc);
        let n = to_int(whole);
        let mut out = if !frac.is_empty() {
            format!("{} {many}", decimal(n, frac, gnd))
        } else if n == 1 {
            if gnd == "f" { one.to_string() } else { format!("{} {one}", card(1, gnd)) }
        } else {
            format!("{} {many}", card(n, gnd))
        };
        if !cur.is_empty() {
            out += &format!(" {}", currency(cur));
        }
        let tok = if cur.is_empty() { sc } else { cur };
        Some(format!("{out}{}", drop_dot(tok, &t[end(m)..])))
    })
}

fn bg_range(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}({NUM}){SP}?[–—]{SP}?({NUM}){RB}(?:({SP}?){UNIT_RX})?(?={SP}?\S)");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (a, b, sp, u, dot) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        let (na, nb) = (to_int(a), to_int(b));
        if na >= nb || (1000..=2100).contains(&na) && (1000..=2100).contains(&nb) {
            return None; // a score (2–1) or a range of years
        }
        let rest = &t[end(m)..];
        if !search(RANGE_PREP_RX, &t[..start(m)].to_lowercase()) {
            return Some(format!("от {a} до {b}{sp}{u}{dot}"));
        }
        // after a preposition: N-M (в 2–3 пъти → в два-три пъти, за 5–10 мин. → за пет-десет минути)
        if !u.is_empty() {
            let key = u.replace('\u{a0}', " ");
            if key == "г" && !dot.is_empty() {
                return None;
            }
            let (gnd, _, many) = unit(&key)?;
            let tok = format!("{u}{dot}");
            return Some(format!("{}-{} {many}{}", card(na, gnd), card(nb, gnd), drop_dot(&tok, rest)));
        }
        let nm = caps(&format!(r"^{SP}+([а-я]{{3,}})(?![\w])"), rest)?;
        let noun_w = g(&nm, 1);
        if words(&format!("5 {noun_w}"), "bg") != format!("пет {noun_w}") {
            return None;
        }
        let gnd = match noun_gender(noun_w, nb) {
            "" => "n",
            "mp" => "m",
            x => x,
        };
        Some(format!("{}-{}", card(na, gnd), card(nb, gnd)))
    })
}

const RANGE_PREP_RX: &str =
    r#"(?<![^\s(«\"„“])(?:в|във|на|за|с|със|от|до|около|между|по|над|под|при|без|след|преди)[ \x{A0}]*$"#;

/// Units the grammar leaves unread: token → (gender, singular, counted form).
fn unit(tok: &str) -> Option<(&'static str, &'static str, &'static str)> {
    match tok {
        "ч." | "ч" => Some(("m", "час", "часа")),
        "мин." | "мин" => Some(("f", "минута", "минути")),
        "сек." | "сек" => Some(("f", "секунда", "секунди")),
        "кв. м" | "кв.м" => Some(("m", "квадратен метър", "квадратни метра")),
        "кв. км" | "кв.км" => Some(("m", "квадратен километър", "квадратни километра")),
        "куб. м" | "куб.м" => Some(("m", "кубичен метър", "кубични метра")),
        "г" => Some(("m", "грам", "грама")),
        _ => None,
    }
}

const UNIT_RX: &str = r"(кв\.[ \x{A0}]?км|кв\.[ \x{A0}]?м|куб\.[ \x{A0}]?м|мин\.?|сек\.?|ч\.?|г)(?![\w])(\.?)";

fn bg_units(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}({NUM}){RB}{SP}?{UNIT_RX}");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let (whole, u, dot) = (g(m, 1), g(m, 2), g(m, 3));
        let n = to_int(whole);
        let key = u.replace('\u{a0}', " ");
        if key == "г" && (!dot.is_empty() || (1000..=2100).contains(&n)) {
            return None;
        }
        let (gnd, one, many) = unit(&key)?;
        let tok = format!("{u}{dot}");
        Some(format!("{} {}{}", card(n, gnd), if n == 1 { one } else { many }, drop_dot(&tok, &t[end(m)..])))
    })
}

fn bg_half(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}(?:(\d{{1,9}}){SP}+)?1/2(?![\d/])");
    let t = c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let whole = g(m, 1);
        let nm = caps(&format!(r"^{SP}+([а-я]{{3,}})(?![\w])"), &t[end(m)..])?;
        let noun_w = g(&nm, 1);
        if words(&format!("5 {noun_w}"), "bg") != format!("пет {noun_w}") {
            return None; // not a plain noun (1/2 кг: the unit pass below)
        }
        if !whole.is_empty() {
            let n = py_int(whole) as u64;
            let gnd = noun_gender(noun_w, n);
            let gnd = if gnd == "mp" {
                "m"
            } else if gnd.is_empty() {
                "n"
            } else {
                gnd
            };
            return Some(format!("{} и половина", card(n, gnd)));
        }
        Some("половин".to_string())
    });
    let pat = format!(r"{SKIP}{LB}1/2{SP}?((?:кг|г|гр\.?|л|мл|км|м|см|ч\.?|мин\.?)(?![\w]))");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let tok = g(m, 1);
        if let Some((_, one, _)) = unit(tok) {
            return Some(format!("половин {one}{}", drop_dot(tok, &t[end(m)..])));
        }
        let gw = words(&format!("1 {tok}"), "bg");
        let um = caps(r"^(?:един|една|едно) (.+)$", &gw)?;
        if g(&um, 1) == tok {
            return None;
        }
        Some(format!("половин {}{}", g(&um, 1), drop_dot(tok, &t[end(m)..])))
    })
}

/// Masculine nouns in the counted form (два хляба, два часа) and the plurals that take два (два дни, два пъти).
const MASC_COUNT: &[&str] = &[
    "часа",
    "дни",
    "пъти",
    "месеца",
    "века",
    "етажа",
    "лева",
    "долара",
    "хляба",
    "стола",
    "града",
    "билета",
    "телефона",
    "компютъра",
    "автобуса",
    "влака",
    "самолета",
    "банана",
    "лимона",
    "домата",
    "зъба",
    "крака",
    "пръста",
    "плода",
    "начина",
    "въпроса",
    "отговора",
    "проблема",
    "случая",
    "урока",
    "филма",
    "сайта",
    "файла",
    "документа",
    "процента",
    "градуса",
    "килограма",
    "грама",
    "литра",
    "метра",
    "километра",
    "сантиметра",
    "милиметра",
    "броя",
    "пакета",
    "чифта",
    "сезона",
    "мача",
    "гола",
    "апартамента",
    "дома",
    "магазина",
    "ресторанта",
    "хотела",
    "парка",
    "моста",
    "острова",
    "езика",
    "учебника",
    "романа",
    "подаръка",
    "ключа",
    "вида",
    "варианта",
    "етапа",
    "кръга",
    "тома",
    "листа",
    "реда",
    "текста",
    "знака",
    "примера",
    "опита",
    "курса",
    "класа",
    "милиона",
    "милиарда",
    "сина",
    "внука",
];
/// Masculine persons (двама братя, трима студенти).
const MASC_PERSONS: &[&str] = &[
    "братя",
    "мъже",
    "синове",
    "сина",
    "студенти",
    "ученици",
    "учители",
    "лекари",
    "войници",
    "работници",
    "служители",
    "участници",
    "приятели",
    "гости",
    "туристи",
    "пътници",
    "играчи",
    "футболисти",
    "депутати",
    "журналисти",
    "полицаи",
    "пациенти",
    "клиенти",
    "кандидати",
    "министри",
    "съдии",
    "души",
    "човека",
    "внуци",
    "внука",
    "племенници",
    "адвокати",
    "инженери",
    "програмисти",
    "артисти",
    "певци",
    "пилоти",
    "шофьори",
    "бизнесмени",
    "мъжа",
    "членове",
    "кмета",
    "кметове",
    "братовчеди",
];
/// Masculine nouns in -а/-я/-о (баща, съдия, чичо) and neuter nouns in -и/-у (такси, меню).
const MASC_SG: &[&str] = &["баща", "съдия", "чичо", "дядо", "владика", "колега", "слуга"];
const NEUT_SG: &[&str] = &["такси", "меню", "бижу", "кафе", "евро"];
const LABEL_RX: &str = r"(?i)(?:^|[^\w])(?:глава|член|точка|алинея|раздел|част|том|номер|параграф|приложение|страница|таблица|фигура|вариант|етап|ниво|урок|задача|въпрос|стъпка|серия|сезон|епизод|версия|[а-я]{1,4}\.|№)[ \x{A0}]*$";

/// The gender a number takes from the noun after it: m, f, n or mp (masculine persons); "" when unsure.
fn noun_gender(noun_w: &str, n: u64) -> &'static str {
    let w = noun_w.to_lowercase();
    if MASC_PERSONS.contains(&w.as_str()) {
        return "mp";
    }
    if n == 1 {
        if MASC_SG.contains(&w.as_str()) {
            return "m";
        }
        if NEUT_SG.contains(&w.as_str()) || search(r"[оеиую]$", &w) {
            return "n";
        }
        if search(r"[ая]$", &w) {
            return "f";
        }
        return "m";
    }
    if MASC_COUNT.contains(&w.as_str()) {
        return "m";
    }
    ""
}

fn bg_gender(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"{SKIP}{LB}({NUM}){RB}");
    c.sub(&rx(&pat), &t, |m| {
        if skipped(m) {
            return None;
        }
        let n = to_int(g(m, 1));
        if search(LABEL_RX, &t[..start(m)]) {
            return None;
        }
        let nm = caps(&format!(r"^{SP}+(?:до{SP}+\d+{SP}+)?([а-я]+)"), &t[end(m)..])?;
        let noun_w = g(&nm, 1);
        if noun_w.chars().count() < 2 || (11..=19).contains(&(n % 100)) || super::shared::is_op_word("bg", noun_w) {
            return None; // (1 плюс 77 е равно на 78: an equation, not a count)
        }
        if words(&format!("5 {noun_w}"), "bg") != format!("пет {noun_w}") && noun_w != "година" {
            return None; // a unit or abbreviation the grammar reads (1 лв., 1 кг); година is read as a year
        }
        let mut gnd = noun_gender(noun_w, n);
        let last = n % 10;
        if gnd.is_empty() && last == 1 && n != 1 && search(r"и$", noun_w) {
            gnd = "f"; // двадесет и една години
        }
        if gnd.is_empty()
            || gnd == "n"
            || gnd == "mp" && !(1..=6).contains(&last)
            || gnd != "mp" && last != 1 && last != 2
        {
            return None;
        }
        if gnd == "mp" && last == 1 {
            gnd = "m";
        }
        let out = card(n, gnd);
        if out == words(g(m, 1), "bg") { None } else { Some(out) }
    })
}
