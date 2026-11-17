//! 'ka' rules: the port of the workbench's `langrules/ka.py` (ids `ka.*`).
//!
//! Georgian attributive numbers drop their final -ი before a noun in the dative or with a dative-based postposition
//! (ხუთ წუთში, ას ლარად); a suffix glued to a number with a hyphen replaces the number's final -ი when it starts with
//! -ი (90-იან → ოთხმოცდაათიან). These rules write those forms, starting from the grammar's own reading of the number.

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, re_escape, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ka.ordinal-prefix", ka_ordinal_prefix),
    ("ka.roman-century", ka_roman_century),
    ("ka.scale-abbrev", ka_scale_abbrev),
    ("ka.money-code", ka_money_code),
    ("ka.money-minus", ka_money_minus),
    ("ka.money-scale", ka_money_scale),
    ("ka.money-range", ka_money_range),
    ("ka.money-decimal", ka_money_decimal),
    ("ka.money-sign-suffix", ka_money_sign_suffix),
    ("ka.money-per", ka_money_per),
    ("ka.half", ka_half),
    ("ka.money-suffix", ka_money_suffix),
    ("ka.time-suffix", ka_time_suffix),
    ("ka.suffix-merge", ka_suffix_merge),
    ("ka.serial-suffix", ka_serial_suffix),
    ("ka.day-one", ka_day_one),
    ("ka.year-abbrev", ka_year_abbrev),
    ("ka.range", ka_range),
    ("ka.duration-and", ka_duration_and),
    ("ka.case-trunc", ka_case_trunc),
    ("ka.equals", ka_equals),
    ("ka.street-city", ka_street_city),
];

const SP: &str = r"[ \t\x{A0}]";
const NUM: &str = r"(\d{1,3}(?:[ \x{A0}]\d{3})+|\d+)";
const VERB_END: &[&str] = &["ებს", "ობს", "ავს", "ამს", "ვს"];
const VERBS: &[&str] = &["ღირს", "აქვს", "ჰყავს", "უყვარს", "წერს", "ჭამს", "სვამს", "ხვდება"];

/// A noun in the dative or with a dative-based postposition (წუთში, ლარად, სექტემბერს, წელს, კაცთან, წლამდე); not the
/// genitive -ის, the -ოს / -უს genitive of vowel stems, or a verb (აქვს, ცხოვრობს).
fn dative_word(w: &str) -> bool {
    if VERBS.contains(&w) || VERB_END.iter().any(|e| w.ends_with(e)) {
        return false;
    }
    full(r"[ა-ჰ]+?(?:ში|ზე|თან|ად|მდე|[ა-ჰ]ს)(?:ა|ც|აც|ვე)?", w) && !full(r"[ა-ჰ]*(?:[იოუ]ს)(?:ა|ც|აც|ვე)?", w)
}

/// The attributive form: the final -ი dropped (ხუთი → ხუთ, ასი → ას); vowel-final numbers (რვა, ცხრა) unchanged.
fn trunc(s: &str) -> &str {
    s.strip_suffix('ი').unwrap_or(s)
}

const VOWEL_GLUE: &[(&str, &str)] =
    &[("ია", "ა"), ("ა", "ა"), ("ად", "დ"), ("ს", "ს"), ("ში", "ში"), ("ზე", "ზე"), ("მდე", "მდე")];

/// A case suffix on a noun or number word: დოლარი + ია → დოლარია, + ად → დოლარად, + მდე → დოლარამდე; a word ending
/// in another vowel takes the vowel-stem forms (ევრო + ია → ევროა, + ად → ევროდ, რვა + ის → რვის) or None when unsure.
fn glue(word: &str, suffix: &str) -> Option<String> {
    if !word.ends_with('ი') {
        let last = word.chars().next_back();
        if suffix == "ის" && matches!(last, Some('ა' | 'ე')) {
            let mut w = word.to_string();
            w.pop();
            return Some(w + "ის");
        }
        if suffix == "ის" && matches!(last, Some('ო' | 'უ')) {
            return Some(format!("{word}ს"));
        }
        if matches!(last, Some('ა' | 'ე' | 'ო' | 'უ')) {
            return VOWEL_GLUE.iter().find(|(k, _)| *k == suffix).map(|(_, v)| format!("{word}{v}"));
        }
        return None;
    }
    let stem = trunc(word);
    Some(if suffix.starts_with('ი') {
        format!("{stem}{suffix}")
    } else if suffix == "მდე" {
        format!("{stem}ამდე")
    } else if suffix == "დან" {
        format!("{stem}იდან")
    } else if suffix == "თვის" {
        format!("{stem}ისთვის")
    } else {
        format!("{stem}{suffix}")
    })
}

const TRUNC_SUFFIX: &[&str] = &["ს", "ში", "ზე", "თან", "ად", "მდე"];

fn ka_ordinal_prefix(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\w-])მე[-–](\d+)(?![\d.,:/])"), &t, r"\1-ე")
}

const ROMAN: &str = r"(?=[IVXLC]{2,}|[IVX](?![a-zA-Z]))(C{0,3}(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))";

fn roman_value(s: &str) -> u32 {
    let val = |ch: char| match ch {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        _ => 100,
    };
    let cs: Vec<char> = s.chars().collect();
    let mut n: i64 = 0;
    for (i, &ch) in cs.iter().enumerate() {
        let v = val(ch);
        n += if i + 1 < cs.len() && val(cs[i + 1]) > v { -(v as i64) } else { v as i64 };
    }
    n as u32
}

fn ka_roman_century(t: String, c: &mut Ctx) -> String {
    let pat = [r"(?<![\w.-])", ROMAN, r"(?![\w.-])(", SP, r"+(?:საუკუნ|ათასწლეულ|კლას|ტომ|ნაწილ)[ა-ჰ]*)"].concat();
    c.sub(&rx(&pat), &t, |m| {
        if g(m, 1).is_empty() {
            return None;
        }
        Some(format!("{}-ე{}", roman_value(g(m, 1)), g(m, 2)))
    })
}

fn ka_scale_abbrev(t: String, c: &mut Ctx) -> String {
    let pat = [r"(?<![\w.,])(\d+(?:,\d+)?)(", SP, r"?)(მლნ|მლრდ)\.?(?![ა-ჰ])"].concat();
    c.sub(&rx(&pat), &t, |m| Some(format!("{} {}", g(m, 1), if g(m, 3) == "მლნ" { "მილიონი" } else { "მილიარდი" })))
}

// ------------------------------------------------------------------------------------------------- money

/// (sign or code, the currency's word); the grammar reads all but AZN / ₼.
const KA_CUR: &[(&str, &str)] = &[
    ("₾", "ლარი"),
    ("GEL", "ლარი"),
    ("$", "დოლარი"),
    ("USD", "დოლარი"),
    ("€", "ევრო"),
    ("EUR", "ევრო"),
    ("£", "გირვანქა სტერლინგი"),
    ("GBP", "გირვანქა სტერლინგი"),
    ("₽", "რუბლი"),
    ("RUB", "რუბლი"),
    ("₺", "ლირა"),
    ("TRY", "ლირა"),
    ("֏", "დრამი"),
    ("AMD", "დრამი"),
    ("₼", "მანათი"),
    ("AZN", "მანათი"),
];

fn ka_cur_rx() -> String {
    let mut keys: Vec<&str> = KA_CUR.iter().map(|x| x.0).collect();
    keys.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    format!("({})", keys.iter().map(|k| re_escape(k)).collect::<Vec<_>>().join("|"))
}

fn ka_cur_word(k: &str) -> &'static str {
    KA_CUR.iter().find(|x| x.0 == k).map_or("", |x| x.1)
}

/// The signs whose -დან / -მდე forms ka.money-suffix reads ($20-ად, €2.50-დან).
const KA_SUFFIX_SIGNS: &str = "$€£₾";
/// A whole part with commas or spaces between the groups, or plain digits.
const KA_AMT: &str = r"\d{1,3}(?:,\d{3})+|\d{1,3}(?:[  ]\d{3})+|\d+";

/// A scale after the amount: the decimal is not cents (2,5 მლნ ₾).
fn ka_scale() -> String {
    format!(r"(?:[A-Za-z]|{SP}*(?:მლნ|მლრდ|მილიონ|მილიარდ|ტრილიონ|ათას))")
}

/// The digits of `s` (`re.sub(r"[^0-9]", "", s)`).
fn ascii_digits(s: &str) -> String {
    s.chars().filter(char::is_ascii_digit).collect()
}

fn manat(whole: &str, frac: &str, suffix: &str) -> Option<String> {
    if !suffix.is_empty() {
        if !frac.is_empty() || suffix == "მა" {
            return None;
        }
        let word = glue("მანათი", suffix)?;
        let num = words(whole, "ka");
        if search(r"\d", &num) {
            return None;
        }
        let num = if TRUNC_SUFFIX.contains(&suffix) { trunc(&num).to_string() } else { num.clone() };
        return Some(format!("{num} {word}"));
    }
    if frac.is_empty() {
        return Some(format!("{whole} მანათი"));
    }
    let q = py_int(&format!("{frac}0").chars().take(2).collect::<String>());
    if whole.trim_matches('0').is_empty() {
        return Some(format!("{q} ყაფიკი"));
    }
    Some(if q > 0 {
        format!("{whole} მანათი და {q} ყაფიკი")
    } else {
        format!("{whole} მანათი")
    })
}

fn ka_money_code(t: String, c: &mut Ctx) -> String {
    let p = format!(r"(?<![\w.,])(?:AZN|₼){SP}?({KA_AMT})(?:[.,](\d{{1,2}}))?(?:[-–]([ა-ჰ]+))?(?![\w-]|[.,]\d)");
    let t = c.sub(&rx(&p), &t, |m| manat(g(m, 1), g(m, 2), g(m, 3)));
    let p = format!(r"(?<![\w.,])({KA_AMT})(?:[.,](\d{{1,2}}))?{SP}?(?:AZN|₼)(?:[-–]([ა-ჰ]+))?(?![\w-])");
    c.sub(&rx(&p), &t, |m| manat(g(m, 1), g(m, 2), g(m, 3)))
}

fn ka_money_minus(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\w.,-])([$€£₾₽₺֏])-(?=\d)"), &t, r"-\1")
}

fn ka_money_scale(t: String, c: &mut Ctx) -> String {
    let cur = ka_cur_rx();
    let p = format!(
        r"(?<![\w.,])(\d+(?:[.,]\d+)?)({SP}+)(მილიონი|მილიარდი|ტრილიონი|ათასი){SP}?{cur}(?:[-–]([ა-ჰ]+))?(?![\w-])"
    );
    let t = c.sub(&rx(&p), &t, |m| {
        let (mut word, suffix) = (ka_cur_word(g(m, 4)).to_string(), g(m, 5));
        if !suffix.is_empty() {
            let mut ws: Vec<String> = word.split(' ').map(str::to_string).collect();
            let last = if suffix != "მა" { glue(ws.last()?, suffix) } else { None }?;
            *ws.last_mut()? = last;
            word = ws.join(" ");
        }
        Some(format!("{}{}{} {word}", g(m, 1), g(m, 2), g(m, 3)))
    });
    let p = format!(r"(?<![\w.,]){cur}{SP}?(\d+(?:[.,]\d+)?)({SP}+)(მილიონი|მილიარდი|ტრილიონი|ათასი)(?![\w-])");
    c.sub(&rx(&p), &t, |m| Some(format!("{}{}{} {}", g(m, 2), g(m, 3), g(m, 4), ka_cur_word(g(m, 1)))))
}

/// One decimal is tens of cents: 2.5 → 2.50, 2,5 → 2,50.
fn ka_cents(amount: &str) -> String {
    if search(r"[.,]\d$", amount) { format!("{amount}0") } else { amount.to_string() }
}

/// The amount without its thousands separators, as ka.money-suffix reads it: 1,234.56 → 1234.56, 2 000,5 → 2000,5.
fn ka_flat(amount: &str) -> String {
    let r = rx(r"^(?:(.+?)(?:([.,])(\d{1,2}))?)\z");
    match r.captures(amount) {
        Ok(Some(m)) => {
            let dec = if g(&m, 3).is_empty() { String::new() } else { format!("{}{}", g(&m, 2), g(&m, 3)) };
            format!("{}{dec}", ascii_digits(g(&m, 1)))
        }
        _ => amount.to_string(),
    }
}

/// 2,50 and 2.50 → 2.5; 1,000 and 1 000 → 1000.
fn ka_value(amount: &str) -> f64 {
    let r = rx(r"^(?:(.+?)(?:[.,](\d{1,2}))?)\z");
    match r.captures(amount) {
        Ok(Some(m)) => {
            let frac = if g(&m, 2).is_empty() { "0" } else { g(&m, 2) };
            format!("{}.{frac}", ascii_digits(g(&m, 1))).parse().unwrap_or(0.0)
        }
        _ => 0.0,
    }
}

#[allow(clippy::too_many_arguments)]
fn ka_range_say(
    t: &str,
    end: usize,
    sign: &str,
    a: &str,
    b: &str,
    sep: &str,
    sign2: &str,
    after: bool,
) -> Option<String> {
    if ka_value(a) >= ka_value(b) || t[end..].split('\n').next().unwrap_or("").contains('=') {
        return None;
    }
    if search(r"[.,]\d{1,2}$", a) || search(r"[.,]\d{1,2}$", b) {
        if !KA_SUFFIX_SIGNS.contains(sign) {
            return None;
        }
        return Some(format!("{sign}{}-დან {sign}{}-მდე", ka_cents(&ka_flat(a)), ka_cents(&ka_flat(b))));
    }
    if !sep.contains('~') && !(after && !sign2.is_empty()) {
        return None; // 5 € - 10 €: the sign on both amounts after them is rewritten too
    }
    Some(if after { format!("{a}-{b} {sign}") } else { format!("{sign}{a}-{sign2}{b}") })
}

fn ka_money_range(t: String, c: &mut Ctx) -> String {
    let cur = ka_cur_rx();
    let scale = ka_scale();
    let amt = format!(r"(?:{KA_AMT})(?:[.,]\d{{1,2}})?");
    let p = format!(
        r"(?<![\w.,/-]){cur}{SP}?({amt})({SP}?[-–~]{SP}?){cur}?({amt})(?![\w]|[.,]\d|{SP}?[-–~]{SP}?\d|{scale})"
    );
    let t = c.sub(&rx(&p), &t, |m| {
        let (sign, a, sep, sign2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        if !sign2.is_empty() && sign2 != sign {
            return None;
        }
        ka_range_say(&t, m.get(0)?.end(), sign, a, b, sep, sign2, false)
    });
    let p = format!(r"(?<![\w.,/-])({amt})(?:{SP}?{cur})?({SP}?[-–~]{SP}?)({amt}){SP}?{cur}(?![\w])");
    c.sub(&rx(&p), &t, |m| {
        let (a, cur1, sep, b, sign) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        if !cur1.is_empty() && cur1 != sign {
            return None;
        }
        ka_range_say(&t, m.get(0)?.end(), sign, a, b, sep, cur1, true)
    })
}

fn ka_money_decimal(t: String, c: &mut Ctx) -> String {
    let cur = ka_cur_rx();
    let scale = ka_scale();
    let p = format!(r"(?<![\w.,]){cur}({SP}?)({KA_AMT})([.,])(\d)(?!\d|[.,]\d|{scale})");
    let t = c.sub(&rx(&p), &t, |m| Some(format!("{}{}{}{}{}0", g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5))));
    let p = format!(r"(?<![\w.,])({KA_AMT})([.,])(\d)({SP}?){cur}(?![\w])");
    c.sub(&rx(&p), &t, |m| Some(format!("{}{}{}0{}{}", g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5))))
}

fn ka_money_sign_suffix(t: String, c: &mut Ctx) -> String {
    let p = format!(r"(?<![\w.,])({KA_AMT})(?:([.,])(\d{{1,2}}))?({SP}?)([$€£₾])[-–]([ა-ჰ]+)(?![\w-])");
    c.sub(&rx(&p), &t, |m| {
        let (whole, sep, dec, sign, suffix) = (g(m, 1), g(m, 2), g(m, 3), g(m, 5), g(m, 6));
        if suffix == "მა" {
            return None;
        }
        let flat = if dec.is_empty() { ascii_digits(whole) } else { format!("{}{sep}{dec}", ascii_digits(whole)) };
        let said = words(&format!("{sign}{flat}"), "ka");
        let ws: Vec<&str> = said.split(' ').collect();
        if ws.len() < 2 || glue(ws[ws.len() - 1], suffix).is_none() || search(r"[0-9$€£₾]", &ws.join(" ")) {
            return None;
        }
        Some(format!("{sign}{flat}-{suffix}"))
    })
}

/// A unit after a price and a slash that the grammar does not read: (written, the per form).
const KA_PER: &[(&str, &str)] = &[
    ("კვ.მ.", "კვადრატულ მეტრზე"),
    ("კვ.მ", "კვადრატულ მეტრზე"),
    ("მ²", "კვადრატულ მეტრზე"),
    ("ლ", "ლიტრზე"),
    ("ც", "ცალზე"),
];

fn ka_money_per(t: String, c: &mut Ctx) -> String {
    let cur = ka_cur_rx();
    let mut keys: Vec<&str> = KA_PER.iter().map(|x| x.0).collect();
    keys.sort_by_key(|k| std::cmp::Reverse(k.chars().count()));
    let keys = keys.iter().map(|k| re_escape(k)).collect::<Vec<_>>().join("|");
    let p = format!(
        r"(?<![\w.,])(?:{cur}{SP}?((?:{KA_AMT})(?:[.,]\d+)?)|((?:{KA_AMT})(?:[.,]\d+)?){SP}?{cur})/({keys}|[ა-ჰ]+)(?![\w.])"
    );
    c.sub(&rx(&p), &t, |m| {
        let said = words(&m[0], "ka");
        if !said.contains('/') && !search(r"[0-9$€£₾₽₺֏₼]", &said) {
            return None;
        }
        let unit = g(m, 5);
        let per = match KA_PER.iter().find(|x| x.0 == unit) {
            Some(x) => x.1.to_string(),
            None if dative_word(unit) => unit.to_string(),
            None => glue(unit, "ზე")?,
        };
        // the sign after the amount: ₾5 კაცზე would have the number read on its own before a dative noun
        let amount = if g(m, 2).is_empty() { g(m, 3) } else { g(m, 2) };
        let sign = if g(m, 1).is_empty() { g(m, 4) } else { g(m, 1) };
        Some(format!("{amount} {sign} {per}"))
    })
}

fn ka_half(t: String, c: &mut Ctx) -> String {
    let mixed = |m: &fancy_regex::Captures<'_, str>| Some(format!("{}ნახევარი", trunc(&words(g(m, 1), "ka"))));
    let t = c.sub(&rx(&[r"(?<![\w.,/])(\d+)(?:", SP, r"+1/2|", SP, r"*½)(?![\d/])"].concat()), &t, mixed);
    let t = c.sub(&rx(&[r"(?<![\w.,])(\d+),5(?=", SP, r"+(?:მილიონ|მილიარდ|ათას)[ა-ჰ]*)"].concat()), &t, mixed);
    c.sub_tpl(&rx(&[r"(?<![\w.,/])(?:1/2|½)(?![\d/])(?=", SP, r"+[ა-ჰ])"].concat()), &t, "ნახევარი")
}

fn ka_money_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,])([$€£₾])(\d+(?:[.,]\d{1,2})?)[-–]([ა-ჰ]+)(?![\w-])"), &t, |m| {
        let suf = g(m, 3);
        if suf == "მა" {
            return None;
        }
        let r = words(&format!("{}{}", g(m, 1), g(m, 2)), "ka");
        let ws: Vec<&str> = r.split(' ').collect();
        let last = if ws.len() >= 2 { glue(ws[ws.len() - 1], suf) } else { None }?;
        let mut head: Vec<String> = ws[..ws.len() - 1].iter().map(|w| w.to_string()).collect();
        if TRUNC_SUFFIX.contains(&suf) {
            let n = head.len();
            head[n - 1] = trunc(&head[n - 1]).to_string();
        }
        head.push(last);
        Some(head.join(" "))
    })
}

fn ka_time_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:])(\d{1,2}):(\d{2})[-–](ია|ა|ზე|მდე)(?![\w-])"), &t, |m| {
        let (h, mm, suf) = (py_int(g(m, 1)), py_int(g(m, 2)), g(m, 3));
        if h > 23 || mm > 59 {
            return None;
        }
        let (hw, mw) = (words(&h.to_string(), "ka"), words(&mm.to_string(), "ka"));
        if matches!(suf, "ია" | "ა") {
            return Some(if mm == 0 {
                format!("{hw} საათია")
            } else {
                format!("{hw} საათი და {mw} წუთია")
            });
        }
        if mm == 0 {
            return Some(format!("{} {}", trunc(&hw), glue("საათი", suf)?));
        }
        Some(format!("{} საათსა და {} {}", trunc(&hw), trunc(&mw), glue("წუთი", suf)?))
    })
}

fn ka_suffix_merge(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/$€£₾-])(\d{1,3}(?:[ \u00a0]\d{3})+|\d+)[-–](ი[ა-ჰ]*)(?![\w-])"), &t, |m| {
        let r = words(g(m, 1), "ka");
        let stem = r.strip_suffix('ი')?;
        Some(format!("{stem}{}", g(m, 2)))
    })
}

fn ka_serial_suffix(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(r"(?<![\w-])([A-Za-z]+)-(\d+)-(ის|ში|ზე|ით|მა|ს|დან|მდე|თვის|ად|ია|ა)(?![\w-])"),
        &t,
        |m| {
            let r = words(g(m, 2), "ka");
            if r.contains(' ') || !full(r"[ა-ჰ]+", &r) {
                return None;
            }
            Some(format!("{} {}", g(m, 1), glue(&r, g(m, 3))?))
        },
    )
}

const MONTH: &str = r"(?:იანვ|თებერვ|მარტ|აპრილ|მაის|ივნის|ივლის|აგვისტო|სექტემბ|ოქტომბ|ნოემბ|დეკემბ)[ა-ჰ]*";

fn ka_day_one(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&[r"(?<![\w.,:/-])1(", SP, r"+)(", MONTH, r")(?![\w])"].concat()), &t, |m| {
        let month = g(m, 2);
        Some(format!("{}{}{month}", if dative_word(month) { "პირველ" } else { "პირველი" }, g(m, 1)))
    })
}

fn ka_year_abbrev(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&[r"(?<![\w.,:/-])(\d{3,4})(", SP, r"+)წ\."].concat()), &t, |m| {
        let nxt = &t[m.get(0).expect("group 0").end()..];
        if matches_at_start(&[SP, r"*\d"].concat(), nxt) {
            return None;
        }
        let dot = if matches_at_start(&[SP, r"*(?:$|\n)"].concat(), nxt) { "." } else { "" };
        Some(format!("{}{}წელს{dot}", trunc(&words(g(m, 1), "ka")), g(m, 2)))
    })
}

fn ka_range(t: String, c: &mut Ctx) -> String {
    let pat = [r"(?<![\w.,:/-])(\d{1,3})[-–](\d{1,3})(?![\d.,:/-])(", SP, r"+)([ა-ჰ]+)(?![\w-])"].concat();
    c.sub(&rx(&pat), &t, |m| {
        let (a, b, sp, noun) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        if py_int(a) >= py_int(b) || search(r"ებ[ა-ჰ]*$", noun) || VERBS.contains(&noun) {
            return None;
        }
        let (ra, rb) = (words(a, "ka"), words(b, "ka"));
        let (ra, rb) = if dative_word(noun) { (trunc(&ra), trunc(&rb)) } else { (ra.as_str(), rb.as_str()) };
        Some(format!("{ra}-{rb}{sp}{noun}"))
    })
}

const DUR_RANK: &[(&str, u8)] = &[("სთ", 0), ("წთ", 1), ("წმ", 2)];

fn ka_duration_and(t: String, c: &mut Ctx) -> String {
    let pat =
        [r"(?<![\w.,])(\d+", SP, r"?(სთ|წთ)\.?)(", SP, r"+)(\d+", SP, r"?(წთ|წმ)\.?)(?![\w])(?!", SP, r"*\d)"].concat();
    c.sub(&rx(&pat), &t, |m| {
        let rank = |u: &str| DUR_RANK.iter().find(|(k, _)| *k == u).map(|(_, r)| *r);
        if rank(g(m, 2))? >= rank(g(m, 5))? {
            return None;
        }
        Some(format!("{}{}და {}", g(m, 1), g(m, 3), g(m, 4)))
    })
}

fn ka_case_trunc(t: String, c: &mut Ctx) -> String {
    let pat = [
        r"(?<![\w.,:/-])(?:",
        NUM,
        r"|([ა-ჰ]*ნახევარი))((?:",
        SP,
        r"+(?:მილიონი|მილიარდი|ათასი))?)(",
        SP,
        r"+)([ა-ჰ]+)(?![\w-])",
    ]
    .concat();
    c.sub(&rx(&pat), &t, |m| {
        let noun = g(m, 5);
        if !dative_word(noun) {
            return None;
        }
        let r = if m.get(1).is_some() { words(g(m, 1), "ka") } else { g(m, 2).to_string() };
        if !r.ends_with('ი') && g(m, 3).is_empty() {
            return None;
        }
        let mut new = trunc(&r).to_string();
        for w in g(m, 3).split_whitespace() {
            new.push(' ');
            new.push_str(trunc(w));
        }
        Some(format!("{new}{}{noun}", g(m, 4)))
    })
}

fn dative_number(r: &str) -> String {
    format!("{}ს", trunc(r))
}

fn ka_equals(t: String, c: &mut Ctx) -> String {
    // a minus between numbers before that =: the grammar reads it (მინუს) only while the = is still there
    let minus =
        [r"(?<=\d)", SP, r"*[-−]", SP, r"*(?=\d[^=\n]*(?<![=<>!])=", SP, r"*\d+(?![\d.,:/])(?!", SP, r"*[-+*/×÷=<>]))"]
            .concat();
    let t = c.sub(&rx(&minus), &t, |_| Some(" მინუს ".to_string()));
    let pat = [r"(?<![=<>!])=", SP, r"*(\d+)(?![\d.,:/])(?!", SP, r"*[-+*/×÷=<>])"].concat();
    c.sub(&rx(&pat), &t, |m| Some(format!(" უდრის {}", dative_number(&words(g(m, 1), "ka")))))
}

const CASE_END: &str = r"(?:ში|ის|ით|ს|ზე|დან|მდე|თან|ად|მა|თვის)$";

fn ka_street_city(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&[r"(?<=[ა-ჰ]ის", SP, r")(ქ|გამზ|შეს)\."].concat()), &t, |m| {
        Some(
            match g(m, 1) {
                "ქ" => "ქუჩა",
                "გამზ" => "გამზირი",
                _ => "შესახვევი",
            }
            .to_string(),
        )
    });
    c.sub(&rx(&[r"(?<![\w.])ქ\.(", SP, r"*)([ა-ჰ]+)(?![\w-])"].concat()), &t, |m| {
        let w = g(m, 2);
        let sp = if g(m, 1).is_empty() { " " } else { g(m, 1) };
        Some(format!("{}{sp}{w}", if search(CASE_END, w) { "ქალაქ" } else { "ქალაქი" }))
    })
}
