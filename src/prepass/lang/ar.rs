//! 'ar' rules: the port of the workbench's `langrules/ar.py` (ids `ar.*`).
//!
//! The Arabic grammar reads 3–10 with ة before every noun and keeps the noun singular, reads الـN (al- with a tatweel)
//! not at all, dates with a cardinal day and a nominative year, says الساعة twice before a clock time and reads م after
//! an hour as metres. These rules write the spoken words for those spans, starting from the grammar's own reading.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ar.proclitic", ar_proclitic),
    ("ar.time", ar_time),
    ("ar.date", ar_date),
    ("ar.al-number", ar_al_number),
    ("ar.money-cents", ar_money_cents),
    ("ar.gender", ar_gender),
];

/// Nothing glued before a number: a letter, a digit, a decimal mark, a sign or an approximation sign (~10 is حوالي).
const NUM_BEFORE: &str = r"(?<![\w.,:/\-−+~≈±<>])";

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

/// `s[:-k]` in characters.
fn drop_last(s: &str, k: usize) -> &str {
    let n = n_chars(s);
    if k >= n {
        return "";
    }
    let cut = s.char_indices().nth(n - k).map_or(s.len(), |(i, _)| i);
    &s[..cut]
}

/// `s[k:]` in characters.
fn drop_first(s: &str, k: usize) -> &str {
    let cut = s.char_indices().nth(k).map_or(s.len(), |(i, _)| i);
    &s[cut..]
}

fn sub_all(pat: &str, s: &str, template: &str) -> String {
    super::super::sub_plain(&rx(pat), s, |m| Some(tpl(m, template)))
}

// ------------------------------------------------------------------------------------------------- number words

/// The grammar's masculine unit words (3–10 with ة, used before masculine nouns) -> the feminine-noun forms.
const UNIT_F: &[(&str, &str)] = &[
    ("واحد", "إحدى"),
    ("اثنان", "اثنتان"),
    ("ثلاثة", "ثلاث"),
    ("أربعة", "أربع"),
    ("اربعة", "أربع"),
    ("خمسة", "خمس"),
    ("ستة", "ست"),
    ("سبعة", "سبع"),
    ("ثمانية", "ثماني"),
    ("تسعة", "تسع"),
    ("عشرة", "عشر"),
];
/// The first word of a masculine teen (… عشر) -> feminine (… عشرة).
const TEEN_F: &[(&str, &str)] = &[
    ("احد", "إحدى"),
    ("أحد", "إحدى"),
    ("اثنا", "اثنتا"),
    ("ثلاثة", "ثلاث"),
    ("أربعة", "أربع"),
    ("اربعة", "أربع"),
    ("خمسة", "خمس"),
    ("ستة", "ست"),
    ("سبعة", "سبع"),
    ("ثمانية", "ثماني"),
    ("تسعة", "تسع"),
];
const TENS: &str = "عشرون|ثلاثون|أربعون|خمسون|ستون|سبعون|ثمانون|تسعون";

fn lookup(table: &[(&'static str, &'static str)], k: &str) -> Option<&'static str> {
    table.iter().find(|(a, _)| *a == k).map(|(_, b)| *b)
}

fn strip_wa(w: &str) -> (&'static str, &str) {
    if n_chars(w) > 2
        && let Some(rest) = w.strip_prefix('و')
        && (lookup(UNIT_F, rest).is_some() || full(TENS, rest))
    {
        return ("و", rest);
    }
    ("", w)
}

/// The grammar's reading `s` of a number (masculine forms) before a feminine noun.
fn feminine(s: &str) -> String {
    let mut toks: Vec<String> = s.split_whitespace().map(str::to_string).collect();
    let k = toks.len();
    if k >= 2 && toks[k - 1] == "عشر" && lookup(TEEN_F, strip_wa(&toks[k - 2]).1).is_some() {
        let (v, w) = strip_wa(&toks[k - 2]);
        let new = format!("{v}{}", lookup(TEEN_F, w).unwrap_or(w));
        toks[k - 2] = new;
        toks[k - 1] = "عشرة".to_string();
        return toks.join(" ");
    }
    let tens_pat = format!("و(?:{TENS})");
    for i in 0..k {
        let (v, w) = strip_wa(&toks[i]);
        let Some(fem) = lookup(UNIT_F, w) else { continue };
        let last = i == k - 1;
        let before_tens = !last && full(&tens_pat, &toks[i + 1]);
        let new = if before_tens {
            format!("{v}{fem}")
        } else if last {
            format!("{v}{}", if w == "واحد" { "واحدة" } else { fem })
        } else {
            continue;
        };
        toks[i] = new;
    }
    toks.join(" ")
}

/// Nominative number words -> the oblique forms speakers use after a preposition and in dates.
fn oblique(s: &str) -> String {
    let s = sub_all(r"(?<!\w)(و?(?:ال)?)(عشر|ثلاث|أربع|خمس|ست|سبع|ثمان|تسع)ون(?!\w)", s, r"\1\2ين");
    let s = sub_all(r"(?<!\w)(و?(?:ال)?)(ألف|مئت|اثنت|اثن|مليون|مليار)ان(?!\w)", &s, r"\1\2ين");
    sub_all(r"(?<!\w)(و?(?:ال)?)(اثنت|اثن)ا(?= عشر)", &s, r"\1\2ي")
}

/// A number ending in a dual before its noun drops the ن: مئتان دولار -> مئتي دولار.
fn construct(s: &str) -> String {
    sub_all(r"(?<!\w)(و?)(مئت|ألف|مليون|مليار)ان$", s, r"\1\2ي")
}

const ORD_M: [&str; 10] =
    ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع", "الثامن", "التاسع", "العاشر"];
const ORD_F: [&str; 10] =
    ["الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة", "السادسة", "السابعة", "الثامنة", "التاسعة", "العاشرة"];
const TENS_DEF: [&str; 8] = ["العشرون", "الثلاثون", "الأربعون", "الخمسون", "الستون", "السبعون", "الثمانون", "التسعون"];

/// The ordinal of 1–100 with the article, feminine or masculine, nominative or oblique.
fn ordinal(n: u128, fem: bool, obl: bool) -> String {
    if n == 100 {
        return "المائة".to_string();
    }
    let units = if fem { ORD_F } else { ORD_M };
    let n = n as usize;
    if n <= 10 {
        return units[n - 1].to_string();
    }
    let u = n % 10;
    let one = if u == 1 {
        if fem { "الحادية" } else { "الحادي" }
    } else if u > 0 {
        units[u - 1]
    } else {
        ""
    };
    if n < 20 {
        return format!("{one} {}", if fem { "عشرة" } else { "عشر" });
    }
    let mut tens = TENS_DEF[n / 10 - 2].to_string();
    if obl {
        tens = format!("{}ين", drop_last(&tens, 2));
    }
    if u == 0 { tens } else { format!("{one} و{tens}") }
}

/// Number words with the article on each part, as before a counted noun.
fn definite(s: &str) -> String {
    let toks: Vec<&str> = s.split_whitespace().collect();
    let mut out = Vec::new();
    for (i, tok) in toks.iter().enumerate() {
        if (*tok == "عشرة" || *tok == "عشر") && i > 0 {
            out.push(tok.to_string());
        } else if tok.starts_with('و') && n_chars(tok) > 2 {
            out.push(format!("وال{}", drop_first(tok, 1)));
        } else {
            out.push(format!("ال{tok}"));
        }
    }
    out.join(" ")
}

// ------------------------------------------------------------------------------------------------- nouns

/// Counted nouns and units: gender and the plural after 3–10.
const NOUNS: &[(&str, char, &str)] = &[
    ("دولار", 'm', "دولارات"),
    ("جنيه", 'm', "جنيهات"),
    ("ريال", 'm', "ريالات"),
    ("درهم", 'm', "دراهم"),
    ("دينار", 'm', "دنانير"),
    ("ليرة", 'f', "ليرات"),
    ("روبية", 'f', "روبيات"),
    ("فرنك", 'm', "فرنكات"),
    ("كيلومتر", 'm', "كيلومترات"),
    ("متر", 'm', "أمتار"),
    ("سنتيمتر", 'm', "سنتيمترات"),
    ("مليمتر", 'm', "مليمترات"),
    ("كيلوغرام", 'm', "كيلوغرامات"),
    ("غرام", 'm', "غرامات"),
    ("لتر", 'm', "لترات"),
    ("طن", 'm', "أطنان"),
    ("ميل", 'm', "أميال"),
    ("درجة", 'f', "درجات"),
    ("ساعة", 'f', "ساعات"),
    ("دقيقة", 'f', "دقائق"),
    ("ثانية", 'f', "ثوان"),
    ("يوم", 'm', "أيام"),
    ("أسبوع", 'm', "أسابيع"),
    ("شهر", 'm', "أشهر"),
    ("سنة", 'f', "سنوات"),
    ("عام", 'm', "أعوام"),
    ("مرة", 'f', "مرات"),
    ("شخص", 'm', "أشخاص"),
    ("سيارة", 'f', "سيارات"),
    ("بيضة", 'f', "بيضات"),
    ("كلمة", 'f', "كلمات"),
    ("صفحة", 'f', "صفحات"),
    ("دولة", 'f', "دول"),
    ("مدينة", 'f', "مدن"),
    ("غرفة", 'f', "غرف"),
];
static F_PLURALS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("سيارات درجات ساعات سنوات سنين مرات بيضات كلمات صفحات دقائق ليال ليالي شركات طالبات غرف مدن دول لغات
قطع حبات ملاعق نقاط جوائز مباريات رحلات محاولات مراحل زيارات أسر عائلات نساء بنات فتيات معلمات سيدات حلقات دورات نسخ
ولايات ركعات جولات شقق بطاقات رسائل قصص خطوات ثوان ليرات روبيات")
});
static M_PLURALS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("أيام أشهر شهور أسابيع أعوام سنتات دولارات جنيهات ريالات دراهم دنانير كيلومترات أمتار كيلوغرامات
غرامات لترات أطنان أميال أشخاص رجال أطفال طلاب كتب أفراد لاعبين أهداف ملايين مليارات آلاف قرون عقود")
});
/// Words ending in ة that are names or not counted nouns.
static NOT_NOUNS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set("خليفة حمزة أسامة طلحة عبيدة"));
/// Prepositions after which a number is in the oblique (genitive).
static PREPS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("في من إلى الى على عن خلال منذ بعد قبل حتى مع بين حوالي حوالى نحو قرابة لمدة مدة غضون طوال حول ضمن دون عبر
لأكثر لأقل أكثر أقل")
});

/// (gender, plural, singular?) of a counted noun after a number; None when nothing vouches for one.
fn noun_info(w: &str) -> Option<(char, Option<&'static str>, bool)> {
    if let Some((_, gender, plural)) = NOUNS.iter().find(|(k, _, _)| *k == w) {
        return Some((*gender, Some(plural), true));
    }
    if F_PLURALS.contains(w) {
        return Some(('f', None, false));
    }
    if M_PLURALS.contains(w) {
        return Some(('m', None, false));
    }
    if n_chars(w) >= 3 && w.ends_with('ة') && !w.starts_with("ال") && !NOT_NOUNS.contains(w) {
        return Some(('f', None, true));
    }
    None
}

/// The word before a number that makes it a label or a year, not a count (عام 2003, رقم 5, غرفة 205, الصفحة 15).
static LABELS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    set("عام سنة رقم صفحة ص مادة فصل جزء شارع طريق غرفة قاعة مبنى بوابة رحلة طابق حلقة موسم إصدار نسخة آية سورة
مقعد خط منصة رمز")
});

/// The word before offset `i` (with ال and its proclitics: في الصفحة, بالغرفة) is a label word.
fn label_before(t: &str, i: usize) -> bool {
    let Some(m) = cap(r"(\S+)\s+$", super::super::chars_before(t, i, 80)) else { return false };
    let w = g(&m, 1);
    LABELS.contains(w) || LABELS.contains(sub_all(r"^[وفبلك]?(?:ال)?", w, "").as_str())
}

/// The word before offset `i` is a preposition.
fn after_prep(t: &str, i: usize) -> bool {
    cap(r"(\S+)\s+$", super::super::chars_before(t, i, 80)).is_some_and(|m| PREPS.contains(g(&m, 1)))
}

fn dual(w: &str) -> String {
    if w.ends_with('ة') { format!("{}تان", drop_last(w, 1)) } else { format!("{w}ان") }
}

// ------------------------------------------------------------------------------------------------- rules

fn ar_proclitic(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w\ue001])([وف][بلك]?|[بلك])ـ*(?=\d)"), &t, |m| {
        Some(format!("{}\u{e000}\u{e001}", g(m, 1)))
    })
}

const HOUR_WORDS: &str =
    r"(صباحًا|صباحاً|صباحا|مساءً|مساءا|مساء|ظهرًا|ظهراً|ظهرا|ليلًا|ليلاً|ليلا|فجرًا|فجراً|فجرا|عصرًا|عصراً|عصرا)";

fn ar_time(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<!\w)الساعة (?=\d{1,2}:\d{2}(?!\d))"), &t, "");
    let has_am = search(r"(?<![\d.,:])(?:[1-9]|1[0-2]) ?ص(?!\w)", &t);
    let t = c.sub(&rx(r"(?<![\w.,:/])(الساعة )?(\d{1,2}) ?(ص|م)(?!\w)"), &t, |m| {
        let h = py_int(g(m, 2));
        if !(1..=12).contains(&h) || (g(m, 3) == "م" && !(m.get(1).is_some() || has_am)) {
            return None;
        }
        Some(format!("{}{}{}", g(m, 1), ordinal(h, true, false), if g(m, 3) == "ص" { " صباحا" } else { " مساء" }))
    });
    let t = c.sub(&rx(r"(?<!\w)(الساعة )(\d{1,2})(?!\d|[.,:/]\d| ?[%°])( |$|[.,;!?])"), &t, |m| {
        let h = py_int(g(m, 2));
        if !(1..=12).contains(&h) {
            return None;
        }
        Some(format!("{}{}{}", g(m, 1), ordinal(h, true, false), g(m, 3)))
    });
    let t = c.sub(&rx(&format!(r"(?<![\w.,:/])(\d{{1,2}}) {HOUR_WORDS}(?!\w)")), &t, |m| {
        let h = py_int(g(m, 1));
        if !(1..=12).contains(&h) {
            return None;
        }
        Some(format!("{} {}", ordinal(h, true, false), g(m, 2)))
    });
    c.sub_tpl(&rx(r"(?<!\w)((?:عام|سنة|العام|السنة|لعام|بعام) \d{3,4}) ?م(?!\w)"), &t, r"\1 ميلادي")
}

const GREG: [&str; 12] =
    ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
const MONTHS_MORE: [&str; 28] = [
    "إبريل",
    "يونيه",
    "يوليه",
    "كانون الثاني",
    "شباط",
    "آذار",
    "نيسان",
    "أيار",
    "حزيران",
    "تموز",
    "آب",
    "أيلول",
    "تشرين الأول",
    "تشرين الثاني",
    "كانون الأول",
    "محرم",
    "ربيع الأول",
    "ربيع الآخر",
    "ربيع الثاني",
    "جمادى الأولى",
    "جمادى الآخرة",
    "جمادى الثانية",
    "رجب",
    "شعبان",
    "رمضان",
    "شوال",
    "ذو القعدة",
    "ذو الحجة",
];

/// The month names, longest first, ties in table order (Python's stable sort).
static MONTH_RX: LazyLock<String> = LazyLock::new(|| {
    let mut all: Vec<&str> = GREG.iter().chain(MONTHS_MORE.iter()).copied().collect();
    all.sort_by_key(|s| std::cmp::Reverse(n_chars(s)));
    all.join("|")
});

fn ar_date(t: String, c: &mut Ctx) -> String {
    fn year(y: &str, era: &str) -> String {
        let w = oblique(&words(&py_int(y).to_string(), "ar"));
        let suffix = if era.is_empty() {
            ""
        } else if era.trim() == "هـ" {
            " هجري"
        } else {
            " ميلادي"
        };
        format!("{w}{suffix}")
    }
    fn numeric(d: &str, mo: &str, y: &str, era: &str) -> Option<String> {
        let (d, mo) = (py_int(d), py_int(mo));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) {
            return None;
        }
        Some(format!("{} من {} {}", ordinal(d, false, true), GREG[(mo - 1) as usize], year(y, era)))
    }
    let era = r"( ?هـ| ?م(?!\w))?";
    let t =
        c.sub(&rx(&format!(r"(?<![\d/.\-])(\d{{1,2}})([/.\-])(\d{{1,2}})\2(\d{{4}})(?![\d/.\-]\d){era}")), &t, |m| {
            numeric(g(m, 1), g(m, 3), g(m, 4), g(m, 5))
        });
    let t = c.sub(&rx(&format!(r"(?<![\d/.\-])(\d{{4}})-(\d{{1,2}})-(\d{{1,2}})(?![\d/.\-]\d){era}")), &t, |m| {
        numeric(g(m, 3), g(m, 2), g(m, 1), g(m, 4))
    });
    let pat = format!(r"(?<![\w.,:/])(\d{{1,2}}) ({})(?!\w)(?: (\d{{3,4}})(?![\d.,:/]\d){era})?", *MONTH_RX);
    c.sub(&rx(&pat), &t, |m| {
        let d = py_int(g(m, 1));
        if !(1..=31).contains(&d) {
            return None;
        }
        let out = format!("{} من {}", ordinal(d, false, true), g(m, 2));
        if m.get(3).is_some() { Some(format!("{out} {}", year(g(m, 3), g(m, 4)))) } else { Some(out) }
    })
}

fn ar_al_number(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<!\w)([وف]?[بك]?ال|[وف]?لل)(?:ـ+ ?|(?=\d))(\d+)(?!\d|[.,:/]\d)"), &t, |m| {
        let (pre, n) = (g(m, 1), py_int(g(m, 2)));
        if n == 0 || n > 100 {
            return None;
        }
        let info = cap(r"^(?: (\S+))", &t[end(m)..])
            .and_then(|x| noun_info(g(&x, 1).trim_end_matches(|ch| ".,;:!?".contains(ch))));
        let before = cap(r"(?:(\S+)\s+)?(\S+)\s+$", super::super::chars_before(&t, start(m), 80));
        let lil = pre.ends_with("لل");
        let outer = drop_last(pre, 2); // the proclitics before the article (ب, و, وب; لل: ل is the preposition)
        let obl = lil
            || outer.contains('ب')
            || outer.contains('ك')
            || before.as_ref().is_some_and(|b| PREPS.contains(g(b, 2)) || PREPS.contains(g(b, 1)));
        let w = match info {
            Some((gender, _, _)) if n <= 99 => {
                let base = words(&n.to_string(), "ar");
                let w = definite(&if gender == 'f' { feminine(&base) } else { base });
                if obl { oblique(&w) } else { w }
            }
            _ => {
                let prev = before.as_ref().map_or("", |b| g(b, 2));
                ordinal(n, prev.ends_with('ة') && !NOT_NOUNS.contains(prev), obl)
            }
        };
        Some(if lil { format!("{outer}ل{}", drop_first(&w, 1)) } else { format!("{outer}{w}") })
    })
}

fn ar_money_cents(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,])(\d+\.\d{2})(?!\d) (دولار|دولارا|دولارات|يورو)(?!\w)"), &t, |m| {
        Some(format!("{}{}", if g(m, 2) == "يورو" { "€" } else { "$" }, g(m, 1)))
    })
}

fn scale_of(w: &str) -> u128 {
    match w {
        "ألف" => 1000,
        "مليون" => 1_000_000,
        _ => 1_000_000_000,
    }
}

/// A nisba adjective after a currency or unit (دولار أمريكي): it agrees with the dual and the plural.
fn nisba(w: &str) -> bool {
    n_chars(w) >= 4 && w.ends_with('ي') && !w.starts_with("ال") && !["علي", "لدي", "إلي", "حوالي"].contains(&w)
}

fn ar_gender(t: String, c: &mut Ctx) -> String {
    fn num(s: &str) -> u128 {
        py_int(&s.replace(',', ""))
    }
    let t = c.sub(&rx(&format!(r"{NUM_BEFORE}(\d{{1,3}}) (ألف|مليون|مليار)(?!\w)")), &t, |m| {
        let n = num(g(m, 1));
        if n == 0 || n >= 1000 || label_before(&t, start(m)) {
            return None;
        }
        let mut new = words(&(n * scale_of(g(m, 2))).to_string(), "ar");
        let rest = &t[end(m)..];
        if matches_at_start(r" [^\W\d_]", rest) && !matches_at_start(r" (?:و|أو|من|في|إلى|على|أو)(?!\w)", rest)
        {
            new = construct(&new);
        }
        if new == words(g(m, 0), "ar") { None } else { Some(new) }
    });

    let t = c.sub(&rx(&format!(r"{NUM_BEFORE}(\d+) ?[-–] ?(\d+) ([^\W\d_]+)")), &t, |m| {
        let tok = g(m, 3).trim_end_matches(|ch| ".,;:!?".contains(ch));
        let (gender, plural, singular) = noun_info(tok)?;
        if label_before(&t, start(m)) {
            return None;
        }
        let (mut x, mut y) = (words(g(m, 1), "ar"), words(g(m, 2), "ar"));
        if gender == 'f' {
            (x, y) = (feminine(&x), feminine(&y));
        }
        let noun = match plural {
            Some(p) if singular && (3..=10).contains(&(num(g(m, 2)) % 100)) => p,
            _ => tok,
        };
        let lead = if after_prep(&t, start(m)) { "" } else { "من " };
        Some(format!("{lead}{x} إلى {y} {noun}"))
    });

    let pat = format!(
        r"{NUM_BEFORE}(-?)(\d{{1,3}}(?:,\d{{3}})+|\d+)(?!\d|[.,:/]\d)( ?)([^\s\d.,;:!?()\[\]\-–/+=]+(?:\.[^\s\d.,;:!?()\[\]\-–/+=]+)*\.?)(?!/)( [^\W\d_]{{3,}}ي(?!\w))?"
    );
    c.sub(&rx(&pat), &t, |m| {
        let (sign, digits, sp) = (g(m, 1), g(m, 2), g(m, 3));
        let tok = format!("{}{}", g(m, 4), g(m, 5));
        let n = num(digits);
        if n < 2 || label_before(&t, start(m)) {
            return None;
        }
        let base = words(&format!("{sign}{digits}"), "ar");
        let w = words(&format!("{sign}{digits}{sp}{tok}"), "ar");
        let k = base.split_whitespace().count();
        let ws: Vec<&str> = w.split_whitespace().collect();
        // the noun as the grammar reads it: the word itself, or the unit or currency it expands
        if ws.len() <= k || ws[..k].join(" ") != base {
            return None;
        }
        let unit = ws[k..].join(" ");
        let core = unit.trim_end_matches(|ch| ".,;:!?".contains(ch));
        let tail = &unit[core.len()..];
        let parts: Vec<&str> = core.split_whitespace().collect();
        let (&noun, rest) = parts.split_first()?;
        let (gender, plural, singular) = noun_info(noun)?;
        // only nisba adjectives after the noun (not مربع, في الساعة): the plural and the dual need them to agree
        let agree =
            rest.iter().all(|x| nisba(x) || x.ends_with("ية")) && !matches_at_start(r" (?:مربع|مكعب)", &t[end(m)..]);
        if n == 2 {
            if !sign.is_empty() || !singular || !NOUNS.iter().any(|(k, _, _)| *k == noun) || noun == "يورو" || !agree
            {
                return None;
            }
            // the dual replaces the number: كيلومتران, ساعتان, دولاران أمريكيان
            let mut out = vec![dual(noun)];
            for x in rest {
                out.push(if nisba(x) {
                    format!("{x}ان")
                } else if x.ends_with("ية") {
                    format!("{}تان", drop_last(x, 1))
                } else {
                    x.to_string()
                });
            }
            return Some(format!("{}{tail}", out.join(" ")));
        }
        let numw = construct(&if gender == 'f' { feminine(&base) } else { base.clone() });
        let mut words_out: Vec<String> = Vec::new();
        match plural {
            Some(p) if singular && agree && (3..=10).contains(&(n % 100)) => {
                words_out.push(p.to_string());
                words_out.extend(rest.iter().map(|x| if nisba(x) { format!("{x}ة") } else { x.to_string() }));
            }
            _ => {
                words_out.push(noun.to_string());
                words_out.extend(rest.iter().map(|x| x.to_string()));
            }
        }
        let out = format!("{numw} {}{tail}", words_out.join(" "));
        if out == w { None } else { Some(out) }
    })
}
