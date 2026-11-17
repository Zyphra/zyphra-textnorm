//! 'sv' rules: the port of the workbench's `langrules/sv.py` (ids `sv.*`).
//!
//! The year rule uses `da.rs`'s [`nordic_year`] with Swedish tables.

use std::collections::HashSet;
use std::sync::LazyLock;

use super::super::{Ctx, g, matches_at_start, py_int, py_int_str, rx, search};
use super::da::{
    YearCues, abbrev_rule, kroner_code, money_decimal, money_range, nordic_year, per_unit, set, unit_groups,
};
use super::{LangRule, words};

pub(super) const RULES: &[LangRule] = &[
    ("sv.half", sv_half),
    ("sv.quarter", sv_quarter),
    ("sv.date-slash", sv_date_slash),
    ("sv.kronor", sv_kronor),
    ("sv.money-groups", sv_money_groups),
    ("sv.money-range", sv_money_range),
    ("sv.sek", sv_sek),
    ("sv.money-decimal", sv_money_decimal),
    ("sv.money-code", sv_money_code),
    ("sv.per-unit", sv_per_unit),
    ("sv.scale", sv_scale),
    ("sv.units", sv_units),
    ("sv.ordinal", sv_ordinal),
    ("sv.en-miljon", sv_en_miljon),
    ("sv.abbrev", sv_abbrev),
    ("sv.regnal", sv_regnal),
    ("sv.year", sv_year),
    ("sv.unit-groups", sv_unit_groups),
];

// ---------------------------------------------------------------------------------------------- halves (S01, S16)

/// Neuter nouns that often follow a half (ett halvt kilo); every other noun is common gender (en halv liter).
static SV_NEUTER: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("kilo kilogram gram hekto år dygn glas ägg äpple paket bröd ton dussin pund kvarter kryddmått lass ark \
         block kort liv land hus rum tal ord lock halvår ögonblick decennium sekel")
});
const SV_UNIT: [(&str, &str); 7] = [
    ("l", "liter"),
    ("dl", "deciliter"),
    ("cl", "centiliter"),
    ("ml", "milliliter"),
    ("tsk", "tesked"),
    ("msk", "matsked"),
    ("krm", "kryddmått"),
];

fn sv_half(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w/.,])(?:(\d+) ?)?(?:½|1/2) ([a-zåäöé]+)(?![\w/²³])"), &t, |m| {
        let whole = g(m, 1);
        let noun = g(m, 2);
        let noun = SV_UNIT.iter().find(|u| u.0 == noun).map_or(noun, |u| u.1);
        let neuter = SV_NEUTER.contains(noun);
        if noun.chars().count() < 3 && !neuter {
            return None;
        }
        let art = if neuter { "ett halvt" } else { "en halv" };
        if whole.is_empty() {
            return Some(format!("{art} {noun}"));
        }
        let head = if py_int(whole) == 1 {
            (if neuter { "ett" } else { "en" }).to_string()
        } else {
            words(&py_int_str(whole), "sv")
        };
        Some(format!("{head} och {art} {noun}"))
    })
}

fn sv_quarter(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w/.,])(\d{1,2})/4(?= av\b)"), &t, |m| {
        Some(if g(m, 1) == "1" {
            "en fjärdedel".to_string()
        } else {
            format!("{} fjärdedelar", words(g(m, 1), "sv"))
        })
    })
}

const SV_MONTHS: [&str; 12] = [
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
];

fn sv_date_slash(t: String, c: &mut Ctx) -> String {
    let p = concat!(
        r"(?<![\w.])(den|från|till|senast|före|efter|sedan|fr\.o\.m\.|t\.o\.m\.) (\d{1,2})/(\d{1,2})",
        r"(?![\w/]|[.,]\d| av\b)"
    );
    c.sub(&rx(p), &t, |m| {
        let (d, mo) = (py_int(g(m, 2)), py_int(g(m, 3)));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) {
            return None;
        }
        Some(format!("{} {d} {}", g(m, 1), SV_MONTHS[(mo - 1) as usize]))
    })
}

fn sv_kronor(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(\d) ?:[-–](?![\w-])"), &t, r"\1 kr")
}

fn sv_sek(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(\d) ?SEK(?!\w)"), &t, r"\1 kr")
}

const SV_CUR: &str = r"US\$|SEK|NOK|DKK|ISK|USD|EUR|GBP|CHF|JPY|kr|\$|€|£|¥";
const SV_NUM: &str = r"(?:[1-9]\d{0,2}(?:[ \x{A0}]\d{3})+|\d+)(?:,\d{1,2})?";

const SV_DOT_GROUPED: &str = r"[1-9]\d{0,2}(?:\.\d{3})+";

fn sv_money_groups(t: String, c: &mut Ctx) -> String {
    let p = format!(r"(?<!\w)({SV_CUR}) ?({SV_DOT_GROUPED})(?=(?:,\d\d)?(?![\w]|[.,]\d|[ \x{{A0}}]\d))");
    let t = c.sub(&rx(&p), &t, |m| Some(format!("{} {}", g(m, 1), g(m, 2).replace('.', ""))));
    let p = format!(r"(?<![\w.,])(?<!\d[ \x{{A0}}])({SV_DOT_GROUPED})(?=(?:,\d\d)? ?(?:{SV_CUR}|kronor|euro)(?!\w))");
    c.sub(&rx(&p), &t, |m| Some(g(m, 1).replace('.', "")))
}

fn sv_money_range(t: String, c: &mut Ctx) -> String {
    money_range(t, c, SV_CUR)
}

fn sv_money_decimal(t: String, c: &mut Ctx) -> String {
    money_decimal(t, c, &format!("{SV_CUR}|kronor|euro"), SV_CUR, SV_NUM, "till", false)
}

fn sv_money_code(t: String, c: &mut Ctx) -> String {
    kroner_code(t, c, "sv", &[("NOK", ("norsk", "norska"))], "kr", r"\bkrona\b", r"\bkronor\b", SV_NUM, r"[ \x{A0}]")
}

const SV_PER: &[(&str, &str)] = &[("timme", "per timme"), ("dygn", "per dygn")];

fn sv_per_unit(t: String, c: &mut Ctx) -> String {
    per_unit(t, c, SV_CUR, SV_PER)
}

fn sv_scale(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,])(\d+(?:,\d+)?) ?(mdr|md|milj|mn)(?:(\.)|(?![\w-]))"), &t, |m| {
        let (num, abbr, dot) = (g(m, 1), g(m, 2), g(m, 3));
        if (abbr == "md" || abbr == "mn") && dot.is_empty() {
            return None;
        }
        Some(format!("{num} {}", if abbr == "mdr" || abbr == "md" { "md" } else { "mn" }))
    })
}

fn sv_units(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(\d ?)kvm\b\.?"), &t, r"\1m²")
}

/// The singular scale words; the grammar's plain cardinal drops the "en" before them (1 000 000 → miljon).
const SV_SCALE_ONE: [&str; 6] = ["miljon", "miljard", "biljon", "biljard", "triljon", "triljard"];

/// 'miljon femhundratusen' -> 'en miljon femhundratusen', 'två miljarder miljon' -> 'två miljarder en miljon'.
fn sv_one_scale(w: &str) -> String {
    let toks: Vec<&str> = w.split(' ').collect();
    let mut out: Vec<&str> = Vec::with_capacity(toks.len() + 2);
    for (i, tok) in toks.iter().enumerate() {
        if SV_SCALE_ONE.contains(tok) && (i == 0 || !matches!(toks[i - 1], "en" | "ett")) {
            out.push("en");
        }
        out.push(tok);
    }
    out.join(" ")
}

const SV_ORD_SCALE: [(&str, &str); 4] = [
    (r"tusen$", "tusende"),
    (r"miljon(?:er)?$", "miljonte"),
    (r"miljard(?:er)?$", "miljardte"),
    (r"biljon(?:er)?$", "biljonte"),
];

/// 2001, 'a' -> 'tvåtusen första'; 10000, 'e' -> 'tiotusende'; 2000000, 'e' -> 'två miljonte' (the grammar's
/// spacing); None when it cannot be built.
fn sv_ordinal_words(n: u128, suf: &str) -> Option<String> {
    let r = n % 1000;
    let out = if r != 0 {
        format!("{} {}", words(&(n - r).to_string(), "sv"), words(&format!("{r}:{suf}"), "sv"))
    } else {
        let w = words(&n.to_string(), "sv");
        let (pat, rep) = SV_ORD_SCALE.iter().find(|(pat, _)| search(pat, &w))?;
        rx(pat).replace_all(&w, *rep).to_string()
    };
    if search(r"\d|(?:^|\s)[ae]$", &out) { None } else { Some(out) }
}

fn sv_ordinal(t: String, c: &mut Ctx) -> String {
    let p = r"(?<![\w.,:/+−-])(?<!\d[ \x{A0}])([1-9]\d{0,2}(?:[ \x{A0}]\d{3})+|[1-9]\d*):([ae])(?!\w)";
    c.sub(&rx(p), &t, |m| {
        let (num, suf) = (g(m, 1), g(m, 2));
        let plain: String = num.chars().filter(|&ch| !matches!(ch, ' ' | '\u{a0}')).collect();
        let w = words(&format!("{plain}:{suf}"), "sv");
        if !search(r"\d|(?:^|\s)[ae]$", &w) {
            return if plain == num { None } else { Some(format!("{plain}:{suf}")) };
        }
        sv_ordinal_words(py_int(&plain), suf)
    })
}

fn sv_en_miljon(t: String, c: &mut Ctx) -> String {
    let pat = r#"(?<![^\s(\[{"'„“”«»‘’])[-−]?(?:\d{1,3}(?:[ \x{A0}]\d{3})+|\d{1,3}(?:\.\d{3}){2,}|\d+)(?:,\d+)?(?:(?: ?[-–] ?)(?:\d{1,3}(?:[ \x{A0}]\d{3})+|\d{1,3}(?:\.\d{3}){2,}|\d+)(?:,\d+)?)?(?![\w]|[.,:]\d|[ \x{A0}]\d)"#;
    c.sub(&rx(pat), &t, |m| {
        let span = g(m, 0);
        if !search(r"\d{7}|\d{1,3}(?:[ \x{A0}]\d{3}){2}|\d{1,3}(?:\.\d{3}){2}", span) {
            return None;
        }
        let w = words(span, "sv");
        let fixed = sv_one_scale(&w);
        if fixed == w {
            return None;
        }
        let whole = m.get(0).unwrap();
        if search(r"[\d+][ \x{A0}]*$", &t[..whole.start()]) {
            return None; // a phone number or a list of numbers
        }
        let rest = &t[whole.end()..];
        match rx(r"^[ \x{A0}]+([^\W\d_]+)").captures(rest) {
            Ok(Some(nm)) => {
                if !words(&format!("{span} {}", g(&nm, 1)), "sv").starts_with(&format!("{w} ")) {
                    return None; // a unit or a currency the grammar reads with the number (en miljon kilometer)
                }
            }
            _ => {
                if !matches_at_start(r#"[ \x{A0}]*(?:$|\n|[.,;:!?)\]"»”…](?!\w))"#, rest) {
                    return None;
                }
            }
        }
        Some(fixed)
    })
}

const SV_ABBREV: [(&str, &str); 5] = [
    ("fr. o. m.", "från och med"),
    ("t. o. m.", "till och med"),
    ("ev.", "eventuellt"),
    ("resp.", "respektive"),
    ("s. a. s.", "så att säga"),
];

fn sv_abbrev(t: String, c: &mut Ctx) -> String {
    abbrev_rule(t, c, &SV_ABBREV, &["t.o.m."])
}

const SV_REGNAL_M: &str = concat!(
    "Gustav|Gustaf|Karl|Carl|Erik|Johan|Oscar|Oskar|Fredrik|Adolf|Magnus|Olof|Knut|Sverker|Birger|",
    "Kristian|Christian|Kristoffer|Albrekt|Håkan|Haakon|Valdemar|Sigismund|Henrik|Ludvig|Filip|Ferdinand|",
    "Leopold|Wilhelm|Vilhelm|Napoleon|Peter|Nikolaj|Alexander|Ivan|Frans|Josef|Pius|Benedictus|Paulus|",
    "Johannes|Leo|Gregorius|Edvard|Georg|Richard|Jakob|Olav|Harald|Frederik|Albert|Felipe|Rudolf|Otto|",
    "Konstantin|Mikael|Stefan|Sixtus|Urban|Clemens|Innocentius|Bonifatius|Julius"
);
const SV_TITLES_M: &str = "Kung|Konung|Kejsar|Kejsare|Påve|Påven|Tsar|Prins|Hertig|Kurfurste";

fn sv_regnal(t: String, c: &mut Ctx) -> String {
    let regnal = |m: &fancy_regex::Captures<'_, str>| {
        Some(format!("{}{}{}", g(m, 1), g(m, 2), if g(m, 3) == "I" { " den förste" } else { " den andre" }))
    };
    let p1 = format!(r"(?<![\w.])((?:{SV_TITLES_M}) )?({SV_REGNAL_M}) (II|I)(?![\w'])");
    let t = c.sub(&rx(&p1), &t, regnal);
    let p2 = format!(r"(?<![\w.])((?:{SV_TITLES_M}) )([A-ZÅÄÖ][a-zåäöé]+) (II|I)(?![\w'])");
    c.sub(&rx(&p2), &t, regnal)
}

/// 1923 -> 'nittonhundratjugotre', 1900 -> 'nittonhundra'.
fn sv_year_words(y: u128) -> String {
    let r = if !y.is_multiple_of(100) { words(&(y % 100).to_string(), "sv") } else { String::new() };
    format!("{}hundra{r}", words(&(y / 100).to_string(), "sv"))
}

static SV_YEAR_STRONG: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("år året anno januari februari mars april maj juni juli augusti september oktober november december jan feb \
         apr jun jul aug sep sept okt nov dec")
});
static SV_YEAR_WEAK: LazyLock<HashSet<&str>> =
    LazyLock::new(|| set("i från till sedan före efter omkring kring vid mellan och eller innan fram runt"));
static SV_AMOUNT: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set(
        "kostar kostade betalar betalade betalt har hade ca cirka över under mer än bara nästan knappt drygt nummer nr \
         sida rum plus minus väger räknar på med av alla",
    )
});
static SV_AFTER_OK: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("i och till på med för då men eller som efter före blev var är har hade kom fick gick under vid från där \
         förlorade vann dog startade började slutade öppnade stängde flyttade utkom hände föddes uppstod fann kunde \
         skulle ville måste bodde levde byggdes grundades")
});
static SV_NOT_AFTER: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("år års dagar dag timmar timme minuter sekunder veckor månader meter m km kilometer kg kilo gram g liter l kr \
         kronor euro dollar procent personer människor st stycken gånger sidor ord elever invånare anställda medlemmar \
         deltagare bilar hus poäng mål kalorier kcal miljoner miljarder tusen hundra barn vuxna studenter soldater")
});

static SV_CUES: YearCues = YearCues {
    say: sv_year_words,
    strong: &SV_YEAR_STRONG,
    weak: &SV_YEAR_WEAK,
    amount: &SV_AMOUNT,
    after_ok: &SV_AFTER_OK,
    not_after: &SV_NOT_AFTER,
    span_words: "och|till|eller",
    to_word: "till",
};

fn sv_year(t: String, c: &mut Ctx) -> String {
    nordic_year(t, c, &SV_CUES)
}

fn sv_unit_groups(t: String, c: &mut Ctx) -> String {
    unit_groups(t, c, "sv", SV_DOT_GROUPED)
}
