//! 'tl' rules: the port of the workbench's `langrules/tl.py` (ids `tl.*`).
//!
//! The Tagalog grammar reads a number the same way wherever it stands: without the linker before a noun (lima bata
//! for limang bata), "ng" after a number as nanograms, dates with a cardinal day, clock times as "ika-…" ordinals and
//! the decimal point as "tuldok". These rules write the spoken words for those spans (starting from the grammar's own
//! reading) or rewrite them into a form the grammar reads correctly.

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, py_rstrip, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("tl.date-day", tl_date_day),
    ("tl.time", tl_time),
    ("tl.ng", tl_ng),
    ("tl.unit-k", tl_unit_k),
    ("tl.peso", tl_peso),
    ("tl.english-number", tl_english_number),
    ("tl.linker", tl_linker),
    ("tl.decimal", tl_decimal),
    ("tl.abbrev", tl_abbrev),
    ("tl.decade", tl_decade),
];

// ------------------------------------------------------------------------------------------------- helpers

/// `re.search(pat, s)` with its groups.
fn cap<'t>(pat: &str, s: &'t str) -> Option<Captures<'t, str>> {
    let r = rx(pat);
    if !r.may_match(s) {
        return None;
    }
    r.captures(s).ok().flatten()
}

/// The grammar's linker (src/lang/tl/graph_utils.rs link_in_place) on the last word: lima -> limang,
/// isang daan -> isang daang, apat -> apat na; None when the word does not end in an ASCII letter.
fn link(s: &str) -> Option<String> {
    match s.chars().next_back()? {
        'a' | 'e' | 'i' | 'o' | 'u' | 'A' | 'E' | 'I' | 'O' | 'U' => Some(format!("{s}ng")),
        'n' | 'N' => {
            let mut out = s.to_string();
            out.pop();
            out.push_str("ng");
            Some(out)
        }
        'b'..='m' | 'p'..='z' | 'B'..='M' | 'P'..='Z' => Some(format!("{s} na")),
        _ => None,
    }
}

/// The grammar's decimal word 'tuldok' (a punctuation dot) said as 'punto'.
fn punto(s: &str) -> String {
    s.replace(" tuldok ", " punto ")
}

/// True when nothing but a sentence break comes before the end of `head`.
fn sentence_initial(head: &str) -> bool {
    match py_rstrip(head).chars().next_back() {
        None => true,
        Some(ch) => ".!?:;…\"“”(«»–—-*•".contains(ch),
    }
}

const MONTHS: [&str; 12] = [
    "Enero",
    "Pebrero",
    "Marso",
    "Abril",
    "Mayo",
    "Hunyo",
    "Hulyo",
    "Agosto",
    "Setyembre",
    "Oktubre",
    "Nobyembre",
    "Disyembre",
];
const MONTH_ABBR: &[(&str, &str)] = &[
    ("Ene", "Enero"),
    ("Peb", "Pebrero"),
    ("Mar", "Marso"),
    ("Abr", "Abril"),
    ("Hun", "Hunyo"),
    ("Hul", "Hulyo"),
    ("Ago", "Agosto"),
    ("Set", "Setyembre"),
    ("Okt", "Oktubre"),
    ("Nob", "Nobyembre"),
    ("Dis", "Disyembre"),
    ("Des", "Disyembre"),
];
const MONTH_RX: &str = r"(Enero|Pebrero|Marso|Abril|Mayo|Hunyo|Hulyo|Agosto|Setyembre|Oktubre|Nobyembre|Disyembre|(?:Ene|Peb|Mar|Abr|Hun|Hul|Ago|Set|Okt|Nob|Dis|Des)\.)";

fn month_name(s: &str) -> &str {
    for &(a, full) in MONTH_ABBR {
        if s.strip_suffix('.') == Some(a) {
            return full;
        }
    }
    s
}

// ------------------------------------------------------------------------------------------------- dates (S08)

fn tl_date_day(t: String, c: &mut Ctx) -> String {
    let t =
        c.sub(&rx(&format!(r"(?<![\w.]){MONTH_RX} (\d{{1,2}})(?![\d:/.\-]\d|\d)((?:,? \d{{4}})?)(?!\d)")), &t, |m| {
            let d = py_int(g(m, 2));
            if !(1..=31).contains(&d) {
                return None;
            }
            Some(format!("ika-{d} ng {}{}", month_name(g(m, 1)), g(m, 3)))
        });
    let t = c.sub(&rx(&format!(r"(?<![\w.,/:\-])(\d{{1,2}}) (?:ng )?{MONTH_RX}(?!\w)")), &t, |m| {
        let d = py_int(g(m, 1));
        if !(1..=31).contains(&d) {
            return None;
        }
        Some(format!("ika-{d} ng {}", month_name(g(m, 2))))
    });
    c.sub(&rx(r"(?<![\w.,/:\-])(\d{1,2}|\d{4})([/.\-])(\d{1,2})\2(\d{1,4})(?![\w/]|[.,\-]\d)"), &t, |m| {
        let (a, sep, b, y) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let (mon, day, y) = if a.chars().count() == 4 {
            if sep != "-" || y.chars().count() > 2 {
                return None;
            }
            (py_int(b), py_int(y), a) // YYYY-MM-DD: month, day, year
        } else {
            if y.chars().count() != 4 {
                return None;
            }
            let (ia, ib) = (py_int(a), py_int(b));
            if (1..=12).contains(&ia) && (1..=31).contains(&ib) {
                (ia, ib, y)
            } else if (1..=31).contains(&ia) && (1..=12).contains(&ib) {
                (ib, ia, y)
            } else {
                return None;
            }
        };
        if !((1..=12).contains(&mon) && (1..=31).contains(&day) && matches!(y.chars().next(), Some('1' | '2'))) {
            return None;
        }
        Some(format!("ika-{day} ng {} {y}", MONTHS[mon as usize - 1]))
    })
}

// ------------------------------------------------------------------------------------------------- clock times (S09)

const ES_HOURS: [&str; 13] =
    ["", "una", "dos", "tres", "kuwatro", "singko", "sais", "siyete", "otso", "nuwebe", "diyes", "onse", "dose"];
const ES_UNITS: [&str; 10] = ["", "uno", "dos", "tres", "kuwatro", "singko", "sais", "siyete", "otso", "nuwebe"];
const ES_TEENS: [&str; 10] =
    ["diyes", "onse", "dose", "trese", "katorse", "kinse", "disisais", "disisiyete", "disiotso", "disinuwebe"];
const ES_TENS: [&str; 6] = ["", "", "beynte", "treynta", "kuwarenta", "singkuwenta"];
const PERIOD_WORDS: &str = r"(?:umaga|tanghali|hapon|gabi|madaling-araw|hatinggabi)";
const TIME: &str =
    r"(?:([Aa]las|[Aa]la)[- ]?)?(\d{1,2})(?::(\d{2}))?(?: ?((?:[AaPp]\.[Mm]\.|[AaPp][Mm]|n\.[uhgt]\.)))?";
const TIME_ZONES: &str = "WITA|PHT|UTC|GMT|WIB|WIT|EST|EDT|CST|CDT|MST|MDT|PST|PDT|JST|KST";
const TIME_CUES: &[&str] = &[
    "sa",
    "mula",
    "hanggang",
    "bandang",
    "mga",
    "simula",
    "pagsapit",
    "ng",
    "nang",
    "alas",
    "oras",
    "hanggat",
    "bago",
    "pagkatapos",
    "pasado",
    "eksaktong",
];

fn es_minutes(mm: u128) -> String {
    match mm {
        15 => "y kinse".into(),
        30 => "y medya".into(),
        0..=9 => ES_UNITS[mm as usize].into(),
        10..=19 => ES_TEENS[mm as usize - 10].into(),
        _ => {
            let (tens, unit) = ((mm / 10) as usize, (mm % 10) as usize);
            if unit == 0 {
                ES_TENS[tens].into()
            } else if tens == 2 {
                format!("beynte {}", ES_UNITS[unit])
            } else {
                format!("{}'y {}", ES_TENS[tens], ES_UNITS[unit])
            }
        }
    }
}

fn am_pm(h12: u128, pm: bool) -> &'static str {
    if pm {
        if h12 == 12 {
            "ng tanghali"
        } else if h12 <= 5 {
            "ng hapon"
        } else {
            "ng gabi"
        }
    } else if h12 == 12 {
        "ng hatinggabi"
    } else if h12 <= 4 {
        "ng madaling-araw"
    } else {
        "ng umaga"
    }
}

/// The Spanish clock reading of one time (alas-dos y medya ng hapon), or None when the span is not a time.
fn say_time(t: &str, start: usize, end: usize, alas: &str, hh: &str, mm: &str, suf: &str) -> Option<String> {
    let h = py_int(hh);
    let minutes = if mm.is_empty() { 0 } else { py_int(mm) };
    let period_after = matches_at_start(&format!(r" ng {PERIOD_WORDS}(?!\w)"), &t[end..]);
    if (!mm.is_empty() && minutes > 59) || (!alas.is_empty() && alas.to_lowercase() == "ala" && h != 1) {
        return None;
    }
    let mut period = String::new();
    let h12;
    if !suf.is_empty() {
        if !(1..=12).contains(&h) {
            return None;
        }
        let s = suf.to_lowercase().replace('.', "");
        period = match s.as_str() {
            "am" | "pm" => am_pm(h, s == "pm").to_string(),
            "nu" => "ng umaga".into(),
            "nh" => "ng hapon".into(),
            "ng" => "ng gabi".into(),
            _ => "ng tanghali".into(),
        };
        h12 = h;
    } else if !alas.is_empty() {
        if !(1..=12).contains(&h) {
            return None;
        }
        h12 = h;
    } else if !mm.is_empty() {
        if h > 23 {
            return None;
        }
        if let Some(prev) = cap(r"(\S+)\s+$", &t[..start]) {
            let p = g(&prev, 1);
            if matches_at_start(r"[A-ZÑ]", p) && !TIME_CUES.contains(&p.to_lowercase().as_str()) {
                return None; // Juan 3:16, a label or a name before the number
            }
        }
        if h == 0 {
            h12 = 12;
            period = "ng hatinggabi".into();
        } else if h <= 12 {
            h12 = h;
        } else {
            h12 = h - 12;
            period = am_pm(h - 12, true).into();
        }
    } else if period_after {
        if !(1..=12).contains(&h) {
            return None;
        }
        h12 = h;
    } else {
        return None;
    }
    if period_after {
        period.clear();
    }
    let mut out = if h12 == 1 { "ala-una".to_string() } else { format!("alas-{}", ES_HOURS[h12 as usize]) };
    if minutes != 0 {
        out.push(' ');
        out.push_str(&es_minutes(minutes));
    }
    if alas.starts_with('A') {
        out.replace_range(..1, "A");
    }
    if !period.is_empty() {
        out.push(' ');
        out.push_str(&period);
    }
    Some(out)
}

fn tl_time(t: String, c: &mut Ctx) -> String {
    let lb = r"(?<![\w.,:/\-])";
    let la = r"(?![\w:]|[.,]\d)";
    let t = c.sub(&rx(&format!("{lb}{TIME}( ?[-–] ?){TIME}{la}")), &t, |m| {
        let w = m.get(0).expect("group 0");
        let sep = m.get(5).expect("separator");
        let a = say_time(&t, w.start(), sep.start(), g(m, 1), g(m, 2), g(m, 3), g(m, 4))?;
        let b = say_time(&t, sep.end(), w.end(), g(m, 6), g(m, 7), g(m, 8), g(m, 9))?;
        Some(format!("{a} hanggang {b}"))
    });
    c.sub(&rx(&format!(r"{lb}{TIME}{la}(?: ({TIME_ZONES})(?!\w))?")), &t, |m| {
        let w = m.get(0).expect("group 0");
        let end = m.get(5).map_or(w.end(), |z| z.start());
        let said = say_time(&t, w.start(), end, g(m, 1), g(m, 2), g(m, 3), g(m, 4))?;
        let zone = g(m, 5);
        if zone.is_empty() {
            return Some(said);
        }
        // the grammar spells a zone after a time (P H T); kept from the whitelist, which reads G as Ginoo
        let spelled: Vec<String> = zone.chars().map(String::from).collect();
        Some(format!("{said} \u{e000}{}\u{e001}", spelled.join(" ")))
    })
}

// ------------------------------------------------------------------------------------------------- ng (S21)

fn tl_ng(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\w.,/:\-₱$€£¥])(\d+(?:,\d{3})*(?:[./]\d+)?) ng(?= [^\W\d_])"), &t, "\\1 \u{e000}ng\u{e001}")
}

// ------------------------------------------------------------------------------------------------- k-units (S19)

const K_UNITS: &[(&str, &str)] = &[
    ("km/h", "kilometro kada oras"),
    ("kph", "kilometro kada oras"),
    ("km²", "parisukat na kilometro"),
    ("km2", "parisukat na kilometro"),
    ("km³", "kubikong kilometro"),
    ("km3", "kubikong kilometro"),
    ("kbps", "kilobit bawat segundo"),
    ("kcal", "kilocalorie"),
    ("kWh", "kilowatt-oras"),
    ("kHz", "kilohertz"),
    ("kPa", "kilopascal"),
    ("km", "kilometro"),
    ("kg", "kilo"),
    ("kW", "kilowatt"),
    ("kV", "kilovolt"),
    ("kΩ", "kiloohm"),
];
const K_RX: &str = "km/h|kbps|kcal|kph|km²|km2|km³|km3|kWh|kHz|kPa|km|kg|kW|kV|kΩ";

fn tl_unit_k(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.,])(\d+(?:,\d{{3}})*(?:\.\d+)?) ?({K_RX})(?![\w²³/])")), &t, |m| {
        let word = K_UNITS.iter().find(|(k, _)| *k == g(m, 2)).map(|(_, v)| *v)?;
        Some(format!("{} {word}", g(m, 1)))
    })
}

// ------------------------------------------------------------------------------------------------- pesos (S11)

fn tl_peso(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<![\w.])(?:Php|PhP|php)(?= ?\d)"), &t, "PHP");
    let t = c.sub_tpl(&rx(r"(?<=\d) (?:Php|PhP|php)(?!\w)"), &t, " PHP");
    c.sub_tpl(&rx(r"(?<![\w.,])P((?:\d{1,3}(?:,\d{3})+|\d{2,})(?:\.\d{1,2})?)(?![\w,]|\.\d)"), &t, "₱\\1")
}

// ------------------------------------------------------------------------------------------------- English (S24)

const EN_NOUN_RX: &str = "subscribers|followers|comments|episodes|minutes|seconds|persons|players|friends|members|tickets|minute|months|people|person|pieces|shares|points|rounds|hours|weeks|month|years|times|piece|items|likes|views|votes|goals|games|steps|pages|songs|days|hour|week|year|item|kids|day|pcs";

fn ordinal_suffix(n: u128) -> &'static str {
    if (10..=20).contains(&(n % 100)) {
        return "th";
    }
    match n % 10 {
        1 => "st",
        2 => "nd",
        3 => "rd",
        _ => "th",
    }
}

fn tl_english_number(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,])(\d+)(st|nd|rd|th|ST|ND|RD|TH)(?!\w)"), &t, |m| {
        let suffix = ordinal_suffix(py_int(g(m, 1)));
        if g(m, 2).to_lowercase() != suffix {
            return None;
        }
        Some(words(&format!("{}{suffix}", g(m, 1)), "en"))
    });
    let t =
        c.sub(&rx(&format!(r"(?<![\w.,/:\-₱$€£¥])(\d+(?:,\d{{3}})*(?:\.\d+)?) ({EN_NOUN_RX})(?!\w)")), &t, |m| {
            Some(format!("{} {}", words(g(m, 1), "en"), g(m, 2)))
        });
    c.sub(&rx(r"(?<!\w)((?:[a-z]+|[A-Z][a-z]+)[A-Z][a-z]{2,}[A-Za-z]*) (\d{1,4})(?![\w,:/]|[.,]\d)"), &t, |m| {
        Some(format!("{} {}", g(m, 1), words(g(m, 2), "en")))
    })
}

// ------------------------------------------------------------------------------------------------- linker (S03, S35)

const TL_STOP: &[&str] = &[
    "ang",
    "ng",
    "nang",
    "sa",
    "si",
    "sina",
    "ni",
    "nina",
    "kay",
    "kina",
    "ay",
    "at",
    "o",
    "na",
    "pa",
    "pang",
    "ba",
    "man",
    "din",
    "rin",
    "daw",
    "raw",
    "po",
    "ho",
    "pong",
    "naman",
    "nga",
    "kasi",
    "lang",
    "lamang",
    "muna",
    "pala",
    "yata",
    "sana",
    "talaga",
    "kaya",
    "dahil",
    "para",
    "pero",
    "ngunit",
    "subalit",
    "kung",
    "kapag",
    "pag",
    "hanggang",
    "mula",
    "tungkol",
    "laban",
    "bawat",
    "kada",
    "mga",
    "ito",
    "iyan",
    "iyon",
    "yan",
    "yun",
    "nito",
    "niyan",
    "niyon",
    "noon",
    "dito",
    "diyan",
    "doon",
    "ko",
    "mo",
    "niya",
    "nya",
    "namin",
    "natin",
    "ninyo",
    "nila",
    "ako",
    "ikaw",
    "ka",
    "siya",
    "sya",
    "kami",
    "tayo",
    "kayo",
    "sila",
    "akin",
    "atin",
    "amin",
    "inyo",
    "kanila",
    "kanya",
    "kaniya",
    "ngayon",
    "kahapon",
    "bukas",
    "habang",
    "bago",
    "pagkatapos",
    "upang",
    "samantala",
    "saka",
    "tapos",
    "pati",
    "maging",
    "kahit",
    "kundi",
    "pataas",
    "pababa",
    "lahat",
    "lalo",
    "agad",
    "kaagad",
    "ano",
    "sino",
    "saan",
    "kailan",
    "bakit",
    "paano",
    "ilan",
    "magkano",
    "alin",
    "hindi",
    "di",
    "wala",
    "may",
    "mayroon",
    "meron",
    "oo",
    "opo",
    "huwag",
    "ayon",
    "gaya",
    "tulad",
    "katulad",
    "parang",
    "mas",
    "pinaka",
    "higit",
    "mahigit",
    "halos",
    "lng",
    "bawas",
    "dagdag",
    "beses",
    "hinati",
    "katumbas",
];
const YEAR_CUES: &[&str] = &[
    "noong",
    "nung",
    "sapul",
    "taong",
    "taon",
    "mula",
    "simula",
    "hanggang",
    "bago",
    "pagkatapos",
    "sa",
    "enero",
    "pebrero",
    "marso",
    "abril",
    "mayo",
    "hunyo",
    "hulyo",
    "agosto",
    "setyembre",
    "oktubre",
    "nobyembre",
    "disyembre",
];
const LABELS: &[&str] = &[
    "kabanata", "kab.", "pahina", "pah.", "blg.", "bilang", "numero", "no.", "seksiyon", "seksyon", "artikulo",
    "bahagi", "yugto", "taludtod", "kuwarto", "silid", "room", "grade", "antas", "linya", "hanay", "level", "episode",
    "season", "part", "chapter", "page", "bersyon", "version", "modelo",
];
const LINK_NUM: &str = r"(?:[Ii]ka-?\d+|\d+ \d+/\d+|\d+/\d+|\d+(?:,\d{3})*(?:\.\d+)?(?:-\d+(?:,\d{3})*)?(?: (?:libo|milyon|bilyon|trilyon))?)";

/// A label (Kabanata 5), a name (Apollo 11) or a year cue (noong 1990) before the number: not a count.
fn link_blocked(t: &str, start: usize, num: &str) -> bool {
    let head = &t[..start];
    let Some(m) = cap(r"(\S+)\s+$", head) else { return false };
    let p = m.get(1).expect("group 1");
    let prev = p.as_str();
    let low = prev.to_lowercase();
    if LABELS.contains(&low.as_str()) {
        return true;
    }
    if full(r"\d{4}", num) && (1000..=2099).contains(&py_int(num)) && YEAR_CUES.contains(&low.as_str()) {
        return true;
    }
    matches_at_start(r"[A-ZÑ][^\W\d_]*$", prev) && !sentence_initial(&head[..p.start()])
}

fn tl_linker(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,/:+\-₱$€£¥#@%])({LINK_NUM}) ([a-zñ]{{2,}}(?:-[a-zñ]+)*)(?!\w)");
    c.sub(&rx(&pat), &t, |m| {
        let (num, word) = (g(m, 1), g(m, 2));
        if TL_STOP.contains(&word) || link_blocked(&t, m.get(0).expect("group 0").start(), num) {
            return None;
        }
        let plain = words(num, "tl");
        let linked = link(&plain)?;
        let mut said = punto(&plain);
        if full(r"\d+ \d+/\d+", num)
            && let Ok(Some(at)) = rx(r"(?<=[aeiou]) at ").find(&said)
        {
            said = format!("{}'t {}", &said[..at.start()], &said[at.end()..]);
        }
        let out = link(&said)?;
        let joined = words(&format!("{num} {word}"), "tl");
        if joined != format!("{plain} {word}") && !(joined == format!("{linked} {word}") && out != linked) {
            return None;
        }
        Some(format!("{out} {word}"))
    })
}

// ------------------------------------------------------------------------------------------------- decimals (S35)

fn tl_decimal(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?<![\w.,/:\-₱$€£¥¢₹])(?:[₱$€£¥]|PHP ?|-[₱$€£¥]?)?\d+(?:,\d{3})*\.\d+",
        r"(?: ?(?:%|‰|°[CF]?|℃|℉|[₱$€£¥¢₹]|[A-Za-zµμΩ]+(?:[²³]|/[A-Za-z]+)?))?(?![\w/°%‰℃℉₱$€£¥¢₹]|[.,]\w| [°%‰℃℉₱$€£¥¢₹])"
    );
    c.sub(&rx(pat), &t, |m| {
        let said = words(&m[0], "tl");
        if !said.contains(" tuldok ") {
            return None;
        }
        Some(punto(&said))
    })
}

// ------------------------------------------------------------------------------------------------- abbreviations (S22)

const TL_ABBREV: &[(&str, &str)] = &[
    ("Brgy.", "Barangay"),
    ("Brgy", "Barangay"),
    ("brgy.", "barangay"),
    ("BRGY.", "Barangay"),
    ("Sto.", "Santo"),
    ("Sta.", "Santa"),
    ("Gen.", "Heneral"),
    ("Kap.", "Kapitan"),
];
const TL_ABBREV_RX: &str = r"Brgy\.|brgy\.|BRGY\.|Brgy|Sto\.|Sta\.|Gen\.|Kap\.";

fn tl_abbrev(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.])({TL_ABBREV_RX})(?=\s)")), &t, |m| {
        let a = g(m, 1);
        if a.starts_with(['S', 'G', 'K']) && !matches_at_start(r" [A-ZÑ]", &t[m.get(0).expect("group 0").end()..]) {
            return None;
        }
        TL_ABBREV.iter().find(|(k, _)| *k == a).map(|(_, v)| v.to_string())
    })
}

// ------------------------------------------------------------------------------------------------- decades (S10)

const ES_DECADES: [&str; 10] =
    ["", "", "beynte", "treynta", "kuwarenta", "singkuwenta", "sisenta", "sitenta", "otsenta", "nobenta"];

fn tl_decade(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"\b([Dd]ekada) ['’]?([2-9])0(?![\w'’])"), &t, |m| {
        Some(format!("{} {}", g(m, 1), ES_DECADES[py_int(g(m, 2)) as usize]))
    })
}
