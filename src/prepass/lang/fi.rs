//! 'fi' rules: the port of the workbench's `langrules/fi.py` (ids `fi.*`).
//!
//! Finnish numbers take the case of the noun they count (kolmessa maassa, viiden päivän, kolmannelle sijalle) except
//! in the nominative and partitive, where the grammar's reading is already right. The case rules write the declined
//! number themselves, built from the digits.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("fi.thousands", fi_thousands),
    ("fi.time-dot", fi_time_dot),
    ("fi.date", fi_date),
    ("fi.abbrev", fi_abbrev),
    ("fi.money", fi_money),
    ("fi.units", fi_units),
    ("fi.half", fi_half),
    ("fi.colon-suffix", fi_colon_suffix),
    ("fi.case", fi_case),
];

const SP: &str = r"[ \t\x{A0}]";
const CASES: [&str; 10] = ["gen", "part", "ine", "ela", "ill", "ade", "abl", "all", "ess", "tra"];

fn caps<'t>(pat: &str, s: &'t str) -> Option<Captures<'t, str>> {
    rx(pat).captures(s).ok().flatten()
}

fn set(words: &'static str) -> HashSet<&'static str> {
    words.split_whitespace().collect()
}

/// Cardinal parts in every case: nominative, then CASES in order.
const CARD: &[(&str, &str)] = &[
    ("yksi", "yhden yhtä yhdessä yhdestä yhteen yhdellä yhdeltä yhdelle yhtenä yhdeksi"),
    ("kaksi", "kahden kahta kahdessa kahdesta kahteen kahdella kahdelta kahdelle kahtena kahdeksi"),
    ("kolme", "kolmen kolmea kolmessa kolmesta kolmeen kolmella kolmelta kolmelle kolmena kolmeksi"),
    ("neljä", "neljän neljää neljässä neljästä neljään neljällä neljältä neljälle neljänä neljäksi"),
    ("viisi", "viiden viittä viidessä viidestä viiteen viidellä viideltä viidelle viitenä viideksi"),
    ("kuusi", "kuuden kuutta kuudessa kuudesta kuuteen kuudella kuudelta kuudelle kuutena kuudeksi"),
    (
        "seitsemän",
        "seitsemän seitsemää seitsemässä seitsemästä seitsemään seitsemällä seitsemältä seitsemälle seitsemänä seitsemäksi",
    ),
    (
        "kahdeksan",
        "kahdeksan kahdeksaa kahdeksassa kahdeksasta kahdeksaan kahdeksalla kahdeksalta kahdeksalle kahdeksana kahdeksaksi",
    ),
    (
        "yhdeksän",
        "yhdeksän yhdeksää yhdeksässä yhdeksästä yhdeksään yhdeksällä yhdeksältä yhdeksälle yhdeksänä yhdeksäksi",
    ),
    (
        "kymmenen",
        "kymmenen kymmentä kymmenessä kymmenestä kymmeneen kymmenellä kymmeneltä kymmenelle kymmenenä kymmeneksi",
    ),
    ("sata", "sadan sataa sadassa sadasta sataan sadalla sadalta sadalle satana sadaksi"),
    ("tuhat", "tuhannen tuhatta tuhannessa tuhannesta tuhanteen tuhannella tuhannelta tuhannelle tuhantena tuhanneksi"),
    (
        "miljoona",
        "miljoonan miljoonaa miljoonassa miljoonasta miljoonaan miljoonalla miljoonalta miljoonalle miljoonana miljoonaksi",
    ),
];
const UNITS: [&str; 9] = ["yksi", "kaksi", "kolme", "neljä", "viisi", "kuusi", "seitsemän", "kahdeksan", "yhdeksän"];

fn case_index(case: &str) -> usize {
    CASES.iter().position(|c| *c == case).expect("case")
}

/// One cardinal part in a case: cform("viisi", "ade") == "viidellä".
fn cform(word: &str, case: &str) -> String {
    let (nom, forms) = CARD.iter().find(|(n, _)| *n == word).expect("cardinal part");
    if case == "nom" { nom.to_string() } else { forms.split(' ').nth(case_index(case)).expect("form").to_string() }
}

fn card_below_1000(n: u128, case: &str) -> String {
    let mut out = String::new();
    let (h, r) = (n / 100, n % 100);
    let mult = if case == "nom" { "part" } else { case };
    if h == 1 {
        out += &cform("sata", case);
    } else if h > 0 {
        out += &cform(UNITS[h as usize - 1], case);
        out += &cform("sata", mult);
    }
    if (1..=9).contains(&r) {
        out += &cform(UNITS[r as usize - 1], case);
    } else if r == 10 {
        out += &cform("kymmenen", case);
    } else if (11..=19).contains(&r) {
        out += &cform(UNITS[r as usize - 11], case);
        out += "toista";
    } else if r >= 20 {
        let (tens, ones) = (r / 10, r % 10);
        out += &cform(UNITS[tens as usize - 1], case);
        out += &cform("kymmenen", mult);
        if ones > 0 {
            out += &cform(UNITS[ones as usize - 1], case);
        }
    }
    out
}

/// A cardinal 1 – 999 999 999 in a case: cardinal(23, "ine") == "kahdessakymmenessäkolmessa".
fn cardinal(n: u128, case: &str) -> String {
    let mut parts = Vec::new();
    let (mil, rest) = (n / 1_000_000, n % 1_000_000);
    let (th, below) = (rest / 1000, rest % 1000);
    let mult = if case == "nom" { "part" } else { case };
    for (k, base) in [(mil, "miljoona"), (th, "tuhat")] {
        if k == 1 {
            parts.push(cform(base, case));
        } else if k > 0 {
            parts.push(card_below_1000(k, case) + &cform(base, mult));
        }
    }
    if below > 0 {
        parts.push(card_below_1000(below, case));
    }
    parts.join(if mil > 0 { " " } else { "" })
}

/// Ordinal parts: nominative, the -nne- stem, the -nte- stem, the partitive.
const ORD: &[(&str, &str, &str, &str)] = &[
    ("kolmas", "kolmanne", "kolmante", "kolmatta"),
    ("neljäs", "neljänne", "neljänte", "neljättä"),
    ("viides", "viidenne", "viidente", "viidettä"),
    ("kuudes", "kuudenne", "kuudente", "kuudetta"),
    ("seitsemäs", "seitsemänne", "seitsemänte", "seitsemättä"),
    ("kahdeksas", "kahdeksanne", "kahdeksante", "kahdeksatta"),
    ("yhdeksäs", "yhdeksänne", "yhdeksänte", "yhdeksättä"),
    ("kymmenes", "kymmenenne", "kymmenente", "kymmenettä"),
    ("sadas", "sadanne", "sadante", "sadatta"),
    ("tuhannes", "tuhannenne", "tuhannente", "tuhannetta"),
    ("yhdes", "yhdenne", "yhdente", "yhdettä"),
    ("kahdes", "kahdenne", "kahdente", "kahdetta"),
];
/// ensimmäinen / toinen: nominative, then CASES.
const ORD12: &[(&str, &str)] = &[
    (
        "ensimmäinen",
        "ensimmäisen ensimmäistä ensimmäisessä ensimmäisestä ensimmäiseen ensimmäisellä ensimmäiseltä ensimmäiselle ensimmäisenä ensimmäiseksi",
    ),
    ("toinen", "toisen toista toisessa toisesta toiseen toisella toiselta toiselle toisena toiseksi"),
];
const ORD_UNITS: [&str; 9] =
    ["yhdes", "kahdes", "kolmas", "neljäs", "viides", "kuudes", "seitsemäs", "kahdeksas", "yhdeksäs"];

fn harmony<'a>(stem: &str, back: &'a str, front: &'a str) -> &'a str {
    if stem.contains(['a', 'o', 'u']) { back } else { front }
}

/// One ordinal part in a case: oform("kolmas", "all") == "kolmannelle".
fn oform(word: &str, case: &str) -> String {
    if let Some((nom, forms)) = ORD12.iter().find(|(n, _)| *n == word) {
        return if case == "nom" {
            nom.to_string()
        } else {
            forms.split(' ').nth(case_index(case)).expect("form").into()
        };
    }
    let (nom, nne, nte, part) = ORD.iter().find(|(n, ..)| *n == word).expect("ordinal part");
    match case {
        "nom" => nom.to_string(),
        "part" => part.to_string(),
        "ill" => format!("{nte}en"),
        "ess" => format!("{nte}{}", harmony(nte, "na", "nä")),
        _ => {
            let end = match case {
                "gen" => "n",
                "ine" => harmony(nne, "ssa", "ssä"),
                "ela" => harmony(nne, "sta", "stä"),
                "ade" => harmony(nne, "lla", "llä"),
                "abl" => harmony(nne, "lta", "ltä"),
                "all" => "lle",
                _ => "ksi",
            };
            format!("{nne}{end}")
        }
    }
}

/// An ordinal 1–999 in a case: ordinal(3, "all") == "kolmannelle"; None from 1000 up.
fn ordinal(n: u128, case: &str) -> Option<String> {
    if !(1..=999).contains(&n) {
        return None;
    }
    let mut out = String::new();
    let (h, r) = (n / 100, n % 100);
    if h == 1 {
        out += &oform("sadas", case);
    } else if h > 0 {
        out += &oform(ORD_UNITS[h as usize - 1], case);
        out += &oform("sadas", case);
    }
    if r == 1 {
        out += &oform("ensimmäinen", case);
    } else if r == 2 {
        out += &oform("toinen", case);
    } else if (3..=9).contains(&r) {
        out += &oform(ORD_UNITS[r as usize - 1], case);
    } else if r == 10 {
        out += &oform("kymmenes", case);
    } else if (11..=19).contains(&r) {
        out += &oform(ORD_UNITS[r as usize - 11], case);
        out += "toista";
    } else if r >= 20 {
        let (tens, ones) = (r / 10, r % 10);
        out += &oform(ORD_UNITS[tens as usize - 1], case);
        out += &oform("kymmenes", case);
        if ones == 1 {
            out += &oform("ensimmäinen", case);
        } else if ones == 2 {
            out += &oform("toinen", case);
        } else if ones > 0 {
            out += &oform(ORD_UNITS[ones as usize - 1], case);
        }
    }
    Some(out)
}

/// Words after a number that are not the noun it counts, or whose ending only looks like a case.
static STOP: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("on ovat oli olivat olla ollut ja tai sekä mutta kuin että jos kun niin ei en eikä myös vain noin yli alle \
         ennen jälkeen asti saakka lähtien alkaen mennessä kanssa aikana ajan sitten vastaan vuoksi takia mukaan varten lisäksi \
         sijaan verran kohden jäljellä mukana paikalla kotona ulkona sisällä yhdessä kerrallaan aina nyt jo \
         vielä sen tämän sitä se hän he me te minun sinun hänen meidän teidän heidän joka mikä kunnes välillä välissä päässä \
         päästä kuluttua kuluessa edellä takana edessä luona lähellä enemmän vähemmän vähintään enintään ainakin peräkkäin \
         sieltä täältä tuolta siellä täällä tuolla sinne tänne tuonne siksi miksi ensiksi toiseksi huomenna aikanaan yhteensä \
         kertaa prosenttia astetta henkeä paljon uudelleen kauan pian taas vaan siinä tässä tuossa sillä tällä siltä tältä \
         sille tälle tähän siihen tuohon tuon niiden näiden noiden jossa josta jolla jolta jolle johon")
});
static NOT_GEN: LazyLock<HashSet<&str>> =
    LazyLock::new(|| set("puhelin avain soitin kirjoitin keitin sydän ihminen nainen"));
/// Elatives of nouns often counted (other -sta / -stä words are taken for partitives: ihmistä, asukasta, tapausta).
static ELATIVE: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("päivästä vuodesta viikosta kuukaudesta tunnista minuutista sekunnista eurosta sentistä kilosta grammasta \
         litrasta desilitrasta metristä kilometristä senttimetristä millimetristä prosentista maasta kaupungista kunnasta \
         talosta asunnosta osasta kohdasta luvusta sivusta kirjasta vaihtoehdosta hengestä lapsesta henkilöstä jäsenestä \
         opiskelijasta kerrasta ottelusta pelistä tehtävästä työntekijästä koulusta autosta junasta paikasta lajista \
         kappaleesta")
});
/// Partitives in -ltä / -lta an ablative ending would be read into.
static PART_LTA: LazyLock<HashSet<&str>> = LazyLock::new(|| set("kieltä tuulta puolta nuolta pieltä suolta"));
/// Partitive nouns after an ordinal, which then is partitive too (viidettä kertaa); other partitives (3. toukokuuta)
/// keep the nominative ordinal.
static PART_ORD: LazyLock<HashSet<&str>> =
    LazyLock::new(|| set("kertaa vuotta kautta päivää viikkoa kuukautta kierrosta"));
static YEAR_CUE: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("vuonna vuoden vuodesta vuoteen vuosina vuosi vuodelta vuodelle v. klo kello sivu sivulla s. nro \
         numero luku kohta kohdassa huone linja versio")
});

fn ends_any(s: &str, ends: &[&str]) -> bool {
    ends.iter().any(|e| s.ends_with(e))
}

/// The case of the noun after a number, from its ending: gen ine ela ill ade abl all ess tra; None for the
/// nominative, the partitive and words that are not a counted noun.
fn noun_case(w: &str, one: bool) -> Option<&'static str> {
    if STOP.contains(w) || w.chars().count() < 3 || ends_any(w, &["taan", "tään", "daan", "dään"]) {
        return None;
    }
    let table: [(&[&str], &str); 5] = [
        (&["ssaan", "ssään", "ssa", "ssä"], "ine"),
        (&["llaan", "llään", "lla", "llä"], "ade"),
        (&["ltaan", "ltään", "lta", "ltä"], "abl"),
        (&["lleen", "lle"], "all"),
        (&["kseen", "ksi"], "tra"),
    ];
    for (ends, case) in table {
        if ends_any(w, ends) {
            if case == "abl" && PART_LTA.contains(w) {
                return None;
            }
            return Some(case);
        }
    }
    if ends_any(w, &["sta", "stä"]) {
        // most -sta / -stä words after a number are partitives (ihmistä, asukasta, miestä, tapausta): only a long vowel
        // or -kse- before the ending, or a listed noun, makes an elative
        if ELATIVE.contains(w) || search(r"(?:([aeiouyäö])\1|kse)st[aä]$", w) {
            return Some("ela");
        }
        return None;
    }
    if ends_any(w, &["seen", "siin"]) {
        return Some("ill");
    }
    if let Some(m) = caps(r"([aeiouyäö])h([aeiouyäö])n$", w)
        && g(&m, 1) == g(&m, 2)
    {
        return Some("ill");
    }
    if let Some(m) = caps(r"([aeiouyäö])\1n$", w) {
        let start = m.get(0).expect("group 0").start();
        return Some(if search(r"[aeiouyäö]", &w[..start]) { "ill" } else { "gen" });
    }
    if search(r"[aeiouyäö]n$", w) {
        if w.ends_with("nen") || (one && NOT_GEN.contains(w)) {
            return None;
        }
        return Some("gen");
    }
    if !one && search(r"[aeiouyäö]n[aä]$", w) && w.chars().count() >= 5 {
        return Some("ess");
    }
    None
}

fn fi_case(t: String, c: &mut Ctx) -> String {
    let pat =
        [r"(?<![\w.,:/+−–-])(?:(\d+)([-–]))?(\d+)(\.)?(?![\d]|[.,:/]\d)(", SP, r"+)([a-zåäö]+)(?![\w:-])"].concat();
    c.sub(&rx(&pat), &t, |m| {
        let a = m.get(1).map(|x| x.as_str());
        let (num, dot, sep, noun) = (g(m, 3), m.get(4).is_some(), g(m, 5), g(m, 6));
        let n = py_int(num);
        if n == 0
            || n >= 1_000_000_000
            || (!dot && a.is_none() && num.chars().count() == 4 && (1800..=2099).contains(&n))
        {
            return None;
        }
        if let Some(a) = a
            && (dot || py_int(a) == 0 || py_int(a) >= n)
        {
            return None;
        }
        let head = &t[..m.get(0).expect("group 0").start()];
        let prev = caps(&[r"(\S+)", SP, r"+$"].concat(), head);
        if let Some(p) = prev
            && YEAR_CUE.contains(g(&p, 1).to_lowercase().as_str())
        {
            return None;
        }
        let case =
            if dot && PART_ORD.contains(noun) { "part" } else { noun_case(noun, n == 1 && !dot && a.is_none())? };
        let w = if dot { ordinal(n, case)? } else { cardinal(n, case) };
        let first = a.map(|a| format!("{}–", cardinal(py_int(a), case))).unwrap_or_default();
        Some(format!("{first}{w}{sep}{noun}"))
    })
}

const SUFFIX_CASE: &[(&str, &str)] = &[
    ("n", "gen"),
    ("ssa", "ine"),
    ("ssä", "ine"),
    ("sta", "ela"),
    ("stä", "ela"),
    ("lla", "ade"),
    ("llä", "ade"),
    ("lta", "abl"),
    ("ltä", "abl"),
    ("lle", "all"),
    ("ksi", "tra"),
    ("na", "ess"),
    ("nä", "ess"),
    ("a", "part"),
    ("ä", "part"),
    ("ta", "part"),
    ("tä", "part"),
    ("tta", "part"),
    ("ttä", "part"),
    ("aa", "part"),
    ("ää", "part"),
    ("ea", "part"),
    ("een", "ill"),
    ("ään", "ill"),
    ("aan", "ill"),
    ("iin", "ill"),
    ("seen", "ill"),
];
const ORD_SUFFIX: &[(&str, &str)] = &[
    ("s", "nom"),
    ("nnen", "gen"),
    ("nnessa", "ine"),
    ("nnessä", "ine"),
    ("nnesta", "ela"),
    ("nnestä", "ela"),
    ("nnella", "ade"),
    ("nnellä", "ade"),
    ("nnelta", "abl"),
    ("nneltä", "abl"),
    ("nnelle", "all"),
    ("nneksi", "tra"),
    ("ntena", "ess"),
    ("ntenä", "ess"),
    ("nteen", "ill"),
    ("sen", "gen"),
    ("nen", "nom"),
];

fn lookup<'a>(map: &[(&str, &'a str)], k: &str) -> Option<&'a str> {
    map.iter().find(|(a, _)| *a == k).map(|(_, b)| *b)
}

fn fi_colon_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/+−-])(\d+):([a-zåäö]+)(?![\w])"), &t, |m| {
        let (num, suf) = (g(m, 1), g(m, 2));
        let n = py_int(num);
        if n == 0 || n >= 1_000_000_000 || !search(r"\d", &words(&m[0], "fi")) {
            return None;
        }
        if let Some(oc) = lookup(ORD_SUFFIX, suf)
            && (!matches!(suf, "sen" | "nen") || matches!(n % 10, 1 | 2))
        {
            return ordinal(n, oc);
        }
        Some(cardinal(n, lookup(SUFFIX_CASE, suf)?))
    })
}

fn fi_thousands(t: String, c: &mut Ctx) -> String {
    let pat =
        [r"(?<![\d.,:/+−-])(?<!\d", SP, r")([1-9]\d{0,2})((?:[ \x{A0}\x{202F}]\d{3}){2,})(?![\d]|[.,]\d|", SP, r"\d)"]
            .concat();
    c.sub(&rx(&pat), &t, |m| Some(format!("{}{}", g(m, 1), rx(r"\D").replace_all(g(m, 2), ""))))
}

/// A version number's name before a dotted number (Python 3.10, versio 1.2.2024).
const VERSION_CUE: &str = r"(?:^|[^\w.])(?:[Vv]ersio\w*|v\.?|Python|iOS|macOS|OS|Android|Windows|Linux|Ubuntu|Java|Node|PHP|Chrome|Firefox|Safari|Office|Excel)[ \t\x{A0}]*$";

fn fi_time_dot(t: String, c: &mut Ctx) -> String {
    let pat = [r"(?<!\w)((?:klo|kello|Klo|Kello)", SP, r"+)(\d{1,2})\.(\d{2})(?![\d]|[.,]\d)"].concat();
    let t = c.sub(&rx(&pat), &t, |m| {
        if py_int(g(m, 2)) > 23 || py_int(g(m, 3)) > 59 {
            return None;
        }
        Some(format!("{}{}:{}", g(m, 1), g(m, 2), g(m, 3)))
    });
    c.sub(&rx(r"(?<![\w.,:/+−-])([01]\d|2[0-3])\.([0-5]\d)(?![\d]|[.,]\d)"), &t, |m| {
        let (h, mm) = (py_int(g(m, 1)), py_int(g(m, 2)));
        if h > 23 || mm > 59 {
            return None;
        }
        let whole = m.get(0).expect("group 0");
        if search(VERSION_CUE, &t[..whole.start()]) {
            return None;
        }
        let after = &t[whole.end()..];
        if after.starts_with('.') && (1..=12).contains(&mm) {
            return None;
        }
        if matches_at_start(&[SP, r"*(?:[a-zåäö%€$]|\d)"].concat(), after)
            && !matches_at_start(
                &[SP, r"+(?:ja|tai|asti|alkaen|mennessä|lähtien|saakka|jälkeen)(?!\w)"].concat(),
                after,
            )
        {
            return None;
        }
        Some(format!("{}:{}", g(m, 1), g(m, 2)))
    })
}

const MONTHS_PART: [&str; 12] = [
    "tammikuuta",
    "helmikuuta",
    "maaliskuuta",
    "huhtikuuta",
    "toukokuuta",
    "kesäkuuta",
    "heinäkuuta",
    "elokuuta",
    "syyskuuta",
    "lokakuuta",
    "marraskuuta",
    "joulukuuta",
];

fn fi_date(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,:/+−-])(\d{1,2})\.(\d{1,2})\.(\d{4})(?![\d]|\.\d)"), &t, |m| {
        if search(VERSION_CUE, &t[..m.get(0).expect("group 0").start()]) {
            return None;
        }
        let (d, mo) = (py_int(g(m, 1)), py_int(g(m, 2)));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) {
            return None;
        }
        let r = words(&m[0], "fi");
        if search(r"\d|piste", &r) {
            return None;
        }
        Some(r)
    });
    c.sub(&rx(r"(?<![\w.,:/+−-])(\d{1,2})\.(\d{1,2})\.(?![\d]|\.\d|\w)"), &t, |m| {
        let whole = m.get(0).expect("group 0");
        let (d, mo) = (py_int(g(m, 1)), py_int(g(m, 2)));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) || search(VERSION_CUE, &t[..whole.start()]) {
            return None;
        }
        let new = format!("{} {}", ordinal(d, "nom")?, MONTHS_PART[mo as usize - 1]);
        let dot = matches_at_start(&[SP, r"*(?:$|\n)|", SP, r"+[A-ZÅÄÖ]"].concat(), &t[whole.end()..]);
        Some(format!("{new}{}", if dot { "." } else { "" }))
    })
}

const ABBREV: &[(&str, &str)] = &[
    ("n.", "noin"),
    ("ks.", "katso"),
    ("Ks.", "Katso"),
    ("mm.", "muun muassa"),
    ("Mm.", "Muun muassa"),
    ("ym.", "ynnä muuta"),
    ("yms.", "ynnä muuta sellaista"),
    ("vrt.", "vertaa"),
    ("Vrt.", "Vertaa"),
    ("ts.", "toisin sanoen"),
    ("puh.", "puhelin"),
    ("Puh.", "Puhelin"),
];

fn fi_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&[r"(?<![\w.])n\.(?=", SP, r"*\d)"].concat()), &t, "noin");
    let pat = [r"(?<![\w.])(?<!\d", SP, r")(ks|Ks|mm|Mm|ym|yms|vrt|Vrt|ts|puh|Puh)\.(?!\w)"].concat();
    c.sub(&rx(&pat), &t, |m| lookup(ABBREV, &format!("{}.", g(m, 1))).map(str::to_string))
}

fn fi_money(t: String, c: &mut Ctx) -> String {
    let pat = [r"(?<![\w.,])USD", SP, r"?(\d+(?:[ \x{A0}]\d{3})*(?:,\d{1,2})?)(?![\d.,]\d|\w)"].concat();
    let t = c.sub_tpl(&rx(&pat), &t, r"\1 $");
    c.sub(&rx(&[r"(?<=\d)(", SP, r"?)(USD|eur|EUR)\.?(?![\w])"].concat()), &t, |m| {
        Some(format!("{}{}", g(m, 1), if g(m, 2) == "USD" { "$" } else { "€" }))
    })
}

/// Unit abbreviations the grammar leaves as typed: nominative singular, partitive.
const UNIT_WORDS: &[(&str, &str, &str)] = &[
    ("h", "tunti", "tuntia"),
    ("min", "minuutti", "minuuttia"),
    ("s", "sekunti", "sekuntia"),
    ("sek", "sekunti", "sekuntia"),
    ("ms", "millisekunti", "millisekuntia"),
    ("vrk", "vuorokausi", "vuorokautta"),
    ("kk", "kuukausi", "kuukautta"),
    ("tl", "teelusikallinen", "teelusikallista"),
    ("rkl", "ruokalusikallinen", "ruokalusikallista"),
    ("kpl", "kappale", "kappaletta"),
    ("hlö", "henkilö", "henkilöä"),
    ("ha", "hehtaari", "hehtaaria"),
    ("snt", "sentti", "senttiä"),
];
const UNIT_RX: &str = r"(h|min|sek|ms|s|vrk|kk|tl|rkl|kpl|hlö|ha|snt)";

fn fi_units(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&[r"(?<![\w.,])(\d+(?:,\d+)?)(", SP, r"?)", UNIT_RX, r"\.?(?![\w/²³])"].concat()), &t, |m| {
        if g(m, 3) == "s" && g(m, 2).is_empty() {
            return None; // 2020s, 5s: only a spaced s is seconds
        }
        let (_, nom, part) = UNIT_WORDS.iter().find(|(ab, ..)| *ab == g(m, 3))?;
        Some(format!("{} {}", g(m, 1), if g(m, 1) == "1" { nom } else { part }))
    })
}

fn fi_half(t: String, c: &mut Ctx) -> String {
    let pat =
        [r"(?<![\w.,:/])(?:(\d+)", SP, r"+)?(1/2|½)(?![\d/])", SP, r"*([a-zåäö]+\.?|[a-zA-Z]+)(?![\w/])"].concat();
    c.sub(&rx(&pat), &t, |m| {
        let tok = g(m, 3);
        let two = words("2", "fi");
        let r = words(&format!("2 {tok}"), "fi");
        let unit = r.strip_prefix(&format!("{two} "))?;
        let new = match m.get(1).map(|x| x.as_str()) {
            None => format!("puoli {unit}"),
            Some("1") => format!("puolitoista {unit}"),
            Some(n) => format!("{} ja puoli {unit}", words(n, "fi")),
        };
        if new == words(&m[0], "fi") { None } else { Some(new) }
    })
}
