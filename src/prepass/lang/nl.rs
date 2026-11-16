//! 'nl' rules: the port of the workbench's `langrules/nl.py` (ids `nl.*`).

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

use super::super::{Ctx, g, matches_at_start, py_int, py_int_str, py_rstrip, rx};
use super::{LangRule, words};

pub(super) const RULES: &[LangRule] = &[
    ("nl.half", nl_half),
    ("nl.scale", nl_scale),
    ("nl.dash-price", nl_dash_price),
    ("nl.units", nl_units),
    ("nl.time", nl_time),
    ("nl.een", nl_een),
];

const MONTHS: [&str; 12] = [
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
];

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.start())
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

// ---------------------------------------------------------------------------------------------- halves (S01, S16)

/// het-words that often follow a half (een half uur); every other noun is a de-word (een halve liter); a diminutive
/// (-je) is a het-word too.
static NL_HET: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    "uur jaar pond ons dozijn procent stuk blik pak brood ei deel miljoen miljard glas bord etmaal kwartier \
     kilootje litertje bakje potje pakje zakje flesje glaasje kopje lepeltje theelepeltje eetlepeltje blokje stukje \
     gram woord jaartje leven land huis dorp boek pakket"
        .split_whitespace()
        .collect()
});
const NL_UNIT: [(&str, &str); 13] = [
    ("l", "liter"),
    ("dl", "deciliter"),
    ("cl", "centiliter"),
    ("ml", "milliliter"),
    ("kg", "kilo"),
    ("g", "gram"),
    ("m", "meter"),
    ("km", "kilometer"),
    ("cm", "centimeter"),
    ("mm", "millimeter"),
    ("u", "uur"),
    ("tl", "theelepel"),
    ("el", "eetlepel"),
];

fn nl_half(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w/.,])(?:(\d+) ?)?(?:½|1/2) ([a-zäëïöüé]+)(?![\w/²³])"), &t, |m| {
        let whole = g(m, 1);
        let noun = g(m, 2);
        let noun = NL_UNIT.iter().find(|u| u.0 == noun).map_or(noun, |u| u.1);
        let het = NL_HET.contains(noun) || noun.ends_with("je");
        if noun.chars().count() < 3 && !het {
            return None;
        }
        let out = if whole.is_empty() {
            (if het { "een half" } else { "een halve" }).to_string()
        } else if py_int(whole) == 1 {
            (if het { "anderhalf" } else { "anderhalve" }).to_string()
        } else {
            format!("{}{}", words(&py_int_str(whole), "nl"), if het { " en een half" } else { " en een halve" })
        };
        Some(format!("{out} {noun}"))
    })
}

// ----------------------------------------------------------------------------------------------- scale words (S13)

fn nl_scale_word(w: &str) -> &'static str {
    match w {
        "mln" | "miljoen" => "miljoen",
        "mld" | "mrd" | "miljard" => "miljard",
        _ => "biljoen",
    }
}

fn nl_sign(s: &str) -> &'static str {
    match s {
        "€" => "euro",
        "$" => "dollar",
        "£" => "pond",
        _ => "yen",
    }
}

fn nl_scale(t: String, c: &mut Ctx) -> String {
    let p = concat!(
        r"(?<!\w)(?:([€$£¥]) ?)?(?<![\w.,])(\d+(?:,\d+)?) ?(mln|mld|mrd|bln|miljoen|miljard|biljoen)",
        r"(?:(\.)|(?![\w-]))(?: ?([€$£¥]))?"
    );
    c.sub(&rx(p), &t, |m| {
        let (pre, num, word, post) = (g(m, 1), g(m, 2), g(m, 3), g(m, 5));
        if ["miljoen", "miljard", "biljoen"].contains(&word) && pre.is_empty() && post.is_empty() {
            return None;
        }
        let cur = if !pre.is_empty() { pre } else { post };
        let sign = if cur.is_empty() { String::new() } else { format!(" {}", nl_sign(cur)) };
        Some(format!("{num} {}{sign}", nl_scale_word(word)))
    })
}

fn nl_dash_price(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(\d),(?:--?|–|—)(?![\w])"), &t, r"\1")
}

// ----------------------------------------------------------------------------------------------------- units (S19)

fn nl_units(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(\d ?)km/u(?:ur)?(?![\w/])"), &t, r"\1km/h");
    let t = c.sub(&rx(r"(\d ?)(k?m)/s(?:ec)?(?![\w/])"), &t, |m| {
        let unit = if g(m, 2) == "km" { "kilometer" } else { "meter" };
        Some(format!("{} {unit} per seconde", py_rstrip(g(m, 1))))
    });
    c.sub(&rx(r"(\d ?)(km|dm|cm|mm|m)([23])(?![\w²³/])"), &t, |m| {
        Some(format!("{}{}{}", g(m, 1), g(m, 2), if g(m, 3) == "2" { "²" } else { "³" }))
    })
}

// ----------------------------------------------------------------------------------------------------- times (S09)

const NL_TIME_STRONG: [&str; 5] = ["om", "vanaf", "omstreeks", "rond", "tegen"];
const NL_TIME_WEAK: [&str; 7] = ["tot", "tussen", "en", "van", "sinds", "na", "voor"];

fn nl_time(t: String, c: &mut Ctx) -> String {
    let p = r"(?<![\w.,:])([01]?\d|2[0-4])([.:])([0-5]\d)(?![\w.,:]?\d)(?:( ?(?:uur|u))(?!\w))?";
    c.sub(&rx(p), &t, |m| {
        let (h, sep, mm, uur) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        if sep == ":" {
            return (!uur.is_empty()).then(|| format!("{h}:{mm}"));
        }
        if uur.is_empty() {
            let rest = &t[end(m)..];
            let p = match rx(r"(\w+)\s+$").captures(&t[..start(m)]) {
                Ok(Some(pm)) => g(&pm, 1).to_lowercase(),
                _ => String::new(),
            };
            if NL_TIME_STRONG.contains(&p.as_str()) {
                if matches_at_start(r"\s?(?:[%€$£]|(?:km|m|cm|mm|kg|g|l|euro|procent|meter|kilo|graden)\b)", rest) {
                    return None;
                }
            } else if NL_TIME_WEAK.contains(&p.as_str()) {
                if !matches_at_start(r"\s*(?:$|[.,;:!?)]|(?:en|tot)\b|[–-]\s?\d)", rest) {
                    return None;
                }
            } else if !matches_at_start(r"\s?[–-]\s?\d{1,2}[.:]\d\d\s?(?:uur|u)\b", rest) {
                return None;
            }
        }
        Some(format!("{h}:{mm}"))
    })
}

// ------------------------------------------------------------------------------------------------------ één (S01)

fn nl_een(t: String, c: &mut Ctx) -> String {
    let alt = MONTHS.join("|");
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,/:-])0?1 ({alt}|uur)\b")), &t, r"één \1");
    let t = c.sub(&rx(r"(?<![\w.,/:-])0?1([/.-])(0?[1-9]|1[0-2])\1(\d{4})(?![\w]|[.,/-]\d)"), &t, |m| {
        Some(format!("één {} {}", MONTHS[(py_int(g(m, 2)) - 1) as usize], g(m, 3)))
    });
    let t = c.sub(&rx(r"(?<![\w.,/:-])(\d{4})-(0[1-9]|1[0-2])-01(?![\w]|[.,/-]\d)"), &t, |m| {
        Some(format!("één {} {}", MONTHS[(py_int(g(m, 2)) - 1) as usize], g(m, 1)))
    });
    c.sub(&rx(r"(?<![\w.,/:-])0?1:([0-5]\d)(?![\w.,:]?\d)"), &t, |m| {
        let mm = g(m, 1);
        let rest = match mm {
            "00" => String::new(),
            "01" => " één".to_string(),
            _ => format!(" {}", py_int_str(mm)),
        };
        Some(format!("één uur{rest}"))
    })
}
