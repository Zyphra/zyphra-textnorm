//! 'he' rules: the port of the workbench's `langrules/he.py` (ids `he.*`).
//!
//! The Hebrew grammar reads every number in the feminine counting form, leaves a number with a proclitic letter
//! glued to it (ב-1948) unread, reads ordinals ה-N only in the masculine and for a few N, spells a Latin name before a
//! number letter by letter and reads HH:MM without the ו before the minutes. These rules write the spoken words for
//! those spans, starting from the grammar's own reading, or split the sentence right after a proclitic.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, full, g, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("he.abbrev", he_abbrev),
    ("he.letter-numeral", he_letter_numeral),
    ("he.latin-number", he_latin_number),
    ("he.time", he_time),
    ("he.decade", he_decade),
    ("he.gender", he_gender),
    ("he.ordinal", he_ordinal),
    ("he.proclitic", he_proclitic),
];

/// A proclitic run glued to a number (ב-1948, וב-5, כ-9.8): 1–3 of ו ה ב כ ל מ ש, then -, maqaf or nothing.
const PRE: &str = r"(?:([ובכלמשה]{1,3})[-־]?)?";
/// Geresh and gershayim, typed as ׳ ״ or as ' ".
const QUOTES: &str = "׳״'\"";
const GERSHAYIM: &str = "[״\"]";

/// Nothing glued before a number (or before its proclitics): a letter, a digit, a decimal mark, a geresh or a sign.
fn num_before() -> String {
    format!(r"(?<![\w.,:/{QUOTES}\-−+])")
}

/// `re.search(pat, s)` with its groups.
fn cap<'t>(pat: &str, s: &'t str) -> Option<Captures<'t, str>> {
    let r = rx(pat);
    if !r.may_match(s) {
        return None;
    }
    r.captures(s).ok().flatten()
}

fn set(words: &'static str) -> HashSet<&'static str> {
    words.split_whitespace().collect()
}

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.start())
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

fn n_chars(s: &str) -> usize {
    s.chars().count()
}

// ------------------------------------------------------------------------------------------------- number words

const TENS: &str = "עשרים|שלושים|ארבעים|חמישים|שישים|שבעים|שמונים|תשעים";
/// The grammar's feminine (counting) unit words -> masculine.
const UNIT_M: &[(&str, &str)] = &[
    ("אחת", "אחד"),
    ("שתיים", "שניים"),
    ("שלוש", "שלושה"),
    ("ארבע", "ארבעה"),
    ("חמש", "חמישה"),
    ("שש", "שישה"),
    ("שבע", "שבעה"),
    ("שמונה", "שמונה"),
    ("תשע", "תשעה"),
    ("עשר", "עשרה"),
];
/// The first word of a feminine teen (… עשרה) -> masculine (… עשר).
const TEEN_M: &[(&str, &str)] = &[
    ("אחת", "אחד"),
    ("שתים", "שנים"),
    ("שלוש", "שלושה"),
    ("ארבע", "ארבעה"),
    ("חמש", "חמישה"),
    ("שש", "שישה"),
    ("שבע", "שבעה"),
    ("שמונה", "שמונה"),
    ("תשע", "תשעה"),
];
/// Masculine 3–10 -> the construct form before a definite noun (שלושת הימים).
const CONSTRUCT_M: &[(&str, &str)] = &[
    ("שלושה", "שלושת"),
    ("ארבעה", "ארבעת"),
    ("חמישה", "חמשת"),
    ("שישה", "ששת"),
    ("שבעה", "שבעת"),
    ("שמונה", "שמונת"),
    ("תשעה", "תשעת"),
    ("עשרה", "עשרת"),
];

fn lookup(table: &[(&'static str, &'static str)], k: &str) -> Option<&'static str> {
    table.iter().find(|(a, _)| *a == k).map(|(_, b)| *b)
}

static NUMBER_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    let mut s: HashSet<&'static str> = HashSet::new();
    for t in [UNIT_M, TEEN_M] {
        for (a, b) in t {
            s.insert(a);
            s.insert(b);
        }
    }
    for (_, b) in CONSTRUCT_M {
        s.insert(b);
    }
    s.extend(TENS.split('|'));
    s.extend(["עשרה", "שני", "שתי", "מאה", "מאתיים", "מאות", "אלף", "אלפיים", "אלפים", "מיליון", "מיליארד", "חצות"]);
    s
});

/// The grammar says ו before the tens and before the units (תשע מאות וארבעים ושמונה); Hebrew says it only before the
/// last element (תשע מאות ארבעים ושמונה). Applied to the words these rules write.
fn std_(s: &str) -> String {
    super::super::sub_plain(&rx(&format!(r"ו({TENS}) (?=ו)")), s, |m| Some(tpl(m, r"\1 ")))
}

fn strip_vav(w: &str) -> (&'static str, &str) {
    if let Some(rest) = w.strip_prefix('ו')
        && !rest.is_empty()
        && NUMBER_WORDS.contains(rest)
    {
        return ("ו", rest);
    }
    ("", w)
}

/// The grammar's reading `s` of the integer `n` (the feminine counting form) in the form a noun of `gender` needs.
fn gender_form(s: &str, n: u128, gender: char, construct: bool, before_noun: bool) -> String {
    let mut toks: Vec<String> = s.split_whitespace().map(str::to_string).collect();
    let k = toks.len();
    if gender == 'm' {
        if k >= 2 && toks[k - 1] == "עשרה" && lookup(TEEN_M, strip_vav(&toks[k - 2]).1).is_some() {
            let (v, w) = strip_vav(&toks[k - 2]);
            let new = format!("{v}{}", lookup(TEEN_M, w).unwrap_or(w));
            toks[k - 2] = new;
            toks[k - 1] = "עשר".to_string();
        } else if k >= 1 && lookup(UNIT_M, strip_vav(&toks[k - 1]).1).is_some() {
            let (v, w) = strip_vav(&toks[k - 1]);
            let new = format!("{v}{}", lookup(UNIT_M, w).unwrap_or(w));
            toks[k - 1] = new;
        }
        if construct
            && toks.len() == 1
            && let Some(c) = lookup(CONSTRUCT_M, &toks[0])
        {
            toks[0] = c.to_string();
        }
    }
    if n == 2 && before_noun && toks.len() == 1 {
        toks[0] = if gender == 'm' { "שני" } else { "שתי" }.to_string();
    }
    toks.join(" ")
}

// ------------------------------------------------------------------------------------------------- noun gender

static M_NOUNS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("ימים ימי שבועות שבועות חודשים חודשי לילות רגעים ילדים אנשים איש תלמידים סטודנטים עובדים חיילים
שחקנים אורחים משתתפים נוסעים הרוגים פצועים תושבים מורים רופאים בנים אחים חברים נכדים גברים זוגות מתנדבים לקוחות
מנהלים שוטרים קורבנות שקלים שקל דולרים דולר אירו יורו אחוז אחוזים קילו קילוגרם קילוגרמים גרם גרמים מטר מטרים
קילומטר קילומטרים סנטימטר סנטימטרים מילימטר ליטר ליטרים טון דונם ספרים בתים חדרים מקומות שולחנות כיסאות חלונות
קולות דורות כוחות רחובות מכתבים טלפונים מחשבים אוטובוסים רכבים מטוסים שירים סרטים פרקים עמודים דפים שלבים צעדים
סעיפים פריטים מוצרים מקרים ניסיונות פתרונות רעיונות יתרונות חשבונות שמות חלומות משחקים שערים פרסים עצים פרחים
תפוחים כלבים חתולים סוסים בקבוקים ארגזים מכשירים קבצים דברים כלים אירועים מאמרים שיעורים קורסים תפקידים אתרים
אבות ארונות עפרונות זיכרונות ניצחונות חובות אוצרות מוסדות קירות אורות סודות יסודות הרוגים הסכמים הבדלים הישגים
הליכים היבטים מהנדסים מהלכים בקבוקי ילדי אנשי חברי עובדי תלמידי חיילי בתי ספרי כרטיסי")
});
static F_NOUNS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("שנים שנות שעות דקות שניות פעמים ביצים מילים ערים נשים אבנים כוסות כפות כפיות נקודות מדינות מעלות
בנות ילדות אחיות תלמידות חברות משפחות שיחות הודעות תמונות מכוניות דירות קומות שורות שאלות תשובות טעויות אפשרויות
מנות פרוסות חתיכות שקיות חבילות קופסאות עגבניות ספינות אגורות מכונות שכונות עונות הצגות הרצאות הזמנות הנחות
החלטות הצעות הערות")
});
/// Words after a number that are not counted nouns, though they look like plurals (cities, names, adverbs).
static NOT_NOUNS: LazyLock<HashSet<&'static str>> =
    LazyLock::new(|| set("ירושלים מצרים חיים אפרים גבעתיים נהריים מים שמים שמיים פנים אלוהים לפעמים"));
/// Plural adjectives after a number (“3 נוספים”): they agree, but 2 keeps its absolute form (שניים נוספים).
static ADJECTIVES: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("נוספים נוספות אחרים אחרות חדשים חדשות שלמים שלמות ראשונים ראשונות אחרונים אחרונות רצופים רצופות
שונים שונות")
});
/// The units the grammar's measure words expand to that are feminine; the others are masculine.
static F_UNITS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set("שעות שעה דקות דקה שניות שנייה מעלות מעלה"));
const M_UNIT: &str =
    r"(?:קילו|מגה|גיגה|טרה|מילי|מיקרו|סנטי|ננו)?(?:מטר|גרם|ליטר|בייט|ביט|וואט|אמפר|הרץ|טון|מיל|אחוז|דונם)\w*";
/// The word before a number that makes it a label, not a count (פרק 3, קו 5, רחוב 12).
static LABELS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("פרק סעיף עמוד עמ׳ עמ' מספר מס׳ מס' קו כביש רחוב רח׳ רח' שדרות שד׳ דרך חדר דירה קומה בית שער רציף טור
כיתה גרסה שנת שנה גיליון כרך")
});

/// (gender, kind) of a word after a number: kind is "noun", "def", "part", "adj" or "guess"; None when nothing
/// vouches for a counted noun.
fn noun_gender(w: &str) -> Option<(char, &'static str)> {
    if super::shared::is_op_word("he", w) {
        return None; // 2 פחות 7 שווה: an equation, not a count
    }
    if ADJECTIVES.contains(w) {
        return Some((if w.ends_with("ים") { 'm' } else { 'f' }, "adj"));
    }
    if NOT_NOUNS.contains(w) {
        return None;
    }
    for (pre, kind) in [("", "noun"), ("ה", "def"), ("מה", "part")] {
        if let Some(x) = w.strip_prefix(pre)
            && !NOT_NOUNS.contains(x)
            && (M_NOUNS.contains(x) || F_NOUNS.contains(x))
        {
            return Some((if M_NOUNS.contains(x) { 'm' } else { 'f' }, kind));
        }
    }
    let kind = if w.starts_with('ה') || w.starts_with("מה") { "guess" } else { "noun" };
    if n_chars(w) >= 4 && w.ends_with("ים") && !w.ends_with("יים") {
        return Some(('m', kind));
    }
    if n_chars(w) >= 4 && w.ends_with("ות") {
        return Some(('f', kind));
    }
    None
}

/// The word before offset `i` (with its proclitics: בפרק, ברחוב) is a label word.
fn label_before(t: &str, i: usize) -> bool {
    let Some(m) = cap(r"(\S+)\s+$", super::super::chars_before(t, i, 80)) else { return false };
    let w = g(&m, 1);
    if LABELS.contains(w) {
        return true;
    }
    let stripped = super::super::sub_plain(&rx(r"^[ובכלמשה]{1,2}(?=\S{3})"), w, |_| Some(String::new()));
    LABELS.contains(stripped.as_str())
}

// ------------------------------------------------------------------------------------------------- rules

const ABBREV: &[(&str, &str)] = &[
    ("רח", "רחוב"),
    ("שד", "שדרות"),
    ("ת״ד", "תא דואר"),
    ("רו״ח", "רואה חשבון"),
    ("לפנה״ס", "לפני הספירה"),
    ("לספה״נ", "לספירת הנוצרים"),
];

fn he_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w{QUOTES}])([ובכלמש]{{0,2}})(רח|שד)[׳'](?= \S)")), &t, |m| {
        Some(format!("{}{}", g(m, 1), lookup(ABBREV, g(m, 2))?))
    });
    c.sub(
        &rx(&format!(r"(?<![\w{QUOTES}])([ובכלמש]{{0,2}})(ת|רו|לפנה|לספה){GERSHAYIM}(ד|ח|ס|נ)(?![\w{QUOTES}])")),
        &t,
        |m| {
            let key = format!("{}״{}", g(m, 2), g(m, 3));
            Some(format!("{}{}", g(m, 1), lookup(ABBREV, &key)?))
        },
    )
}

const LETTER_NAMES: &[(char, &str)] = &[
    ('א', "אלף"),
    ('ב', "בית"),
    ('ג', "גימל"),
    ('ד', "דלת"),
    ('ה', "הא"),
    ('ו', "וו"),
    ('ז', "זין"),
    ('ח', "חית"),
    ('ט', "טית"),
    ('י', "יוד"),
    ('כ', "כף"),
    ('ל', "למד"),
    ('מ', "מם"),
    ('נ', "נון"),
    ('ס', "סמך"),
    ('ע', "עין"),
    ('פ', "פא"),
    ('צ', "צדי"),
    ('ק', "קוף"),
    ('ר', "ריש"),
    ('ש', "שין"),
    ('ת', "תו"),
    ('ך', "כף"),
    ('ם', "מם"),
    ('ן', "נון"),
    ('ף', "פא"),
    ('ץ', "צדי"),
];
const NUMERAL_CUE: &str =
    "פרק|סעיף|תת-סעיף|כיתה|כיתת|חלק|כרך|נספח|פסקה|סימן|דף|עמוד|עמ׳|עמ'|שלב|פסוק|משנה|הלכה|מדור|שער|אגף|בניין|תא";

fn he_letter_numeral(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?<!\w)((?:[ובכלמש]{{0,2}}ה?)(?:{NUMERAL_CUE}) )(?:([א-י]|[כלמנסעפצקרשת])[׳']|([א-ת]{{1,2}}){GERSHAYIM}([א-ת]))(?![\w{QUOTES}])"
    );
    c.sub(&rx(&pat), &t, |m| {
        let letters = if m.get(2).is_some() { g(m, 2).to_string() } else { format!("{}{}", g(m, 3), g(m, 4)) };
        let names: Vec<&str> =
            letters.chars().map(|x| LETTER_NAMES.iter().find(|(k, _)| *k == x).map_or("", |(_, v)| *v)).collect();
        Some(format!("{}{}", g(m, 1), names.join(" ")))
    })
}

fn he_latin_number(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w])([A-Za-z]{2,})( ?)(\d+(?:[.,:/]\d+)*)"), &t, |m| {
        let w = g(m, 1);
        let vowel = w.chars().any(|ch| "aeiouyAEIOUY".contains(ch));
        let mixed = w.chars().any(|ch| ch.is_ascii_lowercase()) && w.chars().any(|ch| ch.is_ascii_uppercase());
        if !vowel || !(n_chars(w) >= 4 || mixed) {
            return None;
        }
        if words(g(m, 0), "he").contains(w) {
            return None; // the grammar keeps the name here (iOS 17.4.1 is read as a version)
        }
        Some(format!("\u{e000}{w}\u{e001} {}", g(m, 3)))
    })
}

fn he_time(t: String, c: &mut Ctx) -> String {
    fn one(h: &str, mm: &str) -> String {
        let hw = words(&format!("{}:00", py_int(h)), "he");
        if mm == "00" { hw } else { format!("{hw} ו{}", words(&py_int(mm).to_string(), "he")) }
    }
    let nb = num_before();
    let t = c.sub(
        &rx(&format!(r"{nb}{PRE}([01]?\d|2[0-3]):([0-5]\d) ?[-–] ?([01]?\d|2[0-3]):([0-5]\d)(?![\d:])")),
        &t,
        |m| Some(format!("{}{} עד {}", g(m, 1), one(g(m, 2), g(m, 3)), one(g(m, 4), g(m, 5)))),
    );
    c.sub(
        &rx(&format!(r"{nb}(?<![-–] ){PRE}([01]?\d|2[0-3]):([0-5]\d)(?![\d:]|\.\d| ?[-–] ?\d| ?[A-Za-z])")),
        &t,
        |m| {
            if g(m, 3) == "00" && g(m, 1).is_empty() {
                return None;
            }
            Some(format!("{}{}", g(m, 1), one(g(m, 2), g(m, 3))))
        },
    )
}

fn he_decade(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w])([ובכלמש]{1,3})(שנות ה[-־]?\d+)(?!\d|[.,:/]\d)"), &t, |m| {
        let w = words(g(m, 2), "he");
        if w == g(m, 2) { None } else { Some(format!("{}{w}", g(m, 1))) }
    })
}

fn scale_of(w: &str) -> u128 {
    match w {
        "אלף" => 1000,
        "מיליון" => 1_000_000,
        _ => 1_000_000_000,
    }
}

fn he_gender(t: String, c: &mut Ctx) -> String {
    fn num(s: &str) -> u128 {
        py_int(&s.replace(',', ""))
    }
    let nb = num_before();
    let t =
        c.sub(&rx(&format!(r"{nb}{PRE}(\d{{1,3}}) (אלף|מיליון|מיליארד)(?![\w{QUOTES}])")), &t, |m| {
            let n = num(g(m, 2));
            if n == 0 || n >= 1000 || label_before(&t, start(m)) {
                return None;
            }
            let new = words(&(n * scale_of(g(m, 3))).to_string(), "he");
            if g(m, 1).is_empty() && new == words(&format!("{} {}", g(m, 2), g(m, 3)), "he") {
                return None;
            }
            Some(format!("{}{}", g(m, 1), std_(&new)))
        });

    let t =
        c.sub(&rx(&format!(r"{nb}{PRE}(\d+)( ?[-–] ?| עד | או )(\d+) ([^\W\d_]+)(?![\w{QUOTES}])")), &t, |m| {
            let (gender, kind) = noun_gender(g(m, 5))?;
            if kind == "guess" || label_before(&t, start(m)) {
                return None;
            }
            let (a, b) = (num(g(m, 2)), num(g(m, 4)));
            let x = gender_form(&words(g(m, 2), "he"), a, gender, kind == "def", false);
            let y = gender_form(&words(g(m, 4), "he"), b, gender, kind == "def", kind == "noun" || kind == "def");
            let sep = g(m, 3).trim();
            let joint = if sep == "-" || sep == "–" { "עד" } else { sep };
            Some(format!("{}{} {joint} {} {}", g(m, 1), std_(&x), std_(&y), g(m, 5)))
        });

    c.sub(
        &rx(&format!(r"{nb}{PRE}(\d{{1,3}}(?:,\d{{3}})+|\d+)(?!\d|[.,:/]\d)( ?)([^\s\d.,;:!?()\[\]\-–/+=]+)")),
        &t,
        |m| {
            let n = num(g(m, 2));
            if n < 2 || label_before(&t, start(m)) {
                return None;
            }
            let base = words(g(m, 2), "he");
            let (sp, tok) = (g(m, 3), g(m, 4));
            let w = words(&format!("{}{sp}{tok}", g(m, 2)), "he");
            let out = if w == format!("{base}{sp}{tok}") {
                // a word the grammar passes through: a noun or not
                if sp.is_empty() {
                    return None;
                }
                let (gender, kind) = noun_gender(tok)?;
                if n == 2 && (kind == "guess" || g(m, 1).ends_with('ה')) {
                    return None; // ה-2 before a noun is neither שני nor שניים
                }
                let new = gender_form(&base, n, gender, kind == "def", kind == "noun" || kind == "def");
                if new == base && g(m, 1).is_empty() {
                    return None; // (with a proclitic the number is written out even when its form is right)
                }
                format!("{} {tok}", std_(&new))
            } else {
                // a unit or symbol the grammar expands (ק״ג → קילוגרם, דק׳ → דקות)
                let k = base.split_whitespace().count();
                let ws: Vec<&str> = w.split_whitespace().collect();
                if ws.len() <= k || !ws[..k].iter().all(|x| NUMBER_WORDS.contains(strip_vav(x).1)) {
                    return None;
                }
                let unit = ws[k].trim_end_matches(|ch| ".,;:!?".contains(ch));
                let gender = if F_UNITS.contains(unit) {
                    'f'
                } else if full(M_UNIT, unit) {
                    'm'
                } else {
                    return None;
                };
                let new = gender_form(&base, n, gender, false, true);
                if new == ws[..k].join(" ") && g(m, 1).is_empty() {
                    return None;
                }
                format!("{} {}", std_(&new), ws[k..].join(" "))
            };
            Some(format!("{}{out}", g(m, 1)))
        },
    )
}

const ORD_F: [&str; 10] =
    ["ראשונה", "שנייה", "שלישית", "רביעית", "חמישית", "שישית", "שביעית", "שמינית", "תשיעית", "עשירית"];
/// Feminine nouns without a feminine ending, and masculine nouns with one (for the noun before an ordinal).
static F_SINGULAR: LazyLock<HashSet<&'static str>> =
    LazyLock::new(|| set("פעם עיר ארץ דרך יד רגל כוס עין אוזן נפש אבן חרב בטן ציפור שמש"));
static M_SINGULAR: LazyLock<HashSet<&'static str>> =
    LazyLock::new(|| set("לילה מקרה מחנה שדה מעשה מבנה מורה מראה פה בית שירות צוות מוות זית תות קו"));

/// `w` and `w` without its proclitics (1–2 of ו ב כ ל מ ש, then ה): the forms to look up in a table.
fn strips(w: &str) -> Vec<String> {
    let ch: Vec<char> = w.chars().collect();
    let mut out = vec![w.to_string()];
    for k in [1usize, 2] {
        if ch.len() > k + 1 && ch[..k].iter().all(|x| "ובכלמש".contains(*x)) {
            out.push(ch[k..].iter().collect());
            if ch[k] == 'ה' && ch.len() > k + 2 {
                out.push(ch[k + 1..].iter().collect());
            }
        }
    }
    if ch.first() == Some(&'ה') && ch.len() > 2 {
        out.push(ch[1..].iter().collect());
    }
    out
}

/// The gender of the (singular) noun before an ordinal: the exception tables, then the ending -ה/-ת.
fn singular_gender(w: &str) -> char {
    let xs = strips(w);
    if xs.iter().any(|x| F_SINGULAR.contains(x.as_str())) {
        return 'f';
    }
    if xs.iter().any(|x| M_SINGULAR.contains(x.as_str())) {
        return 'm';
    }
    if n_chars(w) >= 3 && (w.ends_with('ה') || w.ends_with('ת')) { 'f' } else { 'm' }
}

fn he_ordinal(t: String, c: &mut Ctx) -> String {
    let nb = num_before();
    c.sub(&rx(&format!(r"{nb}([ובכלמש]{{0,2}})ה[-־](\d+)(?![\d.,:/]\d|\d|\s?%)")), &t, |m| {
        let n = py_int(g(m, 2));
        if n == 0 || n > 999 {
            return None;
        }
        let mut gender = 'm';
        if let Some(b) = cap(r"(?:(\S+)\s+)?(\S+)\s+$", super::super::chars_before(&t, start(m), 80)) {
            let prev = g(&b, 2);
            let stripped =
                super::super::sub_plain(&rx(r"^[ובכלמש]{1,3}(?=שנות$)"), prev, |_| Some(String::new()));
            if prev == "שנות" || stripped == "שנות" {
                return None;
            }
            gender = singular_gender(prev);
            let head = g(&b, 1);
            if !head.is_empty()
                && prev.starts_with('ה')
                && full(r"[^\W\d_]{2,}ת", head)
                && !head.starts_with('ה')
                && !strips(head).iter().any(|x| M_SINGULAR.contains(x.as_str()))
            {
                gender = 'f'; // מלחמת העולם ה-2: the ordinal agrees with the construct head
            }
        }
        let pre = g(m, 1);
        if n <= 10 {
            if gender == 'm' {
                return None;
            }
            return Some(format!("{pre}ה{}", ORD_F[(n - 1) as usize]));
        }
        Some(format!("{pre}ה{}", std_(&gender_form(&words(&n.to_string(), "he"), n, gender, false, false))))
    })
}

fn he_proclitic(t: String, c: &mut Ctx) -> String {
    let nb = num_before();
    c.sub(&rx(&format!(r"{nb}([ובכלמשה]{{1,3}})[-־]?([$€£₪]?\d+(?:[.,:/]\d+)*%?)")), &t, |m| {
        let (p, num) = (g(m, 1), g(m, 2));
        if p == "ה" {
            return None;
        }
        if let Some(outer) = p.strip_suffix('ה') {
            // וה-3: the grammar reads ה-3; split off the outer letters
            return Some(format!("{outer}\u{e000}\u{e001}ה-{num}"));
        }
        let rest = &t[end(m)..];
        let alone = words(num, "he");
        if let Some(nxt) = cap(r"^(?:( ?)([^\s.,;:!?()]+))", rest)
            && words(&format!("{num}{}", g(&nxt, 0)), "he")
                != format!("{alone}{}{}", g(&nxt, 1), words(g(&nxt, 2), "he"))
        {
            return Some(format!("{p}\u{e000}\u{e001}{num}"));
        }
        if alone == num {
            return None;
        }
        Some(format!("{p}{}", std_(&alone)))
    })
}
