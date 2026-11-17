//! 'sk' rules: the port of the workbench's `langrules/sk.py` (ids `sk.*`).
//!
//! The grammar reads every number in the nominative and in the masculine, every ordinal in the masculine
//! nominative, reads a mid-sentence numeric date digit by digit and the colon of a clock time aloud. These rules
//! write the words themselves where the context fixes another form, and read dates, units and abbreviations.

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, chars_after, chars_before, full, g, matches_at_start, py_int, rx, search, sub_plain, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::{py_capitalize, py_split_ws, py_strip};

pub(super) const RULES: &[LangRule] = &[
    ("sk.date", sk_date),
    ("sk.money-range", sk_money_range),
    ("sk.scale", sk_scale),
    ("sk.per-unit", sk_per_unit),
    ("sk.hectare", sk_hectare),
    ("sk.big-number", sk_big_number),
    ("sk.groups-unit", sk_groups_unit),
    ("sk.grouped-decimal", sk_grouped_decimal),
    ("sk.time", sk_time),
    ("sk.units", sk_units),
    ("sk.century", sk_century),
    ("sk.decade", sk_decade),
    ("sk.ordinal", sk_ordinal),
    ("sk.half", sk_half),
    ("sk.abbrev", sk_abbrev),
    ("sk.number-case", sk_number_case),
    ("sk.money-words", sk_money_words),
    ("sk.weekdays", sk_weekdays),
    ("sk.vocalize", sk_vocalize),
];

const LETTER: &str = r"[^\W\d_]";
const CASES: [&str; 4] = ["gen", "dat", "loc", "ins"];

/// The units 2-9 and the tens: nominative -> genitive, dative, locative, instrumental.
const CARD: &[(&str, &str)] = &[
    ("dva", "dvoch dvom dvoch dvoma"),
    ("dve", "dvoch dvom dvoch dvoma"),
    ("tri", "troch trom troch troma"),
    ("štyri", "štyroch štyrom štyroch štyrmi"),
    ("päť", "piatich piatim piatich piatimi"),
    ("šesť", "šiestich šiestim šiestich šiestimi"),
    ("sedem", "siedmich siedmim siedmich siedmimi"),
    ("osem", "ôsmich ôsmim ôsmich ôsmimi"),
    ("deväť", "deviatich deviatim deviatich deviatimi"),
    ("desať", "desiatich desiatim desiatich desiatimi"),
    ("jedenásť", "jedenástich jedenástim jedenástich jedenástimi"),
    ("dvanásť", "dvanástich dvanástim dvanástich dvanástimi"),
    ("trinásť", "trinástich trinástim trinástich trinástimi"),
    ("štrnásť", "štrnástich štrnástim štrnástich štrnástimi"),
    ("pätnásť", "pätnástich pätnástim pätnástich pätnástimi"),
    ("šestnásť", "šestnástich šestnástim šestnástich šestnástimi"),
    ("sedemnásť", "sedemnástich sedemnástim sedemnástich sedemnástimi"),
    ("osemnásť", "osemnástich osemnástim osemnástich osemnástimi"),
    ("devätnásť", "devätnástich devätnástim devätnástich devätnástimi"),
    ("dvadsať", "dvadsiatich dvadsiatim dvadsiatich dvadsiatimi"),
    ("tridsať", "tridsiatich tridsiatim tridsiatich tridsiatimi"),
    ("štyridsať", "štyridsiatich štyridsiatim štyridsiatich štyridsiatimi"),
    ("päťdesiat", "päťdesiatich päťdesiatim päťdesiatich päťdesiatimi"),
    ("šesťdesiat", "šesťdesiatich šesťdesiatim šesťdesiatich šesťdesiatimi"),
    ("sedemdesiat", "sedemdesiatich sedemdesiatim sedemdesiatich sedemdesiatimi"),
    ("osemdesiat", "osemdesiatich osemdesiatim osemdesiatich osemdesiatimi"),
    ("deväťdesiat", "deväťdesiatich deväťdesiatim deväťdesiatich deväťdesiatimi"),
];

const ORD_NOUNS: &[(&str, &str)] = &[
    ("n", "miesto miesta mieste miestom miesto"),
    ("n", "poschodie poschodia poschodí poschodím poschodie"),
    ("n", "storočie storočia storočí storočím storočie"),
    ("n", "kolo kola kole kolom kolo"),
    ("n", "výročie výročia výročí výročím výročie"),
    ("n", "vydanie vydania vydaní vydaním vydanie"),
    ("n", "tisícročie tisícročia tisícročí tisícročím tisícročie"),
    ("m", "ročník ročníka ročníku ročníkom ročník"),
    ("m", "rok roka roku rokom rok"),
    ("m", "deň dňa dni dňom deň"),
    ("m", "týždeň týždňa týždni týždňom týždeň"),
    ("m", "mesiac mesiaca mesiaci mesiacom mesiac"),
    ("m", "diel dielu diele dielom diel"),
    ("m", "stupeň stupňa stupni stupňom stupeň"),
    ("m", "krok kroku kroku krokom krok"),
    ("m", "zápas zápasu zápase zápasom zápas"),
    ("m", "semester semestra semestri semestrom semester"),
    ("m", "bod bodu bode bodom bod"),
    ("m", "odsek odseku odseku odsekom odsek"),
    ("m", "článok článku článku článkom článok"),
    ("m", "turnaj turnaja turnaji turnajom turnaj"),
    ("m", "festival festivalu festivale festivalom festival"),
    ("m", "pokus pokusu pokuse pokusom pokus"),
    ("m", "štvrťrok štvrťroka štvrťroku štvrťrokom štvrťrok"),
    ("m", "polrok polroka polroku polrokom polrok"),
    ("m", "kongres kongresu kongrese kongresom kongres"),
    ("f", "trieda triedy triede triedou triedu"),
    ("f", "liga ligy lige ligou ligu"),
    ("f", "strana strany strane stranou stranu"),
    ("f", "kapitola kapitoly kapitole kapitolou kapitolu"),
    ("f", "časť časti časti časťou časť"),
    ("f", "vojna vojny vojne vojnou vojnu"),
    ("f", "sezóna sezóny sezóne sezónou sezónu"),
    ("f", "etapa etapy etape etapou etapu"),
    ("f", "verzia verzie verzii verziou verziu"),
    ("f", "pozícia pozície pozícii pozíciou pozíciu"),
    ("f", "rada rady rade radou radu"),
    ("f", "priečka priečky priečke priečkou priečku"),
    ("f", "hodina hodiny hodine hodinou hodinu"),
    ("f", "minúta minúty minúte minútou minútu"),
    ("f", "lekcia lekcie lekcii lekciou lekciu"),
    ("f", "generácia generácie generácii generáciou generáciu"),
    ("f", "symfónia symfónie symfónii symfóniou symfóniu"),
    ("f", "republika republiky republike republikou republiku"),
    ("f", "cena ceny cene cenou cenu"),
    ("f", "kategória kategórie kategórii kategóriou kategóriu"),
    ("f", "divízia divízie divízii divíziou divíziu"),
    ("f", "dávka dávky dávke dávkou dávku"),
    ("f", "zastávka zastávky zastávke zastávkou zastávku"),
    ("f", "vlna vlny vlne vlnou vlnu"),
    ("f", "fáza fázy fáze fázou fázu"),
    ("f", "polovica polovice polovici polovicou polovicu"),
    ("f", "kniha knihy knihe knihou knihu"),
    ("f", "séria série sérii sériou sériu"),
    ("f", "dekáda dekády dekáde dekádou dekádu"),
];

const FEM_SG: &str =
    "sestra žena dcéra matka mama babka teta osoba hodina minúta sekunda kniha strana lyžica lyžička šálka
fľaša porcia tableta cibuľa mrkva paprika hruška slivka ryba sliepka krava mačka ruka noha hlava verzia metóda
firma značka cena hra karta rozprávka kategória skupina rodina spálňa kúpeľňa kuchyňa lampa skriňa stena mapa
taška bunda košeľa čiapka koruna tona kalória míľa návšteva splátka dávka zmena vojna šanca izba škola trieda
ulica cesta káva pizza žemľa kôpka priateľka kamarátka učiteľka študentka lekárka kolegyňa otázka odpoveď noc vec
kosť reč pieseň myš soľ pomoc tvár posteľ časť jeseň";

const FEM_NEUT_PL: &str = "sestry ženy dcéry matky mamy babky tety osoby hodiny minúty sekundy noci veci knihy strany
lyžice lyžičky šálky fľaše porcie tablety cibule mrkvy papriky hrušky slivky ryby sliepky kravy mačky ruky nohy
hlavy verzie možnosti metódy firmy značky ceny hry karty piesne rozprávky kategórie skupiny rodiny spálne kúpeľne
kuchyne lampy skrine steny mapy tašky bundy košele čiapky koruny tony kalórie míle návštevy splátky dávky zmeny
vojny šance izby školy triedy ulice cesty kávy pizze žemle priateľky kamarátky učiteľky študentky otázky odpovede
deti vajcia autá mestá okná jablká kolá pivá slová kurčatá zvieratá poschodia námestia srdcia polia mora";

const ANIM_NOM: &str = "bratia synovia priatelia kamaráti muži chlapci študenti žiaci učitelia lekári kolegovia ľudia
rodičia susedia hostia hráči robotníci zamestnanci pracovníci policajti vojaci turisti pasažieri zákazníci pacienti
účastníci poslanci politici ministri vodiči herci autori vedci odborníci inžinieri spisovatelia novinári občania
obyvatelia otcovia dedovia strýkovia bratranci";

const UNITS: [&str; 10] = ["", "jeden", "dva", "tri", "štyri", "päť", "šesť", "sedem", "osem", "deväť"];
const TENS: [&str; 10] =
    ["", "", "dvadsať", "tridsať", "štyridsať", "päťdesiat", "šesťdesiat", "sedemdesiat", "osemdesiat", "deväťdesiat"];
const TEENS: [&str; 10] =
    ["desať", "jedenásť", "dvanásť", "trinásť", "štrnásť", "pätnásť", "šestnásť", "sedemnásť", "osemnásť", "devätnásť"];
/// 1 on its own: masculine/neuter and feminine forms of each case.
const ONE: &[(&str, &str)] = &[("m", "jedného jednému jednom jedným"), ("f", "jednej jednej jednej jednou")];
const NEUT_SG: &str = "vajce auto mesto okno jablko pivo slovo číslo jedlo kino rádio kreslo dieťa kurča dievča zviera
miesto poschodie námestie storočie výročie vydanie more pole srdce euro tričko mlieko vajíčko kilo pravidlo svetlo
koleso";
const ANIM_GEN: &[&str] = &["ľudí", "hostí", "rodičov"];
const MASC_A: &[&str] = &["hrdina", "kolega", "sudca", "starosta", "predseda", "turista", "vodca"];

fn set(src: &'static str) -> HashSet<&'static str> {
    py_split_ws(src).into_iter().collect()
}

static FEM_SG_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(FEM_SG));
static FEM_NEUT_PL_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(FEM_NEUT_PL));
static ANIM_NOM_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(ANIM_NOM));
static NEUT_SG_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(NEUT_SG));

static ORD_FORMS: LazyLock<HashMap<&'static str, Vec<(&'static str, &'static str)>>> = LazyLock::new(|| {
    let mut m: HashMap<&'static str, Vec<(&'static str, &'static str)>> = HashMap::new();
    for &(gender, forms) in ORD_NOUNS {
        for (case, w) in ["nom", "gen", "loc", "ins", "acc"].into_iter().zip(py_split_ws(forms)) {
            m.entry(w).or_default().push((gender, case));
        }
    }
    m
});

/// Ordinal endings by gender (nom gen dat acc ins loc): after a long ý, after a short y (piaty: the rhythmic law).
const ORD_LONG: &[(&str, &str)] =
    &[("m", "ý ého ému ý ým om"), ("n", "é ého ému é ým om"), ("f", "á ej ej ú ou ej"), ("pl", "é ých ým é ými ých")];
const ORD_SHORT: &[(&str, &str)] =
    &[("m", "y eho emu y ym om"), ("n", "e eho emu e ym om"), ("f", "a ej ej u ou ej"), ("pl", "e ych ym e ymi ych")];
const TRETI: &[(&str, &str)] = &[
    ("m", "tretí tretieho tretiemu tretí tretím treťom"),
    ("n", "tretie tretieho tretiemu tretie tretím treťom"),
    ("f", "tretia tretej tretej tretiu treťou tretej"),
    ("pl", "tretie tretích tretím tretie tretími tretích"),
];
const ORD_CASES: [&str; 6] = ["nom", "gen", "dat", "acc", "ins", "loc"];

const GEN_PREPS: &[&str] = &[
    "od",
    "do",
    "z",
    "zo",
    "okolo",
    "u",
    "bez",
    "počas",
    "podľa",
    "namiesto",
    "vedľa",
    "okrem",
    "blízko",
    "uprostred",
    "pomocou",
    "vrátane",
    "výške",
    "veku",
    "vzdialenosti",
    "hodnote",
    "množstve",
    "počte",
    "rozmedzí",
];
const DAT_PREPS: &[&str] = &["k", "ku", "vďaka", "kvôli", "proti", "voči", "oproti"];
const LOC_PREPS: &[&str] = &["pri"];
const INS_PREPS: &[&str] = &["s", "so"];
const LOC_OR_ACC: &[&str] = &["v", "vo", "na", "o", "po"];
const OTHER_PREPS: &[&str] = &["za", "pred", "nad", "pod", "medzi", "pre", "cez"];

const MONTHS_GEN: &str = "januára|februára|marca|apríla|mája|júna|júla|augusta|septembra|októbra|novembra|decembra";
const UPPER: &str = "A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ";
const LOWER: &str = "a-záäčďéíĺľňóôŕšťúýž";
const TRAIL: &str = ".,;:!?)]»\"'…";

fn lookup<'a>(map: &[(&str, &'a str)], k: &str) -> Option<&'a str> {
    map.iter().find(|(a, _)| *a == k).map(|(_, v)| *v)
}

fn nth(s: &str, i: usize) -> &str {
    py_split_ws(s)[i]
}

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.start())
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

fn nchars(s: &str) -> usize {
    s.chars().count()
}

fn is_prep(p: &str) -> bool {
    GEN_PREPS.contains(&p)
        || DAT_PREPS.contains(&p)
        || LOC_PREPS.contains(&p)
        || INS_PREPS.contains(&p)
        || LOC_OR_ACC.contains(&p)
        || OTHER_PREPS.contains(&p)
}

/// One unit or ten word (päť, dvadsať) in case i, or None.
fn decline(w: &str, i: usize) -> Option<String> {
    lookup(CARD, w).map(|f| nth(f, i).to_string())
}

/// The cardinal n (1-99, and whole thousands in the genitive) in `case`; `gender` m/f picks the forms of 1.
fn card(n: u128, case: &str, gender: &str) -> Option<String> {
    let i = CASES.iter().position(|c| *c == case)?;
    if n == 1 {
        return lookup(ONE, gender).map(|f| nth(f, i).to_string());
    }
    if n >= 2000 && n.is_multiple_of(1000) && n < 100000 && case == "gen" {
        let k = card(n / 1000, case, gender)?;
        return Some(format!("{k} tisíc"));
    }
    if n >= 100 {
        return None;
    }
    let n = n as usize;
    if n < 10 {
        return decline(UNITS[n], i);
    }
    if n < 20 {
        return decline(TEENS[n - 10], i);
    }
    let (tens, units) = (TENS[n / 10], n % 10);
    if units == 1 {
        return None;
    }
    let a = decline(tens, i);
    if units == 0 {
        return a;
    }
    let b = decline(UNITS[units], i);
    Some(format!("{} {}", a?, b?))
}

/// One ordinal word (masculine nominative: prvý, piaty, tretí) in a gender and case; other words stay.
fn ord_word(w: &str, gender: &str, case: &str) -> String {
    let i = ORD_CASES.iter().position(|c| *c == case).unwrap_or(0);
    if w == "tretí" {
        return nth(lookup(TRETI, gender).unwrap_or("tretí tretieho tretiemu tretí tretím treťom"), i).to_string();
    }
    if let Some(stem) = w.strip_suffix('ý') {
        return format!("{stem}{}", nth(lookup(ORD_LONG, gender).unwrap_or("ý ého ému ý ým om"), i));
    }
    if let Some(stem) = w.strip_suffix('y') {
        return format!("{stem}{}", nth(lookup(ORD_SHORT, gender).unwrap_or("y eho emu y ym om"), i));
    }
    w.to_string()
}

/// The ordinal n (1-999) in a gender and case (dvadsiatom prvom), or None when the grammar has none.
fn ordinal(n: u128, gender: &str, case: &str) -> Option<String> {
    if !(1..1000).contains(&n) {
        return None;
    }
    let base = words(&format!("{n}."), "sk");
    let ws = py_split_ws(&base);
    let last = *ws.last()?;
    if base.contains('.') || !(last.ends_with('ý') || last.ends_with('y') || last == "tretí") {
        return None;
    }
    Some(ws.iter().map(|w| ord_word(w, gender, case)).collect::<Vec<_>>().join(" "))
}

/// '.' when the dot that ends at `end` also ends the sentence (end of text or line, or a capitalized word).
fn end_dot(t: &str, end: usize) -> &'static str {
    if matches_at_start(&format!(r"(?:\s*$|\n|\s+[{UPPER}][{LOWER}])"), &t[end..]) { "." } else { "" }
}

/// '.' when the abbreviation dot that ends at `end` is the last thing on its line.
fn line_end(t: &str, end: usize) -> &'static str {
    if matches_at_start(r"(?:\s*$|\n)", &t[end..]) { "." } else { "" }
}

/// The genitive plural the grammar gives a unit or currency after a number (€ -> eur), or None for a word.
fn unit_gen(tok: &str) -> Option<String> {
    let r = words(&format!("5 {tok}"), "sk");
    let rest = r.strip_prefix("päť ")?;
    if search(r"\d", &r) || rest == tok {
        return None;
    }
    Some(rest.to_string())
}

/// The word before the number at `start`, lowercased, looking past 'N a/až/alebo' (o 5 a 10 mačkách).
fn prep_before(t: &str, start: usize) -> String {
    let win = chars_before(t, start, 40);
    match rx(r"(?:^|[^\w.])(\w+\.?)\s+(?:\d+\s*(?:a|až|alebo|či|,)\s*)?$").captures(win) {
        Ok(Some(m)) => g(&m, 1).to_lowercase(),
        _ => String::new(),
    }
}

/// The first word after the number at `end`, past 'a/až/alebo/do N', lowercased.
fn noun_after(t: &str, end: usize) -> String {
    let win = chars_after(t, end, 60);
    match rx(r"^(?:(?:\s*(?:a|až|alebo|či|do|–|-|,)\s*\d+)*\s*([^\W\d_]+))").captures(win) {
        Ok(Some(m)) => g(&m, 1).to_lowercase(),
        _ => String::new(),
    }
}

/// The case a plural noun's ending shows: -ách/-och/-iach locative, -ami/-mi instrumental, -ám/-iam dative.
fn suffix_case(w: &str) -> Option<&'static str> {
    if nchars(w) < 4 {
        return None;
    }
    if search(r"(?:ách|ach|och|iach)$", w) {
        return Some("loc");
    }
    if search(r"(?:ami|iami|[ďťňľdtnlrsk]mi)$", w) {
        return Some("ins");
    }
    if search(r"(?:ám|iam)$", w) {
        return Some("dat");
    }
    None
}

/// A decimal in the short form (jedna celá dva, dve celé päť, päť celých tri).
fn short_decimal(num: &str) -> String {
    let (whole, frac) = num.split_once(',').unwrap_or((num, ""));
    let w = py_int(whole);
    let head = match w {
        0 => "nula celých".to_string(),
        1 => "jedna celá".to_string(),
        2 => "dve celé".to_string(),
        3 => "tri celé".to_string(),
        4 => "štyri celé".to_string(),
        _ => format!("{} celých", words(&w.to_string(), "sk")),
    };
    let stripped = frac.trim_start_matches('0');
    let zeros = nchars(frac) - nchars(stripped);
    let mut tail = "nula ".repeat(zeros);
    if !frac.trim_matches('0').is_empty() {
        tail.push_str(&words(stripped, "sk"));
    }
    py_strip(&format!("{head} {}", py_strip(&tail))).to_string()
}

/// N hodina/minúta/sekunda/deciliter in the nominative with the noun's agreement (dve hodiny, päť minút).
fn unit_words(n: &str, unit: &str) -> String {
    let (one, few, many, fem) = match unit {
        "h" => ("hodina", "hodiny", "hodín", true),
        "min" => ("minúta", "minúty", "minút", true),
        "s" => ("sekunda", "sekundy", "sekúnd", true),
        "dl" => ("deciliter", "decilitre", "decilitrov", false),
        _ => ("centiliter", "centilitre", "centilitrov", false),
    };
    if n.contains(',') {
        let noun = if ["h", "min", "s"].contains(&unit) { few } else { many };
        return format!("{} {noun}", short_decimal(n));
    }
    match py_int(n) {
        1 => format!("{}{one}", if fem { "jedna " } else { "jeden " }),
        2 => format!("{} {few}", if fem { "dve" } else { "dva" }),
        3 => format!("tri {few}"),
        4 => format!("štyri {few}"),
        _ => format!("{} {many}", words(n, "sk")),
    }
}

fn sk_date(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(
        &rx(r"(?<![\w.,])(0?[1-9]|[12]\d|3[01])\.(0?[1-9]|1[0-2])\.((?:1\d|20)\d\d)(?!\w|\.\d)"),
        &t,
        r"\1. \2. \3",
    );
    let s: &str = &t;
    let t2 = c.sub(
        &rx(r"(?<![\w.])((?:[Dd]o|[Oo]d|[Pp]o|[Pp]red|[Kk]u?|[Dd]ňa|[Zz]o?|[Nn]a|[Aa]ž) )(0?[1-9]|[12]\d|3[01])\. ?(0?[1-9]|1[0-2])\.(?! ?\d)(?!\w)"),
        &t,
        |m| {
            let (prep, d, mo) = (g(m, 1), g(m, 2), g(m, 3));
            let sp = words(&format!("{}. {}. 2000", py_int(d), py_int(mo)), "sk");
            let dm = sp.strip_suffix(" dvetisíc")?;
            Some(format!("{prep}{dm}{}", end_dot(s, end(m))))
        },
    );
    c.sub(
        &rx(&format!(
            r"(?<![\w.,])(?:([Oo]d) ([12]?\d|3[01])\. do ([12]?\d|3[01])\.|([12]?\d|3[01])\. ?[–-] ?([12]?\d|3[01])\.) ({MONTHS_GEN})\b"
        )),
        &t2,
        |m| {
            let od = g(m, 1);
            let (a, b) = if od.is_empty() { (g(m, 4), g(m, 5)) } else { (g(m, 2), g(m, 3)) };
            let x = ordinal(py_int(a), "m", "gen")?;
            let y = ordinal(py_int(b), "m", "gen")?;
            let od = if od.is_empty() { "od" } else { od };
            Some(format!("{od} {x} do {y} {}", g(m, 6)))
        },
    )
}

fn sk_scale(t: String, c: &mut Ctx) -> String {
    let scales: &[(&str, (&str, &str))] =
        &[("tis", ("000", "tisíca")), ("mil", ("000 000", "milióna")), ("mld", ("000 000 000", "miliardy"))];
    let s: &str = &t;
    let t2 = c.sub(&rx(r"(?<![\w.,])(\d+(?:,\d+)?) ?(tis\.|mil\.|mld\.|mld(?![\w.]))(?!\w)"), &t, |m| {
        let (num, sc) = (g(m, 1), g(m, 2));
        let (zeros, gen_sg) = scales.iter().find(|(k, _)| *k == &sc[..3]).map(|(_, v)| *v)?;
        let dot = if sc.ends_with('.') { line_end(s, end(m)) } else { "" };
        if !num.contains(',') {
            let n = py_int(num);
            if n >= 1000 {
                return None;
            }
            return Some(format!("{n} {zeros}{dot}"));
        }
        Some(format!("{} {gen_sg}{dot}", short_decimal(num)))
    });
    c.sub(&rx(r"\b((?:tisíca|milióna|miliardy)) (€|EUR|USD|\$|Kč|CZK)(?!\w)"), &t2, |m| {
        let gw = unit_gen(g(m, 2))?;
        Some(format!("{} {gw}", g(m, 1)))
    })
}

fn sk_minutes(mm: &str) -> String {
    match py_int(mm) {
        1 => "jedna minúta".to_string(),
        2 => "dve minúty".to_string(),
        3 => "tri minúty".to_string(),
        4 => "štyri minúty".to_string(),
        v => format!("{} minút", words(&v.to_string(), "sk")),
    }
}

fn sk_time_spoken(h: &str, mm: &str, case: &str) -> Option<String> {
    let hw = ordinal(py_int(h), "f", case)?;
    if mm == "00" {
        return Some(hw);
    }
    let mut ch = mm.chars();
    let (a, b) = (ch.next()?, ch.next()?);
    let minutes = if a == '0' { format!("nula {}", words(&b.to_string(), "sk")) } else { words(mm, "sk") };
    Some(format!("{hw} {minutes}"))
}

fn sk_time(t: String, c: &mut Ctx) -> String {
    let prep_case: &[(&str, &str)] = &[
        ("o", "loc"),
        ("po", "loc"),
        ("od", "gen"),
        ("do", "gen"),
        ("okolo", "gen"),
        ("z", "gen"),
        ("zo", "gen"),
        ("pred", "ins"),
        ("medzi", "ins"),
        ("na", "acc"),
    ];
    let s: &str = &t;
    let t2 = c.sub(
        &rx(r"(?<![\w.,:])(?:([Oo]d) )?([01]?\d|2[0-3]):([0-5]\d) ?[–-] ?([01]?\d|2[0-3]):([0-5]\d)(?![\d:])( ?hod\.(?!\w))?"),
        &t,
        |m| {
            let a = sk_time_spoken(g(m, 2), g(m, 3), "gen")?;
            let b = sk_time_spoken(g(m, 4), g(m, 5), "gen")?;
            let dot = if g(m, 6).is_empty() { "" } else { line_end(s, end(m)) };
            let od = if g(m, 1).is_empty() { "od" } else { g(m, 1) };
            Some(format!("{od} {a} do {b}{dot}"))
        },
    );
    let s2: &str = &t2;
    c.sub(
        &rx(r"(?<![\w.])(?:([Oo]|[Pp]o|[Oo]d|[Dd]o|[Oo]kolo|[Zz]o?|[Pp]red|[Mm]edzi|[Nn]a) )?([01]?\d|2[0-3])([:.])([0-5]\d)(?![\d:]|[.,]\d|\w)( ?hod\.(?!\w))?(?! ?(?:[AaPp]\.?[Mm]\b|GMT|UTC|SE?ČS?|CES?T))"),
        &t2,
        |m| {
            let (prep, h, sep, mm, hod) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            let case = lookup(prep_case, &prep.to_lowercase());
            let dot = if hod.is_empty() { "" } else { line_end(s2, end(m)) };
            let Some(case) = case else {
                if sep == "." || !prep.is_empty() {
                    return None;
                }
                if mm == "00" {
                    if hod.is_empty() {
                        return None;
                    }
                    return Some(format!("{}{dot}", words(&format!("{}:00", py_int(h)), "sk")));
                }
                return Some(format!("{} {}{dot}", words(&format!("{}:00", py_int(h)), "sk"), sk_minutes(mm)));
            };
            if sep == "." && case != "loc" && case != "gen" {
                return None;
            }
            let sp = sk_time_spoken(h, mm, case)?;
            Some(format!("{prep} {sp}{dot}"))
        },
    )
}

fn sk_units(t: String, c: &mut Ctx) -> String {
    let unit_of: &[(&str, &str)] = &[
        ("h", "h"),
        ("hod", "h"),
        ("hod.", "h"),
        ("min", "min"),
        ("min.", "min"),
        ("sek", "s"),
        ("sek.", "s"),
        ("dl", "dl"),
        ("cl", "cl"),
    ];
    let gen_pl: &[(&str, &str)] =
        &[("h", "hodín"), ("min", "minút"), ("s", "sekúnd"), ("dl", "decilitrov"), ("cl", "centilitrov")];
    let gen_sg: &[(&str, &str)] =
        &[("h", "hodiny"), ("min", "minúty"), ("s", "sekundy"), ("dl", "decilitra"), ("cl", "centilitra")];
    let s: &str = &t;
    c.sub(
        &rx(r"(?<![\w.,/:])(\d+(?:,\d+)?)(?: ?[–-] ?(\d+))? ?(hod\.|hod|h|min\.|min|sek\.|sek|dl|cl)(?![\w/])"),
        &t,
        |m| {
            let (a, b, u) = (g(m, 1), g(m, 2), g(m, 3));
            let unit = lookup(unit_of, u)?;
            let dot = if u.ends_with('.') { end_dot(s, end(m)) } else { "" };
            let prep = prep_before(s, start(m));
            if unit == "h"
                && (prep == "o" || prep == "po")
                && b.is_empty()
                && !a.contains(',')
                && (1..=23).contains(&py_int(a))
            {
                let o = ordinal(py_int(a), "f", "loc")?;
                return Some(format!("{o}{dot}"));
            }
            if GEN_PREPS.contains(&prep.as_str()) && !a.contains(',') && !b.contains(',') {
                let x = card(py_int(a), "gen", "f")?;
                let y = if b.is_empty() { None } else { Some(card(py_int(b), "gen", "f")?) };
                let last = if b.is_empty() { a } else { b };
                let noun = if last == "1" { lookup(gen_sg, unit)? } else { lookup(gen_pl, unit)? };
                let mid = match y {
                    Some(y) => format!(" až {y}"),
                    None => String::new(),
                };
                return Some(format!("{x}{mid} {noun}{dot}"));
            }
            if !b.is_empty() {
                return Some(format!("{} až {}{dot}", words(a, "sk"), unit_words(b, unit)));
            }
            Some(format!("{}{dot}", unit_words(a, unit)))
        },
    )
}

fn roman(s: &str) -> u128 {
    let v = |ch: char| -> i64 {
        match ch {
            'I' => 1,
            'V' => 5,
            'X' => 10,
            'L' => 50,
            'C' => 100,
            _ => 0,
        }
    };
    let cs: Vec<char> = s.chars().collect();
    let mut total: i64 = 0;
    for (i, &ch) in cs.iter().enumerate() {
        let nxt = cs.get(i + 1).map_or(0, |&x| v(x));
        total += if nxt > v(ch) { -v(ch) } else { v(ch) };
    }
    total.max(0) as u128
}

fn sk_century(t: String, c: &mut Ctx) -> String {
    let case_of: &[(&str, &str)] =
        &[("storočie", "nom"), ("storočia", "gen"), ("storočí", "loc"), ("storočím", "ins"), ("storočiu", "dat")];
    c.sub(
        &rx(r"\b(X{0,2}(?:IX|IV|VI{0,3}|I{1,3})|X{1,2})\.? (storočie|storočia|storočí|storočím|storočiu)\b"),
        &t,
        |m| {
            let n = roman(g(m, 1));
            if !(1..=21).contains(&n) {
                return None;
            }
            let o = ordinal(n, "n", lookup(case_of, g(m, 2))?)?;
            Some(format!("{o} {}", g(m, 2)))
        },
    )
}

fn sk_decade(t: String, c: &mut Ctx) -> String {
    let case_of: &[(&str, &str)] =
        &[("roky", "nom"), ("rokov", "gen"), ("rokoch", "loc"), ("rokmi", "ins"), ("rokom", "dat")];
    c.sub(
        &rx(r"(?<![\w.,])((?:[1-9]0)\.(?:(?:,| a| i| alebo| až|–|-) ?[1-9]0\.)*) (roky|rokov|rokoch|rokmi|rokom)\b"),
        &t,
        |m| {
            let (chain, noun) = (g(m, 1), g(m, 2));
            let case = lookup(case_of, noun)?;
            let out = sub_plain(&rx(r"(\d0)\."), chain, |d| {
                Some(ordinal(py_int(g(d, 1)), "pl", case).unwrap_or_else(|| g(d, 0).to_string()))
            });
            Some(format!("{out} {noun}"))
        },
    )
}

/// (gender, case) of the word after an ordinal: the noun table first, then an ending that shows it, else None.
fn noun_form(w: &str, prep: &str) -> Option<(&'static str, &'static str)> {
    let gen_p = GEN_PREPS.contains(&prep);
    let loc_p = LOC_OR_ACC.contains(&prep) || LOC_PREPS.contains(&prep);
    let empty = Vec::new();
    let cands = ORD_FORMS.get(w).unwrap_or(&empty);
    let want = if gen_p {
        Some("gen")
    } else if loc_p {
        Some("loc")
    } else if INS_PREPS.contains(&prep) {
        Some("ins")
    } else {
        None
    };
    for &(gender, case) in cands {
        if Some(case) == want {
            return Some((gender, case));
        }
    }
    if !cands.is_empty() && prep.is_empty() {
        for &(gender, case) in cands {
            if case == "nom" {
                return Some((gender, case));
            }
        }
        return None;
    }
    if !cands.is_empty() {
        for &(gender, case) in cands {
            if case == "acc" && ["na", "za", "pre", "cez", "v", "vo", "o", "po"].contains(&prep) {
                return Some((gender, case));
            }
        }
        return None;
    }
    if search(r"(?:ého|eho)$", w) {
        return Some(("m", "gen"));
    }
    if search(r"(?:ému|emu)$", w) {
        return Some(("m", "dat"));
    }
    if search(r"(?:ými|ymi)$", w) {
        return Some(("pl", "ins"));
    }
    if search(r"(?:ým|ym)$", w) {
        return Some(("m", "ins"));
    }
    if search(r"(?:ých|ych)$", w) {
        return Some(("pl", "gen"));
    }
    if nchars(w) >= 4 && search(r"(?:ách|och|iach)$", w) {
        return Some(("pl", "loc"));
    }
    if w.ends_with("ou") {
        return Some(("f", "ins"));
    }
    if w.ends_with('ú') && nchars(w) >= 4 && ["na", "za", "pre", "cez", "v", "vo", "o", "po"].contains(&prep) {
        return Some(("f", "acc"));
    }
    if w.ends_with('á') && nchars(w) >= 4 && prep.is_empty() {
        return Some(("f", "nom"));
    }
    if w.ends_with("ej") && gen_p {
        return Some(("f", "gen"));
    }
    if w.ends_with("ej") && loc_p {
        return Some(("f", "loc"));
    }
    None
}

fn sk_ordinal(t: String, c: &mut Ctx) -> String {
    let s: &str = &t;
    c.sub(&rx(&format!(r"(?<![\w.,])(\d{{1,3}})\. ?((?=[{LOWER}])[^\W\d_]+)")), &t, |m| {
        let (n, w) = (py_int(g(m, 1)), g(m, 2));
        let line = s[..start(m)].rsplit('\n').next().unwrap_or("");
        if py_strip(line).is_empty() {
            return None;
        }
        let mut prep = prep_before(s, start(m));
        if !is_prep(&prep) {
            prep = String::new();
        }
        let (gender, case) = noun_form(&w.to_lowercase(), &prep)?;
        if gender == "m" && (case == "nom" || case == "acc") {
            return None;
        }
        let o = ordinal(n, gender, case)?;
        Some(format!("{o} {w}"))
    })
}

fn sk_half(t: String, c: &mut Ctx) -> String {
    let units: &[(&str, &str)] = &[
        ("l", "litra"),
        ("ml", "mililitra"),
        ("dl", "decilitra"),
        ("kg", "kilogramu"),
        ("g", "gramu"),
        ("dkg", "dekagramu"),
        ("m", "metra"),
        ("cm", "centimetra"),
        ("km", "kilometra"),
        ("h", "hodiny"),
        ("hod.", "hodiny"),
        ("min", "minúty"),
        ("min.", "minúty"),
    ];
    let stop = ["alebo", "až", "sú", "je", "to", "nich", "toho", "nás", "vás", "časť"];
    c.sub(&rx(r"(?<![\d/.,])(?:(\d+) )?1/([24])(?![\d/]) (hod\.|min\.|[^\W\d_]+)"), &t, |m| {
        let (whole, den, noun) = (g(m, 1), g(m, 2), g(m, 3));
        let word = match lookup(units, noun) {
            Some(w) => w,
            None => {
                if nchars(noun) < 3 || stop.contains(&noun.to_lowercase().as_str()) || !full(r"[^\W\d_]+", noun) {
                    return None;
                }
                noun
            }
        };
        if !whole.is_empty() {
            if den != "2" {
                return None;
            }
            let fem = word.ends_with('y') || word.ends_with('e');
            let w = match whole {
                "1" => "jeden".to_string(),
                "2" => (if fem { "dve" } else { "dva" }).to_string(),
                _ => words(whole, "sk"),
            };
            return Some(format!("{w} a pol {word}"));
        }
        Some(format!("{}{word}", if den == "2" { "pol " } else { "štvrť " }))
    })
}

fn sk_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"\b([Vv]o?) r\. (?=\d{4}\b)"), &t, r"\1 roku ");
    let t = c.sub_tpl(&rx(r"(?<![\w.])r\. (?=\d{4}\b)"), &t, "roku ");
    let t = c.sub_tpl(&rx(r"\b(Ing\.) arch\."), &t, r"\1 architekt");
    let t =
        c.sub_tpl(&rx(&format!(r"\b(?:MU|MV|JU|Ph|RN|Paed|Pharm|Th)Dr\.(?= [{UPPER}]\w*(?:ová|á)\b)")), &t, "doktorka");
    let table: &[(&str, &str)] = &[
        ("ul.", "ulica"),
        ("nám.", "námestie"),
        ("tj.", "to jest"),
        ("tzn.", "to znamená"),
        ("a pod.", "a podobne"),
        ("atp.", "a tak podobne"),
        ("príp.", "prípadne"),
        ("kap.", "kapitola"),
        ("obr.", "obrázok"),
        ("tab.", "tabuľka"),
        ("pozn.", "poznámka"),
        ("cca", "cirka"),
        ("csc.", "cé es cé"),
    ];
    let s: &str = &t;
    c.sub(
        &rx(r"(?<![\w.])([Uu]l\.|[Nn]ám\.|[Tt]j\.|[Tt]zn\.|a pod\.|atp\.|[Pp]ríp\.|[Kk]ap\.(?= \d)|[Oo]br\.(?= \d)|[Tt]ab\.(?= \d)|[Pp]ozn\.|[Cc]ca|CSc\.)(?!\w)"),
        &t,
        |m| {
            let a = g(m, 1);
            let key = a.to_lowercase();
            let out = lookup(table, &key)?;
            let lower = a.chars().next().is_some_and(char::is_lowercase);
            let out = if lower || key == "csc." { out.to_string() } else { py_capitalize(out) };
            let dot = if a.ends_with('.') { line_end(s, end(m)) } else { "" };
            Some(format!("{out}{dot}"))
        },
    )
}

/// m/f for 1 in an oblique case, from the noun's singular ending (koruny -> f, roka -> m), else None.
fn one_gender(noun: &str, case: &str) -> Option<&'static str> {
    let last = noun.chars().next_back()?;
    match case {
        "gen" => {
            if noun.ends_with('y') || noun.ends_with("ie") {
                Some("f")
            } else if "ua".contains(last) {
                Some("m")
            } else {
                None
            }
        }
        "ins" => {
            if noun.ends_with("ou") {
                Some("f")
            } else if noun.ends_with("om") {
                Some("m")
            } else {
                None
            }
        }
        _ => None,
    }
}

/// The cardinal before a nominative/accusative noun in its gender and animacy (dve sestry, dvoch bratov).
fn nominative(n: u128, noun: &str, prep: &str) -> Option<String> {
    if nchars(noun) < 3 {
        return None;
    }
    let last = n % 10;
    if n == 1 {
        if FEM_SG_SET.contains(noun) && !MASC_A.contains(&noun) {
            return Some("jedna".into());
        }
        if let Some(stem) = noun.strip_suffix('u')
            && FEM_SG_SET.contains(format!("{stem}a").as_str())
            && ["", "pre", "cez", "za", "na", "o"].contains(&prep)
        {
            return Some("jednu".into());
        }
        if NEUT_SG_SET.contains(noun) || (noun.ends_with("um") && nchars(noun) >= 5) {
            return Some("jedno".into());
        }
        return None;
    }
    if n >= 100 || n % 100 == 12 {
        return None;
    }
    if (2..=4).contains(&n) {
        if ANIM_NOM_SET.contains(noun) {
            return Some((["dvaja", "traja", "štyria"][(n - 2) as usize]).to_string());
        }
        if ANIM_GEN.contains(&noun) || (noun.ends_with("ov") && nchars(noun) >= 4) {
            return Some((["dvoch", "troch", "štyroch"][(n - 2) as usize]).to_string());
        }
    }
    if last == 2 && n != 12 {
        if ANIM_NOM_SET.contains(noun) {
            return None;
        }
        if FEM_NEUT_PL_SET.contains(noun) {
            let sp = words(&n.to_string(), "sk");
            if let Some(stem) = sp.strip_suffix("dva") {
                return Some(format!("{stem}dve"));
            }
        }
    }
    None
}

fn sk_number_case(t: String, c: &mut Ctx) -> String {
    let s: &str = &t;
    c.sub(
        &rx(&format!(
            r"(?<![\w.,:/+\-−])(\d{{1,3}}(?:[ \xa0]\d{{3}})+|\d+)(?![\d]|[.,:/]\d|-|\.\s?[\d{LOWER}])(?:( ?)([^\s\d][^\s]*))?"
        )),
        &t,
        |m| {
            let (num, sp, tok) = (g(m, 1), g(m, 2), g(m, 3));
            let n = py_int(&num.replace([' ', '\u{a0}'], ""));
            if n == 0 {
                return None;
            }
            let prep = prep_before(s, start(m));
            let mut word = tok.trim_end_matches(|ch| TRAIL.contains(ch));
            let mut trail = tok[word.len()..].to_string();
            let lw = word.to_lowercase();
            if full(&format!(r"(?:roku|rok|roka|r)|{MONTHS_GEN}"), &lw) {
                return None;
            }
            let mut unit = if !word.is_empty() && (!sp.is_empty() || !matches_at_start(LETTER, word)) {
                unit_gen(word)
            } else {
                None
            };
            if unit.is_none() && tok != word && tok.ends_with('.') && full(r"[^\W\d_]+\.", tok) {
                unit = unit_gen(tok);
                if unit.is_some() {
                    word = tok;
                    trail = end_dot(s, end(m)).to_string();
                }
            }
            if !word.is_empty() && sp.is_empty() && unit.is_none() && matches_at_start(LETTER, word) {
                return None;
            }
            let mut noun = if unit.is_none() && !word.is_empty() && full(r"[^\W\d_]+", word) {
                lw.clone()
            } else {
                String::new()
            };
            if ["do", "a", "až", "alebo", "či"].contains(&noun.as_str()) {
                let nxt = noun_after(s, m.get(1)?.end());
                if full(MONTHS_GEN, &nxt) {
                    return None;
                }
                noun = if full(r"roku|r", &nxt) { String::new() } else { nxt };
            }
            let p = prep.as_str();
            let case = if GEN_PREPS.contains(&p) {
                Some("gen")
            } else if DAT_PREPS.contains(&p) {
                Some("dat")
            } else if LOC_PREPS.contains(&p) {
                Some("loc")
            } else if INS_PREPS.contains(&p) {
                if unit.is_none() { Some("ins") } else { None }
            } else {
                let mut cs = if noun.is_empty() { None } else { suffix_case(&noun) };
                if cs.is_none() && ["pred", "medzi", "nad", "pod"].contains(&p) && noun.ends_with("mi") {
                    cs = Some("ins");
                }
                cs
            };
            let mut rest = if tok.is_empty() { String::new() } else { format!("{sp}{tok}") };
            if let Some(case) = case {
                if let Some(u) = &unit {
                    if case != "gen" || n == 1 {
                        return None;
                    }
                    rest = format!(" {u}{trail}");
                }
                let mut gender = "m";
                if n == 1 {
                    gender = one_gender(&noun, case)?;
                }
                let w = card(n, case, gender)?;
                return Some(format!("{w}{rest}"));
            }
            if unit.is_some() || noun.is_empty() || !word.chars().next().is_some_and(char::is_lowercase) {
                return None;
            }
            let w = nominative(n, &noun, if is_prep(p) { p } else { "" })?;
            Some(format!("{w}{rest}"))
        },
    )
}

fn sk_weekdays(t: String, c: &mut Ctx) -> String {
    let day: &[(&str, &str)] = &[
        ("po", "pondelok"),
        ("ut", "utorok"),
        ("st", "streda"),
        ("št", "štvrtok"),
        ("pi", "piatok"),
        ("so", "sobota"),
        ("ne", "nedeľa"),
    ];
    let s: &str = &t;
    c.sub(&rx(r"(?i)(?<![\w.])(po|ut|st|št|pi|so|ne)\.? ?[–-] ?(po|ut|st|št|pi|so|ne)(\.)?(?!\w)"), &t, |m| {
        let a = lookup(day, &g(m, 1).to_lowercase())?;
        let b = lookup(day, &g(m, 2).to_lowercase())?;
        let dot = if g(m, 3).is_empty() { "" } else { line_end(s, end(m)) };
        if a == b { None } else { Some(format!("{a} až {b}{dot}")) }
    })
}

fn sk_vocalize(t: String, c: &mut Ctx) -> String {
    let num = r"(?:sedem|siedm\w*|šesť|šiest\w*|štyri|štyroch|štyrom|štyrmi|štrnásť|štrnást\w*|štyridsať|štyridsiat\w*|šesťdesiat\w*|sedemdesiat\w*|sedemnásť|sedemnást\w*|šestnásť|šestnást\w*)";
    c.sub_tpl(&rx(&format!(r"(?<![\w.])([SsZz]) (?={num}\b)")), &t, r"\1o ")
}

// ============================================================================== money and big numbers (Nov 16 b)

/// Currencies the grammar reads after an amount.
const MONEY_CUR: &str = r"€|EUR|\$|USD|£|GBP|CHF|Kč|CZK|PLN|zł|UAH|₴|RUB|₽|TRY|₺|JPY|¥";
const MONEY_SIGN: &str = r"[€$£¥₽₴₺]";
const GROUPED: &str = r"\d{1,3}(?:[ \xa0]\d{3})+|\d+";

fn sk_money_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<=\d)((?:[ \xa0]?(?:{MONEY_CUR}))?) ?~ ?(?={MONEY_SIGN}?\d)")), &t, r"\1-");
    let t = c.sub(
        &rx(&format!(
            r"(?<![\w.,])({MONEY_SIGN})(\d+(?:,\d{{1,2}})?)[-–](\d+(?:,\d{{1,2}})?)(?![\d,.]?\d|[ \xa0]?(?:tis|mil|mld|{MONEY_CUR})(?!\w)|[ \xa0]\d)"
        )),
        &t,
        |m| Some(format!("{}-{} {}", g(m, 2), g(m, 3), g(m, 1))),
    );
    let t = c.sub(
        &rx(&format!(r"(?<![\w.,])(\d+(?:,\d{{1,2}})?)[ \xa0]?({MONEY_CUR})[-–](\d+(?:,\d{{1,2}})?)[ \xa0]?\2(?!\w)")),
        &t,
        |m| Some(format!("{}-{} {}", g(m, 1), g(m, 3), g(m, 2))),
    );
    c.sub_tpl(&rx(r"(?<![\w.,~\d])~ ?(?=\d)"), &t, "približne ")
}

/// The digits of `s` as a number (`int(re.sub(r"\D", "", s))`).
fn digits_int(s: &str) -> u128 {
    py_int(&digits_of(s))
}

/// `re.sub(r"\D", "", s)`.
fn digits_of(s: &str) -> String {
    s.chars().filter(char::is_ascii_digit).collect()
}

/// 12345678 -> "12 345 678".
fn group3(n: u128) -> String {
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

/// `frac.ljust(2, "0")` as a number.
fn cents_of(frac: &str) -> u128 {
    py_int(&format!("{frac:0<2}"))
}

/// Scale words above a million: (div, the word for 1, the form after 2-4, the form after 5+, gender).
const SK_SCALES: &[(u128, &str, &str, &str, &str)] = &[
    (1_000_000_000_000, "jeden bilión", "bilióny", "biliónov", "m"),
    (1_000_000_000, "jedna miliarda", "miliardy", "miliárd", "f"),
];

/// 2, 3, 4 in a gender (dva/dve, tri, štyri).
fn two_to_four(n: u128, gender: &str) -> &'static str {
    match n {
        2 if gender == "f" => "dve",
        2 => "dva",
        3 => "tri",
        _ => "štyri",
    }
}

/// The cardinal n (up to 999 999 999 999 999): billions and trillions by these rules, the rest by the grammar.
fn sk_number(n: u128) -> String {
    let mut parts: Vec<String> = Vec::new();
    for &(div, one, few, many, gender) in SK_SCALES {
        let gv = n / div % 1000;
        if gv == 0 {
            continue;
        }
        if gv == 1 {
            parts.push(one.to_string());
        } else if (2..=4).contains(&gv) {
            parts.push(format!("{} {few}", two_to_four(gv, gender)));
        } else {
            parts.push(format!("{} {many}", words(&gv.to_string(), "sk")));
        }
    }
    if n % 1_000_000_000 > 0 {
        parts.push(words(&group3(n % 1_000_000_000), "sk"));
    }
    parts.join(" ")
}

fn sk_big_number(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&format!(
            r"(?<![\w.,:/+\-−])([€$£] ?)?(\d{{1,3}}(?:[ \xa0]\d{{3}}){{3,4}}|[1-9]\d{{0,2}}0{{9}}(?:000)?)(,\d{{2}})?(?![\d]|[.,:/]\d|[ \xa0]\d)(?:[ \xa0]?({MONEY_CUR}|HUF|Ft|SEK|NOK|DKK|CNY|km|kg|m|t|l|g|ha)(?!\w))?"
        )),
        &t,
        |m| {
            let (sign, num, cents, tok) = (py_strip(g(m, 1)), g(m, 2), g(m, 3), g(m, 4));
            if !sign.is_empty() && !tok.is_empty() {
                return None;
            }
            let n = digits_int(num);
            if !(1_000_000_000..1_000_000_000_000_000).contains(&n) {
                return None;
            }
            let cur = if sign.is_empty() { tok } else { sign };
            if !cents.is_empty() && !full(MONEY_CUR, cur) {
                return None;
            }
            let mut mine = sk_number(n);
            let mut plain = format!("{sign}{}{cents}", group3(n));
            if !cur.is_empty() {
                let genw = unit_gen(cur)?;
                let rest = n % 1_000_000_000;
                let money = full(MONEY_CUR, cur);
                if rest > 0 {
                    let tail = if money {
                        format!("{sign}{}{cents}{}", group3(rest), if tok.is_empty() { String::new() } else { format!(" {tok}") })
                    } else {
                        format!("{rest} {tok}")
                    };
                    mine = format!("{} {}", sk_number(n - rest), words(&tail, "sk"));
                } else {
                    mine = format!("{mine} {genw}");
                    if !cents.is_empty() {
                        mine = format!("{mine} {}", words(&format!("0{cents} {cur}"), "sk"));
                    }
                }
                if !tok.is_empty() {
                    plain = format!("{plain} {tok}");
                }
            }
            if search(r"\d", &mine) || words(&plain, "sk") == mine {
                return None;
            }
            Some(mine)
        },
    )
}

fn sk_groups_unit(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(r"(?<![\w.,:/+\-−])(\d{1,3}(?:[ \xa0]\d{3}){1,2})(?![\d]|[.,:/]\d|[ \xa0]\d)[ \xa0]?([^\W\d_][^\s.,;:!?)]*|%|°C)(?!\w)"),
        &t,
        |m| {
            let (num, tok) = (g(m, 1), g(m, 2));
            if full(MONEY_CUR, tok) || unit_gen(tok).is_none() {
                return None;
            }
            let plain = digits_of(num);
            if words(&format!("{num} {tok}"), "sk") == words(&format!("{plain} {tok}"), "sk") {
                return None;
            }
            Some(format!("{plain} {tok}"))
        },
    )
}

/// A slash after an amount: the denominators the grammar leaves unread.
const PER_UNIT: &[(&str, &str)] = &[
    ("mesiac", "mesačne"),
    ("mes.", "mesačne"),
    ("mes", "mesačne"),
    ("deň", "denne"),
    ("rok", "ročne"),
    ("týždeň", "týždenne"),
    ("hod.", "za hodinu"),
    ("hod", "za hodinu"),
    ("h", "za hodinu"),
    ("ks", "za kus"),
    ("os.", "za osobu"),
    ("osobu", "za osobu"),
    ("noc", "za noc"),
    ("m²", "za meter štvorcový"),
    ("m2", "za meter štvorcový"),
    ("m³", "za meter kubický"),
    ("m3", "za meter kubický"),
    ("kWh", "za kilowatthodinu"),
    ("kg", "za kilogram"),
    ("km", "za kilometer"),
    ("ha", "za hektár"),
    ("min", "za minútu"),
    ("l", "za liter"),
    ("t", "za tonu"),
    ("g", "za gram"),
    ("m", "za meter"),
];

/// `|`-joined escaped keys, longest first (ties in table order).
fn alternation(keys: &[&str]) -> String {
    let mut ks: Vec<&str> = keys.to_vec();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    ks.iter().map(|k| super::super::re_escape(k)).collect::<Vec<_>>().join("|")
}

fn sk_per_unit(t: String, c: &mut Ctx) -> String {
    let dens = alternation(&PER_UNIT.iter().map(|kv| kv.0).collect::<Vec<_>>());
    let t = c.sub(&rx(&format!(r"(?<![\w.,])({MONEY_SIGN})({GROUPED}(?:,\d{{1,2}})?)/(?=\w)")), &t, |m| {
        Some(format!("{} {}/", g(m, 2), g(m, 1)))
    });
    let s: &str = &t;
    c.sub(&rx(&format!(r"(?<=\d)([ \xa0]?(?:{MONEY_CUR}|HUF|Ft))/({dens})(?![\w²³])")), &t, |m| {
        let den = g(m, 2);
        let dot = if den.ends_with('.') { end_dot(s, end(m)) } else { "" };
        Some(format!("{} {}{dot}", g(m, 1), lookup(PER_UNIT, den)?))
    })
}

fn sk_hectare(t: String, c: &mut Ctx) -> String {
    let s: &str = &t;
    c.sub(&rx(&format!(r"(?<![\w.,])({GROUPED})(,\d+)?[ \xa0]?(ha|km²)(?![\w²])")), &t, |m| {
        let (num, frac, unit) = (g(m, 1), g(m, 2), g(m, 3));
        let plain = digits_of(num);
        let n = py_int(&plain);
        if unit != "ha" {
            // km²: the number is written too (the grammar says “km na druhú”)
            if !frac.is_empty() {
                return Some(format!("{plain}{frac} štvorcového kilometra"));
            }
            let p = prep_before(s, start(m));
            if GEN_PREPS.contains(&p.as_str()) {
                let w = card(n, "gen", "m")?;
                return Some(format!(
                    "{w} {}",
                    if n == 1 { "štvorcového kilometra" } else { "štvorcových kilometrov" }
                ));
            }
            if DAT_PREPS.contains(&p.as_str()) || LOC_PREPS.contains(&p.as_str()) || INS_PREPS.contains(&p.as_str()) {
                return None;
            }
            let out = counted(n, &["štvorcový kilometer", "štvorcové kilometre", "štvorcových kilometrov", "m"]);
            return if search(r"\d", &out) { None } else { Some(out) };
        }
        if !frac.is_empty() {
            return Some(format!("{plain}{frac} hektára"));
        }
        if n == 1 {
            return Some("jeden hektár".to_string());
        }
        Some(format!("{plain} {}", if (2..=4).contains(&n) { "hektáre" } else { "hektárov" }))
    })
}

/// Currencies the grammar leaves unread: forms after 1, after 2-4, after 5+, gender.
const OTHER_CUR: &[(&str, [&str; 4])] = &[
    ("HUF", ["forint", "forinty", "forintov", "m"]),
    ("Ft", ["forint", "forinty", "forintov", "m"]),
    ("SEK", ["švédska koruna", "švédske koruny", "švédskych korún", "f"]),
    ("NOK", ["nórska koruna", "nórske koruny", "nórskych korún", "f"]),
    ("DKK", ["dánska koruna", "dánske koruny", "dánskych korún", "f"]),
    ("CNY", ["jüan", "jüany", "jüanov", "m"]),
];
/// Their genitive singular (od jedného forintu).
const OTHER_GEN_SG: &[(&str, &str)] = &[
    ("HUF", "forintu"),
    ("Ft", "forintu"),
    ("SEK", "švédskej koruny"),
    ("NOK", "nórskej koruny"),
    ("DKK", "dánskej koruny"),
    ("CNY", "jüanu"),
];
/// The hundredths of the złoty and the hryvnia (the grammar says centov).
const MINOR: &[(&str, [&str; 4])] = &[
    ("PLN", ["groš", "groše", "grošov", "m"]),
    ("zł", ["groš", "groše", "grošov", "m"]),
    ("UAH", ["kopejka", "kopejky", "kopejok", "f"]),
    ("₴", ["kopejka", "kopejky", "kopejok", "f"]),
];

/// n before a noun of `gender` (jeden/jedna, dva/dve, tri, štyri, päť …).
fn number_words(n: u128, gender: &str) -> String {
    if n == 1 {
        return (if gender == "f" { "jedna" } else { "jeden" }).to_string();
    }
    if (2..=4).contains(&n) {
        return two_to_four(n, gender).to_string();
    }
    if n >= 1_000_000_000 { sk_number(n) } else { words(&group3(n), "sk") }
}

/// n and the noun in the form it needs (jeden forint, dve koruny, päť korún).
fn counted(n: u128, forms: &[&str; 4]) -> String {
    let [sg, few, many, gender] = *forms;
    let noun = if n == 1 {
        sg
    } else if (2..=4).contains(&n) {
        few
    } else {
        many
    };
    format!("{} {noun}", number_words(n, gender))
}

fn sk_money_words(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = OTHER_CUR.iter().chain(MINOR.iter()).map(|kv| kv.0).collect();
    let codes = alternation(&keys);
    let s: &str = &t;
    let t2 = c.sub(
        &rx(&format!(r"(?<![\w.,\-–])(?:(\d+)[-–](?=\d))?({GROUPED})(?:,(\d{{1,2}}))?[ \xa0]?({codes})(?!\w)")),
        &t,
        |m| {
            let (num, code) = (g(m, 2), g(m, 4));
            let p = prep_before(s, start(m));
            let gen_p = GEN_PREPS.contains(&p.as_str());
            let oblique = gen_p
                || DAT_PREPS.contains(&p.as_str())
                || LOC_PREPS.contains(&p.as_str())
                || INS_PREPS.contains(&p.as_str());
            let n = digits_int(num);
            if let Some(minor) = MINOR.iter().find(|kv| kv.0 == code) {
                let frac = m.get(3)?.as_str();
                if m.get(1).is_some() || oblique {
                    return None;
                }
                let cents = cents_of(frac);
                let out = words(&format!("{num} {code}"), "sk");
                if cents == 0 || search(r"\d", &out) || out.ends_with(code) {
                    return None;
                }
                return Some(format!("{out} {}", counted(cents, &minor.1)));
            }
            let forms = &OTHER_CUR.iter().find(|kv| kv.0 == code)?.1;
            if let Some(a) = m.get(1) {
                // a range: N až M and the noun agreeing with M (päť až desať forintov)
                let na = py_int(a.as_str());
                if m.get(3).is_some() || na >= n || oblique {
                    return None;
                }
                let out = format!("{} až {}", number_words(na, forms[3]), counted(n, forms));
                return if search(r"\d", &out) { None } else { Some(out) };
            }
            if gen_p && m.get(3).is_none() {
                let w = card(n, "gen", forms[3])?;
                let noun = if n == 1 { lookup(OTHER_GEN_SG, code)? } else { forms[2] };
                return Some(format!("{w} {noun}"));
            }
            if oblique {
                return None;
            }
            let mut out = counted(n, forms);
            if let Some(frac) = m.get(3) {
                let cents = cents_of(frac.as_str());
                if cents > 0 {
                    out = format!("{out} {}", words(&cents.to_string(), "sk"));
                }
            }
            if search(r"\d", &out) { None } else { Some(out) }
        },
    );
    // after a number sk.number-case wrote in the genitive (od 5 HUF → od piatich HUF): the genitive of the currency
    let mut gen_words: Vec<&str> = CARD.iter().map(|kv| kv.1.split_whitespace().next().unwrap_or("")).collect();
    gen_words.extend(["jedného", "jednej", "tisíc"]);
    gen_words.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    gen_words.dedup();
    let alt = gen_words.join("|");
    let other_codes = alternation(&OTHER_CUR.iter().map(|kv| kv.0).collect::<Vec<_>>());
    let s2: &str = &t2;
    c.sub(&rx(&format!(r"(?<!\w)({alt}) ({other_codes})(?!\w)")), &t2, |m| {
        let head = sub_plain(&rx(&format!(r"(?:(?<!\w)(?:{alt}) )+$")), &s2[..start(m)], |_| Some(String::new()));
        if !GEN_PREPS.contains(&prep_before(&head, head.len()).as_str()) {
            return None;
        }
        let code = g(m, 2);
        let w = g(m, 1);
        let noun = if w == "jedného" || w == "jednej" {
            lookup(OTHER_GEN_SG, code)?
        } else {
            OTHER_CUR.iter().find(|kv| kv.0 == code)?.1[2]
        };
        Some(format!("{w} {noun}"))
    })
}

fn sk_grouped_decimal(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&format!(
            r"(?<![\w.,:/+\-−])(\d{{1,3}}(?:[ \xa0]\d{{3}})+),(\d+)(?![\d])(?![ \xa0]?(?:{MONEY_CUR})(?!\w))"
        )),
        &t,
        |m| Some(format!("{},{}", digits_of(g(m, 1)), g(m, 2))),
    )
}
