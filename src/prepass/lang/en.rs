//! 'en' rules: the port of the workbench's `langrules/en.py` (ids `en.*`). They run before the pre-pass's own
//! English rules (en.footnote … en.acronym-plural), right after the character rules.

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, full, g, matches_at_start, py_int, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("en.score", en_score),
    ("en.money-scale-t", en_money_scale_t),
    ("en.spaced-groups", en_spaced_groups),
    ("en.money-code", en_money_code),
    ("en.money-range", en_money_range),
    ("en.money-sign-after", en_money_sign_after),
    ("en.money-minus", en_money_minus),
    ("en.money-quadrillion", en_money_quadrillion),
    ("en.money-per", en_money_per),
    ("en.rupee", en_rupee),
    ("en.yen-decimals", en_yen_decimals),
    ("en.tonne", en_tonne),
    ("en.count", en_count),
];

const SCORE_CUES: &str = r"(?i)\b(?:beat|beats|beating|won|win|wins|winning|lost|lose|loses|losing|defeated|defeats|defeating|edged|edges|edging|routed|thrashed|trounced|crushed|downed|drew|tied|ties|led|leads|leading|trailed|trails|trailing|scored?|scores|final|victory|defeat|loss|win)\b";
/// prepass.py's DETERMINERS (src/prepass/rules.rs).
const DETERMINERS: &str = "(?:a|an|the|this|that|each|every|one|its|his|her|their|our|my|your|whose)";

fn en_score(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,/:\-–])(\d{1,3})[-–](\d{1,3})(?![\w\-–]|[.,:]\d)"), &t, |m| {
        let w = m.get(0).expect("group 0");
        if !search(&format!(r"{SCORE_CUES}(?:\s+\S+){{0,3}}\s+$"), chars_before(&t, w.start(), 60)) {
            return None;
        }
        if matches_at_start(r"\s*=", &t[w.end()..]) {
            return None;
        }
        Some(format!("{} to {}", g(m, 1), g(m, 2)))
    })
}

fn en_money_scale_t(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\w.])([$€£¥]\d+(?:,\d{3})*(?:\.\d+)?) ?(?:T|tn|trn)(?![\w-])"), &t, r"\1 trillion")
}

/// code, symbol, plural name, singular name; a symbol alone means the grammar's own reading of the symbol is right.
const CODES: &[(&str, &str, &str, &str)] = &[
    ("USD", "$", "US dollars", "US dollar"),
    ("EUR", "€", "", ""),
    ("GBP", "£", "", ""),
    ("JPY", "¥", "", ""),
    ("INR", "₹", "", ""),
    ("CAD", "$", "Canadian dollars", "Canadian dollar"),
    ("AUD", "$", "Australian dollars", "Australian dollar"),
    ("NZD", "$", "New Zealand dollars", "New Zealand dollar"),
    ("HKD", "$", "Hong Kong dollars", "Hong Kong dollar"),
    ("SGD", "$", "Singapore dollars", "Singapore dollar"),
    ("CHF", "", "Swiss francs", "Swiss franc"),
    ("MXN", "", "Mexican pesos", "Mexican peso"),
    ("CNY", "", "yuan", "yuan"),
    ("RMB", "", "yuan", "yuan"),
    ("SEK", "", "Swedish kronor", "Swedish krona"),
    ("NOK", "", "Norwegian kroner", "Norwegian krone"),
    ("DKK", "", "Danish kroner", "Danish krone"),
    ("ZAR", "", "South African rand", "South African rand"),
    ("BRL", "", "Brazilian reais", "Brazilian real"),
    ("KRW", "", "South Korean won", "South Korean won"),
    ("RUB", "", "Russian rubles", "Russian ruble"),
    ("PLN", "", "Polish zlotys", "Polish zloty"),
];
const CODE_RX: &str = "USD|EUR|GBP|JPY|INR|CAD|AUD|NZD|HKD|SGD|CHF|MXN|CNY|RMB|SEK|NOK|DKK|ZAR|BRL|KRW|RUB|PLN";
const AMOUNT: &str = r"\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?";

fn say_code(t: &str, start: usize, code: &str, amount: &str) -> Option<String> {
    let &(_, sym, pl, sg) = CODES.iter().find(|row| row.0 == code)?;
    let adjective = search(&format!(r"(?i)\b{DETERMINERS}\s+$"), &t[..start]);
    if !pl.is_empty() && !amount.contains('.') && !adjective {
        return Some(format!("{} {}", count_form(amount), if amount == "1" { sg } else { pl }));
    }
    if sym.is_empty() { None } else { Some(format!("{sym}{amount}")) }
}

fn code_range(code: &str, a: &str, b: &str) -> Option<String> {
    let &(_, sym, pl, _) = CODES.iter().find(|row| row.0 == code)?;
    if !pl.is_empty() && !a.contains('.') && !b.contains('.') {
        return Some(format!("{} to {} {pl}", count_form(a), count_form(b)));
    }
    if sym.is_empty() { None } else { Some(format!("{sym}{a}-{b}")) } // €5-10: en.money-range reads it
}

fn en_spaced_groups(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(r"(?<![\w.,+/])(?<![\w.,+/]-)(-?)([1-9]\d{0,2}(?:[ \u00a0\u202f]\d{3})+)(?![\d]|[.,]\d|[ \u00a0\u202f]\d)"),
        &t,
        |m| {
            let n = m.get(2).expect("group 2");
            let groups: Vec<&str> = n.as_str().split([' ', '\u{a0}', '\u{202f}']).collect();
            let money = search(&format!(r"(?:[$€£¥₹]|\b(?:{CODE_RX}))[ \t]?$"), &t[..n.start()])
                || matches_at_start(&format!(r"[ \t]?(?:[$€£¥₹]|(?:{CODE_RX})(?!\w))"), &t[m.get(0)?.end()..]);
            if !money && (groups.len() == 2 || (groups.len() == 3 && !groups[1..].contains(&"000"))) {
                return None;
            }
            Some(format!("{}{}", g(m, 1), groups.join(",")))
        },
    )
}

fn en_money_code(t: String, c: &mut Ctx) -> String {
    // ranges: USD 5-10, CHF 5~10, 5~10 USD
    let t = c.sub(
        &rx(&format!(r"(?<![\w.$€£¥])({CODE_RX}) ?({AMOUNT})[ \t]?[-–~][ \t]?({AMOUNT})(?!\w|[.,]\d)")),
        &t,
        |m| code_range(g(m, 1), g(m, 2), g(m, 3)),
    );
    let t = c.sub(
        &rx(&format!(r"(?<![\w.,$€£¥-])({AMOUNT})[ \t]?[-–~][ \t]?({AMOUNT}) ?({CODE_RX})(?!\w)")),
        &t,
        |m| code_range(g(m, 3), g(m, 1), g(m, 2)),
    );
    let t = c.sub(&rx(&format!(r"(?<![\w.$€£¥])({CODE_RX}) ?({AMOUNT})(?!\w|[.,]\d)")), &t, |m| {
        say_code(&t, m.get(0).expect("group 0").start(), g(m, 1), g(m, 2))
    });
    c.sub(&rx(&format!(r"(?<![\w.,$€£¥])({AMOUNT}) ?({CODE_RX})(?!\w)")), &t, |m| {
        say_code(&t, m.get(0).expect("group 0").start(), g(m, 2), g(m, 1))
    })
}

// ------------------------------------------------------------------------------------------------- money signs

const SIGN_RX: &str = "[$€£¥₹]";
const MONEY_AMT: &str = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?";
/// A scale after an amount: a word with an optional space, or an abbreviation glued to it ($5-10M, $5bn).
const SCALE_RX: &str = r"(?:[ \t]?(thousand|million|billion|trillion|lakh|crore)|(k|K|mn|m|M|bn|b|B))";

fn singular(sign: &str) -> &'static str {
    match sign {
        "$" => "dollar",
        "€" => "euro",
        "£" => "pound",
        "¥" => "yen",
        _ => "rupee",
    }
}

fn plural(sign: &str) -> &'static str {
    match sign {
        "$" => "dollars",
        "€" => "euros",
        "£" => "pounds",
        "¥" => "yen",
        _ => "rupees",
    }
}

fn scale_abbr(s: &str) -> &'static str {
    match s {
        "k" | "K" => "thousand",
        "mn" | "m" | "M" => "million",
        "bn" | "b" | "B" => "billion",
        _ => "",
    }
}

/// The text of the line before byte offset `i`.
fn line_head(t: &str, i: usize) -> &str {
    &t[t[..i].rfind('\n').map_or(0, |p| p + 1)..i]
}

/// A TeX math $ is open before this point of the line: an odd number of $ that are neither a sign before a digit
/// ($5) nor after one (50$).
fn tex_open(head: &str) -> bool {
    let r = rx(r"(?<!\d)\$(?!\d)");
    let mut n = 0;
    let mut pos = 0;
    while let Ok(Some(m)) = r.captures_from_pos(head, pos) {
        let w = m.get(0).expect("group 0");
        n += 1;
        pos = w.end();
    }
    n % 2 == 1
}

/// The rest of the line from byte offset `i`.
fn line_tail(t: &str, i: usize) -> &str {
    t[i..].split('\n').next().unwrap_or("")
}

fn amount_value(s: &str) -> f64 {
    // Python's float() reads any decimal digits (٥ is 5)
    let ascii: String = s
        .chars()
        .filter(|&ch| ch != ',')
        .map(|ch| {
            if crate::text::is_py_digit(ch) && !ch.is_ascii_digit() {
                char::from_digit((ch as u32 - crate::text::nd_range_start(ch).unwrap_or(ch as u32)) % 10, 10)
                    .unwrap_or('0')
            } else {
                ch
            }
        })
        .collect();
    ascii.parse().unwrap_or(0.0)
}

#[allow(clippy::too_many_arguments)]
fn range_say(t: &str, start: usize, end: usize, sign: &str, a: &str, b: &str, sc: &str, both: bool) -> String {
    let mut pl = plural(sign);
    if let Some(nxt) = caps(r"^(?:[ \t]+([a-z][a-z-]+))", &t[end..])
        && !has(TONNE_NOT_NOUN, g(&nxt, 1))
        && !has(ADJ_STOP, g(&nxt, 1))
        && search(r"(?i)\b(?:a|an|the|this|that|each|every)[ \t]+$", &t[..start])
    {
        pl = singular(sign); // a $5-10 fee → a five to ten dollar fee
    }
    if !sc.is_empty() {
        return format!("{a} to {b} {sc} {pl}");
    }
    if a.contains('.') || b.contains('.') || both {
        return format!("{sign}{a} to {sign}{b}");
    }
    format!("{} to {} {pl}", count_form(a), count_form(b))
}

fn en_money_range(t: String, c: &mut Ctx) -> String {
    let equation = |t: &str, end: usize| search(r"=|\bequals\b", line_tail(t, end));
    let ok = |t: &str, end: usize, a: &str, b: &str, sep: &str, spaced: bool, both: bool| {
        if amount_value(a) >= amount_value(b) || equation(t, end) {
            return false;
        }
        !(sep == "-" && spaced && !both)
    };
    let t = c.sub(
        &rx(&format!(
            r"(?<![\w.,$€£¥₹/@~〜–-])({SIGN_RX})({MONEY_AMT})([ \t]*)([-–~〜])([ \t]*)({SIGN_RX})?({MONEY_AMT}){SCALE_RX}?(?![\w$€£¥₹%]|[.,]\d|[ \t]?[-–~〜][ \t]?\d)"
        )),
        &t,
        |m| {
            let end = m.get(0).expect("group 0").end();
            let (sign, a, sp1, sep, sp2, sign2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6), g(m, 7));
            let sc = if g(m, 8).is_empty() { scale_abbr(g(m, 9)) } else { g(m, 8) };
            if !sign2.is_empty() && sign2 != sign {
                return None;
            }
            let spaced = !sp1.is_empty() || !sp2.is_empty();
            if sep == "-"
                && spaced
                && !sign2.is_empty()
                && sc.is_empty()
                && (equation(&t, end) || amount_value(a) >= amount_value(b))
            {
                return Some(format!("{sign}{a} minus {sign}{b}")); // $10 - $5 is $5, $5 - $3 = $2: a subtraction
            }
            if !ok(&t, end, a, b, sep, spaced, !sign2.is_empty()) {
                return None;
            }
            let w = m.get(0).expect("group 0");
            Some(range_say(&t, w.start(), w.end(), sign, a, b, sc, !sign2.is_empty()))
        },
    );
    c.sub(
        &rx(&format!(
            r"(?<![\w.,$€£¥₹/@~〜–-])({MONEY_AMT})([ \t]*)([-–~〜])([ \t]*)({MONEY_AMT}){SCALE_RX}?[ \t]?({SIGN_RX})(?![\w$€£¥₹])"
        )),
        &t,
        |m| {
            let w = m.get(0).expect("group 0");
            let (a, sp1, sep, sp2, b, sign) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 8));
            if sign == "$" && tex_open(line_head(&t, w.start())) {
                return None;
            }
            if !ok(&t, w.end(), a, b, sep, !sp1.is_empty() || !sp2.is_empty(), false) {
                return None;
            }
            let sc = if g(m, 6).is_empty() { scale_abbr(g(m, 7)) } else { g(m, 6) };
            Some(range_say(&t, w.start(), w.end(), sign, a, b, sc, false))
        },
    )
}

/// Words en.money-adj takes for a noun after “a/the/that $5” though they are not one.
const ADJ_STOP: &str = "not no very really instead though either anymore even";

fn en_money_sign_after(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&format!(r"(?<![\w.,+$€£¥₹~〜–-])(-?)({MONEY_AMT})([ \t]?)({SIGN_RX})(?![\w$€£¥₹]|[ \t]?\d)")),
        &t,
        |m| {
            let w = m.get(0).expect("group 0");
            if g(m, 4) == "$" && tex_open(line_head(&t, w.start())) {
                return None;
            }
            if let Some(nxt) = caps(r"^(?:[ \t]+([a-z]+))", &t[w.end()..])
                && has(ADJ_STOP, g(&nxt, 1))
                && search(&format!(r"(?i)\b{DETERMINERS}[ \t]+$"), &t[..w.start()])
            {
                return None;
            }
            Some(format!("{}{}{}", g(m, 1), g(m, 4), g(m, 2)))
        },
    )
}

fn en_money_minus(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,$€£¥₹)\]%-])-(?={SIGN_RX}\d)")), &t, "minus ");
    c.sub_tpl(&rx(&format!(r"(?<![\w.,$€£¥₹-])({SIGN_RX})-(?=\d)")), &t, r"minus \1")
}

fn en_money_quadrillion(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.,])({SIGN_RX})(\d{{1,3}}(?:,\d{{3}}){{5,}})(?![\d,]|\.\d)")), &t, |m| {
        Some(format!("{} {}", g(m, 2), plural(g(m, 1))))
    })
}

const CUR_WORDS: &str = r"(?:dollars?|euros?|pounds?|yen|yuan|rupees?|francs?|pesos?|kronor|krona|kroner|krone|rand|reais|real|won|rubles?|zlotys?)";

fn en_money_per(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&format!(
            r"(?<![\w.,])((?:{SIGN_RX})(?:{MONEY_AMT})(?:[ \t]?(?:thousand|million|billion|trillion)|k|K|mn|m|M|bn|b|B)?|(?:{MONEY_AMT})[ \t](?:[A-Z][A-Za-z]*[ \t]){{0,2}}{CUR_WORDS})((?:/[A-Za-z]+)+)(?![\w/])"
        )),
        &t,
        |m| {
            let said = words(&format!("{}{}", g(m, 1), g(m, 2)), "en");
            if !said.contains("slash") && !said.contains('/') {
                return None;
            }
            Some(format!("{}{}", g(m, 1), g(m, 2).replace('/', " per ")))
        },
    )
}

fn rupee_scale(s: &str) -> &str {
    match s {
        "lakhs" => "lakh",
        "crores" | "cr" | "Cr" => "crore",
        "k" | "K" => "thousand",
        "mn" | "m" | "M" => "million",
        "bn" | "b" | "B" => "billion",
        _ => s,
    }
}

fn en_rupee(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<![\w.$€£¥])(?:₹[ \t]+|Rs\.?[ \t]?)(?=\d)"), &t, "₹");
    let t = c.sub(
        &rx(&format!(
            r"(?<![\w.])₹({MONEY_AMT})(?:[ \t]?(thousand|million|billion|trillion|lakhs?|crores?)|(k|K|mn|m|M|bn|b|B|cr|Cr))(?!\w)"
        )),
        &t,
        |m| {
            let sc = if g(m, 2).is_empty() { g(m, 3) } else { g(m, 2) };
            Some(format!("{} {} rupees", g(m, 1), rupee_scale(sc)))
        },
    );
    c.sub(&rx(r"(?<![\w.])₹(\d{1,3}(?:,\d{3})+|\d+)\.(\d{1,2})(?!\d|[.,]\d)"), &t, |m| {
        let whole = g(m, 1);
        let p = py_int(&format!("{}0", g(m, 2)).chars().take(2).collect::<String>());
        let n = py_int(&whole.replace(',', ""));
        let cents = format!("{p} {}", if p == 1 { "paisa" } else { "paise" });
        if n == 0 {
            return Some(cents);
        }
        let rupees = format!("{whole} {}", if n == 1 { "rupee" } else { "rupees" });
        Some(if p == 0 { rupees } else { format!("{rupees} {cents}") })
    })
}

fn en_yen_decimals(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(
        &rx(r"(?<![\w.])¥(\d{1,3}(?:,\d{3})+|\d+)\.(\d+)(?!\d|[.,]\d|[ \t]?(?:thousand|million|billion|trillion)(?!\w)|(?:k|K|mn|m|M|bn|b|B|T|tn|trn)(?!\w))"),
        &t,
        r"\1.\2 yen",
    )
}

/// A noun after “a 40 t …” that is not one: the unit stays plural (tonnes).
const TONNE_NOT_NOUN: &str = "of per and or to in on at for from by with a an the is was are were each every";
/// t/ha, t/yr … → tonnes per hectare, per year.
const TONNE_PER: &[(&str, &str)] = &[
    ("hectare", "hectare"),
    ("ha", "hectare"),
    ("year", "year"),
    ("yr", "year"),
    ("month", "month"),
    ("week", "week"),
    ("day", "day"),
    ("d", "day"),
    ("hour", "hour"),
    ("hr", "hour"),
    ("h", "hour"),
];

fn en_tonne(t: String, c: &mut Ctx) -> String {
    let per_rx = TONNE_PER.iter().map(|p| p.0).collect::<Vec<_>>().join("|");
    c.sub(
        &rx(&format!(
            r"(?<![\w.,=+*/^×-])(\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?)([ \t]?)t(?:/({per_rx}))?(?![\w'’/-]|\.\w)"
        )),
        &t,
        |m| {
            let w = m.get(0).expect("group 0");
            let (n, sp, per) = (g(m, 1), g(m, 2), g(m, 3));
            let head = line_head(&t, w.start());
            let line = format!("{head}{}", line_tail(&t, w.end()));
            if search(r"=|\bequals\b", &line) || search(r"[-+*/×^÷][ \t]*$", head) {
                return None;
            }
            let rest = &t[w.end()..];
            let cue = !per.is_empty() || matches_at_start(r"[ \t]*(?:CO2|CO₂|per\b)", rest);
            if full(r"\d", n) && !cue {
                return None;
            }
            if sp.is_empty() && !cue && !full(r"\d{1,3}(?:,\d{3})+|\d+\.\d+|\d{2,}", n) {
                return None;
            }
            let single = n == "1"
                || (search(r"(?i)\b(?:a|an|the|this|that|one|each|every)[ \t]+$", &t[..w.start()])
                    && caps(r"^(?:[ \t]+([a-z][a-z-]+))", rest).is_some_and(|x| !has(TONNE_NOT_NOUN, g(&x, 1))));
            let mut out = format!("{n} {}", if single { "tonne" } else { "tonnes" });
            if let Some(&(_, word)) = TONNE_PER.iter().find(|p| p.0 == per) {
                out.push_str(" per ");
                out.push_str(word);
            }
            Some(out)
        },
    )
}

// ------------------------------------------------------------------------------------------------- en.count
// The grammar reads every bare 1010–2999 as a year (1234 → twelve thirty four, 1101 → eleven oh one, 2024 → twenty
// twenty four, 1500 → fifteen hundred), except the round thousands and 1001–1009 / 2001–2009 (one thousand one), and
// reads 1,234 as a cardinal. en.count writes the comma when the number counts something.

/// 1500 people: true keeps the grammar's round-hundreds reading (fifteen hundred people); false writes 1,500.
const KEEP_ROUND_HUNDREDS: bool = true;
/// A cue before 2101–2999 does not make it a year (in 2345 cases).
const CUE_MAX: u32 = 2100;
/// A number that looks like a modern year counts only before a known count noun (1990 people, 2024 votes).
const MODERN: (u32, u32) = (1600, 2099);
const WORD: &str = r"[A-Za-zµμΩ][A-Za-zµμΩ]*(?:[-'’][A-Za-z]+)*";
// The word tables of langrules/en.py (sets there, whitespace-separated words here; only membership is used).
const ABS_CUES: &str = "apr april aug august autumn circa dec december early fall feb february fiscal jan january jul july jun june \
    late mar march may mid nov november oct october sep sept september spring summer winter year";
const STRONG_CUES: &str = "after before between during in since through throughout til till until";
const DET_CUES: &str = "her his its my our the their whose your";
const WEAK_CUES: &str = "about above annual approx approximately around at below best by current favorite favourite final for \
    forthcoming from last latest new of official on original past per previous recent roughly same top under \
    upcoming versus vs worst";
const LABELS: &str = "appendix apt area art article batch box bus ch channel chapter code column district ep episode exit fig \
    figure flight form gate grade highway hwy id issue item level line lot model no nos number order p page \
    pages para paragraph part phase pin platform pp precinct room rooms route row rule seat sec section serial \
    stage step suite table terminal ticket track type unit ver verse version vol volume ward zip";
const CAP_OK: &str = "about additionally all almost already also altogether among and another approximately around as barely but \
    even exactly fewer for here if including just less more nearly now only over overall plus roughly so some \
    still than then there these those to today up when where while with yesterday yet";
const CONTRACTIONS: &str = "he's here's here’s he’s how's how’s it's it’s let's let’s she's she’s that's that’s there's there’s what's \
    what’s where's where’s who's who’s";
const IRREGULAR: &str = "aircraft alumni bacteria cacti cattle children crew criteria deer feet fish fungi geese larvae lice \
    livestock men mice nuclei offspring oxen people personnel phenomena police sheep spacecraft staff stimuli \
    swine teeth vertebrae women";
const MEASURE: &str = "acres amps barrels bits bytes calories carats centuries days decades degrees feet foot gallons gigabytes \
    grams hectares hours inches joules kilobytes kilocalories kilograms kilometers kilometres kilos kilowatts \
    lbs leagues light-years liters litres megabytes megawatts meters metres miles millennia milligrams minutes \
    months nights ounces pounds seconds terabytes tonnes tons volts watts weeks yards years";
const CURRENCY: &str = "bucks cents dollars euros francs pence pesos roubles rubles rupees yen yuan";
const UNIT_ABBR: &str = "GB GW Gbps HRS KB MB MPa MW MΩ TB TW Wh atm bps cL cal cl dB dL dpi fps gal hPa ha hr hrs kB kHz kJ kPa kV \
    kWh kbps kcal kmh kph kΩ mA mAh mL mV mW mins ml mm mmol mos ms nm ppb ppm psi px qt secs wk wks yr yrs µm Ω \
    μm";
const HOURS: &str = "HRS hours hr hrs";
const HOUR_COUNT_BEFORE: &str =
    "almost another extra flew least logged nearly over roughly some spent than total worked";
const HOUR_COUNT_AFTER: &str = "ago combined flown later left logged long of per spent total worked";
const COUNT_NOUNS: &str = "adults animals answers apartments applicants applications attendees beds birds births boats bombs buildings \
    businesses cases casualties cats cells cities citizens clicks comments companies computers copies cows \
    customers deaths devices dogs downloads emails employees entries families fans files firms followers \
    galaxies guns homes horses households houses images immigrants individuals infections inhabitants injuries \
    items jobs languages letters lines locals machines meals members messages migrants missiles objects officers \
    pages participants passengers patients persons pieces planets plants posts prisoners products pupils \
    questions refugees residents respondents rockets rooms samples schools seats ships shops signatures soldiers \
    species specimens spectators staffers stars steps stores students subscribers tanks teachers tickets times \
    tourists towns trees troops users victims views villages visitors volunteers voters votes weapons words \
    workers";
const NOT_PLURAL: &str = "aesthetics afterwards alias always athletics atlas backwards besides bias canvas chaos christmas cosmos does \
    downwards economics ethics ethos forwards gas genetics gymnastics has hers inwards kudos linguistics \
    logistics mathematics news nowadays onwards ours outwards pathos perhaps physics politics regardless \
    sometimes theirs thus towards unless upwards was whereas yes yours";
const VERBS: &str = "allows appears becomes begins brings celebrates closes comes contains continues describes ends establishes \
    feels follows gives goes heralds includes indicates introduces kicks lacks looks makes marks means mentions \
    opens promises proves provides puts remains represents requires says seems sees starts suggests takes ushers \
    witnesses wraps";
const VERB_NEXT: &str = "a an another everybody everyone everything her him his it its me my nothing our something that the their \
    them these this those us your";
const RATE_START: &str = "a an each every that this";
const RATE_WORDS: &str = "capita century day decade game head hour match minute month night person piece quarter season second \
    semester session time week year";
const FINITE: &str = "are became decreased doubled dropped fell grew had have increased is rose was were";
const MODIFIERS: &str = "active additional adult armed business calendar civilian confirmed cubic daily dead different displaced \
    distinct elderly eligible employed enrolled estimated extra female fewer foreign full-time further homeless \
    individual infected injured innocent international large licensed light living local male metric missing \
    more nautical new other paid part-time qualified recorded registered reported separate skilled small square \
    total trained unemployed unique unpaid working young";
const NOT_MODIFIER: &str = "a about across after again against ago already also although am among an and are as at autumn be became \
    because been before began behind being between beyond billion bought brought budget built but by came can \
    census could cut did do does during eight election even fall fell felt fiscal five for found four from gave \
    general got grew had has have he held her here him his hit hundred i if in into is it its just kept knew \
    later led left let lost made may me met might million must my national near nine nor not now of olympic on \
    one only onto or our over per presidential put ran rose saw season sent set seven shall she should showed \
    since six so sold spent spring still summer tax ten than that the their them then there these they this \
    those though thousand three through to told too took toward towards two under until upon us very via was we \
    went were what when where whereas which while who whom will winter with within without won world would yet \
    you your";
const OF_WORDS: &str = "all each them these those us which whom you";
const INFLATION: &str = "adjusted constant current in inflation-adjusted nominal real today's today’s";

/// `w in TABLE` for a whitespace-separated word table.
fn has(table: &str, w: &str) -> bool {
    table.split_ascii_whitespace().any(|x| x == w)
}

/// `re.search(pat, s)` with its captures.
fn caps<'t>(pat: &str, s: &'t str) -> Option<Captures<'t, str>> {
    rx(pat).captures(s).ok().flatten()
}

/// 1234 → 1,234 when the grammar would read the bare number as a year (the comma makes it a cardinal).
fn count_form(s: &str) -> String {
    if !full(r"[12][0-9]{3}", s) {
        return s.to_string();
    }
    let n: u32 = s.parse().expect("four ASCII digits");
    if n % 1000 < 10 || (KEEP_ROUND_HUNDREDS && n % 100 == 0) {
        return s.to_string();
    }
    format!("{},{}", &s[..1], &s[1..])
}

/// The word after the number: "currency", "measure", "count" (a plural noun), "plain" (an -s plural) or "".
fn count_kind(w: &str, modern: bool) -> &'static str {
    if w.is_empty() {
        return "";
    }
    if has(UNIT_ABBR, w) {
        return "measure";
    }
    if !full(r"[a-z]+(?:[-'’][a-z]+)*", w) {
        return ""; // capitalized: a name or a title (1990 Ford Mustang, 2012 Olympics)
    }
    let base = w.strip_suffix("'s").or_else(|| w.strip_suffix("’s")).unwrap_or(w);
    if has(CURRENCY, base) {
        return "currency";
    }
    if has(MEASURE, base) {
        return "measure";
    }
    if has(IRREGULAR, base) || has(COUNT_NOUNS, base) {
        return "count";
    }
    if modern
        || has(NOT_PLURAL, base)
        || base.chars().count() < 3
        || !base.ends_with('s')
        || base.ends_with("ss")
        || base.ends_with("us")
        || base.ends_with("is")
    {
        return "";
    }
    "plain"
}

fn count_modifier(w: &str, modern: bool) -> bool {
    if !full(r"[a-z]+(?:-[a-z]+)*", w) || has(NOT_MODIFIER, w) {
        return false;
    }
    if has(MODIFIERS, w) {
        return true;
    }
    !modern && (w.ends_with("ous") || !(w.ends_with('s') || w.ends_with("ed") || w.ends_with("ly")))
}

fn en_count(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,$£€¥₹#@/:+~'’‘\-–—])([12][0-9]{3})(?![\d%°'’\-–—/:_]|[.,]\d)"), &t, |m| {
        let w = m.get(0).expect("group 0");
        count_repl(&t, w.start(), w.end(), g(m, 1))
    })
}

fn count_repl(t: &str, start: usize, end: usize, s: &str) -> Option<String> {
    if count_form(s) == s {
        return None;
    }
    let n: u32 = s.parse().expect("four ASCII digits");
    let modern = MODERN.0 <= n && n <= MODERN.1;
    let before = &t[..start];
    let rest = &t[end..];
    if search(r"(?i)\bout of[ \t]+$", before) {
        return Some(count_form(s)); // 3 out of 1234
    }
    if search(r"(?i)\d[ \t]*(?:and|or|to|through|thru|until|till|&|[-–—])[ \t]*$", before) {
        return None; // a range or a list of numbers (1990 and 1991 elections, 1234 to 2345 people)
    }
    if search(
        r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[ \t]+\d{1,2}(?:st|nd|rd|th)?,?[ \t]*$",
        before,
    ) {
        return None; // May 5, 1990
    }
    let mw = caps(&format!(r"^(?:([ \t]*)({WORD})(?:[ \t]+({WORD}))?(?:[ \t]+({WORD}))?)"), rest)?;
    let (sp, w1, w2, w3) = (g(&mw, 1), g(&mw, 2), g(&mw, 3), g(&mw, 4));
    if sp.is_empty() && !has(UNIT_ABBR, w1) {
        return None; // 1990s, 1234th, 1990AD
    }
    let mut cue = "";
    let mut lp = String::new();
    if let Some(pm) = caps(r"(?:^|[^\w'’.])([A-Za-z][A-Za-z'’-]*\.?)[ \t]+$", before) {
        let p = g(&pm, 1);
        lp = p.to_lowercase();
        let bare = lp.trim_end_matches('.');
        if has(LABELS, bare) || has(ABS_CUES, bare) || ["c.", "ca.", "cca."].contains(&lp.as_str()) {
            return None;
        }
        if has(STRONG_CUES, &lp) {
            cue = "strong";
        } else if has(DET_CUES, &lp) || (!has(CONTRACTIONS, &lp) && search(r"[a-z](?:['’]s|s['’])$", &lp)) {
            cue = "det";
        } else if has(WEAK_CUES, bare) {
            cue = "weak";
        } else if p.as_bytes()[0].is_ascii_uppercase() && !has(CAP_OK, &lp) && !has(CONTRACTIONS, &lp) {
            return None;
        }
    }
    let lp = lp.as_str();
    let year_cue = ((cue == "strong" || cue == "det") && n <= CUE_MAX) || (cue == "weak" && modern);
    // what follows: a noun, a modifier and a noun, of them, out of
    let (mut kind, mut noun, mut nxt, mut via_mod) = (count_kind(w1, modern), w1, w2, false);
    if w1 == "m"
        && !sp.is_empty()
        && matches_at_start(
            r"[ \t]*m(?=\s*(?:$|[.,;:!?)]|\s(?:long|wide|tall|high|deep|away|apart|of|from|in|above|below|across|thick|to|by|and|or)\b))",
            rest,
        )
    {
        kind = "measure"; // 1234 m long (en.units: meters)
    }
    if kind.is_empty() {
        if (w1 == "of" && has(OF_WORDS, w2)) || (w1 == "out" && w2 == "of") {
            return if year_cue { None } else { Some(count_form(s)) };
        }
        if !count_modifier(w1, modern) {
            return None;
        }
        (kind, noun, nxt, via_mod) = (count_kind(w2, modern), w2, w3, true);
        if kind.is_empty() || has(UNIT_ABBR, w2) {
            return None;
        }
    }
    if has(HOURS, noun)
        && n <= 2359
        && n % 100 < 60
        && !(via_mod || has(HOUR_COUNT_BEFORE, lp) || has(HOUR_COUNT_AFTER, nxt))
    {
        return None; // at 1430 hours: military time (en.units)
    }
    if year_cue && (kind != "measure" || has(FINITE, nxt)) {
        return None; // In 1990 people moved; the 1990 elections; In 1886 hours were cut
    }
    if kind == "currency" && (has(INFLATION, lp) || (modern && search(r"\([ \t]*$", before))) {
        return None; // in 2010 dollars, constant 2015 dollars, (2015 dollars)
    }
    if (kind == "plain" || kind == "count") && !via_mod && has(VERBS, noun) {
        return None; // 2024 brings new rules
    }
    if kind == "plain" && !via_mod && has(VERB_NEXT, nxt) && !(has(RATE_START, nxt) && has(RATE_WORDS, w3)) {
        return None; // 1215 marks the end (but 1234 trials a day)
    }
    Some(count_form(s))
}
