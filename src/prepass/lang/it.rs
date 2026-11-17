//! 'it' rules: the port of the workbench's `langrules/it.py` (ids `it.*`).
//!
//! NeMo r1.2.0's Italian grammar reads cardinals, decimals, money, measures and HH:MM times, but has no ordinal,
//! date, Roman or fraction reading (S30), and its cardinal is always “uno” whatever noun follows (S01). These rules
//! write those spoken forms themselves, on top of the grammar's own cardinals (`words`), and leave everything else to
//! the grammar.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

use super::super::{Ctx, chars_before, full, g, matches_at_start, py_int, rx, search};
use super::{LangRule, words};
use crate::text::py_strip;

pub(super) const RULES: &[LangRule] = &[
    ("it.abbrev", it_abbrev),
    ("it.date", it_date),
    ("it.time", it_time),
    ("it.space-groups", it_space_groups),
    ("it.money-code", it_money_code),
    ("it.money-range", it_money_range),
    ("it.per-unit", it_per_unit),
    ("it.grouped", it_grouped),
    ("it.measure", it_measure),
    ("it.ordinal", it_ordinal),
    ("it.roman", it_roman),
    ("it.scale", it_scale),
    ("it.scale-di", it_scale_di),
    ("it.fraction", it_fraction),
    ("it.range", it_range),
    ("it.elision", it_elision),
    ("it.decade", it_decade),
    ("it.gender", it_gender),
    ("it.billions", it_billions),
];

const LETTER: &str = r"[^\W\d_]";
const S: &str = "[ \u{a0}]";
/// 1.234.567 or 1234567.
const INT: &str = r"\d{1,3}(?:\.\d{3})+|\d+";
const VOWEL: &str = "aeiouàèéìòóùAEIOUÀÈÉÌÒÓÙhH";

fn cat(parts: &[&str]) -> String {
    parts.concat()
}

/// Python's `re.escape` (3.7+): only the regex metacharacters and whitespace get a backslash.
fn esc(s: &str) -> String {
    let mut out = String::new();
    for ch in s.chars() {
        if "()[]{}?*+-|^$\\.&~# \t\n\r\x0b\x0c".contains(ch) {
            out.push('\\');
        }
        out.push(ch);
    }
    out
}

/// `"|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))`.
fn alt(keys: &[&str]) -> String {
    let mut k: Vec<&str> = keys.to_vec();
    k.sort_by_key(|s| std::cmp::Reverse(s.chars().count()));
    k.iter().map(|s| esc(s)).collect::<Vec<_>>().join("|")
}

fn lookup<T: Copy>(map: &[(&str, T)], k: &str) -> Option<T> {
    map.iter().find(|(a, _)| *a == k).map(|(_, v)| *v)
}

fn tail(t: &str, i: usize) -> &str {
    chars_before(t, i, 40)
}

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.start())
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

/// Python's `s[:-1]` for a non-empty string.
fn chop(s: &str) -> &str {
    s.char_indices().next_back().map_or(s, |(i, _)| &s[..i])
}

fn first(s: &str) -> Option<char> {
    s.chars().next()
}

/// `s[:1].islower()`.
fn starts_lower(s: &str) -> bool {
    first(s).is_some_and(char::is_lowercase)
}

/// `s[:1] in VOWEL and s[:1] not in "hH"`.
fn starts_vowel(s: &str) -> bool {
    first(s).is_some_and(|ch| VOWEL.contains(ch) && !"hH".contains(ch))
}

/// The reading of a whole number written in ASCII digits: the grammar's below a billion; from a billion up with
/// miliardi, which the grammar lacks (it says “mille milioni” for 1.000.000.000 and “un miliardo” for
/// 1.000.000.000.000): un miliardo, tre miliardi cinquecento milioni, ventun miliardi, mille miliardi.
fn cardinal(i: &str) -> String {
    if !full(r"[1-9][0-9]{9,14}", i) {
        return words(i, "it");
    }
    let n = py_int(i);
    let (a, b) = (n / 1_000_000_000, n % 1_000_000_000);
    let w = words(&a.to_string(), "it");
    let head = if a == 1 {
        "un miliardo".to_string()
    } else {
        format!("{} miliardi", if w.ends_with("uno") { chop(&w) } else { &w })
    };
    if b != 0 { format!("{head} {}", words(&b.to_string(), "it")) } else { head }
}

/// The grammar's reading of '1.234' or '1.234,5' (group dots dropped), with the billions composed by `cardinal`.
fn num(s: &str) -> String {
    let s = s.replace('.', "");
    let (i, d) = match s.split_once(',') {
        Some((i, d)) => (i, Some(d)),
        None => (s.as_str(), None),
    };
    if !full(r"[1-9][0-9]{9,14}", i) {
        return words(&s, "it");
    }
    match d {
        None => cardinal(i),
        Some(d) => {
            let frac = words(&format!("0,{d}"), "it");
            match frac.strip_prefix("zero ") {
                Some(r) => format!("{} {r}", cardinal(i)),
                None => words(&s, "it"),
            }
        }
    }
}

fn int_of(s: &str) -> u128 {
    py_int(&s.replace('.', ""))
}

/// `a + "," + b` when b is not empty.
fn with_dec(a: &str, b: &str) -> String {
    if b.is_empty() { a.to_string() } else { format!("{a},{b}") }
}

/// 'uno' → 'un' before a masculine noun ('uno' stays before s + consonant, z, gn, ps, x, y).
fn un(w: &str, nxt: &str) -> String {
    if w != "uno" {
        return w.to_string();
    }
    (if matches_at_start(r"(?i)(?:s[^aeiouàèéìòóù]|z|gn|ps|pn|x|y)", nxt) { "uno" } else { "un" }).to_string()
}

/// 'uno' → 'una', or 'un'' before a vowel: the article form of 1 before a feminine noun.
fn una(w: &str, nxt: &str) -> String {
    if w != "uno" {
        return w.to_string();
    }
    (if starts_vowel(nxt) { "un'" } else { "una" }).to_string()
}

fn sentence_end(rest: &str) -> bool {
    matches_at_start(r"[ \t]*(?:$|\n|[A-ZÀ-Ý])", rest)
}

// ------------------------------------------------------------------------------------------------- gender of nouns

const FEM_WORDS: &str = "ora volta persona settimana cipolla tazza notte chiave parte madre fame nave gente luce voce classe sede rete
legge mente morte carne neve fronte febbre tosse pelle fede frase base specie serie superficie torre croce pace sorte arte
moglie canzone opinione unione mano radio foto moto auto crisi analisi tesi ipotesi sintesi diagnosi metropoli oasi
mail email app chat password newsletter playlist metà città età volta";
const MASC_WORDS: &str =
    "mese nome pane cane fiore ponte padre dente mare sole latte bicchiere cognome paese piede pesce re giornale
ospedale animale segnale canale locale cuore fiume monte leone sapone limone milione miliardo campione esame studente
film bar gol goal sms post click like hotel sport computer file link tram bus camion record test team match set round
weekend server tablet smartphone caffè tè euro dollaro problema sistema programma tema schema clima dramma diploma
panorama cinema pigiama papa poeta pianeta profeta telegramma fantasma dilemma enigma teorema aroma";
const NOT_NOUN_WORDS: &str =
    "dopo quando solo molto poco troppo tanto quanto verso contro dentro sopra sotto presso dietro accanto
intorno almeno oltre nemmeno neanche perciò ecco cosiddetto uno meno fino circa ancora prima senza tra fra una la alla
della nella sulla dalla colla questa quella nessuna nessuno ogni sia era aveva ha va sta fa basta tutta tutto
ciascuno ciascuna altrimenti appena insieme invece mentre oppure ovvero cioè però eppure dunque quindi";
static FEM: LazyLock<HashSet<&str>> = LazyLock::new(|| FEM_WORDS.split_whitespace().collect());
static MASC: LazyLock<HashSet<&str>> = LazyLock::new(|| MASC_WORDS.split_whitespace().collect());
static NOT_NOUN: LazyLock<HashSet<&str>> = LazyLock::new(|| NOT_NOUN_WORDS.split_whitespace().collect());

fn ends_any(w: &str, ends: &[&str]) -> bool {
    ends.iter().any(|e| w.ends_with(e))
}

/// 'm', 'f' or None: the table, then -zione/-sione/-gione, -tà/-tù (f), -mento, -ore (m), then -a (f) / -o (m)
/// outside the function words and verb endings.
fn gender(w: &str) -> Option<char> {
    let w = w.to_lowercase();
    let w = w.as_str();
    if w.chars().count() < 2 || NOT_NOUN.contains(w) {
        return None;
    }
    if FEM.contains(w) {
        return Some('f');
    }
    if MASC.contains(w) {
        return Some('m');
    }
    if ends_any(w, &["zione", "sione", "gione", "tà", "tù"]) {
        return Some('f');
    }
    if ends_any(w, &["mento", "ore", "è"]) {
        return Some('m');
    }
    if ends_any(w, &["ista", "iatra", "cida", "ava", "eva", "iva", "ata", "ita"]) {
        return w.ends_with("ata").then_some('f');
    }
    if w.ends_with('a') {
        return Some('f');
    }
    if w.ends_with('o') {
        return Some('m');
    }
    None
}

const MASC_PL_WORDS: &str =
    "anni giorni mesi minuti secondi euro chili chilometri litri metri gradi punti uomini bambini ragazzi posti
voti gol dollari libri figli amici colpi casi morti feriti milioni miliardi centimetri grammi chilogrammi secoli paesi
comuni membri soldati";
static MASC_PL: LazyLock<HashSet<&str>> = LazyLock::new(|| MASC_PL_WORDS.split_whitespace().collect());

fn masc_plural(w: &str) -> bool {
    let w = w.to_lowercase();
    MASC_PL.contains(w.as_str()) || ends_any(&w, &["menti", "ori", "ini", "etti", "elli", "ati"])
}

// ------------------------------------------------------------------------------------------------- codes, ranges, per

const CODE_SIGN: &[(&str, &str)] = &[("USD", "$"), ("EUR", "€"), ("GBP", "£")];
/// Currencies the grammar does not read: forms, singular, plural, cent words (no cents: "").
type OtherCur = (&'static [&'static str], &'static str, &'static str, &'static str);
const OTHER_CURS: &[OtherCur] =
    &[(&["CHF"], "franco svizzero", "franchi svizzeri", "centesimi"), (&["JPY", "¥"], "yen", "yen", "")];
const SIGN: &str = r"€|\$|£";
const AMOUNT: &str = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?";

/// “5 CHF” → “cinque franchi svizzeri” (prototype `other_amount`).
fn other_amount(minus: &str, i: &str, cents: &str, form: &str) -> Option<String> {
    let &(_, one, many, minor) = OTHER_CURS.iter().find(|c| c.0.contains(&form))?;
    let cv = if cents.is_empty() { 0 } else { py_int(&format!("{cents}0")[..2]) };
    if cv != 0 && minor.is_empty() {
        return None;
    }
    let w = num(i);
    let mut out = if int_of(i) == 1 {
        format!("{} {one}", un(&w, one))
    } else {
        format!("{w}{}{many}", if search(SCALE_END, &w) { " di " } else { " " })
    };
    if cv != 0 {
        out = format!("{out} {} {minor}", num(&cv.to_string()));
    }
    Some(format!("{}{out}", if minus.is_empty() { "" } else { "meno " }))
}

fn it_money_code(t: String, c: &mut Ctx) -> String {
    let codes = CODE_SIGN.iter().map(|x| x.0).collect::<Vec<_>>().join("|");
    let t = c.sub(&rx(&cat(&[r"(?<![\w.,])(", AMOUNT, r")(", S, r"?)(", &codes, r")(?!\w)"])), &t, |m| {
        Some(format!("{}{}{}", g(m, 1), g(m, 2), lookup(CODE_SIGN, g(m, 3))?))
    });
    let t = c.sub(&rx(&cat(&[r"(?<!\w)(", &codes, r")(", S, r"?)(?=\d)"])), &t, |m| {
        Some(format!("{}{}", lookup(CODE_SIGN, g(m, 1))?, g(m, 2)))
    });
    let alt = OTHER_CURS.iter().flat_map(|c| c.0.iter()).map(|f| esc(f)).collect::<Vec<_>>().join("|");
    let t = c.sub(
        &rx(&cat(&[r"(?<![\w.,\-–~])([-−]?)(", INT, r")(?:,(\d{1,2}))?", S, r"?(", &alt, r")(?!\w)"])),
        &t,
        |m| other_amount(g(m, 1), g(m, 2), g(m, 3), g(m, 4)),
    );
    c.sub(
        &rx(&cat(&[
            r"(?<!\w)(",
            &alt,
            r")",
            S,
            r"?([-−]?)(",
            INT,
            r")(?:,(\d{1,2}))?(?!\w|[.,]\d|",
            S,
            r"?[-–~]|",
            S,
            r"*(?:",
            &SCALE_ALT,
            r")(?!\w))",
        ])),
        &t,
        |m| other_amount(g(m, 2), g(m, 3), g(m, 4), g(m, 1)),
    )
}

/// An amount as written (“1.200”, “2,5”, “7,50”) in cents, to compare the two ends of a range.
fn cents_of(a: &str) -> u128 {
    let (i, d) = a.split_once(',').unwrap_or((a, ""));
    let dv = if d.is_empty() { 0 } else { py_int(&format!("{d}0")[..2]) };
    int_of(i).saturating_mul(100).saturating_add(dv)
}

fn joined(p: &str, first: &str, last: &str) -> String {
    if ["tra", "fra"].contains(&p.to_lowercase().as_str()) {
        format!("{p} {first} e {last}")
    } else {
        format!("{} {first} a {last}", if p.is_empty() { "da" } else { p })
    }
}

fn it_money_range(t: String, c: &mut Ctx) -> String {
    let prep = cat(&[r"(?:([Dd]a|[Tt]ra|[Ff]ra)", S, r"+)?"]);
    let t = c.sub(
        &rx(&cat(&[
            r"(?<![\w$])",
            &prep,
            r"(",
            SIGN,
            r")",
            S,
            r"?(",
            AMOUNT,
            r")",
            S,
            r"?[-–~]",
            S,
            r"?(?:(",
            SIGN,
            r")",
            S,
            r"?)?(",
            AMOUNT,
            r")(?!\w|[.,]\d)",
        ])),
        &t,
        |m| {
            let (p, s, a, s2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            if (!s2.is_empty() && s2 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            let first = if a.contains(',') { format!("{a} {s}") } else { a.to_string() };
            Some(joined(p, &first, &format!("{b} {s}")))
        },
    );
    let t = c.sub(
        &rx(&cat(&[
            r"(?<![\w.,])",
            &prep,
            r"(",
            AMOUNT,
            r")(?:",
            S,
            r"?(",
            SIGN,
            r"))?",
            S,
            r"?[-–~]",
            S,
            r"?(",
            AMOUNT,
            r")(",
            S,
            r"?)(",
            SIGN,
            r")(?![\w$])",
        ])),
        &t,
        |m| {
            let (p, a, s1, b, sp, s) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
            if (!s1.is_empty() && s1 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            let first = if a.contains(',') { format!("{a}{sp}{s}") } else { a.to_string() };
            Some(joined(p, &first, &format!("{b}{sp}{s}")))
        },
    );
    let t = c.sub_tpl(
        &rx(&cat(&[r"(?<![\w.,$€£¥])[-−](", SIGN, r")(", S, r"?)(", AMOUNT, r")(?!\w|[.,]\d)"])),
        &t,
        r"meno \1\2\3",
    );
    let t = c.sub_tpl(
        &rx(&cat(&[r"(?<![\w.,$€£¥])[-−](", AMOUNT, r")(", S, r"?)(", SIGN, r")(?![\w$])"])),
        &t,
        r"meno \1\2\3",
    );
    c.sub_tpl(&rx(&cat(&[r"(?<![\w$])(", SIGN, r")(", S, r"?)[-−](", AMOUNT, r")(?!\w|[.,]\d)"])), &t, r"meno \1\2\3")
}

const PER: &[(&str, &str)] = &[
    ("mese", "al mese"),
    ("anno", "all'anno"),
    ("giorno", "al giorno"),
    ("settimana", "alla settimana"),
    ("ora", "all'ora"),
    ("h", "all'ora"),
    ("notte", "a notte"),
    ("persona", "a persona"),
    ("kg", "al chilo"),
    ("chilo", "al chilo"),
    ("l", "al litro"),
    ("litro", "al litro"),
    ("m", "al metro"),
    ("metro", "al metro"),
    ("m²", "al metro quadrato"),
    ("mq", "al metro quadro"),
    ("pezzo", "al pezzo"),
    ("minuto", "al minuto"),
    ("min", "al minuto"),
    ("km", "al chilometro"),
];

fn it_per_unit(t: String, c: &mut Ctx) -> String {
    let amount = cat(&[r"(?:(?:", SIGN, r")", S, r"?", AMOUNT, r"|", AMOUNT, S, r"?(?:", SIGN, r"))"]);
    c.sub(&rx(&cat(&[r"(?<![\w.,$])(", &amount, r")/([^\W\d_]+[²³]?)(?![\w/²³])"])), &t, |m| {
        let tok = g(m, 2);
        if let Some(per) = lookup(PER, &tok.to_lowercase()) {
            return Some(format!("{} {per}", g(m, 1)));
        }
        let one = words(&format!("1 {tok}"), "it");
        let rest = one.strip_prefix("un ").or_else(|| one.strip_prefix("uno ")).or_else(|| one.strip_prefix("una "))?;
        full(&format!("{LETTER}+(?: {LETTER}+)*"), rest).then(|| format!("{} per {rest}", g(m, 1)))
    })
}

fn it_grouped(t: String, c: &mut Ctx) -> String {
    let grp = r"[1-9]\d{0,2}(?:\.\d{3}){1,2}";
    let t = c.sub(
        &rx(&cat(&[
            r"(?<![\w.,/:\-])(",
            grp,
            r")(?!\d|[.,]\d)(",
            S,
            r"?)([^\W\d_]+(?:[²³]|/[^\W\d_]+)?|°",
            S,
            r#"?[CF]|%|‰)(?=\s|$|[.,;:!?)\]}»”"…])"#,
        ])),
        &t,
        |m| {
            let tok = g(m, 3);
            if !UNITS.iter().any(|u| u.0 == tok) && words(&format!("2 {tok}"), "it") == format!("due {tok}") {
                return None; // a word, not a unit: the grammar reads the number as it is
            }
            Some(format!("{}{}{tok}", g(m, 1).replace('.', ""), g(m, 2)))
        },
    );
    let t = c.sub(&rx(&cat(&[r"(?<![\w.,])(", grp, r"),(\d{1,2})(", S, r"?(?:", SIGN, r"))(?![\w$])"])), &t, |m| {
        Some(format!("{},{}{}", g(m, 1).replace('.', ""), g(m, 2), g(m, 3)))
    });
    c.sub(&rx(&cat(&[r"(?<![\w.,$])((?:", SIGN, r")", S, r"?)(", grp, r"),(\d{1,2})(?!\w|[.,]\d)"])), &t, |m| {
        Some(format!("{}{},{}", g(m, 1), g(m, 2).replace('.', ""), g(m, 3)))
    })
}

// ------------------------------------------------------------------------------------------------- ordinals

const ORD: [&str; 11] =
    ["", "primo", "secondo", "terzo", "quarto", "quinto", "sesto", "settimo", "ottavo", "nono", "decimo"];

/// primo … decimo, then the cardinal in one word + esimo (ventitreesimo, ventunesimo, centodecimo, duemillesimo).
fn ordinal(n: u128, fem: bool, plural: bool) -> String {
    let w = if n <= 10 {
        ORD[n as usize].to_string()
    } else {
        let w = num(&n.to_string()).replace(' ', "");
        if let Some(h) = w.strip_suffix("dieci") {
            format!("{h}decimo")
        } else if let Some(h) = w.strip_suffix("mila") {
            format!("{h}millesimo")
        } else if w.ends_with("tre") || w.ends_with("sei") {
            format!("{w}esimo")
        } else {
            format!("{}esimo", chop(&w))
        }
    };
    if plural {
        return format!("{}{}", chop(&w), if fem { "e" } else { "i" });
    }
    if fem { format!("{}a", chop(&w)) } else { w }
}

// ------------------------------------------------------------------------------------------------- abbreviations

const TITLES_NAME: &[(&str, &str)] = &[
    ("Sig.", "signor"),
    ("sig.", "signor"),
    ("Prof.", "professor"),
    ("prof.", "professor"),
    ("Ing.", "ingegner"),
    ("ing.", "ingegner"),
    ("Rag.", "ragionier"),
    ("rag.", "ragionier"),
    ("Cav.", "cavalier"),
    ("cav.", "cavalier"),
    ("Mons.", "monsignor"),
    ("mons.", "monsignor"),
];
const ABBREV: &[(&str, &str)] = &[
    ("Dott.ssa", "dottoressa"),
    ("dott.ssa", "dottoressa"),
    ("Avv.ta", "avvocata"),
    ("p. es.", "per esempio"),
    ("p.es.", "per esempio"),
    ("ad es.", "ad esempio"),
    ("a.C.", "avanti Cristo"),
    ("d.C.", "dopo Cristo"),
    ("cfr.", "confronta"),
    ("Cfr.", "confronta"),
    ("tel.", "telefono"),
    ("Tel.", "telefono"),
    ("Spett.le", "spettabile"),
    ("spett.le", "spettabile"),
    ("Egr.", "egregio"),
    ("egr.", "egregio"),
    ("Gent.mo", "gentilissimo"),
    ("gent.mo", "gentilissimo"),
    ("Gent.ma", "gentilissima"),
    ("gent.ma", "gentilissima"),
    ("Gent.mi", "gentilissimi"),
    ("gent.mi", "gentilissimi"),
];
const BEFORE_NUM: &[(&str, &str)] = &[
    ("pagg.", "pagine"),
    ("pag.", "pagina"),
    ("pp.", "pagine"),
    ("nn.", "numeri"),
    ("nr.", "numero"),
    ("n.", "numero"),
    ("N.", "numero"),
    ("n°", "numero"),
    ("N°", "numero"),
    ("nº", "numero"),
    ("Nº", "numero"),
    ("artt.", "articoli"),
    ("art.", "articolo"),
    ("Art.", "articolo"),
    ("cap.", "capitolo"),
    ("Cap.", "capitolo"),
    ("vol.", "volume"),
    ("Vol.", "volume"),
    ("ca.", "circa"),
];

fn it_abbrev(t: String, c: &mut Ctx) -> String {
    let mut t = t;
    for (a, w) in TITLES_NAME {
        t = c.sub_tpl(&rx(&cat(&[r"(?<![\w.])", &esc(a), r"(?=", S, r"*[A-ZÀ-Ý])"])), &t, w);
    }
    for (a, w) in ABBREV {
        t = c.sub(&rx(&cat(&[r"(?<![\w.])", &esc(a), r"(?!\w)"])), &t, |m| {
            let stop = g(m, 0).ends_with('.') && sentence_end(&t[end(m)..]);
            Some(if stop { format!("{w}.") } else { w.to_string() })
        });
    }
    for (a, w) in BEFORE_NUM {
        t = c.sub_tpl(&rx(&cat(&[r"(?<![\w.])", &esc(a), r"(?=", S, r"*(?:\d|[IVXLC]+\b))"])), &t, &format!("{w} "));
    }
    t
}

// ------------------------------------------------------------------------------------------------- dates

const MONTHS: [&str; 12] = [
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
];

fn is_month(w: &str) -> bool {
    MONTHS.contains(&w.to_lowercase().as_str())
}

fn day(d: u128) -> String {
    if d == 1 { "primo".to_string() } else { num(&d.to_string()) }
}

fn it_date(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,/:-])(\d{1,2})([/.-])(\d{1,2})\2(\d{4}|\d{2})(?!\d|[/.-]\d)"), &t, |m| {
        let (d, mo) = (py_int(g(m, 1)), py_int(g(m, 3)));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) || (g(m, 4).chars().count() == 2 && g(m, 2) != "/") {
            return None;
        }
        Some(format!("{} {} {}", day(d), MONTHS[mo as usize - 1], g(m, 4)))
    });
    let t = c.sub(&rx(r"(?<![\w.,/:-])(\d{4})-(\d{2})-(\d{2})(?!\d|[/.-]\d)"), &t, |m| {
        let (mo, d) = (py_int(g(m, 2)), py_int(g(m, 3)));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) {
            return None;
        }
        Some(format!("{} {} {}", day(d), MONTHS[mo as usize - 1], g(m, 1)))
    });
    let t = c.sub(&rx(r"(?<![\w.,/:-])(\d{1,2})/(\d{1,2})(?!\d|[/.-]\d)"), &t, |m| {
        let (d, mo) = (py_int(g(m, 1)), py_int(g(m, 2)));
        if !((1..=31).contains(&d)
            && (1..=12).contains(&mo)
            && search(&cat(&[r"(?i)(?:^|[^\w])(?:il|dal|al|del|nel|sul)", S, "$"]), tail(&t, start(m))))
        {
            return None;
        }
        Some(format!("{} {}", day(d), MONTHS[mo as usize - 1]))
    });
    c.sub_tpl(&rx(&cat(&[r"(?<![\w.,/:-])0?1(?=", S, r"+(?:", &MONTHS.join("|"), r")\b)"])), &t, "primo")
}

// ------------------------------------------------------------------------------------------------- clock times

static TIME_CUE: LazyLock<String> =
    LazyLock::new(|| cat(&[r"(?i)(?:^|[^\w])(?:ore|alle|dalle|le|delle|nelle|sulle|verso le)", S, r"+$"]));

fn it_time(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,:/-])(\d):([0-5]\d)(?![\d:]|[.,]\d)"), &t, |m| {
        if search(&cat(&[r"[A-ZÀ-Ý][\w-]*", S, "$"]), tail(&t, start(m))) {
            return None;
        }
        Some(format!("0{}:{}", g(m, 1), g(m, 2)))
    });
    c.sub(&rx(r"(?<![\w.,:/-])(\d{1,2})\.([0-5]\d)(?![\d:]|[.,]\d)"), &t, |m| {
        let h = py_int(g(m, 1));
        if h > 23 || !search(&TIME_CUE, tail(&t, start(m))) {
            return None;
        }
        Some(format!("{:0>2}:{}", g(m, 1), g(m, 2)))
    })
}

// ------------------------------------------------------------------------------------------------- measures

/// (abbreviation, singular, plural, feminine): the units whose reading the grammar gets wrong.
const UNITS: &[(&str, &str, &str, bool)] = &[
    ("° C", "grado Celsius", "gradi Celsius", false),
    ("°C", "grado Celsius", "gradi Celsius", false),
    ("° F", "grado Fahrenheit", "gradi Fahrenheit", false),
    ("°F", "grado Fahrenheit", "gradi Fahrenheit", false),
    ("km²", "chilometro quadrato", "chilometri quadrati", false),
    ("km2", "chilometro quadrato", "chilometri quadrati", false),
    ("kmq", "chilometro quadrato", "chilometri quadrati", false),
    ("cm²", "centimetro quadrato", "centimetri quadrati", false),
    ("cm2", "centimetro quadrato", "centimetri quadrati", false),
    ("m²", "metro quadrato", "metri quadrati", false),
    ("m2", "metro quadrato", "metri quadrati", false),
    ("mq", "metro quadrato", "metri quadrati", false),
    ("cm³", "centimetro cubo", "centimetri cubi", false),
    ("m³", "metro cubo", "metri cubi", false),
    ("m3", "metro cubo", "metri cubi", false),
    ("mc", "metro cubo", "metri cubi", false),
    ("kcal", "chilocaloria", "chilocalorie", true),
    ("cal", "caloria", "calorie", true),
    ("h", "ora", "ore", true),
    ("t", "tonnellata", "tonnellate", true),
    ("ha", "ettaro", "ettari", false),
];
/// Words after “2 ha” that make “ha” the verb (“il 2 ha vinto”, “il 2 ha un vantaggio”), not hectares.
const HA_VERB_NEXT_WORDS: &str =
    "già anche sempre mai ancora appena solo poi più un uno una il lo la i gli le l del della dei
delle nel nella detto fatto avuto visto preso messo dato vinto perso scritto chiesto deciso bisogno ragione torto
paura voglia fame sete";
static HA_VERB_NEXT: LazyLock<HashSet<&str>> = LazyLock::new(|| HA_VERB_NEXT_WORDS.split_whitespace().collect());
static UNIT_ALT: LazyLock<String> = LazyLock::new(|| alt(&UNITS.iter().map(|u| u.0).collect::<Vec<_>>()));
/// A reading that takes “di” before what it counts.
const SCALE_END: &str = r"(?:milione|milioni|miliardo|miliardi)$";

fn it_measure(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[r"(?<![\w.,/-])(-?)(", INT, r")(?:,(\d+))?", S, r"?(", &UNIT_ALT, r")(?![\w/²³'’]|\.\w)"])),
        &t,
        |m| {
            let (sign, i, dec) = (g(m, 1), g(m, 2), g(m, 3));
            let u = UNITS.iter().find(|x| x.0 == g(m, 4)).expect("unit");
            let one = i == "1" && dec.is_empty();
            if ["h", "cal", "kcal"].contains(&u.0) && !one {
                return None;
            }
            if u.0 == "ha" {
                let nxt = rx(&cat(&["^(?:", S, r"+([a-zà-ù]+))"])).captures(&t[end(m)..]).ok().flatten();
                if let Some(x) = nxt.as_ref() {
                    let w = g(x, 1);
                    if HA_VERB_NEXT.contains(w) || (w.ends_with('o') && w.chars().count() > 2) {
                        let lead = if sign.is_empty() { "" } else { "meno " };
                        return Some(format!("{lead}{} ha", num(&with_dec(i, dec)))); // the verb
                    }
                }
            }
            let n = num(&with_dec(i, dec));
            let unit = if one { u.1 } else { u.2 };
            let n = if u.3 { una(&n, unit) } else { un(&n, unit) };
            let unit = if search(SCALE_END, &n) { format!("di {unit}") } else { unit.to_string() }; // due milioni di metri quadrati
            Some(format!(
                "{}{n}{}{unit}",
                if sign.is_empty() { "" } else { "meno " },
                if n.ends_with('\'') { "" } else { " " }
            ))
        },
    )
}

// ------------------------------------------------------------------------------------------------- ordinals

const DET_M: &str = r"(?:il|lo|l'|l’|al|allo|del|dello|dal|dallo|nel|nello|sul|sullo|col|un|uno|quel|quello|questo|ogni|suo|mio|tuo|nostro|vostro)";
const DET_F: &str = r"(?:la|alla|della|dalla|nella|sulla|una|un'|un’|quella|questa|sua|mia|tua|nostra|vostra)";
const RANKED: &str = r"(?:arrivat|classificat|giunt|piazzat|finit|qualificat|posizionat)([oaie])";
const NOT_AFTER_WORDS: &str =
    "a ad di da in con su per tra fra e ed o od ma che se come al allo alla ai agli alle all del dello della
dei degli delle dell dal dallo dalla dai dagli dalle dall nel nello nella nei negli nelle nell sul sullo sulla sui sugli
sulle sull col coi il lo la i gli le l un uno una non più meno circa oggi ieri domani ora già ancora sotto sopra fuori
dentro gradi nord sud est ovest centigradi celsius fahrenheit kelvin sono è era erano sarà saranno fa faceva farà
ci si mi ti vi ne lì là qui qua poi quindi invece anche pure solo soltanto appena almeno oltre verso entro ha hanno ho
hai abbiamo avete aveva avevano siamo siete fu furono sarebbe fanno può possono deve devono viene vengono va vanno sta
stanno io tu lui lei noi voi loro egli esso essa questo questa quello quella";
static NOT_AFTER: LazyLock<HashSet<&str>> = LazyLock::new(|| NOT_AFTER_WORDS.split_whitespace().collect());

fn it_ordinal(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,])(-?)(\d+)(?:,(\d+))?([°ºª])(?![\w])"), &t, |m| {
        let (sign, n, dec, mark) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let rest = &t[end(m)..];
        let nxt = rx(&cat(&["^(?:", S, r"+(", LETTER, r"+))"])).captures(rest).ok().flatten();
        let w = nxt.as_ref().map_or("", |x| g(x, 1));
        let lw = w.to_lowercase();
        let before = tail(&t, start(m));
        let mut degree = !sign.is_empty() || !dec.is_empty() || py_int(n) == 0;
        if !degree && mark == "°" {
            let noun = (starts_lower(w) && !NOT_AFTER.contains(lw.as_str())) || is_month(w);
            let det = search(&cat(&[r"(?i)(?:^|[^\w])(?:", DET_M, "|", DET_F, ")", S, "*$"]), before);
            let ranked = search(&cat(&[r"(?i)\b", RANKED, S, "+$"]), before);
            degree = !(noun || det || ranked || n == "1");
        }
        if degree {
            if mark != "°" {
                return None;
            }
            let v = num(&with_dec(n, dec));
            if w == "gradi" {
                return Some(if sign.is_empty() { v } else { format!("meno {v}") });
            }
            return Some(format!(
                "{}{}{}",
                if sign.is_empty() { "" } else { "meno " },
                un(&v, ""),
                if n == "1" && dec.is_empty() { " grado" } else { " gradi" }
            ));
        }
        let v = py_int(n);
        if v > 999_999 {
            return None;
        }
        let mut fem = mark == "ª";
        if mark != "ª" {
            let r = rx(&cat(&[r"(?i)\b", RANKED, S, "+$"])).captures(before).ok().flatten();
            fem = search(&cat(&[r"(?i)(?:^|[^\w])", DET_F, S, "*$"]), before)
                || r.as_ref().is_some_and(|x| "ae".contains(g(x, 1)))
                || (starts_lower(w)
                    && gender(w) == Some('f')
                    && !search(&cat(&[r"(?i)(?:^|[^\w])", DET_M, S, "*$"]), before));
        }
        Some(ordinal(v, fem, false))
    })
}

// ------------------------------------------------------------------------------------------------- Roman numerals

const ROMAN: &[(&str, u128)] = &[
    ("M", 1000),
    ("CM", 900),
    ("D", 500),
    ("CD", 400),
    ("C", 100),
    ("XC", 90),
    ("L", 50),
    ("XL", 40),
    ("X", 10),
    ("IX", 9),
    ("V", 5),
    ("IV", 4),
    ("I", 1),
];

/// The value of a well-formed Roman numeral (XIV → 14), or 0.
fn roman(s: &str) -> u128 {
    let (mut n, mut i) = (0u128, 0usize);
    for (sym, v) in ROMAN {
        while s[i..].starts_with(sym) {
            n += v;
            i += sym.len();
        }
    }
    if i != s.len() || n == 0 {
        return 0;
    }
    let (mut back, mut k) = (String::new(), n);
    for (sym, v) in ROMAN {
        while k >= *v {
            back.push_str(sym);
            k -= v;
        }
    }
    if back == s { n } else { 0 }
}

const REGNAL_WORDS: &str =
    "Giovanni Paolo Pio Benedetto Leone Gregorio Clemente Innocenzo Urbano Bonifacio Alessandro Sisto Giulio
Martino Niccolò Nicola Adriano Eugenio Celestino Onorio Callisto Marcello Silvestro Stefano Luigi Carlo Enrico Filippo
Francesco Federico Ferdinando Emanuele Umberto Elisabetta Giorgio Guglielmo Edoardo Riccardo Giacomo Napoleone Ludovico
Lorenzo Cosimo Ottone Corrado Ranieri Alberto Amedeo Pietro Caterina Maria Isabella Giovanna Anna Margherita Costantino
Teodosio Giustiniano Ramses Tolomeo Rodolfo Massimiliano Leopoldo Gustavo Cristiano Haakon Olaf Harald Ivan Alfonso
Fernando Sancho Felipe Juan Carlos Baldovino Alberto Vittorio Galeazzo Giuseppe Mohammed Hassan Abdallah Re Regina Papa
Imperatore Principe Duca Conte";
const FEM_NAME_WORDS: &str = "Elisabetta Caterina Maria Isabella Giovanna Anna Margherita Regina";
static REGNAL: LazyLock<HashSet<&str>> = LazyLock::new(|| REGNAL_WORDS.split_whitespace().collect());
static FEM_NAMES: LazyLock<HashSet<&str>> = LazyLock::new(|| FEM_NAME_WORDS.split_whitespace().collect());
const TITLED: &[(&str, bool)] = &[
    ("capitolo", false),
    ("libro", false),
    ("atto", false),
    ("canto", false),
    ("volume", false),
    ("tomo", false),
    ("titolo", false),
    ("parte", true),
    ("scena", true),
    ("sezione", true),
    ("puntata", true),
    ("stagione", true),
    ("legislatura", true),
    ("guerra", true),
];

fn it_roman(t: String, c: &mut Ctx) -> String {
    let t =
        c.sub(&rx(&cat(&[r"(?<![\w-])([IVXLC]+)", S, r"+(secolo|secoli|sec\.|secc\.|millennio)(?!\w)"])), &t, |m| {
            let v = roman(g(m, 1));
            if v == 0 {
                return None;
            }
            let w = g(m, 2);
            let pl = w.starts_with("secoli") || w == "secc.";
            let noun = if w.starts_with("sec") { if pl { "secoli" } else { "secolo" } } else { w };
            Some(format!("{} {noun}", ordinal(v, false, false)))
        });
    let t = c.sub(&rx(&cat(&[r"(?<![\w.])(sec\.|secc\.|secolo|secoli)", S, r"*([IVXLC]+)(?![\w'’-])"])), &t, |m| {
        let v = roman(g(m, 2));
        if v == 0 {
            return None;
        }
        let noun = if ["secc.", "secoli"].contains(&g(m, 1)) { "secoli" } else { "secolo" };
        Some(format!("{noun} {}", ordinal(v, false, false)))
    });
    let t = c.sub(
        &rx(&cat(&[r"(?<![\w-])((?:[A-ZÀ-Ý][a-zà-ù]+", S, r")*[A-Za-zÀ-ù][a-zà-ù]+)", S, r"+([IVXLC]+)(?![\w'’-])"])),
        &t,
        |m| {
            let (name, r) = (g(m, 1), g(m, 2));
            let v = roman(r);
            let last = name.rsplit(' ').next().unwrap_or(name);
            if v == 0 {
                return None;
            }
            if let Some(fem) = lookup(TITLED, &last.to_lowercase()) {
                return Some(format!("{name} {}", ordinal(v, fem, false)));
            }
            if !REGNAL.contains(last) {
                return None;
            }
            Some(format!("{name} {}", ordinal(v, FEM_NAMES.contains(last), false)))
        },
    );
    c.sub(
        &rx(&cat(&[
            r"(?<![\w'’])(",
            DET_M,
            "|",
            DET_F,
            r")",
            S,
            r"+([IVXLC]{2,}|[IVX])",
            S,
            r"+([a-zà-ù]+)(?![\w'’-])",
        ])),
        &t,
        |m| {
            let (art, r, w) = (g(m, 1), g(m, 2), g(m, 3));
            let v = roman(r);
            if v == 0 || (gender(w).is_none() && lookup(TITLED, w).is_none()) {
                return None;
            }
            let fem =
                full(&format!("(?i){DET_F}"), art) || (gender(w) == Some('f') && !full(&format!("(?i){DET_M}"), art));
            Some(format!("{art} {} {w}", ordinal(v, fem, false)))
        },
    )
}

// ------------------------------------------------------------------------------------------------- scale words, money

const SCALES: &[(&str, (&str, &str))] = &[
    ("mln", ("milione", "milioni")),
    ("mld", ("miliardo", "miliardi")),
    ("mrd", ("miliardo", "miliardi")),
    ("milioni", ("milione", "milioni")),
    ("milione", ("milione", "milioni")),
    ("miliardi", ("miliardo", "miliardi")),
    ("miliardo", ("miliardo", "miliardi")),
];
static SCALE_ALT: LazyLock<String> = LazyLock::new(|| {
    let mut k: Vec<&str> = SCALES.iter().map(|s| s.0).collect();
    k.sort_by_key(|s| std::cmp::Reverse(s.chars().count()));
    k.join("|")
});
const CURS: &[(&str, &str)] = &[
    ("€", "euro"),
    ("EUR", "euro"),
    ("euro", "euro"),
    ("$", "dollari"),
    ("USD", "dollari"),
    ("dollari", "dollari"),
    ("£", "sterline"),
    ("GBP", "sterline"),
    ("sterline", "sterline"),
];
static CUR_ALT: LazyLock<String> = LazyLock::new(|| alt(&CURS.iter().map(|c| c.0).collect::<Vec<_>>()));
static CUR_SIGN: LazyLock<String> =
    LazyLock::new(|| alt(&CURS.iter().map(|c| c.0).filter(|k| !k.chars().any(char::is_lowercase)).collect::<Vec<_>>()));

fn cur(k: &str) -> &'static str {
    lookup(CURS, k).expect("currency")
}

const SIGN_OF: &[(&str, &str)] = &[("EUR", "€"), ("USD", "$"), ("GBP", "£")];

/// A whole number of a million or more with cents and a currency, in the grammar's money style with “di” after a
/// round million and miliardi from a billion up (prototype `big_cents`).
fn big_cents(k: &str, i: &str, d: &str) -> Option<String> {
    let w = num(i);
    if !search(SCALE_END, &w) && int_of(i) < 1_000_000_000 {
        return None; // the grammar reads it (un milione duecentomila euro cinquanta centesimi)
    }
    let cp = words(&format!("0,{d} {}", lookup(SIGN_OF, k).unwrap_or(k)), "it");
    if !full(&format!("{LETTER}+(?: {LETTER}+)*"), &cp) || cp.starts_with("zero") {
        return None;
    }
    Some(format!("{w}{}{} {cp}", if search(SCALE_END, &w) { " di " } else { " " }, cur(k)))
}

fn scaled(sign: &str, i: &str, dec: &str, sc: &str) -> String {
    let (sg, pl) = lookup(SCALES, sc).expect("scale");
    let one = i == "1" && dec.is_empty();
    let n = num(&with_dec(i, dec));
    let n = if one {
        un(&n, "")
    } else if n.ends_with("uno") {
        chop(&n).to_string()
    } else {
        n
    };
    format!("{}{n} {}", if sign.is_empty() { "" } else { "meno " }, if one { sg } else { pl })
}

fn it_scale(t: String, c: &mut Ctx) -> String {
    // The abbreviation's period also ends the sentence: keep one.
    let stop = |m: &Captures<'_, str>, t: &str| -> &'static str {
        if g(m, 0).ends_with('.') && sentence_end(&t[end(m)..]) { "." } else { "" }
    };
    let t = c.sub(
        &rx(&cat(&[
            r"(?<![\w.,$€£])(",
            &CUR_SIGN,
            r")",
            S,
            r"?(-?)(",
            INT,
            r")(?:,(\d+))?",
            S,
            r"?(",
            &SCALE_ALT,
            r")\.?(?![\w])",
        ])),
        &t,
        |m| Some(format!("{} di {}{}", scaled(g(m, 2), g(m, 3), g(m, 4), g(m, 5)), cur(g(m, 1)), stop(m, &t))),
    );
    let t = c.sub(
        &rx(&cat(&[
            r"(?<![\w.,])(-?)(",
            INT,
            r")(?:,(\d+))?",
            S,
            r"?(",
            &SCALE_ALT,
            r")\.?(?:",
            S,
            r"?(?:di",
            S,
            r"+)?(",
            &CUR_ALT,
            r"))?(?![\w$€£])",
        ])),
        &t,
        |m| {
            if g(m, 5).is_empty() && !["mln", "mld", "mrd"].contains(&g(m, 4)) {
                return None;
            }
            let out = scaled(g(m, 1), g(m, 2), g(m, 3), g(m, 4));
            Some(if g(m, 5).is_empty() {
                format!("{out}{}", stop(m, &t))
            } else {
                format!("{out} di {}", cur(g(m, 5)))
            })
        },
    );
    let big = r"[1-9]\d{0,2}(?:\.\d{3}){2,4}|[1-9]\d{6,14}";
    // € 2000000,50 → due milioni di euro cinquanta centesimi (the grammar: “due milioni euro”, “tremila milioni”)
    let t = c.sub(
        &rx(&cat(&[r"(?<![\w.,$€£])(", &CUR_SIGN, r")", S, r"?(", big, r"),(\d{1,2})(?![\w,.]\d|\d)"])),
        &t,
        |m| big_cents(g(m, 1), g(m, 2), g(m, 3)),
    );
    let t = c.sub(&rx(&cat(&[r"(?<![\w.,])(", big, r"),(\d{1,2})", S, r"?(", &CUR_SIGN, r")(?![\w])"])), &t, |m| {
        big_cents(g(m, 3), g(m, 1), g(m, 2))
    });
    c.sub(
        &rx(&cat(&[
            r"(?<![\w.,$€£])(?:(",
            &CUR_SIGN,
            r")",
            S,
            r"?(",
            big,
            r")(?![\w,.]\d)|(?<![\w.,])()(",
            big,
            r")(",
            S,
            r"+di",
            S,
            r"+|",
            S,
            r"?)(",
            &CUR_SIGN,
            r"))(?![\w])",
        ])),
        &t,
        |m| {
            let i = if g(m, 2).is_empty() { g(m, 4) } else { g(m, 2) };
            let k = if g(m, 1).is_empty() { g(m, 6) } else { g(m, 1) };
            let w = num(i);
            if search(SCALE_END, &w) {
                return Some(format!("{} di {}", un(&w, ""), cur(k)));
            }
            if int_of(i) >= 1_000_000_000 && py_strip(g(m, 5)).is_empty() {
                return Some(format!("{w} {}", cur(k))); // the grammar reads no amount from a billion up
            }
            None
        },
    )
}

// ------------------------------------------------------------------------------------------------- round millions

/// A whole number of millions as written (2.000.000, 3.500.000.000, 2000000; no leading zero); its reading decides.
const ROUND: &str = r"(?:[1-9]\d{0,2}(?:\.\d{3})*\.000\.000|[1-9]\d{0,8}000000)(?![\w%°ºª'’]|[.,:/\-–]\d)";
/// Lower-case words ending in -i/-e after a round million that are not what it counts.
const SCALE_NOT_COUNTED_WORDS: &str = "
che come dove mentre anche oltre sempre insieme invece presso poi oggi ieri qui più dopo fine dei degli delle nei negli
nelle ai agli alle dai dagli dalle sui sugli sulle coi gli le questi queste quelli quelle altri altre tutti tutte pochi
poche molti molte tanti tante troppi troppe quanti quante alcuni alcune diversi diverse vari varie certi certe
parecchi parecchie ogni entro circa perché poiché benché affinché nonché oppure eppure pure neppure inoltre infine
quindi forse persino perfino tuttavia infatti mille due tre sei sette nove dieci undici dodici tredici quattordici
quindici sedici diciassette diciannove venti trenta quaranta cinquanta sessanta settanta ottanta novanta sei hai
vuoi puoi devi sai fai dai stai vai deve viene vale riceve prende spende supera annui annuali mensili settimanali
giornalieri netti lordi totali complessivi aggiuntivi iniziali ulteriori esatti tondi pari spesi presi resi sospesi
compresi inclusi esclusi raccolti tolti persi vinti annue nette lorde complessive aggiuntive esatte previsti previste
richiesti concessi promessi messi chiesti visti primi prime ultimi ultime
";
/// -ati/-iti/-uti words that are counted nouns (“2.000.000 soldati”).
const PARTICIPLE_NOUN_WORDS: &str = "
soldati dati deputati risultati candidati mercati avvocati impiegati alleati malati ammalati contagiati vaccinati
rifugiati sfollati disoccupati laureati abbonati tesserati delegati sindacati stati senati reati peccati gelati prati
magistrati iscritti siti crediti debiti inviti vestiti limiti meriti spiriti riti miti abiti ospiti circuiti partiti
quesiti requisiti depositi minuti contenuti rifiuti tributi istituti saluti statuti sostituti attributi contributi
";
/// Nouns that are the same in the plural and do not end in -i/-e.
const INVARIABLE_WORDS: &str =
    "euro yen auto foto moto radio film sport bar computer smartphone tablet follower like click clic download";
static SCALE_NOT_COUNTED: LazyLock<HashSet<&str>> =
    LazyLock::new(|| SCALE_NOT_COUNTED_WORDS.split_whitespace().collect());
static PARTICIPLE_NOUNS: LazyLock<HashSet<&str>> = LazyLock::new(|| PARTICIPLE_NOUN_WORDS.split_whitespace().collect());
static INVARIABLE: LazyLock<HashSet<&str>> = LazyLock::new(|| INVARIABLE_WORDS.split_whitespace().collect());

/// A plural noun after a round million (prototype `counted_noun`).
fn counted_noun(w: &str) -> bool {
    if w.chars().count() < 3 || !starts_lower(w) || !full(&cat(&[LETTER, "+"]), w) {
        return false;
    }
    if INVARIABLE.contains(w) {
        return true;
    }
    if !w.chars().next_back().is_some_and(|c| c == 'i' || c == 'e') && !w.ends_with("tà") && !w.ends_with("tù") {
        return false;
    }
    if SCALE_NOT_COUNTED.contains(w) || NOT_NOUN.contains(w) || w.ends_with("mente") {
        return false;
    }
    PARTICIPLE_NOUNS.contains(w) || !(w.ends_with("ati") || w.ends_with("iti") || w.ends_with("uti"))
}

fn it_scale_di(t: String, c: &mut Ctx) -> String {
    let re = rx(&cat(&[
        r"(?<![\w.,/:\-])(?<!\d",
        S,
        r")(",
        ROUND,
        r")(",
        S,
        r"+)([^\W\d_]+(?:[²³]|/[^\W\d_]+)?)(?![\w/²³'’\-]|",
        S,
        r"*\d)",
    ]));
    c.sub(&re, &t, |m| {
        let (n, tok) = (g(m, 1), g(m, 3));
        let w = num(n);
        if !search(SCALE_END, &w) {
            return None;
        }
        if counted_noun(tok) {
            return Some(format!("{w} di {tok}"));
        }
        let unit = words(&format!("2 {tok}"), "it");
        let rest = unit.strip_prefix("due ").unwrap_or("");
        if rest == tok
            || !full(&cat(&[LETTER, "+(?: ", LETTER, "+)*"]), rest)
            || !rest.split(' ').next().and_then(|x| x.chars().next_back()).is_some_and(|c| c == 'i' || c == 'e')
        {
            return None;
        }
        Some(format!("{w} di {rest}"))
    })
}

// ------------------------------------------------------------------------------------------------- fractions

const FRAC_UNITS: &[(&str, (&str, &str, bool))] = &[
    ("kg", ("chilo", "chili", false)),
    ("g", ("grammo", "grammi", false)),
    ("l", ("litro", "litri", false)),
    ("km", ("chilometro", "chilometri", false)),
    ("m", ("metro", "metri", false)),
    ("cm", ("centimetro", "centimetri", false)),
    ("h", ("ora", "ore", true)),
];

static LABELS: LazyLock<String> = LazyLock::new(|| {
    cat(&[
        r"(?i)(?:^|[^\w])(?:pagina|pagine|pag|foto|slide|parte|episodio|puntata|capitolo|cap|numero|n|nr|articolo|art|",
        r"comma|riga|righe|linea|punto|livello|fase|volume|vol|tomo|stanza|binario|gate|uscita|piano|scala|classe|",
        r"gruppo|lotto|tavola|figura|fig|tabella|esercizio|domanda|sezione|via|piazza|viale|corso|interno|int)\.?",
        S,
        r"*$",
    ])
});

fn it_fraction(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[
            r"(?<![\w.,/-])(?:(-?\d+)",
            S,
            r"+)?(\d{1,2})/(\d{1,3})(?![\w/]|[.,]\d)(?:(",
            S,
            r"+)(",
            LETTER,
            r"+)(?![\w'’/²³-]))?",
        ])),
        &t,
        |m| {
            let (whole, a_s, b_s, sp, w) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            let (a, b) = (py_int(a_s), py_int(b_s));
            if !(0 < a && a < b && b <= 100)
                || (a_s.chars().count() > 1 && a_s.starts_with('0'))
                || search(&LABELS, tail(&t, start(m)))
            {
                return None;
            }
            let u = lookup(FRAC_UNITS, w).map(|x| (w, x.0, x.1, x.2));
            let half = a == 1 && b == 2;
            let gw = if starts_lower(w) { gender(w) } else { None };
            let part = if half {
                (if u.map_or(gw == Some('f'), |x| x.3) { "mezza" } else { "mezzo" }).to_string()
            } else {
                format!("{} {}", un(&num(a_s), ""), ordinal(b, false, a > 1))
            };
            if !whole.is_empty() {
                if let Some(u) = u {
                    let one = whole == "1";
                    let mut head = num(whole);
                    if one {
                        head = if u.3 { una(&head, u.1) } else { un(&head, u.1) };
                    }
                    return Some(format!(
                        "{head}{}{} e {part}",
                        if head.ends_with('\'') { "" } else { " " },
                        if one { u.1 } else { u.2 }
                    ));
                }
                return Some(format!("{} e {part}{sp}{w}", num(whole)));
            }
            if let Some(u) = u {
                if half {
                    return Some(if u.0 == "h" { "mezz'ora".to_string() } else { format!("{part} {}", u.1) });
                }
                return Some(format!("{part} di {}", u.1));
            }
            if half {
                if gw.is_none() {
                    return Some(format!("un mezzo{sp}{w}"));
                }
                if gw == Some('f') && starts_vowel(w) {
                    return Some(format!("mezz'{w}"));
                }
            }
            Some(format!("{part}{sp}{w}"))
        },
    )
}

// ------------------------------------------------------------------------------------------------- ranges

const SYMBOL_WORDS: &[(&str, &str)] = &[("%", "percento"), ("€", "euro"), ("°", "gradi")];
const RANGE_UNITS: &[&str] = &["km", "kg", "cm", "mm", "ml", "m", "g", "l", "h", "min", "sec", "mq", "anni"];
const PREP_TO: &[(&str, &str)] = &[
    ("da", "a"),
    ("dal", "al"),
    ("dai", "ai"),
    ("dalle", "alle"),
    ("dagli", "agli"),
    ("dallo", "allo"),
    ("dalla", "alla"),
];

fn noun_like(w: &str) -> bool {
    let lw = w.to_lowercase();
    if RANGE_UNITS.contains(&lw.as_str()) || MASC_PL.contains(lw.as_str()) {
        return true;
    }
    if !starts_lower(w) || NOT_AFTER.contains(lw.as_str()) {
        return false;
    }
    gender(&lw).is_some()
        || (lw.ends_with('e') && gender(&format!("{}a", chop(&lw))) == Some('f'))
        || (lw.ends_with('i') && gender(&format!("{}o", chop(&lw))) == Some('m'))
}

fn fem_plural(w: &str) -> bool {
    let lw = w.to_lowercase();
    gender(&lw) == Some('f') || (lw.ends_with('e') && gender(&format!("{}a", chop(&lw))) == Some('f'))
}

/// dal / dall' (and al / all') before a day number.
fn dal(n: &str, a: &str) -> String {
    let w = day(py_int(n));
    if first(&w).is_some_and(|ch| VOWEL.contains(ch)) { format!("{a}l'{w}") } else { format!("{a}l {w}") }
}

fn it_range(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[r"(?<![\w.,/:-])(\d{1,4})[-–](\d{1,4})(?![\w/:-]|[.,]\d)(", S, r"*)(%|€|°|", LETTER, r"+)(?![\w'’-])"])),
        &t,
        |m| {
            let (a, b, mut sp, mut w) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
            let (la, lb) = (a.chars().count(), b.chars().count());
            if (la > 1 && a.starts_with('0')) || (lb > 1 && b.starts_with('0')) || (la == 3 && lb == 4) {
                return None;
            }
            if py_int(a) >= py_int(b) {
                return None;
            }
            let before = tail(&t, start(m));
            if before.ends_with(") ") {
                return None;
            }
            let sym = ["%", "€", "°"].contains(&w);
            if !sym && (sp.is_empty() || !noun_like(w)) && !is_month(w) {
                return None;
            }
            if is_month(w) {
                if search(&cat(&[r"(?i)(?:^|[^\w])(?:dal|dall['’])", S, "*$"]), before) {
                    return Some(format!("{} {}{sp}{w}", day(py_int(a)), dal(b, "a")));
                }
                if search(&cat(&[r"(?i)(?:^|[^\w])(?:il|l['’])", S, "*$"]), before) {
                    return None;
                }
                return Some(format!("{} {}{sp}{w}", dal(a, "da"), dal(b, "a")));
            }
            let (mut wa, wb) = (num(a), num(b));
            if wa == "uno" && !sym && fem_plural(w) {
                wa = "una".to_string();
            }
            if sym {
                sp = " ";
                w = lookup(SYMBOL_WORDS, w).expect("symbol");
            }
            if search(
                &cat(&[
                    r"(?i)(?:^|[^\w])(?:il|lo|la|l['’]|i|gli|le|del|dello|della|dell['’]|dei|degli|delle|al|allo|alla|all['’]|",
                    r"ai|agli|alle|nel|nello|nella|nell['’]|nei|negli|nelle|sul|sullo|sulla|sull['’]|sui|sugli|sulle)",
                    S,
                    "*$",
                ]),
                before,
            ) {
                return Some(format!("{wa}-{wb}{sp}{w}"));
            }
            let p = rx(&cat(&[r"(?i)(?:^|[^\w])(da|dal|dai|dalle|dagli|dallo|dalla|tra|fra)", S, "+$"]));
            if let Ok(Some(p)) = p.captures(before) {
                let prep = g(&p, 1).to_lowercase();
                if prep == "tra" || prep == "fra" {
                    return Some(format!("{wa} e {wb}{sp}{w}"));
                }
                return Some(format!("{wa} {} {wb}{sp}{w}", lookup(PREP_TO, &prep).expect("preposition")));
            }
            Some(format!("da {wa} a {wb}{sp}{w}"))
        },
    )
}

// ------------------------------------------------------------------------------------------------- elision, decades

fn it_elision(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[
            r"(?<![\w'’])((?:[Ll]|[Dd]ell|[Aa]ll|[Dd]all|[Nn]ell|[Ss]ull|[Cc]oll|[Qq]uell|[Qq]uest)['’])(",
            INT,
            r")(?:,(\d+))?(",
            S,
            r"?%)?(?!\d|[.,]\d)",
        ])),
        &t,
        |m| {
            let w = num(&with_dec(g(m, 2), g(m, 3)));
            Some(format!("{}{w}{}", g(m, 1), if g(m, 4).is_empty() { "" } else { " percento" }))
        },
    )
}

fn it_decade(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w'’‘])['’‘](\d{2})(?![\d'’:]|[.,]\d)"), &t, |m| Some(num(g(m, 1))))
}

// ------------------------------------------------------------------------------------------------- gender of 1

fn it_gender(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[r"(?<![\w.,/:-])(\d{1,3}(?:\.\d{3})*)(", S, r"+)([a-zà-ù]", LETTER, r"*)(?![\w'’-])"])),
        &t,
        |m| {
            let (n, sp, w) = (g(m, 1), g(m, 2), g(m, 3));
            if search(&LABELS, tail(&t, start(m))) {
                return None;
            }
            let r = num(n);
            if n == "1" {
                let a = match gender(w) {
                    Some('m') => un(&r, w),
                    Some('f') => una(&r, w),
                    _ => return None,
                };
                return Some(format!("{a}{}{w}", if a.ends_with('\'') { "" } else { sp }));
            }
            if r.ends_with("uno")
                && int_of(n) > 1
                && masc_plural(w)
                && !matches_at_start(r"(?i)(?:s[^aeiouàèéìòóù]|z|gn|ps|x|y)", w)
            {
                return Some(format!("{}{sp}{w}", chop(&r)));
            }
            None
        },
    )
}

// ------------------------------------------------------------------------------------------------- billions

fn it_billions(t: String, c: &mut Ctx) -> String {
    let re = rx(&cat(&[
        r"(?<![\w.,/:\-−+$€£¥])(?<![$€£¥]",
        S,
        r")([-−]?)([1-9]\d{0,2}(?:\.\d{3}){3,4})(?:,(\d+))?(?![\w%‰°ºª'’]|[.,:/\-–]\d|",
        S,
        r"?[%‰°€$£¥])",
    ]));
    c.sub(&re, &t, |m| {
        let (sign, n, d) = (g(m, 1), g(m, 2), g(m, 3));
        let rest = &t[end(m)..];
        let nxt = rx(&cat(&["^(?:", S, r"*([^\W\d_]+(?:[²³]|/[^\W\d_]+)?))"])).captures(rest).ok().flatten();
        if let Some(x) = nxt.as_ref() {
            let tok = g(x, 1);
            if words(&format!("2 {tok}"), "it") != format!("due {tok}") {
                return None; // a unit or currency the grammar reads after the number
            }
        }
        Some(format!("{}{}", if sign.is_empty() { "" } else { "meno " }, num(&with_dec(n, d))))
    })
}

// ------------------------------------------------------------------------------------------------ space-grouped numbers

const SPACE_NUM: &str = r"[1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+";

fn it_space_groups(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r#"(?<![^\s(«“"'‘])((?:€|\$|£|¥)[ \t\x{{A0}}]?)?(?<![\w.,])(?<!\d[ \x{{A0}}\x{{202F}}])({SPACE_NUM})(?![ \x{{A0}}\x{{202F}}]?\d|[.,]\d{{3}}|,(?:\d\d|\d(?!\d))[^\s€$£¥])"#
    ));
    c.sub(&re, &t, |m| {
        let m0 = m.get(0).expect("group 0");
        let rest = &t[m0.end()..];
        let ok = m.get(1).is_some()
            || matches_at_start(r"(?:,\d{1,2})?[ \t\x{A0}\x{202F}]?(?:€|\$|£|¥)(?!\w)", rest)
            || matches_at_start(r"[ \t\x{A0}\x{202F}]+(?!(?:mila|milione|milioni|miliardo|miliardi|mln|mld|mrd)(?!\w))[^\W\d_]+(?![\w])", rest)
            || (g(m, 2).ends_with("000") && matches_at_start(r#"(?:\s|$|[.,;:!?)\]»”"…])"#, rest));
        ok.then(|| {
            let dotted: String = g(m, 2).chars().map(|ch| if " \u{a0}\u{202f}".contains(ch) { '.' } else { ch }).collect();
            format!("{}{dotted}", g(m, 1))
        })
    })
}
