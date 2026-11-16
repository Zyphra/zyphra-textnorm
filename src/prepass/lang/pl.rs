//! 'pl' rules: the port of the workbench's `langrules/pl.py` (ids `pl.*`).
//!
//! The grammar reads every number in the nominative and in the masculine. These rules write the number words
//! themselves where the context fixes another form: the case a preposition or the noun's ending requires, the gender
//! of the noun, the case and gender of an ordinal.

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, chars_after, chars_before, full, g, matches_at_start, py_int, rx, search, sub_plain, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::{py_capitalize, py_split_ws, py_strip};

pub(super) const RULES: &[LangRule] = &[
    ("pl.scale", pl_scale),
    ("pl.time", pl_time),
    ("pl.date", pl_date),
    ("pl.century", pl_century),
    ("pl.ordinal-suffix", pl_ordinal_suffix),
    ("pl.decade", pl_decade),
    ("pl.ordinal", pl_ordinal),
    ("pl.half", pl_half),
    ("pl.abbrev", pl_abbrev),
    ("pl.number-case", pl_number_case),
    ("pl.weekdays", pl_weekdays),
];

const LETTER: &str = r"[^\W\d_]";
const CASES: [&str; 4] = ["gen", "dat", "loc", "ins"];

/// A cardinal word in the nominative -> its genitive, dative, locative, instrumental.
const CARD: &[(&str, &str)] = &[
    ("dwa", "dwóch dwóm dwóch dwoma"),
    ("dwie", "dwóch dwóm dwóch dwiema"),
    ("trzy", "trzech trzem trzech trzema"),
    ("cztery", "czterech czterem czterech czterema"),
    ("pięć", "pięciu pięciu pięciu pięcioma"),
    ("sześć", "sześciu sześciu sześciu sześcioma"),
    ("siedem", "siedmiu siedmiu siedmiu siedmioma"),
    ("osiem", "ośmiu ośmiu ośmiu ośmioma"),
    ("dziewięć", "dziewięciu dziewięciu dziewięciu dziewięcioma"),
    ("dziesięć", "dziesięciu dziesięciu dziesięciu dziesięcioma"),
    ("jedenaście", "jedenastu jedenastu jedenastu jedenastoma"),
    ("dwanaście", "dwunastu dwunastu dwunastu dwunastoma"),
    ("trzynaście", "trzynastu trzynastu trzynastu trzynastoma"),
    ("czternaście", "czternastu czternastu czternastu czternastoma"),
    ("piętnaście", "piętnastu piętnastu piętnastu piętnastoma"),
    ("szesnaście", "szesnastu szesnastu szesnastu szesnastoma"),
    ("siedemnaście", "siedemnastu siedemnastu siedemnastu siedemnastoma"),
    ("osiemnaście", "osiemnastu osiemnastu osiemnastu osiemnastoma"),
    ("dziewiętnaście", "dziewiętnastu dziewiętnastu dziewiętnastu dziewiętnastoma"),
    ("dwadzieścia", "dwudziestu dwudziestu dwudziestu dwudziestoma"),
    ("trzydzieści", "trzydziestu trzydziestu trzydziestu trzydziestoma"),
    ("czterdzieści", "czterdziestu czterdziestu czterdziestu czterdziestoma"),
    ("pięćdziesiąt", "pięćdziesięciu pięćdziesięciu pięćdziesięciu pięćdziesięcioma"),
    ("sześćdziesiąt", "sześćdziesięciu sześćdziesięciu sześćdziesięciu sześćdziesięcioma"),
    ("siedemdziesiąt", "siedemdziesięciu siedemdziesięciu siedemdziesięciu siedemdziesięcioma"),
    ("osiemdziesiąt", "osiemdziesięciu osiemdziesięciu osiemdziesięciu osiemdziesięcioma"),
    ("dziewięćdziesiąt", "dziewięćdziesięciu dziewięćdziesięciu dziewięćdziesięciu dziewięćdziesięcioma"),
    ("sto", "stu stu stu stoma"),
    ("dwieście", "dwustu dwustu dwustu dwustoma"),
    ("trzysta", "trzystu trzystu trzystu trzystoma"),
    ("czterysta", "czterystu czterystu czterystu czterystoma"),
    ("pięćset", "pięciuset pięciuset pięciuset pięciuset"),
    ("sześćset", "sześciuset sześciuset sześciuset sześciuset"),
    ("siedemset", "siedmiuset siedmiuset siedmiuset siedmiuset"),
    ("osiemset", "ośmiuset ośmiuset ośmiuset ośmiuset"),
    ("dziewięćset", "dziewięciuset dziewięciuset dziewięciuset dziewięciuset"),
    ("tysiąc", "tysiąca tysiącowi tysiącu tysiącem"),
    ("tysiące", "tysięcy tysiącom tysiącach tysiącami"),
    ("tysięcy", "tysięcy tysiącom tysiącach tysiącami"),
    ("milion", "miliona milionowi milionie milionem"),
    ("miliony", "milionów milionom milionach milionami"),
    ("milionów", "milionów milionom milionach milionami"),
    ("miliard", "miliarda miliardowi miliardzie miliardem"),
    ("miliardy", "miliardów miliardom miliardach miliardami"),
    ("miliardów", "miliardów miliardom miliardach miliardami"),
    ("jeden", "jeden jeden jeden jeden"),
];
/// 1 on its own: masculine/neuter and feminine forms of each case.
const ONE: &[(&str, &str)] = &[("m", "jednego jednemu jednym jednym"), ("f", "jednej jednej jednej jedną")];

const FEM_SG: &str =
    "siostra córka matka babcia ciocia kobieta dziewczyna dziewczynka koleżanka przyjaciółka żona osoba
studentka godzina minuta sekunda doba książka strona gazeta lekcja klasa szkoła ulica droga linia sala para sztuka
porcja łyżka łyżeczka szklanka filiżanka butelka puszka paczka torebka kromka szczypta kostka tabletka kapsułka
kropla kawa herbata pizza bułka cebula marchewka papryka pomarańcza cytryna gruszka śliwka ryba kura krowa ręka
noga głowa wersja opcja metoda zasada sprawa decyzja firma marka nagroda gra karta płyta piosenka historia seria
kategoria grupa drużyna rodzina sypialnia łazienka kuchnia lampa szafa ściana mapa torba walizka kurtka koszula
sukienka czapka korona złotówka tona kaloria mila wizyta rata dawka zmiana wojna szansa uwaga noc rzecz część
odpowiedź pani";
const FEM_PL: &str =
    "siostry córki matki babcie ciocie kobiety dziewczyny dziewczynki koleżanki przyjaciółki żony osoby
panie studentki uczennice nauczycielki lekarki godziny minuty sekundy doby noce rzeczy książki strony gazety lekcje
klasy szkoły ulice drogi linie sale pary sztuki porcje łyżki łyżeczki szklanki filiżanki butelki puszki paczki
torebki kromki szczypty garście kostki tabletki kapsułki krople kawy herbaty pizze bułki cebule marchewki papryki
pomarańcze cytryny gruszki śliwki truskawki kiełbaski parówki ryby kury krowy owce kozy świnie kaczki gęsi myszy
żaby pszczoły muchy ręce nogi głowy części wersje opcje możliwości metody zasady odpowiedzi sprawy decyzje firmy
spółki marki gwiazdki nagrody bramki rundy partie gry karty płyty piosenki bajki historie sceny serie edycje
kategorie grupy drużyny rodziny sypialnie łazienki kuchnie lampy szafy półki ściany mapy torby walizki kurtki
koszule sukienki czapki bluzki korony złotówki tony kalorie mile wizyty raty dawki zmiany wojny bitwy szanse
prośby uwagi tygodniówki pensje noce wiadomości";
const MP_GEN: &str =
    "braci ludzi mężczyzn chłopców synów panów kolegów przyjaciół studentów uczniów nauczycieli lekarzy
pracowników zawodników piłkarzy graczy kibiców policjantów żołnierzy strażaków ratowników turystów pasażerów
klientów pacjentów uczestników gości księży sędziów posłów polityków ministrów kierowców aktorów autorów naukowców
badaczy ekspertów specjalistów inżynierów pisarzy dziennikarzy obywateli mężów ojców wujków kuzynów chłopaków
facetów kandydatów sportowców muzyków artystów żeglarzy rolników górników";
const MP_NOM: &str = "bracia synowie panowie studenci uczniowie nauczyciele lekarze pracownicy koledzy przyjaciele
mężczyźni chłopcy zawodnicy piłkarze gracze policjanci żołnierze turyści pasażerowie klienci pacjenci uczestnicy
goście księża sędziowie posłowie politycy ministrowie kierowcy aktorzy autorzy naukowcy eksperci specjaliści
inżynierowie pisarze dziennikarze";
const NEUT_SG: &str =
    "jajko dziecko piwo jabłko zdjęcie miejsce okno auto mieszkanie pytanie zadanie łóżko krzesło euro
ciasto ciastko opakowanie danie śniadanie słowo zdanie miasto państwo województwo morze jezioro drzewo pole serce
oko ucho koło biuro radio kino piętro ćwiczenie pudełko wiadro jajo lustro pióro wiosło słoiko";
const COLLECTIVE: &[&str] = &["dzieci", "drzwi", "oczu", "uszu"];
const NEUT_E: &[&str] = &["imię", "ramię", "zwierzę", "plemię", "znamię", "kurczę", "cielę", "źrebię"];
const FEM_CONS: &[&str] = &[
    "noc",
    "rzecz",
    "mysz",
    "twarz",
    "podróż",
    "wieś",
    "krew",
    "myśl",
    "łódź",
    "dłoń",
    "jesień",
    "sieć",
    "sól",
    "część",
    "kość",
    "pieśń",
    "brew",
    "odpowiedź",
    "wiadomość",
];

fn set(src: &'static str) -> HashSet<&'static str> {
    py_split_ws(src).into_iter().collect()
}

static FEM_SG_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(FEM_SG));
static FEM_PL_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(FEM_PL));
static MP_GEN_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(MP_GEN));
static MP_NOM_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(MP_NOM));
static NEUT_SG_SET: LazyLock<HashSet<&'static str>> = LazyLock::new(|| set(NEUT_SG));

/// Nouns after an ordinal: gender, nominative, genitive, locative singular (pl = plural-only nouns).
const ORD_NOUNS: &[(&str, &str)] = &[
    ("n", "miejsce miejsca miejscu"),
    ("n", "piętro piętra piętrze"),
    ("n", "wydanie wydania wydaniu"),
    ("n", "półrocze półrocza półroczu"),
    ("n", "stulecie stulecia stuleciu"),
    ("n", "zadanie zadania zadaniu"),
    ("n", "pytanie pytania pytaniu"),
    ("n", "okrążenie okrążenia okrążeniu"),
    ("n", "spotkanie spotkania spotkaniu"),
    ("n", "posiedzenie posiedzenia posiedzeniu"),
    ("n", "dziecko dziecka dziecku"),
    ("m", "rok roku roku"),
    ("m", "wiek wieku wieku"),
    ("m", "dzień dnia dniu"),
    ("m", "raz razu razie"),
    ("m", "etap etapu etapie"),
    ("m", "kwartał kwartału kwartale"),
    ("m", "sezon sezonu sezonie"),
    ("m", "poziom poziomu poziomie"),
    ("m", "rozdział rozdziału rozdziale"),
    ("m", "tom tomu tomie"),
    ("m", "punkt punktu punkcie"),
    ("m", "stopień stopnia stopniu"),
    ("m", "rząd rzędu rzędzie"),
    ("m", "krok kroku kroku"),
    ("m", "tydzień tygodnia tygodniu"),
    ("m", "miesiąc miesiąca miesiącu"),
    ("m", "odcinek odcinka odcinku"),
    ("m", "mecz meczu meczu"),
    ("m", "semestr semestru semestrze"),
    ("m", "kurs kursu kursie"),
    ("m", "festiwal festiwalu festiwalu"),
    ("m", "numer numeru numerze"),
    ("m", "peron peronu peronie"),
    ("m", "tor toru torze"),
    ("m", "set seta secie"),
    ("m", "plan planu planie"),
    ("m", "pułk pułku pułku"),
    ("m", "zjazd zjazdu zjeździe"),
    ("m", "kongres kongresu kongresie"),
    ("f", "klasa klasy klasie"),
    ("f", "liga ligi lidze"),
    ("f", "runda rundy rundzie"),
    ("f", "strona strony stronie"),
    ("f", "edycja edycji edycji"),
    ("f", "część części części"),
    ("f", "pozycja pozycji pozycji"),
    ("f", "rocznica rocznicy rocznicy"),
    ("f", "kadencja kadencji kadencji"),
    ("f", "połowa połowy połowie"),
    ("f", "wojna wojny wojnie"),
    ("f", "seria serii serii"),
    ("f", "linia linii linii"),
    ("f", "godzina godziny godzinie"),
    ("f", "minuta minuty minucie"),
    ("f", "lekcja lekcji lekcji"),
    ("f", "dawka dawki dawce"),
    ("f", "tura tury turze"),
    ("f", "kolejka kolejki kolejce"),
    ("f", "osoba osoby osobie"),
    ("f", "nagroda nagrody nagrodzie"),
    ("f", "rata raty racie"),
    ("f", "wersja wersji wersji"),
    ("f", "dekada dekady dekadzie"),
    ("f", "zmiana zmiany zmianie"),
    ("f", "faza fazy fazie"),
    ("f", "sesja sesji sesji"),
    ("f", "kategoria kategorii kategorii"),
    ("f", "grupa grupy grupie"),
    ("f", "armia armii armii"),
    ("f", "dywizja dywizji dywizji"),
    ("f", "brygada brygady brygadzie"),
    ("f", "szkoła szkoły szkole"),
    ("f", "ulica ulicy ulicy"),
    ("f", "księga księgi księdze"),
    ("f", "symfonia symfonii symfonii"),
    ("f", "próba próby próbie"),
    ("f", "wizyta wizyty wizycie"),
    ("f", "doba doby dobie"),
    ("pl", "urodziny urodzin urodzinach"),
    ("pl", "imieniny imienin imieninach"),
    ("pl", "igrzyska igrzysk igrzyskach"),
    ("pl", "mistrzostwa mistrzostw mistrzostwach"),
    ("pl", "zawody zawodów zawodach"),
    ("pl", "wybory wyborów wyborach"),
    ("pl", "obchody obchodów obchodach"),
];

static ORD_FORMS: LazyLock<HashMap<&'static str, Vec<(&'static str, &'static str)>>> = LazyLock::new(|| {
    let mut m: HashMap<&'static str, Vec<(&'static str, &'static str)>> = HashMap::new();
    for &(gender, forms) in ORD_NOUNS {
        for (case, w) in ["nom", "gen", "loc"].into_iter().zip(py_split_ws(forms)) {
            m.entry(w).or_default().push((gender, case));
        }
    }
    m
});

/// Ordinal endings of a hard stem (pierwszy) for a gender and case; soft stems (drugi, trzeci) are derived.
const ORD_END: &[(&str, &str)] =
    &[("m", "y ego emu y ym ym"), ("n", "e ego emu e ym ym"), ("f", "a ej ej ą ą ej"), ("pl", "e ych ym e ymi ych")];
const ORD_CASES: [&str; 6] = ["nom", "gen", "dat", "acc", "ins", "loc"];

const GEN_PREPS: &[&str] = &[
    "od",
    "do",
    "około",
    "ok.",
    "bez",
    "dla",
    "u",
    "według",
    "wg",
    "podczas",
    "wśród",
    "spośród",
    "obok",
    "koło",
    "oprócz",
    "zamiast",
    "wokół",
    "sprzed",
    "powyżej",
    "poniżej",
    "naprzeciwko",
    "wysokości",
    "wieku",
    "odległości",
    "ciągu",
    "trakcie",
    "okresie",
];
const DAT_PREPS: &[&str] = &["dzięki", "ku", "przeciw", "przeciwko", "wbrew"];
const LOC_PREPS: &[&str] = &["przy"];
const LOC_OR_ACC: &[&str] = &["na", "w", "we", "o", "po", "przy"];
const OTHER_PREPS: &[&str] = &["z", "ze", "przed", "za", "nad", "pod", "między", "pomiędzy", "przez"];

const MONTHS_GEN: &str =
    "stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia";
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

fn last_char(s: &str) -> Option<char> {
    s.chars().next_back()
}

fn nchars(s: &str) -> usize {
    s.chars().count()
}

/// The cardinal n in `case` (gen, dat, loc, ins); `gender` m/f picks 1 and the instrumental of 2 (dwiema).
fn card(n: u128, case: &str, gender: &str) -> Option<String> {
    let i = CASES.iter().position(|c| *c == case)?;
    if n == 1 {
        return lookup(ONE, gender).map(|f| nth(f, i).to_string());
    }
    let mut out: Vec<String> = Vec::new();
    for w in py_split_ws(&words(&n.to_string(), "pl")) {
        let forms = lookup(CARD, w)?;
        let mut f = nth(forms, i);
        if f == "dwoma" && gender == "f" {
            f = "dwiema";
        }
        out.push(f.to_string());
    }
    Some(out.join(" "))
}

/// The genitive cardinal used with masculine-personal nouns (dwóch, trzech, pięciu).
fn gen_numeral(n: u128) -> Option<String> {
    card(n, "gen", "m")
}

/// One ordinal word (masculine nominative, pierwszy/drugi/trzeci) in a gender and case; cardinals stay.
fn ord_word(w: &str, gender: &str, case: &str) -> String {
    if !(w.ends_with('y') || w.ends_with('i')) || w == "trzy" || w == "cztery" {
        return w.to_string();
    }
    let ci = ORD_CASES.iter().position(|c| *c == case).unwrap_or(0);
    let mut end = nth(lookup(ORD_END, gender).unwrap_or("y ego emu y ym ym"), ci).to_string();
    let stem = &w[..w.len() - 1];
    if w.ends_with('i') {
        if let Some(rest) = end.strip_prefix('y') {
            end = format!("i{rest}");
        } else if end.starts_with('e') || ((end == "a" || end == "ą") && !(w.ends_with("gi") || w.ends_with("ki"))) {
            end = format!("i{end}");
        }
    }
    format!("{stem}{end}")
}

/// The ordinal n in a gender and case (dwa tysiące dwudziestym czwartym), or None when the grammar has none.
fn ordinal(n: u128, gender: &str, case: &str) -> Option<String> {
    let base = if n >= 1000 {
        let gw = words(&format!("{n} roku"), "pl");
        let gw = gw.strip_suffix(" roku")?;
        py_split_ws(gw)
            .into_iter()
            .map(|w| {
                if let Some(s) = w.strip_suffix("iego") {
                    format!("{s}i")
                } else if let Some(s) = w.strip_suffix("ego") {
                    format!("{s}y")
                } else {
                    w.to_string()
                }
            })
            .collect::<Vec<_>>()
            .join(" ")
    } else {
        words(&format!("{n}."), "pl")
    };
    let ws = py_split_ws(&base);
    let last = *ws.last()?;
    if base.contains('.') || !(last.ends_with('y') || last.ends_with('i')) || last == "trzy" || last == "cztery" {
        return None;
    }
    Some(ws.iter().map(|w| ord_word(w, gender, case)).collect::<Vec<_>>().join(" "))
}

/// A masculine genitive ordinal (trzeciego, dwudziestego czwartego) in the locative/instrumental (-ym, -im).
fn gen_to(phrase: &str, _case: &str) -> String {
    py_split_ws(phrase)
        .into_iter()
        .map(|w| {
            if let Some(s) = w.strip_suffix("iego") {
                format!("{s}im")
            } else if let Some(s) = w.strip_suffix("ego") {
                format!("{s}ym")
            } else {
                w.to_string()
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// '.' when the abbreviation dot that ends at `end` also ends the sentence (end of text or line, or a capital).
fn end_dot(t: &str, end: usize) -> &'static str {
    if matches_at_start(r"(?:\s*$|\n|\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż])", &t[end..]) { "." } else { "" }
}

/// The genitive plural the grammar gives a unit or currency after a number (zł -> złotych), or None for a word.
fn unit_gen(tok: &str) -> Option<String> {
    let r = words(&format!("5 {tok}"), "pl");
    let rest = r.strip_prefix("pięć ")?;
    if search(r"\d", &r) || rest == tok {
        return None;
    }
    Some(rest.to_string())
}

/// The word before the number at `start`, lowercased, looking past 'N i/a/lub' (o 5 i 10 kotach).
fn prep_before(t: &str, start: usize) -> String {
    let win = chars_before(t, start, 40);
    match rx(r"(?:^|[^\w.])(\w+\.?)\s+(?:\d+\s*(?:i|a|lub|albo|oraz|czy|,)\s*)?$").captures(win) {
        Ok(Some(m)) => g(&m, 1).to_lowercase(),
        _ => String::new(),
    }
}

/// The first word after the number at `end`, past 'i/a/lub/do N' (o 5 i 10 kotach), lowercased.
fn noun_after(t: &str, end: usize) -> String {
    let win = chars_after(t, end, 60);
    match rx(r"^(?:(?:\s*(?:i|a|lub|albo|oraz|czy|do|–|-|,)\s*\d+)*\s*([^\W\d_]+))").captures(win) {
        Ok(Some(m)) => g(&m, 1).to_lowercase(),
        _ => String::new(),
    }
}

/// The case a plural noun's ending shows: -ach locative, -ami instrumental, -om dative.
fn suffix_case(w: &str) -> Option<&'static str> {
    if nchars(w) < 4 {
        return None;
    }
    if w.ends_with("ach") {
        return Some("loc");
    }
    if search(r"(?:ami|ymi|imi|[ćńźśłżz]mi)$", w) {
        return Some("ins");
    }
    if w.ends_with("om") {
        return Some("dat");
    }
    None
}

fn pl_scale(t: String, c: &mut Ctx) -> String {
    let scales: &[(&str, (&str, &str))] = &[
        ("tys", ("000", "tysiąca")),
        ("mln", ("000 000", "miliona")),
        ("mld", ("000 000 000", "miliarda")),
        ("bln", ("000 000 000 000", "biliona")),
    ];
    let s: &str = &t;
    let t2 = c.sub(&rx(r"(?<![\w.,])([€$£])?(\d+(?:,\d+)?) ?(tys|mln|mld|bln)(\.)?(?!\w)"), &t, |m| {
        let (cur, num, sc) = (g(m, 1), g(m, 2), g(m, 3));
        let (zeros, gen_sg) = scales.iter().find(|(k, _)| *k == sc).map(|(_, v)| *v)?;
        if !num.contains(',') {
            if !cur.is_empty() {
                return None;
            }
            let n = py_int(num);
            if n >= 1000 {
                return None;
            }
            return Some(format!("{n} {zeros}{}", end_dot(s, end(m))));
        }
        let (whole, frac) = num.split_once(',')?;
        let spoken = if frac == "5" {
            let mut sp = match whole {
                "0" => "pół".to_string(),
                "1" => "półtora".to_string(),
                _ => format!("{} i pół", words(whole, "pl")),
            };
            if cur.is_empty()
                && py_int(whole) >= 2
                && GEN_PREPS.contains(&prep_before(s, start(m)).as_str())
                && let Some(gw) = card(py_int(whole), "gen", "m")
            {
                sp = format!("{gw} i pół");
            }
            sp
        } else {
            words(num, "pl")
        };
        let mut out = format!("{spoken} {gen_sg}");
        if !cur.is_empty() {
            let gw = unit_gen(cur)?;
            out = format!("{out} {gw}");
        }
        Some(format!("{out}{}", end_dot(s, end(m))))
    });
    // the currency after a written-out decimal scale: dwa i pół miliona zł -> dwa i pół miliona złotych
    c.sub(&rx(r"\b((?:tysiąca|miliona|miliarda|biliona)) (zł|PLN|€|EUR|USD|\$|GBP|£|CHF)(?!\w)"), &t2, |m| {
        let gw = unit_gen(g(m, 2))?;
        Some(format!("{} {gw}", g(m, 1)))
    })
}

fn pl_time_spoken(h: &str, mm: &str, case: &str) -> Option<String> {
    let hw = ordinal(py_int(h), "f", case)?;
    if mm.is_empty() || mm == "00" {
        return Some(hw);
    }
    let mut ch = mm.chars();
    let (a, b) = (ch.next()?, ch.next()?);
    let minutes = if a == '0' { format!("zero {}", words(&b.to_string(), "pl")) } else { words(mm, "pl") };
    Some(format!("{hw} {minutes}"))
}

fn pl_time(t: String, c: &mut Ctx) -> String {
    let hour_word: &[(&str, &str)] =
        &[("nom", "godzina"), ("gen", "godziny"), ("loc", "godzinie"), ("ins", "godziną"), ("acc", "godzinę")];
    let prep_case: &[(&str, &str)] = &[
        ("o", "loc"),
        ("po", "loc"),
        ("od", "gen"),
        ("do", "gen"),
        ("około", "gen"),
        ("ok.", "gen"),
        ("koło", "gen"),
        ("przed", "ins"),
        ("między", "ins"),
        ("pomiędzy", "ins"),
        ("na", "acc"),
    ];
    let t = c.sub(
        &rx(r"(?<![\w.,:])([Ww] )?(?:godz\. ?)?(?:([Oo]d) )?(1\d|2[0-3]|0?[1-9]):([0-5]\d) ?[–-] ?(1\d|2[0-3]|0?[1-9]):([0-5]\d)(?![\d:])(?! ?(?:[AaPp]\.?[Mm]\b|GMT|UTC|CES?T))"),
        &t,
        |m| {
            if !(g(m, 1).is_empty() || g(m, 0).contains("godz")) {
                return None;
            }
            let a = pl_time_spoken(g(m, 3), g(m, 4), "gen")?;
            let b = pl_time_spoken(g(m, 5), g(m, 6), "gen")?;
            let lead = if g(m, 1).is_empty() { String::new() } else { format!("{}godzinach ", g(m, 1)) };
            let od = if g(m, 2).is_empty() { "od" } else { g(m, 2) };
            Some(format!("{lead}{od} {a} do {b}"))
        },
    );
    let s: &str = &t;
    c.sub(
        &rx(r"(?<![\w.])(?:([Oo]|[Oo]d|[Dd]o|[Pp]o|[Oo]koło|[Oo]k\.|[Kk]oło|[Pp]rzed|[Mm]iędzy|[Pp]omiędzy|[Nn]a)\s+)?(godz\.\s*|godzin[aiyeę]\s+|godziną\s+)?(1\d|2[0-3]|0?[1-9])(?:([:.])([0-5]\d))?(?![\d:]|[.,]\d|\s?(?:zł|PLN|%|€|\$|kg|km|m\b|g\b|l\b)| ?(?:[AaPp]\.?[Mm]\b|GMT|UTC|CES?T))"),
        &t,
        |m| {
            let (prep, godz, h, sep, mm) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            let case = lookup(prep_case, &prep.to_lowercase()).unwrap_or("nom");
            if sep == "." && prep.is_empty() && godz.is_empty() {
                return None;
            }
            if mm.is_empty() && godz.is_empty() {
                return None;
            }
            if !godz.is_empty() && prep.is_empty() && search(r"\d\s*$", &s[..start(m)]) {
                return None; // 2 godz. 15 min: a duration
            }
            if case == "nom" && godz.is_empty() && mm != "00" {
                return None;
            }
            let sp = pl_time_spoken(h, mm, case)?;
            let p = if prep.is_empty() { String::new() } else { format!("{prep} ") };
            let hw = if godz.is_empty() { String::new() } else { format!("{} ", lookup(hour_word, case)?) };
            Some(format!("{p}{hw}{sp}"))
        },
    )
}

fn pl_day(d: &str) -> String {
    let w = words(&format!("{} maja", py_int(d)), "pl");
    let n = nchars(&w);
    w.chars().take(n.saturating_sub(5)).collect()
}

fn pl_date(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&format!(
            r"\b([Pp]rzed|[Pp]o|[Mm]iędzy|[Pp]omiędzy) ([12]?\d|3[01])(?: a ([12]?\d|3[01]))? ({MONTHS_GEN})\b"
        )),
        &t,
        |m| {
            let (prep, d1, d2, month) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
            let case = if prep.to_lowercase() == "po" { "loc" } else { "ins" };
            let mut out = format!("{prep} {}", gen_to(&pl_day(d1), case));
            if !d2.is_empty() {
                out = format!("{out} a {}", gen_to(&pl_day(d2), case));
            }
            Some(format!("{out} {month}"))
        },
    );
    let t = c.sub(
        &rx(&format!(
            r"(?<![\w.,])(?:([Oo]d) ([12]?\d|3[01]) do ([12]?\d|3[01])|([12]?\d|3[01]) ?[–-] ?([12]?\d|3[01])) ({MONTHS_GEN})\b"
        )),
        &t,
        |m| {
            let od = g(m, 1);
            let (d1, d2) = if od.is_empty() { (g(m, 4), g(m, 5)) } else { (g(m, 2), g(m, 3)) };
            let od = if od.is_empty() { "od" } else { od };
            Some(format!("{od} {} do {} {}", pl_day(d1), pl_day(d2), g(m, 6)))
        },
    );
    let s: &str = &t;
    let t2 = c.sub(&rx(r"\b([Ww]e?|[Pp]o|[Pp]rzed) (1\d{3}|20\d\d) ?(roku|r\.|rokiem)(?!\w)"), &t, |m| {
        let (prep, y, noun) = (g(m, 1), g(m, 2), g(m, 3));
        let gw = words(&format!("{y} roku"), "pl");
        let gw = gw.strip_suffix(" roku")?;
        let dot = if noun == "r." { end_dot(s, end(m)) } else { "" };
        if prep.to_lowercase() == "przed" {
            return Some(format!("{prep} {} rokiem{dot}", gen_to(gw, "ins")));
        }
        if noun == "rokiem" {
            return None;
        }
        Some(format!("{prep} {} roku{dot}", gen_to(gw, "loc")))
    });
    let t3 = c.sub(
        &rx(r"\b([Ww]e?|[Pp]o|[Pp]rzy|[Oo]d|[Dd]o|[Zz]e?|[Pp]rzed|[Oo]koło) (roku|rokiem) (1\d{3}|20\d\d)(?![\w,]|\.\d)"),
        &t2,
        |m| {
            let (prep, noun, y) = (g(m, 1), g(m, 2), g(m, 3));
            let gw = words(&format!("{y} roku"), "pl");
            let gw = gw.strip_suffix(" roku")?;
            let p = prep.to_lowercase();
            let case = if p == "przed" {
                "ins"
            } else if ["w", "we", "po", "przy"].contains(&p.as_str()) {
                "loc"
            } else {
                "gen"
            };
            if (case == "ins") != (noun == "rokiem") {
                return None;
            }
            let y = if case == "gen" { gw.to_string() } else { gen_to(gw, case) };
            Some(format!("{prep} {noun} {y}"))
        },
    );
    // 15.05.2024 r. -> the grammar already says roku after a numeric date
    c.sub_tpl(&rx(r"(?<![\w.])(\d{1,2}\.\d{1,2}\.\d{4}) r\."), &t3, r"\1")
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

fn pl_century(t: String, c: &mut Ctx) -> String {
    let rom = r"(?:X{0,2}(?:IX|IV|VI{0,3}|I{1,3})|X{1,2})";
    let pat = format!(
        r"\b((?:[Ww]e?|[Zz]e?|[Oo]d|[Dd]o|[Pp]rzed|[Pp]o|[Oo]|[Pp]rzy|[Oo]koło|[Pp]odczas|[Ss]przed) )?\b({rom}(?:\s*(?:i|do|–|-|,|lub|oraz|a)\s*{rom})*) (w\.|wieku|wiekiem|wiek)(?!\w)"
    );
    let s: &str = &t;
    c.sub(&rx(&pat), &t, |m| {
        let (prep, chain, noun) = (g(m, 1), g(m, 2), g(m, 3));
        let p = py_strip(prep).to_lowercase();
        let case = if noun == "wiek" {
            if p.is_empty() { "nom" } else { return None }
        } else if p == "przed" || noun == "wiekiem" {
            "ins"
        } else if ["w", "we", "o", "po", "przy"].contains(&p.as_str()) {
            "loc"
        } else {
            "gen"
        };
        let roms = rx(r"[IVX]+");
        for r in roms.find_iter(chain) {
            let n = roman(r.ok()?.as_str());
            if !(1..=21).contains(&n) || ordinal(n, "m", case).is_none() {
                return None;
            }
        }
        let out = sub_plain(&roms, chain, |r| ordinal(roman(g(r, 0)), "m", case));
        let word = match case {
            "nom" => "wiek",
            "ins" => "wiekiem",
            _ => "wieku",
        };
        let dot = if noun == "w." { end_dot(s, end(m)) } else { "" };
        Some(format!("{prep}{out} {word}{dot}"))
    })
}

fn pl_ordinal_suffix(t: String, c: &mut Ctx) -> String {
    let ends: &[(&str, (&str, &str))] = &[
        ("ego", ("m", "gen")),
        ("go", ("m", "gen")),
        ("emu", ("m", "dat")),
        ("mu", ("m", "dat")),
        ("ym", ("m", "loc")),
        ("im", ("m", "loc")),
        ("ej", ("f", "gen")),
        ("ą", ("f", "ins")),
        ("ych", ("pl", "gen")),
        ("ich", ("pl", "gen")),
        ("tych", ("pl", "gen")),
        ("ymi", ("pl", "ins")),
        ("imi", ("pl", "ins")),
    ];
    c.sub(&rx(r"(?<![\w.,-])(\d{1,4})-(ego|go|emu|mu|ym|im|ej|ą|ych|ich|tych|ymi|imi)(?!\w)"), &t, |m| {
        let (gender, case) = ends.iter().find(|(k, _)| *k == g(m, 2)).map(|(_, v)| *v)?;
        ordinal(py_int(g(m, 1)), gender, case)
    })
}

fn pl_decade(t: String, c: &mut Ctx) -> String {
    let case_of: &[(&str, &str)] =
        &[("lata", "nom"), ("lat", "gen"), ("latach", "loc"), ("latami", "ins"), ("latom", "dat")];
    let s: &str = &t;
    c.sub(
        &rx(r"\b([Ll]at(?:a|ach|ami|om)?) ((?:[1-9]0)(?:\.|-tych|-ych|-te|-e)?(?:(?:,| i| oraz| lub| a|–|-) ?[1-9]0(?:\.|-tych|-ych|-te|-e)?)*)(?![\w-])"),
        &t,
        |m| {
            let (lat, chain) = (g(m, 1), g(m, 2));
            let case = lookup(case_of, &lat.to_lowercase())?;
            let out = sub_plain(&rx(r"(\d0)(?:\.|-tych|-ych|-te|-e)?"), chain, |d| {
                Some(ordinal(py_int(g(d, 1)), "pl", case).unwrap_or_else(|| g(d, 0).to_string()))
            });
            let dot = if chain.ends_with('.') { end_dot(s, end(m)) } else { "" };
            Some(format!("{lat} {out}{dot}"))
        },
    )
}

/// (gender, case) of the noun after an ordinal: the noun table first, then its ending, else None.
fn noun_form(w: &str, prep: &str) -> Option<(&'static str, &'static str)> {
    let gen_p = GEN_PREPS.contains(&prep) || prep == "z" || prep == "ze";
    let loc_p = LOC_OR_ACC.contains(&prep);
    let empty = Vec::new();
    let cands = ORD_FORMS.get(w).unwrap_or(&empty);
    let want = if gen_p {
        Some("gen")
    } else if loc_p {
        Some("loc")
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
        return Some(cands[0]);
    }
    if !cands.is_empty() {
        return None;
    }
    let n = nchars(w);
    if n >= 4 && w.ends_with("ach") {
        return Some(("pl", "loc"));
    }
    if n >= 4 && w.ends_with("ami") {
        return Some(("pl", "ins"));
    }
    if n >= 4 && w.ends_with("ów") {
        return Some(("pl", "gen"));
    }
    if n >= 3 && w.ends_with("em") {
        return Some(("m", "ins"));
    }
    if w.ends_with('ą')
        && nchars(w) >= 4
        && !["mają", "będą", "mogą", "chcą", "robią", "wiedzą", "widzą", "piszą"].contains(&w)
    {
        return Some(("f", "ins"));
    }
    if w.ends_with('ę') {
        return Some(if NEUT_E.contains(&w) { ("n", "nom") } else { ("f", "acc") });
    }
    let last = last_char(w);
    if gen_p {
        if matches!(last, Some('a' | 'u')) {
            return Some(("m", "gen"));
        }
        if matches!(last, Some('y' | 'i')) {
            return Some(("f", "gen"));
        }
    } else if loc_p {
        if w.ends_with('u') {
            return Some(("m", "loc"));
        }
        if matches!(last, Some('y' | 'i')) {
            return Some(("f", "loc"));
        }
    } else if prep.is_empty() && (w.ends_with('o') || w.ends_with('e') || w.ends_with("um")) {
        return Some(("n", "nom"));
    }
    None
}

fn pl_ordinal(t: String, c: &mut Ctx) -> String {
    let s: &str = &t;
    c.sub(&rx(r"(?<![\w.,])(\d{1,4})\. ?((?=[a-ząćęłńóśźż])[^\W\d_]+)"), &t, |m| {
        let (n, w) = (py_int(g(m, 1)), g(m, 2));
        let line = s[..start(m)].rsplit('\n').next().unwrap_or("");
        if py_strip(line).is_empty() {
            return None;
        }
        let mut prep = prep_before(s, start(m));
        let p = prep.as_str();
        if !GEN_PREPS.contains(&p) && !DAT_PREPS.contains(&p) && !LOC_OR_ACC.contains(&p) && !OTHER_PREPS.contains(&p) {
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

fn pl_half(t: String, c: &mut Ctx) -> String {
    let units: &[(&str, &str)] = &[
        ("l", "litra"),
        ("ml", "mililitra"),
        ("kg", "kilograma"),
        ("g", "grama"),
        ("dag", "dekagrama"),
        ("m", "metra"),
        ("cm", "centymetra"),
        ("km", "kilometra"),
        ("h", "godziny"),
        ("godz.", "godziny"),
        ("min", "minuty"),
        ("min.", "minuty"),
    ];
    let stop = ["lub", "albo", "oraz", "czy", "jest", "to", "nich", "tego", "nas", "was", "część"];
    c.sub(&rx(r"(?<![\d/.,])(?:(\d+) )?1/([24])(?![\d/]) (godz\.|min\.|[^\W\d_]+)"), &t, |m| {
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
            if den != "2" || whole != "1" {
                return None;
            }
            let fem = word.ends_with('y') || word.ends_with('i');
            return Some(format!("{}{word}", if fem { "półtorej " } else { "półtora " }));
        }
        Some(format!("{}{word}", if den == "2" { "pół " } else { "ćwierć " }))
    })
}

/// m/f for 1 in an oblique case, from the noun's singular ending (osoby -> f, kota -> m), else None.
fn one_gender(noun: &str, case: &str) -> Option<&'static str> {
    let last = last_char(noun)?;
    match case {
        "gen" => {
            if "yi".contains(last) {
                Some("f")
            } else if "au".contains(last) {
                Some("m")
            } else {
                None
            }
        }
        "loc" => {
            if noun.ends_with('u') {
                Some("m")
            } else if "yi".contains(last) {
                Some("f")
            } else {
                None
            }
        }
        "ins" => {
            if noun.ends_with("em") {
                Some("m")
            } else if noun.ends_with('ą') {
                Some("f")
            } else {
                None
            }
        }
        _ => None,
    }
}

/// True for the instrumental plural of a noun in the feminine list (siostrami, książkami).
fn fem_plural_ins(noun: &str) -> bool {
    let Some(stem) = noun.strip_suffix("ami") else { return false };
    let soft = match stem.strip_suffix('i') {
        Some(s) => format!("{s}i"),
        None => String::new(),
    };
    [format!("{stem}y"), format!("{stem}i"), format!("{stem}e"), soft].iter().any(|f| FEM_PL_SET.contains(f.as_str()))
}

/// The cardinal before a nominative/accusative noun in its gender (dwie siostry, dwóch braci, jedno jajko).
fn nominative(n: u128, noun: &str, _prep: &str) -> Option<String> {
    let base = words(&n.to_string(), "pl");
    let last = n % 10;
    let teen = (10..=19).contains(&(n % 100));
    if n == 1 {
        if NEUT_E.contains(&noun) {
            return Some("jedno".into());
        }
        if let Some(stem) = noun.strip_suffix('ę')
            && FEM_SG_SET.contains(format!("{stem}a").as_str())
        {
            return Some("jedną".into());
        }
        if FEM_SG_SET.contains(noun) || FEM_CONS.contains(&noun) || (noun.ends_with("ość") && noun != "gość") {
            return Some("jedna".into());
        }
        if NEUT_SG_SET.contains(noun) || (noun.ends_with("um") && nchars(noun) >= 5) {
            return Some("jedno".into());
        }
        return None;
    }
    if n >= 1000 {
        return None;
    }
    if (2..=4).contains(&last) && !teen {
        if COLLECTIVE.contains(&noun) {
            return match n {
                2 => Some("dwoje".into()),
                3 => Some("troje".into()),
                4 => Some("czworo".into()),
                _ => None,
            };
        }
        if MP_NOM_SET.contains(noun) {
            return match n {
                2 => Some("dwaj".into()),
                3 => Some("trzej".into()),
                4 => Some("czterej".into()),
                _ => None,
            };
        }
        if MP_GEN_SET.contains(noun) || (noun.ends_with("ów") && nchars(noun) >= 4) {
            return gen_numeral(n);
        }
        if FEM_PL_SET.contains(noun) && last == 2 {
            let mut ws = py_split_ws(&base);
            if ws.last() == Some(&"dwa") {
                ws.pop();
                ws.push("dwie");
                return Some(ws.join(" "));
            }
        }
        return None;
    }
    if n >= 5 && MP_GEN_SET.contains(noun) {
        return gen_numeral(n);
    }
    None
}

fn pl_number_case(t: String, c: &mut Ctx) -> String {
    let s: &str = &t;
    c.sub(
        &rx(r"(?<![\w.,:/+\-−])(\d{1,3}(?:[ \xa0]\d{3})+|\d+)(?![\d]|[.,:/]\d|-|\.\s?[\da-ząćęłńóśźż])(?:( ?)([^\s\d][^\s]*))?"),
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
            if full(&format!(r"(?:roku|rok|rokiem|r)|{MONTHS_GEN}"), &lw) {
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
            if ["do", "i", "a", "lub", "albo", "oraz", "czy"].contains(&noun.as_str()) {
                let nxt = noun_after(s, m.get(1)?.end());
                noun = if full(&format!(r"{MONTHS_GEN}|roku|r"), &nxt) { String::new() } else { nxt.clone() };
                if full(MONTHS_GEN, &nxt) {
                    return None;
                }
            }
            let p = prep.as_str();
            let case = if GEN_PREPS.contains(&p) {
                Some("gen")
            } else if DAT_PREPS.contains(&p) {
                Some("dat")
            } else if LOC_PREPS.contains(&p) {
                Some("loc")
            } else {
                let mut cs = if noun.is_empty() { None } else { suffix_case(&noun) };
                if cs.is_none() && (p == "z" || p == "ze") && (unit.is_some() || lw == "do") {
                    cs = Some("gen");
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
                } else if case == "ins" && !noun.is_empty() && fem_plural_ins(&noun) {
                    gender = "f";
                }
                let w = card(n, case, gender)?;
                return Some(format!("{w}{rest}"));
            }
            if unit.is_some() || noun.is_empty() || !word.chars().next().is_some_and(char::is_lowercase) {
                return None;
            }
            let w = nominative(n, &noun, p)?;
            Some(format!("{w}{rest}"))
        },
    )
}

fn pl_weekdays(t: String, c: &mut Ctx) -> String {
    let days: &[(&str, &str)] = &[
        ("pn", "poniedziałku"),
        ("pon", "poniedziałku"),
        ("wt", "wtorku"),
        ("śr", "środy"),
        ("sr", "środy"),
        ("czw", "czwartku"),
        ("pt", "piątku"),
        ("pią", "piątku"),
        ("sb", "soboty"),
        ("sob", "soboty"),
        ("nd", "niedzieli"),
        ("ndz", "niedzieli"),
        ("niedz", "niedzieli"),
    ];
    let day = r"(pn|pon|wt|śr|sr|czw|pt|pią|sb|sob|nd|ndz|niedz)";
    let s: &str = &t;
    let t2 = c.sub(&rx(&format!(r"(?i)(?<![\w.]){day}(\.)? ?[–-] ?{day}(\.)?(?!\w)")), &t, |m| {
        let dot = if g(m, 4).is_empty() { "" } else { end_dot(s, end(m)) };
        let a = lookup(days, &g(m, 1).to_lowercase())?;
        let b = lookup(days, &g(m, 3).to_lowercase())?;
        Some(format!("od {a} do {b}{dot}"))
    });
    let s2: &str = &t2;
    c.sub(&rx(&format!(r"(?i)(?<![\w.])(od) {day}(\.)? do {day}(\.)?(?!\w)")), &t2, |m| {
        let dot = if g(m, 5).is_empty() { "" } else { end_dot(s2, end(m)) };
        let a = lookup(days, &g(m, 2).to_lowercase())?;
        let b = lookup(days, &g(m, 4).to_lowercase())?;
        Some(format!("{} {a} do {b}{dot}", g(m, 1)))
    })
}

fn pl_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<![\w.])([Oo])k\. (?=\d)"), &t, r"\1koło ");
    let t = c.sub_tpl(&rx(r"\b([Ww]) dn\. (?=\d)"), &t, r"\1 dniu ");
    let table: &[(&str, &str)] = &[
        ("tj.", "to jest"),
        ("wg", "według"),
        ("zob.", "zobacz"),
        ("jw.", "jak wyżej"),
        ("cdn.", "ciąg dalszy nastąpi"),
        ("br.", "bieżącego roku"),
        ("ds.", "do spraw"),
        ("im.", "imienia"),
        ("dn.", "dnia"),
    ];
    let s: &str = &t;
    c.sub(
        &rx(
            r"(?<![\w.])(tj\.|[Ww]g|[Zz]ob\.|jw\.|cdn\.|br\.|ds\.|im\.(?= [A-ZĄĆĘŁŃÓŚŹŻ])|dn\.(?= \d)|ub\. ?r\.)(?!\w)",
        ),
        &t,
        |m| {
            let a = g(m, 1);
            if a.starts_with("ub") {
                return Some(format!("ubiegłego roku{}", end_dot(s, end(m))));
            }
            let w = lookup(table, &a.to_lowercase())?;
            let out = if a.chars().next().is_some_and(char::is_lowercase) { w.to_string() } else { py_capitalize(w) };
            let dot = if a.ends_with('.') && a != "im." { end_dot(s, end(m)) } else { "" };
            Some(format!("{out}{dot}"))
        },
    )
}
