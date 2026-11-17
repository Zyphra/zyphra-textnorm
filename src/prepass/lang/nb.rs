//! 'nb' rules: the port of the workbench's `langrules/nb.py` (ids `nb.*`).
//!
//! The year rule uses `da.rs`'s [`nordic_year`] with Norwegian tables.

use std::collections::HashSet;
use std::sync::LazyLock;

use super::super::{Ctx, g, matches_at_start, py_int, rx};
use super::da::{
    YearCues, abbrev_rule, kroner_code, money_decimal, money_range, nordic_year, per_unit, scale_money, set,
    unit_groups,
};
use super::{LangRule, words};

pub(super) const RULES: &[LangRule] = &[
    ("nb.money-range", nb_money_range),
    ("nb.minus", nb_minus),
    ("nb.money-code", nb_money_code),
    ("nb.money-decimal", nb_money_decimal),
    ("nb.code-first", nb_code_first),
    ("nb.scale-money", nb_scale_money),
    ("nb.per-unit", nb_per_unit),
    ("nb.scale", nb_scale),
    ("nb.units", nb_units),
    ("nb.units-more", nb_units_more),
    ("nb.abbrev", nb_abbrev),
    ("nb.date", nb_date),
    ("nb.decade", nb_decade),
    ("nb.year", nb_year),
    ("nb.unit-groups", nb_unit_groups),
];

const MONTHS: [&str; 12] = [
    "januar",
    "februar",
    "mars",
    "april",
    "mai",
    "juni",
    "juli",
    "august",
    "september",
    "oktober",
    "november",
    "desember",
];

/// 1905 -> 'nitten hundre og fem', 1900 -> 'nitten hundre', 1987 -> 'nitten åttisju' (the grammar's own date style
/// for the tens).
fn nb_year_words(y: u128) -> String {
    let (head, r) = (words(&(y / 100).to_string(), "nb"), y % 100);
    if r == 0 {
        return format!("{head} hundre");
    }
    if r < 10 {
        return format!("{head} hundre og {}", words(&r.to_string(), "nb"));
    }
    format!("{head} {}", words(&r.to_string(), "nb"))
}

/// The signs and codes the grammar reads after an amount (src/lang/nb/money.rs), longest first.
const NB_CUR: &str = r"kr\.|US\$|NOK|USD|EUR|GBP|JPY|CAD|AUD|SEK|DKK|CHF|INR|RUB|KRW|TRY|ILS|UAH|VND|BDT|PHP|THB|AMD|kr|\$|€|£|¥|₽|₩|₺|₪|₴|₫|৳|₱|฿|֏";
/// The ones it reads with cents (kroner og øre, dollar og cent, euro og cent).
const NB_CENTS: &str = r"kr\.|US\$|NOK|USD|EUR|kr|\$|€";
const NB_NUM: &str = r"(?:[1-9]\d{0,2}(?:[ \x{A0}]\d{3})+|[1-9]\d{0,2}(?:\.\d{3})+|\d+)(?:,\d{1,2})?";
const NB_GROUPED: &str = r"[1-9]\d{0,2}(?:\.\d{3})+|[1-9]\d{0,2}(?:[ \x{A0}]\d{3})+";

fn nb_money_range(t: String, c: &mut Ctx) -> String {
    money_range(t, c, NB_CUR)
}

fn nb_money_decimal(t: String, c: &mut Ctx) -> String {
    money_decimal(t, c, &format!("{NB_CENTS}|kroner|euro|dollar"), NB_CENTS, NB_NUM, "til", true)
}

const NB_CODES: &[(&str, (&str, &str))] =
    &[("SEK", ("svensk", "svenske")), ("DKK", ("dansk", "danske")), ("ISK", ("islandsk", "islandske"))];

fn nb_money_code(t: String, c: &mut Ctx) -> String {
    kroner_code(t, c, "nb", NB_CODES, "kr", r"\bkrone\b", r"\bkroner\b", NB_NUM, r"[. \x{A0}]")
}

fn nb_code_first(t: String, c: &mut Ctx) -> String {
    let p = format!(r"(?<!\w)(CHF|KRW|TRY|ILS|UAH|VND|BDT|PHP|THB|AMD) ?((?:{NB_GROUPED}|\d+))(?![\w]|[.,]\d)");
    c.sub_tpl(&rx(&p), &t, r"\2 \1")
}

fn nb_scale_money(t: String, c: &mut Ctx) -> String {
    scale_money(t, c, NB_CUR, NB_NUM, "nb", &["kr.", "kr"])
}

const NB_PER: &[(&str, &str)] = &[
    ("md.", "per måned"),
    ("md", "per måned"),
    ("mnd.", "per måned"),
    ("mnd", "per måned"),
    ("måned", "per måned"),
    ("år", "per år"),
    ("dag", "per dag"),
    ("døgn", "per døgn"),
    ("uke", "per uke"),
    ("time", "per time"),
    ("stk.", "per stykk"),
    ("stk", "per stykk"),
    ("person", "per person"),
    ("pers.", "per person"),
    ("natt", "per natt"),
    ("g", "per gram"),
    ("l", "per liter"),
    ("liter", "per liter"),
    ("km", "per kilometer"),
    ("m²", "per kvadratmeter"),
    ("m2", "per kvadratmeter"),
    ("kvm", "per kvadratmeter"),
    ("m", "per meter"),
    ("m³", "per kubikkmeter"),
];

fn nb_per_unit(t: String, c: &mut Ctx) -> String {
    per_unit(t, c, NB_CUR, NB_PER)
}

fn nb_scale(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,])(\d+(?:,\d+)?) ?(mill|mln|mrd|mnd|mio|mia)(?:\.|(?![\w-]))"), &t, |m| {
        let (num, abbr) = (g(m, 1), g(m, 2));
        let (sg, pl) = match abbr {
            "mill" | "mln" | "mio" => ("million", "millioner"),
            "mrd" | "mia" => ("milliard", "milliarder"),
            _ => ("måned", "måneder"),
        };
        Some(format!("{num} {}", if num == "1" { sg } else { pl }))
    });
    c.sub_tpl(&rx(r"\b(millioner|million|milliarder|milliard) kr\b"), &t, r"\1 kroner")
}

fn nb_units(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(\d ?)kvm\b\.?"), &t, r"\1m²");
    c.sub(&rx(r"(\d ?)(km|dm|cm|mm|m)([23])(?![\w²³/])"), &t, |m| {
        Some(format!("{}{}{}", g(m, 1), g(m, 2), if g(m, 3) == "2" { "²" } else { "³" }))
    })
}

fn nb_units_more(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,])(\d+(?:,\d+)?)( ?)(ha|spsk)(\.)?(?![\w/²³-])"), &t, |m| {
        let unit = if g(m, 3) == "ha" {
            "hektar"
        } else if g(m, 1) == "1" {
            "spiseskje"
        } else {
            "spiseskjeer"
        };
        let dot = if !g(m, 4).is_empty() && matches_at_start(r"[ \t]*(?:\n|$)", &t[m.get(0).unwrap().end()..]) {
            "."
        } else {
            ""
        };
        Some(format!("{}{}{unit}{dot}", g(m, 1), g(m, 2)))
    })
}

const NB_ABBREV: [(&str, &str); 7] = [
    ("evt.", "eventuelt"),
    ("mht.", "med hensyn til"),
    ("iflg.", "ifølge"),
    ("inkl.", "inklusive"),
    ("ekskl.", "eksklusive"),
    ("vha.", "ved hjelp av"),
    ("ifm.", "i forbindelse med"),
];

fn nb_abbrev(t: String, c: &mut Ctx) -> String {
    abbrev_rule(t, c, &NB_ABBREV, &[])
}

fn nb_date(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,/-])(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})(?![\w]|[.,/-]?\d)"), &t, |m| {
        let (d, mo, y) = (py_int(g(m, 1)), py_int(g(m, 2)), g(m, 3));
        if !((1..=31).contains(&d) && (1..=12).contains(&mo)) {
            return None;
        }
        let month = MONTHS[(mo - 1) as usize];
        if y.chars().count() == 2 {
            if g(m, 1).chars().count() != 2 || g(m, 2).chars().count() != 2 {
                return None;
            }
            return Some(format!("{d}. {month} {y}"));
        }
        if (1100..=1999).contains(&py_int(y)) && py_int(y) % 100 < 10 {
            return Some(format!("{d}. {month} {y}"));
        }
        if g(m, 1).starts_with('0') {
            return Some(format!("{d}.{}.{y}", g(m, 2)));
        }
        None
    })
}

fn nb_decade(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,])(\d)0-tall(et|ets)\b"), &t, |m| {
        Some(format!("{}tall{}", words(&format!("{}0", g(m, 1)), "nb"), g(m, 2)))
    });
    c.sub(&rx(r"(?<![\w.,])(1[1-9])00-tall(et|ets)\b"), &t, |m| {
        Some(format!("{}hundretall{}", words(g(m, 1), "nb"), g(m, 2)))
    })
}

static NB_YEAR_STRONG: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("år året anno januar februar mars april mai juni juli august september oktober november desember jan feb \
         mar apr jun jul aug sep sept okt nov des")
});
static NB_YEAR_WEAK: LazyLock<HashSet<&str>> =
    LazyLock::new(|| set("i fra til siden før etter omkring ved inntil mellom og eller innen fram"));
static NB_AMOUNT: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("koster kostet betaler betalte betalt har hadde ca cirka over under mer enn bare nesten knapt drøyt nummer nr \
         side rom plus minus veier teller på med av alle")
});
static NB_AFTER_OK: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("i og til på med for da men eller som etter før ble var er har hadde kom fikk gikk under ved fra hvor tapte \
         vant døde startet begynte sluttet åpnet stengte flyttet utkom skjedde fødtes oppsto fant kunne skulle ville \
         måtte bodde levde")
});
static NB_NOT_AFTER: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    set("år års dager dag timer time minutter sekunder uker måneder meter m km kilometer kg kilo gram g liter l kr \
         kroner euro dollar prosent personer mennesker stk ganger sider ord elever innbyggere ansatte medlemmer \
         deltakere biler hus poeng mål kalorier kcal millioner milliarder tusen hundre barn voksne studenter soldater")
});

static NB_CUES: YearCues = YearCues {
    say: nb_year_words,
    strong: &NB_YEAR_STRONG,
    weak: &NB_YEAR_WEAK,
    amount: &NB_AMOUNT,
    after_ok: &NB_AFTER_OK,
    not_after: &NB_NOT_AFTER,
    span_words: "og|til|eller",
    to_word: "til",
};

fn nb_year(t: String, c: &mut Ctx) -> String {
    nordic_year(t, c, &NB_CUES)
}

fn nb_minus(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,)\]\-−+*/=^])[-−](?=\d+(?:[.,]\d+)?\s?(?:[°%‰]|[^\W\d_]))"), &t, |_| {
        Some("minus ".to_string())
    })
}

fn nb_unit_groups(t: String, c: &mut Ctx) -> String {
    unit_groups(t, c, "nb", NB_GROUPED)
}
