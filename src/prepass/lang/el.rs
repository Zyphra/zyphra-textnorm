//! 'el' rules: the port of the workbench's `langrules/el.py` (ids `el.*`).
//!
//! The grammar reads every number in its neuter citation form (τρία, τέσσερα, διακόσια, χίλια, ένα). Greek numbers
//! agree with the noun they count; these rules find the noun's gender and case from its ending (and short lexicons), or
//! from the article before the number, and write the agreeing number words themselves.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("el.abbrev-case", el_abbrev_case),
    ("el.century", el_century),
    ("el.ampm", el_ampm),
    ("el.half", el_half),
    ("el.date-day", el_date_day),
    ("el.scale-one", el_scale_one),
    ("el.money-range", el_money_range),
    ("el.money-decimal", el_money_decimal),
    ("el.pound", el_pound),
    ("el.groups-unit", el_groups_unit),
    ("el.per-unit", el_per_unit),
    ("el.units", el_units),
    ("el.number-agree", el_number_agree),
];

/// Lowercase without accents: ώρες -> ωρες.
fn plain(w: &str) -> String {
    w.to_lowercase()
        .chars()
        .map(|ch| match ch {
            'ά' => 'α',
            'έ' => 'ε',
            'ή' => 'η',
            'ί' | 'ϊ' | 'ΐ' => 'ι',
            'ό' => 'ο',
            'ύ' | 'ϋ' | 'ΰ' => 'υ',
            'ώ' => 'ω',
            c => c,
        })
        .collect()
}

fn set(words: &'static str) -> HashSet<&'static str> {
    words.split_whitespace().collect()
}

fn ends_any(s: &str, ends: &[&str]) -> bool {
    ends.iter().any(|e| s.ends_with(e))
}

fn caps<'t>(pat: &str, s: &'t str) -> Option<Captures<'t, str>> {
    rx(pat).captures(s).ok().flatten()
}

/// Words after a number that are not the counted noun (plain forms).
static STOP: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("τους οι των της τις τα το του τη την μας σας μου σου εμεις εσεις αυτοι αυτες αυτους αυτων ολοι ολες ολους \
         ολων ειναι ηταν εως ως μεχρι και η με σε απο για εκ επι πανω κατω οπου παντου αλλου που πως ενω οταν αν προς εκτος \
         εντος ισως μεταξυ εναντιον")
});

/// Feminine nouns whose ending does not say so (plain forms).
static FEM: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("ωρα ωρας ωρες ωρων μερα μερας μερες μερων ημερα ημερας ημερες ημερων φορα φορας φορες φορων νυχτα νυχτας \
         νυχτες νυχτων χρονια χρονιας χρονιες χρονιων γυναικα γυναικας γυναικες γυναικων ψηφος ψηφου ψηφο ψηφοι ψηφους ψηφων \
         εργασιμη εργασιμης εργασιμες εργασιμων χωρα χωρας χωρες χωρων πολη πολης πολεις πολεων δραχμη δραχμης δραχμες δραχμων \
         λιρα λιρας λιρες λιρων κουπα κουπας κουπες κουπων φετα φετας φετες φετων σταγονα σταγονας σταγονες σταγονων γλωσσα \
         γλωσσας γλωσσες γλωσσων πορτα πορτας πορτες πορτων γραμμη γραμμης γραμμες γραμμων στιγμη στιγμης στιγμες στιγμων \
         εκλογη εκλογης εκλογες εκλογων πλευρα πλευρας πλευρες πλευρων σειρα σειρας σειρες σειρων μοιρα μοιρας μοιρες μοιρων \
         στροφη στροφης στροφες στροφων νικη νικης νικες νικων ηττα ηττας ηττες ηττων μετοχη μετοχης μετοχες μετοχων κλινη \
         κλινης κλινες κλινων σχολη σχολης σχολες σχολων μηχανη μηχανης μηχανες μηχανων αδελφη αδελφης αδελφες αδελφων αδερφη \
         αδερφης αδερφες αδερφων κορη κορης κορες κορων βδομαδα βδομαδας βδομαδες βδομαδων κουταλια κουταλιας κουταλιες \
         κουταλιων τουαλετα τουαλετας τουαλετες βολτα βολτας βολτες πιτα πιτας πιτες πιτων ζωνη ζωνης ζωνες ζωνων φωνη φωνης \
         φωνες φωνων ψυχη ψυχης ψυχες ψυχων αρχη αρχης αρχες αρχων τιμη τιμης τιμες τιμων φορτωση μπαλα μπαλας μπαλες μπαλων \
         θυρα θυρας θυρες θυρων αιθουσα αιθουσας αιθουσες αιθουσων λεξη λεξης λεξεις λεξεων ταινια ταινιας ταινιες ταινιων \
         οδος οδου οδο οδοι οδους οδων μεθοδος μεθοδου μεθοδο μεθοδοι μεθοδους μεθοδων περιοδος περιοδου περιοδο περιοδοι \
         περιοδους περιοδων εισοδος εισοδου εισοδο εισοδοι εισοδους εισοδων εξοδος εξοδου εξοδο εξοδοι εξοδους εξοδων \
         παραγραφος παραγραφου παραγραφο παραγραφοι παραγραφους παραγραφων νησος νησου νησοι νησους νησων λεωφορος λεωφορου \
         λεωφοροι λεωφορους λεωφορων διαλεκτος διαλεκτοι διαλεκτους διαλεκτων ηπειρος ηπειρου ηπειροι ηπειρους ηπειρων \
         θερμιδα θερμιδας θερμιδες θερμιδων μεριδα μεριδας μεριδες μεριδων κιλοθερμιδα")
});

/// Masculine nouns an ending would take for feminine, and masculine -ες/-ας/-ης nouns (plain forms).
static MASC: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("τραυματιες τραυματιας τραυματια ταμιες ταμιας νεανιες μηνες μηνας μηνα μηνων αντρες αντρας αντρα αντρων \
         ανδρες ανδρας ανδρα ανδρων πατερες πατερας πατερα αιωνες αιωνας αιωνα αιωνων αγωνες αγωνας αγωνα αγωνων χειμωνες \
         χειμωνας επιβατες επιβατης επιβατη επιβατων πελατες πελατης πελατη πελατων εργατες εργατης εργατη εργατων μαθητες \
         μαθητης μαθητη μαθητων φοιτητες φοιτητης φοιτητη φοιτητων αθλητες αθλητης αθλητη αθλητων πολιτες πολιτης πολιτη \
         πολιτων τουριστες τουριστας τουριστα τουριστων βουλευτες βουλευτης βουλευτη βουλευτων ναυτες ναυτης ναυτων \
         στρατιωτες στρατιωτης στρατιωτη στρατιωτων πλανητες πλανητης κατοικοι κατοικους κατοικων γονεις γονεων συγγραφεις \
         συγγραφεα συγγραφεων")
});

/// Neuter nouns in -ος (genitive -ους): έτος, μέρος, ... (plain forms).
static NEUT_OS: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("ετος ετους μερος μερους κρατος κρατους λαθος λαθους βαρος βαρους υψος υψους μηκος μηκους πλατος πλατους \
         βαθος βαθους παχος παχους μεγεθος μεγεθους κοστος κοστους εδαφος εδαφους δασος δασους ορος ορους τελος τελους εθνος \
         εθνους γενος γενους ειδος ειδους πληθος πληθους κερδος κερδους χρεος χρεους στελεχος στελεχους σκευος σκευους αγχος \
         αγχους ξιφος ξιφους ηθος ηθους φυλλο λαθη ετη μερη κρατη")
});

const FEM_SG: &[&str] = &["εια", "αδα", "ιδα", "τητα", "ουλα", "ιτσα", "τρια", "ισσα", "αινα", "ση", "ξη", "ψη"];
const FEM_SG_GEN: &[&str] = &["ειας", "αδας", "ιδας", "τητας", "σης", "ξης", "ψης"];
const FEM_PL: &[&str] = &["αδες", "ιδες", "ειες", "τητες", "ουλες", "ιτσες", "τριες", "ισσες"];
const MASC_PL: &[&str] = &["ωνες", "ηνες", "ντρες", "ητες", "ατες", "ιστες", "τηρες", "ηδες"];
const FEM_PL_GEN: &[&str] = &["αδων", "ιδων"];

/// Gender ("f" "m" "n" "mf" "mn"; "" for unknown) and case ("nom" "acc" "gen" "na"; "" for none).
type GC = (&'static str, &'static str);

/// The gender and case of the noun after a number, from its ending and the lexicons; None when the word says nothing.
/// `one`: the number is 1, so the noun is singular.
fn noun_case(w: &str, one: bool) -> Option<GC> {
    let p = plain(w);
    let low = w.to_lowercase();
    if STOP.contains(p.as_str()) || p.chars().count() < 3 {
        return None;
    }
    if one {
        if FEM.contains(p.as_str()) {
            return Some(("f", if ends_any(&p, &["ας", "ης", "ου"]) { "gen" } else { "na" }));
        }
        if NEUT_OS.contains(p.as_str()) {
            return Some(if p.ends_with("ους") { ("n", "gen") } else { ("n", "") });
        }
        if MASC.contains(p.as_str()) {
            let c = if p.ends_with("ου") {
                "gen"
            } else if ends_any(&p, &["ος", "ας", "ης"]) {
                "nom"
            } else {
                "acc"
            };
            return Some(("m", c));
        }
        if low.ends_with("ία") || ends_any(&p, FEM_SG) {
            return Some(("f", "na"));
        }
        if ends_any(&p, FEM_SG_GEN) {
            return Some(("f", "gen"));
        }
        if p.ends_with("ου") && p.chars().count() >= 4 {
            return Some(("mn", "gen"));
        }
        if ends_any(&p, &["ος", "της", "ωνας", "ηνας", "ντρας"]) {
            return Some(("m", "nom"));
        }
        return None;
    }
    let mut g = if FEM.contains(p.as_str()) {
        "f"
    } else if MASC.contains(p.as_str()) {
        "m"
    } else {
        ""
    };
    if p.ends_with("ων") {
        if g.is_empty() {
            g = if ends_any(&p, FEM_PL_GEN) || low.ends_with("εων") { "f" } else { "mn" };
        }
        return Some((g, "gen"));
    }
    if g == "f" {
        return Some(("f", "na"));
    }
    if p.ends_with("οι") {
        return Some(("m", "nom"));
    }
    if p.ends_with("ους") {
        return Some(("m", "acc"));
    }
    if g == "m" {
        return Some(("m", "na"));
    }
    if low.ends_with("είς") {
        return Some(("mf", "na"));
    }
    if p.ends_with("εις") {
        return Some(("f", "na"));
    }
    if p.ends_with("ες") {
        if low.ends_with("ίες") || ends_any(&p, FEM_PL) {
            return Some(("f", "na"));
        }
        if ends_any(&p, MASC_PL) {
            return Some(("m", "na"));
        }
        return Some(("mf", "na"));
    }
    if ends_any(&p, &["α", "η"]) {
        return Some(("n", ""));
    }
    None
}

/// The article before the number: (gender, case); the singular feminine ones only for 1.
const ARTICLE: &[(&str, GC)] = &[
    ("τις", ("f", "na")),
    ("στις", ("f", "na")),
    ("τους", ("m", "acc")),
    ("στους", ("m", "acc")),
    ("οι", ("mf", "nom")),
    ("των", ("", "gen")),
    ("στων", ("", "gen")),
    ("την", ("f", "na")),
    ("στην", ("f", "na")),
    ("τη", ("f", "na")),
    ("στη", ("f", "na")),
];
const ARTICLE_RX: &str = r"(?<!\w)(σ?τις|σ?τους|οι|σ?των|σ?την|σ?τη)[ \t\x{A0}]+$";

fn article_case(head: &str, one: bool) -> Option<GC> {
    let m = caps(ARTICLE_RX, head)?;
    let a = g(&m, 1);
    if matches!(a, "την" | "στην" | "τη" | "στη") && !one {
        return None;
    }
    ARTICLE.iter().find(|(k, _)| *k == a).map(|(_, v)| *v)
}

const SCALES: &[&str] = &[
    "χιλιάδες",
    "χιλιάδων",
    "εκατομμύριο",
    "εκατομμύρια",
    "δισεκατομμύριο",
    "δισεκατομμύρια",
    "τρισεκατομμύριο",
    "τρισεκατομμύρια",
];
const GEN: &[(&str, &str)] = &[
    ("ένα", "ενός"),
    ("μία", "μιας"),
    ("μια", "μιας"),
    ("τρία", "τριών"),
    ("τρεις", "τριών"),
    ("τέσσερα", "τεσσάρων"),
    ("τέσσερις", "τεσσάρων"),
    ("δεκατρία", "δεκατριών"),
    ("δεκατρείς", "δεκατριών"),
    ("δεκατέσσερα", "δεκατεσσάρων"),
    ("δεκατέσσερις", "δεκατεσσάρων"),
    ("χίλια", "χιλίων"),
    ("χιλιάδες", "χιλιάδων"),
    ("εκατομμύριο", "εκατομμυρίου"),
    ("εκατομμύρια", "εκατομμυρίων"),
    ("δισεκατομμύριο", "δισεκατομμυρίου"),
    ("δισεκατομμύρια", "δισεκατομμυρίων"),
    ("τρισεκατομμύριο", "τρισεκατομμυρίου"),
    ("τρισεκατομμύρια", "τρισεκατομμυρίων"),
];
const NONNEUT: &[(&str, &str)] =
    &[("τρία", "τρεις"), ("τέσσερα", "τέσσερις"), ("δεκατρία", "δεκατρείς"), ("δεκατέσσερα", "δεκατέσσερις")];

fn lookup<'a>(map: &[(&str, &'a str)], k: &str) -> Option<&'a str> {
    map.iter().find(|(a, _)| *a == k).map(|(_, b)| *b)
}

/// One number word of the last group (after the last scale word) in gender g and case c.
fn agree_word(w: &str, g: &str, c: &str) -> String {
    if c == "gen" {
        if w == "ένα" && g == "f" {
            return "μιας".into();
        }
        if w.ends_with("κόσια") || w.ends_with("κόσιες") {
            let i = w.rfind("κόσι").expect("κόσι");
            return format!("{}κοσίων", &w[..i]);
        }
        return lookup(GEN, w).unwrap_or(w).to_string();
    }
    let w = if matches!(g, "m" | "f" | "mf") { lookup(NONNEUT, w).unwrap_or(w) } else { w };
    if w == "ένα" {
        return if g == "f" {
            "μία".into()
        } else if (g, c) == ("m", "nom") {
            "ένας".into()
        } else {
            w.into()
        };
    }
    if w.ends_with("κόσια") || w == "χίλια" {
        let mut stem = w.to_string();
        stem.pop();
        if g == "f" {
            return stem + "ες";
        }
        if g == "m" && c == "nom" {
            return stem + "οι";
        }
        if g == "m" && c == "acc" {
            return stem + "ους";
        }
    }
    w.to_string()
}

/// The grammar's neuter reading of a number in gender g and case c: only the last group agrees with the noun; in the
/// genitive every word declines.
fn agree(reading: &str, g: &str, c: &str) -> String {
    let toks: Vec<&str> = reading.split(' ').collect();
    let last = toks.iter().enumerate().filter(|(_, w)| SCALES.contains(w)).map(|(i, _)| i as isize).max().unwrap_or(-1);
    let mut out = Vec::with_capacity(toks.len());
    for (i, w) in toks.iter().enumerate() {
        if i as isize > last {
            out.push(agree_word(w, g, c));
        } else if c == "gen" {
            let next = &toks[(i + 1).min(toks.len())..(i + 3).min(toks.len())];
            out.push(agree_word(w, if next.contains(&"χιλιάδες") { "f" } else { "n" }, "gen"));
        } else {
            out.push(w.to_string());
        }
    }
    out.join(" ")
}

const NUM: &str = r"(\d{1,3}(?:\.\d{3})+|\d+)";
const GREEK_WORD: &str = r"([ΐά-ώ]+)";

/// The gender and case a number written at t[start:end] takes: from the noun after it (and the word after an unknown
/// -ες adjective), else from the article before it. None: leave the number to the grammar.
fn features(t: &str, start: usize, end: usize, num: &str, noun: Option<&str>, plural_hint: bool) -> Option<GC> {
    let one = num == "1" && !plural_hint;
    let mut f = noun.and_then(|n| noun_case(n, one));
    if let Some((fg, fc)) = f
        && fg == "n"
        && fc != "gen"
    {
        return None;
    }
    let art = article_case(&t[..start], one);
    if let Some((fg, fc)) = f
        && matches!(fg, "mf" | "mn" | "")
        && fc != "gen"
        && !one
    {
        let f2 = caps(r"^[ \t\x{A0}]+([ΐά-ώ]+)(?!\w)", &t[end..]).and_then(|m| noun_case(g(&m, 1), false));
        if let Some((g2, c2)) = f2
            && matches!(g2, "m" | "f")
            && c2 == fc
        {
            f = f2;
        }
    }
    let Some((mut gg, mut cc)) = f else {
        if let Some(n) = noun
            && noun_case(n, one).is_none()
            && !STOP.contains(plain(n).as_str())
        {
            return None; // a word that says nothing: an article alone is not enough
        }
        return art;
    };
    if let Some((ag, ac)) = art {
        if matches!(gg, "mf" | "mn") && matches!(ag, "m" | "f") {
            gg = ag;
        }
        if cc == "na" && matches!(ac, "nom" | "acc") {
            cc = ac;
        }
    }
    Some((gg, cc))
}

fn el_number_agree(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"(?<![\w.,:/−+-])(?:{NUM}([ \t\x{{A0}}]?[-–][ \t\x{{A0}}]?|[ \t\x{{A0}}]+(?:έως|ως|μέχρι|με|ή|και)[ \t\x{{A0}}]+))?([-−])?{NUM}(?![\w%°€$£]|[.,:/]\d)(?:([ \t\x{{A0}}]+){GREEK_WORD}(?!\w))?"
    ));
    c.sub(&re, &t, |m| {
        let whole = m.get(0).expect("group 0");
        let (a, sep, sign, num) = (m.get(1).map(|x| x.as_str()), g(m, 2), g(m, 3), g(m, 4));
        let noun = m.get(6).map(|x| x.as_str());
        if a.is_some() && !sign.is_empty() {
            return None;
        }
        if noun.is_none() && !matches_at_start(r#"[ \t\x{A0}]*(?:$|[.,;!?…)»"”\n])"#, &t[whole.end()..]) {
            return None; // no noun: only before the end of the phrase (not στις 3 €)
        }
        let (gg, cs) = features(&t, whole.start(), whole.end(), num, noun, a.is_some())?;
        let tail = format!("{}{}", g(m, 5), noun.unwrap_or(""));
        if let Some(a) = a {
            let (ra, rb) = (words(a, "el"), words(num, "el"));
            let mut sep = sep.to_string();
            if matches!(sep.trim(), "-" | "–") {
                if py_int(&a.replace('.', "")) >= py_int(&num.replace('.', ""))
                    || words(&format!("{a}-{num}"), "el") != format!("{ra} έως {rb}")
                {
                    return None;
                }
                sep = " έως ".into();
            }
            let new = format!("{}{sep}{}", agree(&ra, gg, cs), agree(&rb, gg, cs));
            return if new == format!("{ra}{sep}{rb}") { None } else { Some(new + &tail) };
        }
        let r = words(&format!("{sign}{num}"), "el");
        let new = agree(&r, gg, cs);
        if new == r { None } else { Some(new + &tail) }
    })
}

const MONTHS: &str = "Ιανουαρίου|Φεβρουαρίου|Μαρτίου|Απριλίου|Μαΐου|Ιουνίου|Ιουλίου|Αυγούστου|Σεπτεμβρίου|Οκτωβρίου|Νοεμβρίου|\
                      Δεκεμβρίου|Γενάρη|Φλεβάρη|Μάρτη|Απρίλη|Μάη|Ιούνη|Ιούλη|Σεπτέμβρη|Οκτώβρη|Νοέμβρη|Δεκέμβρη";

fn el_date_day(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w.,:/−+-])(\d{{1,2}})([ \t\x{{A0}}]+(?:{MONTHS}))(?!\w)")), &t, |m| {
        let d = py_int(g(m, 1));
        if !(1..=31).contains(&d) {
            return None;
        }
        if d == 1 {
            return Some(format!("πρώτη{}", g(m, 2)));
        }
        let r = words(g(m, 1), "el");
        let new = agree(&r, "f", "na");
        if new == r { None } else { Some(new + g(m, 2)) }
    });
    c.sub(&rx(r"(?<![\w.,:/−+-])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\w/]|[.,]\d)"), &t, |m| {
        let r = words(&m[0], "el");
        let d = words(g(m, 1), "el");
        if !r.starts_with(&format!("{d} ")) || py_int(g(m, 1)) == 1 {
            return None;
        }
        let new = agree(&d, "f", "na");
        if new == d { None } else { Some(new + &r[d.len()..]) }
    })
}

fn el_abbrev_case(t: String, c: &mut Ctx) -> String {
    const FORMS: &[(&str, &str)] = &[
        ("τον", "κύριο"),
        ("στον", "κύριο"),
        ("του", "κυρίου"),
        ("στου", "κυρίου"),
        ("Αγαπητέ", "κύριε"),
        ("αγαπητέ", "κύριε"),
    ];
    let t = c.sub(
        &rx(r"(?<!\w)(σ?τον|σ?του|[Αα]γαπητέ)([ \t\x{A0}]+)κ\.(?=[ \t\x{A0}]*[Α-ΩΆ-Ώ])"),
        &t,
        |m| Some(format!("{}{}{}", g(m, 1), g(m, 2), lookup(FORMS, g(m, 1))?)),
    );
    c.sub_tpl(&rx(r"(?<!\w)(σ?της)([ \t\x{A0}]+)κας(?=[ \t\x{A0}]+[Α-ΩΆ-Ώ])"), &t, r"\1\2κυρίας")
}

fn el_century(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<!\w)(\d+(?:ο|ου))([ \t\x{A0}]+)αι\."), &t, |m| {
        Some(format!("{}{}αιώνα{}", g(m, 1), g(m, 2), end_dot(&t, m.get(0).expect("group 0").end())))
    });
    c.sub(&rx(r"(?<![\d.,])(?<!\d[ \t\x{A0}])(?<!\w)(μ\.Χ\.|π\.Χ\.)"), &t, |m| {
        let w = if g(m, 1) == "μ.Χ." { "μετά Χριστόν" } else { "προ Χριστού" };
        Some(format!("{w}{}", end_dot(&t, m.get(0).expect("group 0").end())))
    })
}

/// The period an abbreviation's own dot stood for when it also ended the sentence (end of line or a capital next).
fn end_dot(t: &str, end: usize) -> &'static str {
    if matches_at_start(r"[ \t\x{A0}]*(?:$|\n)|[ \t\x{A0}]+[Α-ΩΆ-Ώ]", &t[end..]) { "." } else { "" }
}

fn ampm_words(h: u128, pm: bool) -> &'static str {
    if pm {
        return match h {
            12 => "το μεσημέρι",
            0..=2 => "μετά το μεσημέρι",
            3..=7 => "το απόγευμα",
            _ => "το βράδυ",
        };
    }
    match h {
        12 => "τα μεσάνυχτα",
        0..=4 => "μετά τα μεσάνυχτα",
        _ => "το πρωί",
    }
}

fn el_ampm(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/])(\d{1,2})(:\d{2})?[ \t\x{A0}]?(μ\.μ\.|π\.μ\.)"), &t, |m| {
        let h = py_int(g(m, 1));
        if !(1..=12).contains(&h) {
            return None;
        }
        let part = format!("{}{}", ampm_words(h, g(m, 3) == "μ.μ."), end_dot(&t, m.get(0).expect("group 0").end()));
        if m.get(2).is_some() {
            return Some(format!("{}{} {part}", g(m, 1), g(m, 2)));
        }
        Some(format!("{} {part}", agree(&words(g(m, 1), "el"), "f", "na")))
    })
}

const HALF_COMPOUND: &[(u128, &str, &str)] = &[
    (2, "δυόμισι", "δυόμισι"),
    (3, "τρεισήμισι", "τριάμισι"),
    (4, "τεσσερισήμισι", "τεσσεράμισι"),
    (5, "πεντέμισι", "πεντέμισι"),
    (6, "εξίμισι", "εξίμισι"),
    (7, "εφτάμισι", "εφτάμισι"),
    (8, "οχτώμισι", "οχτώμισι"),
    (9, "εννιάμισι", "εννιάμισι"),
    (10, "δεκάμισι", "δεκάμισι"),
    (11, "εντεκάμισι", "εντεκάμισι"),
    (12, "δωδεκάμισι", "δωδεκάμισι"),
];

fn el_half(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(r"(?<![\w.,:/])(?:(\d+)[ \t\x{{A0}}]+)?(1/2|½)(?![\d/])([ \t\x{{A0}}]+){GREEK_WORD}(?!\w)"));
    c.sub(&re, &t, |m| {
        let (space, noun) = (g(m, 3), g(m, 4));
        let Some(n) = m.get(1).map(|x| x.as_str()) else {
            let (gg, cs) = noun_case(noun, true).unwrap_or(("n", ""));
            let w = if cs == "gen" {
                if gg == "f" { "μισής" } else { "μισού" }
            } else if gg == "f" {
                "μισή"
            } else if (gg, cs) == ("m", "nom") {
                "μισός"
            } else {
                "μισό"
            };
            return Some(format!("{w}{space}{noun}"));
        };
        let k = py_int(n);
        let f = noun_case(noun, false).unwrap_or(("n", ""));
        let gg = f.0;
        if f.1 == "gen" {
            return None;
        }
        if k == 1 {
            let f1 = noun_case(noun, true).unwrap_or(("n", ""));
            let g1 = f1.0;
            let w = if g1 == "f" {
                "μιάμιση"
            } else if f1 == ("m", "nom") {
                "ενάμισης"
            } else if g1 == "m" {
                "ενάμιση"
            } else {
                "ενάμισι"
            };
            return Some(format!("{w}{space}{noun}"));
        }
        for &(num, mf, neut) in HALF_COMPOUND {
            if num == k {
                return Some(format!("{}{space}{noun}", if matches!(gg, "m" | "f" | "mf") { mf } else { neut }));
            }
        }
        Some(format!("{} και {}{space}{noun}", words(n, "el"), if gg == "f" { "μισή" } else { "μισό" }))
    })
}

fn el_scale_one(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/])1([ \t\x{A0}]+)(εκατ\.|δισ\.)"), &t, |m| {
        Some(format!("1{}{}", g(m, 1), if g(m, 2) == "εκατ." { "εκατομμύριο" } else { "δισεκατομμύριο" }))
    })
}

// ================================================================================ money and units (Nov 16 b)

const MONEY_CUR: &str = r"€|EUR|\$|USD|£|GBP|CHF|TRY";
const MONEY_SIGN: &str = r"[€$£]";
const SP: &str = r"[ \t\xa0]";

fn el_money_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<=\d)((?:{SP}?(?:{MONEY_CUR}))?) ?~ ?(?={MONEY_SIGN}?\d)")), &t, r"\1-");
    let t = c.sub(
        &rx(&format!(
            r"(?<![\w.,])({MONEY_SIGN})(\d+(?:,\d{{1,2}})?)-(\d+(?:,\d{{1,2}})?)(?![\d,.]?\d|{SP}?(?:{MONEY_CUR})(?!\w))"
        )),
        &t,
        |m| Some(format!("{}-{} {}", g(m, 2), g(m, 3), g(m, 1))),
    );
    c.sub_tpl(&rx(r"(?<![\w.,~\d])~ ?(?=\d)"), &t, "περίπου ")
}

fn el_money_decimal(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&format!(r"(?<![\w.,])(\d{{1,3}}(?:\.\d{{3}})+|\d+),(\d)(?={SP}?(?:€|EUR|\$|USD)(?!\w))")),
        &t,
        |m| Some(format!("{},{}0", g(m, 1), g(m, 2))),
    );
    c.sub(&rx(r"(?<![\w.,])([€$])(\d{1,3}(?:\.\d{3})+|\d+),(\d)(?![\d\w]|,\d)"), &t, |m| {
        Some(format!("{}{},{}0", g(m, 1), g(m, 2), g(m, 3)))
    })
}

/// n in the feminine (μία, τρεις, είκοσι μία), from the grammar's reading of n £ (λίρα is feminine).
fn fem_number(n: u128) -> String {
    let r = words(&format!("{n} £"), "el");
    if r.ends_with(" λίρες") || r.ends_with(" λίρα") {
        r.rsplit_once(' ').map_or(r.clone(), |(a, _)| a.to_string())
    } else {
        words(&n.to_string(), "el")
    }
}

fn el_pound_money(num: &str, frac: &str) -> Option<String> {
    let mut out = words(&format!("{num} £"), "el");
    let cents = py_int(&format!("{frac:0<2}"));
    if cents > 0 {
        let p = if cents == 1 { "μία πένα".to_string() } else { format!("{} πένες", fem_number(cents)) };
        out = format!("{out} και {p}");
    }
    if super::super::search(r"[\d£]", &out) { None } else { Some(out) }
}

fn el_pound(t: String, c: &mut Ctx) -> String {
    let t =
        c.sub(&rx(&format!(r"(?<![\w.,])(\d{{1,3}}(?:\.\d{{3}})+|\d+),(\d{{1,2}}){SP}?(?:£|GBP)(?!\w)")), &t, |m| {
            el_pound_money(g(m, 1), g(m, 2))
        });
    let t = c.sub(&rx(r"(?<![\w.,])£(\d{1,3}(?:\.\d{3})+|\d+),(\d{1,2})(?![\d\w]|,\d)"), &t, |m| {
        el_pound_money(g(m, 1), g(m, 2))
    });
    c.sub(&rx(&format!(r"(?<![\w.,])(\d+)-(\d+){SP}?£(?!\w)")), &t, |m| {
        Some(format!("{} έως {}", fem_number(py_int(g(m, 1))), words(&format!("{} £", g(m, 2)), "el")))
    })
}

fn el_groups_unit(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&format!(
            r"(?<![\w.,])([1-9]\d{{0,2}}(?:\.\d{{3}})+)(,\d+)?(?![\d]|[.,]\d)({SP}?)([A-Za-zμ]+[²³]?)(?![\w/])"
        )),
        &t,
        |m| {
            let (num, frac, sep, tok) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
            let plain = format!("{}{frac}", num.replace('.', ""));
            let new = words(&format!("{plain} {tok}"), "el");
            if super::super::search(r"[\dA-Za-z]", &new) || words(&format!("{num}{frac}{sep}{tok}"), "el") == new {
                return None;
            }
            Some(format!("{plain} {tok}"))
        },
    )
}

/// A slash after an amount: the denominators the grammar leaves unread.
const PER_UNIT: &[(&str, &str)] = &[
    ("μήνα", "τον μήνα"),
    ("μήνας", "τον μήνα"),
    ("ημέρα", "την ημέρα"),
    ("μέρα", "την ημέρα"),
    ("εβδομάδα", "την εβδομάδα"),
    ("έτος", "τον χρόνο"),
    ("χρόνο", "τον χρόνο"),
    ("άτομο", "το άτομο"),
    ("νύχτα", "τη νύχτα"),
    ("βράδυ", "τη νύχτα"),
    ("λίτρο", "το λίτρο"),
    ("κιλό", "το κιλό"),
    ("τεμ.", "το τεμάχιο"),
    ("τεμάχιο", "το τεμάχιο"),
    ("τ.μ.", "το τετραγωνικό μέτρο"),
    ("τμ", "το τετραγωνικό μέτρο"),
    ("m²", "το τετραγωνικό μέτρο"),
    ("m2", "το τετραγωνικό μέτρο"),
    ("kWh", "την κιλοβατώρα"),
    ("km", "το χιλιόμετρο"),
    ("l", "το λίτρο"),
];

fn el_per_unit(t: String, c: &mut Ctx) -> String {
    let mut ks: Vec<&str> = PER_UNIT.iter().map(|kv| kv.0).collect();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    let dens = ks.iter().map(|k| super::super::re_escape(k)).collect::<Vec<_>>().join("|");
    let t =
        c.sub(&rx(&format!(r"(?<![\w.,])({MONEY_SIGN})(\d{{1,3}}(?:\.\d{{3}})+|\d+)(,\d{{1,2}})?/(?=\w)")), &t, |m| {
            Some(format!("{}{} {}/", g(m, 2), g(m, 3), g(m, 1)))
        });
    let s: &str = &t;
    c.sub(&rx(&format!(r"(?<=\d)({SP}?(?:{MONEY_CUR}))/({dens})(?![\w²³])")), &t, |m| {
        let den = g(m, 2);
        let rest = &s[m.get(0).map_or(0, |x| x.end())..];
        let dot =
            if den.ends_with('.') && matches_at_start(r"\s*$|\s+[Α-ΩΆΈΉΊΌΎΏA-Z]", rest) { "." } else { "" };
        let per = PER_UNIT.iter().find(|kv| kv.0 == den)?.1;
        Some(format!("{} {per}{dot}", g(m, 1)))
    })
}

/// Units and currencies the grammar leaves as typed: the noun after 1 and after other numbers.
const UNIT_WORDS: &[(&str, (&str, &str))] = &[
    ("ha", ("εκτάριο", "εκτάρια")),
    ("TL", ("TRY", "TRY")),
    ("BGN", ("βουλγαρικό λεβ", "βουλγαρικά λέβα")),
    ("ALL", ("αλβανικό λεκ", "αλβανικά λεκ")),
];

fn el_units(t: String, c: &mut Ctx) -> String {
    let mut ks: Vec<&str> = UNIT_WORDS.iter().map(|kv| kv.0).collect();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    let keys = ks.join("|");
    c.sub(
        &rx(&format!(r"(?<![\w.,])(\d{{1,3}}(?:\.\d{{3}})+(?:,\d+)?|\d+(?:,\d+)?)({SP}?)({keys})(?![\w/²])")),
        &t,
        |m| {
            let (one, many) = UNIT_WORDS.iter().find(|kv| kv.0 == g(m, 3))?.1;
            Some(format!("{} {}", g(m, 1), if g(m, 1) == "1" { one } else { many }))
        },
    )
}
