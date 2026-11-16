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

fn th_units(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<=\d)( ?)({TH_UNIT_RX})(?![{THAI}])")), &t, |m| {
        let unit = TH_UNITS.iter().find(|(k, _)| *k == g(m, 2)).map(|(_, v)| *v)?;
        Some(format!("{}{unit}", g(m, 1)))
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
