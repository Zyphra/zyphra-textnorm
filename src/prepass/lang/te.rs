//! 'te' rules: the port of the workbench's `langrules/te.py` (ids `te.*`).

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, re_escape, rx, search, tpl};
#[allow(unused_imports)]
use super::ta::{
    DR_CODES_MINUS, dr_alt, dr_big, dr_code, dr_cur_word, dr_half_scale, dr_money, dr_money_range, dr_pad, dr_per,
    dr_scale_case,
};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("te.money-abbrev", te_money_abbrev),
    ("te.minus", te_minus),
    ("te.big", te_big),
    ("te.money-code", te_money_code),
    ("te.per", te_per),
    ("te.money-range", te_money_range),
    ("te.money-scale", te_money_scale),
    ("te.money-scale-case", te_money_scale_case),
    ("te.half-scale", te_half_scale),
    ("te.units", te_units),
    ("te.range", te_range),
    ("te.ordinal-hyphen", te_ordinal_hyphen),
    ("te.pm-evening", te_pm_evening),
    ("te.pm-suffix", te_pm_suffix),
    ("te.suffix", te_suffix),
    ("te.unit-abbrev", te_unit_abbrev),
    ("te.half", te_half),
    ("te.one", te_one),
    ("te.scale-form", te_scale_form),
    ("te.doctor", te_doctor),
];

/// Telugu letters and vowel signs (not the Telugu digits).
const TE: &str = "\u{0C00}-\u{0C63}";
/// 1947, 1,500, 5,00,00,000 (10+ bare digits: a phone number).
const NUM: &str = r"[0-9]{1,3}(?:,[0-9]{2,3})*,[0-9]{3}|[0-9]{1,9}";
/// Postpositions and case endings written glued to a number (1947లో, 2024న, 100కి, 1990లలో).
const TAILS: &[&str] = &[
    "లోనే",
    "లోని",
    "లోనూ",
    "లోపు",
    "లోగా",
    "లో",
    "నుంచే",
    "నుంచి",
    "నుండి",
    "నాటికే",
    "నాటికి",
    "నాటి",
    "నాడు",
    "న",
    "కైనా",
    "కి",
    "కు",
    "కే",
    "లలోని",
    "లలో",
    "లకు",
    "లకి",
    "ల",
    "తోనే",
    "తో",
    "వరకూ",
    "వరకు",
    "దాకా",
    "కల్లా",
    "గా",
];
/// Scale words: the plural said alone (ఐదు కోట్లు) and the oblique before a noun (ఐదు కోట్ల మంది).
const SCALES: &[(&str, &str)] = &[("వందలు", "వందల"), ("వేలు", "వేల"), ("లక్షలు", "లక్షల"), ("కోట్లు", "కోట్ల")];
const PERIODS: &[&str] = &["ఉదయం", "మధ్యాహ్నం", "సాయంత్రం", "రాత్రి", "తెల్లవారుజామున"];
/// Telugu unit abbreviations: (written, one, plural said alone, plural before the noun it measures).
const UNITS: &[(&str, &str, &str, &str)] = &[
    ("కి.గ్రా.", "కిలోగ్రాము", "కిలోగ్రాములు", "కిలోగ్రాముల"),
    ("మి.గ్రా.", "మిల్లీగ్రాము", "మిల్లీగ్రాములు", "మిల్లీగ్రాముల"),
    ("గ్రా.", "గ్రాము", "గ్రాములు", "గ్రాముల"),
    ("మి.లీ.", "మిల్లీలీటరు", "మిల్లీలీటర్లు", "మిల్లీలీటర్ల"),
    ("లీ.", "లీటరు", "లీటర్లు", "లీటర్ల"),
    ("కి.మీ.", "కిలోమీటరు", "కిలోమీటర్లు", "కిలోమీటర్ల"),
    ("మీ.", "మీటరు", "మీటర్లు", "మీటర్ల"),
];
/// Latin unit symbols: the oblique plural before the noun they measure (the grammar's plural stays elsewhere).
const LATIN_UNITS: &[(&str, &str)] = &[
    ("kg", "కిలోగ్రాముల"),
    ("mg", "మిల్లీగ్రాముల"),
    ("g", "గ్రాముల"),
    ("ml", "మిల్లీలీటర్ల"),
    ("km", "కిలోమీటర్ల"),
    ("cm", "సెంటీమీటర్ల"),
    ("mm", "మిల్లీమీటర్ల"),
    ("t", "టన్నుల"),
    ("ha", "హెక్టార్ల"),
];
/// Units and time words “half” stands before as అర (అర కిలో, అర గంట).
const HALF_NOUNS: &[&str] = &[
    "కిలో",
    "లీటరు",
    "లీటర్",
    "గంట",
    "రోజు",
    "కప్పు",
    "గ్లాసు",
    "చెంచా",
    "స్పూన్",
    "మీటరు",
    "మీటర్",
    "అడుగు",
    "డజను",
    "ఎకరం",
    "ఎకరా",
    "గ్రాము",
    "నిమిషం",
    "శాతం",
];
/// Nouns and units a count of one stands before (prefixes: రోజు matches రోజులో, గంట matches గంటకు).
const ONE_NOUNS: &[&str] = &[
    "కిలో",
    "గ్రాము",
    "లీటరు",
    "లీటర్",
    "మీటరు",
    "మీటర్",
    "కిలోమీటర్",
    "సెంటీమీటర్",
    "అడుగు",
    "అంగుళ",
    "టన్ను",
    "ఎకరా",
    "ఎకరం",
    "డిగ్రీ",
    "శాతం",
    "రోజు",
    "గంట",
    "నిమిషం",
    "నిమిష",
    "సెకను",
    "వారం",
    "వారా",
    "నెల",
    "సంవత్సర",
    "ఏడాది",
    "శతాబ్ద",
    "మనిషి",
    "వ్యక్తి",
    "సారి",
    "కప్పు",
    "గ్లాసు",
    "చెంచా",
    "స్పూన్",
    "ముక్క",
    "ప్యాకెట్",
    "బాటిల్",
    "సీసా",
    "పేజీ",
    "పాయింట్",
    "గోల్",
    "పరుగు",
    "వికెట్",
    "పతక",
    "లక్ష",
    "కోటి",
    "రూపాయి",
    "డాలర్",
    "బిడ్డ",
    "కొడుకు",
    "కూతురు",
    "ఇల్లు",
    "కారు",
    "పుస్తక",
    "ఇంచు",
    "చోట",
    "భాగం",
    "చదరపు",
];
/// A currency code or sign and a space before the number: the grammar's money reading stays.
const NOT_MONEY: &str = r"(?<!Rs )(?<!Rs\. )(?<!INR )(?<!USD )(?<!EUR )(?<!GBP )(?<![₹$¥€£] )";
/// Words after a number that make it stand alone (the plural form: ఐదు కోట్లు దాటింది).
const VERBS: &[&str] = &[
    "దాటి",
    "దాటా",
    "దాటు",
    "ఉంది",
    "ఉన్నాయి",
    "ఉన్నారు",
    "ఉంటుంది",
    "ఉంటాయి",
    "అయింది",
    "అయ్యింది",
    "అయ్యాయి",
    "అవుతుంది",
    "పెరిగి",
    "తగ్గి",
    "చేరి",
    "చేరు",
    "మాత్రమే",
];
/// Noun endings: plurals and their oblique (పుస్తకాలు, కిలోమీటర్ల, రోజుల్లో).
const NOUN_END: &str = r"(?:లు|ల|ల్లో|లలో|లకు|లకి|లతో|లను|ల్ని)";
const SCALE_NOUNS: &[&str] = &[
    "మంది",
    "కిలో",
    "గ్రాము",
    "లీటరు",
    "లీటర్",
    "మీటరు",
    "మీటర్",
    "కిలోమీటర్",
    "ఎకరా",
    "రూపాయ",
    "డాలర్",
    "ఓట్ల",
    "ఓట్లు",
    "సంవత్సర",
    "ఏళ్ల",
    "చదరపు",
];

/// `"|".join(sorted(keys, key=len, reverse=True))`: longest first, ties in table order.
fn longest_first(keys: &[&str]) -> String {
    let mut ks: Vec<&str> = keys.to_vec();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    ks.join("|")
}

fn end0(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

/// The Telugu word right after `rest`'s leading space (`re.match(r" ([TE]+)", rest)`).
fn next_word(rest: &str) -> Option<String> {
    rx(&format!(r"^ ([{TE}]+)")).captures(rest).ok().flatten().map(|c| g(&c, 1).to_string())
}

/// A written number as the grammar reads it, or None for a leading zero (codes are not numbers).
fn plain(n: &str) -> Option<String> {
    let d = n.replace(',', "");
    let b = d.as_bytes();
    if b.len() > 1 && b[0] == b'0' && b[1] != b'.' {
        return None;
    }
    Some(words(&d, "te"))
}

/// A year 1100–1999 as Telugu says it, in hundreds: 1947 -> “పంతొమ్మిది వందల నలభై ఏడు” (the grammar's “వెయ్యి
/// తొమ్మిది వందల …” is the counting form); any other number as the grammar reads it.
fn year(n: &str) -> Option<String> {
    let d = n.replace(',', "");
    let b = d.as_bytes();
    if b.len() == 4 && !d.contains('.') && b[0] == b'1' && b[1] != b'0' {
        let rest = d[2..].trim_start_matches('0');
        let tail = if rest.is_empty() {
            " వందలు".to_string()
        } else {
            format!(" వందల {}", words(rest, "te"))
        };
        return Some(format!("{}{tail}", words(&d[..2], "te")));
    }
    plain(n)
}

/// The suffix glued to the last word; a plural scale word takes its oblique first (ఐదు వందలు + లో -> ఐదు వందలలో).
fn inflect(spoken: &str, tail: &str) -> String {
    let mut ws: Vec<String> = spoken.split_whitespace().map(str::to_string).collect();
    let n = ws.len();
    let mut last = ws[n - 1].clone();
    for &(pl, obl) in SCALES.iter().chain(&[("గంటలు", "గంటల")]) {
        if last == pl {
            last = obl.to_string();
        }
    }
    ws[n - 1] = format!("{last}{tail}");
    ws.join(" ")
}

fn te_minus(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,])([₹$€£¥]) ?-(?=[0-9])"), &t, |m| Some(format!("మైనస్ {}", g(m, 1))));
    c.sub_tpl(&rx(&format!(r"(?<![\w.,)\]{TE}-])(?<![0-9] )-(?=[0-9]|{DR_CODES_MINUS})")), &t, "మైనస్ ")
}

fn te_money_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<![{TE}\w])రూ\.? ?(?=[0-9])")), &t, "₹");
    c.sub_tpl(&rx(&format!(r"(₹ ?(?:{NUM})(?:\.[0-9]{{1,2}})?)/-")), &t, r"\1")
}

fn te_money_scale(t: String, c: &mut Ctx) -> String {
    const FORMS: &[(&str, &str, &[&str])] = &[
        ("కోటి", "కోట్ల", &["కోటి", "కోట్లు", "కోట్ల"]),
        ("లక్ష", "లక్షల", &["లక్ష", "లక్షలు", "లక్షల"]),
        ("వెయ్యి", "వేల", &["వెయ్యి", "వేలు", "వేల"]),
    ];
    let pat = format!(
        r"(?:₹|(?<![\w.])Rs\.?|(?<!\w)INR) ?((?:{NUM})(?:\.[0-9]+)?) ?(కోట్లు|కోట్ల|కోటి|లక్షలు|లక్షల|లక్ష|వెయ్యి|వేలు|వేల)(?![{TE}\w])"
    );
    c.sub(&rx(&pat), &t, |m| {
        let (n, s) = (g(m, 1), g(m, 2));
        let one = n == "1";
        for &(sing, obl, forms) in FORMS {
            if forms.contains(&s) {
                return Some(format!("{n} {} రూపాయలు", if one { sing } else { obl }));
            }
        }
        None
    })
}

fn te_range(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?<![\w.,:/+-])([0-9]{{1,9}})-([0-9]{{1,9}})(?![\w,:/]|[.-][0-9])(?= [{TE}]|[.!?,;:)]?(?:\n|$)|[.!?,;:)] )"
    );
    c.sub(&rx(&pat), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        if (a.len() > 1 && a.starts_with('0')) || (b.len() > 1 && b.starts_with('0')) || py_int(a) >= py_int(b) {
            return None;
        }
        Some(format!("{a} నుంచి {b}"))
    })
}

fn te_ordinal_hyphen(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&format!(r"(?<![\w.,:/-])([0-9]+)-(?=వ(?:ది|దే)?(?![{TE}]))")), &t, r"\1")
}

fn te_pm_evening(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?:([{TE}]+) )?(?<![\w.,:/])(0?[1-9]|1[0-2])(?::([0-5][0-9]))? ?(pm|PM|p\.m\.|P\.M\.|am|AM|a\.m\.|A\.M\.)(?!\w)"
    );
    c.sub(&rx(&pat), &t, |m| {
        let h = py_int(g(m, 2)).to_string();
        let hm = if g(m, 3).is_empty() { format!("{h} గంటలు") } else { format!("{h}:{}", g(m, 3)) };
        if PERIODS.contains(&g(m, 1)) {
            return Some(format!("{} {hm}", g(m, 1)));
        }
        if !matches!(py_int(&h), 4 | 5) {
            return None;
        }
        let word = if g(m, 4).starts_with(['p', 'P']) { "సాయంత్రం" } else { "ఉదయం" };
        let before = if g(m, 1).is_empty() { String::new() } else { format!("{} ", g(m, 1)) };
        Some(format!("{before}{word} {hm}"))
    })
}

fn te_pm_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<=[0-9]) ?(pm|PM|am|AM)(?=[{TE}])")), &t, |m| {
        Some(format!(" {}", if matches!(g(m, 1), "pm" | "PM") { "పీఎం" } else { "ఏఎం" }))
    })
}

fn te_suffix(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?<![\w.,:/–-])(?:([0-9]{{1,2}}):([0-5][0-9])|((?:{NUM})(?:\.[0-9]+)?))-?({})(?![{TE}])",
        TAILS.join("|")
    );
    let src = t.clone();
    let after = format!(r" [{TE}]");
    c.sub(&rx(&pat), &t, |m| {
        let tail = g(m, 4);
        if tail == "ల" && !matches_at_start(&after, &src[end0(m)..]) {
            return None;
        }
        if m.get(1).is_some() {
            let (h, mm) = (g(m, 1), g(m, 2));
            if py_int(h) > 23 || (mm.starts_with('0') && mm != "00") {
                return None;
            }
            let hw = words(&py_int(h).to_string(), "te");
            if mm == "00" {
                return Some(format!("{hw} {}", inflect("గంటలు", tail)));
            }
            return Some(format!("{hw} {}", inflect(&words(mm, "te"), tail)));
        }
        Some(inflect(&year(g(m, 3))?, tail))
    })
}

fn te_unit_abbrev(t: String, c: &mut Ctx) -> String {
    let abbr: Vec<String> =
        UNITS.iter().map(|u| re_escape(u.0)).chain(LATIN_UNITS.iter().map(|u| u.0.to_string())).collect();
    let pat = format!(r"(?<![\w.,:/-])((?:{NUM})(?:\.[0-9]+)?) ({})(?![{TE}\w])", abbr.join("|"));
    let src = t.clone();
    c.sub(&rx(&pat), &t, |m| {
        let (n, ab) = (g(m, 1), g(m, 2));
        let rest = &src[end0(m)..];
        let noun = next_word(rest).is_some_and(|w| !VERBS.iter().any(|v| w.starts_with(v)));
        for &(a, obl) in LATIN_UNITS {
            if a == ab {
                return if noun && n != "1" { Some(format!("{n} {obl}")) } else { None };
            }
        }
        for &(a, one, pl, obl) in UNITS {
            if a == ab {
                let end = if rest.is_empty() || rest.starts_with('\n') { "." } else { "" };
                if n == "1" {
                    return Some(format!("{n} {one}{end}"));
                }
                return Some(format!("{n} {}{end}", if noun { obl } else { pl }));
            }
        }
        None
    })
}

fn te_half(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,:/-])(?<![0-9] )(?:½|1/2) ?(?=(?:{}))", longest_first(HALF_NOUNS));
    c.sub_tpl(&rx(&pat), &t, "అర ")
}

fn te_one(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,:/₹$-])1(?= (?:{}))", longest_first(ONE_NOUNS));
    c.sub_tpl(&rx(&pat), &t, "ఒక")
}

fn te_scale_form(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,:/₹$¥€£+-]){NOT_MONEY}({NUM})(?= [{TE}]|[.!?,;:]?(?:\n|$)|[.!?,;:] )");
    let noun_end = format!("{NOUN_END}$");
    let src = t.clone();
    c.sub(&rx(&pat), &t, |m| {
        let sp = plain(g(m, 1))?;
        let mut ws: Vec<String> = sp.split_whitespace().map(str::to_string).collect();
        let nxt = next_word(&src[end0(m)..]);
        let alone = nxt.as_ref().is_none_or(|w| VERBS.iter().any(|v| w.starts_with(v)));
        let noun = !alone
            && nxt.as_ref().is_some_and(|w| SCALE_NOUNS.iter().any(|v| w.starts_with(v)) || search(&noun_end, w));
        let n = ws.len();
        for &(pl, obl) in SCALES {
            if alone && ws[n - 1] == obl {
                ws[n - 1] = pl.to_string();
            } else if noun && ws[n - 1] == pl {
                ws[n - 1] = obl.to_string();
            }
        }
        let out = ws.join(" ");
        if out == sp { None } else { Some(out) }
    })
}

fn te_doctor(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&format!(r"(?<!\w)Dr\.? (?=[{TE}])")), &t, "డాక్టర్ ")
}

// ------------------------------------------------------------------------------------------------- money (see ta.rs)

const TE_SCALES: &[&str] = &["కోట్లు", "కోట్ల", "కోటి", "లక్షలు", "లక్షల", "లక్ష", "వెయ్యి", "వేలు", "వేల"];
const TE_HALF_SCALES: &[&str] = &["వెయ్యి", "వేల", "లక్ష", "కోటి", "కోట్ల", "మిలియన్", "బిలియన్"];
/// Codes the grammar leaves unread (or misreads with decimals): (code, plural, singular, minor unit).
const TE_CODES: &[(&str, &str, &str, &str)] = &[
    ("LKR", "శ్రీలంక రూపాయలు", "శ్రీలంక రూపాయి", "సెంట్లు"),
    ("QAR", "ఖతార్ రియాల్లు", "ఖతార్ రియాల్", "దిర్హామ్లు"),
    ("KWD", "కువైట్ దినార్లు", "కువైట్ దినార్", ""),
    ("BHD", "బహ్రెయిన్ దినార్లు", "బహ్రెయిన్ దినార్", ""),
    ("JPY", "యెన్", "యెన్", ""),
    ("CNY", "యువాన్", "యువాన్", ""),
    ("KRW", "వాన్", "వాన్", ""),
    ("IDR", "ఇండోనేషియా రూపాయలు", "ఇండోనేషియా రూపాయి", ""),
];
const TE_SIGNS: &[(&str, &str)] = &[("¥", "JPY"), ("₩", "KRW")];
const TE_PER: &[(&str, &str)] = &[
    ("నెల", "నెలకు"),
    ("సంవత్సరం", "సంవత్సరానికి"),
    ("ఏడాది", "ఏడాదికి"),
    ("రోజు", "రోజుకు"),
    ("వారం", "వారానికి"),
    ("గంట", "గంటకు"),
    ("కిలో", "కిలోకు"),
    ("కేజీ", "కేజీకి"),
    ("గ్రాము", "గ్రాముకు"),
    ("లీటరు", "లీటరుకు"),
    ("లీటర్", "లీటరుకు"),
    ("మీటరు", "మీటరుకు"),
    ("మీటర్", "మీటరుకు"),
    ("వ్యక్తి", "వ్యక్తికి"),
    ("మనిషి", "మనిషికి"),
    ("రాత్రి", "రాత్రికి"),
    ("యూనిట్", "యూనిట్\u{200c}కు"),
    ("చదరపు అడుగు", "చదరపు అడుగుకు"),
    ("ఎకరం", "ఎకరానికి"),
    ("ఎకరా", "ఎకరానికి"),
    ("టన్ను", "టన్నుకు"),
    ("క్వింటాల్", "క్వింటాల్\u{200c}కు"),
    ("ముక్క", "ముక్కకు"),
    ("month", "నెలకు"),
    ("mo", "నెలకు"),
    ("year", "సంవత్సరానికి"),
    ("yr", "సంవత్సరానికి"),
    ("week", "వారానికి"),
    ("t", "టన్నుకు"),
    ("qtl", "క్వింటాల్\u{200c}కు"),
    ("unit", "యూనిట్\u{200c}కు"),
    ("sqft", "చదరపు అడుగుకు"),
    ("sq ft", "చదరపు అడుగుకు"),
    ("sq.ft", "చదరపు అడుగుకు"),
    ("sq. ft", "చదరపు అడుగుకు"),
    ("acre", "ఎకరానికి"),
    ("piece", "ఒక్కోదానికి"),
    ("pc", "ఒక్కోదానికి"),
    ("person", "ఒక్కొక్కరికి"),
    ("night", "రాత్రికి"),
    ("kg", "కిలోగ్రాముకు"),
    ("km", "కిలోమీటరుకు"),
    ("m", "మీటరుకు"),
    ("hr", "గంటకు"),
    ("h", "గంటకు"),
    ("day", "రోజుకు"),
    ("l", "లీటరుకు"),
    ("L", "లీటరుకు"),
    ("g", "గ్రాముకు"),
    ("kWh", "కిలోవాట్ గంటకు"),
    ("m²", "చదరపు మీటరుకు"),
    ("ml", "మిల్లీలీటరుకు"),
    ("mg", "మిల్లీగ్రాముకు"),
];
/// Units the grammar leaves unread: (written, one, plural said alone, plural before the noun it measures).
const TE_UNITS: &[(&str, &str, &str, &str)] = &[
    ("sq ft", "చదరపు అడుగు", "చదరపు అడుగులు", "చదరపు అడుగుల"),
    ("sq.ft", "చదరపు అడుగు", "చదరపు అడుగులు", "చదరపు అడుగుల"),
    ("sq. ft", "చదరపు అడుగు", "చదరపు అడుగులు", "చదరపు అడుగుల"),
    ("sqft", "చదరపు అడుగు", "చదరపు అడుగులు", "చదరపు అడుగుల"),
    ("acres", "ఎకరం", "ఎకరాలు", "ఎకరాల"),
    ("acre", "ఎకరం", "ఎకరాలు", "ఎకరాల"),
];
const TE_ARAB: &[&str] = &["అరబ్", "ఖరబ్"];

/// The last scale word in its oblique (ఐదు వందలు -> ఐదు వందల), as before a postposition.
fn te_obl(sp: &str) -> String {
    let mut ws: Vec<String> = sp.split(' ').map(str::to_string).collect();
    let n = ws.len();
    for &(pl, obl) in SCALES {
        if ws[n - 1] == pl {
            ws[n - 1] = obl.to_string();
        }
    }
    ws.join(" ")
}

/// N and a half: 2 -> రెండున్నర, 1 -> ఒకటిన్నర.
fn te_and_half(n: u128) -> Option<String> {
    Some(format!("{}న్నర", plain(&n.to_string())?))
}

fn te_amount(x: &str, scale: bool) -> Option<String> {
    if scale && full(r"[1-9][0-9]?\.5", x) {
        return te_and_half(py_int(&x[..x.len() - 2]));
    }
    plain(x)
}

/// A scale word before the currency word: కోటి after 1, the oblique otherwise (ఐదు కోట్ల రూపాయలు).
fn te_scale_word<'a>(scale: &'a str, n: &str) -> &'a str {
    for (sing, obl, forms) in [
        ("కోటి", "కోట్ల", ["కోటి", "కోట్లు", "కోట్ల"]),
        ("లక్ష", "లక్షల", ["లక్ష", "లక్షలు", "లక్షల"]),
        ("వెయ్యి", "వేల", ["వెయ్యి", "వేలు", "వేల"]),
    ] {
        if forms.contains(&scale) {
            return if n == "1" { sing } else { obl };
        }
    }
    scale
}

fn te_compose(a: &str, b: &str, cur: &str, after: bool, scale: &str) -> Option<String> {
    if !scale.is_empty() {
        let (aw, bw, cw) = (te_amount(a, true)?, te_amount(b, true)?, dr_cur_word(cur, after, "te")?);
        return Some(format!("{} నుండి {bw} {} {cw}", te_obl(&aw), te_scale_word(scale, b)));
    }
    let aw = if a.contains('.') { words(&dr_money(cur, &dr_pad(a), after), "te") } else { plain(a)? };
    Some(format!("{} నుండి {}", te_obl(&aw), words(&dr_money(cur, &dr_pad(b), after), "te")))
}

/// కోట్లు at the end, before punctuation or a verb; కోట్ల before the noun it counts (`rest`: the text after).
fn te_alone(rest: &str) -> &'static str {
    match next_word(rest) {
        Some(w) if !VERBS.iter().any(|v| w.starts_with(v)) => "కోట్ల",
        _ => "కోట్లు",
    }
}

fn te_big(t: String, c: &mut Ctx) -> String {
    dr_big(t, c, "te", te_alone, "కోట్ల", "కోట్ల", ("లక్షల", "లక్షల"), TE_ARAB)
}

fn te_money_code(t: String, c: &mut Ctx) -> String {
    dr_code(t, c, "te", TE_CODES, TE_SIGNS, &["రూపాయలు", "రూపాయి"], "పైసలు", plain, |s| s.to_string())
}

fn te_per(t: String, c: &mut Ctx) -> String {
    dr_per(t, c, TE_PER, TE_SCALES, &["రూపాయలు", "రూపాయి"], TE)
}

fn te_money_range(t: String, c: &mut Ctx) -> String {
    dr_money_range(t, c, TE_SCALES, TE, te_compose)
}

fn te_half_scale(t: String, c: &mut Ctx) -> String {
    dr_half_scale(t, c, TE_HALF_SCALES, te_and_half)
}

fn te_units(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = TE_UNITS.iter().map(|e| e.0).collect();
    let pat = format!(r"(?<![\w.,:/-])((?:{NUM})(?:\.[0-9]+)?) ?({})(?:\.(?= [^\W\d_]))?(?![A-Za-z])", dr_alt(&keys));
    let src = t.clone();
    c.sub(&rx(&pat), &t, |m| {
        let (n, u) = (g(m, 1), g(m, 2));
        let noun = next_word(&src[end0(m)..]).is_some_and(|w| !VERBS.iter().any(|v| w.starts_with(v)));
        let &(_, one, pl, obl) = TE_UNITS.iter().find(|e| e.0 == u)?;
        Some(format!(
            "{n} {}",
            if n == "1" {
                one
            } else if noun {
                obl
            } else {
                pl
            }
        ))
    })
}

/// A scale word with a case ending after a rupee amount: (as written, the bare scale word, the rupee word with the ending).
const TE_SCALE_CASE: &[(&str, &str, &str)] = &[
    ("కోట్లకు", "కోట్ల", "రూపాయలకు"),
    ("కోటికు", "కోటి", "రూపాయలకు"),
    ("లక్షలకు", "లక్షల", "రూపాయలకు"),
    ("లక్షకు", "లక్ష", "రూపాయలకు"),
    ("వేలకు", "వేల", "రూపాయలకు"),
    ("కోట్లకి", "కోట్ల", "రూపాయలకి"),
    ("కోటికి", "కోటి", "రూపాయలకి"),
    ("లక్షలకి", "లక్షల", "రూపాయలకి"),
    ("లక్షకి", "లక్ష", "రూపాయలకి"),
    ("వేలకి", "వేల", "రూపాయలకి"),
    ("కోట్లతో", "కోట్ల", "రూపాయలతో"),
    ("కోటితో", "కోటి", "రూపాయలతో"),
    ("లక్షలతో", "లక్షల", "రూపాయలతో"),
    ("లక్షతో", "లక్ష", "రూపాయలతో"),
    ("వేలతో", "వేల", "రూపాయలతో"),
    ("కోట్లలో", "కోట్ల", "రూపాయలలో"),
    ("కోటిలో", "కోటి", "రూపాయలలో"),
    ("లక్షలలో", "లక్షల", "రూపాయలలో"),
    ("లక్షలో", "లక్ష", "రూపాయలలో"),
    ("వేలలో", "వేల", "రూపాయలలో"),
    ("కోట్లనుంచి", "కోట్ల", "రూపాయలనుంచి"),
    ("కోటినుంచి", "కోటి", "రూపాయలనుంచి"),
    ("లక్షలనుంచి", "లక్షల", "రూపాయలనుంచి"),
    ("లక్షనుంచి", "లక్ష", "రూపాయలనుంచి"),
    ("వేలనుంచి", "వేల", "రూపాయలనుంచి"),
    ("కోట్లనుండి", "కోట్ల", "రూపాయలనుండి"),
    ("కోటినుండి", "కోటి", "రూపాయలనుండి"),
    ("లక్షలనుండి", "లక్షల", "రూపాయలనుండి"),
    ("లక్షనుండి", "లక్ష", "రూపాయలనుండి"),
    ("వేలనుండి", "వేల", "రూపాయలనుండి"),
    ("కోట్లవరకు", "కోట్ల", "రూపాయలవరకు"),
    ("కోటివరకు", "కోటి", "రూపాయలవరకు"),
    ("లక్షలవరకు", "లక్షల", "రూపాయలవరకు"),
    ("లక్షవరకు", "లక్ష", "రూపాయలవరకు"),
    ("వేలవరకు", "వేల", "రూపాయలవరకు"),
    ("కోట్లదాకా", "కోట్ల", "రూపాయలదాకా"),
    ("కోటిదాకా", "కోటి", "రూపాయలదాకా"),
    ("లక్షలదాకా", "లక్షల", "రూపాయలదాకా"),
    ("లక్షదాకా", "లక్ష", "రూపాయలదాకా"),
    ("వేలదాకా", "వేల", "రూపాయలదాకా"),
];

fn te_money_scale_case(t: String, c: &mut Ctx) -> String {
    dr_scale_case(t, c, TE_SCALE_CASE, TE)
}
