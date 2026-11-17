//! 'id' rules: the port of the workbench's `langrules/id.py` (ids `id.*`).

#[allow(unused_imports)]
use super::super::{Ctx, g, py_int, rx, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("id.groups", id_groups),
    ("id.grouping", id_grouping),
    ("id.money", id_money),
    ("id.per", id_per),
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

// ------------------------------------------------------------------------------------------------- money (Nov 16)

/// Signs and codes with a minor unit.
const SIGN: &str = r"(?:[€$£]|(?<![A-Za-z])(?:RM|S\$|USD|EUR|GBP|MYR|SGD)(?![A-Za-z]) ?)";
const SIGN_ANY: &str =
    r"(?:[€$£¥]|(?<![A-Za-z])(?:RM|Rp|S\$|USD|EUR|GBP|MYR|SGD|IDR|JPY|CNY|AUD|HKD|THB)(?![A-Za-z]) ?)";
const CUR_AFTER: &str = r"(?:[€$£]|(?:RM|USD|EUR|GBP|MYR|SGD)(?![A-Za-z]))";
const SCALE: &str = r"(?![A-Za-z]| ?(?:ribu|juta|miliar|bilion|billion|trilion|triliun|rb|jt)(?!\w))";

fn id_money(t: String, c: &mut Ctx) -> String {
    let pat = format!(r"(?<![\w.,])({SIGN}\d+(?:[.,]\d{{3}})*)([.,])(\d)(?![\d.,]\d|\d){SCALE}");
    let t = c.sub(&rx(&pat), &t, |m| Some(format!("{}{}{}0", g(m, 1), g(m, 2), g(m, 3))));
    let pat =
        format!(r"(?<![\w.,])(?<!\d[\-–—~～〜])(?<!\d [\-–—~～〜])(\d+(?:[.,]\d{{3}})*)([.,])(\d)( ?{CUR_AFTER})");
    let t = c.sub(&rx(&pat), &t, |m| Some(format!("{}{}{}0{}", g(m, 1), g(m, 2), g(m, 3), g(m, 4))));
    c.sub_tpl(&rx(&format!(r"(?<![\w.,])({SIGN_ANY}?\d[\d.,]*) ?[~～〜] ?(?={SIGN_ANY}?\d)")), &t, r"\1-")
}

fn id_per(t: String, c: &mut Ctx) -> String {
    let money = format!(
        r"(?<![\w.,])({SIGN_ANY}\d[\d.,]*(?: ?(?:ribu|juta|rb|jt))?|\d[\d.,]* ?(?:{SIGN_ANY}|(?:ringgit|euro|dolar|rupiah|sen|ribu|juta|rb|jt)(?!\w)))"
    );
    c.sub(&rx(&format!(r"{money} ?/ ?([^\W\d_]+)")), &t, |m| {
        if !words(&m[0], "id").contains('/') {
            return None; // the grammar reads it (100 €/bulan → seratus euro per bulan)
        }
        Some(format!("{} per {}", g(m, 1), g(m, 2)))
    })
}

fn id_groups(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?<![\w.,/:+\-–])(?<!\d[ \x{A0}\x{202F}])([1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+)(?:[.,](\d{1,2})(?!\d))?",
        r"(?!\d|[.,]\d)(?![ \x{A0}\x{202F}]\d)"
    );
    let after = format!(r"[ \x{{A0}}\x{{202F}}]?(?:{SIGN_ANY}|[^\W\d_])");
    c.sub(&rx(pat), &t, |m| {
        let gaps = g(m, 1).chars().filter(|&ch| matches!(ch, ' ' | '\u{a0}' | '\u{202f}')).count();
        if gaps < 2
            && !super::super::search(r"[$€£¥₩₱฿₫₹] ?$", &t[..m.get(0).expect("group 0").start()])
            && !super::super::matches_at_start(&after, &t[m.get(0).expect("group 0").end()..])
        {
            return None;
        }
        let head: String =
            g(m, 1).chars().map(|ch| if matches!(ch, ' ' | '\u{a0}' | '\u{202f}') { '.' } else { ch }).collect();
        Some(format!("{head}{}", if g(m, 2).is_empty() { String::new() } else { format!(",{}", g(m, 2)) }))
    })
}

fn id_grouping(t: String, c: &mut Ctx) -> String {
    let pat = r"(?<![\d.,])(\d{1,3}(?:,\d{3}){2,}|\d{1,3}(?:,\d{3})+(?=\.\d))(?:\.(\d+))?(?![\d,]|\.\d)";
    c.sub(&rx(pat), &t, |m| {
        Some(format!(
            "{}{}",
            g(m, 1).replace(',', "."),
            if g(m, 2).is_empty() { String::new() } else { format!(",{}", g(m, 2)) }
        ))
    })
}
