//! 'ka' rules: the port of the workbench's `langrules/ka.py` (ids `ka.*`).
//!
//! Georgian attributive numbers drop their final -ი before a noun in the dative or with a dative-based postposition
//! (ხუთ წუთში, ას ლარად); a suffix glued to a number with a hyphen replaces the number's final -ი when it starts with
//! -ი (90-იან → ოთხმოცდაათიან). These rules write those forms, starting from the grammar's own reading of the number.

#[allow(unused_imports)]
use super::super::{Ctx, full, g, matches_at_start, py_int, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ka.ordinal-prefix", ka_ordinal_prefix),
    ("ka.roman-century", ka_roman_century),
    ("ka.scale-abbrev", ka_scale_abbrev),
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
    c.sub(&rx(r"(?<![\w.,:/$€£₾-])(\d+)[-–](ი[ა-ჰ]*)(?![\w-])"), &t, |m| {
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
