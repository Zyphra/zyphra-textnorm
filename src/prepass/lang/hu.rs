//! 'hu' rules: the port of the workbench's `langrules/hu.py` (ids `hu.*`).
//!
//! Hungarian says két (not kettő) before a noun and inside a compound number (kétezer, tizenkét, huszonkétmillió); the
//! grammar writes kettő everywhere and drops the egy of a leading million. These rules start from the grammar's own
//! reading of the number (and of the unit after it) and change only those words.

use std::collections::HashSet;
use std::sync::LazyLock;

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("hu.date", hu_date),
    ("hu.time", hu_time),
    ("hu.half", hu_half),
    ("hu.money-range", hu_money_range),
    ("hu.range", hu_range),
    ("hu.money-decimal", hu_money_decimal),
    ("hu.per-unit", hu_per_unit),
    ("hu.units", hu_units),
    ("hu.two", hu_two),
    ("hu.decimal-two", hu_decimal_two),
    ("hu.stb", hu_stb),
];

const SP: &str = r"[ \t\x{A0}]";
const NUM: &str = r"(\d{1,3}(?:[ \x{A0}\x{202F}]\d{3})+|\d+)";
/// The word (or unit, currency sign) after a number.
const TOKEN: &str = r"((?:[^\W\d_]+\.?(?:[-/][^\W\d_]+)*|[%€$£°]+[A-Za-z]?(?:-[^\W\d_]+)?))";

/// Words after a number that do not make it attributive (the number stands alone before them).
static STOP: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    "és vagy meg is sem se pedig de mint illetve ill. plusz mínusz szor szorozva osztva per egyenlő között után \
     előtt alatt felett fölött óta múlva közül helyett körül szerint nélkül ellen miatt által mellett felé közé mögött alá \
     elé fölé iránt keresztül át túl belül kívül van volt lesz vannak voltak lesznek lett maradt marad kell kellett legyen \
     jön jött ment megy kap kapott lehet lehetett nincs már még csak például pl. kb. tehát azaz vagyis ha hogy amikor mert \
     sem is a az egy"
        .split_whitespace()
        .collect()
});

const MONTHS: [&str; 12] = [
    "január",
    "február",
    "március",
    "április",
    "május",
    "június",
    "július",
    "augusztus",
    "szeptember",
    "október",
    "november",
    "december",
];
const MONTH_RX: &str = r"(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december|jan|febr|márc|ápr|jún|júl|aug|szept|okt|nov|dec)";

/// kettő inside a compound number → két (kettőezer → kétezer, huszonkettőmillió → huszonkétmillió), and the egy of a
/// leading million (millió-hétszázezer → egymillió-hétszázezer).
fn fix_inner(r: &str) -> String {
    let r = rx(r"kettő(?=ezer|millió|milliárd|billió)").replace_all(r, "két").into_owned();
    let (pre, rest) = match r.strip_prefix("mínusz ") {
        Some(x) => ("mínusz ", x),
        None => ("", r.as_str()),
    };
    if ["millió", "milliárd", "billió"].iter().any(|s| rest.starts_with(s)) {
        return format!("{pre}egy{rest}");
    }
    r
}

/// The number's last word before a noun: …kettő → …két.
fn attributive(r: &str) -> String {
    match r.strip_suffix("kettő") {
        Some(head) => fix_inner(&format!("{head}két")),
        None => fix_inner(r),
    }
}

/// The grammar's reading of the word or unit after a number (2 kg → kilogramm), or None when it reads the pair some
/// other way.
fn unit_reading(token: &str) -> Option<String> {
    let one = words("1", "hu");
    let r = words(&format!("1 {token}"), "hu");
    r.strip_prefix(&format!("{one} ")).map(str::to_string)
}

/// A word after a number that leaves it standing alone: a listed conjunction, postposition or verb, or a verb in -ik
/// (hiányzik, található).
fn stop(tok: &str) -> bool {
    let w = tok.to_lowercase();
    let w = w.trim_end_matches('.');
    STOP.contains(w) || (w.chars().count() > 3 && w.ends_with("ik"))
}

/// The last element of a number word and its vowel harmony: B back, F front, R front rounded (longest first).
const ELEMENTS: &[(&str, char)] = &[
    ("kilencven", 'F'),
    ("nyolcvan", 'B'),
    ("milliárd", 'B'),
    ("negyven", 'F'),
    ("harminc", 'B'),
    ("hetven", 'F'),
    ("hatvan", 'B'),
    ("kilenc", 'F'),
    ("millió", 'B'),
    ("ötven", 'F'),
    ("három", 'B'),
    ("kettő", 'R'),
    ("nyolc", 'B'),
    ("nulla", 'B'),
    ("húsz", 'B'),
    ("négy", 'F'),
    ("ezer", 'F'),
    ("száz", 'B'),
    ("tíz", 'F'),
    ("hat", 'B'),
    ("hét", 'F'),
    ("egy", 'F'),
    ("öt", 'R'),
];
/// Suffixes whose vowel follows the word: back, front, front rounded.
const HARMONIC: &[[&str; 3]] = &[
    ["ra", "re", "re"],
    ["ba", "be", "be"],
    ["ban", "ben", "ben"],
    ["ból", "ből", "ből"],
    ["ról", "ről", "ről"],
    ["tól", "től", "től"],
    ["nál", "nél", "nél"],
    ["hoz", "hez", "höz"],
    ["nak", "nek", "nek"],
    ["szor", "szer", "ször"],
];

/// The suffix in the vowel harmony of the number word it goes on: 5-ra → re (ötre), 3-szer → szor (háromszor).
fn harmonize<'a>(suf: &'a str, r: &str) -> &'a str {
    let Some((e, h)) = ELEMENTS.iter().find(|(e, _)| r.ends_with(e)) else { return suf };
    let i = match h {
        'B' => 0,
        'F' => 1,
        _ => 2,
    };
    // kettő takes -szer on its két stem (kétszer)
    HARMONIC
        .iter()
        .find(|trio| trio.contains(&suf))
        .map_or(suf, |trio| if trio[0] == "szor" && *e == "kettő" { "szer" } else { trio[i] })
}

/// A compound element written with a hyphen (2-féle, 2-éves, 2-szobás, 2-heti), not a case or ordinal suffix.
const COMPOUND: &str = r"(?:[^\W\d_]{2,}(?:s|ú|ű|i)|féle)";

fn hu_two(t: String, c: &mut Ctx) -> String {
    let pat = [
        r"(?<![\w.,:/+−–$€£¥-])(?<!\d",
        SP,
        r")([$€£¥]?)([-−]?)",
        NUM,
        r"(?![\d]|[.,:/]\d|",
        SP,
        r"\d|[.:/]|[-–]\d)(?:-([^\W\d_]+))?(?:(",
        SP,
        r"?)",
        TOKEN,
        r")?(?![\w])",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        let (sym, sign, num, sep, tok) = (g(m, 1), g(m, 2), g(m, 3), g(m, 5), g(m, 6));
        let suf = m.get(4).map(|x| x.as_str());
        let n = format!("{sign}{num}");
        if !sym.is_empty() {
            let r = words(&format!("{sym}{n}{}", suf.map(|s| format!("-{s}")).unwrap_or_default()), "hu");
            let new = rx(r"kettő(?= [^\W\d_])").replace_all(&fix_inner(&r), "két").into_owned();
            return if new == r { None } else { Some(format!("{new}{sep}{tok}")) };
        }
        if let Some(suf) = suf {
            let r = words(&format!("{n}-{suf}"), "hu");
            if r.ends_with(&format!(" {suf}")) && full(COMPOUND, suf) {
                let new = attributive(&words(&n, "hu")) + suf;
                return if new == r.replace(' ', "") { None } else { Some(format!("{new}{sep}{tok}")) };
            }
            let new = fix_inner(&words(&format!("{n}-{}", harmonize(suf, &words(&n, "hu"))), "hu"));
            return if new == r { None } else { Some(format!("{new}{sep}{tok}")) };
        }
        let rn = words(&n, "hu");
        if !tok.is_empty() {
            if sep.is_empty() && matches_at_start(r"[^\W\d_]", tok) {
                return None;
            }
            let rest = unit_reading(tok)?;
            let new = if stop(tok) { fix_inner(&rn) } else { attributive(&rn) };
            return if new == rn { None } else { Some(format!("{new} {rest}")) };
        }
        let new = fix_inner(&rn);
        if new == rn { None } else { Some(new) }
    })
}

/// YYYY, MM, DD (and a final period or suffix) as the year's words, the month name and the day for the grammar.
fn ymd(y: &str, mo: &str, d: &str, tail: &str) -> Option<String> {
    let (mo, d) = (py_int(mo), py_int(d));
    if !((1..=12).contains(&mo) && (1..=31).contains(&d)) {
        return None;
    }
    let tail = if tail.starts_with('-') { tail } else { "." };
    Some(format!("{} {} {d}{tail}", fix_inner(&words(y, "hu")), MONTHS[mo as usize - 1]))
}

fn hu_date(t: String, c: &mut Ctx) -> String {
    let pat =
        [r"(?<![\w.,:/-])(\d{4})\.", SP, r"?(\d{1,2})\.", SP, r"?(\d{1,2})(\.|-[^\W\d_]+)?(?![\d.]\d|\w)"].concat();
    let t = c.sub(&rx(&pat), &t, |m| ymd(g(m, 1), g(m, 2), g(m, 3), g(m, 4)));
    let t = c.sub(&rx(r"(?<![\w.,:/-])(\d{4})-(\d\d)-(\d\d)(-[^\W\d_]+)?(?![\d\w])"), &t, |m| {
        ymd(g(m, 1), g(m, 2), g(m, 3), g(m, 4))
    });
    c.sub(&rx(&[r"(?<![\w.,:/-])(\d{4})\.?", SP, r"+(?=", MONTH_RX, r")"].concat()), &t, |m| {
        let r = words(g(m, 1), "hu");
        let new = fix_inner(&r);
        if new == r { None } else { Some(new + " ") }
    })
}

fn hu_time(t: String, c: &mut Ctx) -> String {
    let pat = [
        r"(?<![\w.,:/-])(\d{1,2})([:.])(\d{2})(?:-([^\W\d_]+))?(?![\w.,:]\d|\w)(",
        SP,
        r"*(?:[aApP]\.?[mM]\.?|de\.|du\.)(?!\w))?",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        let (h, mm) = (g(m, 1), g(m, 3));
        let suf = m.get(4).map(|x| x.as_str());
        if g(m, 2) == "." && suf.is_none() {
            return None;
        }
        if m.get(5).is_some() && suf.is_some() {
            return None;
        }
        if py_int(h) > 23 || py_int(mm) > 59 {
            return None;
        }
        let rt = words(&m[0], "hu");
        let rh = words(&py_int(h).to_string(), "hu");
        if !rt.starts_with(&format!("{rh} óra")) {
            return None;
        }
        if let Some(suf) = suf
            && py_int(mm) != 0
        {
            let m_ = py_int(mm).to_string();
            let suf = harmonize(suf, &words(&m_, "hu"));
            return Some(format!("{} óra {}", attributive(&rh), words(&format!("{m_}-{suf}"), "hu")));
        }
        let new = attributive(&rh) + &rx(r"kettő(?= perc)").replace_all(&rt[rh.len()..], "két");
        if new == rt { None } else { Some(new) }
    })
}

fn hu_half(t: String, c: &mut Ctx) -> String {
    const FR: &[(&str, &str)] = &[
        ("1/2", "fél"),
        ("½", "fél"),
        ("1/4", "negyed"),
        ("¼", "negyed"),
        ("3/4", "háromnegyed"),
        ("¾", "háromnegyed"),
    ];
    let pat =
        [r"(?<![\w.,:/])(?:(\d+)(?:", SP, r"+|(?=½)))?(1/2|½|1/4|¼|3/4|¾)(?![\d/])(", SP, r"*)", TOKEN, r"(?![\w])"]
            .concat();
    let t = c.sub(&rx(&pat), &t, |m| {
        let (f, tok) = (g(m, 2), g(m, 4));
        if stop(tok) {
            return None;
        }
        let rest = unit_reading(tok)?;
        let word = FR.iter().find(|(k, _)| *k == f).map(|(_, v)| *v)?;
        let Some(n) = m.get(1).map(|x| x.as_str()) else {
            return Some(format!("{word} {rest}"));
        };
        if word != "fél" {
            return None;
        }
        if n == "1" {
            return Some(format!("másfél {rest}"));
        }
        Some(format!("{} és fél {rest}", attributive(&words(n, "hu"))))
    });
    c.sub(&rx(&[r"(?<![\w.,:/+−-])(\d+)(?=", SP, r"+és", SP, r"+fél(?!\w))"].concat()), &t, |m| {
        let r = words(g(m, 1), "hu");
        let a = attributive(&r);
        if a == r { None } else { Some(a) }
    })
}

fn hu_range(t: String, c: &mut Ctx) -> String {
    let pat =
        [r"(?<![\w.,:/+−–-])(\d+)[-–](\d+)(?![\d.,:/]|[-–]?[^\W\d_])(?:(", SP, r"+)", TOKEN, r")?(?![\w])"].concat();
    c.sub(&rx(&pat), &t, |m| {
        let (a, b, sep) = (g(m, 1), g(m, 2), g(m, 3));
        let tok = m.get(4).map(|x| x.as_str());
        if py_int(a) >= py_int(b) {
            return None;
        }
        if let Some(tok) = tok
            && !stop(tok)
        {
            let rest = unit_reading(tok)?;
            return Some(format!("{}-{} {rest}", attributive(&words(a, "hu")), attributive(&words(b, "hu"))));
        }
        let r = words(&format!("{a}-{b}"), "hu");
        let new = fix_inner(&r);
        if new == r { None } else { Some(format!("{new}{sep}{}", tok.unwrap_or(""))) }
    })
}

fn hu_stb(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.])stb\.(?!\w)"), &t, |m| {
        let end = m.get(0).expect("group 0").end();
        let dot = matches_at_start(&[SP, r"*(?:$|\n)|", SP, r"+[A-ZÁÉÍÓÖŐÚÜŰ]"].concat(), &t[end..]);
        Some(format!("satöbbi{}", if dot { "." } else { "" }))
    })
}

// ================================================================================ money and units (Nov 16 b)

const MONEY_CUR: &str = r"Ft|HUF|€|EUR|\$|USD|£|GBP|CHF";
const MONEY_SIGN: &str = r"[€$£]";

fn hu_money_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&format!(r"(?<=\d){SP}?({MONEY_CUR}){SP}?[-–~]{SP}?(\d+(?:,\d{{1,2}})?){SP}?\1(?![\w])")),
        &t,
        |m| Some(format!("-{} {}", g(m, 2), g(m, 1))),
    );
    c.sub_tpl(&rx(&format!(r"(?<=\d) ?~ ?(?={MONEY_SIGN}?\d)")), &t, "-")
}

/// An amount with decimals in the grammar's money style with két for kettő, or None when the grammar has no
/// hundredths word for the currency.
fn money_words(sign: &str, num: &str, frac: &str, cur: &str) -> Option<String> {
    let name = unit_reading(cur)?;
    let r = words(&format!("1,50 {cur}"), "hu");
    let head = format!("egy {name} ötven ");
    let minor = r.strip_prefix(&head)?;
    let whole = py_int(&num.chars().filter(char::is_ascii_digit).collect::<String>());
    let cents = py_int(&format!("{frac:0<2}"));
    let mut out = if whole > 0 { format!("{} {name}", attributive(&words(num, "hu"))) } else { String::new() };
    if cents > 0 {
        let cw = format!("{} {minor}", attributive(&words(&cents.to_string(), "hu")));
        out = if out.is_empty() { cw } else { format!("{out} {cw}") };
    }
    if out.is_empty() {
        return None;
    }
    Some(format!("{}{out}", if sign.is_empty() { "" } else { "mínusz " }))
}

fn hu_money_decimal(t: String, c: &mut Ctx) -> String {
    let t =
        c.sub(&rx(&format!(r"(?<![\w.,:/+−–-])([-−]?){NUM},(\d{{1,2}}){SP}?({MONEY_CUR})(?![\w-])")), &t, |m| {
            let out = money_words(g(m, 1), g(m, 2), g(m, 3), g(m, 4))?;
            if out == words(&m[0], "hu") { None } else { Some(out) }
        });
    c.sub(&rx(&format!(r"(?<![\w.,:/+−–-])([-−]?)({MONEY_SIGN}){NUM},(\d{{1,2}})(?![\d\w-]|,\d)")), &t, |m| {
        let out = money_words(g(m, 1), g(m, 3), g(m, 4), g(m, 2))?;
        if out == words(&m[0], "hu") { None } else { Some(out) }
    })
}

/// A slash after an amount: the denominators the grammar leaves unread.
const PER_UNIT: &[(&str, &str)] = &[
    ("éjszaka", "per éjszaka"),
    ("éj", "per éjszaka"),
    ("hét", "per hét"),
    ("kWh", "per kilowattóra"),
    ("km", "per kilométer"),
    ("ha", "per hektár"),
    ("l", "per liter"),
    ("t", "per tonna"),
];

/// `|`-joined keys, longest first (ties in table order); `escape` runs `re.escape` on each.
fn alternation(keys: &[&str], escape: bool) -> String {
    let mut ks: Vec<&str> = keys.to_vec();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    ks.iter().map(|k| if escape { super::super::re_escape(k) } else { k.to_string() }).collect::<Vec<_>>().join("|")
}

fn hu_per_unit(t: String, c: &mut Ctx) -> String {
    let dens = alternation(&PER_UNIT.iter().map(|kv| kv.0).collect::<Vec<_>>(), true);
    c.sub(&rx(&format!(r"(?<=\d)({SP}?(?:{MONEY_CUR}))/({dens})(?![\w²])")), &t, |m| {
        let plain = words(&format!("5 {}/{}", g(m, 1).trim_matches([' ', '\t', '\u{a0}']), g(m, 2)), "hu");
        if !plain.contains('/') {
            return None;
        }
        Some(format!("{} {}", g(m, 1), PER_UNIT.iter().find(|kv| kv.0 == g(m, 2))?.1))
    })
}

/// Units and currencies the grammar leaves as typed after a number.
const UNIT_WORDS: &[(&str, &str)] = &[
    ("t", "tonna"),
    ("ha", "hektár"),
    ("RON", "román lej"),
    ("RSD", "szerb dinár"),
    ("HRK", "horvát kuna"),
    ("BGN", "bolgár leva"),
];

fn hu_units(t: String, c: &mut Ctx) -> String {
    let keys = alternation(&UNIT_WORDS.iter().map(|kv| kv.0).collect::<Vec<_>>(), false);
    c.sub(&rx(&format!(r"(?<=\d)({SP}?)({keys})(?![\w/²-])")), &t, |m| {
        Some(format!(" {}", UNIT_WORDS.iter().find(|kv| kv.0 == g(m, 2))?.1))
    })
}

fn hu_decimal_two(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.,:/+−–-])[-−]?{NUM},\d+(?![\d]|[.,:/]\d)(?:{SP}?{TOKEN}(?![\w]))?")), &t, |m| {
        let r = words(&m[0], "hu");
        let new = fix_inner(&r);
        if new == r { None } else { Some(new) }
    })
}
