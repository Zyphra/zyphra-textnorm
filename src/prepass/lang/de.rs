//! 'de' rules: the port of the workbench's `langrules/de.py` (ids `de.*`).
//!
//! Where a rule writes German number words itself it writes them as German does, one word below a million
//! (zweihundertsechsundzwanzig, eine Million zweihunderttausend), not the grammar's spaced form (S35).

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

use fancy_regex::Captures;

use super::super::{Ctx, full, g, matches_at_start, py_int, py_int_str, rx, search};
use super::{LangRule, words};
use crate::text::{is_py_digit, nd_range_start, py_split_ws};

pub(super) const RULES: &[LangRule] = &[
    ("de.abbrev", de_abbrev),
    ("de.roman", de_roman),
    ("de.scale", de_scale),
    ("de.money", de_money),
    ("de.grouped", de_grouped),
    ("de.range", de_range),
    ("de.date", de_date),
    ("de.ordinal", de_ordinal),
    ("de.decade", de_decade),
    ("de.year", de_year),
    ("de.half", de_half),
    ("de.one", de_one),
];

// ------------------------------------------------------------------------------------------------- helpers

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.start())
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

/// Group `i` of `re.match(pat, s)` (anchored at the start), if it matches.
fn group_at_start(pat: &str, s: &str, i: usize) -> Option<String> {
    let r = rx(&format!("^(?:{pat})"));
    match r.captures(s) {
        Ok(Some(m)) => Some(g(&m, i).to_string()),
        _ => None,
    }
}

/// `s[0].upper() + s[1:]`.
fn cap(s: &str) -> String {
    let mut it = s.chars();
    match it.next() {
        Some(f) => f.to_uppercase().collect::<String>() + it.as_str(),
        None => String::new(),
    }
}

fn first_upper(s: &str) -> bool {
    s.chars().next().is_some_and(char::is_uppercase)
}

fn len(s: &str) -> usize {
    s.chars().count()
}

/// `str.isalpha()`.
fn is_alpha(s: &str) -> bool {
    !s.is_empty() && s.chars().all(char::is_alphabetic)
}

/// `str.islower()`.
fn is_lower(s: &str) -> bool {
    s.chars().any(char::is_lowercase) && !s.chars().any(char::is_uppercase)
}

/// `float(s.replace(",", "."))` for a `\d+(,\d+)?` string.
fn num_value(s: &str) -> f64 {
    let ascii: String = s
        .chars()
        .map(|ch| {
            if ch == ',' {
                '.'
            } else if is_py_digit(ch) && !ch.is_ascii_digit() {
                char::from_digit((ch as u32 - nd_range_start(ch).unwrap_or(ch as u32)) % 10, 10).unwrap_or('0')
            } else {
                ch
            }
        })
        .collect();
    ascii.parse().unwrap_or(0.0)
}

fn set(words: &'static str) -> HashSet<&'static str> {
    words.split_whitespace().collect()
}

// ------------------------------------------------------------------------------------------------- number words

const BIG: [&str; 6] = ["million", "millionen", "milliarde", "milliarden", "billion", "billionen"];

/// The grammar's spaced number words as one word below a million: 'zwei hundert sechs und zwanzig' ->
/// 'zweihundertsechsundzwanzig', 'eine million zwei hundert tausend' -> 'eine Million zweihunderttausend'.
fn de_join(s: &str) -> String {
    let mut out: Vec<String> = Vec::new();
    let mut cur = String::new();
    for w in py_split_ws(s) {
        if BIG.contains(&w) {
            if !cur.is_empty() {
                out.push(std::mem::take(&mut cur));
            }
            out.push(cap(w));
        } else {
            cur.push_str(w);
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out.join(" ")
}

/// The cardinal of the digit string n, written as one word below a million.
fn de_num(n: &str) -> String {
    de_join(&words(n, "de"))
}

/// The ordinal stem of n (1 <= n < 1000000): erst, zweit, dritt, zwanzigst, einundzwanzigst, hundertst.
fn de_ord(n: u128) -> String {
    let spoken = words(&n.to_string(), "de");
    let mut ws: Vec<String> = py_split_ws(&spoken).into_iter().map(str::to_string).collect();
    let last = ws.pop().unwrap_or_default();
    let last = match last.as_str() {
        "eins" => "erst".to_string(),
        "drei" => "dritt".to_string(),
        "sieben" => "siebt".to_string(),
        "acht" => "acht".to_string(),
        _ if !n.is_multiple_of(100) && n % 100 < 20 => format!("{last}t"),
        _ => format!("{last}st"),
    };
    ws.push(last);
    let stem = de_join(&ws.join(" "));
    if ((100..200).contains(&n) || (1000..2000).contains(&n)) && stem.starts_with("ein") {
        return stem["ein".len()..].to_string(); // hundertste, tausendste (einhundertste is rare in speech)
    }
    stem
}

/// A year as said: 1100-1999 'neunzehnhundertfünfundvierzig', others as the cardinal (zweitausendvierundzwanzig).
fn year_words(y: u128) -> String {
    if (1100..=1999).contains(&y) {
        let r = if !y.is_multiple_of(100) { de_num(&(y % 100).to_string()) } else { String::new() };
        return format!("{}hundert{}", de_num(&(y / 100).to_string()), r);
    }
    de_num(&y.to_string())
}

/// Up to two words before a position, nearest first, without quotes or brackets around them; '' stands for a
/// sentence start (the text start, a line break, or a token ending in . ! ? :), after which nothing is looked at.
fn prev_words(head: &str) -> Vec<String> {
    let mut out = Vec::new();
    let h = head.replace('\n', " \n ");
    for tok in h.split(' ').rev() {
        if out.len() == 2 {
            return out;
        }
        if tok.is_empty() {
            continue;
        }
        if tok == "\n" || tok.ends_with(['.', '!', '?', ':']) {
            out.push(String::new());
            return out;
        }
        out.push(tok.trim_matches(|ch| "(„\"'»«“”".contains(ch)).to_string());
    }
    out.push(String::new());
    out
}

const END_RX: &str = r"[ \t]*(?:\n|$)"; // the text or the line ends here
const NEXT_CAP_RX: &str = r"\s+[A-ZÄÖÜ]"; // a capitalised word follows

// --------------------------------------------------------------------------------------------- abbreviations (S22)

/// (written form, spoken form, can end a sentence).
const DE_ABBREV: &[(&str, &str, bool)] = &[
    ("z. B.", "zum Beispiel", false),
    ("d. h.", "das heißt", false),
    ("u. a.", "unter anderem", true),
    ("usw.", "und so weiter", true),
    ("usf.", "und so fort", true),
    ("etc.", "et cetera", true),
    ("ca.", "circa", false),
    ("bzw.", "beziehungsweise", false),
    ("ggf.", "gegebenenfalls", false),
    ("vgl.", "vergleiche", false),
    ("inkl.", "inklusive", false),
    ("exkl.", "exklusive", false),
    ("evtl.", "eventuell", false),
    ("bspw.", "beispielsweise", false),
    ("bzgl.", "bezüglich", false),
    ("zzgl.", "zuzüglich", false),
    ("z. T.", "zum Teil", false),
    ("u. U.", "unter Umständen", false),
    ("i. d. R.", "in der Regel", false),
    ("o. Ä.", "oder Ähnliches", true),
    ("o. ä.", "oder ähnlich", true),
    ("u. Ä.", "und Ähnliches", true),
    ("u. ä.", "und ähnlich", true),
    ("s. o.", "siehe oben", true),
    ("s. u.", "siehe unten", true),
    ("u. v. m.", "und vieles mehr", true),
    ("v. a.", "vor allem", false),
    ("insb.", "insbesondere", false),
    ("Jh.", "Jahrhundert", true),
    ("Jhd.", "Jahrhundert", true),
    ("Jhdt.", "Jahrhundert", true),
    ("Str.", "Straße", true),
];

/// 'z. B.' -> '[zZ]\.\s?B\.': the parts with or without the space, the first letter in either case.
fn abbrev_pattern(a: &str) -> String {
    let parts: Vec<&str> = a.split('.').map(str::trim).filter(|p| !p.is_empty()).collect();
    let mut chars = parts[0].chars();
    let f = chars.next().expect("a part");
    let lead = format!("[{}{}]{}", f.to_lowercase(), f.to_uppercase(), chars.as_str());
    let mut ps = vec![lead];
    ps.extend(parts[1..].iter().map(|p| p.to_string()));
    format!(r"{}\.", ps.join(r"\.\s?"))
}

static DE_ABBREV_KEY: LazyLock<HashMap<String, (&'static str, bool)>> =
    LazyLock::new(|| DE_ABBREV.iter().map(|&(a, w, e)| (a.replace(' ', ""), (w, e))).collect());
static DE_ABBREV_RX: LazyLock<String> = LazyLock::new(|| {
    let mut v: Vec<&(&str, &str, bool)> = DE_ABBREV.iter().collect();
    v.sort_by_key(|x| std::cmp::Reverse(len(&x.0.replace(' ', ""))));
    let alt: Vec<String> = v.iter().map(|x| abbrev_pattern(x.0)).collect();
    format!(r"(?<![\w.])({})(?!\w)", alt.join("|"))
});

/// The key with its first letter's case flipped.
fn flip_first(key: &str) -> String {
    let mut it = key.chars();
    match it.next() {
        Some(f) if f.is_uppercase() => f.to_lowercase().collect::<String>() + it.as_str(),
        Some(f) => f.to_uppercase().collect::<String>() + it.as_str(),
        None => String::new(),
    }
}

fn de_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&DE_ABBREV_RX), &t, |m| {
        let s = g(m, 1);
        if s == "z.B." {
            return None;
        }
        let mut key = s.replace(' ', "");
        if !DE_ABBREV_KEY.contains_key(&key) {
            key = flip_first(&key);
        }
        let &(spoken, can_end) = DE_ABBREV_KEY.get(&key)?;
        let mut spoken = if first_upper(s) && !first_upper(&key) { cap(spoken) } else { spoken.to_string() };
        let rest = &t[end(m)..];
        if matches_at_start(END_RX, rest) || (can_end && matches_at_start(NEXT_CAP_RX, rest)) {
            spoken.push('.');
        }
        Some(spoken)
    });
    c.sub(&rx(r"(?<![\w.])([A-ZÄÖÜ][a-zäöüß]{2,})str\.(?!\w)"), &t, |m| {
        let rest = &t[end(m)..];
        let dot = if matches_at_start(END_RX, rest) || matches_at_start(NEXT_CAP_RX, rest) { "." } else { "" };
        Some(format!("{}straße{dot}", g(m, 1)))
    })
}

// ------------------------------------------------------------------------------------------------ Roman numerals (S20)

const ROMAN: &str = r"(?:M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))";
const DE_REGNAL_M: &str = concat!(
    "Ludwig|Friedrich|Wilhelm|Karl|Heinrich|Otto|Konrad|Maximilian|Ferdinand|Leopold|Joseph|Josef|Franz|",
    "Rudolf|Albrecht|Johann|Johannes|Paul|Pius|Benedikt|Leo|Gregor|Clemens|Innozenz|Urban|Bonifatius|",
    "Sixtus|Julius|Alexander|Peter|Iwan|Nikolaus|Georg|Eduard|Richard|Jakob|Philipp|Gustav|Christian|",
    "Harald|Olav|Haakon|Carl|Napoleon|Ramses|Ptolemaios|Konstantin|Lothar|Sigismund|Wenzel|Ruprecht|",
    "August|Ernst|Alfons|Felipe|Carlos|Umberto|Vittorio|Albert|Baudouin|Michael|Stephan|Matthias|",
    "Ladislaus|Kasimir|Wladimir|Pippin|Arnulf|Hugo|Robert|Edward|Henry|Louis|George|Charles|James|",
    "William|John|Frederik|Oskar|Erik|Magnus|Waldemar|Amadeus|Eugen|Hadrian|Honorius|Coelestin|Cölestin|",
    "Viktor|Felix|Sergius|Anastasius|Marcellus|Silvester|Martin|Kalixt|Hirohito|Akihito|Rama|Selim|",
    "Mehmed|Murad"
);
const DE_REGNAL_F: &str = concat!(
    "Elisabeth|Elizabeth|Katharina|Maria|Mary|Victoria|Viktoria|Johanna|Isabella|Margarethe|Margrethe|",
    "Beatrix|Christina|Kristina|Kleopatra|Wilhelmina|Juliana|Anna|Isabel"
);
const DE_TITLES: &str = concat!(
    "Papst|König|Königin|Kaiser|Kaiserin|Zar|Zarin|Herzog|Herzogin|Fürst|Fürstin|Graf|Gräfin|Prinz|",
    "Prinzessin|Kurfürst|Pharao|Sultan|Markgraf|Landgraf|Erzherzog|Erzherzogin|Großherzog|Kalif|Schah"
);
const DE_TITLES_F: [&str; 8] =
    ["Königin", "Kaiserin", "Zarin", "Herzogin", "Fürstin", "Gräfin", "Prinzessin", "Erzherzogin"];
const DE_CARD_CTX: &str = concat!(
    "Kapitel|Teil|Band|Akt|Szene|Staffel|Folge|Phase|Stufe|Abschnitt|Artikel|Anhang|Buch|Psalm|Episode|",
    "Runde|Level|Gruppe|Kategorie|Klasse|Typ"
);
static DATIVE: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("mit von aus bei nach seit zu außer gegenüber samt nebst unter vor in an auf hinter neben zwischen binnen \
         entgegen gemäß zufolge")
});
static ACCUSATIVE: LazyLock<HashSet<&str>> = LazyLock::new(|| set("für durch gegen ohne um bis"));
/// Verbs whose object is an accusative (kostet einen Euro, hat einen Hund).
static ACC_VERBS: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("kostet kosten kostete kosteten zahlt zahle zahlen zahlte zahlten bezahlt bezahle bezahlte verdient verdiene \
         verdiente spart spare sparte gibt gab hat habe hast haben hatte hatten braucht brauche brauchen brauchte \
         kauft kaufe kaufen kaufte bekommt bekomme bekam kriegt nimmt nehme nahm sucht suche findet finde fand sieht \
         sehe sah bestellt bestelle bestellte will möchte wünsche wünscht")
});
static DE_ADVERBS: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("nur noch genau etwa rund knapp mindestens höchstens fast maximal circa bloß lediglich gerade zirka insgesamt \
         auch schon bereits")
});

/// The case a count takes from the word before it (past one adverb: mit nur 1 Klick): dat after a dative
/// preposition, acc after an accusative preposition or verb, else nom.
fn de_case(head: &str) -> &'static str {
    let pw = prev_words(head);
    let w = if DE_ADVERBS.contains(pw[0].to_lowercase().as_str()) && pw.len() > 1 { &pw[1] } else { &pw[0] };
    let w = w.to_lowercase();
    if DATIVE.contains(w.as_str()) {
        return "dat";
    }
    if ACCUSATIVE.contains(w.as_str()) || ACC_VERBS.contains(w.as_str()) {
        return "acc";
    }
    "nom"
}

/// ein/eine/einen/einem/einer for a noun of this gender (m, n, f) in this case.
fn de_one_word(gender: &str, case: &str) -> &'static str {
    if gender == "f" {
        return if case == "dat" { "einer" } else { "eine" };
    }
    if case == "dat" {
        return "einem";
    }
    if gender == "m" && case == "acc" { "einen" } else { "ein" }
}

fn roman_value(ch: char) -> i64 {
    match ch {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        'C' => 100,
        'D' => 500,
        'M' => 1000,
        _ => 0,
    }
}

fn roman_to_int(s: &str) -> u128 {
    let c: Vec<char> = s.chars().collect();
    let mut total: i64 = 0;
    for i in 0..c.len() {
        if i + 1 < c.len() && roman_value(c[i + 1]) > roman_value(c[i]) {
            total -= roman_value(c[i]);
        } else {
            total += roman_value(c[i]);
        }
    }
    total.max(0) as u128
}

/// II, XIV, LX: anything with D or M, and a single C or L, are letters, not numerals; up to 100.
fn plausible(num: &str) -> bool {
    !num.is_empty()
        && !num.contains('D')
        && !num.contains('M')
        && (len(num) > 1 || "IVX".contains(num))
        && roman_to_int(num) <= 100
}

fn de_regnal(m: &Captures<'_, str>, t: &str) -> Option<String> {
    let (title, name, genitive, num, dot) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
    if !plausible(num) {
        return None;
    }
    let fem = DE_TITLES_F.contains(&title.trim()) || full(DE_REGNAL_F, name);
    let prev = prev_words(&t[..start(m)])[0].to_lowercase();
    let case = if !genitive.is_empty() {
        "gen"
    } else if DATIVE.contains(prev.as_str()) {
        "dat"
    } else if ACCUSATIVE.contains(prev.as_str()) {
        "acc"
    } else {
        "nom"
    };
    let (art, ending) = if fem {
        if case == "nom" || case == "acc" { ("die", "e") } else { ("der", "en") }
    } else {
        let art = match case {
            "nom" => "der",
            "acc" => "den",
            "dat" => "dem",
            _ => "des",
        };
        (art, if case == "nom" { "e" } else { "en" })
    };
    let rest = &t[end(m)..];
    let keep = if !dot.is_empty() && (matches_at_start(END_RX, rest) || matches_at_start(NEXT_CAP_RX, rest)) {
        "."
    } else {
        ""
    };
    Some(format!("{title}{name}{genitive} {art} {}{ending}{keep}", cap(&de_ord(roman_to_int(num)))))
}

fn de_roman(t: String, c: &mut Ctx) -> String {
    let names = format!("{DE_REGNAL_M}|{DE_REGNAL_F}");
    let p1 = format!(r"(?<![\w.])((?:{DE_TITLES}) )?({names})(s?) ({ROMAN})(\.?)(?![\w'])");
    let t = c.sub(&rx(&p1), &t, |m| de_regnal(m, &t));
    let p2 = format!(r"(?<![\w.])((?:{DE_TITLES}) )([A-ZÄÖÜ][a-zäöüß]+)(s?) ({ROMAN})(\.?)(?![\w'])");
    let t = c.sub(&rx(&p2), &t, |m| de_regnal(m, &t));
    c.sub(&rx(&format!(r"\b({DE_CARD_CTX}) ({ROMAN})(?![\w'])")), &t, |m| {
        plausible(g(m, 2)).then(|| format!("{} {}", g(m, 1), de_num(&roman_to_int(g(m, 2)).to_string())))
    })
}

// ------------------------------------------------------------------------------------------------- money (S11, S13)

/// (written forms, singular, plural, minor unit or "", gender: m, n or f).
type Currency = (&'static [&'static str], &'static str, &'static str, &'static str, &'static str);
const DE_CURRENCIES: &[Currency] = &[
    (&["€", "EUR"], "Euro", "Euro", "Cent", "m"),
    (&["CHF", "SFr.", "Fr."], "Franken", "Franken", "Rappen", "m"),
    (&["US$", "$", "USD"], "Dollar", "Dollar", "Cent", "m"),
    (&["£", "GBP"], "Pfund", "Pfund", "Pence", "n"),
    (&["¥", "JPY"], "Yen", "Yen", "", "m"),
    (&["₽", "RUB"], "Rubel", "Rubel", "", "m"),
    (&["zł", "PLN"], "Złoty", "Złoty", "", "m"),
    (&["Kč", "CZK"], "Krone", "Kronen", "", "f"),
    (&["SEK"], "schwedische Krone", "schwedische Kronen", "", "f"),
    (&["NOK"], "norwegische Krone", "norwegische Kronen", "", "f"),
    (&["DKK"], "dänische Krone", "dänische Kronen", "", "f"),
    (&["₺", "TRY"], "Lira", "Lira", "", "f"),
    (&["₹", "INR"], "Rupie", "Rupien", "", "f"),
];
static DE_CUR: LazyLock<HashMap<&str, &Currency>> =
    LazyLock::new(|| DE_CURRENCIES.iter().flat_map(|cur| cur.0.iter().map(move |f| (*f, cur))).collect());
/// Longest first (US$ before $, SFr. before Fr.), ties in table order.
static DE_CUR_RX: LazyLock<String> = LazyLock::new(|| {
    let mut forms: Vec<&str> = DE_CURRENCIES.iter().flat_map(|cur| cur.0.iter().copied()).collect();
    forms.sort_by_key(|f| std::cmp::Reverse(len(f)));
    let alt: Vec<String> = forms.iter().map(|f| f.replace('.', r"\.").replace('$', r"\$")).collect();
    format!("({})", alt.join("|"))
});
const AMOUNT: &str = r"([1-9]\d{0,2}(?:\.\d{3})+|\d+)(?:,(\d\d|--?|–))?";

/// The spoken amount: 'eintausendzweihundertvierunddreißig Euro sechsundfünfzig', 'fünfundvierzig Cent'; one
/// takes the case (einen Euro after kostet, mit einem Euro).
fn de_amount(major: &str, minor: &str, cur: &Currency, case: &str) -> Option<String> {
    let (_, sg, pl, sub, gender) = *cur;
    let digits = major.replace('.', "");
    let n = py_int(&digits);
    let cents = if !minor.is_empty() && minor.chars().all(is_py_digit) { py_int(minor) } else { 0 };
    if cents > 0 && sub.is_empty() {
        return Some(format!("{digits},{minor} {pl}")); // no minor unit: the grammar reads the decimal
    }
    if n == 0 && cents > 0 {
        let c = if cents == 1 { "ein".to_string() } else { de_num(&cents.to_string()) };
        return Some(format!("{c} {sub}"));
    }
    let head = if n == 1 {
        de_one_word(gender, case).to_string()
    } else {
        let h = de_num(&n.to_string());
        if h.ends_with("eins") { h[..h.len() - 1].to_string() } else { h }
    };
    let mut out = format!("{head} {}", if n == 1 { sg } else { pl });
    if cents > 0 {
        out = format!("{out} {}", de_num(&cents.to_string()));
    }
    Some(out)
}

fn de_scale_words(abbr: &str) -> (&'static str, &'static str) {
    match abbr {
        "Mio" | "Mill" => ("Million", "Millionen"),
        "Mrd" => ("Milliarde", "Milliarden"),
        "Bio" => ("Billion", "Billionen"),
        _ => ("tausend", "tausend"),
    }
}

fn de_scale(t: String, c: &mut Ctx) -> String {
    let cur = &*DE_CUR_RX;
    let p = format!(
        r"(?<!\w)(?:{cur} ?)?(?<![\w.,])(\d+(?:,\d+)?) ?(Mio|Mill|Mrd|Bio|Tsd)(?:(\.)|(?![\w-]))(?: ?{cur}(?!\w))?"
    );
    let t = c.sub(&rx(&p), &t, |m| {
        let (pre, num, abbr, post) = (g(m, 1), g(m, 2), g(m, 3), g(m, 5));
        if abbr == "Bio" && g(m, 4).is_empty() {
            return None;
        }
        let (sg, pl) = de_scale_words(abbr);
        let mut out = if num == "1" {
            if abbr == "Tsd" { "eintausend".to_string() } else { format!("eine {sg}") }
        } else {
            format!("{num} {pl}")
        };
        let k = if !post.is_empty() { post } else { pre };
        if !k.is_empty() {
            out = format!("{out} {}", DE_CUR[k].2);
        }
        Some(out)
    });
    let p = format!(r"\b(Millionen|Million|Milliarden|Milliarde|Billionen|Billion|Tausend|tausend) ?{cur}(?!\w)");
    c.sub(&rx(&p), &t, |m| Some(format!("{} {}", g(m, 1), DE_CUR[g(m, 2)].2)))
}

fn de_money(t: String, c: &mut Ctx) -> String {
    let cur = &*DE_CUR_RX;
    let t = c.sub(&rx(&format!(r"(?<![\w.,]){AMOUNT} ?{cur}(?!\w)")), &t, |m| {
        de_amount(g(m, 1), g(m, 2), DE_CUR[g(m, 3)], de_case(&t[..start(m)]))
    });
    let t = c.sub(&rx(&format!(r"(?<![\w.]){cur}( ?){AMOUNT}(?![\w]|[.,]\d)")), &t, |m| {
        let (k, space) = (g(m, 1), g(m, 2));
        if k == "Fr." || (space.is_empty() && !is_alpha(k) && !g(m, 3).contains('.')) {
            return None;
        }
        de_amount(g(m, 3), g(m, 4), DE_CUR[k], de_case(&t[..start(m)]))
    });
    c.sub(&rx(&format!(r"(?<![\w.,])(\d+,\d+) ?{cur}(?!\w)")), &t, |m| {
        Some(format!("{} {}", g(m, 1), DE_CUR[g(m, 2)].2))
    })
}

// ------------------------------------------------------------------------------------------- grouped numbers (S04)

fn de_grouped(t: String, c: &mut Ctx) -> String {
    let p = r#"(?<![^\s(\["'„“»«-])([1-9]\d{0,2}(?:\.\d{3})+)(?=(?:,\d+)?(?:$|[\s)\]"'»«“”]|[.,;:!?](?!\d)))"#;
    c.sub(&rx(p), &t, |m| {
        let s = g(m, 1);
        let parts: Vec<&str> = s.split('.').collect();
        if parts.len() == 4 && parts.iter().all(|p| py_int(p) <= 255) && parts[1..].iter().any(|p| *p != "000") {
            return None;
        }
        Some(s.replace('.', ""))
    })
}

// ---------------------------------------------------------------------------------------------------- ranges (S14)

const MONTHS: [&str; 12] = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
];
const MONTH_NAMES: [(&str, u128); 25] = [
    ("Januar", 1),
    ("Jänner", 1),
    ("Februar", 2),
    ("März", 3),
    ("April", 4),
    ("Mai", 5),
    ("Juni", 6),
    ("Juli", 7),
    ("August", 8),
    ("September", 9),
    ("Oktober", 10),
    ("November", 11),
    ("Dezember", 12),
    ("Jan", 1),
    ("Feb", 2),
    ("Mär", 3),
    ("Apr", 4),
    ("Jun", 6),
    ("Jul", 7),
    ("Aug", 8),
    ("Sept", 9),
    ("Sep", 9),
    ("Okt", 10),
    ("Nov", 11),
    ("Dez", 12),
];
/// Each name capitalised and in lowercase, an abbreviation with or without its period.
static MONTH_FORMS: LazyLock<Vec<(String, u128)>> = LazyLock::new(|| {
    let mut v: Vec<(String, u128)> = Vec::new();
    for &(name, n) in &MONTH_NAMES {
        v.push((name.to_string(), n));
        v.push((name.to_lowercase(), n));
    }
    for &(name, n) in &MONTH_NAMES[13..] {
        v.push((format!("{name}."), n));
        v.push((format!("{}.", name.to_lowercase()), n));
    }
    v
});
static MONTH_OF: LazyLock<HashMap<String, u128>> = LazyLock::new(|| MONTH_FORMS.iter().cloned().collect());
static MONTH_ALT: LazyLock<String> = LazyLock::new(|| {
    let mut v: Vec<&(String, u128)> = MONTH_FORMS.iter().collect();
    v.sort_by_key(|x| std::cmp::Reverse(len(&x.0)));
    let alt: Vec<String> =
        v.iter().map(|(f, _)| if f.ends_with('.') { f.replace('.', r"\.") } else { format!(r"{f}\b") }).collect();
    alt.join("|")
});

static SCORE_CUES: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("gewann gewinnt verlor verliert siegte siegt unterlag endete steht stand spielte endstand ergebnis sieg \
         niederlage remis führt führte")
});

fn de_range(t: String, c: &mut Ctx) -> String {
    let p = format!(r"(?<![\w.,:/–-])(\d+(?:,\d+)?)( ?– ?|-)(\d+(?:,\d+)?)(?![\w:/–-]|[.,]\d|\. ?(?:{}))", &*MONTH_ALT);
    c.sub(&rx(&p), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 3));
        if (len(a) > 1 && a.starts_with('0')) || (len(b) > 1 && b.starts_with('0')) {
            return None;
        }
        if num_value(a) >= num_value(b) {
            return None;
        }
        let head = &t[..start(m)];
        if SCORE_CUES.contains(prev_words(head)[0].to_lowercase().as_str()) {
            return None;
        }
        if (g(m, 2) == "-" && len(a) == 3 && len(b) == 4) || search(r"\d\)? $", head) {
            return None; // a phone number: 555-1234, (026) 114-9608, 030 123-456
        }
        Some(format!("{a} bis {b}"))
    })
}

// ------------------------------------------------------------------------------------------- dates, ordinals (S02/S07)

/// -ten after these; -te after der/die/das (der after a preposition or a noun is dative/genitive: -ten).
const TEN_WORDS: [&str; 28] = [
    "am", "vom", "zum", "beim", "im", "dem", "den", "des", "zur", "einem", "einen", "eines", "diesem", "diesen",
    "dieses", "jedem", "jeden", "jedes", "seinem", "seinen", "seines", "ihrem", "ihren", "ihres", "meinem", "meinen",
    "unserem", "unseren",
];
const TE_WORDS: [&str; 3] = ["der", "die", "das"];

/// `"(" + "|".join(w + "|" + cap(w) for w in sorted(ws, key=lambda w: (-len(w), w))) + ")"`.
fn article_rx(ws: &[&str]) -> String {
    let mut v: Vec<&str> = ws.to_vec();
    v.sort_by(|a, b| len(b).cmp(&len(a)).then(a.cmp(b)));
    let alt: Vec<String> = v.iter().map(|w| format!("{w}|{}", cap(w))).collect();
    format!("({})", alt.join("|"))
}

static ART_RX: LazyLock<String> = LazyLock::new(|| {
    let ws: Vec<&str> = TEN_WORDS.iter().chain(TE_WORDS.iter()).copied().collect();
    article_rx(&ws)
});
/// Before a date only these count as its article (die/das before a day number are not a date's).
static DATE_ART_RX: LazyLock<String> = LazyLock::new(|| {
    let ws: Vec<&str> = TEN_WORDS.iter().copied().chain(["der"]).collect();
    article_rx(&ws)
});
static DER_DATIVE: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("an auf aus bei in mit nach seit von vor zu zwischen über unter hinter neben bis während wegen trotz \
         innerhalb außerhalb anlässlich gegenüber laut gemäß ab")
});
/// Capitalised words that can stand before a nominative der at a sentence start (anything else there is a noun,
/// and der after a noun is a genitive).
static DER_NOM_STARTERS: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("heute morgen gestern dann da hier jetzt nun also doch und aber oder wann wo wie was ist war wird wäre sei \
         bleibt gilt kommt beginnt endet folgt es das ob")
});

/// The ordinal ending after the article art (head = the text before it): en (dritten), e (dritte), or er
/// without an article (dritter).
fn ending(art: &str, head: &str) -> &'static str {
    let a = art.to_lowercase();
    if a.is_empty() {
        return "er";
    }
    if TEN_WORDS.contains(&a.as_str()) {
        return "en";
    }
    if a == "der" {
        let p = prev_words(head).swap_remove(0);
        let pl = p.to_lowercase();
        if DER_DATIVE.contains(pl.as_str())
            || (is_alpha(&p) && first_upper(&p) && !DER_NOM_STARTERS.contains(pl.as_str()))
        {
            return "en";
        }
    }
    "e"
}

fn de_date(t: String, c: &mut Ctx) -> String {
    let p = format!(
        r"(?:(?<![\w.]){}\s+)?(?<![\w.,/])(?:(\d{{1,2}})\.( ?bis ?| ?[–-] ?))?(\d{{1,2}})\.(?: ?({})(?: ?(\d{{4}}))?|(\d{{1,2}})\.(?: ?(\d{{4}})|(\d{{2}}))?)(?![\w]|[.,]?\d)",
        &*DATE_ART_RX, &*MONTH_ALT
    );
    c.sub(&rx(&p), &t, |m| {
        let (art, d1, d, mname, mnum) = (g(m, 1), g(m, 2), g(m, 4), g(m, 5), g(m, 7));
        let year = [g(m, 6), g(m, 8), g(m, 9)].into_iter().find(|y| !y.is_empty()).unwrap_or("");
        let day = py_int(d);
        let month = if !mname.is_empty() { *MONTH_OF.get(mname)? } else { py_int(mnum) };
        if !((1..=31).contains(&day) && (1..=12).contains(&month))
            || (!d1.is_empty() && !(1..=31).contains(&py_int(d1)))
        {
            return None;
        }
        if !mnum.is_empty() && year.is_empty() && art.is_empty() {
            return None;
        }
        if !year.is_empty() && len(year) == 2 && (len(d) != 2 || len(mnum) != 2) {
            return None;
        }
        let e = ending(art, &t[..start(m)]);
        if e == "er" && !(len(year) == 4 && (1100..=1999).contains(&py_int(year))) {
            return None;
        }
        let mut out = if art.is_empty() { String::new() } else { format!("{art} ") };
        if !d1.is_empty() {
            out.push_str(&format!("{}{e} bis ", de_ord(py_int(d1))));
        }
        out.push_str(&format!("{}{e} {}", de_ord(day), MONTHS[(month - 1) as usize]));
        if !year.is_empty() {
            let y = if len(year) == 4 { year_words(py_int(year)) } else { de_num(&py_int_str(year)) };
            out.push_str(&format!(" {y}"));
        }
        Some(out)
    })
}

fn de_ordinal(t: String, c: &mut Ctx) -> String {
    let p = format!(
        r"(?<![\w.]){}\s+(\d{{1,3}})\.(?:( )(?=[A-ZÄÖÜ][a-zäöüß]|[a-zäöüß]+en [A-ZÄÖÜ])|(?=\s[a-zäöüß]|\s*$|[,;!?)]))",
        &*ART_RX
    );
    c.sub(&rx(&p), &t, |m| {
        let (art, n) = (g(m, 1), py_int(g(m, 2)));
        if !(1..=999).contains(&n) || ending(art, &t[..start(m)]) != "en" {
            return None;
        }
        if m.get(3).is_some() {
            return Some(format!("{art} {}en ", de_ord(n)));
        }
        if !["am", "vom", "zum", "den", "dem"].contains(&art.to_lowercase().as_str()) {
            return None; // no noun after it: only the day after am/vom/zum/den/dem (am 3. ist Feiertag)
        }
        let dot = if matches_at_start(END_RX, &t[end(m)..]) { "." } else { "" };
        Some(format!("{art} {}en{dot}", de_ord(n)))
    })
}

// ---------------------------------------------------------------------------------------------------- decades (S10)

fn de_decade(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,'’])['’]?(\d*0)(ern|ers|er)(?:(-)(?=[A-ZÄÖÜ])|(?![\w-]))"), &t, |m| {
        let (n, suf, hy) = (g(m, 1), g(m, 2), g(m, 3));
        if len(n) > 1 && n.starts_with('0') && n != "00" {
            return None;
        }
        let stem = if len(n) == 4 { year_words(py_int(n)) } else { de_num(&py_int_str(n)) };
        Some(format!("{stem}{suf}{}", if hy.is_empty() { "" } else { " " }))
    })
}

// ------------------------------------------------------------------------------------------------------ years (S07)

static YEAR_STRONG: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("jahr jahre jahres anno jahrgang baujahr sommer winter herbst frühjahr frühling anfang ende mitte januar \
         jänner februar märz april mai juni juli august september oktober november dezember jan feb mär apr jun jul \
         aug sep sept okt nov dez")
});
static YEAR_WEAK: LazyLock<HashSet<&str>> =
    LazyLock::new(|| set("seit bis von ab um nach vor zwischen gegen in und oder bzw"));
static AMOUNT_WORDS: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("kostet kosten kostete kosteten beträgt betragen betrug betrugen zahlt zahlen zahlte zahlten bezahlt verdient \
         verdiente wiegt wog misst maß zählt zählte hat haben hatte hatten gibt gab ca circa etwa rund knapp fast über \
         unter mindestens höchstens maximal minimal insgesamt genau nur noch auf bei mehr weniger als je pro mal \
         nummer seite zimmer plus minus")
});
static NOT_AFTER_YEAR: LazyLock<HashSet<&str>> =
    LazyLock::new(|| set("min sek std mph kcal cal mol bar mbar auf pro mal je und bis oder von x"));
const YEAR_END_RX: &str = r#"\s*(?:$|[.,;:!?)\]"»“”])"#;

fn de_year(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/–-])(1[1-9]\d\d)(?![\w]|[.,:/]\d|[–-]\d)"), &t, |m| {
        let (head, rest) = (&t[..start(m)], &t[end(m)..]);
        let raw = prev_words(head).swap_remove(0);
        let p = raw.to_lowercase();
        if matches_at_start(r"\s?[%€$£°/‰]", rest) {
            return None;
        }
        if YEAR_STRONG.contains(p.as_str()) {
            return Some(year_words(py_int(g(m, 1))));
        }
        if matches_at_start(r"\s?[A-ZÄÖÜ]", rest) {
            return None;
        }
        let fm = group_at_start(r"\s+([a-zäöüß]+)(?![\w/²³])", rest, 1);
        let follow = matches_at_start(YEAR_END_RX, rest)
            || fm.is_some_and(|w| len(&w) >= 3 && !NOT_AFTER_YEAR.contains(w.as_str()))
            || matches_at_start(r"\s+(?:und|bis|oder|–|-)\s+1[1-9]\d\d(?!\d)", rest);
        if !follow {
            return None;
        }
        if p.is_empty() && matches_at_start(YEAR_END_RX, rest) {
            return None; // a number standing alone as a sentence is a count as often as a year
        }
        if YEAR_WEAK.contains(p.as_str())
            || p.is_empty()
            || (is_alpha(&raw) && is_lower(&raw) && !AMOUNT_WORDS.contains(p.as_str()))
        {
            return Some(year_words(py_int(g(m, 1))));
        }
        None
    })
}

// ---------------------------------------------------------------------------------------------- 1 before a noun (S01)

const DE_FEM_ENDS: [&str; 12] = ["ung", "heit", "keit", "schaft", "ion", "tät", "ik", "ie", "enz", "anz", "ei", "e"];
static DE_NOT_FEM: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("Name Junge Kunde Käse Gedanke Glaube Buchstabe Friede Funke Wille Same Haufe Löwe Affe Hase Rabe \
         Bote Kollege Experte Zeuge Neffe Riese Franzose Grieche Russe Pole Türke Däne Schwede Chinese Matrose Sklave \
         Bursche Laie Knabe Drache Gatte Genosse Komplize Lotse Pate Ochse Bube Schütze Insasse Hirte Erbe Biologe \
         Psychologe Pädagoge Soziologe Geologe Code Service Cache Like Score Charme Kaffee Tee Klee Schnee See Ende \
         Auge Interesse Image Finale Gebäude Gemüse Gebirge Getreide Gelände Gewebe Gemälde Gefälle Gehäuse Genre \
         Ensemble Regime Prestige Update Feature Device Interface Release Smartphone Game Office Komitee Resümee Püree \
         Gelee Knie Genie Zombie Hippie Selfie Junkie Rookie Cookie Smoothie Brownie Ei Schrei Papagei Brei Blei Lakai \
         Katholik Pazifik Atlantik Plastik Mosaik")
});
static DE_FUNC: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("nur noch genau etwa rund knapp mindestens höchstens fast maximal circa bloß lediglich gerade zirka insgesamt \
         und oder aber auch je pro über es da hier dort heute jetzt schon bereits")
});
/// Masculine nouns that often follow a count (einen after an accusative).
static DE_MASC: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("Euro Dollar Franken Cent Rappen Tag Monat Abend Morgen Moment Augenblick Punkt Platz Versuch Fehler \
         Mann Hund Freund Grund Schritt Satz Brief Termin Wunsch Vorschlag Kommentar Kaffee Tee Apfel Kunde Name \
         Gedanke Kollege Stern Ball Baum Stuhl Tisch Schlüssel Computer Laptop Film Song Job Preis Wert Bus Zug Weg \
         Fall Gast Sohn Bruder Vater Onkel Lehrer Arzt Koffer Rucksack Eintrag Link Klick Anruf Tipp Plan Antrag \
         Auftrag Vertrag Meter Kilometer Zentimeter Liter Becher Löffel Teelöffel Esslöffel Euroschein Cent \
         Jahrestag Feiertag Urlaub Besuch Besucher Mitarbeiter Partner Spieler Sieg Treffer Elfmeter Hinweis Bericht \
         Artikel Beitrag Post Account Kurs")
});

fn de_fem(noun: &str) -> bool {
    if DE_NOT_FEM.contains(noun) || len(noun) < 3 {
        return false;
    }
    if noun.ends_with("ei") && len(noun) < 5 {
        return false;
    }
    DE_FEM_ENDS.iter().any(|e| noun.ends_with(e))
}

fn noun_gender(noun: &str) -> &'static str {
    if de_fem(noun) {
        "f"
    } else if DE_MASC.contains(noun) {
        "m"
    } else {
        "n"
    }
}

/// Unit abbreviations after a half: (written, word, plural, gender).
const DE_HALF_UNIT: [(&str, &str, &str, &str); 12] = [
    ("l", "Liter", "Liter", "m"),
    ("kg", "Kilo", "Kilo", "n"),
    ("g", "Gramm", "Gramm", "n"),
    ("ml", "Milliliter", "Milliliter", "m"),
    ("m", "Meter", "Meter", "m"),
    ("cm", "Zentimeter", "Zentimeter", "m"),
    ("km", "Kilometer", "Kilometer", "m"),
    ("h", "Stunde", "Stunden", "f"),
    ("Std.", "Stunde", "Stunden", "f"),
    ("TL", "Teelöffel", "Teelöffel", "m"),
    ("EL", "Esslöffel", "Esslöffel", "m"),
    ("Pfd.", "Pfund", "Pfund", "n"),
];

/// ein halber / einen halben / ein halbes / eine halbe / einem halben / einer halben.
fn de_half_word(gender: &str, case: &str) -> &'static str {
    if gender == "f" {
        return if case == "dat" { "einer halben" } else { "eine halbe" };
    }
    if case == "dat" {
        return "einem halben";
    }
    if gender == "n" {
        return "ein halbes";
    }
    if case == "acc" { "einen halben" } else { "ein halber" }
}

fn de_half(t: String, c: &mut Ctx) -> String {
    let p = concat!(
        "(?<![\\w/.,])(?:(\\d+)[ \u{a0}]?)?(?:½|1/2) (?:([A-ZÄÖÜ][a-zäöüß]+)(?![\\w-])|",
        r"(l|kg|g|ml|m|cm|km|h|TL|EL)(?![\w/²³])|(Std\.|Pfd\.))"
    );
    c.sub(&rx(p), &t, |m| {
        let (whole, noun) = (g(m, 1), g(m, 2));
        let unit = if !g(m, 3).is_empty() { g(m, 3) } else { g(m, 4) };
        let (word, plural, gender) = if !unit.is_empty() {
            let u = DE_HALF_UNIT.iter().find(|u| u.0 == unit)?;
            (u.1, u.2, u.3)
        } else {
            (noun, noun, noun_gender(noun))
        };
        if !whole.is_empty() {
            let n = de_num(&py_int_str(whole));
            let n = if n.ends_with("eins") { &n[..n.len() - 1] } else { &n[..] };
            return Some(format!("{n}einhalb {plural}"));
        }
        Some(format!("{} {word}", de_half_word(gender, de_case(&t[..start(m)]))))
    })
}

fn de_one(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/+-])1(?= ([A-ZÄÖÜ][a-zäöüß]+)(?![\w-]))"), &t, |m| {
        let noun = g(m, 1);
        if MONTH_OF.contains_key(noun) || noun == "Uhr" {
            return None;
        }
        let head = &t[..start(m)];
        if search(r"(?:^|\s)[A-Za-zÄÖÜäöüß]{1,4}\.\s+$", head) {
            return None;
        }
        let mut pw = prev_words(head);
        if pw[0].ends_with([',', ';']) {
            pw = vec![String::new()];
        }
        let p = &pw[0];
        if !p.is_empty() && first_upper(p) {
            let pl = p.to_lowercase();
            let known =
                DE_FUNC.contains(pl.as_str()) || DATIVE.contains(pl.as_str()) || ACCUSATIVE.contains(pl.as_str());
            if !(pw.len() > 1 && pw[1].is_empty() && known) {
                return None;
            }
        }
        Some(de_one_word(noun_gender(noun), de_case(head)).to_string())
    })
}
