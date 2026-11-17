//! 'ro' rules: the port of the workbench's `langrules/ro.py` (ids `ro.*`).
//!
//! The Romanian grammar gives units and currencies their gender and the “de” that numbers from 20 up take
//! (“22 zile” → “douăzeci și două de zile”), but any other noun gets the counting form: “1 ceapă” → “unu ceapă”,
//! “2 surori” → “doi surori”, “12 fete” → “doisprezece fete”. Neuter nouns are masculine in the singular and feminine
//! in the plural (“un ou”, “două ouă”), so a plural that does not end in -i takes the feminine form.

use std::collections::HashSet;
use std::sync::LazyLock;

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, full, g, matches_at_start, py_int, rx, search, sub_plain, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ro.ordinal-roman", ro_ordinal_roman),
    ("ro.money-code", ro_money_code),
    ("ro.money-range", ro_money_range),
    ("ro.per-unit", ro_per_unit),
    ("ro.money-cents", ro_money_cents),
    ("ro.scale", ro_scale),
    ("ro.big", ro_big),
    ("ro.units", ro_units),
    ("ro.hour", ro_hour),
    ("ro.fraction", ro_fraction),
    ("ro.gender", ro_gender),
];

const LETTER: &str = r"[^\W\d_]";
const SP: &str = r"[ \t\x{A0}]";
const NUM: &str = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?![\w%°ºª'’]|[.,:/\-–]\w|[ \x{A0}]\d)";
const NUM_BEFORE: &str = r"(?<![\w.,/:\-−–+$€£¥#\\])(?<!\d[ \x{A0}])";
const ROMAN: &str = r"(?=[IVXLC])C{0,3}(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})";

fn roman_value(s: &str) -> u32 {
    let v = |c: char| match c {
        'I' => 1i64,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        'C' => 100,
        _ => 0,
    };
    let cs: Vec<char> = s.chars().collect();
    let mut n: i64 = 0;
    for (i, &ch) in cs.iter().enumerate() {
        let x = v(ch);
        n += if i + 1 < cs.len() && v(cs[i + 1]) > x { -x } else { x };
    }
    n as u32
}

// ------------------------------------------------------------------------------------------------ number forms

const FEM: &[(&str, &str)] = &[("unu", "una"), ("doi", "două"), ("doisprezece", "douăsprezece")];
const BIG: &[&str] =
    &["mie", "mii", "milion", "milioane", "miliard", "miliarde", "bilion", "bilioane", "trilion", "trilioane"];

/// The feminine reading of a cardinal's words, last group only; 1 alone is “o”; an hour keeps “unu” (prototype
/// `feminine`).
fn feminine(w: &str, hour: bool) -> String {
    let toks: Vec<&str> = w.split(' ').collect();
    let mut start = 0;
    for (i, x) in toks.iter().enumerate() {
        if BIG.contains(x) {
            start = i + 1;
        }
    }
    if toks == ["unu"] {
        return if hour { "unu" } else { "o" }.to_string();
    }
    toks.iter()
        .enumerate()
        .map(|(i, x)| {
            if i < start || (hour && *x == "unu") {
                *x
            } else {
                FEM.iter().find(|(a, _)| a == x).map_or(*x, |(_, b)| *b)
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// The reading before a masculine or neuter noun: 1 alone is “un”.
fn masculine(w: &str) -> String {
    if w == "unu" { "un".to_string() } else { w.to_string() }
}

/// From 20 up, a number whose last two digits are 00 or 20–99 takes “de” before the noun.
fn needs_de(n: u128) -> bool {
    n > 0 && (n.is_multiple_of(100) || n % 100 >= 20)
}

// ------------------------------------------------------------------------------------------------ noun genders

const FEM_SG: &str = "
fată femeie mamă soră fiică mătușă bunică prietenă colegă doamnă domnișoară elevă studentă profesoară doctoriță
persoană familie ceapă lingură linguriță cană ceașcă sticlă bucată felie porție pastilă tabletă doză picătură foaie
pagină literă cifră notă melodie piesă poză fotografie imagine idee metodă regulă lege firmă companie echipă bancă
stradă piață sală biserică școală clasă țară mașină cameră ușă fereastră cheie carte scrisoare floare pisică vacă
oaie găină capră albină banană portocală pară roșie lămâie cutie pungă oră zi lună săptămână noapte seară dimineață
dată lecție întrebare problemă casă masă insulă regiune bicicletă motocicletă navă barcă armă bombă sticluță
farfurie tigaie oală cratiță pâine felie ladă cutiuță pereche jumătate treime parte bucățică linie propoziție
frază temă ofertă factură comandă oră etapă rundă repriză tură mie sută liră rublă rupie
";
const FEM_PL: &str = "
surori cărți luni săptămâni nopți mâini ori flori țări uși școli mașini pagini idei legi reguli bănci străzi piețe
săli biserici insule regiuni bărci arme pisici vaci oi găini capre lămâi roșii linguri căni cești felii porții
pastile doze picături foi litere cifre note melodii piese poze fotografii imagini metode firme companii echipe camere
ferestre chei scrisori întrebări probleme lecții mătuși bunici prietene colege doamne domnișoare eleve studente
profesoare persoane familii femei mame fiice fete case mese sticle bucăți tablete cutii pungi zile ore secunde
minute mii sute ouă perechi jumătăți treimi părți bucățele linii propoziții fraze teme oferte facturi comenzi etape
runde reprize ture lire ruble rupii
";
const MASC_SG: &str = "
băiat copil om bărbat frate tată prieten coleg elev student profesor doctor medic jucător câine pește cal leu dolar
euro metru oraș sat ou tren scaun loc lucru obiect produs punct procent milion miliard minut ceas telefon calculator
laptop apartament bilet pahar castron borcan cub cartof morcov măr ou an deget kilogram gram litru kilometru ban
nume membru angajat client copac pom fruct prânz meci gol joc film episod sezon capitol articol
volum etaj tur set rând cuvânt exemplu caz motiv mesaj email site program proiect plan pas nivel grad
";
const MASC_PL: &str = "
băieți copii oameni bărbați frați tați prieteni colegi elevi studenți profesori doctori medici jucători câini pești
cai lei dolari metri kilometri litri ani bani membri angajați clienți copaci pomi cartofi morcovi pantofi munți
nori arbori euro pași
";
const NEUT_PL: &str = "
trenuri scaune orașe sate locuri lucruri obiecte produse puncte procente milioane miliarde ceasuri telefoane
calculatoare apartamente bilete pahare castroane borcane mere ouă degete kilograme grame nume meciuri goluri jocuri
filme episoade sezoane capitole articole volume etaje tururi seturi rânduri cuvinte exemple cazuri motive mesaje
emailuri programe proiecte planuri niveluri grade fructe
";
const NOUNLESS: &str = "
este sunt e are au am ai avea face fac merge pot poate pare vine vin trebuie rămâne ține ține ce care de pe se ne
le te cele acele aceste unele multe alte toate mele tale sale noastre voastre lor câte și sau dar la în din cu
pentru până spre după fără despre între dintre prin că ca nu mai deja doar abia încă tot fost va vor ar era erau
ianuarie februarie martie aprilie mai iunie iulie august septembrie octombrie noiembrie decembrie ian feb mar apr
iun iul aug sep sept oct noi nov dec luni marți miercuri joi vineri sâmbătă duminică
";
const GRAMMAR_UNITS: &str = "
A AMD AUD B BDT BRL CAD CHF CM EUR Euro G GB GBP GHz Gbps Hz ILS INR JPY KB KG KM KRW Kbps L LEI LEU MB MG MHz ML MM
MXN Mbps NGN PHP RON RUB Rs TB THB TRY UAH USD V VND W amd amperi an ani aud bdt bit biți brl bytes byți cad calorii
centimetri centimetru chf cm dB db decibeli eur euro g gb gbp gbps ghz gigabytes gigabyți grad grade gram grame h
hPa hpa hz ils inr jpy kHz kW kWh kb kbps kcal kg khz kilobytes kilobyți kilograme kilogram kilometri kilometru
kilowați km kmh kmp krw kwh l lei leu litri litru luni lună m mAh mL mah mb mbps mc megabytes megabyți metri metru
mg mhz micrograme micrometri miligrame miligram mililitri mililitru milimetri milimetru min minut minute ml mm mp ms
mxn ngn ohmi ore oră php ron rub s sec secunde secundă t tb terabytes terabyți thb tone tonă try uah ug um usd vnd
volți watt wați zi zile
";

fn set(s: &'static str) -> HashSet<&'static str> {
    s.split_whitespace().collect()
}

static FEM_SG_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(FEM_SG));
static FEM_PL_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(FEM_PL));
static MASC_SG_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(MASC_SG));
static MASC_PL_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(MASC_PL));
static NEUT_PL_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(NEUT_PL));
static NOUNLESS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(NOUNLESS));
static GRAMMAR_UNITS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(GRAMMAR_UNITS));

fn ends(w: &str, suffixes: &[&str]) -> bool {
    let n = w.chars().count();
    suffixes.iter().any(|x| w.ends_with(x) && n > x.chars().count() + 1)
}

/// 'f' (feminine, or a neuter plural), 'm' (masculine, or a neuter singular) or "" when unknown.
fn noun_gender(word: &str, plural: bool) -> &'static str {
    let w = word.to_lowercase();
    let w = w.as_str();
    if NOUNLESS_SET.contains(w) {
        return "";
    }
    if plural {
        if FEM_PL_SET.contains(w) || NEUT_PL_SET.contains(w) {
            return "f";
        }
        if MASC_PL_SET.contains(w) {
            return "m";
        }
        if w.chars().count() > 2 && (w.ends_with('e') || w.ends_with("uri") || w.ends_with('ă')) {
            return "f"; // case, scaune, trenuri, ouă: feminine and neuter plurals
        }
        return "";
    }
    if FEM_SG_SET.contains(w) {
        return "f";
    }
    if MASC_SG_SET.contains(w) {
        return "m";
    }
    if ends(w, &["ție", "iune", "tate", "ință", "anță", "eală", "ime"]) {
        return "f";
    }
    if ends(w, &["ment", "ism", "tor"]) {
        return "m";
    }
    ""
}

fn known_noun(word: &str) -> bool {
    let w = word.to_lowercase();
    [&*FEM_SG_SET, &*FEM_PL_SET, &*MASC_SG_SET, &*MASC_PL_SET, &*NEUT_PL_SET].iter().any(|t| t.contains(w.as_str()))
}

// ------------------------------------------------------------------------------------------------ Roman ordinals

fn ro_ordinal_roman(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<!\w)sec\.(?={SP}+al{SP})")), &t, "secolul");
    c.sub(&rx(&format!(r"(?<!\w)(al|a)({SP}+)({ROMAN})-(lea|a)(?!\w)")), &t, |m| {
        Some(format!("{}{}{}-{}", g(m, 1), g(m, 2), roman_value(g(m, 3)), g(m, 4)))
    })
}

// ------------------------------------------------------------------------------------------------ scale words

// ------------------------------------------------------------------------------------------------ money

const INTEGER: &str = r"\d{1,3}(?:\.\d{3})+|\d+";
const AMT: &str = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?";
const SIGN: &str = r"€|\$|£";
/// Read by the grammar after an amount.
const CUR: &str = r"€|\$|£|lei|RON|EUR|USD|euro";
/// The codes the grammar reads after an amount, which it leaves as written before one.
const CODES_AFTER: &[&str] = &[
    "RON", "EUR", "USD", "GBP", "CHF", "AUD", "CAD", "JPY", "CNY", "TRY", "UAH", "RUB", "INR", "BRL", "MXN", "ILS",
    "KRW",
];
/// Neighbours' currencies the grammar does not know: code, singular, plural, feminine.
const LOCAL: &[(&str, &str, &str, bool)] = &[
    ("MDL", "leu moldovenesc", "lei moldovenești", false),
    ("HUF", "forint", "forinți", false),
    ("BGN", "leva", "leva", false),
    ("RSD", "dinar sârbesc", "dinari sârbești", false),
    ("PLN", "zlot", "zloți", false),
    ("CZK", "coroană cehă", "coroane cehe", true),
];

/// “1 HUF” → “un forint”, “2 CZK” → “două coroane cehe”, “20 HUF” → “douăzeci de forinți” (prototype `counted`).
fn counted(n: u128, w: &str, fem: bool, one: &str, many: &str) -> String {
    if n == 1 {
        return format!("{}{one}", if fem { "o " } else { "un " });
    }
    format!("{}{}{many}", if fem { feminine(w, false) } else { w.to_string() }, if needs_de(n) { " de " } else { " " })
}

fn ro_money_code(t: String, c: &mut Ctx) -> String {
    let codes = CODES_AFTER.join("|");
    let t = c.sub(&rx(&format!(r"(?<!\w)({codes}){SP}?({AMT})(?!\w|[.,]\d)")), &t, |m| {
        Some(format!("{} {}", g(m, 2), g(m, 1)))
    });
    let alt = LOCAL.iter().map(|x| x.0).collect::<Vec<_>>().join("|");
    c.sub(
        &rx(&format!(
            r"(?<![\w.,\-–~])({INTEGER}){SP}?({alt})(?!\w)|(?<!\w)({alt}){SP}?({INTEGER})(?!\w|[.,]\d|{SP}?[-–~])"
        )),
        &t,
        |m| {
            let num = if m.get(1).is_some() { g(m, 1) } else { g(m, 4) };
            let code = if m.get(2).is_some() { g(m, 2) } else { g(m, 3) };
            let &(_, one, many, fem) = LOCAL.iter().find(|x| x.0 == code)?;
            Some(counted(py_int(&num.replace('.', "")), &words(num, "ro"), fem, one, many))
        },
    )
}

/// An amount as written (“1.200”, “2,5”, “7,50”) in cents, to compare the two ends of a range.
fn cents_of(a: &str) -> u128 {
    let (i, d) = a.split_once(',').unwrap_or((a, ""));
    let dv = if d.is_empty() { 0 } else { py_int(&format!("{d}0")[..2]) };
    py_int(&i.replace('.', "")).saturating_mul(100).saturating_add(dv)
}

fn ro_money_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&format!(r"(?<![\w$€£])({SIGN}){SP}?({AMT}){SP}?[-–~]{SP}?(?:({SIGN}){SP}?)?({AMT})(?!\w|[.,]\d)")),
        &t,
        |m| {
            let (s, a, s2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
            if (!s2.is_empty() && s2 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            Some(if a.contains(',') { format!("{a} {s} până la {b} {s}") } else { format!("{a} până la {b} {s}") })
        },
    );
    c.sub(
        &rx(&format!(r"(?<![\w.,])({AMT})(?:{SP}?({CUR}))?{SP}?[-–~]{SP}?({AMT})({SP}?)({CUR})(?![\w$€£])")),
        &t,
        |m| {
            let (a, s1, b, sp, s) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            if (!s1.is_empty() && s1 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            Some(if a.contains(',') {
                format!("{a}{sp}{s} până la {b}{sp}{s}")
            } else {
                format!("{a} până la {b}{sp}{s}")
            })
        },
    )
}

fn ro_per_unit(t: String, c: &mut Ctx) -> String {
    let amount = format!(r"(?:(?:{SIGN}){SP}?{AMT}|{AMT}{SP}?(?:{CUR}))");
    c.sub(&rx(&format!(r"(?<![\w.,$€£])({amount})/([^\W\d_]+[²³]?)(?![\w/²³])")), &t, |m| {
        let tok = g(m, 2);
        let one = words(&format!("1 {tok}"), "ro");
        if let Some(rest) = one.strip_prefix("un ").or_else(|| one.strip_prefix("o ")) {
            if full(&format!("{LETTER}+(?: {LETTER}+)*"), rest) {
                return Some(format!("{} pe {rest}", g(m, 1)));
            }
        }
        full(r"[a-zăâîșțşţ]+", tok).then(|| format!("{} pe {tok}", g(m, 1)))
    })
}

fn ro_money_cents(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w.,])({INTEGER}),(\d)({SP}?(?:€|\$|lei|RON|EUR|USD|euro))(?!\w)")), &t, |m| {
        Some(format!("{},{}0{}", g(m, 1), g(m, 2), g(m, 3)))
    });
    c.sub(&rx(&format!(r"(?<![\w$€£])((?:€|\$){SP}?)({INTEGER}),(\d)(?!\w|[.,]\d)")), &t, |m| {
        Some(format!("{}{},{}0", g(m, 1), g(m, 2), g(m, 3)))
    })
}

fn ro_scale(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(r"(?<![\w.,])(\d+(?:,\d+)?){SP}*(mil\.|mln\.?|mld\.|mlrd\.?)(?:({SP}+)({LETTER}+))?"));
    c.sub(&re, &t, |m| {
        let (num, abbr, sp, nxt) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let (one, many) = if abbr.starts_with("mld") || abbr.starts_with("mlrd") {
            ("miliard", "miliarde")
        } else {
            ("milion", "milioane")
        };
        let word = if num == "1" { one } else { many };
        let de = if !nxt.is_empty() && nxt != "de" { " de" } else { "" };
        Some(format!("{num} {word}{de}{sp}{nxt}"))
    })
}

// ------------------------------------------------------------------------------------------------ hours

// ------------------------------------------------------------------------------------------------ 10^12 and up

/// A whole number of 13 to 18 digits in thousands of billions (prototype `big_words`).
fn big_words(d: &str) -> String {
    let n = py_int(d);
    let (q, r) = (n / 1_000_000_000, n % 1_000_000_000);
    let out =
        format!("{}{} miliarde", feminine(&words(&q.to_string(), "ro"), false), if needs_de(q) { " de" } else { "" });
    if r != 0 { format!("{out} {}", words(&r.to_string(), "ro")) } else { out }
}

fn ro_big(t: String, c: &mut Ctx) -> String {
    let big = r"[1-9]\d{0,2}(?:\.\d{3}){4,5}|[1-9]\d{0,2}(?:[ \x{A0}]\d{3}){4,5}";
    let re = rx(&format!(
        r"(?<![\w.,])(?<!\d[ \x{{A0}}])(-?)({big})(?![\w]|[.,]\d|[ \x{{A0}}]\d)(?:({SP}?)({SIGN}|{LETTER}+)(?!\w))?"
    ));
    c.sub(&re, &t, |m| {
        let (minus, n, sp, tok) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let d: String = n.chars().filter(|ch| *ch != '.' && *ch != ' ' && *ch != '\u{a0}').collect();
        let out = format!("{}{}", if minus.is_empty() { "" } else { "minus " }, big_words(&d));
        if m.get(4).is_none() {
            return Some(out);
        }
        let unit = words(&format!("20 {tok}"), "ro");
        if let Some(rest) = unit.strip_prefix("douăzeci de ") {
            if full(&format!("{LETTER}+(?: {LETTER}+)*"), rest) {
                return Some(format!("{out}{}{rest}", if needs_de(py_int(&d)) { " de " } else { " " }));
            }
        }
        Some(format!("{out}{sp}{tok}"))
    })
}

// ------------------------------------------------------------------------------------------------ units

fn ro_units(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.,\-–~])((?:{INTEGER})(?:,\d+)?){SP}?ha(?!\w)")), &t, |m| {
        let spoken = words(&format!("{} kg", g(m, 1)), "ro");
        if let Some(h) = spoken.strip_suffix("kilograme").filter(|h| h.ends_with(' ')) {
            return Some(format!("{h}hectare"));
        }
        spoken.strip_suffix("kilogram").filter(|h| h.ends_with(' ')).map(|h| format!("{h}hectar"))
    })
}

fn ro_hour(t: String, c: &mut Ctx) -> String {
    let re =
        rx(&format!(r"(?<!\w)([Oo]ra{SP}+|[Oo]rele{SP}+)(\d{{1,2}})(?![\w%°ºª'’]|[.,:/\-–]\w|{SP}*(?:h|ore)(?!\w))"));
    c.sub(&re, &t, |m| {
        if py_int(g(m, 2)) > 24 {
            return None;
        }
        let w = words(g(m, 2), "ro");
        let fem = feminine(&w, true);
        (fem != w).then(|| format!("{}{fem}", g(m, 1)))
    })
}

// ------------------------------------------------------------------------------------------------ fractions

fn ro_fraction(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(r"(?<![\w.,/:\-])(\d+)/(\d+)(?![\d/])({SP}+)({LETTER}+)"));
    c.sub(&re, &t, |m| {
        let (a, b, sp, word) = (py_int(g(m, 1)), py_int(g(m, 2)), g(m, 3), g(m, 4));
        if !(0 < a && a < b && b <= 16) {
            return None;
        }
        if !known_noun(word) || GRAMMAR_UNITS_SET.contains(word) {
            return None;
        }
        Some(format!("{}/{}{sp}de {word}", g(m, 1), g(m, 2)))
    })
}

// ------------------------------------------------------------------------------------------------ gender

static DATE_BEFORE: LazyLock<String> = LazyLock::new(|| {
    format!(
        r"(?<!\w)(?i:ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|septembrie|octombrie|noiembrie|decembrie){SP}*$"
    )
});

fn ro_gender(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"{NUM_BEFORE}((?:{NUM}{SP}+(?:sau|și|ori){SP}+)*)({NUM})({SP}+)(?:(de)({SP}+))?({LETTER}+)(?![\w-])"
    ));
    c.sub(&re, &t, |m| {
        let m0 = m.get(0).expect("group 0");
        let (head, num, sp1, de, sp2, word) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
        if GRAMMAR_UNITS_SET.contains(word) && de.is_empty() {
            return None;
        }
        if word == "ori" && matches_at_start(&format!(r"{SP}*\d"), &t[m0.end()..]) {
            return None; // 2 ori 3: multiplication
        }
        if search(&DATE_BEFORE, chars_before(&t, m0.start(), 24)) || (num.starts_with('0') && num != "0") {
            return None;
        }
        let n = py_int(&num.replace('.', ""));
        let gender = noun_gender(word, n != 1);
        if gender.is_empty() {
            return None;
        }
        let w = words(num, "ro");
        let new = if gender == "f" { feminine(&w, false) } else { masculine(&w) };
        let add_de = needs_de(n) && de.is_empty();
        // a number before sau/și/ori: “una sau două fete”, “unu sau doi băieți”
        let new_head = sub_plain(&rx(r"\d{1,3}(?:\.\d{3})+|\d+"), head, |x| {
            let s = &x[0];
            if s.starts_with('0') && s != "0" {
                return Some(s.to_string());
            }
            let xw = words(s, "ro");
            let xn = if gender == "f" && xw == "unu" {
                "una".to_string()
            } else if gender == "f" {
                feminine(&xw, false)
            } else {
                xw.clone()
            };
            Some(if xn != xw { xn } else { s.to_string() })
        });
        if new == w && !add_de && new_head == head {
            return None;
        }
        Some(format!("{new_head}{new}{sp1}{}{de}{sp2}{word}", if add_de { "de " } else { "" }))
    })
}
