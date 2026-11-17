//! 'vi' rules: the port of the workbench's `langrules/vi.py` (ids `vi.*`).

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, g, matches_at_start, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[
    ("vi.groups", vi_groups),
    ("vi.grouping", vi_grouping),
    ("vi.money", vi_money),
    ("vi.per", vi_per),
    ("vi.city", vi_city),
    ("vi.address", vi_address),
    ("vi.score", vi_score),
];

fn vi_city(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(r"(?<!\w)(?:TP|Tp|tp)\.? ?HCM(?!\w)"), &t, "Thành phố Hồ Chí Minh");
    let t = c.sub_tpl(&rx(r"(?<!\w)HCM(?!\w)"), &t, "Hồ Chí Minh");
    c.sub_tpl(&rx(r"(?<!\w)(?:TP|Tp)\.(?=[A-ZĐ][a-zđà-ỹ])"), &t, "Thành phố ")
}

fn vi_address(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.])([QP])\.(?: ?(?=\d)|(?=[A-ZĐ][a-zđà-ỹ]))"), &t, |m| {
        Some(if g(m, 1) == "Q" { "Quận " } else { "Phường " }.to_string())
    })
}

const SCORE_CUES: &str = r"(?i)(?:thắng|thua|hòa|hoà|tỷ số|tỉ số|đánh bại|cầm hòa|cầm hoà|gỡ hòa|gỡ hoà|hạ gục|đè bẹp)";
const RANGE_AFTER: &str = r"\s*(?:%|tỷ|tỉ|triệu|nghìn|ngàn|trăm|người|giờ|phút|giây|ngày|tuần|tháng|năm|tuổi|lần|đồng|điểm|bàn|trận|vòng|km|kg|cm|mm|m(?!\w)|USD|VND)";

fn vi_score(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,:/\-])(\d{1,3}) ?[-–] ?(\d{1,3})(?![\w:/\-]|[.,]\d)"), &t, |m| {
        let w = m.get(0).expect("group 0");
        if !search(SCORE_CUES, chars_before(&t, w.start(), 40)) {
            return None;
        }
        if matches_at_start(RANGE_AFTER, &t[w.end()..]) {
            return None; // thua lỗ 2-3 tỷ: a range of amounts
        }
        Some(format!("{} {}", words(g(m, 1), "vi"), words(g(m, 2), "vi")))
    })
}

// ------------------------------------------------------------------------------------------------- money (Nov 16)

const VI_SIGN: &str = r"[$€£¥₫]";
const VI_CODE: &str = r"(?:USD|EUR|GBP|VND|JPY|CNY|KRW|THB|SGD|AUD|HKD)";
/// Codes whose sign the grammar reads with cents before the amount.
const VI_CODE_SIGN: &[(&str, &str)] = &[("USD", "$"), ("EUR", "€"), ("GBP", "£")];
/// Neighbours the grammar leaves unread.
const VI_CODES: &[(&str, &str)] = &[("LAK", "kíp Lào"), ("KHR", "riên Campuchia"), ("MMK", "kyat Myanmar")];
const VI_MONEY_AFTER: &str = concat!(
    r"(?:[$€£¥₫]|đ(?!\w)|(?:USD|EUR|GBP|VND|JPY|CNY|KRW|THB|SGD|AUD|HKD)(?![A-Za-z])|đồng(?!\w)|k(?![A-Za-z])|",
    r"nghìn(?!\w)|ngàn(?!\w)|triệu(?!\w)|tr(?![A-Za-z]))"
);

fn vi_groups(t: String, c: &mut Ctx) -> String {
    let pat = concat!(
        r"(?<![\w.,/:+\-–])(?<!\d[ \x{A0}\x{202F}])([1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+)(?:[.,](\d{1,2})(?!\d))?",
        r"(?!\d|[.,]\d)(?![ \x{A0}\x{202F}]\d)"
    );
    let after = format!(r"[ \x{{A0}}\x{{202F}}]?(?:{VI_SIGN}|{VI_CODE}|[^\W\d_])");
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

fn vi_grouping(t: String, c: &mut Ctx) -> String {
    let pat = r"(?<![\d.,])(\d{1,3}(?:,\d{3}){2,}|\d{1,3}(?:,\d{3})+(?=\.\d))(?:\.(\d+))?(?![\d,]|\.\d)";
    c.sub(&rx(pat), &t, |m| {
        Some(format!(
            "{}{}",
            g(m, 1).replace(',', "."),
            if g(m, 2).is_empty() { String::new() } else { format!(",{}", g(m, 2)) }
        ))
    })
}

fn vi_num(x: &str) -> f64 {
    x.replace('.', "").replace(',', ".").parse::<f64>().unwrap_or(0.0)
}

fn vi_money(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(r"(?<![\w.,])(?<!\d[\-–—~～〜])(?<!\d [\-–—~～〜])(\d+)\.(\d{1,2})(?!\d) ?([$€£]|USD|EUR|GBP)(?![A-Za-z])"),
        &t,
        |m| {
            let sign = VI_CODE_SIGN.iter().find(|(k, _)| *k == g(m, 3)).map_or(g(m, 3), |(_, v)| *v);
            Some(format!("{sign}{}.{}", g(m, 1), g(m, 2)))
        },
    );
    let pat = format!(
        r"(?<![\w.,])({VI_SIGN}|(?<![A-Za-z]){VI_CODE} ?)(\d+(?:[.,]\d+)*)( ?[-–—~～〜] ?)({VI_SIGN}|{VI_CODE} ?)?(\d+(?:[.,]\d+)*)(?![\d.,]*\d)"
    );
    let t = c.sub(&rx(&pat), &t, |m| {
        let (a, b) = (g(m, 2), g(m, 5));
        if (!g(m, 4).is_empty() && g(m, 4).trim() != g(m, 1).trim()) || vi_num(a) >= vi_num(b) {
            return None;
        }
        Some(format!("{a}-{b} {}", g(m, 1).trim()))
    });
    let t = c.sub_tpl(&rx(r"(?<![\w.,])(\d+(?:[.,]\d+)*) ?[~～〜] ?(?=\d)"), &t, r"\1-");
    let pat =
        r"(?<![\w.,])(?:(LAK|KHR|MMK) ?(\d+(?:[.,]\d+)*)(?![\d.,]*\d)|(\d+(?:[.,]\d+)*) ?(LAK|KHR|MMK))(?![A-Za-z])";
    c.sub(&rx(pat), &t, |m| {
        let code = if g(m, 1).is_empty() { g(m, 4) } else { g(m, 1) };
        let word = VI_CODES.iter().find(|(k, _)| *k == code).map(|(_, v)| *v)?;
        Some(format!("{} {word}", if g(m, 2).is_empty() { g(m, 3) } else { g(m, 2) }))
    })
}

fn vi_per(t: String, c: &mut Ctx) -> String {
    let money =
        format!(r"(?<![\w.,])({VI_SIGN} ?\d[\d.,]*|(?<![A-Za-z]){VI_CODE} ?\d[\d.,]*|\d[\d.,]* ?{VI_MONEY_AFTER})");
    c.sub(&rx(&format!(r"{money} ?/ ?([^\W\d_]+)")), &t, |m| {
        if !words(&m[0], "vi").contains('/') {
            return None;
        }
        let tight = format!("{}/{}", g(m, 1), g(m, 2));
        if !words(&tight, "vi").contains('/') {
            return Some(tight); // 100 € / tháng: the grammar reads the slash without the spaces
        }
        Some(format!("{} một {}", g(m, 1), g(m, 2)))
    })
}
