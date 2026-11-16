//! 'vi' rules: the port of the workbench's `langrules/vi.py` (ids `vi.*`).

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, g, matches_at_start, rx, search, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};

pub(super) const RULES: &[LangRule] = &[("vi.city", vi_city), ("vi.address", vi_address), ("vi.score", vi_score)];

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
