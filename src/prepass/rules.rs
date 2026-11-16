//! The pre-pass rules, in the prototype's order of definition. Patterns are written in Python's syntax and compiled
//! by [`super::rx`], so each rule reads like the prototype it was reviewed as.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

use super::tables::{emoji_alias, emoji_list, emoji_name, html_unescape};
use super::{
    Ctx, after, before, chars_after, chars_before, commas, english, full, g, is_alnum, matches_at_start,
    ordinal_digits, py_int, py_int_str, py_rstrip, py_strip, rx, search,
};
use crate::text::is_py_space;

pub(super) type T = String;

const END_PUNCT: &str = ".!?:;,…";

fn end_sentence(s: &str) -> String {
    let s = py_rstrip(s);
    let core = s.trim_end_matches(|c| "\"')]*_”’»".contains(c));
    match core.chars().next_back() {
        None => s.to_string(),
        Some(c) if END_PUNCT.contains(c) => s.to_string(),
        _ => format!("{s}."),
    }
}

fn caps<'t>(pat: &str, s: &'t str) -> Option<Captures<'t, str>> {
    rx(&format!("^(?:{pat})")).captures(s).ok().flatten()
}

/// Alternation of `keys`, longest first, ties in the given order (Python's stable `sorted(..., key=len, reverse=True)`).
fn alt_by_len(keys: &[&str]) -> String {
    let mut k: Vec<&str> = keys.to_vec();
    k.sort_by_key(|s| std::cmp::Reverse(s.chars().count()));
    k.join("|")
}

fn lookup<'a>(map: &[(&str, &'a str)], k: &str) -> Option<&'a str> {
    map.iter().find(|(a, _)| *a == k).map(|(_, v)| *v)
}

// ================================================================================================= markup

pub(super) fn md_fence(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?m)^[ \t]*(?:```|~~~)[^\n]*(?:\n|$)"), &t, "")
}

pub(super) fn md_rule(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?m)^[ \t]*([-*_=])(?:[ \t]*\1){2,}[ \t]*$"), &t, "")
}

pub(super) fn md_table(t: T, c: &mut Ctx) -> T {
    let sep = r"[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$";
    let mut out: Vec<String> = Vec::new();
    for line in t.split('\n') {
        let s = py_strip(line);
        if s.contains('|') && matches_at_start(sep, s) {
            c.hits.push(super::Hit { rule: c.rid, before: line.to_string(), after: String::new() });
            continue;
        }
        if s.chars().count() > 2 && s.starts_with('|') && s.ends_with('|') && s.matches('|').count() >= 3 {
            let cells: Vec<&str> = s[1..s.len() - 1].split('|').map(py_strip).filter(|x| !x.is_empty()).collect();
            let mut joined: Vec<String> = Vec::new();
            if cells.len() > 1 {
                for x in &cells[..cells.len() - 1] {
                    let last = x.chars().next_back().expect("non-empty cell");
                    joined.push(if END_PUNCT.contains(last) { x.to_string() } else { format!("{x},") });
                }
            }
            let new = end_sentence(&format!(
                "{}{}{}",
                joined.join(" "),
                if cells.len() > 1 { " " } else { "" },
                cells.last().copied().unwrap_or("")
            ));
            c.hits.push(super::Hit { rule: c.rid, before: line.to_string(), after: new.clone() });
            out.push(new);
            continue;
        }
        out.push(line.to_string());
    }
    out.join("\n")
}

/// The word for # in each language: the grammar's own where its data has one (electronic/symbol tables), else ours.
const HASH_WORD: [(&str, &str); 43] = [
    ("en", "hash"),
    ("de", "Raute"),
    ("es", "almohadilla"),
    ("fr", "dièse"),
    ("it", "cancelletto"),
    ("pt", "cerquilha"),
    ("ja", "ハッシュタグ"),
    ("zh", "井号"),
    ("ko", "샵"),
    ("nl", "hekje"),
    ("pl", "kratka"),
    ("tr", "diyez"),
    ("uk", "решітка"),
    ("cs", "mřížka"),
    ("da", "havelåge"),
    ("fi", "risuaita"),
    ("el", "δίεση"),
    ("nb", "firkant"),
    ("ro", "diez"),
    ("sk", "mriežka"),
    ("bg", "диез"),
    ("he", "סולמית"),
    ("th", "แฮช"),
    ("tl", "hash"),
    ("ms", "pagar"),
    ("ka", "ჰეშთეგი"),
    ("ta", "ஹேஷ்"),
    ("gu", "હેશ"),
    ("kn", "ಹ್ಯಾಶ್"),
    ("ml", "ഹാഷ്"),
    ("pa", "ਹੈਸ਼"),
    ("or", "ହ୍ୟାସ୍"),
    ("ru", "решетка"),
    ("sv", "brädgård"),
    ("hu", "kettőskereszt"),
    ("ar", "هاش"),
    ("vi", "thăng"),
    ("id", "pagar"),
    ("hi", "हैशटैग"),
    ("bn", "হ্যাশ"),
    ("te", "హ్యాష్"),
    ("mr", "हॅशटॅग"),
    ("ur", "ہیش ٹیگ"),
];

pub(super) fn md_heading(t: T, c: &mut Ctx) -> T {
    let hash = lookup(&HASH_WORD, c.lang()).unwrap_or("hash");
    c.sub(&rx(r"(?m)^[ \t]{0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$"), &t, |m| {
        let text = g(m, 2);
        // “# Additional currencies are listed below.”: a comment line, not a heading
        if g(m, 1) == "#" && search(r"[^\W\d_]\.[\d.]*$", text) {
            return Some(format!("{hash} {text}"));
        }
        Some(end_sentence(text))
    })
}

pub(super) fn md_quote(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?m)^[ \t]{0,3}>+[ \t]?(?![ \t]*[\d=])"), &t, "")
}

pub(super) fn md_bullet(t: T, c: &mut Ctx) -> T {
    let re = rx(r"(?m)^[ \t]*[\-\*\+•◦▪▫‣⁃●○■□►▶➢➤✓✔✗☐☑→–—][ \t]+(?:\[[ xX]\][ \t]+)?(.*\S)[ \t]*$");
    c.sub(&re, &t, |m| {
        let item = g(m, 1);
        if full(r"[\d\s+\-*/=.,()]+", item) { None } else { Some(end_sentence(item)) }
    })
}

static HTML_TAGS: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    "a abbr address article aside audio b bdi bdo big blockquote body br button caption center cite code col \
     colgroup data dd del details dfn dialog div dl dt em embed fieldset figcaption figure font footer form h1 h2 h3 h4 \
     h5 h6 head header hr html i iframe img input ins kbd label legend li link main mark meta nav noscript object ol \
     optgroup option output p param picture pre q rp rt ruby s samp script section select small source span strike \
     strong style sub summary sup table tbody td template textarea tfoot th thead time title tr track tt u ul var video \
     wbr speak break prosody emphasis say-as phoneme voice lang w"
        .split_whitespace()
        .collect()
});
const BLOCK_TAGS: [&str; 22] = [
    "br",
    "p",
    "div",
    "li",
    "tr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "ul",
    "ol",
    "table",
    "blockquote",
    "section",
    "article",
    "header",
    "footer",
    "dd",
    "dt",
];

fn tag_word(name: &str) -> String {
    rx(r"[-_]+").replace_all(name, " ").into_owned()
}

pub(super) fn html_tag(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>"), &t, "");
    let t = c.sub_tpl(&rx(r"<((?:https?|ftp|mailto):[^\s<>]+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)>"), &t, r"\1");
    let names: HashSet<String> =
        rx(r"</([A-Za-z][\w:-]*)\s*>").captures_iter(t.as_str()).flatten().map(|m| g(&m, 1).to_lowercase()).collect();
    let openers: HashSet<String> = rx(r"<([A-Za-z][\w:-]*)(?:=[^<>\s/]*)?\s*>")
        .captures_iter(t.as_str())
        .flatten()
        .map(|m| g(&m, 1).to_lowercase())
        .collect();
    let spoken: HashSet<&String> = names.intersection(&openers).collect();
    let en = c.lang() == "en";
    let re = rx(r"<(/?)([A-Za-z][\w:-]*)((?:\s+[^<>]*?|=[^<>\s/]*)?)\s*(/?)>");
    c.sub(&re, &t, |m| {
        let name = g(m, 2).to_lowercase();
        if HTML_TAGS.contains(name.as_str()) {
            return Some(if BLOCK_TAGS.contains(&name.as_str()) { "\n".into() } else { String::new() });
        }
        let attrs = py_strip(g(m, 3));
        if attrs.is_empty() {
            if spoken.contains(&name) {
                return Some(if en { format!(" {} ", tag_word(g(m, 2))) } else { String::new() });
            }
            if !g(m, 1).is_empty() || names.contains(&name) {
                return Some(String::new());
            }
            if !en {
                return Some(" ".into());
            }
            return Some(format!(" {} ", tag_word(g(m, 2))));
        }
        if let Some(value) = attrs.strip_prefix('=')
            && en
        {
            let value = rx(r"^-(?=[\d.])").replace(value, "negative ").into_owned();
            return Some(format!(" {} equals {value} ", tag_word(g(m, 2))));
        }
        if attrs.contains('=') {
            return Some(String::new());
        }
        let whole = m.get(0).expect("group 0");
        let b = before(&t, whole.start(), ' ');
        let a = after(&t, whole.end(), ' ');
        if (is_py_space(b) || "([\"'".contains(b)) && (is_py_space(a) || ".,;:!?)]\"'".contains(a)) {
            let s = whole.as_str();
            return Some(s[1..s.len() - 1].to_string());
        }
        None
    })
}

pub(super) fn html_entity(t: T, c: &mut Ctx) -> T {
    c.sub(&rx(r"&(?:#\d{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});"), &t, |m| {
        let d = html_unescape(&m[0]);
        if d == m[0] { None } else { Some(d) }
    })
}

pub(super) fn md_link(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?m)^[ \t]*\[[^\]\n]+\]:[ \t]+\S+.*$"), &t, "");
    let t = c.sub_tpl(&rx(r#"!\[[^\]\n]*\]\([^)\s]*(?:\s+"[^"]*")?\)"#), &t, "");
    let t = c.sub_tpl(&rx(r#"\[([^\]\n]+)\]\((?:[^()\s]|\([^()\s]*\))*(?:\s+"[^"]*")?\)"#), &t, r"\1");
    c.sub_tpl(&rx(r"\[([^\]\n]+)\]\[[^\]\n]*\]"), &t, r"\1")
}

pub(super) fn md_emphasis(mut t: T, c: &mut Ctx) -> T {
    let star = rx(r"(?<![\w*\\])(\*{1,3})(?=[^\s*])([^\n]*?[^\s*\\])\1(?![\w*])");
    let us = rx(r"(?<![\w_\\.])(_{1,3})(?=[^\s_])([^\n]*?[^\s_\\])\1(?![\w_])");
    for _ in 0..3 {
        let s1 = c.sub(&star, &t, |m| Some(g(m, 2).to_string()));
        let new = c.sub(&us, &s1, |m| {
            let end = m.get(0).expect("group 0").end();
            if (end < s1.len() && "(.".contains(after(&s1, end, ' '))) || search(r"\w_\w", g(m, 2)) {
                return None;
            }
            Some(g(m, 2).to_string())
        });
        if new == t {
            break;
        }
        t = new;
    }
    t
}

pub(super) fn md_strike(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?<![\w~])(~~?)(?=[^\W\d_])([^\n~]*?[^\s~])\1(?![\w~])"), &t, r"\2")
}

fn operand_left(s: &str) -> bool {
    search(r"(?:^|[^\w.])(?:\d+(?:\.\d+)?|[A-Za-z])\)?\s*$", s)
}

fn operand_right(s: &str) -> bool {
    matches_at_start(r"\s*\(?(?:\d|[A-Za-z](?!\w))", s)
}

pub(super) fn md_asterisk(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?i)\b(dial|press|call|enter|type|hit)\s+\*(?=[\d#]|\s)"), &t, r"\1 star ");
    c.sub(&rx(r"\*+"), &t, |m| {
        let w = m.get(0).expect("group 0");
        let left = &t[..w.start()];
        if is_alnum(after(&t, w.end(), ' ')) || (operand_left(left) && operand_right(&t[w.end()..])) {
            return None;
        }
        if search(r"(?<![\w.,$£€¥])\d+$", left) {
            return None;
        }
        if search(r"\d%?\)?$|\d(?:st|nd|rd|th)$|\d\s?[A-Za-zµμ°]{1,3}$", left) {
            return Some(format!(" {}", w.as_str()));
        }
        None
    })
}

pub(super) fn md_blank(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"_{3,}"), &t, "")
}

pub(super) fn md_code_scope(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?<=\w)::(?=\w)"), &t, " ")
}

/// ja and zh: an emoji's name joins the sentence without spaces (a space stops the Japanese grammar reading 3日).
fn emoji_pad(lang: &str) -> &'static str {
    if matches!(lang, "ja" | "zh") { "" } else { " " }
}

pub(super) fn md_shortcode(t: T, c: &mut Ctx) -> T {
    let lang = c.lang().to_string();
    let pad = emoji_pad(&lang);
    c.sub(&rx(r"(?<![\w:]):(?:(?=[a-z0-9_+\-]*[a-z])[a-z0-9_+\-]{2,30}|[+-]1):(?![\w:])"), &t, |m| {
        let name = emoji_alias(&m[0]).and_then(|e| emoji_name(&e, &lang));
        Some(name.map_or(String::new(), |n| format!("{pad}{n}{pad}")))
    })
}

pub(super) fn ch_emoji(t: T, c: &mut Ctx) -> T {
    let lang = c.lang().to_string();
    let pad = emoji_pad(&lang);
    let t = if lang == "en" {
        c.sub(&rx(r"[★☆]{3,}"), &t, |m| {
            let full = m[0].matches('★').count();
            let empty = m[0].matches('☆').count();
            Some(format!(" {full} out of {} stars ", full + empty))
        })
    } else {
        t
    };
    let mut out = String::new();
    let mut pos = 0usize;
    let mut last: Option<String> = None;
    for (start, end, e) in emoji_list(&t) {
        let Some(name) = emoji_name(&e, &lang) else { continue };
        let gap = &t[pos..start];
        out.push_str(gap);
        if !(last.as_deref() == Some(name.as_str()) && py_strip(gap).is_empty()) {
            out.push_str(&format!("{pad}{name}{pad}"));
            c.hits.push(super::Hit { rule: c.rid, before: e.clone(), after: name.clone() });
        }
        last = Some(name);
        pos = end;
    }
    out.push_str(&t[pos..]);
    c.sub_tpl(&rx(r"[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}]"), &out, "")
}

pub(super) fn md_pipe(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?<=[^\s|])(?=\|+(?:\s|$))"), &t, " ")
}

static HASH_KEEP: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    "a an and are as at be but by do for from he her his i if in is it its me my no not of on or our she so than that \
     the their them then there they this to us was we were what when where which who why will with you your"
        .split_whitespace()
        .collect()
});

/// VidaSana → Vida Sana, MutluYıllar → Mutlu Yıllar, AIForGood → AI For Good; iPhone, eBay stay whole: prototype
/// `camel_split`.
fn camel_split(w: &str) -> String {
    let c: Vec<char> = w.chars().collect();
    let mut out = String::new();
    for (i, &ch) in c.iter().enumerate() {
        if i > 0 && ch.is_uppercase() {
            let prev = c[i - 1];
            let mut j = i - 1;
            while j > 0 && (if prev.is_lowercase() { c[j - 1].is_lowercase() } else { c[j - 1].is_uppercase() }) {
                j -= 1;
            }
            let run = i - j; // the letters of prev's case right before ch
            if run >= 2 && (prev.is_lowercase() || (prev.is_uppercase() && i + 1 < c.len() && c[i + 1].is_lowercase()))
            {
                out.push(' ');
            }
        }
        out.push(ch);
    }
    out
}

pub(super) fn md_hashtag(t: T, c: &mut Ctx) -> T {
    let en = c.lang() == "en";
    let t = if en {
        c.sub(&rx(r"(?<![\w#&])#(\d+)([A-Za-z]\w*)(?![\w#])"), &t, |m| {
            let (mut num, mut rest) = (g(m, 1).to_string(), g(m, 2));
            if ["st", "nd", "rd", "th"].contains(&rest) {
                return None;
            }
            if matches_at_start(r"(?:st|nd|rd|th)[A-Z]", rest) {
                num.push_str(&rest[..2]);
                rest = &rest[2..];
            }
            let words: Vec<&str> =
                rx(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+").find_iter(rest).flatten().map(|x| x.as_str()).collect();
            Some(format!("{num} {}", words.join(" ")))
        })
    } else {
        t
    };
    // Weibo / Douyin topic: #双十一# 今天… → 双十一 今天…
    let t = if matches!(c.lang(), "zh" | "ja") {
        c.sub_tpl(&rx(r"(?<![\w#&])#(?=[^#\n]*[^\x00-\x7f])([^\s#](?:[^#\n]{0,40}?[^\s#])?)#(?!#)"), &t, r"\1")
    } else {
        t
    };
    c.sub(&rx(r"(?<![\w#&])#([^\W\d_]\w*)(?![\w#]|\.\w)"), &t, |m| {
        let w = g(m, 1);
        if HASH_KEEP.contains(w.to_lowercase().as_str()) || full(r"[IVX]+", w) {
            return None;
        }
        // “ist# … #ist”: the same word with a # after it, not after a word character or #
        let needle = format!("{w}#");
        if t.match_indices(&needle)
            .any(|(i, _)| !t[..i].chars().next_back().is_some_and(|p| super::is_word(p) || p == '#'))
        {
            return None;
        }
        if en {
            return Some(w.to_string()); // English keeps “underscore” and the tag whole (Gabriel, Nov 15)
        }
        Some(camel_split(&w.split('_').filter(|p| !p.is_empty()).collect::<Vec<_>>().join(" ")))
    })
}

// ================================================================================================= characters

pub(super) fn ch_backtick(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?<!`)`(?!`)"), &t, "'")
}

pub(super) fn ch_quote(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"[‘’‚‛‹›]"), &t, "'");
    let t = c.sub_tpl(&rx(r"(?<=\d)′(?=s\b)"), &t, "'");
    c.sub_tpl(&rx(r"(?<=[^\W\d_])[´ʹ]|[´ʹ](?=[^\W\d_])"), &t, "'")
}

pub(super) fn ch_dash(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"[‐‑‒−]"), &t, "-")
}

pub(super) fn ch_endash_pause(t: T, c: &mut Ctx) -> T {
    let t = c.sub(&rx(r"(?<=\b[A-Za-z])[ \t]+([-–—−])[ \t]+(?=[A-Za-z]\b)"), &t, |m| {
        let end = m.get(0).expect("group 0").end();
        let line = t[end..].split('\n').next().unwrap_or("");
        let eq = line.contains('=') || search(r"\bequals\b", line);
        Some(if "-−".contains(g(m, 1)) && eq { " minus ".into() } else { " dash ".into() })
    });
    c.sub_tpl(&rx(r"(?<=[^\W\d_])[ \t]+–[ \t]+(?=[^\W\d_])"), &t, " — ")
}

pub(super) fn ch_ellipsis(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"…(?=\d)"), &t, "... "); // ...3 read “.. point three”
    c.sub_tpl(&rx("…"), &t, "...")
}

pub(super) fn ch_invisible(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"[\x{200B}\x{2060}\x{FEFF}\x{AD}]"), &t, "")
}

/// Spanish: ves glued to a number (829ves, ves817) or VES beside one (261 VES) is the bolívar soberano. The grammar's
/// currency table spells the code “ves” plus a zero-width space (a NeMo data typo), so that is the key written back.
pub(super) fn es_ves(t: T, c: &mut Ctx) -> T {
    let key = "ves\u{200B}";
    let t = c.sub_tpl(&rx(r"(?<=\d)(?:ves|VES)(?!\w)|(?<!\w)(?:ves|VES)(?=\d)"), &t, key);
    c.sub_tpl(&rx(r"(?<=\d[ \t\x{A0}])VES(?!\w)|(?<!\w)VES(?=[ \t\x{A0}]\d)"), &t, key)
}

fn shift(s: &str) -> String {
    s.chars().map(|ch| char::from_u32(ch as u32 - 0xFEE0).unwrap_or(ch)).collect()
}

pub(super) fn ch_fullwidth(t: T, c: &mut Ctx) -> T {
    if matches!(c.lang(), "ja" | "zh" | "ko") {
        return c.sub(&rx(r"[０-９]"), &t, |m| Some(shift(&m[0])));
    }
    let t = c.sub(&rx(r"[\x{FF01}-\x{FF5E}]"), &t, |m| Some(shift(&m[0])));
    c.sub_tpl(&rx(r"\x{3000}"), &t, " ")
}

pub(super) fn ch_ligature(t: T, c: &mut Ctx) -> T {
    const LIG: [(&str, &str); 7] =
        [("ﬀ", "ff"), ("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬃ", "ffi"), ("ﬄ", "ffl"), ("ﬅ", "st"), ("ﬆ", "st")];
    c.sub(&rx("[ﬀﬁﬂﬃﬄﬅﬆ]"), &t, |m| lookup(&LIG, &m[0]).map(str::to_string))
}

pub(super) fn ch_lookalike(t: T, c: &mut Ctx) -> T {
    const MAP: [(&str, &str); 8] = [
        ("\u{b5}", "\u{3bc}"),
        ("\u{212a}", "K"),
        ("\u{212b}", "\u{c5}"),
        ("\u{3d5}", "\u{3c6}"),
        ("\u{3d1}", "\u{3b8}"),
        ("\u{3f5}", "\u{3b5}"),
        ("\u{3f1}", "\u{3c1}"),
        ("\u{3d6}", "\u{3c0}"),
    ];
    // it, pl, de and the Indic grammars read the micro sign µ, not Greek μ
    let class = if c.lang() == "en" {
        r"[\x{B5}\x{212A}\x{212B}\x{3D5}\x{3D1}\x{3F5}\x{3F1}\x{3D6}]"
    } else {
        r"[\x{212A}\x{212B}\x{3D5}\x{3D1}\x{3F5}\x{3F1}\x{3D6}]"
    };
    let t = c.sub(&rx(class), &t, |m| lookup(&MAP, &m[0]).map(str::to_string));
    c.sub_tpl(&rx(r"(?<=\d)\s?˚|˚(?=[CF]\b)"), &t, "°")
}

#[derive(Clone, Copy)]
enum Plural {
    /// one form
    Inv,
    /// singular for exactly 1, else plural (en, es, pt, fi, bg, te)
    One,
    /// singular below 2 (fr)
    Fr,
    /// ro: 1 / 0, 2–19 and decimals / 20+
    Ro,
    /// cs, sk: 1 / 2–4 / 5+ / decimals
    Cs,
    /// pl: 1 / 2–4, 22–24… / 5+ / decimals
    Pl,
    /// ru, uk: 1, 21… / 2–4, 22–24… / 5+ / decimals
    Ru,
}

/// The ohm units in a language: its forms (a template whose {} is the prefix), the kilo/mega/giga/milli prefixes, the
/// plural rule, and the forms once a prefix is attached when they differ (de Ohm → Kiloohm, el ωμ → κιλοώμ). Where a
/// grammar has the unit, these are its words.
struct Ohm {
    forms: &'static [&'static str],
    pre: [&'static str; 4],
    plural: Plural,
    prefixed: Option<&'static [&'static str]>,
}

const fn ohm(forms: &'static [&'static str], pre: [&'static str; 4], plural: Plural) -> Ohm {
    Ohm { forms, pre, plural, prefixed: None }
}

const LATIN: [&str; 4] = ["kilo", "mega", "giga", "milli"];
const LATIN1: [&str; 4] = ["kilo", "mega", "giga", "mili"];

static OHM: [(&str, Ohm); 43] = {
    use Plural::*;
    [
        ("en", ohm(&["{}ohm", "{}ohms"], ["kil", "meg", "gig", "milli"], One)),
        (
            "de",
            Ohm { forms: &["Ohm"], pre: ["Kilo", "Mega", "Giga", "Milli"], plural: Inv, prefixed: Some(&["{}ohm"]) },
        ),
        ("es", ohm(&["{}ohmio", "{}ohmios"], LATIN1, One)),
        ("fr", ohm(&["{}ohm", "{}ohms"], ["kilo", "méga", "giga", "milli"], Fr)),
        ("it", ohm(&["{}ohm"], LATIN, Inv)),
        ("pt", ohm(&["{}ohm", "{}ohms"], ["quilo-", "mega", "giga", "mili"], One)),
        ("ja", ohm(&["{}オーム"], ["キロ", "メガ", "ギガ", "ミリ"], Inv)),
        ("zh", ohm(&["{}欧姆"], ["千", "兆", "吉", "毫"], Inv)),
        ("ko", ohm(&["{}옴"], ["킬로", "메가", "기가", "밀리"], Inv)),
        ("nl", ohm(&["{}ohm"], LATIN, Inv)),
        ("pl", ohm(&["{}om", "{}omy", "{}omów", "{}oma"], LATIN1, Pl)),
        ("tr", ohm(&["{}ohm"], LATIN1, Inv)),
        ("uk", ohm(&["{}ом", "{}оми", "{}омів", "{}ома"], ["кіло", "мега", "гіга", "мілі"], Ru)),
        ("cs", ohm(&["{}ohm", "{}ohmy", "{}ohmů", "{}ohmu"], LATIN1, Cs)),
        ("da", ohm(&["{}ohm"], LATIN, Inv)),
        ("fi", ohm(&["{}ohmi", "{}ohmia"], ["kilo-", "mega", "giga", "milli"], One)),
        (
            "el",
            Ohm {
                forms: &["ωμ"], pre: ["κιλο", "μεγα", "γιγα", "μιλι"], plural: Inv, prefixed: Some(&["{}ώμ"])
            },
        ),
        ("nb", ohm(&["{}ohm"], LATIN, Inv)),
        ("ro", ohm(&["{}ohm", "{}ohmi", "de {}ohmi"], LATIN1, Ro)),
        ("sk", ohm(&["{}ohm", "{}ohmy", "{}ohmov", "{}ohmu"], LATIN1, Cs)),
        ("bg", ohm(&["{}ом", "{}ома"], ["кило", "мега", "гига", "мили"], One)),
        ("he", ohm(&["{}אוהם"], ["קילו-", "מגה-", "גיגה-", "מילי-"], Inv)),
        ("th", ohm(&["{}โอห์ม"], ["กิโล", "เมกะ", "จิกะ", "มิลลิ"], Inv)),
        ("tl", ohm(&["{}ohm"], LATIN1, Inv)),
        ("ms", ohm(&["{}ohm"], LATIN1, Inv)),
        ("ka", ohm(&["{}ომი"], ["კილო", "მეგა", "გიგა", "მილი"], Inv)),
        ("ta", ohm(&["{}ஓம்"], ["கிலோ ", "மெகா ", "ஜிகா ", "மில்லி "], Inv)),
        ("gu", ohm(&["{}ઓહ્મ"], ["કિલો", "મેગા", "ગીગા", "મિલી"], Inv)),
        ("kn", ohm(&["{}ಓಮ್"], ["ಕಿಲೋ ", "ಮೆಗಾ ", "ಗಿಗಾ ", "ಮಿಲಿ "], Inv)),
        ("ml", ohm(&["{}ഓം"], ["കിലോ ", "മെഗാ ", "ഗിഗാ ", "മില്ലി "], Inv)),
        ("pa", ohm(&["{}ਓਹਮ"], ["ਕਿਲੋ", "ਮੈਗਾ", "ਗੀਗਾ", "ਮਿਲੀ"], Inv)),
        ("or", ohm(&["{}ଓହମ୍"], ["କିଲୋ", "ମେଗା", "ଗିଗା", "ମିଲି"], Inv)),
        ("ru", ohm(&["{}ом", "{}ома", "{}ом", "{}ома"], ["кило", "мега", "гига", "милли"], Ru)),
        ("sv", ohm(&["{}ohm"], LATIN, Inv)),
        ("hu", ohm(&["{}ohm"], LATIN, Inv)),
        ("ar", ohm(&["{}أوم"], ["كيلو ", "ميغا ", "غيغا ", "ملي "], Inv)),
        ("vi", ohm(&["{}ôm"], ["ki lô ", "mê ga ", "gi ga ", "mi li "], Inv)),
        ("id", ohm(&["{}ohm"], LATIN1, Inv)),
        ("hi", ohm(&["{}ओम"], ["किलो", "मेगा", "गीगा", "मिली"], Inv)),
        ("bn", ohm(&["{}ওহম"], ["কিলো", "মেগা", "গিগা", "মিলি"], Inv)),
        ("te", ohm(&["{}ఓమ్", "{}ఓమ్స్"], ["కిలో ", "మెగా ", "గిగా ", "మిల్లీ "], One)),
        ("mr", ohm(&["{}ओहम"], ["किलो", "मेगा", "गिगा", "मिली"], Inv)),
        ("ur", ohm(&["{}اوہم"], ["کلو ", "میگا ", "گیگا ", "ملی "], Inv)),
    ]
};

/// The ohm units each grammar already reads after a number (5 Ω, 1 kΩ; checked 2026-11-15): left to the grammar, with
/// the Greek Ω its data uses. English Ω/kΩ/MΩ are the units rule's (5 Ω → five ohms).
const OHM_READ: [(&str, &str); 35] = [
    ("en", "Ω kΩ MΩ"),
    ("nl", "Ω"),
    ("pl", "Ω kΩ MΩ"),
    ("tr", "Ω"),
    ("uk", "Ω"),
    ("cs", "Ω"),
    ("da", "Ω"),
    ("fi", "Ω"),
    ("el", "Ω"),
    ("nb", "Ω"),
    ("ro", "Ω"),
    ("sk", "Ω"),
    ("bg", "Ω"),
    ("he", "Ω"),
    ("th", "Ω"),
    ("tl", "Ω kΩ MΩ"),
    ("ms", "Ω kΩ MΩ"),
    ("ka", "Ω kΩ MΩ"),
    ("ta", "Ω kΩ MΩ"),
    ("gu", "Ω kΩ MΩ"),
    ("kn", "Ω kΩ MΩ"),
    ("ml", "Ω"),
    ("pa", "Ω kΩ MΩ"),
    ("or", "Ω"),
    ("ru", "Ω"),
    ("sv", "Ω"),
    ("hu", "Ω kΩ MΩ"),
    ("ar", "Ω kΩ MΩ mΩ"),
    ("vi", "Ω kΩ MΩ GΩ mΩ"),
    ("id", "Ω kΩ MΩ"),
    ("hi", "Ω kΩ MΩ GΩ mΩ"),
    ("bn", "Ω kΩ MΩ"),
    ("te", "Ω kΩ MΩ"),
    ("mr", "Ω kΩ MΩ"),
    ("ur", "Ω kΩ MΩ"),
];

/// ... and before a number (Arabic reads “kΩ 123” as 123 kiloohm); the flag says whether that works before 1.
const OHM_READ_BEFORE: [(&str, &str, bool); 2] = [("ar", "Ω kΩ MΩ mΩ", false), ("ru", "Ω", true)];

/// Which form a count takes: 0 is the singular (also the form said with no number).
fn ohm_form(plural: Plural, num: Option<&str>) -> usize {
    let Some(num) = num else { return 0 };
    if matches!(plural, Plural::Inv) {
        return 0;
    }
    // 1.000 / 7,030,927 are grouped; 2,5 / 1.5 are decimals
    let (n, m100, frac) = match rx(r"^(\d+(?:[.,]\d{3})*)(?:[.,](\d+))?$").captures(num).ok().flatten() {
        Some(m) => {
            let digits = super::py_int_str(&m[1]);
            let tail = &digits[digits.len().saturating_sub(2)..];
            (py_int(&m[1]), tail.parse::<u32>().unwrap_or(0), m.get(2).is_some())
        }
        None => (0, 0, true),
    };
    let (one, m10) = (n == 1, m100 % 10);
    match plural {
        Plural::Inv => 0,
        Plural::One => usize::from(!one || frac),
        Plural::Fr => usize::from(n >= 2),
        Plural::Ro if one && !frac => 0,
        Plural::Ro => {
            if frac || n == 0 || (1..=19).contains(&m100) {
                1
            } else {
                2
            }
        }
        _ if frac => 3,
        Plural::Cs if one => 0,
        Plural::Cs => {
            if (2..=4).contains(&n) {
                1
            } else {
                2
            }
        }
        Plural::Pl if one => 0,
        Plural::Ru if m10 == 1 && m100 != 11 => 0,
        _ => {
            if (2..=4).contains(&m10) && !(12..=14).contains(&m100) {
                1
            } else {
                2
            }
        }
    }
}

fn ohm_word(lang: &str, prefix: &str, num: Option<&str>) -> String {
    let o = &OHM.iter().find(|(l, _)| *l == lang).expect("every language has ohm words").1;
    let forms = match o.prefixed {
        Some(p) if !prefix.is_empty() => p,
        _ => o.forms,
    };
    let p = "kMGm".find(prefix).filter(|_| !prefix.is_empty()).map_or("", |i| o.pre[i]);
    forms[ohm_form(o.plural, num)].replace("{}", p)
}

pub(super) fn ch_ohm(t: T, c: &mut Ctx) -> T {
    let lang = c.lang().to_string();
    let read: Vec<&str> = lookup(&OHM_READ, &lang).unwrap_or("").split_whitespace().collect();
    let (before, one_ok) =
        OHM_READ_BEFORE.iter().find(|(l, _, _)| *l == lang).map_or(("", true), |(_, u, ok)| (*u, *ok));
    // Latin or Greek: Ω inside a word (a kana or hanzi beside it is fine: 抵抗は5Ωです)
    let edge = r"[A-Za-z\x{C0}-\x{24F}\x{370}-\x{3FF}\x{1F00}-\x{1FFF}]";
    let re = rx(&format!(
        r"(?:(?<![\d.,_])(?<!{edge})(\d+(?:[.,]\d+)*)[ \t\x{{A0}}]?)?(?<!{edge})([kMGm]?)([\x{{2126}}\x{{3A9}}])(?!{edge})"
    ));
    c.sub(&re, &t, |m| {
        let num = m.get(1).map(|x| x.as_str());
        let (prefix, sym) = (g(m, 2), g(m, 3));
        if sym == "\u{3A9}" && num.is_none() && prefix.is_empty() {
            return None; // a Greek capital omega on its own is the letter
        }
        let unit = format!("{prefix}\u{3A9}");
        let end = m.get(0).expect("group 0").end();
        let next = caps(r"[ \t\x{A0}](\d+)(?![\d.,])|[ \t\x{A0}]\d", &t[end..]);
        if num.is_none()
            && before.split_whitespace().any(|u| u == unit)
            && next.is_some_and(|nx| one_ok || nx.get(1).map(|x| x.as_str()) != Some("1"))
        {
            return Some(unit);
        }
        if let Some(num) = num {
            if read.contains(&unit.as_str()) {
                return Some(format!("{num} {unit}"));
            }
            let sep = if matches!(lang.as_str(), "ja" | "zh") { "" } else { " " }; // ja: 5オーム, not 5 オーム
            return Some(format!("{num}{sep}{}", ohm_word(&lang, prefix, Some(num))));
        }
        Some(ohm_word(&lang, prefix, None))
    })
}

pub(super) fn ch_fracslash(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?<=\d)[⁄∕](?=\d)"), &t, "/")
}

pub(super) fn ch_bang(t: T, c: &mut Ctx) -> T {
    c.sub(&rx("[‼⁉⁈]"), &t, |m| lookup(&[("‼", "!!"), ("⁉", "?!"), ("⁈", "?!")], &m[0]).map(str::to_string))
}

fn unsub(s: &str) -> String {
    s.chars()
        .map(|ch| if ('₀'..='₉').contains(&ch) { char::from(b'0' + (ch as u32 - '₀' as u32) as u8) } else { ch })
        .collect()
}

pub(super) fn ch_subscript(t: T, c: &mut Ctx) -> T {
    let t = c.sub(&rx(r"(?<!\w)(?:[A-Z][a-z]?[₀-₉]*)+(?!\w)"), &t, |m| {
        if !search("[₀-₉]", &m[0]) {
            return None;
        }
        let parts: Vec<String> =
            rx(r"[A-Z][a-z]?|[₀-₉]+").find_iter(&m[0]).flatten().map(|p| unsub(p.as_str())).collect();
        Some(parts.join(" "))
    });
    c.sub(&rx("[₀-₉]+"), &t, |m| Some(unsub(&m[0])))
}

pub(super) fn ch_mojibake(t: T, c: &mut Ctx) -> T {
    const FIX: [(&str, &str); 8] = [
        ("â€™", "’"),
        ("â€˜", "‘"),
        ("â€œ", "“"),
        ("â€\u{9d}", "”"),
        ("â€", "”"),
        ("â€“", "–"),
        ("â€”", "—"),
        ("â€¦", "…"),
    ];
    c.sub(&rx(r"â€(?:™|˜|œ|\x{9D}|–|—|…)?"), &t, |m| lookup(&FIX, &m[0]).map(str::to_string))
}

pub(super) fn ch_midbullet(t: T, c: &mut Ctx) -> T {
    let t = if c.lang() == "en" { c.sub_tpl(&rx(r"(?<=\S)[ \t]+[·‧∙][ \t]+(?=\S)"), &t, " dot ") } else { t };
    c.sub_tpl(&rx(r"(?<=\S)[ \t]+[•▪●◦][ \t]+(?=\S)"), &t, ", ")
}

// ================================================================================================= English

const SUPS: &str = "⁰¹²³⁴⁵⁶⁷⁸⁹";
const SUP_UNITS: [&str; 15] = ["m", "cm", "mm", "km", "dm", "μm", "nm", "ft", "in", "yd", "mi", "s", "ms", "m/s", "sq"];

fn unsup(s: &str) -> String {
    s.chars()
        .map(|ch| match "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺".chars().position(|x| x == ch) {
            Some(i) => "0123456789-+".chars().nth(i).expect("same length"),
            None => ch,
        })
        .collect()
}

pub(super) fn en_footnote(t: T, c: &mut Ctx) -> T {
    let not_unit: String = SUP_UNITS.iter().map(|u| format!(r"(?<!\b{u})(?<!\d{u})")).collect();
    c.sub_tpl(&rx(&format!(r"(?:(?<=[^\W\d_]{{2}}){not_unit}|(?<=[.,;:]))[{SUPS}]+")), &t, "")
}

fn ord_word(n: &str) -> String {
    match py_int(n) {
        2 => "squared".into(),
        3 => "cubed".into(),
        _ => format!("to the {}", ordinal_digits(n)),
    }
}

pub(super) fn en_power(t: T, c: &mut Ctx) -> T {
    let units: Vec<&str> = SUP_UNITS.iter().copied().filter(|u| *u != "m/s").collect();
    let t = c.sub_tpl(&rx(&format!(r"(?<=\d)({})([²³])/(?=[A-Za-z])", units.join("|"))), &t, r"\1\2 slash ");
    let t = c.sub(&rx(&format!(r"(\d)\s*[×x]\s*10([⁻⁺]?)([{SUPS}]+)")), &t, |m| {
        Some(format!("{} times 10 to the {}{}", g(m, 1), if g(m, 2) == "⁻" { "minus " } else { "" }, unsup(g(m, 3))))
    });
    let t = c.sub(&rx(&format!(r"(?<![\w.])10([⁻⁺]?)([{SUPS}]+)")), &t, |m| {
        let n = unsup(g(m, 2));
        Some(format!("10 to the {}", if g(m, 1) == "⁻" { format!("minus {n}") } else { ordinal_digits(&n) }))
    });
    let t = c.sub(&rx(&format!(r"(?<![\w.])(?<!\d )([A-Za-z])([{SUPS}]+)")), &t, |m| {
        Some(format!("{} {}", g(m, 1), ord_word(&unsup(g(m, 2)))))
    });
    let t = c.sub(&rx(r"(?<![\w.])(\d+|[A-Za-z])\s?(?:\^|\*\*)\s?(\d+)(?![\w.])"), &t, |m| {
        let a = g(m, 1);
        Some(if a.chars().all(char::is_alphabetic) {
            format!("{a} {}", ord_word(g(m, 2)))
        } else {
            format!("{a} to the {}", ordinal_digits(g(m, 2)))
        })
    });
    c.sub(&rx(r"(?<![\w.])(\d+(?:\.\d+)?)[eE]([-+]?)(\d+)(?![\w.])"), &t, |m| {
        Some(format!("{} e {}{}", g(m, 1), if g(m, 2) == "-" { "minus " } else { "" }, g(m, 3)))
    })
}

pub(super) fn en_approx(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?<![\w~])~\s?(?=[$£€¥₹]?\d)"), &t, "about ");
    let t = c.sub_tpl(&rx(r"(?i)\b(about|around|roughly|approximately|approx\.?)\s*≈\s*"), &t, r"\1 ");
    c.sub_tpl(&rx(r"\s*≈\s*"), &t, " approximately ")
}

fn math_word(op: &str) -> &'static str {
    match op {
        "≤" | "<=" => "is less than or equal to",
        "≥" | ">=" => "is greater than or equal to",
        "≠" | "!=" => "is not equal to",
        "÷" => "divided by",
        "==" => "equals",
        "<" => "is less than",
        ">" => "is greater than",
        _ => unreachable!("math operator {op}"),
    }
}

pub(super) fn en_math(t: T, c: &mut Ctx) -> T {
    let a = r"((?<![\w.])(?:\d+(?:\.\d+)?|[A-Za-z](?!\w))|\))";
    let b = r"(?=-?(?:\d|[A-Za-z](?!\w)|\())";
    let t = c.sub(&rx(&format!(r"{a}\s*(≤|≥|≠|÷)\s*{b}")), &t, |m| {
        Some(format!("{} {} ", g(m, 1), math_word(g(m, 2))))
    });
    let t = c
        .sub(&rx(&format!(r"{a} (<=|>=|!=|==|<|>) {b}")), &t, |m| Some(format!("{} {} ", g(m, 1), math_word(g(m, 2)))));
    let t = c.sub_tpl(&rx(r"(?<![\w.])±\s?(?=[$]?\d)"), &t, "plus or minus ");
    let t = c.sub(&rx(&format!(r"{a}\s*\*\s*{b}")), &t, |m| Some(format!("{} times ", g(m, 1))));
    let t = c.sub_tpl(&rx(r"(?<=[\w)]) = (?=[-$]?[\w(])"), &t, " equals ");
    let t = c.sub_tpl(
        &rx(r"(?<![\w/?&=.:%-])([A-Za-z]{1,3}|\d+(?:\.\d+)?)=(-?\d+(?:\.\d+)?|[A-Za-z](?![\w=]))(?![\w=&/])"),
        &t,
        r"\1 equals \2",
    );
    let t = c.sub_tpl(&rx(r"(?<=\d)±(?=\d)"), &t, " plus or minus ");
    let t = c.sub_tpl(&rx(r"(?<![^\s(\[])([A-Za-z]|\d+)<([A-Za-z]|\d+)(?![\w>])"), &t, r"\1 is less than \2");
    let t = c.sub_tpl(&rx(r"(?<![^\s(\[])([A-Za-z]|\d+)>([A-Za-z]|\d+)(?![\w<])"), &t, r"\1 is greater than \2");
    let t = c.sub_tpl(&rx(r"(?<![\w.])(\d+(?:\.\d+)?)\s?π"), &t, r"\1 pi");
    let t = c.sub_tpl(
        &rx(r"(?<![\w./])(\d+(?:\.\d+)?) / (\d+(?:\.\d+)?)(?=\s*(?:$|[.,;:!?)=]|equals\b))"),
        &t,
        r"\1 divided by \2",
    );
    c.sub_tpl(&rx(r"(?<![\w.])([A-Za-z])\(([A-Za-z0-9])\)"), &t, r"\1 of \2")
}

pub(super) fn en_times_sign(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(
        &rx(r"(?<![\w.])(\d+(?:\.\d+)?)x(?=\s+(?:faster|slower|more|less|better|worse|bigger|smaller|larger|higher|lower|cheaper|stronger)\b)"),
        &t,
        r"\1 times",
    );
    c.sub(
        &rx(r#"(?<![\w.])(\d+(?:\.\d+)?)([″"']|\s?(?:mm|cm|m|km|in|ft|px|µm|μm)(?![A-Za-z]))?\s*([×x])\s*(?=(\d))"#),
        &t,
        |m| {
            let end = m.get(0).expect("group 0").end();
            let next = after(&t, end, ' ').to_string();
            if g(m, 1) == "0" && full(r"[0-9a-fA-F]", &next) {
                return None;
            }
            let window = chars_after(&t, end, 40);
            let clause = match rx(r"[\n,;]|\band\b").find(window) {
                Ok(Some(x)) => &window[..x.start()],
                _ => window,
            };
            let eq = search(r"=|\bequals\b", clause);
            if g(m, 3) == "x"
                && !eq
                && g(m, 2).is_empty()
                && !matches_at_start(
                    r#"\d+(?:\.\d+)?(?:[″"']|\s?(?:mm|cm|m|km|in|ft|px|µm|μm)(?![A-Za-z]))"#,
                    &t[end..],
                )
            {
                return None; // 2x8, 2 x 3, 4x4: the grammar's “two x eight”
            }
            Some(format!("{}{} {} ", g(m, 1), g(m, 2), if eq { "times" } else { "by" }))
        },
    )
}

pub(super) fn en_arrow(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?<=\S)\s+(?:→|⇒|⟶|➔|->|=>)\s+(?=\S)"), &t, " to ")
}

fn lakh_words(digits: &str) -> String {
    let v = py_int(&digits.replace(',', ""));
    let (crore, rest) = (v / 10_000_000, v % 10_000_000);
    let (lakh, rest) = (rest / 100_000, rest % 100_000);
    let mut parts = Vec::new();
    if crore > 0 {
        parts.push(format!("{crore} crore"));
    }
    if lakh > 0 {
        parts.push(format!("{lakh} lakh"));
    }
    if rest > 0 {
        let s = rest.to_string();
        parts.push(if s.len() > 3 { format!("{},{}", &s[..s.len() - 3], &s[s.len() - 3..]) } else { s });
    }
    if parts.is_empty() { "0".into() } else { parts.join(" ") }
}

pub(super) fn en_lakh(t: T, c: &mut Ctx) -> T {
    let core = r"(\d{1,2}(?:,\d\d){1,3},\d{3})(?![\d,-]|\.\d)";
    let t = c.sub(&rx(&format!(r"(?:₹|\bRs\.?\s?|\bINR\s?){core}")), &t, |m| {
        Some(format!("{} rupees", lakh_words(g(m, 1))))
    });
    let t = c.sub(&rx(&format!(r"(?<![\d,-]){core}")), &t, |m| Some(lakh_words(g(m, 1))));
    c.sub(&rx(r"(?:₹|\bRs\.\s?)(\d[\d,]*(?:\.\d+)?)"), &t, |m| {
        Some(format!("{} rupee{}", g(m, 1), if g(m, 1) == "1" { "" } else { "s" }))
    })
}

fn list_or_number(run: &str) -> Option<String> {
    let number = |x: &str| {
        let groups: Vec<&str> = x.split(',').collect();
        groups[0].chars().count() <= 3 && groups[1..].iter().all(|y| y.chars().count() == 3)
    };
    if run.split('-').all(number) && run.matches('-').count() <= 1 {
        return None; // 1,000,000 or 50,000-100,000
    }
    Some(run.split(',').collect::<Vec<_>>().join(", "))
}

pub(super) fn en_list(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?<=\w)-\[(\d+(?:-\d+)?(?:,\s?\d+(?:-\d+)?){2,})\]"), &t, r" \1");
    let t = c.sub(&rx(r"(?<=[(\[])(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)+)(?=[)\]])"), &t, |m| list_or_number(&m[0]));
    c.sub(&rx(r"(?<![\w.,/-])\d+(?:-\d+)?(?:,\d+(?:-\d+)?){2,}(?![\w,/-]|\.\d)"), &t, |m| list_or_number(&m[0]))
}

const VERSION_CUE: &str = r"(?:v|V|version|Version|ver\.|Python|python|iOS|macOS|OS|Android|Windows|Ubuntu|Debian|Node|Java|Rust|Go|Chrome|Firefox|Safari|Kotlin|Swift|release|Release|update|Update|firmware|build|Build|API|SDK|PHP|Perl|Ruby|GCC|CUDA|cuDNN|PyTorch|TensorFlow)";

fn version_part(p: &str) -> String {
    if p == "0" { "oh".into() } else { py_int_str(p) }
}

pub(super) fn en_version(t: T, c: &mut Ctx) -> T {
    let t = c.sub(&rx(&format!(r"(?<![\w.])({VERSION_CUE}\s?)?(\d+(?:\.\d+){{2,3}})(?![\w]|\.\d)")), &t, |m| {
        let parts: Vec<&str> = g(m, 2).split('.').collect();
        let cue = g(m, 1);
        if cue.is_empty() && parts.iter().any(|p| p.chars().count() > 2) {
            return None; // 192.168.1.1, 555.555.5555: addresses and phone numbers
        }
        if parts.len() == 3
            && cue.is_empty()
            && py_int(parts[0]) <= 31
            && py_int(parts[1]) <= 31
            && [2, 4].contains(&parts[2].chars().count())
        {
            return None;
        }
        Some(format!("{cue}{}", parts.iter().map(|p| version_part(p)).collect::<Vec<_>>().join(" point ")))
    });
    c.sub(&rx(&format!(r"(?<![\w.])({VERSION_CUE}\s?)(\d+\.\d+)(?![\w]|\.\d)")), &t, |m| {
        Some(format!("{}{}", g(m, 1), g(m, 2).split('.').map(version_part).collect::<Vec<_>>().join(" point ")))
    })
}

const RANGE_BEFORE: &str = r"(?:pages?|pp\.?|ages?|aged|from|between|chapters?|ch\.|verses?|sections?|items?|rows?|lines?|steps?|grades?|levels?|seasons?|episodes?|weeks?|days?|years?|nos?\.?|numbers?|sizes?|range[sd]?|scored?|won|lost|beat|defeated|record|went|final|score|lead|led|trail(?:ed|ing)?|split|vote[sd]?|ratio)";
const MATH_BEFORE: &str =
    r"(?:what\s+is|what's|calculate|compute|solve|evaluate|equals|plus|minus|times|divided\s+by|subtract|is\s+it)";
const MATH_AFTER: &str = r"(?:is|equals|=|gives|makes|leaves)\s+-?\d";

/// `float(s)` for digits with an optional point (Unicode digits allowed, as Python's `float`).
fn py_float(s: &str) -> Option<f64> {
    let (int, frac) = s.split_once('.').unwrap_or((s, ""));
    let ascii = |x: &str| -> String {
        x.chars()
            .map(|ch| {
                if ch.is_ascii_digit() {
                    ch
                } else {
                    char::from_digit(py_int_str(&ch.to_string()).parse::<u32>().unwrap_or(0), 10).unwrap_or('0')
                }
            })
            .collect()
    };
    let text = if s.contains('.') { format!("{}.{}", ascii(int), ascii(frac)) } else { ascii(int) };
    text.parse().ok()
}

pub(super) fn en_range(t: T, c: &mut Ctx) -> T {
    let num = r"[$£€¥]?(?:(?<![^\s(\[])-)?\d+(?:,\d{3})*(?:\.\d+)?";
    let t = c.sub_tpl(
        &rx(&format!(r"(?:(?<![\w.,–-])|(?<=[A-Za-z]{{2}},))({num})(%|°[CF]?)?\s*[–](?!-)\s*({num})(?![\d–]|-\d)")),
        &t,
        r"\1\2 to \3",
    );
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,–-])({num})(%)-({num}%)")), &t, r"\1\2 to \3");
    let t = c.sub_tpl(
        &rx(r"(?<=\d)–(?=(?:January|February|March|April|May|June|July|August|September|October|November|December)\b)"),
        &t,
        " to ",
    );
    let t = c.sub_tpl(&rx(r"(?<=\d)\s+–\s+(?=[A-Za-z])"), &t, " — ");
    let t = c.sub(&rx(&format!(r"(?<![\w.,/:-])({num})([ \t]*)-([ \t]*)({num})(?![\w-]|\.\d|,\d)")), &t, |m| {
        let (a, sp1, sp2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let strip = |x: &str| x.trim_start_matches(|ch| "$£€¥-".contains(ch)).replace(',', "");
        let (aa, bb) = (strip(a), strip(b));
        let w = m.get(0).expect("group 0");
        if chars_after(&t, w.end(), 60).split('\n').next().unwrap_or("").contains('=') {
            return None; // unspaced equations (10-5=5) stay with the grammar
        }
        let before0 = chars_before(&t, w.start(), 40).to_lowercase();
        if sp1.is_empty() && sp2.is_empty() {
            if full(r"\d{3}", &aa) && full(r"\d{4}", &bb) && a == aa {
                let tail = chars_before(&before0, before0.len(), 6);
                if search(r"[\d)]\s*[-.]?\s*$", &before0) || search(r"\+\d", tail) {
                    return None; // (555) 123-4567: the area code is in front
                }
                if search(&format!(r"\b{RANGE_BEFORE}\s*$"), &before0) {
                    return Some(format!("{a} to {b}"));
                }
                let spaced = |x: &str| x.chars().map(String::from).collect::<Vec<_>>().join(" ");
                return Some(format!("{}, {}", spaced(&aa), spaced(&bb)));
            }
            if full(r"\d{5}", &aa) && full(r"\d{4}", &bb) {
                return None;
            }
            if full(r"\d{4}", &aa) && full(r"\d{2}", &bb) {
                return None;
            }
        }
        if full(r"\d{4}", &aa) && full(r"\d{4}", &bb) {
            return None;
        }
        let before = chars_before(&t, w.start(), 40).to_lowercase();
        let after_ = chars_after(&t, w.end(), 30);
        let word = if search(&format!(r"{MATH_BEFORE}\s*$"), &before)
            || matches_at_start(&format!(r"\s*{MATH_AFTER}"), after_)
        {
            "minus"
        } else if search(&format!(r"\b{RANGE_BEFORE}\s*(?:of\s+|was\s+|is\s+)?$"), &before)
            || matches_at_start(r"\s*(?:%|°|[a-zA-Z])", after_)
        {
            "to"
        } else {
            let ascending = match (py_float(&bb), py_float(&aa)) {
                (Some(x), Some(y)) => x > y,
                _ => true,
            };
            let spaced = !sp1.is_empty() && !sp2.is_empty();
            if !spaced && !ascending {
                return None; // 978-0, 10-5 with nothing around it
            }
            if spaced { "minus" } else { "to" }
        };
        Some(format!("{a} {word} {b}"))
    });
    c.sub_tpl(&rx(r"(?<![\w.])([a-zA-Z]) - (?=\d)"), &t, r"\1 minus ")
}

pub(super) fn en_ratio(t: T, c: &mut Ctx) -> T {
    c.sub(&rx(r"(?<![\w:.])(\d{1,3}):(\d{1,3})(?![\w:]|\.\d)"), &t, |m| {
        let w = m.get(0).expect("group 0");
        let cue = matches_at_start(
            r"\s+(?:ratio|split|mix|odds|aspect|scale|margin|majority|lead|win|victory|vote)",
            &t[w.end()..],
        ) || search(r"(?i)\b(?:ratio|odds|aspect ratio|scale|mix|split)\s+(?:of\s+)?$", &t[..w.start()]);
        cue.then(|| format!("{} to {}", g(m, 1), g(m, 2)))
    })
}

pub(super) fn en_feet(t: T, c: &mut Ctx) -> T {
    let t = c.sub(&rx(r#"(?<![\w.])(\d+)\s?[′'](?:\s?(\d+(?:\.\d+)?)\s?(?:″|"|''))"#), &t, |m| {
        let (a, b) = (g(m, 1), g(m, 2));
        if matches_at_start(r"\s*(?:tall|high|in height)\b", &t[m.get(0).expect("group 0").end()..]) {
            return Some(format!("{a} foot {b}"));
        }
        Some(format!("{a} {} {b} {}", if a == "1" { "foot" } else { "feet" }, if b == "1" { "inch" } else { "inches" }))
    });
    let t = c.sub(&rx(r"(?<![\w.])(\d+(?:\.\d+)?)\s?′(?![A-Za-z])"), &t, |m| {
        Some(format!("{} {}", g(m, 1), if g(m, 1) == "1" { "foot" } else { "feet" }))
    });
    let t = c.sub(&rx(r"(?<![\w.])(\d+(?:\.\d+)?)\s?″"), &t, |m| {
        Some(format!("{} {}", g(m, 1), if g(m, 1) == "1" { "inch" } else { "inches" }))
    });
    c.sub_tpl(&rx(r"(\d+\s?ft\.?\s+\d+)\s?in\b\.?"), &t, r"\1 inches")
}

/// (pattern after a number, singular, plural); `None` is cal / kcal.
const UNITS: &[(&str, Option<(&str, &str)>)] = &[
    (
        r"Mb(?!ps)(?=\s+(?:per|a|/)\s*(?:second|sec|s)\b|/s\b|\s+(?:connection|link|line|speed|bandwidth|network|internet|plan|fiber|broadband|uplink|downlink|download|upload|Ethernet|LAN|WAN|port|modem)\b)",
        Some(("megabit", "megabits")),
    ),
    (
        r"Gb(?!ps)(?=\s+(?:per|a|/)\s*(?:second|sec|s)\b|/s\b|\s+(?:connection|link|line|speed|bandwidth|network|internet|plan|fiber|broadband|uplink|downlink|download|upload|Ethernet|LAN|WAN|port|modem)\b)",
        Some(("gigabit", "gigabits")),
    ),
    (r"MB(?!/|ps)", Some(("megabyte", "megabytes"))),
    (r"GB(?!/|ps)", Some(("gigabyte", "gigabytes"))),
    (r"TB(?!/)", Some(("terabyte", "terabytes"))),
    (r"[Kk]B(?!/)", Some(("kilobyte", "kilobytes"))),
    (r"m[lL]", Some(("milliliter", "milliliters"))),
    (r"ms", Some(("millisecond", "milliseconds"))),
    (r"hrs?\.?", Some(("hour", "hours"))),
    (r"mins\.?", Some(("minute", "minutes"))),
    (r"secs\.?", Some(("second", "seconds"))),
    (r"yrs?\.?", Some(("year", "years"))),
    (r"mos\.?", Some(("month", "months"))),
    (r"wks?\.?", Some(("week", "weeks"))),
    (r"tbsp\.?|Tbsp\.?|T(?=\s+(?:of|butter|sugar|oil|flour|salt))", Some(("tablespoon", "tablespoons"))),
    (r"tsp\.?", Some(("teaspoon", "teaspoons"))),
    (r"¢", Some(("cent", "cents"))),
    (r"[\x{2126}\x{3A9}]", Some(("ohm", "ohms"))),
    (r"kΩ", Some(("kilohm", "kilohms"))),
    (r"MΩ", Some(("megohm", "megohms"))),
    (r"‰", Some(("per mille", "per mille"))),
    (r"dB", Some(("decibel", "decibels"))),
    (r"fps", Some(("FPS", "FPS"))),
    (r"mm", Some(("millimeter", "millimeters"))),
    (r"[μµ]m", Some(("micrometer", "micrometers"))),
    (r"nm", Some(("nanometer", "nanometers"))),
    (r"dL", Some(("deciliter", "deciliters"))),
    (r"c[lL]", Some(("centiliter", "centiliters"))),
    (r"gal", Some(("gallon", "gallons"))),
    (r"qt", Some(("quart", "quarts"))),
    (r"HRS", Some(("hour", "hours"))),
    (r"kHz", Some(("kilohertz", "kilohertz"))),
    (r"mW", Some(("milliwatt", "milliwatts"))),
    (r"MW", Some(("megawatt", "megawatts"))),
    (r"GW", Some(("gigawatt", "gigawatts"))),
    (r"TW", Some(("terawatt", "terawatts"))),
    (r"kWh", Some(("kilowatt hour", "kilowatt hours"))),
    (r"Wh", Some(("watt hour", "watt hours"))),
    (r"mV", Some(("millivolt", "millivolts"))),
    (r"kV", Some(("kilovolt", "kilovolts"))),
    (r"mA", Some(("milliamp", "milliamps"))),
    (r"mAh", Some(("milliamp hour", "milliamp hours"))),
    (r"kPa", Some(("kilopascal", "kilopascals"))),
    (r"MPa", Some(("megapascal", "megapascals"))),
    (r"hPa", Some(("hectopascal", "hectopascals"))),
    (r"psi", Some(("P S I", "P S I"))),
    (r"atm", Some(("atmosphere", "atmospheres"))),
    (r"kph|kmh", Some(("kilometer per hour", "kilometers per hour"))),
    (r"k?cal", None),
    (r"kJ", Some(("kilojoule", "kilojoules"))),
    (r"mmol", Some(("millimole", "millimoles"))),
    (r"[μµ]mol", Some(("micromole", "micromoles"))),
    (r"ha", Some(("hectare", "hectares"))),
    (r"bps", Some(("bit per second", "bits per second"))),
    (r"kbps", Some(("kilobit per second", "kilobits per second"))),
    (r"Gbps", Some(("gigabit per second", "gigabits per second"))),
    (r"px", Some(("pixel", "pixels"))),
    (r"dpi", Some(("D P I", "D P I"))),
    (r"ppm", Some(("part per million", "parts per million"))),
    (r"ppb", Some(("part per billion", "parts per billion"))),
    (
        r"g(?=\s*(?:$|[.,;:!?)](?![A-Za-z])|\s+(?:of|per|protein|fat|fiber|fibre|sugars?|carbs?|carbohydrates?|salt|sodium|each|serving|a day|daily)\b))",
        Some(("gram", "grams")),
    ),
    (
        r"(?<=\s)(?<!\d0\s)(?<!\d\d0\s)s(?=\s*(?:$|[.,;:!?)](?![A-Za-z]))|\s+(?:to|and|or|per|after|before|later|long|each|apart|total|intervals?|delay)\b)",
        Some(("second", "seconds")),
    ),
    (
        r"[Ll](?=\s*(?:$|[.,;:!?)](?![A-Za-z]))|\s+(?:of|bottles?|tanks?|jugs?|containers?|engines?|per|each|water)\b)",
        Some(("liter", "liters")),
    ),
    (
        r"V(?=\s*(?:$|[.,;:!?)](?![A-Za-z]))|\s+(?:batter(?:y|ies)|supply|power|DC|AC|charger|adapter|rail|output|input|outlet|socket|system|motor|lamp|bulb|LED|cell|line)\b)",
        Some(("volt", "volt")),
    ),
    (
        r"W(?=\s+(?:bulbs?|LEDs?|lamps?|chargers?|power|output|motors?|lasers?|amplifiers?|amps?|speakers?|supply|heaters?|panels?|solar|equivalent)\b)",
        Some(("watt", "watt")),
    ),
];

/// Compound-unit words (X/Y after a number), in the prototype's order.
const UNIT_WORDS: [(&str, &str); 59] = [
    ("mm", "millimeter"),
    ("cm", "centimeter"),
    ("m", "meter"),
    ("km", "kilometer"),
    ("μm", "micrometer"),
    ("µm", "micrometer"),
    ("nm", "nanometer"),
    ("mg", "milligram"),
    ("g", "gram"),
    ("kg", "kilogram"),
    ("μg", "microgram"),
    ("µg", "microgram"),
    ("ng", "nanogram"),
    ("mL", "milliliter"),
    ("ml", "milliliter"),
    ("L", "liter"),
    ("l", "liter"),
    ("dL", "deciliter"),
    ("s", "second"),
    ("sec", "second"),
    ("ms", "millisecond"),
    ("min", "minute"),
    ("h", "hour"),
    ("hr", "hour"),
    ("d", "day"),
    ("mol", "mole"),
    ("mmol", "millimole"),
    ("μmol", "micromole"),
    ("µmol", "micromole"),
    ("MB", "megabyte"),
    ("GB", "gigabyte"),
    ("KB", "kilobyte"),
    ("kB", "kilobyte"),
    ("TB", "terabyte"),
    ("Mb", "megabit"),
    ("Gb", "gigabit"),
    ("W", "watt"),
    ("kW", "kilowatt"),
    ("Hz", "hertz"),
    ("Pa", "pascal"),
    ("kPa", "kilopascal"),
    ("N", "newton"),
    ("J", "joule"),
    ("kJ", "kilojoule"),
    ("cal", "calorie"),
    ("kcal", "kilocalorie"),
    ("ft", "foot"),
    ("in", "inch"),
    ("mi", "mile"),
    ("yd", "yard"),
    ("lb", "pound"),
    ("oz", "ounce"),
    ("gal", "gallon"),
    ("mcg", "microgram"),
    ("yr", "year"),
    ("wk", "week"),
    ("mo", "month"),
    ("m2", "square meter"),
    ("m²", "square meter"),
];
const UNIT_WORDS_3: [(&str, &str); 2] = [("m3", "cubic meter"), ("m³", "cubic meter")];
const IRREGULAR: [(&str, &str); 5] = [
    ("foot", "feet"),
    ("inch", "inches"),
    ("hertz", "hertz"),
    ("square meter", "square meters"),
    ("cubic meter", "cubic meters"),
];
const FRACS: &str = "½¼¾⅓⅔⅛⅜⅝⅞";
const RES: [(&str, &str); 8] = [
    ("240", "two forty"),
    ("360", "three sixty"),
    ("480", "four eighty"),
    ("720", "seven twenty"),
    ("1080", "ten eighty"),
    ("1440", "fourteen forty"),
    ("2160", "twenty one sixty"),
    ("4320", "forty three twenty"),
];

static NOT_NOUN: LazyLock<HashSet<&str>> = LazyLock::new(|| {
    "a an the and or but nor of in on at to for from by with per each is was are were be been being will would can \
     could should may might must has had have do does did that which who whom than as if so more less over under into \
     onto off up down out worth apiece total plus minus then too also only just now later ago back away today tomorrow \
     yesterday already still yet ever never cash bucks usd it this these those there here when while because thousand \
     million billion trillion he she we they you i me him us them"
        .split_whitespace()
        .collect()
});

fn unit_word(k: &str) -> &'static str {
    UNIT_WORDS.iter().chain(UNIT_WORDS_3.iter()).find(|(a, _)| *a == k).map(|(_, v)| *v).expect("unit key")
}

fn plur<'a>(n: &str, s: &'a str, p: &'a str) -> &'a str {
    if n == "1" || n == "1.0" || FRACS.contains(n) { s } else { p }
}

pub(super) fn en_units(t: T, c: &mut Ctx) -> T {
    let amount = format!(r"(\d+(?:\.\d+)?|\d*[{FRACS}])");
    let keys: Vec<&str> = UNIT_WORDS.iter().chain(UNIT_WORDS_3.iter()).map(|(k, _)| *k).collect();
    let keys = alt_by_len(&keys);
    let t = c.sub(&rx(&format!(r"(?<![\w.]){amount}\s?({keys})/({keys})(2|²)?(?![\w/])")), &t, |m| {
        let (n, a, b) = (g(m, 1), unit_word(g(m, 2)), unit_word(g(m, 3)));
        let pl = if n == "1" || n == "1.0" {
            a.to_string()
        } else {
            lookup(&IRREGULAR, a).map_or_else(|| format!("{a}s"), str::to_string)
        };
        Some(format!("{} {pl} per {b}{}", commas(n), if g(m, 4).is_empty() { "" } else { " squared" }))
    });
    let mut t = c.sub_tpl(&rx(&format!(r"(?<=\d)(\s?(?:{keys}|miles|feet|meters|kilometers))/(?=\d)")), &t, r"\1, ");
    let adjectival = |t: &str, m: &Captures<'_, str>| -> bool {
        let w = m.get(0).expect("group 0");
        let Some(nxt) = caps(r"[ \t]+([a-z][a-z-]+)\b", &t[w.end()..]) else { return false };
        search(r"(?i)\b(?:a|an|the|this|that|one|each|every|per)\s+$", &t[..w.start()])
            && !NOT_NOUN.contains(g(&nxt, 1))
    };
    // “25 mins.” at the end of a sentence: the abbreviation's dot was also the full stop, keep one
    let sentence_dot = |t: &str, m: &Captures<'_, str>| -> &'static str {
        let w = m.get(0).expect("group 0");
        if w.as_str().ends_with('.') && matches_at_start(r"\s*$|\s+[A-Z]", &t[w.end()..]) { "." } else { "" }
    };
    // 0900 hrs → oh nine hundred hours; at 1430 hours → fourteen thirty hours
    let cur = t.clone();
    t = c.sub(&rx(r"(?<![\w.:,])([0-2][0-9])([0-5][0-9])\s?(?:hrs?\.?|hours|HRS)(?![A-Za-z/])"), &cur, |m| {
        let (hh, mm) = (g(m, 1), g(m, 2));
        let w = m.get(0).expect("group 0");
        if py_int(hh) > 23
            || (!hh.starts_with('0')
                && !search(r"(?i)\b(?:at|by|until|till|from|before|after|since|around)\s+$", &cur[..w.start()]))
        {
            return None; // 1500 hours of training is a duration
        }
        let oh = |s: &str| if s.starts_with('0') { "oh " } else { "" };
        let hour = if hh == "00" {
            (if mm != "00" { "zero zero" } else { "zero" }).to_string()
        } else {
            format!("{}{}", oh(hh), number_words(py_int(hh) as i128, false))
        };
        let minute = if mm == "00" {
            "hundred".to_string()
        } else {
            format!("{}{}", oh(mm), number_words(py_int(mm) as i128, false))
        };
        Some(format!("{hour} {minute} hours{}", sentence_dot(&cur, m)))
    });
    for (pat, words) in UNITS {
        let cur = t.clone();
        t = match words {
            None => c.sub(&rx(&format!(r"(?<![\w.]){amount}(\s?)(k?)cal(?![A-Za-z/])")), &cur, |m| {
                Some(format!(
                    "{} {}{}",
                    commas(g(m, 1)),
                    if g(m, 3).is_empty() { "" } else { "kilo" },
                    plur(g(m, 1), "calorie", "calories")
                ))
            }),
            Some((s, p)) => c.sub(&rx(&format!(r"(?<![\w.]){amount}(\s?)({pat})(?![A-Za-z/])")), &cur, |m| {
                Some(format!(
                    "{} {}{}",
                    commas(g(m, 1)),
                    if adjectival(&cur, m) { *s } else { plur(g(m, 1), s, p) },
                    sentence_dot(&cur, m)
                ))
            }),
        };
    }
    let res = RES.iter().map(|(k, _)| *k).collect::<Vec<_>>().join("|");
    let t = c.sub(&rx(&format!(r"(?<![\w.])({res})p\b")), &t, |m| Some(format!("{} p", lookup(&RES, g(m, 1))?)));
    let t = c.sub_tpl(&rx(r"(?<![\w.])(\d+(?:\.\d+)?)\s?ML\b"), &t, r"\1 M L");
    let t = c.sub(&rx(r"(?<![\w:.])(\d{1,2}):(\d\d):(\d\d)(?![\w:]|\.\d)"), &t, |m| {
        let (h, mi, se) = (py_int(g(m, 1)), py_int(g(m, 2)), py_int(g(m, 3)));
        let parts: Vec<String> = [(h, "hour"), (mi, "minute"), (se, "second")]
            .iter()
            .filter(|(v, _)| *v != 0)
            .map(|(v, w)| format!("{v} {}", if *v == 1 { w.to_string() } else { format!("{w}s") }))
            .collect();
        let w = m.get(0).expect("group 0");
        if matches_at_start(r"\s*(?:[aApP]\.?[mM]\b\.?|[A-Z]{2,4}\b|[a-z]\.[a-z]\.)", &t[w.end()..])
            || search(r"\b(?:at|by|until|from|since)\s+$", &t[..w.start()])
        {
            return None; // 10:00:00 p.m. EST is a clock time
        }
        (!parts.is_empty() && (mi == 0 || se == 0)).then(|| parts.join(" "))
    });
    let t = c.sub(&rx(r"(?<![\w.])(\d+(?:\.\d+)?)\s?(km|mi|m)/h\b"), &t, |m| {
        Some(format!("{} {} per hour", g(m, 1), g(m, 2)))
    });
    let t = c.sub(
        &rx(r"(?<![\w.$£€¥])(\d+(?:\.\d+)?) m(?=\s*(?:$|[.,;:!?)]|\s(?:long|wide|tall|high|deep|away|apart|of|from|in|above|below|across|thick|to|by|and|or)\b))"),
        &t,
        |m| Some(format!("{} {}", commas(g(m, 1)), plur(g(m, 1), "meter", "meters"))),
    );
    let t = c.sub_tpl(&rx(r"(?<![\w.$£€¥])(\d+(?:\.\d+)?)M(?=\s+[a-z])"), &t, r"\1 million");
    c.sub_tpl(&rx(r"(?<![\w.$£€¥])(\d+(?:\.\d+)?)k(?![\w])"), &t, r"\1 thousand")
}

pub(super) fn en_compound_number(t: T, c: &mut Ctx) -> T {
    c.sub(&rx(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+)(?=-[A-Za-z])"), &t, |m| Some(g(m, 1).replace(',', "")))
}

const DETERMINERS: &str = "(?:a|an|the|this|that|each|every|one|its|his|her|their|our|my|your|whose)";

pub(super) fn en_money_adj(t: T, c: &mut Ctx) -> T {
    const CUR: [(&str, &str); 5] = [("$", "dollar"), ("£", "pound"), ("€", "euro"), ("¥", "yen"), ("₹", "rupee")];
    const SCALE: [(&str, &str); 7] = [
        ("k", "thousand"),
        ("K", "thousand"),
        ("M", "million"),
        ("m", "million"),
        ("B", "billion"),
        ("b", "billion"),
        ("bn", "billion"),
    ];
    let re = rx(&format!(
        r"(?i)\b({DETERMINERS})[ \t]+([$£€¥₹])(\d[\d,]*(?:\.\d+)?)([ \t]?(?:thousand|million|billion|trillion)|k|K|M|m|B|bn)?[ \t]+([a-z][a-z-]+)\b"
    ));
    c.sub(&re, &t, |m| {
        let nxt = g(m, 5);
        if NOT_NOUN.contains(nxt.to_lowercase().as_str()) {
            return None;
        }
        let sc = py_strip(g(m, 4));
        let sc = lookup(&SCALE, sc).unwrap_or(sc);
        Some(format!(
            "{} {}{} {} {nxt}",
            g(m, 1),
            commas(g(m, 3)),
            if sc.is_empty() { String::new() } else { format!(" {sc}") },
            lookup(&CUR, g(m, 2))?
        ))
    })
}

pub(super) fn en_money_after(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"(?<![\w.])(\d+(?:\.\d+)?)\s?([€£¥])(?!\w)"), &t, r"\2\1")
}

const DAYS: [(&str, &str); 10] = [
    ("Mon", "Monday"),
    ("Tue", "Tuesday"),
    ("Tues", "Tuesday"),
    ("Wed", "Wednesday"),
    ("Thu", "Thursday"),
    ("Thur", "Thursday"),
    ("Thurs", "Thursday"),
    ("Fri", "Friday"),
    ("Sat", "Saturday"),
    ("Sun", "Sunday"),
];
const MONTHS: [(&str, &str); 12] = [
    ("Jan", "January"),
    ("Feb", "February"),
    ("Mar", "March"),
    ("Apr", "April"),
    ("Jun", "June"),
    ("Jul", "July"),
    ("Aug", "August"),
    ("Sep", "September"),
    ("Sept", "September"),
    ("Oct", "October"),
    ("Nov", "November"),
    ("Dec", "December"),
];
const RISKY_DAY: [&str; 4] = ["Mon", "Wed", "Sat", "Sun"];
const RISKY_MONTH: [&str; 5] = ["Jan", "Mar", "Jun", "Jul", "Aug"];
const TITLES: [(&str, &str); 15] = [
    ("Ms", "Miz"),
    ("Mx", "Mix"),
    ("Sen", "Senator"),
    ("Rep", "Representative"),
    ("Prof", "Professor"),
    ("Gen", "General"),
    ("Col", "Colonel"),
    ("Pres", "President"),
    ("Supt", "Superintendent"),
    ("Insp", "Inspector"),
    ("Det", "Detective"),
    ("Hon", "Honorable"),
    ("Amb", "Ambassador"),
    ("Adm", "Admiral"),
    ("Cmdr", "Commander"),
];
const BEFORE_NUM: [(&str, &str); 23] = [
    ("Fig", "Figure"),
    ("fig", "figure"),
    ("Figs", "Figures"),
    ("Eq", "Equation"),
    ("eq", "equation"),
    ("pp", "pages"),
    ("p", "page"),
    ("Vol", "Volume"),
    ("vol", "volume"),
    ("Ch", "Chapter"),
    ("ch", "chapter"),
    ("Sec", "Section"),
    ("sec", "section"),
    ("Art", "Article"),
    ("Ex", "Example"),
    ("No", "number"),
    ("no", "number"),
    ("Nos", "numbers"),
    ("Para", "Paragraph"),
    ("para", "paragraph"),
    ("Tab", "Table"),
    ("Thm", "Theorem"),
    ("Def", "Definition"),
];
const STREETS: [(&str, &str); 15] = [
    ("St", "Street"),
    ("Dr", "Drive"),
    ("Ave", "Avenue"),
    ("Av", "Avenue"),
    ("Blvd", "Boulevard"),
    ("Rd", "Road"),
    ("Ln", "Lane"),
    ("Ct", "Court"),
    ("Pl", "Place"),
    ("Pkwy", "Parkway"),
    ("Hwy", "Highway"),
    ("Ter", "Terrace"),
    ("Cir", "Circle"),
    ("Sq", "Square"),
    ("Hts", "Heights"),
];
const TITLE_NOUNS: [&str; 21] = [
    "Secretary",
    "Minister",
    "President",
    "Director",
    "Professor",
    "Chairman",
    "Chair",
    "Dean",
    "Chief",
    "Head",
    "Senator",
    "Governor",
    "Mayor",
    "Ambassador",
    "Commissioner",
    "Chancellor",
    "Superintendent",
    "Principal",
    "Physician",
    "Surgeon",
    "Vet",
];
const STARTERS: [&str; 24] = [
    "The", "Then", "It", "We", "I", "He", "She", "They", "This", "That", "There", "You", "A", "An", "In", "On", "At",
    "But", "And", "So", "If", "When", "After", "Before",
];

fn keys<'a>(map: &[(&'a str, &str)]) -> Vec<&'a str> {
    map.iter().map(|(k, _)| *k).collect()
}

fn is_starter(w: &str) -> bool {
    STARTERS.contains(&w)
}

fn day_rx() -> String {
    alt_by_len(&keys(&DAYS))
}

fn keep_period(rest: &str) -> &'static str {
    if matches_at_start(r#"\s*(?:$|[A-Z"'(])"#, rest) { "." } else { "" }
}

pub(super) fn en_abbrev(t: T, c: &mut Ctx) -> T {
    let days = day_rx();
    let t = c.sub(&rx(&format!(r"\b({days})\.?(\s*(?:[-–]|through|thru|to|and|or|&)\s*)({days})\b(\.?)")), &t, |m| {
        let sep = py_strip(g(m, 2));
        let end = m.get(0).expect("group 0").end();
        Some(format!(
            "{}{}{}{}",
            lookup(&DAYS, g(m, 1))?,
            if "-–".contains(sep) { " to " } else { g(m, 2) },
            lookup(&DAYS, g(m, 3))?,
            if g(m, 4).is_empty() { "" } else { keep_period(&t[end..]) }
        ))
    });
    let t = c.sub(&rx(&format!(r"\b({days})(\.?)(?![\w'])")), &t, |m| {
        let d = g(m, 1);
        let rest = &t[m.get(0).expect("group 0").end()..];
        if RISKY_DAY.contains(&d) && !matches_at_start(r"\s*(?:\d|,|;|\(|[A-Z][a-z]{2}\.?\s*\d|[a-z])", rest) {
            return None;
        }
        let full_day = lookup(&DAYS, d)?;
        if !g(m, 2).is_empty() {
            Some(format!("{full_day}{}", keep_period(rest)))
        } else {
            matches_at_start(r"\s*\d", rest).then(|| full_day.to_string())
        }
    });
    let months = alt_by_len(&keys(&MONTHS));
    let t = c.sub(&rx(&format!(r"\b({months})\.(?!\w)")), &t, |m| {
        let mo = g(m, 1);
        let w = m.get(0).expect("group 0");
        let (rest, before_) = (&t[w.end()..], &t[..w.start()]);
        if RISKY_MONTH.contains(&mo)
            && !(matches_at_start(r"\s*(?:\d|[a-z])", rest)
                || search(r"\b(?:in|of|since|until|by|from|early|late|mid|through|last|next|this)\s+$", before_))
        {
            return None;
        }
        Some(format!("{}{}", lookup(&MONTHS, mo)?, keep_period(rest)))
    });
    let titles = keys(&TITLES).join("|");
    let t = c.sub(&rx(&format!(r"\b(?:({titles})\.|(Ms|Mx))(?=\s+[A-Z][a-z])")), &t, |m| {
        let k = if g(m, 1).is_empty() { g(m, 2) } else { g(m, 1) };
        lookup(&TITLES, k).map(str::to_string)
    });
    let t = c.sub(&rx(r"\b([A-Z][a-z]+\s+)Sr\.(?=\s*(?:$|[,;:!?)]|\s[a-z]|\s[A-Z]))"), &t, |m| {
        Some(format!("{}Senior{}", g(m, 1), keep_period(&t[m.get(0).expect("group 0").end()..])))
    });
    let before_num = alt_by_len(&keys(&BEFORE_NUM));
    let t = c.sub(&rx(&format!(r"\b({before_num})\.\s?(?=\d)")), &t, |m| {
        Some(format!("{} ", lookup(&BEFORE_NUM, g(m, 1))?))
    });
    let t = c.sub_tpl(&rx(r"\b[Aa]pprox\.?(?=\s)"), &t, "approximately");
    let streets = alt_by_len(&keys(&STREETS));
    c.sub(&rx(&format!(r"((?:\b[A-Z][a-z]+|\b\d+(?:st|nd|rd|th)?)\s+)({streets})\.(?!\w)")), &t, |m| {
        let rest = &t[m.get(0).expect("group 0").end()..];
        let (lead, abbr) = (g(m, 1), g(m, 2));
        if is_starter(py_strip(lead)) || (abbr == "Dr" && TITLE_NOUNS.contains(&py_strip(lead))) {
            return None;
        }
        if let Some(nxt) = caps(r"\s+([A-Z][a-z]+)(\.?)", rest)
            && !is_starter(g(&nxt, 1))
            && lookup(&STREETS, g(&nxt, 1)).is_none()
            && g(&nxt, 2).is_empty()
        {
            return match abbr {
                "St" => Some(format!("{lead}Saint")),
                "Dr" => Some(format!("{lead}Doctor")),
                _ => None,
            };
        }
        Some(format!("{lead}{}{}", lookup(&STREETS, abbr)?, keep_period(rest)))
    })
}

pub(super) fn en_slash_words(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?<![\w/])[wW]/[oO](?![\w/])"), &t, "without");
    let t = c.sub_tpl(&rx(r"(?<![\w/])w/(?=\s|[A-Za-z])\s?"), &t, "with ");
    let t = c.sub_tpl(&rx(r"(?i)\b(and)/(or)\b"), &t, r"\1 slash \2");
    let t = c.sub_tpl(
        &rx(r"(?i)\b(he|she|his|her|him|hers|himself|herself)/(he|she|his|her|him|hers|himself|herself|they|them|their)\b"),
        &t,
        r"\1 or \2",
    );
    let t = c.sub_tpl(&rx(r"\b[sS]/he\b"), &t, "she or he");
    let t = c.sub_tpl(&rx(r"(?<![\w/])[nN]/[aA](?![\w/])"), &t, "N A");
    c.sub_tpl(&rx(r"\b([A-Z]{2,})/(\d(?:\.\d)?)\b"), &t, r"\1 \2")
}

fn port_pairs(n: &str) -> String {
    let c: Vec<char> = n.chars().collect();
    let s = |a: usize, b: usize| c[a..b].iter().collect::<String>();
    if c[2] != '0' { format!("{} {}", s(0, 2), s(2, 4)) } else { format!("{} oh {}", s(0, 2), c[3]) }
}

fn highway(n: &str) -> String {
    let c: Vec<char> = n.chars().collect();
    if c[1] == '0' { format!("{} oh {}", c[0], c[2]) } else { format!("{} {}{}", c[0], c[1], c[2]) }
}

pub(super) fn en_reading_style(t: T, c: &mut Ctx) -> T {
    let t = c.sub(&rx(r"\b(ports?\s+)(\d{4})\b"), &t, |m| Some(format!("{}{}", g(m, 1), port_pairs(g(m, 2)))));
    let t = c.sub(
        &rx(r"\b(localhost|\d{1,3}(?:\.\d{1,3}){3}|[a-z0-9-]+\.(?:com|org|net|io|ai|dev|local))(:)(\d{4})\b"),
        &t,
        |m| Some(format!("{} {}", g(m, 1), port_pairs(g(m, 3)))),
    );
    let t = c.sub(&rx(r"\b(the\s+)(\d{3})(?=\s+(?:freeway|highway|interstate|expressway|turnpike)\b)"), &t, |m| {
        Some(format!("{}{}", g(m, 1), highway(g(m, 2))))
    });
    let t = c.sub(&rx(r"\b(I|US|SR|Route|Highway|Hwy\.?)([-\s])(\d{3})\b"), &t, |m| {
        Some(format!("{} {}", g(m, 1), highway(g(m, 3))))
    });
    let t = c.sub_tpl(&rx(r"\betc\.(?=\s+[a-z])"), &t, "etcetera");
    c.sub_tpl(&rx(r"(?m)^[ \t]*>[ \t]?(?=\d)"), &t, "more than ")
}

pub(super) fn en_coordinates(t: T, c: &mut Ctx) -> T {
    let re = rx(
        r#"(?<![\w.])(\d+(?:\.\d+)?)°\s?(?:(\d+(?:\.\d+)?)[′']\s?)?(?:(\d+(?:\.\d+)?)[″"]\s?)?([NSEW])(?![A-Za-z])"#,
    );
    c.sub(&re, &t, |m| {
        let (deg, mi, se) = (g(m, 1), g(m, 2), g(m, 3));
        let mut parts = vec![format!("{deg} degree{}", if deg == "1" { "" } else { "s" })];
        if !mi.is_empty() {
            parts.push(format!("{mi} minute{}", if mi == "1" { "" } else { "s" }));
        }
        if !se.is_empty() {
            parts.push(format!("{se} second{}", if se == "1" { "" } else { "s" }));
        }
        let dir = match g(m, 4) {
            "N" => "north",
            "S" => "south",
            "E" => "east",
            _ => "west",
        };
        Some(format!("{} {dir}", parts.join(" ")))
    })
}

pub(super) fn en_symbols(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?<![\w#&])#\s?(?=\d+(?:st|nd|rd|th)?\b)|№\s?(?=\d)"), &t, "number ");
    let t = c.sub_tpl(&rx(r"(?<![\w#])#(?=\s+of\b)"), &t, "number");
    let t = c.sub_tpl(&rx(r"(?<![\w#])([A-G])#(?=[\s,.;:!?)]|$)"), &t, r"\1 sharp");
    let t = c.sub_tpl(&rx(r"(?<![\w-])([A-DF])-(?=[\s,.;:!?)]|$)"), &t, r"\1 minus");
    let t = c.sub_tpl(&rx(r"\bTL;DR\b:?"), &t, "T L D R,");
    let t = c.sub_tpl(&rx(r"(?<=[A-Z]{2})&(?=[A-Z])|(?<=[A-Z])&(?=[A-Z]{2})"), &t, " and ");
    c.sub_tpl(&rx(r"(?<!\w)\.NET\b"), &t, "dot net")
}

const ROMAN: &str = r"(?:M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))";
const REGNAL: &str = "Henry|Elizabeth|Louis|George|Edward|Charles|James|William|Richard|John|Paul|Pius|Benedict|Leo|Gregory|Napoleon|Frederick|Philip|Peter|Catherine|Mary|Victoria|Ramesses|Ramses|Alexander|Henri|Felipe|Carlos|Carl|Gustav|Gustaf|Ivan|Nicholas|Clement|Innocent|Urban|Boniface|Constantine|Alfonso|Ferdinand|Isabella|Anne|Harald|Olaf|Christian|Haakon|Wilhelm|Otto|Rudolf|Leopold|Franz|Selim|Mehmed|Suleiman|Thutmose|Amenhotep|Rama|Ptolemy|Cleopatra|Darius|Xerxes|Cyrus|Antiochus|Herod|Sixtus|Julius|Adrian|Hadrian|Stephen|Malcolm|David|Robert|Kamehameha|Akbar|Shapur|Justinian|Basil|Michael|Andronikos|Manuel|Dmitri|Vasily|Sancho|Afonso|Juan|Martin|Celestine|Honorius|Callixtus|Calixtus|Eugene|Eugenius|Lucius|Felix|Sergius|Victor|Anastasius|Marcellus|Formosus|Pelagius|Theodore|Agapetus|Silvester|Sylvester|Valentinian|Theodosius|Leopold|Albert|Baudouin|Umberto|Vittorio|Emmanuel|Wilhelmina|Margrethe|Beatrix|Hirohito|Rudolph";
const CARDINAL_CTX: &str = r"Chapter|Part|Book|Volume|Vol\.|Act|Scene|Phase|Stage|Type|Class|Level|Section|Article|Title|Episode|Season|Round|Tier|Grade|Division|Series|Mark|Mk\.?|Apollo|Rocky|Super Bowl|WrestleMania|Final Fantasy|Grand Theft Auto|Star Wars Episode|Episode|Psalm|Canto|Annex|Appendix|Schedule|Category|Stage|Unit|Pt\.|Vatican|Pentium|Gemini|Saturn|Mercury|Voyager|Pioneer|Ranger|Surveyor|Luna|Soyuz|Falcon|Titan|Atlas|Delta|Mega Man|Street Fighter|Civilization|Halo|Fallout|Diablo|Resident Evil|Kingdom Hearts|Dragon Quest|Ys";

fn roman_value(ch: char) -> u128 {
    match ch {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        'C' => 100,
        'D' => 500,
        'M' => 1000,
        _ => 0,
    }
}

fn roman_to_int(s: &str) -> i128 {
    let c: Vec<char> = s.chars().collect();
    let mut total: i128 = 0;
    for (i, &a) in c.iter().enumerate() {
        let v = roman_value(a) as i128;
        match c.get(i + 1) {
            Some(&b) if roman_value(b) as i128 > v => total -= v,
            _ => total += v,
        }
    }
    total
}

fn plausible(num: &str) -> bool {
    !num.is_empty()
        && !num.contains(['D', 'M'])
        && (num.chars().count() > 1 || "IVX".contains(num))
        && roman_to_int(num) <= 100
}

fn number_words(n: i128, ordinal: bool) -> String {
    let s = n.to_string();
    english(&if ordinal { ordinal_digits(&s) } else { s })
}

pub(super) fn en_roman(t: T, c: &mut Ctx) -> T {
    let t = c.sub(&rx(r"\bWW(II|I|2|1)\b"), &t, |m| {
        Some(format!(
            "World War {}",
            match g(m, 1) {
                "2" => "II",
                "1" => "I",
                x => x,
            }
        ))
    });
    let t = c.sub(&rx(&format!(r"\b({REGNAL}) ({ROMAN})(?![\w'])")), &t, |m| {
        let num = g(m, 2);
        if !plausible(num) {
            return None;
        }
        let end = m.get(0).expect("group 0").end();
        if num == "I"
            && !matches_at_start(
                r"\s*(?:$|[,.;:!?)]|(?:and|or|of|died|became|ruled|reigned|married|was crowned)\b)",
                &t[end..],
            )
        {
            return None;
        }
        Some(format!("{} the {}", g(m, 1), number_words(roman_to_int(num), true)))
    });
    c.sub(&rx(&format!(r"\b({CARDINAL_CTX}) ({ROMAN})(?![\w'])")), &t, |m| {
        plausible(g(m, 2)).then(|| format!("{} {}", g(m, 1), number_words(roman_to_int(g(m, 2)), false)))
    })
}

const TENS: [&str; 9] =
    ["tens", "twenties", "thirties", "forties", "fifties", "sixties", "seventies", "eighties", "nineties"];

pub(super) fn en_decades(t: T, c: &mut Ctx) -> T {
    let t = c.sub(&rx(r"(?<![\w.])20([1-9])0s\b"), &t, |m| {
        let d = g(m, 1).parse::<usize>().ok()?;
        Some(format!("twenty {}", TENS[d - 1]))
    });
    let t = c.sub_tpl(&rx(r"(?<![\w.])((?:\d\d)?\d0)'s\b"), &t, r"\1s");
    let t = c.sub_tpl(&rx(r"\b(FY|CY)(\d{4})\b"), &t, r"\1 \2");
    let t = c.sub_tpl(&rx(r"\b([A-Z]{1,3})(\d{2,4})s\b"), &t, r"\1 \2s");
    c.sub(&rx(r"(?<![\w.'$£€¥,])(\d{1,4})s\b"), &t, |m| {
        let n = g(m, 1);
        let len = n.chars().count();
        if !n.ends_with('0') || len == 2 || len == 4 {
            return None; // 4s, 1818s: the grammar's “four S”; 20s, 1990s: the grammar's decades
        }
        let spoken = english(n);
        let mut words: Vec<String> = crate::text::py_split_ws(&spoken).into_iter().map(str::to_string).collect();
        let last = words.pop()?;
        let last = if let Some(stem) = last.strip_suffix('y') {
            format!("{stem}ies")
        } else if last.ends_with('x') || last.ends_with('s') {
            format!("{last}es")
        } else {
            format!("{last}s")
        };
        words.push(last);
        Some(words.join(" "))
    })
}

pub(super) fn en_space_after_period(t: T, c: &mut Ctx) -> T {
    let t = c.sub_tpl(&rx(r"(?:(?<=[A-Za-z0-9]{2})|(?<=^\d)|(?<=\n\d))\.(?=[A-Z][a-z]+\b(?![.(]))"), &t, ". ");
    c.sub_tpl(&rx(r"(?<=\b[A-Z][a-z]{2})(?<!http)(?<!mailto):(?=[a-z]{3,}\b)"), &t, ": ")
}

pub(super) fn en_url(t: T, c: &mut Ctx) -> T {
    c.sub_tpl(&rx(r"\bhttps?://(?:www\.)?(?=\w)"), &t, "")
}

pub(super) fn en_acronym_plural(t: T, c: &mut Ctx) -> T {
    c.sub(&rx(r"(?<![\w\x{E000}])([A-Z]{2,6}s)(?![\w\x{E001}'])"), &t, |m| Some(format!("\u{e000}{}\u{e001}", g(m, 1))))
}

pub(super) fn en_dates_slash(t: T, c: &mut Ctx) -> T {
    const MONTH_NAMES: [&str; 12] = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ];
    let dayname = format!(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|{})\.?,?", day_rx());
    let t = c.sub(&rx(&format!(r"\b({dayname})\s+(\d{{1,2}})/(\d{{1,2}})(?![\d/])")), &t, |m| {
        let (mo, d) = (py_int(g(m, 2)), py_int(g(m, 3)));
        if !((1..=12).contains(&mo) && (1..=31).contains(&d)) {
            return None;
        }
        let name = g(m, 1).trim_end_matches(['.', ',']);
        let full_day = lookup(&DAYS, name).unwrap_or(name);
        Some(format!("{full_day} {} {d}", MONTH_NAMES[mo as usize - 1]))
    });
    let t = c.sub_tpl(&rx(r"(?<![\w/])(\d+(?:\.\d+)?)/(\d+)(?=\s+(?:stars?|points?|rating)\b)"), &t, r"\1 out of \2");
    c.sub_tpl(&rx(r"\b(rated|scored|rating of|score of)\s+(\d+(?:\.\d+)?)/(\d+)(?![\d/])"), &t, r"\1 \2 out of \3")
}
