//! 'ta' rules: the port of the workbench's `langrules/ta.py` (ids `ta.*`).

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, g, matches_at_start, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ta.money-abbrev", ta_money_abbrev),
    ("ta.money-scale", ta_money_scale),
    ("ta.score", ta_score),
    ("ta.range", ta_range),
    ("ta.clock-hour-word", ta_clock_hour_word),
    ("ta.pm-evening", ta_pm_evening),
    ("ta.aaga", ta_aaga),
    ("ta.suffix", ta_suffix),
    ("ta.one", ta_one),
];

/// Tamil letters and vowel signs (not the Tamil digits and symbols).
const TA: &str = "\u{0B82}-\u{0BD7}";
/// 1947, 1,500, 1,25,00,000 (10+ bare digits: a phone number).
const NUM: &str = r"[0-9]{1,3}(?:,[0-9]{2,3})*,[0-9]{3}|[0-9]{1,9}";
/// The vowel sign each independent vowel becomes when it fuses onto a consonant (ஏழு + இல் -> ஏழில்).
const SIGN: &[(&str, &str)] = &[
    ("அ", ""),
    ("ஆ", "\u{0BBE}"),
    ("இ", "\u{0BBF}"),
    ("ஈ", "\u{0BC0}"),
    ("உ", "\u{0BC1}"),
    ("ஊ", "\u{0BC2}"),
    ("எ", "\u{0BC6}"),
    ("ஏ", "\u{0BC7}"),
    ("ஐ", "\u{0BC8}"),
    ("ஒ", "\u{0BCA}"),
    ("ஓ", "\u{0BCB}"),
    ("ஔ", "\u{0BCC}"),
];
/// Vowel-initial suffixes on the oblique stem (ஆயிரத்தில், நூற்றில்) and on the plain stem (ஆயிரமாம், நூறாக).
const TAIL_OBL: &[&str] = &[
    "இலிருந்து",
    "இலேயே",
    "இல்தான்",
    "இலுள்ள",
    "இலும்",
    "இலே",
    "இல்",
    "இற்கு",
    "இனால்",
    "இன்",
    "ஐயும்",
    "ஐ",
    "ஆலும்",
    "ஆல்",
    "ஓடு",
    "உடன்",
];
const TAIL_NOM: &[&str] = &["ஆவது", "ஆம்", "ஆகும்", "ஆக", "ஆன", "உம்"];
/// 1947ல் (written short for இல்).
const TAIL_LOC: &[&str] = &["லிருந்து", "லேயே", "ல்தான்", "லுள்ள", "லும்", "லே", "ல்"];
const TAIL_DAT: &[&str] = &["க்குள்", "க்கும்", "க்கான", "க்குப்", "க்குத்", "க்குச்", "க்குக்", "க்கு"];
const TAIL_PL: &[&str] = &["களிலிருந்து", "களிலும்", "களில்", "களின்", "களுக்கு", "களை", "களாக"];
/// 5ம் தேதி (written short for ஆம்).
const TAIL_ORD: &[&str] = &["ம்"];
/// A number word that starts with a vowel and fuses with the -த்து / -ற்று before it (நாற்பத்து ஏழு -> நாற்பத்தேழு).
const UNIT_START: &[&str] = &["ஒன்", "ஒரு", "ஓர", "இரண்ட", "ஐந்", "ஆற", "ஆறு", "ஏழ", "எட்ட"];
const PERIODS: &[&str] = &["காலை", "மதியம்", "மாலை", "இரவு", "அதிகாலை"];
/// Nouns and units a count of one stands before (prefixes: நாள் matches நாளில், மணி matches மணிக்கு, மணிநேரம்).
const ONE_NOUNS: &[&str] = &[
    "கிலோ",
    "கிராம்",
    "லிட்டர்",
    "மீட்டர்",
    "சென்டிமீட்டர்",
    "மில்லி",
    "டன்",
    "அடி",
    "அங்குல",
    "ஏக்கர்",
    "ஹெக்டேர்",
    "டிகிரி",
    "சதவீத",
    "நாள",
    "நாட்க",
    "மணி",
    "நிமிட",
    "வினாடி",
    "விநாடி",
    "வார",
    "மாத",
    "ஆண்டு",
    "ஆண்டி",
    "வருட",
    "வயது",
    "நூற்றாண்டு",
    "பேர்",
    "நபர",
    "ஆள்",
    "முறை",
    "தடவை",
    "கப்",
    "டம்ளர்",
    "ஸ்பூன்",
    "டீஸ்பூன்",
    "தேக்கரண்டி",
    "மேசைக்கரண்டி",
    "துண்டு",
    "பாக்கெட்",
    "பெட்டி",
    "பாட்டில்",
    "பக்க",
    "புள்ளி",
    "கோல்",
    "ரன்",
    "விக்கெட்",
    "பதக்க",
    "லட்ச",
    "கோடி",
    "ஆயிர",
    "ரூபாய்",
    "டாலர்",
    "குழந்தை",
    "மகன்",
    "மகள்",
    "வீடு",
    "கார்",
    "புத்தக",
    "கிளாஸ்",
    "சிட்டிகை",
    "கைப்பிடி",
    "மடங்கு",
    "பங்கு",
];

fn tails() -> String {
    [TAIL_OBL, TAIL_NOM, TAIL_LOC, TAIL_DAT, TAIL_PL, TAIL_ORD].concat().join("|")
}

/// `"|".join(sorted(keys, key=len, reverse=True))`: longest first, ties in table order.
fn longest_first(keys: &[&str]) -> String {
    let mut ks: Vec<&str> = keys.to_vec();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    ks.join("|")
}

fn sign(v: char) -> Option<&'static str> {
    SIGN.iter().find(|(a, _)| a.starts_with(v)).map(|&(_, b)| b)
}

/// `s[1:]` in characters.
fn rest1(s: &str) -> &str {
    let mut it = s.chars();
    it.next();
    it.as_str()
}

/// `s[:-n]` in characters.
fn drop_last(s: &str, n: usize) -> String {
    let mut out = s.to_string();
    for _ in 0..n {
        out.pop();
    }
    out
}

/// Tamil sandhi between the number words a rule writes: -த்து/-ற்று + a vowel-initial unit fuse (நாற்பத்து ஏழு ->
/// நாற்பத்தேழு, இருபத்து ஒரு -> இருபத்தொரு), and before க ச த ப the consonant doubles (ஆயிரத்துத் தொள்ளாயிரத்து).
fn fuse(ws: &[String]) -> Vec<String> {
    let mut out = vec![ws[0].clone()];
    for w in &ws[1..] {
        let p = out.last().unwrap().clone();
        if p.ends_with("த்து") || p.ends_with("ற்று") {
            let first = w.chars().next().unwrap();
            if UNIT_START.iter().any(|u| w.starts_with(u)) {
                *out.last_mut().unwrap() = format!("{}{}{}", drop_last(&p, 1), sign(first).unwrap_or(""), rest1(w));
                continue;
            }
            if "கசதப".contains(first) {
                *out.last_mut().unwrap() = format!("{p}{first}\u{0BCD}");
            }
        }
        out.push(w.clone());
    }
    out
}

/// A number word and the suffix glued to it as one word: ஏழு + இல் -> ஏழில், நூறு + க்கு -> நூற்றுக்கு, ஆயிரம் + இல்
/// -> ஆயிரத்தில், ஐந்து + ஆம் -> ஐந்தாம், கோடி + இல் -> கோடியில்; None when the word has no known form.
fn join(w: &str, tail: &str) -> Option<String> {
    let mut tail = tail.to_string();
    if TAIL_LOC.contains(&tail.as_str()) {
        tail = format!("இ{tail}");
    }
    if TAIL_ORD.contains(&tail.as_str()) {
        tail = "ஆம்".to_string();
    }
    let nom = TAIL_NOM.contains(&tail.as_str());
    let dat = TAIL_DAT.contains(&tail.as_str());
    let pl = TAIL_PL.contains(&tail.as_str());
    let vowel = || -> String { format!("{}{}", sign(tail.chars().next().unwrap()).unwrap_or(""), rest1(&tail)) };
    if w.ends_with('\u{0BC1}') {
        // -u: ஏழு, ஐந்து, நூறு
        let mut base = drop_last(w, 1);
        if !nom && (w.ends_with("நூறு") || w.ends_with("ணூறு")) {
            base.push_str("\u{0BCD}ற"); // the oblique நூற்று
        }
        if dat {
            return Some(format!("{base}\u{0BC1}{tail}"));
        }
        if pl {
            return Some(format!("{w}{tail}"));
        }
        return Some(format!("{base}{}", vowel()));
    }
    if w.ends_with("ம்") {
        // ஆயிரம், லட்சம், தொள்ளாயிரம்
        let base = drop_last(w, 2);
        if dat {
            return Some(format!("{base}த்து{tail}"));
        }
        if pl {
            return Some(format!("{base}ங்{tail}"));
        }
        return Some(format!("{base}{}{}", if nom { "ம" } else { "த்த" }, vowel()));
    }
    if w.ends_with('\u{0BBF}') {
        // கோடி, மணி
        if dat || pl {
            return Some(format!("{w}{tail}"));
        }
        return Some(format!("{w}ய{}", vowel()));
    }
    None
}

/// The grammar's reading of a number with the suffix fused onto its last word and the sandhi applied.
fn inflect(spoken: &str, tail: &str) -> Option<String> {
    let mut ws: Vec<String> = spoken.split_whitespace().map(str::to_string).collect();
    let n = ws.len();
    let last = ws[n - 1].clone();
    let ord = tail == "ஆம்" || tail == "ம்";
    if ord && last == "ஒன்று" && n > 1 {
        ws[n - 1] = "ஓராம்".to_string(); // இருபத்து ஒன்று + ஆம் -> இருபத்தோராம்
    } else if ord && last == "பதினொன்று" {
        ws[n - 1] = "பதினோராம்".to_string();
    } else {
        ws[n - 1] = join(&last, tail)?;
    }
    Some(fuse(&ws).join(" "))
}

/// A written number as the grammar reads it, or None for a leading zero (codes are not numbers).
fn plain(n: &str) -> Option<String> {
    let d = n.replace(',', "");
    let b = d.as_bytes();
    if b.len() > 1 && b[0] == b'0' && b[1] != b'.' {
        return None;
    }
    Some(words(&d, "ta"))
}

fn end0(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

fn ta_money_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<![{TA}\w])ரூ\.? ?(?=[0-9])")), &t, "₹");
    c.sub_tpl(&rx(&format!(r"(₹ ?(?:{NUM})(?:\.[0-9]{{1,2}})?)/-")), &t, r"\1")
}

fn ta_money_scale(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?:₹|(?<![\w.])Rs\.?|(?<!\w)INR) ?((?:{NUM})(?:\.[0-9]+)?) ?(ஆயிரம்|லட்சம்|கோடி)(?![{TA}])");
    c.sub_tpl(&rx(&pat), &t, r"\1 \2 ரூபாய்")
}

fn ta_score(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(r"(?<![\w.,:/-])([0-9]{1,2}) ?[-–] ?([0-9]{1,2})(?= (?:என்ற|என|கணக்கில்))"),
        &t,
        |m| {
            let a = plain(g(m, 1))?;
            let b = plain(g(m, 2))?;
            let a = inflect(&a, "க்கு")?;
            Some(format!("{a} {b}"))
        },
    )
}

fn ta_range(t: String, c: &mut Ctx) -> String {
    let nouns = longest_first(&[ONE_NOUNS, &["மாணவர்"][..]].concat());
    let noun_pat = format!(r" (?:{nouns})");
    let pat = format!(
        r"(?<![\w.,:/+-])([0-9]{{1,9}})(?:-|–| – )([0-9]{{1,9}})(?![\w,:/]|[.-][0-9])(?= [{TA}]|[.!?,;:)]?(?:\n|$)|[.!?,;:)] )"
    );
    let src = t.clone();
    c.sub(&rx(&pat), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        if (a.len() > 1 && a.starts_with('0')) || (b.len() > 1 && b.starts_with('0')) || py_int(a) >= py_int(b) {
            return None;
        }
        if matches_at_start(&noun_pat, &src[end0(m)..]) {
            return Some(format!("{a} முதல் {b}"));
        }
        if g(m, 0) != format!("{a}-{b}") {
            return None; // an en dash: the grammar's own “முதல் … வரை”
        }
        Some(format!("{a} முதல் {b} வரை"))
    })
}

fn ta_clock_hour_word(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/])([0-9]{1,2}):([0-5][0-9]) ?(?=மணி)"), &t, |m| {
        let (h, mm) = (g(m, 1), g(m, 2));
        if py_int(h) > 23 || (mm.starts_with('0') && mm != "00") {
            return None;
        }
        let tail = if mm == "00" { String::new() } else { format!("{} ", words(mm, "ta")) };
        Some(format!("{} {tail}", words(&py_int(h).to_string(), "ta")))
    })
}

fn ta_pm_evening(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?:([{TA}]+) )?(?<![\w.,:/])(0?[1-9]|1[0-2])(?::([0-5][0-9]))? ?(pm|PM|p\.m\.|P\.M\.|am|AM|a\.m\.|A\.M\.)(?!\w)"
    );
    c.sub(&rx(&pat), &t, |m| {
        let h = py_int(g(m, 2)).to_string();
        let hm = if g(m, 3).is_empty() { format!("{h} மணி") } else { format!("{h}:{}", g(m, 3)) };
        if PERIODS.contains(&g(m, 1)) {
            return Some(format!("{} {hm}", g(m, 1)));
        }
        if !matches!(py_int(&h), 4 | 5) {
            return None;
        }
        let word = if g(m, 4).starts_with(['p', 'P']) { "மாலை" } else { "அதிகாலை" };
        let before = if g(m, 1).is_empty() { String::new() } else { format!("{} ", g(m, 1)) };
        Some(format!("{before}{word} {hm}"))
    })
}

fn ta_aaga(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(&format!(r"(?<=[0-9]) ஆக(?= [{TA}])")), &t, " \u{e000}ஆக\u{e001}")
}

fn ta_suffix(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?<![\w.,:/–-])(?:([0-9]{{1,2}}):([0-5][0-9])|((?:{NUM})(?:\.[0-9]+)?))(-| (?=ஆம் [{TA}]))?({})(?![{TA}])",
        tails()
    );
    c.sub(&rx(&pat), &t, |m| {
        let tail = g(m, 5);
        if m.get(1).is_some() {
            let (h, mm) = (g(m, 1), g(m, 2));
            if py_int(h) > 23 || (mm.starts_with('0') && mm != "00") {
                return None;
            }
            let hw = words(&py_int(h).to_string(), "ta");
            if mm == "00" {
                return Some(format!("{hw} {}", inflect("மணி", tail)?));
            }
            return Some(format!("{hw} {}", inflect(&words(mm, "ta"), tail)?));
        }
        inflect(&plain(g(m, 3))?, tail)
    })
}

fn ta_one(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,:/₹$-])((?:{NUM})(?<=1))(?= (?:{}))", longest_first(ONE_NOUNS));
    c.sub(&rx(&pat), &t, |m| {
        let sp = plain(g(m, 1))?;
        let mut ws: Vec<String> = sp.split_whitespace().map(str::to_string).collect();
        let n = ws.len();
        if ws[n - 1] == "ஒன்று" {
            ws[n - 1] = "ஒரு".to_string();
        } else if ws[n - 1] == "பதினொன்று" {
            ws[n - 1] = "பதினொரு".to_string();
        } else {
            return None;
        }
        Some(fuse(&ws).join(" "))
    })
}
