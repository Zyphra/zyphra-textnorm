//! 'ms' rules: the port of the workbench's `langrules/ms.py` (ids `ms.*`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("ms.regnal", ms_regnal),
    ("ms.place-abbrev", ms_place_abbrev),
    ("ms.chat-abbrev", ms_chat_abbrev),
    ("ms.time", ms_time),
];

const ROMAN: &str = r"(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})";
/// The grammar's ruler names (src/lang/ms/other.rs NAMES), longest first; the numeral after them is an ordinal.
const MONARCHS: &str = "Yang di-Pertuan Agong|Hamengkubuwono|Mangkunegara|Pakubuwono|Benediktus|Fransiskus|Permaisuri|Aleksander|Gregorius|Elizabeth|Alexander|Maharaja|Napoleon|Nicholas|Victoria|Mohammed|Abdullah|Wilhelm|Yohanes|Nikolai|Charles|William|Richard|Paulus|Edward|George|Philip|Felipe|Ramses|Salman|Hassan|Henry|James|Louis|Agong|Pius|Rama|Leo";
const TITLES: &str = r"(?:Sultan|Raja|Permaisuri|Paus|Kaisar|Maharaja|Tuanku)";
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

fn ms_regnal(t: String, c: &mut Ctx) -> String {
    let lead = format!(r"(?<![\w-])((?:{MONARCHS}|{TITLES}(?: {NAME}){{1,2}}|[Pp]erang [Dd]unia|[Aa]bad)) ");
    c.sub(&rx(&format!(r"{lead}(?=[IVXLC])({ROMAN})(?![\w-]|\.\w)")), &t, |m| {
        let n = roman_value(g(m, 2));
        if !(1..=90).contains(&n) {
            return None;
        }
        Some(format!("{} ke-{n}", g(m, 1)))
    })
}

const PLACES: &[(&str, &str)] = &[
    ("Kg.", "Kampung"),
    ("Kpg.", "Kampung"),
    ("Tmn.", "Taman"),
    ("Sg.", "Sungai"),
    ("Bt.", "Batu"),
    ("Jln", "Jalan"),
    ("Bdr.", "Bandar"),
];
const PLACE_RX: &str = r"Kpg\.|Tmn\.|Bdr\.|Kg\.|Sg\.|Bt\.|Jln";

fn ms_place_abbrev(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.])({PLACE_RX})(?= [A-Z])")), &t, |m| {
        PLACES.iter().find(|(k, _)| *k == g(m, 1)).map(|(_, v)| v.to_string())
    })
}

const CHAT: &[(&str, &str)] = &[
    ("spt", "seperti"),
    ("dgn", "dengan"),
    ("yg", "yang"),
    ("utk", "untuk"),
    ("tdk", "tidak"),
    ("kpd", "kepada"),
    ("drpd", "daripada"),
    ("dlm", "dalam"),
    ("sbg", "sebagai"),
    ("krn", "kerana"),
    ("bkn", "bukan"),
];
const CHAT_RX: &str = "[dD]rpd|[sS]pt|[dD]gn|[uU]tk|[tT]dk|[kK]pd|[dD]lm|[sS]bg|[kK]rn|[bB]kn|[yY]g";

fn ms_chat_abbrev(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&format!(r"(?<![\w.@/-])({CHAT_RX})(\.?)(?![\w@/-]|\.\w)")), &t, |m| {
        let w = g(m, 1);
        let key = w.to_lowercase();
        let word = CHAT.iter().find(|(k, _)| *k == key).map(|(_, v)| *v)?;
        let word = if w != key { format!("{}{}", word[..1].to_uppercase(), &word[1..]) } else { word.to_string() };
        // a period after spt is the abbreviation's own
        Some(if key == "spt" { word } else { format!("{word}{}", g(m, 2)) })
    })
}

fn ms_time(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<!\w)((?:[Pp]ukul|[Jj]am) )(\d{1,2})[.:](\d{2})(?![\d:]|[.,]\d)"), &t, |m| {
        let (h, mm) = (py_int(g(m, 2)), py_int(g(m, 3)));
        if h > 24 || !(10..=59).contains(&mm) {
            return None;
        }
        Some(format!("{}{} {}", g(m, 1), words(&h.to_string(), "ms"), words(&mm.to_string(), "ms")))
    })
}
