//! 'ta' rules: the port of the workbench's `langrules/ta.py` (ids `ta.*`).

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ta.money-abbrev", ta_money_abbrev),
    ("ta.money-minus", ta_money_minus),
    ("ta.big", ta_big),
    ("ta.money-code", ta_money_code),
    ("ta.per", ta_per),
    ("ta.money-range", ta_money_range),
    ("ta.money-decimal", ta_money_decimal),
    ("ta.money-scale", ta_money_scale),
    ("ta.money-scale-case", ta_money_scale_case),
    ("ta.half-scale", ta_half_scale),
    ("ta.units", ta_units),
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
    "சதுர",
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

// ------------------------------------------------------------------------------------------------- money (shared)
// The money helpers below are shared with the other Dravidian modules (te.rs, kn.rs, ml.rs): prototype `ta.py`.

/// A sign or code before the amount.
pub(super) const DR_CUR_B: &str = r"(?:[₹$€£]|(?<![A-Za-z])(?:Rs\.|Rs|INR|USD|EUR|GBP)(?![A-Za-z]))";
/// A sign or code after the amount.
pub(super) const DR_CUR_A: &str = r"(?:[₹$€£]|(?<![A-Za-z])(?:Rs|INR|USD|EUR|GBP)(?![A-Za-z]))";
/// 1,500.50, 1,00,000, 25.5.
pub(super) const DR_AMT: &str = r"[0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]{1,9}(?:\.[0-9]{1,2})?";
/// A range: hyphen, dashes, tildes.
pub(super) const DR_SEP: &str = r" ?[-–—~～〜] ?";
/// The spaces that group digits (space, no-break space, narrow no-break space).
pub(super) const DR_GAP: &str = " \u{a0}\u{202f}";
/// After a minus: a currency sign or code and a digit (-₹5, -Rs. 5, -USD 5, -HK$5).
pub(super) const DR_CODES_MINUS: &str =
    r"(?:[₹$€£¥₨]|(?:Rs\.|Rs|INR|USD|EUR|GBP|LKR|PKR|AED|SAR|QAR|KWD|BHD|SGD|MYR|[A-Z]{1,3}\$) ?)[0-9]";

/// The range sayer: (first amount, second amount, currency, currency after, scale word).
pub(super) type Compose = fn(&str, &str, &str, bool, &str) -> Option<String>;

/// An alternation of literal keys, longest first (a dot escaped).
pub(super) fn dr_alt(keys: &[&str]) -> String {
    let mut ks: Vec<&str> = keys.to_vec();
    ks.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    ks.iter().map(|k| k.replace('.', r"\.")).collect::<Vec<_>>().join("|")
}

/// An amount written with its sign or code: ₹5, Rs. 5, USD 5, 5 €.
pub(super) fn dr_money(cur: &str, amt: &str, after: bool) -> String {
    if after {
        return format!("{amt} {cur}");
    }
    let sp = cur.chars().last().is_some_and(|ch| ch.is_alphabetic() || ch == '.');
    format!("{cur}{}{amt}", if sp { " " } else { "" })
}

/// One decimal is tenths of the unit: 2.5 -> 2.50.
pub(super) fn dr_pad(amt: &str) -> String {
    let cs: Vec<char> = amt.chars().collect();
    let n = cs.len();
    if n >= 2 && cs[n - 2] == '.' && cs[n - 1].is_ascii_digit() { format!("{amt}0") } else { amt.to_string() }
}

pub(super) fn dr_lead0(n: &str) -> bool {
    let d = n.replace(',', "");
    let b = d.as_bytes();
    b.len() > 1 && b[0] == b'0' && b[1] != b'.'
}

fn dr_num(n: &str) -> f64 {
    n.replace(',', "").parse::<f64>().unwrap_or(0.0)
}

/// The grammar's word for a currency sign or code (₹ -> ரூபாய், € -> యూరోలు), or None.
pub(super) fn dr_cur_word(cur: &str, after: bool, lang: &str) -> Option<String> {
    let base = words("1000", lang);
    let said = words(&dr_money(cur, "1000", after), lang);
    let head = format!("{base} ");
    if !said.starts_with(&head) {
        return None;
    }
    Some(said[head.len()..].to_string())
}

/// The grammar leaves part of `s` unread or misreads it (a sign, a code, a digit, a dash or a dot is left).
fn dr_wrong(s: &str, lang: &str) -> bool {
    search(r"[0-9A-Za-z₹$€£¥₩₽₺₱฿৳₨~\-–—/.]", &words(s, lang))
}

/// ₹5-10, $5~10, €5–€10, 5-10 €, ₹5-10 லட்சம்: `compose` says the range; the first amount must be smaller and neither
/// may have a leading zero. A price per unit ($10-$20/h) is left to the per rule and the grammar.
pub(super) fn dr_money_range(t: String, c: &mut Ctx, scales: &[&str], letters: &str, compose: Compose) -> String {
    let ok = |a: &str, b: &str, cur: &str, cur2: &str| {
        !(!cur2.is_empty() && cur2 != cur) && !dr_lead0(a) && !dr_lead0(b) && dr_num(a) < dr_num(b)
    };
    let pat = format!(
        r"(?<![\w.,\-–—~])({DR_CUR_B}) ?({DR_AMT}){DR_SEP}(?:({DR_CUR_B}) ?)?({DR_AMT})(?![0-9]|[.,][0-9])(?: ?({})(?![{letters}]))?(?! ?/)",
        scales.join("|")
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        if !ok(g(m, 2), g(m, 4), g(m, 1), g(m, 3)) {
            return None;
        }
        compose(g(m, 2), g(m, 4), g(m, 1), false, g(m, 5))
    });
    let pat = format!(r"(?<![\w.,\-–—~₹$€£])({DR_AMT})(?: ?({DR_CUR_A}))?{DR_SEP}({DR_AMT}) ?({DR_CUR_A})(?! ?/)");
    c.sub(&rx(&pat), &t, |m| {
        if !ok(g(m, 1), g(m, 3), g(m, 4), g(m, 2)) {
            return None;
        }
        compose(g(m, 1), g(m, 3), g(m, 4), true, "")
    })
}

/// `₹500/மாதம்` -> `ஒரு மாதத்திற்கு ₹500`: the per phrase from `table` (unit as written -> phrase) before the amount,
/// which is kept as written (with a range, a scale word or a currency word) for the later rules and the grammar.
pub(super) fn dr_per(
    t: String,
    c: &mut Ctx,
    table: &[(&str, &str)],
    scales: &[&str],
    curwords: &[&str],
    letters: &str,
) -> String {
    let amount = format!("(?:{DR_AMT})");
    let sc = format!("(?: ?(?:{}))?", scales.join("|"));
    let money = format!(
        "(?:{DR_CUR_B} ?{amount}(?:{DR_SEP}(?:{DR_CUR_B} ?)?{amount})?{sc}|{amount}(?:{DR_SEP}{amount})?{sc} ?(?:{DR_CUR_A}|{}))",
        curwords.join("|")
    );
    let keys: Vec<&str> = table.iter().map(|&(k, _)| k).collect();
    let pat = format!(r"(?<![\w.,])({money}) ?/ ?({})(?![{letters}\w²³])", dr_alt(&keys));
    c.sub(&rx(&pat), &t, |m| {
        let per = table.iter().find(|&&(k, _)| k == g(m, 2))?.1;
        Some(format!("{per} {}", g(m, 1)))
    })
}

/// Numbers from 10^9 up (to 10^16) in crores, as they are said: 10,00,00,00,00,000 -> `100000 கோடி`, with the rest
/// after the crores; a space-grouped number (1 500 000, 15 000 kg; not a PIN code 600 001) is joined. `alone(rest)` is the crore word at the
/// end of an amount without a currency (`rest`: the text after the number); from 10^14 the crores are counted in
/// lakhs (`lakh`: the lakh word alone and before more).
#[allow(clippy::too_many_arguments)]
pub(super) fn dr_big(
    t: String,
    c: &mut Ctx,
    lang: &str,
    alone: fn(&str) -> &'static str,
    before: &str,
    link: &str,
    lakh: (&str, &str),
    arab: &[&str],
) -> String {
    let crores = |n: u128| -> String {
        if n < 10u128.pow(7) {
            return n.to_string();
        }
        let (k, r) = (n / 10u128.pow(5), n % 10u128.pow(5));
        if r != 0 { format!("{k} {} {r}", lakh.1) } else { format!("{k} {}", lakh.0) }
    };
    let pat = format!(
        r"(?<![\w.,+])(?<![0-9] )(?:({DR_CUR_B}) ?)?([0-9]{{1,3}}(?:,[0-9]{{2,3}})+|[1-9][0-9]{{0,2}}(?:[{DR_GAP}][0-9]{{3}})+|[1-9][0-9]{{9,14}})(?:\.([0-9]{{1,2}}))?(?![0-9]|[.,][0-9]|[{DR_GAP}][0-9])(?: ?({DR_CUR_A}))?"
    );
    let src = t.clone();
    c.sub(&rx(&pat), &t, |m| {
        let (cur_b, num, dec, cur_a) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let gap = |ch: char| DR_GAP.contains(ch);
        let digits: String = num.chars().filter(|&ch| ch != ',' && !gap(ch)).collect();
        let spaced = num.chars().any(gap);
        let n = py_int(&digits);
        let cur = if cur_b.is_empty() { cur_a } else { cur_b };
        if n >= 10u128.pow(16) {
            return None;
        }
        if n < 10u128.pow(9) {
            if !spaced {
                return None;
            }
            let groups = num.chars().filter(|&ch| gap(ch)).count();
            if groups < 2
                && cur.is_empty()
                && (digits.chars().count() > 5 || !matches_at_start(r" ?[A-Za-z]{1,3}(?![A-Za-z])", &src[end0(m)..]))
            {
                return None;
            }
            return Some(g(m, 0).replace(num, &digits));
        }
        if !spaced && !num.contains(',') {
            let said = words(&digits, lang);
            if !arab.iter().any(|w| said.contains(w)) {
                return None;
            }
        }
        if !dec.is_empty() && cur.is_empty() {
            return None;
        }
        let (crore, rest) = (n / 10u128.pow(7), n % 10u128.pow(7));
        if cur.is_empty() {
            let tail = if rest == 0 { alone(&src[end0(m)..]).to_string() } else { format!("{link} {rest}") };
            return Some(format!("{} {tail}", crores(crore)));
        }
        let after = cur_b.is_empty();
        if rest == 0 {
            let cw = dr_cur_word(cur, after, lang)?;
            let mut out = format!("{} {before} {cw}", crores(crore));
            if !dec.is_empty() {
                let cents = dr_pad(&format!(".{dec}"));
                out = format!("{out} {}", words(&dr_money(cur, &format!("0.{}", &cents[1..]), after), lang));
            }
            return Some(out);
        }
        let amt = if dec.is_empty() { rest.to_string() } else { format!("{rest}.{dec}") };
        Some(format!("{} {link} {}", crores(crore), dr_money(cur, &amt, after)))
    })
}

/// Currency codes (and signs) the grammar leaves unread: `table` is (code, plural, singular, minor unit) and `signs`
/// (sign, code). The amount is read as the grammar reads it with ₹ and the rupee words swapped for the currency's
/// (`rupee`: the grammar's rupee words, plural first; `paisa`: its minor-unit word); with no minor unit (or three
/// decimals) a decimal is read as a decimal, without its trailing zeros. `read` is the language's plain reading of a
/// number, `post` the language's touch to the grammar's reading (ml joins the thousands).
#[allow(clippy::too_many_arguments)]
pub(super) fn dr_code(
    t: String,
    c: &mut Ctx,
    lang: &str,
    table: &[(&str, &str, &str, &str)],
    signs: &[(&str, &str)],
    rupee: &[&str],
    paisa: &str,
    read: fn(&str) -> Option<String>,
    post: fn(&str) -> String,
) -> String {
    let mut ks: Vec<&str> = table.iter().map(|e| e.0).collect();
    ks.extend(signs.iter().map(|e| e.0));
    let keys = dr_alt(&ks);
    let amt = r"[0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,3})?|[0-9]{1,9}(?:\.[0-9]{1,3})?";
    let pat = format!(
        r"(?<![\w.,])(?<![0-9][-–—~～〜])(?:({keys}) ?({amt})|({amt}) ?({keys}))(?![A-Za-z0-9]|[.,][0-9]| ?[-–—~～〜] ?[0-9])"
    );
    c.sub(&rx(&pat), &t, |m| {
        if !dr_wrong(g(m, 0), lang) {
            return None;
        }
        let key = if g(m, 1).is_empty() { g(m, 4) } else { g(m, 1) };
        let a = if g(m, 2).is_empty() { g(m, 3) } else { g(m, 2) };
        if dr_lead0(a) {
            return None;
        }
        let code = signs.iter().find(|&&(s, _)| s == key).map_or(key, |e| e.1);
        let &(_, pl, sg, minor) = table.iter().find(|e| e.0 == code)?;
        let (head, dec) = match a.split_once('.') {
            Some((h, d)) => (h, d),
            None => (a, ""),
        };
        if !dec.is_empty() && (minor.is_empty() || dec.chars().count() == 3) {
            let sp = read(a.trim_end_matches('0').trim_end_matches('.'))?;
            return Some(format!("{sp} {pl}"));
        }
        let amount =
            if dec.is_empty() { head.to_string() } else { format!("{head}.{}", &dr_pad(&format!(".{dec}"))[1..]) };
        let said = post(&words(&format!("₹{amount}"), lang));
        let out: Vec<&str> = said
            .split(' ')
            .map(|w| {
                if w == rupee[0] {
                    pl
                } else if rupee.contains(&w) {
                    sg
                } else if w == paisa {
                    minor
                } else {
                    w
                }
            })
            .collect();
        if !out.contains(&pl) && !out.contains(&sg) && !out.contains(&minor) {
            return None;
        }
        Some(out.join(" "))
    })
}

/// 2.5 கோடி -> இரண்டரை கோடி: N.5 before a scale word (bare or inflected) is N-and-a-half, as it is said.
pub(super) fn dr_half_scale(t: String, c: &mut Ctx, scales: &[&str], half: fn(u128) -> Option<String>) -> String {
    let pat =
        format!(r"(?<![\w.,₹$€£])(?<!Rs )(?<!Rs\. )(?<!INR )([1-9][0-9]?)\.5(?![0-9]) ?(?=(?:{}))", scales.join("|"));
    c.sub(&rx(&pat), &t, |m| Some(format!("{} ", half(py_int(g(m, 1)))?)))
}

/// ₹2 கோடிக்கு -> `2 கோடி ரூபாய்க்கு`: after a rupee amount the case ending of the scale word goes onto the rupee word
/// (`table`: the inflected scale word, the bare one, the rupee word with the ending).
pub(super) fn dr_scale_case(t: String, c: &mut Ctx, table: &[(&str, &str, &str)], letters: &str) -> String {
    let keys: Vec<&str> = table.iter().map(|e| e.0).collect();
    let pat = format!(
        r"(?:₹|(?<![\w.])Rs\.?|(?<!\w)INR) ?((?:[0-9]{{1,3}}(?:,[0-9]{{2,3}})*,[0-9]{{3}}|[0-9]{{1,9}})(?:\.[0-9]+)?) ?({})(?![{letters}])",
        dr_alt(&keys)
    );
    c.sub(&rx(&pat), &t, |m| {
        let &(_, bare, rupee) = table.iter().find(|e| e.0 == g(m, 2))?;
        Some(format!("{} {bare} {rupee}", g(m, 1)))
    })
}

/// ₹-5 -> `-₹5` (or the minus word): a minus between the sign and the amount.
pub(super) fn dr_sign_minus(t: String, c: &mut Ctx, word: &str) -> String {
    c.sub(&rx(r"(?<![\w.,])([₹$€£¥]) ?-(?=[0-9])"), &t, |m| Some(format!("{word}{}", g(m, 1))))
}

// ------------------------------------------------------------------------------------------------- Tamil money rules

const TA_SCALES: &[&str] = &["ஆயிரம்", "லட்சம்", "கோடி"];
const TA_HALF_SCALES: &[&str] = &["ஆயிர", "லட்ச", "கோடி", "மில்லியன்", "பில்லியன்"];
/// Codes the grammar leaves unread: (code, currency, the same before a count of one, minor unit).
const TA_CODES: &[(&str, &str, &str, &str)] = &[
    ("LKR", "இலங்கை ரூபாய்", "இலங்கை ரூபாய்", "சதம்"),
    ("QAR", "கத்தார் ரியால்", "கத்தார் ரியால்", "திர்ஹாம்"),
    ("KWD", "குவைத் தினார்", "குவைத் தினார்", ""),
    ("BHD", "பஹ்ரைன் தினார்", "பஹ்ரைன் தினார்", ""),
];
/// Codes the grammar reads with cents when the amount has two decimals.
const TA_DEC_CODES: &[&str] = &[
    "Rs.", "Rs", "INR", "USD", "EUR", "GBP", "AUD", "CAD", "CHF", "SGD", "MYR", "PKR", "BDT", "AED", "SAR", "HKD",
    "NZD", "ZAR",
];
/// The unit after the slash of a price -> the per phrase (the grammar's own: ஒரு கிலோவிற்கு, ஒரு மாதத்திற்கு, மணிக்கு);
/// the Latin units the grammar reads are listed too, with its own phrase: it misreads $5/kg. before a full stop.
const TA_PER: &[(&str, &str)] = &[
    ("மாதம்", "ஒரு மாதத்திற்கு"),
    ("நாள்", "ஒரு நாளைக்கு"),
    ("தினம்", "ஒரு நாளைக்கு"),
    ("ஆண்டு", "ஒரு ஆண்டுக்கு"),
    ("வருடம்", "ஒரு வருடத்திற்கு"),
    ("வாரம்", "ஒரு வாரத்திற்கு"),
    ("மணி", "மணிக்கு"),
    ("மணிநேரம்", "ஒரு மணி நேரத்திற்கு"),
    ("மணி நேரம்", "ஒரு மணி நேரத்திற்கு"),
    ("கிலோ", "ஒரு கிலோவிற்கு"),
    ("கிராம்", "ஒரு கிராமுக்கு"),
    ("லிட்டர்", "ஒரு லிட்டருக்கு"),
    ("மீட்டர்", "ஒரு மீட்டருக்கு"),
    ("நபர்", "ஒரு நபருக்கு"),
    ("இரவு", "ஒரு இரவுக்கு"),
    ("யூனிட்", "ஒரு யூனிட்டுக்கு"),
    ("சதுர அடி", "ஒரு சதுர அடிக்கு"),
    ("ஏக்கர்", "ஒரு ஏக்கருக்கு"),
    ("டன்", "ஒரு டன்னுக்கு"),
    ("குவிண்டால்", "ஒரு குவிண்டாலுக்கு"),
    ("துண்டு", "ஒரு துண்டுக்கு"),
    ("l", "ஒரு லிட்டருக்கு"),
    ("L", "ஒரு லிட்டருக்கு"),
    ("g", "ஒரு கிராமுக்கு"),
    ("t", "ஒரு டன்னுக்கு"),
    ("qtl", "ஒரு குவிண்டாலுக்கு"),
    ("kWh", "ஒரு கிலோவாட் மணிக்கு"),
    ("unit", "ஒரு யூனிட்டுக்கு"),
    ("sqft", "ஒரு சதுர அடிக்கு"),
    ("sq ft", "ஒரு சதுர அடிக்கு"),
    ("sq.ft", "ஒரு சதுர அடிக்கு"),
    ("sq. ft", "ஒரு சதுர அடிக்கு"),
    ("m²", "ஒரு சதுர மீட்டருக்கு"),
    ("acre", "ஒரு ஏக்கருக்கு"),
    ("piece", "ஒன்றுக்கு"),
    ("pc", "ஒன்றுக்கு"),
    ("person", "ஒரு நபருக்கு"),
    ("night", "ஒரு இரவுக்கு"),
    ("week", "ஒரு வாரத்திற்கு"),
    ("mo", "ஒரு மாதத்திற்கு"),
    ("kg", "ஒரு கிலோவிற்கு"),
    ("km", "ஒரு கிலோமீட்டருக்கு"),
    ("m", "ஒரு மீட்டருக்கு"),
    ("hr", "மணிக்கு"),
    ("h", "மணிக்கு"),
    ("day", "ஒரு நாளைக்கு"),
    ("month", "ஒரு மாதத்திற்கு"),
    ("year", "ஒரு வருடத்திற்கு"),
];
/// Units the grammar leaves unread after a number.
const TA_UNITS: &[(&str, &str)] = &[
    ("sq ft", "சதுர அடி"),
    ("sq.ft", "சதுர அடி"),
    ("sq. ft", "சதுர அடி"),
    ("sqft", "சதுர அடி"),
    ("acres", "ஏக்கர்"),
    ("acre", "ஏக்கர்"),
];
const TA_ARAB: &[&str] = &["அரபம்", "கரபம்"];

/// N and a half: 2 -> இரண்டரை, 25 -> இருபத்தைந்தரை.
fn ta_and_half(n: u128) -> Option<String> {
    let mut ws: Vec<String> = plain(&n.to_string())?.split(' ').map(str::to_string).collect();
    let k = ws.len();
    if !ws[k - 1].ends_with('\u{0BC1}') {
        return None;
    }
    ws[k - 1] = format!("{}ரை", drop_last(&ws[k - 1], 1));
    Some(fuse(&ws).join(" "))
}

/// A number of a range: before a scale word N.5 is N-and-a-half.
fn ta_amount(x: &str, scale: bool) -> Option<String> {
    if scale && full(r"[1-9][0-9]?\.5", x) {
        return ta_and_half(py_int(&x[..x.len() - 2]));
    }
    plain(x)
}

fn ta_compose(a: &str, b: &str, cur: &str, after: bool, scale: &str) -> Option<String> {
    if !scale.is_empty() {
        let (aw, bw, cw) = (ta_amount(a, true)?, ta_amount(b, true)?, dr_cur_word(cur, after, "ta")?);
        return Some(format!("{aw} முதல் {bw} {scale} {cw}"));
    }
    let aw = if a.contains('.') { words(&dr_money(cur, &dr_pad(a), after), "ta") } else { plain(a)? };
    Some(format!("{aw} முதல் {}", words(&dr_money(cur, &dr_pad(b), after), "ta")))
}

fn ta_money_minus(t: String, c: &mut Ctx) -> String {
    dr_sign_minus(t, c, "-")
}

fn ta_big(t: String, c: &mut Ctx) -> String {
    dr_big(t, c, "ta", |_| "கோடி", "கோடி", "கோடியே", ("லட்சம்", "லட்சத்து"), TA_ARAB)
}

fn ta_money_code(t: String, c: &mut Ctx) -> String {
    dr_code(t, c, "ta", TA_CODES, &[], &["ரூபாய்"], "பைசா", plain, |s| s.to_string())
}

fn ta_per(t: String, c: &mut Ctx) -> String {
    dr_per(t, c, TA_PER, TA_SCALES, &["ரூபாய்"], TA)
}

fn ta_money_range(t: String, c: &mut Ctx) -> String {
    dr_money_range(t, c, TA_SCALES, TA, ta_compose)
}

fn ta_money_decimal(t: String, c: &mut Ctx) -> String {
    let codes = dr_alt(TA_DEC_CODES);
    let pat = format!(
        r"(?<![\w.,])((?:[₹$€£]|(?<![A-Za-z])(?:{codes})(?![A-Za-z])) ?(?:[0-9]{{1,3}}(?:,[0-9]{{2,3}})+|[0-9]+))\.([0-9])(?![0-9]|[.,][0-9])(?! ?(?:{}|[A-Za-z]))",
        TA_HALF_SCALES.join("|")
    );
    let t = c.sub(&rx(&pat), &t, |m| Some(format!("{}.{}0", g(m, 1), g(m, 2))));
    let pat = format!(
        r"(?<![\w.,])(?<![0-9][-–—~～〜])(?<![0-9] [-–—~～〜])([0-9]{{1,3}}(?:,[0-9]{{2,3}})+|[0-9]+)\.([0-9])( ?(?:[₹$€£]|(?:{codes})(?![A-Za-z])))"
    );
    c.sub(&rx(&pat), &t, |m| Some(format!("{}.{}0{}", g(m, 1), g(m, 2), g(m, 3))))
}

fn ta_half_scale(t: String, c: &mut Ctx) -> String {
    dr_half_scale(t, c, TA_HALF_SCALES, ta_and_half)
}

fn ta_units(t: String, c: &mut Ctx) -> String {
    let keys: Vec<&str> = TA_UNITS.iter().map(|&(k, _)| k).collect();
    let pat = format!(r"(?<=[0-9]) ?({})(?:\.(?= [^\W\d_]))?(?![A-Za-z])", dr_alt(&keys));
    c.sub(&rx(&pat), &t, |m| TA_UNITS.iter().find(|&&(k, _)| k == g(m, 1)).map(|&(_, w)| format!(" {w}")))
}

/// A scale word with a case ending after a rupee amount: (as written, the bare scale word, the rupee word with the ending).
const TA_SCALE_CASE: &[(&str, &str, &str)] = &[
    ("கோடிக்கு", "கோடி", "ரூபாய்க்கு"),
    ("கோடிக்கும்", "கோடி", "ரூபாய்க்கும்"),
    ("கோடிக்கான", "கோடி", "ரூபாய்க்கான"),
    ("கோடிக்குள்", "கோடி", "ரூபாய்க்குள்"),
    ("கோடியில்", "கோடி", "ரூபாயில்"),
    ("கோடியை", "கோடி", "ரூபாயை"),
    ("கோடியாக", "கோடி", "ரூபாயாக"),
    ("கோடியும்", "கோடி", "ரூபாயும்"),
    ("கோடியின்", "கோடி", "ரூபாயின்"),
    ("கோடியிலிருந்து", "கோடி", "ரூபாயிலிருந்து"),
    ("கோடியுடன்", "கோடி", "ரூபாயுடன்"),
    ("கோடியாகும்", "கோடி", "ரூபாயாகும்"),
    ("லட்சத்துக்கு", "லட்சம்", "ரூபாய்க்கு"),
    ("லட்சத்துக்கும்", "லட்சம்", "ரூபாய்க்கும்"),
    ("லட்சத்துக்கான", "லட்சம்", "ரூபாய்க்கான"),
    ("லட்சத்திற்கு", "லட்சம்", "ரூபாய்க்கு"),
    ("லட்சத்தில்", "லட்சம்", "ரூபாயில்"),
    ("லட்சத்தை", "லட்சம்", "ரூபாயை"),
    ("லட்சமாக", "லட்சம்", "ரூபாயாக"),
    ("லட்சமும்", "லட்சம்", "ரூபாயும்"),
    ("லட்சத்தின்", "லட்சம்", "ரூபாயின்"),
    ("லட்சத்திலிருந்து", "லட்சம்", "ரூபாயிலிருந்து"),
    ("லட்சத்துடன்", "லட்சம்", "ரூபாயுடன்"),
    ("லட்சமாகும்", "லட்சம்", "ரூபாயாகும்"),
    ("ஆயிரத்துக்கு", "ஆயிரம்", "ரூபாய்க்கு"),
    ("ஆயிரத்துக்கும்", "ஆயிரம்", "ரூபாய்க்கும்"),
    ("ஆயிரத்துக்கான", "ஆயிரம்", "ரூபாய்க்கான"),
    ("ஆயிரத்திற்கு", "ஆயிரம்", "ரூபாய்க்கு"),
    ("ஆயிரத்தில்", "ஆயிரம்", "ரூபாயில்"),
    ("ஆயிரத்தை", "ஆயிரம்", "ரூபாயை"),
    ("ஆயிரமாக", "ஆயிரம்", "ரூபாயாக"),
    ("ஆயிரமும்", "ஆயிரம்", "ரூபாயும்"),
    ("ஆயிரத்தின்", "ஆயிரம்", "ரூபாயின்"),
    ("ஆயிரத்திலிருந்து", "ஆயிரம்", "ரூபாயிலிருந்து"),
    ("ஆயிரத்துடன்", "ஆயிரம்", "ரூபாயுடன்"),
    ("ஆயிரமாகும்", "ஆயிரம்", "ரூபாயாகும்"),
];

fn ta_money_scale_case(t: String, c: &mut Ctx) -> String {
    dr_scale_case(t, c, TA_SCALE_CASE, TA)
}
