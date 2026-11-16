//! 'cs' rules: the port of the workbench's `langrules/cs.py` (ids `cs.*`).
//!
//! The grammar reads every number in the nominative, says 1 as “jedna” and 2 as “dva” whatever the noun, and every
//! ordinal in the masculine nominative. These rules write the number words themselves where the context fixes
//! another form, and vocalize the preposition before them (ve, se, ze, ke).

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, chars_after, chars_before, full, g, matches_at_start, py_int, rx, search, sub_plain, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::{py_capitalize, py_split_ws, py_strip};

pub(super) const RULES: &[LangRule] = &[
    ("cs.minus", cs_minus),
    ("cs.scale", cs_scale),
    ("cs.time", cs_time),
    ("cs.hours", cs_hours),
    ("cs.date", cs_date),
    ("cs.century", cs_century),
    ("cs.decade", cs_decade),
    ("cs.ordinal", cs_ordinal),
    ("cs.half", cs_half),
    ("cs.percent", cs_percent),
    ("cs.abbrev", cs_abbrev),
    ("cs.number-case", cs_number_case),
    ("cs.money", cs_money),
    ("cs.weekdays", cs_weekdays),
    ("cs.vocalize", cs_vocalize),
];

const LETTER: &str = r"[^\W\d_]";
const CASES: [&str; 4] = ["gen", "dat", "loc", "ins"];

/// A cardinal word in the nominative -> its genitive, dative, locative, instrumental.
const CARD: &[(&str, &str)] = &[
    ("dva", "dvou dvěma dvou dvěma"),
    ("dvě", "dvou dvěma dvou dvěma"),
    ("tři", "tří třem třech třemi"),
    ("čtyři", "čtyř čtyřem čtyřech čtyřmi"),
    ("pět", "pěti pěti pěti pěti"),
    ("šest", "šesti šesti šesti šesti"),
    ("sedm", "sedmi sedmi sedmi sedmi"),
    ("osm", "osmi osmi osmi osmi"),
    ("devět", "devíti devíti devíti devíti"),
    ("deset", "deseti deseti deseti deseti"),
    ("jedenáct", "jedenácti jedenácti jedenácti jedenácti"),
    ("dvanáct", "dvanácti dvanácti dvanácti dvanácti"),
    ("třináct", "třinácti třinácti třinácti třinácti"),
    ("čtrnáct", "čtrnácti čtrnácti čtrnácti čtrnácti"),
    ("patnáct", "patnácti patnácti patnácti patnácti"),
    ("šestnáct", "šestnácti šestnácti šestnácti šestnácti"),
    ("sedmnáct", "sedmnácti sedmnácti sedmnácti sedmnácti"),
    ("osmnáct", "osmnácti osmnácti osmnácti osmnácti"),
    ("devatenáct", "devatenácti devatenácti devatenácti devatenácti"),
    ("dvacet", "dvaceti dvaceti dvaceti dvaceti"),
    ("třicet", "třiceti třiceti třiceti třiceti"),
    ("čtyřicet", "čtyřiceti čtyřiceti čtyřiceti čtyřiceti"),
    ("padesát", "padesáti padesáti padesáti padesáti"),
    ("šedesát", "šedesáti šedesáti šedesáti šedesáti"),
    ("sedmdesát", "sedmdesáti sedmdesáti sedmdesáti sedmdesáti"),
    ("osmdesát", "osmdesáti osmdesáti osmdesáti osmdesáti"),
    ("devadesát", "devadesáti devadesáti devadesáti devadesáti"),
    ("sto", "sta stu stu stem"),
    ("stě", "set stům stech sty"),
    ("sta", "set stům stech sty"),
    ("set", "set stům stech sty"),
    ("tisíce", "tisíc tisícům tisících tisíci"),
    ("miliony", "milionů milionům milionech miliony"),
    ("milionů", "milionů milionům milionech miliony"),
    ("milion", "milionu milionu milionu milionem"),
];
/// tisíc is a singular (1000) or a genitive plural (5000): the word before it says which.
const TISIC_SG: &str = "tisíce tisíci tisíci tisícem";
const TISIC_PL: &str = "tisíc tisícům tisících tisíci";
/// 1 on its own: masculine/neuter and feminine forms of each case.
const ONE: &[(&str, &str)] = &[("m", "jednoho jednomu jednom jedním"), ("f", "jedné jedné jedné jednou")];

const FEM_NEUT_PL: &str =
    "sestry dcery matky babičky tety ženy dívky holky kamarádky přítelkyně kolegyně učitelky studentky
osoby hodiny minuty sekundy noci věci knihy stránky strany noviny lekce třídy školy ulice cesty silnice čáry řady
části koruny lžíce lžičky sklenice sklenky šálky porce tablety kapky kávy pizzy housky cibule
mrkve papriky hrušky švestky jahody ryby slepice krávy ovce kozy kočky myši ruce nohy hlavy verze možnosti
metody zásady odpovědi otázky firmy značky ceny hry karty písně pohádky scény série kategorie skupiny rodiny
ložnice koupelny kuchyně lampy skříně stěny mapy tašky bundy košile čepice tuny kalorie míle návštěvy splátky
dávky změny války šance prosby poznámky děti vejce auta města okna jablka kola piva slova kuřata zvířata
náměstí nádraží křesla srdce moře pole";
const NEUT_SG: &str =
    "vejce moře srdce slunce pole kuře zvíře dítě rajče náměstí nádraží století výročí vydání poschodí
setkání jednání místo kolo auto okno město jablko pivo slovo číslo jídlo kino rádio křeslo vajíčko kilo deko euro
tričko kotě štěně pravidlo světlo patro";
const NOT_MASC: &[&str] = &[
    "než", "pak", "tak", "jak", "kam", "tam", "sem", "jen", "bez", "pod", "nad", "před", "přes", "dnes", "hned",
    "však", "proč", "jenž", "rád", "jsem", "jsme", "jest", "už", "též", "mezi", "krát",
];
const FEM_CONS: &[&str] = &[
    "noc",
    "věc",
    "kost",
    "řeč",
    "píseň",
    "myš",
    "zeď",
    "sůl",
    "moc",
    "pomoc",
    "tvář",
    "loď",
    "mrkev",
    "postel",
    "kancelář",
    "obec",
    "krev",
    "část",
    "paměť",
    "síť",
    "oběť",
    "daň",
    "lež",
    "dlaň",
    "báseň",
    "čtvrť",
    "kolej",
    "zbraň",
    "láhev",
    "tramvaj",
    "rychlost",
];

static FEM_NEUT_PL_SET: LazyLock<HashSet<&'static str>> =
    LazyLock::new(|| py_split_ws(FEM_NEUT_PL).into_iter().collect());
static NEUT_SG_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| py_split_ws(NEUT_SG).into_iter().collect());

/// Nouns after an ordinal: gender, nominative, genitive, locative, instrumental, accusative singular.
const ORD_NOUNS: &[(&str, &str)] = &[
    ("n", "místo místa místě místem místo"),
    ("n", "patro patra patře patrem patro"),
    ("n", "století století století stoletím století"),
    ("n", "kolo kola kole kolem kolo"),
    ("n", "výročí výročí výročí výročím výročí"),
    ("n", "čtvrtletí čtvrtletí čtvrtletí čtvrtletím čtvrtletí"),
    ("n", "pololetí pololetí pololetí pololetím pololetí"),
    ("n", "vydání vydání vydání vydáním vydání"),
    ("n", "poschodí poschodí poschodí poschodím poschodí"),
    ("n", "setkání setkání setkání setkáním setkání"),
    ("n", "tisíciletí tisíciletí tisíciletí tisíciletím tisíciletí"),
    ("n", "nástupiště nástupiště nástupišti nástupištěm nástupiště"),
    ("m", "ročník ročníku ročníku ročníkem ročník"),
    ("m", "rok roku roce rokem rok"),
    ("m", "den dne dni dnem den"),
    ("m", "týden týdne týdnu týdnem týden"),
    ("m", "měsíc měsíce měsíci měsícem měsíc"),
    ("m", "díl dílu dílu dílem díl"),
    ("m", "stupeň stupně stupni stupněm stupeň"),
    ("m", "krok kroku kroku krokem krok"),
    ("m", "zápas zápasu zápase zápasem zápas"),
    ("m", "sjezd sjezdu sjezdu sjezdem sjezd"),
    ("m", "semestr semestru semestru semestrem semestr"),
    ("m", "bod bodu bodě bodem bod"),
    ("m", "odstavec odstavce odstavci odstavcem odstavec"),
    ("m", "článek článku článku článkem článek"),
    ("m", "svazek svazku svazku svazkem svazek"),
    ("m", "pluk pluku pluku plukem pluk"),
    ("m", "turnaj turnaje turnaji turnajem turnaj"),
    ("m", "festival festivalu festivalu festivalem festival"),
    ("m", "pokus pokusu pokusu pokusem pokus"),
    ("m", "závod závodu závodě závodem závod"),
    ("m", "kongres kongresu kongresu kongresem kongres"),
    ("f", "třída třídy třídě třídou třídu"),
    ("f", "liga ligy lize ligou ligu"),
    ("f", "strana strany straně stranou stranu"),
    ("f", "kapitola kapitoly kapitole kapitolou kapitolu"),
    ("f", "část části části částí část"),
    ("f", "válka války válce válkou válku"),
    ("f", "sezóna sezóny sezóně sezónou sezónu"),
    ("f", "sezona sezony sezoně sezonou sezonu"),
    ("f", "etapa etapy etapě etapou etapu"),
    ("f", "verze verze verzi verzí verzi"),
    ("f", "edice edice edici edicí edici"),
    ("f", "pozice pozice pozici pozicí pozici"),
    ("f", "řada řady řadě řadou řadu"),
    ("f", "příčka příčky příčce příčkou příčku"),
    ("f", "hodina hodiny hodině hodinou hodinu"),
    ("f", "minuta minuty minutě minutou minutu"),
    ("f", "lekce lekce lekci lekcí lekci"),
    ("f", "generace generace generaci generací generaci"),
    ("f", "symfonie symfonie symfonii symfonií symfonii"),
    ("f", "republika republiky republice republikou republiku"),
    ("f", "cena ceny ceně cenou cenu"),
    ("f", "kategorie kategorie kategorii kategorií kategorii"),
    ("f", "divize divize divizi divizí divizi"),
    ("f", "dávka dávky dávce dávkou dávku"),
    ("f", "zastávka zastávky zastávce zastávkou zastávku"),
    ("f", "vlna vlny vlně vlnou vlnu"),
    ("f", "fáze fáze fázi fází fázi"),
    ("f", "polovina poloviny polovině polovinou polovinu"),
    ("f", "kolej koleje koleji kolejí kolej"),
    ("f", "schůze schůze schůzi schůzí schůzi"),
    ("f", "série série sérii sérií sérii"),
    ("f", "dekáda dekády dekádě dekádou dekádu"),
    ("f", "kniha knihy knize knihou knihu"),
    ("f", "mise mise misi misí misi"),
    ("f", "armáda armády armádě armádou armádu"),
    ("f", "brigáda brigády brigádě brigádou brigádu"),
];

static ORD_FORMS: LazyLock<HashMap<&'static str, Vec<(&'static str, &'static str)>>> = LazyLock::new(|| {
    let mut m: HashMap<&'static str, Vec<(&'static str, &'static str)>> = HashMap::new();
    for &(gender, forms) in ORD_NOUNS {
        for (case, w) in ["nom", "gen", "loc", "ins", "acc"].into_iter().zip(py_split_ws(forms)) {
            m.entry(w).or_default().push((gender, case));
        }
    }
    m
});

/// Ordinal endings of a hard (-ý) and a soft (-í) stem by gender: nom gen dat acc ins loc.
const ORD_HARD: &[(&str, &str)] = &[
    ("m", "ý ého ému ý ým ém"),
    ("n", "é ého ému é ým ém"),
    ("f", "á é é ou ou é"),
    ("pl", "é ých ým é ými ých"),
    ("npl", "á ých ým á ými ých"),
];
const ORD_SOFT: &[(&str, &str)] = &[
    ("m", "í ího ímu í ím ím"),
    ("n", "í ího ímu í ím ím"),
    ("f", "í í í í í í"),
    ("pl", "í ích ím í ími ích"),
    ("npl", "í ích ím í ími ích"),
];
const ORD_CASES: [&str; 6] = ["nom", "gen", "dat", "acc", "ins", "loc"];

const GEN_PREPS: &[&str] = &[
    "od",
    "do",
    "z",
    "ze",
    "kolem",
    "okolo",
    "u",
    "bez",
    "během",
    "podle",
    "místo",
    "vedle",
    "kromě",
    "blízko",
    "uprostřed",
    "pomocí",
    "včetně",
    "výši",
    "věku",
    "délce",
    "vzdálenosti",
    "hodnotě",
    "množství",
    "počtu",
    "rozmezí",
];
const DAT_PREPS: &[&str] = &["k", "ke", "díky", "kvůli", "proti", "vůči", "naproti"];
const LOC_PREPS: &[&str] = &["při"];
const INS_PREPS: &[&str] = &["s", "se"];
const LOC_OR_ACC: &[&str] = &["v", "ve", "na", "o", "po"];
const OTHER_PREPS: &[&str] = &["za", "před", "nad", "pod", "mezi", "pro", "přes"];

const MONTHS_GEN: &str = "ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince";
const UPPER: &str = "A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ";
const LOWER: &str = "a-záčďéěíňóřšťúůýž";
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

/// The cardinal n in `case` (gen, dat, loc, ins); `gender` m/f picks the forms of 1.
fn card(n: u128, case: &str, gender: &str) -> Option<String> {
    let i = CASES.iter().position(|c| *c == case)?;
    if n == 1 {
        return lookup(ONE, gender).map(|f| nth(f, i).to_string());
    }
    let mut out: Vec<String> = Vec::new();
    let mut prev = "";
    let spoken = words(&n.to_string(), "cs");
    for w in py_split_ws(&spoken) {
        let forms =
            if w == "tisíc" { Some(if prev.is_empty() { TISIC_SG } else { TISIC_PL }) } else { lookup(CARD, w) };
        out.push(nth(forms?, i).to_string());
        prev = w;
    }
    Some(out.join(" "))
}

/// One ordinal word (masculine nominative: druhý, třetí) in a gender and case; other words stay.
fn ord_word(w: &str, gender: &str, case: &str) -> String {
    let i = ORD_CASES.iter().position(|c| *c == case).unwrap_or(0);
    if let Some(stem) = w.strip_suffix('ý') {
        return format!("{stem}{}", nth(lookup(ORD_HARD, gender).unwrap_or("ý ého ému ý ým ém"), i));
    }
    if let Some(stem) = w.strip_suffix('í') {
        return format!("{stem}{}", nth(lookup(ORD_SOFT, gender).unwrap_or("í ího ímu í ím ím"), i));
    }
    w.to_string()
}

/// The ordinal n (1-999) in a gender and case (dvacátém prvním), or None when the grammar has none.
fn ordinal(n: u128, gender: &str, case: &str) -> Option<String> {
    if !(1..1000).contains(&n) {
        return None;
    }
    let base = words(&format!("{n}."), "cs");
    let ws = py_split_ws(&base);
    let last = *ws.last()?;
    if base.contains('.') || !(last.ends_with('ý') || last.ends_with('í')) {
        return None;
    }
    Some(ws.iter().map(|w| ord_word(w, gender, case)).collect::<Vec<_>>().join(" "))
}

/// '.' when the abbreviation dot that ends at `end` also ends the sentence (end of text or line, or a capital).
fn end_dot(t: &str, end: usize) -> &'static str {
    if matches_at_start(&format!(r"(?:\s*$|\n|\s+[{UPPER}][{LOWER}])"), &t[end..]) { "." } else { "" }
}

/// '.' when the abbreviation dot that ends at `end` is the last thing on its line.
fn line_end(t: &str, end: usize) -> &'static str {
    if matches_at_start(r"(?:\s*$|\n)", &t[end..]) { "." } else { "" }
}

/// The genitive plural the grammar gives a unit or currency after a number (Kč -> korun), or None for a word.
fn unit_gen(tok: &str) -> Option<String> {
    let r = words(&format!("5 {tok}"), "cs");
    let rest = r.strip_prefix("pět ")?;
    if search(r"\d", &r) || rest == tok {
        return None;
    }
    Some(rest.to_string())
}

/// The word before the number at `start`, lowercased, looking past 'N a/až/nebo' (o 5 a 10 kočkách).
fn prep_before(t: &str, start: usize) -> String {
    let win = chars_before(t, start, 40);
    match rx(r"(?:^|[^\w.])(\w+\.?)\s+(?:\d+\s*(?:a|až|nebo|či|,)\s*)?$").captures(win) {
        Ok(Some(m)) => {
            // “rovná se 6” (= in an equation): se is the reflexive pronoun, not the preposition
            if g(&m, 1).to_lowercase() == "se"
                && search(r"(?i)(?:^|[^\w])rovn\w*\s+se\s+(?:\d+\s*(?:a|až|nebo|či|,)\s*)?$", win)
            {
                return String::new();
            }
            g(&m, 1).to_lowercase()
        }
        _ => String::new(),
    }
}

/// The first word after the number at `end`, past 'a/až/nebo/do N' (o 5 a 10 kočkách), lowercased.
fn noun_after(t: &str, end: usize) -> String {
    let win = chars_after(t, end, 60);
    match rx(r"^(?:(?:\s*(?:a|až|nebo|či|do|–|-|,)\s*\d+)*\s*([^\W\d_]+))").captures(win) {
        Ok(Some(m)) => g(&m, 1).to_lowercase(),
        _ => String::new(),
    }
}

/// The case a plural noun's ending shows: -ách/-ech/-ích locative, -ami/-emi/-ími/-mi instrumental, -ům/-ám dative.
fn suffix_case(w: &str) -> Option<&'static str> {
    if nchars(w) < 4 {
        return None;
    }
    if search(r"(?:ách|ech|ích)$", w) {
        return Some("loc");
    }
    if search(r"(?:ami|emi|ími|[dtnň]mi)$", w) {
        return Some("ins");
    }
    if search(r"(?:ům|ám)$", w) {
        return Some("dat");
    }
    None
}

/// N hodina/minuta/sekunda in the nominative with the noun's agreement (dvě hodiny, pět minut).
fn hours(n: &str, word: &str) -> String {
    let forms = match word {
        "h" => ["hodina", "hodiny", "hodin"],
        "min" => ["minuta", "minuty", "minut"],
        _ => ["sekunda", "sekundy", "sekund"],
    };
    if n.contains(',') {
        return format!("{} {}", words(n, "cs"), forms[1]);
    }
    match py_int(n) {
        1 => format!("jedna {}", forms[0]),
        2 => format!("dvě {}", forms[1]),
        3 => format!("tři {}", forms[1]),
        4 => format!("čtyři {}", forms[1]),
        _ => format!("{} {}", words(n, "cs"), forms[2]),
    }
}

fn cs_minus(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\w.,\-−+/])[-−](?=\d)"), &t, "minus ")
}

fn cs_scale(t: String, c: &mut Ctx) -> String {
    let scales: &[(&str, (&str, &str))] =
        &[("tis", ("000", "tisíce")), ("mil", ("000 000", "milionu")), ("mld", ("000 000 000", "miliardy"))];
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
        Some(format!("{} {gen_sg}{dot}", words(num, "cs")))
    });
    c.sub(&rx(r"\b((?:tisíce|milionu|miliardy)) (Kč|CZK|€|EUR|USD|\$)(?!\w)"), &t2, |m| {
        let gw = unit_gen(g(m, 2))?;
        Some(format!("{} {gw}", g(m, 1)))
    })
}

fn cs_hours(t: String, c: &mut Ctx) -> String {
    let unit_of: &[(&str, &str)] =
        &[("h", "h"), ("hod", "h"), ("hod.", "h"), ("min", "min"), ("min.", "min"), ("sek", "s"), ("sek.", "s")];
    let gen_pl: &[(&str, &str)] = &[("h", "hodin"), ("min", "minut"), ("s", "sekund")];
    let s: &str = &t;
    c.sub(
        &rx(r"(?<![\w.,/:])(\d+(?:,\d+)?)(?: ?[–-] ?(\d+))? ?(hod\.|hod|h|min\.|min|sek\.|sek)(?![\w/])"),
        &t,
        |m| {
            let (a, b, u) = (g(m, 1), g(m, 2), g(m, 3));
            let word = lookup(unit_of, u)?;
            let before = &s[..start(m)];
            if word == "h" && u == "h" && search(r"(?:Kč|korun\w*|koruna|korunu),?\s*$", before) {
                return None;
            }
            let dot = if u.ends_with('.') { end_dot(s, end(m)) } else { "" };
            let prep = prep_before(s, start(m));
            if GEN_PREPS.contains(&prep.as_str()) && !a.contains(',') && !b.contains(',') {
                let x = card(py_int(a), "gen", "f")?;
                let y = if b.is_empty() { None } else { Some(card(py_int(b), "gen", "f")?) };
                let single = match word {
                    "h" => "hodiny",
                    "min" => "minuty",
                    _ => "sekundy",
                };
                let last = if b.is_empty() { a } else { b };
                let noun = if last == "1" { single } else { lookup(gen_pl, word)? };
                let mid = match y {
                    Some(y) => format!(" až {y}"),
                    None => String::new(),
                };
                return Some(format!("{x}{mid} {noun}{dot}"));
            }
            if !b.is_empty() {
                return Some(format!("{} až {}{dot}", words(a, "cs"), hours(b, word)));
            }
            if word == "h" && (prep == "v" || prep == "ve") && !a.contains(',') && a == "1" {
                return Some(format!("jednu hodinu{dot}"));
            }
            Some(format!("{}{dot}", hours(a, word)))
        },
    )
}

fn cs_gen_hours(h: &str) -> Option<String> {
    let v = py_int(h);
    let gw = card(v, "gen", "f")?;
    Some(format!("{gw}{}", if v == 1 { " hodiny" } else { " hodin" }))
}

fn cs_time_repl(m: &Captures<'_, str>) -> Option<String> {
    let (prep, h, sep, mm) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
    let p = prep.to_lowercase();
    let p = p.as_str();
    if sep == "." && !["v", "ve", "od", "do"].contains(&p) {
        return None;
    }
    let lead = if prep.is_empty() { String::new() } else { format!("{prep} ") };
    if py_int(h) == 0 {
        return None;
    }
    if mm == "00" {
        if p == "v" || p == "ve" {
            let hw = if py_int(h) == 1 { "jednu hodinu".to_string() } else { hours(&py_int(h).to_string(), "h") };
            return Some(format!("{lead}{hw}"));
        }
        if p == "od" || p == "do" {
            return Some(format!("{lead}{}", cs_gen_hours(h)?));
        }
        if !p.is_empty() {
            return None;
        }
        return Some(hours(&py_int(h).to_string(), "h"));
    }
    if p != "v" && p != "ve" {
        return None;
    }
    let mut spoken = words(&format!("{}:{mm}", py_int(h)), "cs");
    if py_int(h) == 1
        && let Some(rest) = spoken.strip_prefix("jedna ")
    {
        spoken = format!("jednu {rest}");
    }
    Some(format!("{lead}{spoken}"))
}

fn cs_time(t: String, c: &mut Ctx) -> String {
    let s: &str = &t;
    let t2 = c.sub(
        &rx(r"(?<![\w.,:])(?:([Oo]d) )?([01]?\d|2[0-3]):(00) ?[–-] ?([01]?\d|2[0-3]):(00)(?![\d:])( ?hod\.(?!\w))?"),
        &t,
        |m| {
            if g(m, 3) != "00" || g(m, 5) != "00" {
                return None;
            }
            let x = card(py_int(g(m, 2)), "gen", "f")?;
            let y = cs_gen_hours(g(m, 4))?;
            let od = if g(m, 1).is_empty() { "od" } else { g(m, 1) };
            let dot = if g(m, 6).is_empty() { "" } else { line_end(s, end(m)) };
            Some(format!("{od} {x} do {y}{dot}"))
        },
    );
    let s2: &str = &t2;
    c.sub(
        &rx(r"(?<![\w.])(?:([Vv]e?|[Oo]d|[Dd]o|[Pp]o|[Pp]řed|[Kk]olem|[Oo]kolo|[Mm]ezi) )?([01]?\d|2[0-3])([:.])([0-5]\d)(?![\d:]|[.,]\d|\w)( ?hod\.(?!\w))?(?! ?(?:[AaPp]\.?[Mm]\b|GMT|UTC|SE?ČS?|CES?T))"),
        &t2,
        |m| {
            let r = cs_time_repl(m)?;
            let dot = if g(m, 5).is_empty() { "" } else { line_end(s2, end(m)) };
            Some(format!("{r}{dot}"))
        },
    )
}

fn cs_date(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&format!(
            r"(?<![\w.,])(?:([Oo]d) ([12]?\d|3[01])\. do ([12]?\d|3[01])\.|([12]?\d|3[01])\. ?[–-] ?([12]?\d|3[01])\.) ({MONTHS_GEN})\b"
        )),
        &t,
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

fn cs_century(t: String, c: &mut Ctx) -> String {
    let s: &str = &t;
    c.sub(&rx(r"\b(X{0,2}(?:IX|IV|VI{0,3}|I{1,3})|X{1,2})\.? (století|stol\.)(?!\w)"), &t, |m| {
        let n = roman(g(m, 1));
        if !(1..=21).contains(&n) {
            return None;
        }
        let dot = if g(m, 2) == "stol." { end_dot(s, end(m)) } else { "" };
        Some(format!("{n}. století{dot}"))
    })
}

fn cs_decade(t: String, c: &mut Ctx) -> String {
    let case_of: &[(&str, &str)] =
        &[("léta", "nom"), ("let", "gen"), ("letech", "loc"), ("lety", "ins"), ("létům", "dat")];
    c.sub(
        &rx(r"(?<![\w.,])((?:[1-9]0)\.(?:(?:,| a| i| nebo| až|–|-) ?[1-9]0\.)*) (let|letech|léta|lety|létům)\b"),
        &t,
        |m| {
            let (chain, noun) = (g(m, 1), g(m, 2));
            let case = lookup(case_of, noun)?;
            let out = sub_plain(&rx(r"(\d0)\."), chain, |d| {
                Some(ordinal(py_int(g(d, 1)), "npl", case).unwrap_or_else(|| g(d, 0).to_string()))
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
            if case == "acc" && ["na", "za", "pro", "přes", "v", "ve", "o", "po"].contains(&prep) {
                return Some((gender, case));
            }
        }
        return None;
    }
    if search(r"(?:ého)$", w) {
        return Some(("m", "gen"));
    }
    if search(r"(?:ému)$", w) {
        return Some(("m", "dat"));
    }
    if search(r"(?:ém)$", w) {
        return Some(("m", "loc"));
    }
    if search(r"(?:ými)$", w) {
        return Some(("pl", "ins"));
    }
    if search(r"(?:ým)$", w) {
        return Some(("m", "ins"));
    }
    if search(r"(?:ých)$", w) {
        return Some(("pl", "gen"));
    }
    if nchars(w) >= 4 && search(r"(?:ách|ech|ích)$", w) {
        return Some(("pl", "loc"));
    }
    if nchars(w) >= 4 && search(r"(?:ami|emi)$", w) {
        return Some(("pl", "ins"));
    }
    if w.ends_with("ou") && nchars(w) >= 4 && !["jsou", "mohou", "budou", "nesou", "vedou"].contains(&w) {
        return Some(("f", "ins"));
    }
    if w.ends_with('á') && nchars(w) >= 4 && prep.is_empty() {
        return Some(("f", "nom"));
    }
    if w.ends_with('é') && gen_p {
        return Some(("f", "gen"));
    }
    if w.ends_with('é') && loc_p {
        return Some(("f", "loc"));
    }
    None
}

fn is_prep(p: &str) -> bool {
    GEN_PREPS.contains(&p)
        || DAT_PREPS.contains(&p)
        || LOC_PREPS.contains(&p)
        || INS_PREPS.contains(&p)
        || LOC_OR_ACC.contains(&p)
        || OTHER_PREPS.contains(&p)
}

fn cs_ordinal(t: String, c: &mut Ctx) -> String {
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

fn cs_half(t: String, c: &mut Ctx) -> String {
    let units: &[(&str, &str)] = &[
        ("l", "litru"),
        ("ml", "mililitru"),
        ("kg", "kilogramu"),
        ("g", "gramu"),
        ("dkg", "dekagramu"),
        ("m", "metru"),
        ("cm", "centimetru"),
        ("km", "kilometru"),
        ("h", "hodiny"),
        ("hod.", "hodiny"),
        ("min", "minuty"),
        ("min.", "minuty"),
    ];
    let stop = ["nebo", "až", "jsou", "je", "to", "nich", "toho", "nás", "vás", "část"];
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
                "2" => (if fem { "dvě" } else { "dva" }).to_string(),
                _ => words(whole, "cs"),
            };
            return Some(format!("{w} a půl {word}"));
        }
        Some(format!("{}{word}", if den == "2" { "půl " } else { "čtvrt " }))
    })
}

fn cs_percent(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,])(\d+,\d+) ?%"), &t, |m| Some(format!("{} procenta", words(g(m, 1), "cs"))))
}

fn cs_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"\b([Vv]e?) r\. (?=\d{4}\b)"), &t, r"\1 roce ");
    let t = c.sub_tpl(&rx(r"(?<![\w.])r\. (?=\d{4}\b)"), &t, "roku ");
    let t = c.sub_tpl(&rx(r"\b(Ing\.) arch\."), &t, r"\1 architekt");
    let table: &[(&str, &str)] = &[
        ("ul.", "ulice"),
        ("nám.", "náměstí"),
        ("tř.", "třída"),
        ("aj.", "a jiné"),
        ("mj.", "mimo jiné"),
        ("popř.", "popřípadě"),
        ("kap.", "kapitola"),
        ("obr.", "obrázek"),
        ("tab.", "tabulka"),
        ("pozn.", "poznámka"),
        ("ph.d.", "pé há dé"),
        ("csc.", "cé es cé"),
    ];
    let s: &str = &t;
    c.sub(
        &rx(&format!(
            r"(?<![\w.])([Uu]l\.|[Nn]ám\.|tř\.(?= [{UPPER}])|aj\.|mj\.|[Pp]opř\.|[Kk]ap\.(?= \d)|[Oo]br\.(?= \d)|[Tt]ab\.(?= \d)|[Pp]ozn\.|Ph\. ?D\.|CSc\.|(?:MU|MV|JU|Ph|RN|Paed|Pharm|Th|MD)Dr\.)(?!\w)"
        )),
        &t,
        |m| {
            let a = g(m, 1);
            if a.ends_with("Dr.") {
                let fem = matches_at_start(&format!(r" [{UPPER}]\w*(?:ová|á)\b"), &s[end(m)..]);
                return Some((if fem { "doktorka" } else { "doktor" }).to_string());
            }
            let key = a.to_lowercase().replace(' ', "");
            let out = lookup(table, &key)?;
            let lower = a.chars().next().is_some_and(char::is_lowercase);
            let out = if lower || key == "ph.d." || key == "csc." { out.to_string() } else { py_capitalize(out) };
            Some(format!("{out}{}", line_end(s, end(m))))
        },
    )
}

/// m/f for 1 in an oblique case, from the noun's singular ending (koruny -> f, roku -> m), else None.
fn one_gender(noun: &str, case: &str) -> Option<&'static str> {
    let last = noun.chars().next_back()?;
    match case {
        "gen" => {
            if noun.ends_with('y') {
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
            } else if noun.ends_with("em") || noun.ends_with("ím") {
                Some("m")
            } else {
                None
            }
        }
        _ => None,
    }
}

/// The cardinal before a nominative/accusative noun in its gender (dvě sestry, jeden hrnek, jedno auto).
fn nominative(n: u128, noun: &str, prep: &str) -> Option<String> {
    if nchars(noun) < 3 {
        return None;
    }
    if n == 1 {
        if NEUT_SG_SET.contains(noun) || (noun.ends_with("um") && nchars(noun) >= 5) {
            return Some("jedno".into());
        }
        if let Some(stem) = noun.strip_suffix('u')
            && FEM_NEUT_PL_SET.contains(format!("{stem}y").as_str())
            && ["", "pro", "přes", "za", "na"].contains(&prep)
        {
            return Some("jednu".into());
        }
        if search(r"[bcčdďfghjkmnňpqrřsštťvwxzž]$", noun)
            && !FEM_CONS.contains(&noun)
            && !NOT_MASC.contains(&noun)
            && !noun.ends_with("ost")
        {
            return Some("jeden".into());
        }
        return None;
    }
    if n >= 1000 || n % 10 != 2 || n % 100 == 12 {
        return None;
    }
    if FEM_NEUT_PL_SET.contains(noun)
        || (noun.ends_with('a') && nchars(noun) >= 3 && !search(r"(?:ala|ela|ěla|ila|yla|ula|šla|dla|tla|sla)$", noun))
    {
        let spoken = words(&n.to_string(), "cs");
        let mut ws = py_split_ws(&spoken);
        if ws.last() == Some(&"dva") {
            ws.pop();
            ws.push("dvě");
            return Some(ws.join(" "));
        }
    }
    None
}

fn cs_number_case(t: String, c: &mut Ctx) -> String {
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
            if full(&format!(r"(?:roku|rok|roce|r)|{MONTHS_GEN}"), &lw) {
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
            if super::shared::is_op_word("cs", &noun) {
                return None; // 1 plus 69 rovná se 70: an equation, not a count
            }
            if ["do", "a", "až", "nebo", "či"].contains(&noun.as_str()) {
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
                if cs.is_none() && ["před", "mezi", "nad", "pod"].contains(&p) && noun.ends_with('y') && nchars(&noun) >= 3
                {
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

fn cs_money(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/])(\d{1,3}(?:[ \xa0]\d{3})+|\d+) ?(Kč|CZK|€|EUR|\$|USD)(?!\w)"), &t, |m| {
        let (num, cur) = (g(m, 1), g(m, 2));
        let n = py_int(&num.replace([' ', '\u{a0}'], ""));
        let d = n % 10;
        if n <= 20 || !(2..=4).contains(&d) || (12..=14).contains(&(n % 100)) {
            return None;
        }
        Some(format!("{} {}", words(&(n - d).to_string(), "cs"), words(&format!("{d} {cur}"), "cs")))
    })
}

fn cs_weekdays(t: String, c: &mut Ctx) -> String {
    let day: &[(&str, &str)] = &[
        ("po", "pondělí"),
        ("út", "úterý"),
        ("ut", "úterý"),
        ("st", "středa"),
        ("čt", "čtvrtek"),
        ("ct", "čtvrtek"),
        ("pá", "pátek"),
        ("pa", "pátek"),
        ("so", "sobota"),
        ("ne", "neděle"),
    ];
    let s: &str = &t;
    c.sub(
        &rx(r"(?i)(?<![\w.])(po|út|ut|st|čt|ct|pá|pa|so|ne)\.? ?[–-] ?(po|út|ut|st|čt|ct|pá|pa|so|ne)(\.)?(?!\w)"),
        &t,
        |m| {
            let a = lookup(day, &g(m, 1).to_lowercase())?;
            let b = lookup(day, &g(m, 2).to_lowercase())?;
            let dot = if g(m, 3).is_empty() { "" } else { line_end(s, end(m)) };
            if a == b { None } else { Some(format!("{a} až {b}{dot}")) }
        },
    )
}

fn cs_vocalize(t: String, c: &mut Ctx) -> String {
    let cluster = r"(?:dv(?:a|ě|ou|ěma|anáct\w*|acet\w*|acát\w*)|tř(?:i|í|em|ech|emi|ináct\w*|icet\w*|etí\w*|icát\w*)|čt(?:yři|yř|yřem|yřech|yřmi|rnáct\w*|yřicet\w*|yřicát\w*|vrt\w*)|st(?:o|a|u|em|ech|ý|ého|ému|ém|ým)|druh(?:ý|á|é|ého|ému|ém|ým|ou|ých|ými))";
    let sib = r"(?:sedm\w*|šest\w*|šedesát\w*|set)";
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.])([Vv]) (?={cluster}\b)")), &t, r"\1e ");
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.])([SsZz]) (?=(?:{cluster}|{sib})\b)")), &t, r"\1e ");
    c.sub_tpl(&rx(&format!(r"(?<![\w.])([Kk]) (?={cluster}\b)")), &t, r"\1e ")
}
