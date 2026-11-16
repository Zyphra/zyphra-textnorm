//! 'ml' rules: the port of the workbench's `langrules/ml.py` (ids `ml.*`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ml.money-abbrev", ml_money_abbrev),
    ("ml.money-scale", ml_money_scale),
    ("ml.half", ml_half),
    ("ml.range", ml_range),
    ("ml.thousands", ml_thousands),
    ("ml.pm-period", ml_pm_period),
    ("ml.pm-suffix", ml_pm_suffix),
    ("ml.suffix", ml_suffix),
    ("ml.one", ml_one),
    ("ml.doctor", ml_doctor),
];

/// Malayalam letters, signs and chillus, ZWNJ/ZWJ (not the digits).
const ML: &str = "\u{0D00}-\u{0D63}\u{0D7A}-\u{0D7F}\u{200C}\u{200D}";
/// 1947, 1,500, 1,50,000 (10+ bare digits: a phone number).
const NUM: &str = r"[0-9]{1,3}(?:,[0-9]{2,3})*,[0-9]{3}|[0-9]{1,9}";
const VIRAMA: char = '\u{0D4D}';
/// Endings written after a number (1947ൽ, 100ൽ, 3-ന്, 1990കളിൽ, 2030ഓടെ, 100ഓളം).
const TAIL_LOC: &[&str] = &["ൽപ്പരം", "ലായിരുന്നു", "ലുള്ള", "ലേക്ക്", "ലാണ്", "ലും", "ലെ", "ൽ"];
const TAIL_DAT: &[&str] = &["നാണ്", "ന്റെ", "നും", "നു", "ന്"];
const TAIL_PL: &[&str] = &["കളിലാണ്", "കളിലും", "കളിലെ", "കളിൽ", "കളുടെ", "കൾ"];
const TAIL_V: &[&str] = &["ഓടെ", "ഓളം"];
/// The dative after -i (മണിക്ക്, not മണിയിന്).
const DAT_I: &[(&str, &str)] = &[("നാണ്", "ക്കാണ്"), ("ന്റെ", "യുടെ"), ("നും", "ക്കും"), ("നു", "ക്കു"), ("ന്", "ക്ക്")];
const SIGN: &[(char, &str)] =
    &[('ഓ', "\u{0D4B}"), ('ഉ', "\u{0D41}"), ('ആ', "\u{0D3E}"), ('ഇ', "\u{0D3F}"), ('ഏ', "\u{0D47}"), ('എ', "\u{0D46}")];
/// Units, containers and time words “half” stands before as അര (അര ലിറ്റർ, അര മണിക്കൂർ).
const HALF_NOUNS: &[&str] = &[
    "ലിറ്റർ",
    "കിലോ",
    "ഗ്രാം",
    "മീറ്റർ",
    "കപ്പ്",
    "ഗ്ലാസ്",
    "സ്പൂൺ",
    "ടീസ്പൂൺ",
    "ടേബിൾസ്പൂൺ",
    "മണിക്കൂ",
    "ദിവസ",
    "മാസ",
    "വർഷ",
    "ഇഞ്ച്",
    "അടി",
    "കഷണ",
    "ഭാഗ",
    "പാക്കറ്റ്",
    "കുപ്പി",
    "ഡസൻ",
    "ലക്ഷ",
    "കോടി",
];
const PERIODS: &[&str] = &["രാവിലെ", "ഉച്ചയ്ക്ക്", "ഉച്ചകഴിഞ്ഞ്", "വൈകുന്നേരം", "വൈകിട്ട്", "രാത്രി", "പുലർച്ചെ"];
/// Nouns and units a count of one stands before (prefixes: ദിവസ matches ദിവസം, ദിവസത്തിൽ).
const ONE_NOUNS: &[&str] = &[
    "കിലോ",
    "ഗ്രാം",
    "മീറ്റർ",
    "കിലോമീറ്റർ",
    "സെന്റിമീറ്റർ",
    "അടി",
    "ഇഞ്ച്",
    "ടൺ",
    "ഏക്കർ",
    "ഡിഗ്രി",
    "ശതമാന",
    "ദിവസ",
    "മണിക്കൂ",
    "മണി",
    "മിനിറ്റ്",
    "സെക്കൻഡ്",
    "ആഴ്ച",
    "മാസ",
    "വർഷ",
    "വയസ്സ്",
    "നൂറ്റാണ്ട്",
    "ആൾ",
    "തവണ",
    "പ്രാവശ്യ",
    "കപ്പ്",
    "ഗ്ലാസ്",
    "സ്പൂൺ",
    "ടീസ്പൂൺ",
    "കഷണ",
    "പാക്കറ്റ്",
    "കുപ്പി",
    "പുസ്തക",
    "വീട്",
    "കാർ",
    "കുട്ടി",
    "മകൻ",
    "മകൾ",
    "പോയിന്റ്",
    "ഗോൾ",
    "റൺ",
    "വിക്കറ്റ്",
    "മെഡൽ",
    "ലക്ഷ",
    "കോടി",
    "രൂപ",
    "ഡോളർ",
    "സ്ഥല",
    "ഭാഗ",
];

/// `"|".join(sorted(keys, key=len, reverse=True))`: longest first, ties in table order.
fn longest_first(keys: &[&str]) -> String {
    let mut ks: Vec<&str> = keys.to_vec();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    ks.join("|")
}

fn sign(v: char) -> &'static str {
    SIGN.iter().find(|(a, _)| *a == v).map_or("", |&(_, b)| b)
}

/// `s[1:]` in characters.
fn rest1(s: &str) -> &str {
    let mut it = s.chars();
    it.next();
    it.as_str()
}

/// `s[:-1]` in characters.
fn drop_last(s: &str) -> String {
    let mut out = s.to_string();
    out.pop();
    out
}

/// A multiplier word and ആയിരം / ആയിരത്തി as one word: പത്ത് -> പതിനായിരം, ഇരുപത് -> ഇരുപതിനായിരം, പതിമൂന്ന്
/// -> പതിമൂവായിരം, ഇരുപത്തിയഞ്ച് -> ഇരുപത്തിയയ്യായിരം, പതിനെട്ട് -> പതിനെണ്ണായിരം, പന്ത്രണ്ട് -> പന്ത്രണ്ടായിരം.
fn kfuse(w: &str, rest: &str) -> String {
    let tail = rest1(rest); // യിരം / യിരത്തി
    if w == "പത്ത്" {
        return format!("പതിനാ{tail}");
    }
    if let Some(b) = w.strip_suffix("മൂന്ന്") {
        return format!("{b}മൂവാ{tail}");
    }
    if let Some(b) = w.strip_suffix("ഞ്ച്") {
        return format!("{b}യ്യാ{tail}");
    }
    if let Some(b) = w.strip_suffix("ട്ട്") {
        return format!("{b}ണ്ണാ{tail}");
    }
    if w.ends_with("ത്") {
        return format!("{}\u{0D3F}നാ{tail}", drop_last(w));
    }
    format!("{}\u{0D3E}{tail}", drop_last(w))
}

/// The grammar writes 10,000–99,999 as two words (“അൻപത് ആയിരം”); Malayalam says them as one (അൻപതിനായിരം).
fn thousands(spoken: &str) -> String {
    let mut out: Vec<String> = Vec::new();
    for w in spoken.split_whitespace() {
        if let Some(prev) = out.last_mut()
            && (w == "ആയിരം" || w == "ആയിരത്തി")
            && prev.ends_with(VIRAMA)
            && prev.chars().count() > 2
        {
            *prev = kfuse(prev, w);
            continue;
        }
        out.push(w.to_string());
    }
    out.join(" ")
}

/// A written number as the grammar reads it (thousands fused), or None for a leading zero.
fn plain(n: &str) -> Option<String> {
    let d = n.replace(',', "");
    let b = d.as_bytes();
    if b.len() > 1 && b[0] == b'0' && b[1] != b'.' {
        return None;
    }
    Some(thousands(&words(&d, "ml")))
}

/// A number word and the ending glued to it as one word: ഏഴ് + ൽ -> ഏഴിൽ, നൂറ് + ൽ -> നൂറിൽ, മൂന്ന് + ന് ->
/// മൂന്നിന്, ആയിരം + ൽ -> ആയിരത്തിൽ, തൊണ്ണൂറ് + കളിൽ -> തൊണ്ണൂറുകളിൽ, നൂറ് + ഓളം -> നൂറോളം, മണി + ന് -> മണിക്ക്.
fn join(w: &str, tail: &str) -> Option<String> {
    let (base, linked) = if w.ends_with(VIRAMA) {
        (drop_last(w), format!("{}\u{0D3F}", drop_last(w)))
    } else if w.ends_with('ം') {
        (format!("{}ത്ത", drop_last(w)), format!("{}ത്തി", drop_last(w)))
    } else if w.ends_with('\u{0D3F}') {
        for &(d, i) in DAT_I {
            if tail == d {
                return Some(format!("{w}{i}"));
            }
        }
        (format!("{w}യ"), format!("{w}യി"))
    } else {
        return None;
    };
    if TAIL_PL.contains(&tail) {
        if w.ends_with(VIRAMA) {
            return Some(format!("{base}\u{0D41}{tail}"));
        }
        if w.ends_with('ം') {
            return Some(format!("{}ങ്ങ{}", drop_last(w), rest1(tail)));
        }
        return Some(format!("{w}{tail}"));
    }
    if TAIL_V.contains(&tail) {
        return Some(format!("{base}{}{}", sign(tail.chars().next().unwrap()), rest1(tail)));
    }
    Some(format!("{linked}{tail}"))
}

fn inflect(spoken: &str, tail: &str) -> Option<String> {
    let mut ws: Vec<String> = spoken.split_whitespace().map(str::to_string).collect();
    let n = ws.len();
    ws[n - 1] = join(&ws[n - 1], tail)?;
    Some(ws.join(" "))
}

fn ml_money_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<![{ML}\w])രൂ\.? ?(?=[0-9])")), &t, "₹");
    c.sub_tpl(&rx(&format!(r"(₹ ?(?:{NUM})(?:\.[0-9]{{1,2}})?)/-")), &t, r"\1")
}

fn ml_money_scale(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?:₹|(?<![\w.])Rs\.?|(?<!\w)INR) ?((?:{NUM})(?:\.[0-9]+)?) ?(ആയിരം|ലക്ഷം|കോടി)(?![{ML}])");
    c.sub_tpl(&rx(&pat), &t, r"\1 \2 രൂപ")
}

fn ml_half(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(r"(?<![\w.,:/-])([0-9]{1,3})(?:½| 1/2)(?![0-9/])"), &t, |m| {
        let sp = plain(g(m, 1))?;
        if !sp.ends_with(VIRAMA) {
            return None;
        }
        Some(format!("{}ര", drop_last(&sp)))
    });
    let pat = format!(r"(?<![\w.,:/-])(?<![0-9] )(?:½|1/2) ?(?=(?:{}))", longest_first(HALF_NOUNS));
    c.sub_tpl(&rx(&pat), &t, "അര ")
}

fn ml_range(t: String, c: &mut Ctx) -> String {
    let nouns = longest_first(&[ONE_NOUNS, &["പേർ"][..]].concat());
    let pat = format!(r"(?<![\w.,:/+-])([0-9]{{1,9}})(?:-|–| – )([0-9]{{1,9}})(?![\w,:/]|[.-][0-9])(?= (?:{nouns}))");
    c.sub(&rx(&pat), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        if (a.len() > 1 && a.starts_with('0')) || (b.len() > 1 && b.starts_with('0')) || py_int(a) >= py_int(b) {
            return None;
        }
        Some(format!("{a} മുതൽ {b}"))
    })
}

fn ml_thousands(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?<![\w.,:/+-])((?:[₹$€£¥]|(?<![\w.])Rs\.?|(?<!\w)(?:INR|USD|EUR|GBP)) ?)?({NUM})(?:\.[0-9]+)?(?![0-9]|[.,][0-9])(?: ?(?:%|°[CF]?|[A-Za-z]{{1,5}}(?![A-Za-z])))?(?= [{ML}]|[.!?,;:]?(?:\n|$)|[.!?,;:] )"
    );
    c.sub(&rx(&pat), &t, |m| {
        let n = g(m, 2);
        if n.len() > 1 && n.starts_with('0') {
            return None;
        }
        let sp0 = words(g(m, 0), "ml");
        let sp = thousands(&sp0);
        if sp == sp0 { None } else { Some(sp) }
    })
}

fn ml_pm_period(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?:([{ML}]+) )?(?<![\w.,:/])(0?[1-9]|1[0-2])(?::([0-5][0-9]))? ?(pm|PM|p\.m\.|P\.M\.|am|AM|a\.m\.|A\.M\.)(?!\w)"
    );
    c.sub(&rx(&pat), &t, |m| {
        let h = py_int(g(m, 2)).to_string();
        let hm = if g(m, 3).is_empty() { format!("{h} മണി") } else { format!("{h}:{}", g(m, 3)) };
        if PERIODS.contains(&g(m, 1)) {
            return Some(format!("{} {hm}", g(m, 1)));
        }
        if !matches!(py_int(&h), 4 | 5) || g(m, 4).starts_with(['p', 'P']) {
            return None;
        }
        let before = if g(m, 1).is_empty() { String::new() } else { format!("{} ", g(m, 1)) };
        Some(format!("{before}പുലർച്ചെ {hm}"))
    })
}

fn ml_pm_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<=[0-9]) ?(pm|PM|am|AM)([{ML}]+)")), &t, |m| {
        let w = if matches!(g(m, 1), "pm" | "PM") { "പിഎം" } else { "എഎം" };
        let tail = g(m, 2);
        if tail.starts_with(['ന', 'ല', 'ൽ']) {
            return Some(format!(" {}മ്മി{tail}", drop_last(w)));
        }
        Some(format!(" {w}{tail}"))
    })
}

fn ml_suffix(t: String, c: &mut Ctx) -> String {
    let tails = [TAIL_LOC, TAIL_DAT, TAIL_PL, TAIL_V, &["ല്\u{200d}?"][..]].concat().join("|");
    let pat = format!(
        "(?<![\\w.,:/–-])(?:([0-9]{{1,2}}):([0-5][0-9])|((?:{NUM})(?:\\.[0-9]+)?))-?((?:{tails})\u{200c}?)(?![{ML}])"
    );
    c.sub(&rx(&pat), &t, |m| {
        let mut tail = g(m, 4).replace(['\u{200c}', '\u{200d}'], "");
        if tail == "ല്" {
            tail = "ൽ".to_string();
        }
        if m.get(1).is_some() {
            let (h, mm) = (g(m, 1), g(m, 2));
            if py_int(h) > 23 || (mm.starts_with('0') && mm != "00") {
                return None;
            }
            let w = inflect(&if mm == "00" { "മണി".to_string() } else { words(mm, "ml") }, &tail)?;
            return Some(format!("{} {w}", words(&py_int(h).to_string(), "ml")));
        }
        inflect(&plain(g(m, 3))?, &tail)
    })
}

fn ml_one(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,:/₹$-])1(?= (?:{}))", longest_first(ONE_NOUNS));
    c.sub_tpl(&rx(&pat), &t, "ഒരു")
}

fn ml_doctor(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&format!(r"(?<!\w)Dr\.? (?=[{ML}])")), &t, "ഡോക്ടർ ")
}
