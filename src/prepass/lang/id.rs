//! 'id' rules: the port of the workbench's `langrules/id.py` (ids `id.*`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("id.minus-temp", id_minus_temp),
    ("id.regnal", id_regnal),
    ("id.chat-abbrev", id_chat_abbrev),
    ("id.time", id_time),
];

const ROMAN: &str = r"(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})";
/// The grammar's monarch names (src/lang/id/other.rs MONARCHS), longest first; the numeral after them is an ordinal.
const MONARCHS: &str = "Hamengkubuwono|Hamengkubuwana|Mangkunegara|Pakubuwono|Pakubuwana|Benediktus|Fransiskus|Aleksander|Paku Alam|Gregorius|Elizabeth|Alexander|Pakualam|Napoleon|Nicholas|Victoria|Mohammed|Abdullah|Wilhelm|Yohanes|Nikolai|Charles|William|Richard|Paulus|Edward|George|Philip|Felipe|Ramses|Salman|Hassan|Henry|James|Louis|Pius|Rama|Leo";
const TITLES: &str = r"(?:Sultan|Raja|Ratu|Paus|Kaisar|Pangeran|Sunan)";
const NAME: &str = r"[A-Z][a-z]+(?:-[A-Za-z]+)?";

fn roman_value(s: &str) -> u32 {
    let val = |ch: char| match ch {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        _ => 100,
    };
    let chars: Vec<char> = s.chars().collect();
    let mut n: i64 = 0;
    for (i, &ch) in chars.iter().enumerate() {
        let v = val(ch);
        n += if i + 1 < chars.len() && val(chars[i + 1]) > v { -(v as i64) } else { v as i64 };
    }
    n.max(0) as u32
}

fn id_regnal(t: String, c: &mut Ctx) -> String {
    let lead = format!(r"(?<![\w-])((?:{MONARCHS}|{TITLES}(?: {NAME}){{1,2}}|[Pp]erang [Dd]unia|[Aa]bad)) ");
    c.sub(&rx(&format!(r"{lead}(?=[IVXLC])({ROMAN})(?![\w-]|\.\w)")), &t, |m| {
        let n = roman_value(g(m, 2));
        if !(1..=90).contains(&n) {
            return None;
        }
        Some(format!("{} ke-{n}", g(m, 1)))
    })
}

const CHAT: &[(&str, &str)] = &[
    ("yg", "yang"),
    ("dgn", "dengan"),
    ("utk", "untuk"),
    ("tgl", "tanggal"),
    ("krn", "karena"),
    ("tdk", "tidak"),
    ("sdh", "sudah"),
    ("blm", "belum"),
    ("jg", "juga"),
    ("bgt", "banget"),
    ("kpd", "kepada"),
    ("dlm", "dalam"),
    ("spt", "seperti"),
    ("thn", "tahun"),
    ("bln", "bulan"),
    ("hrs", "harus"),
    ("bs", "bisa"),
    ("sm", "sama"),
];
const CHAT_RX: &str = "[dD]gn|[uU]tk|[tT]gl|[kK]rn|[tT]dk|[sS]dh|[bB]lm|[bB]gt|[kK]pd|[dD]lm|[sS]pt|[tT]hn|[bB]ln|[hH]rs|[yY]g|[jJ]g|[bB]s|[sS]m";

fn id_chat_abbrev(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.@/-])({CHAT_RX})(\.?)(?![\w@/-]|\.\w)")), &t, |m| {
        let w = g(m, 1);
        let key = w.to_lowercase();
        if w != key && (key == "bs" || key == "sm") {
            return None;
        }
        let word = CHAT.iter().find(|(k, _)| *k == key).map(|(_, v)| *v)?;
        let word = if w != key { format!("{}{}", word[..1].to_uppercase(), &word[1..]) } else { word.to_string() };
        // a period after tgl is the abbreviation's own
        Some(if key == "tgl" { word } else { format!("{word}{}", g(m, 2)) })
    })
}

fn id_time(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<!\w)((?:[Pp]ukul|[Jj]am) )(\d{1,2})[.:](\d{2})(?![\d:]|[.,]\d)"), &t, |m| {
        let (h, mm) = (py_int(g(m, 2)), py_int(g(m, 3)));
        if h > 24 || !(10..=59).contains(&mm) {
            return None;
        }
        Some(format!("{}{} {}", g(m, 1), words(&h.to_string(), "id"), words(&mm.to_string(), "id")))
    })
}

fn id_minus_temp(t: String, c: &mut Ctx) -> String {
    c.sub_tpl(&rx(r"(?<![\w.,\-])-(?=\d+(?:[.,]\d+)? ?(?:°[CF]?|℃|℉|derajat(?!\w)))"), &t, "minus ")
}
