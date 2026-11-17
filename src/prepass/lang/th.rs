//! 'th' rules: the port of the workbench's `langrules/th.py` (ids `th.*`).
//!
//! The Thai grammar deletes every space (so phrase pauses vanish), reads chat laughter 555 as a number, leaves the
//! Thai time format 14.30 น. and some unit and place abbreviations unread, reads a score as a range and adds a second
//! วันที่ before a numeric date that already has one.

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, full, g, matches_at_start, py_int, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("th.groups", th_groups),
    ("th.money-range", th_money_range),
    ("th.money", th_money),
    ("th.per", th_per),
    ("th.space", th_space),
    ("th.abbrev", th_abbrev),
    ("th.units", th_units),
    ("th.time", th_time),
    ("th.date", th_date),
    ("th.score", th_score),
    ("th.half", th_half),
    ("th.laugh", th_laugh),
];

/// Thai letters, vowels, tone marks, ฯ and ๆ (the Thai digits ๐-๙ come after).
const THAI: &str = "ก-๏";
/// A space kept from the grammar.
const MARK: &str = "\u{e000} \u{e001}";

// ------------------------------------------------------------------------------------------------- money (Nov 16)

/// Currencies the grammar reads with their minor unit when the sign or code comes BEFORE the amount ($5.50 → ห้าดอลลาร์
/// ห้าสิบเซนต์); after the amount it reads only ฿ บาท THB € EUR with decimals (5.50 $ → ห้าจุดห้าศูนย์$).
const TH_MINOR: &[(&str, &str)] = &[
    ("$", "$"),
    ("＄", "$"),
    ("USD", "$"),
    ("€", "€"),
    ("EUR", "€"),
    ("£", "£"),
    ("GBP", "£"),
    ("฿", "฿"),
    ("THB", "฿"),
    ("บาท", "฿"),
];
/// Currencies without a minor unit in the grammar: a decimal amount is read as a decimal with the currency word after it.
const TH_NO_MINOR: &[(&str, &str)] = &[
    ("¥", "เยน"),
    ("￥", "เยน"),
    ("JPY", "เยน"),
    ("₩", "วอน"),
    ("KRW", "วอน"),
    ("₹", "รูปี"),
    ("INR", "รูปี"),
    ("₽", "รูเบิล"),
    ("RUB", "รูเบิล"),
    ("₫", "ดง"),
    ("VND", "ดง"),
];
/// Codes the grammar leaves unread (or reads only as whole amounts): the currency word and its minor unit.
const TH_CODES: &[(&str, &str, &str)] = &[
    ("HKD", "ดอลลาร์ฮ่องกง", "เซนต์"),
    ("SGD", "ดอลลาร์สิงคโปร์", "เซนต์"),
    ("TWD", "ดอลลาร์ไต้หวัน", "เซนต์"),
    ("NZD", "ดอลลาร์นิวซีแลนด์", "เซนต์"),
    ("AUD", "ดอลลาร์ออสเตรเลีย", "เซนต์"),
    ("CAD", "ดอลลาร์แคนาดา", "เซนต์"),
    ("MYR", "ริงกิต", "เซน"),
    ("CNY", "หยวน", ""),
    ("RMB", "หยวน", ""),
    ("LAK", "กีบ", ""),
    ("KHR", "เรียล", ""),
    ("MMK", "จั๊ด", ""),
    ("IDR", "รูเปียห์", ""),
    ("PHP", "เปโซ", ""),
    ("CHF", "ฟรังก์สวิส", ""),
    ("BRL", "เรียลบราซิล", ""),
];
const TH_SIGN: &str = "[$＄€£฿¥￥₩₹₽₫]";
const TH_SIGN_WORD: &[(&str, &str)] = &[
    ("$", "ดอลลาร์"),
    ("＄", "ดอลลาร์"),
    ("€", "ยูโร"),
    ("£", "ปอนด์"),
    ("฿", "บาท"),
    ("¥", "เยน"),
    ("￥", "เยน"),
    ("₩", "วอน"),
];
const TH_CODE: &str =
    "USD|EUR|GBP|THB|JPY|KRW|INR|RUB|VND|HKD|SGD|TWD|NZD|AUD|CAD|MYR|CNY|RMB|LAK|KHR|MMK|IDR|PHP|CHF|BRL";
/// The sign or the code (บาท after the amount is added where it may stand).
const TH_CUR: &str = concat!(
    "[$＄€£฿¥￥₩₹₽₫]|",
    "USD|EUR|GBP|THB|JPY|KRW|INR|RUB|VND|HKD|SGD|TWD|NZD|AUD|CAD|MYR|CNY|RMB|LAK|KHR|MMK|IDR|PHP|CHF|BRL"
);
const TH_AMOUNT: &str = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?";

fn lookup2<'a>(table: &[(&str, &'a str)], key: &str) -> Option<&'a str> {
    table.iter().find(|(k, _)| *k == key).map(|(_, v)| *v)
}

fn num(s: &str) -> f64 {
    s.replace(',', "").parse::<f64>().unwrap_or(0.0)
}

/// A form of `amount` in `cur` the grammar reads right: the sign before the amount with two decimals (฿2.5 → ฿2.50,
/// 5.50 $ → $5.50), a decimal before the currency word for ¥ ₩ ₹ (5.5 เยน), and the words for the codes it does not
/// know (5.50 HKD → 5 ดอลลาร์ฮ่องกง 50 เซนต์).
fn th_say(amount: &str, cur: &str) -> String {
    let (head, dec) = amount.split_once('.').unwrap_or((amount, ""));
    let mut dec = dec.to_string();
    if dec.chars().count() == 1 {
        dec.push('0');
    }
    if let Some(sign) = lookup2(TH_MINOR, cur) {
        return format!("{sign}{head}{}", if dec.is_empty() { String::new() } else { format!(".{dec}") });
    }
    if let Some(word) = lookup2(TH_NO_MINOR, cur) {
        let d = dec.trim_end_matches('0');
        return format!("{head}{} {word}", if d.is_empty() { String::new() } else { format!(".{d}") });
    }
    let &(_, word, cents) = TH_CODES.iter().find(|x| x.0 == cur).expect("currency code");
    if !cents.is_empty() {
        let tail =
            if !dec.is_empty() && py_int(&dec) != 0 { format!(" {} {cents}", py_int(&dec)) } else { String::new() };
        return format!("{head} {word}{tail}");
    }
    let d = dec.trim_end_matches('0');
    format!("{head}{} {word}", if d.is_empty() { String::new() } else { format!(".{d}") })
}

/// The grammar leaves part of `s` unread or misreads a range or a minus (a sign, a code, ~, a dot or ลบ/ประมาณ).
fn th_unread(s: &str) -> bool {
    search(r"[$＄€£฿¥￥₩₹₽₫~～.A-Za-z]|ลบ|ประมาณ", &words(s, "th"))
}

fn th_money_range(t: String, c: &mut Ctx) -> String {
    let pat = format!(
        r"(?<![\dA-Za-z.,])({TH_SIGN}|(?:{TH_CODE}) ?)({TH_AMOUNT}) ?[-–—~～〜] ?({TH_SIGN}|(?:{TH_CODE}) ?)?({TH_AMOUNT})(?![\d.,]\d|\d)(?! ?(?:[A-Za-z]|ล้าน|แสน|หมื่น|พัน|ร้อย))"
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        let (cur, a, cur2, b) = (g(m, 1).trim(), g(m, 2), g(m, 3).trim(), g(m, 4));
        if (!cur2.is_empty() && cur2 != cur) || num(a) >= num(b) {
            return None;
        }
        if !th_unread(&m[0]) {
            return None;
        }
        Some(format!("{a}ถึง{}", th_say(b, cur)))
    });
    let pat =
        format!(r"(?<![\dA-Za-z.,\-–—~～〜])({TH_AMOUNT}) ?[-–—~～〜] ?({TH_AMOUNT}) ?({TH_CUR}|บาท)(?![A-Za-z])");
    c.sub(&rx(&pat), &t, |m| {
        let (a, b, cur) = (g(m, 1), g(m, 2), g(m, 3));
        if num(a) >= num(b) || !th_unread(&m[0]) {
            return None;
        }
        Some(format!("{a}ถึง{}", th_say(b, cur)))
    })
}

fn th_money(t: String, c: &mut Ctx) -> String {
    let say = |m: &fancy_regex::Captures<'_, str>, cur: &str, amount: &str| -> Option<String> {
        if !amount.contains('.') && !TH_CODES.iter().any(|x| x.0 == cur) {
            return None; // a whole amount the grammar reads (5 $, ฿100, 5 JPY)
        }
        let out = format!("{}{}", g(m, 1), th_say(amount, cur));
        if words(&out, "th") == words(&m[0], "th") { None } else { Some(out) }
    };
    let pat = format!(
        r"(?<![\dA-Za-z.,])(-?)({TH_SIGN}|(?<![A-Za-z])(?:{TH_CODE}) ?)({TH_AMOUNT})(?![\d.,]\d|\d)(?! ?(?:[A-Za-z]|ล้าน|แสน|หมื่น|พัน|ร้อย))"
    );
    let t = c.sub(&rx(&pat), &t, |m| say(m, g(m, 2).trim(), g(m, 3)));
    let pat = format!(r"(?<![\dA-Za-z.,])(-?)({TH_AMOUNT}) ?({TH_CUR}|บาท)(?![A-Za-z])");
    let t = c.sub(&rx(&pat), &t, |m| say(m, g(m, 3), g(m, 2)));
    let pat = r"(?<![\dA-Za-z.,])(-?)([$＄€£฿¥￥₩]) ?(\d+(?:\.\d+)?) ?((?:ร้อย|พัน|หมื่น|แสน)?ล้าน(?:ล้าน)?|แสน|หมื่น|พัน)";
    c.sub(&rx(pat), &t, |m| {
        let word = lookup2(TH_SIGN_WORD, g(m, 2))?;
        let end = m.get(0).expect("group 0").end();
        let rest = t[end..].trim_start_matches(crate::text::is_py_space);
        Some(format!("{}{}{}{}", g(m, 1), g(m, 3), g(m, 4), if rest.starts_with(word) { "" } else { word }))
    })
}

const TH_PER: &[(&str, &str)] = &[
    ("กก.", "กิโลกรัม"),
    ("กก", "กิโลกรัม"),
    ("ชม.", "ชั่วโมง"),
    ("ชม", "ชั่วโมง"),
    ("กม.", "กิโลเมตร"),
    ("กม", "กิโลเมตร"),
    ("ตร.ม.", "ตารางเมตร"),
    ("ตร.ว.", "ตารางวา"),
    ("ลบ.ม.", "ลูกบาศก์เมตร"),
];
const TH_PER_RX: &str = r"ตร\.ม\.|ตร\.ว\.|ลบ\.ม\.|กก\.|ชม\.|กม\.|กก|ชม|กม";

fn th_per(t: String, c: &mut Ctx) -> String {
    let cur = format!(
        r"({TH_SIGN} ?\d[\d,]*(?:\.\d+)?|{TH_SIGN}|(?<![A-Za-z])(?:{TH_CODE})|บาท|ดอลลาร์|ยูโร|เยน|วอน|ปอนด์|หยวน)"
    );
    let pat = format!(r"{cur} ?/ ?(?:({TH_PER_RX})(?![ก-๏])|(?=[ก-ฮเ-ไ]))");
    c.sub(&rx(&pat), &t, |m| Some(format!("{}ต่อ{}", g(m, 1), lookup2(TH_PER, g(m, 2)).unwrap_or(""))))
}

fn th_groups(t: String, c: &mut Ctx) -> String {
    let pat = r"(?<![\dA-Za-z.,/:+\-–])(?<!\d[ \x{A0}\x{202F}])[1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+(?![\d]|[.,]\d{3})(?![ \x{A0}\x{202F}]\d)";
    c.sub(&rx(pat), &t, |m| {
        let w = m.get(0).expect("group 0");
        let gaps = w.as_str().chars().filter(|&ch| matches!(ch, ' ' | '\u{a0}' | '\u{202f}')).count();
        if gaps < 2
            && !search(r"[$€£¥₩₱฿₫₹] ?$", &t[..w.start()])
            && !matches_at_start(&format!(r" ?(?:{TH_CUR}|{COUNT_WORDS}|[a-zA-Z]{{1,3}}(?![A-Za-z]))"), &t[w.end()..])
        {
            return None;
        }
        Some(w.as_str().chars().filter(|&ch| !matches!(ch, ' ' | '\u{a0}' | '\u{202f}')).collect())
    })
}

// ------------------------------------------------------------------------------------------------- spaces (S29)

fn th_space(t: String, c: &mut Ctx) -> String {
    let word = format!("[{THAI}A-Za-z\u{e000}]");
    let pat = format!("(\u{e000}[^\u{e001}]*\u{e001})( +(?={word}))?|([{THAI}A-Za-z]\\.?) +(?={word})");
    c.sub(&rx(&pat), &t, |m| {
        let w = m.get(0).expect("group 0");
        let right: String = t[w.end()..].chars().take_while(|ch| ch.is_ascii_alphabetic()).collect();
        if !right.is_empty() && full(r"[IVXLCDM]+", &right) {
            return None;
        }
        if let Some(span) = m.get(1) {
            // a verbatim span an earlier rule wrote stays whole
            return m.get(2).map(|_| format!("{}{MARK}", span.as_str()));
        }
        let left = m.get(3)?;
        if search(r"(?<![A-Za-z])Miss$", chars_before(&t, left.end(), 5)) {
            return None;
        }
        Some(format!("{}{MARK}", left.as_str()))
    })
}

// ------------------------------------------------------------------------------------------------- abbreviations (S22)

const TH_ABBREV: &[(&str, &str)] = &[
    ("กทม.", "กรุงเทพมหานคร"),
    ("ร.ร.", "โรงเรียน"),
    ("รพ.", "โรงพยาบาล"),
    ("ถ.", "ถนน"),
    ("จ.", "จังหวัด"),
    ("ฯลฯ", "และอื่นๆ"),
];

fn th_abbrev(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"กทม\."), &t, "กรุงเทพมหานคร");
    let t = c.sub_tpl(&rx(r"ฯลฯ"), &t, "และอื่นๆ");
    let t = c.sub_tpl(&rx(&format!(r"(?<![{THAI}])ร\.ร\.")), &t, "โรงเรียน");
    c.sub(&rx(&format!(r"(?<![{THAI}])(รพ\.|ถ\.|จ\.)(?=(?: |{MARK})?[ก-ฮเ-ไ])")), &t, |m| {
        TH_ABBREV.iter().find(|(k, _)| *k == g(m, 1)).map(|(_, v)| v.to_string())
    })
}

// ------------------------------------------------------------------------------------------------- units (S19)

const TH_UNITS: &[(&str, &str)] = &[
    ("กม./ชม.", "km/h"),
    ("กม./ชม", "km/h"),
    ("กม/ชม.", "km/h"),
    ("กม/ชม", "km/h"),
    ("ตร.กม.", "km²"),
    ("ตร.กม", "km²"),
    ("ตร.ซม.", "cm²"),
    ("ตร.ซม", "cm²"),
    ("ลบ.ซม.", "cm³"),
    ("ลบ.ซม", "cm³"),
    ("ตร.ม.", "m²"),
    ("ตร.ม", "m²"),
    ("ลบ.ม.", "m³"),
    ("ลบ.ม", "m³"),
    ("ตร.ว.", "ตารางวา"),
    ("ตร.ว", "ตารางวา"),
];
const TH_UNIT_RX: &str = r"กม\./ชม\.|กม\./ชม|กม/ชม\.|ตร\.กม\.|ตร\.ซม\.|ลบ\.ซม\.|กม/ชม|ตร\.กม|ตร\.ซม|ลบ\.ซม|ตร\.ม\.|ลบ\.ม\.|ตร\.ว\.|ตร\.ม|ลบ\.ม|ตร\.ว";

/// Latin units the grammar leaves unread (5 t → ห้าt).
const TH_LATIN_UNITS: &[(&str, &str)] = &[("ha", "เฮกตาร์"), ("t", "ตัน")];

fn th_units(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<=\d)( ?)({TH_UNIT_RX})(?![{THAI}])")), &t, |m| {
        let unit = TH_UNITS.iter().find(|(k, _)| *k == g(m, 2)).map(|(_, v)| *v)?;
        Some(format!("{}{unit}", g(m, 1)))
    });
    c.sub(&rx(r"(?<=\d)( ?)(ha|t)(?![A-Za-z0-9²³/])"), &t, |m| {
        Some(format!("{}{}", g(m, 1), lookup2(TH_LATIN_UNITS, g(m, 2))?))
    })
}

// ------------------------------------------------------------------------------------------------- time (S09)

fn th_time(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.,:])(\d{1,2})[.:](\d{2}) ?(?:น\.|นาฬิกา)"), &t, |m| {
        if py_int(g(m, 1)) > 24 || py_int(g(m, 2)) > 59 {
            return None;
        }
        Some(format!("{}:{}", g(m, 1), g(m, 2)))
    })
}

// ------------------------------------------------------------------------------------------------- dates (S08)

fn th_date(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"วันที่ ?(?=\d{1,2}/\d{1,2}/\d{4}(?!\d))"), &t, "")
}

// ------------------------------------------------------------------------------------------------- scores (S15)

const SCORE_CUES: &str = r"(?:ชนะ|แพ้|เสมอ|สกอร์|ผลการแข่งขัน|ผลบอล|ผลการแข่ง|ด้วยสกอร์|คะแนน|ถล่ม|เฉือน|ไล่ตีเสมอ)";

fn th_score(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.,:/\-])(\d{1,3}) ?[-–:] ?(\d{1,3})(?![\d.,:/\-])"), &t, |m| {
        let w = m.get(0).expect("group 0");
        if !search(SCORE_CUES, chars_before(&t, w.start(), 30)) {
            return None;
        }
        if matches_at_start(&format!(r"\s*(?:{COUNT_WORDS}|[%฿$€£°])"), &t[w.end()..]) {
            return None; // ชนะ 2-3 ครั้ง: a range of counts
        }
        Some(format!("{}ต่อ{}", words(g(m, 1), "th"), words(g(m, 2), "th")))
    })
}

// ------------------------------------------------------------------------------------------------- halves (S16)

fn th_half(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\d.,/])(?<!\d )(?<!ที่)(?<!ที่ )1/2 ?(?=[ก-ฮเ-ไ])"), &t, "ครึ่ง")
}

// ------------------------------------------------------------------------------------------------- laughter (S34)

const NUMBER_CUES: &str = r"(?:ราคา|เบอร์|หมายเลข|ที่|รหัส|โทร|ห้อง|เลข|ปี|พ\.ศ\.|ค\.ศ\.|บ้าน|[฿$€£#])";
const COUNT_WORDS: &str = "บาท|คน|ตัว|อัน|ใบ|เล่ม|คัน|หลัง|ปี|เดือน|วัน|ชั่วโมง|ชม|นาที|วินาที|ครั้ง|ชิ้น|แผ่น|ลูก|เม็ด|ขวด|แก้ว|จาน|ชาม|กล่อง|ห่อ|ถุง|ฟอง|ดอก|ต้น|กิโล|กรัม|เมตร|ลิตร|สตางค์|เปอร์เซ็นต์|องศา|ห้อง|ชั้น|หน้า|ข้อ|เรื่อง|ราย|หน่วย|ล้าน|พัน|หมื่น|แสน|ร้อย|กม|ซม|มม|กก|ไร่|งาน|วา|ดวง|เครื่อง|คู่|ชุด|โมง|ทุ่ม|นาฬิกา|รอบ|แต้ม|ประตู|คะแนน|ตารางวา|รูปี|ดอลลาร์|ยูโร|เยน|วอน|หยวน|ปอนด์";

fn th_laugh(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\d.,:/\-])([5๕]{3,})\+*(?![\d๐-๙:/\-]|[.,][\d๐-๙])"), &t, |m| {
        let w = m.get(0).expect("group 0");
        if search(&format!(r"{NUMBER_CUES}\s*$"), chars_before(&t, w.start(), 20)) {
            return None;
        }
        if matches_at_start(&format!(r"\s*(?:{COUNT_WORDS}|[%฿$€£°]|[A-Za-z])"), &t[w.end()..]) {
            return None;
        }
        Some("ห้า".repeat(g(m, 1).chars().count()))
    })
}
