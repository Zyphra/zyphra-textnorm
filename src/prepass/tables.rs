//! The pre-pass tables (`data/prepass/`, written by `oracle/prepass_tables.py`): HTML character references as Python's
//! `html.unescape` reads them, and the emoji package's (2.14.1) names, shortcodes and tokenizer.

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

fn hex_str(cps: &str) -> String {
    cps.split_whitespace()
        .map(|h| char::from_u32(u32::from_str_radix(h, 16).expect("hex")).expect("code point"))
        .collect()
}

static HTML5: LazyLock<HashMap<&'static str, String>> = LazyLock::new(|| {
    include_str!("../../data/prepass/html5.tsv")
        .lines()
        .filter_map(|l| l.split_once('\t'))
        .map(|(k, v)| (k, hex_str(v)))
        .collect()
});

struct CharRefs {
    replace: HashMap<u32, String>,
    drop: HashSet<u32>,
}

static CHARREFS: LazyLock<CharRefs> = LazyLock::new(|| {
    let mut refs = CharRefs { replace: HashMap::new(), drop: HashSet::new() };
    for l in include_str!("../../data/prepass/html_charrefs.tsv").lines() {
        let f: Vec<&str> = l.split('\t').collect();
        let n = u32::from_str_radix(f[1], 16).expect("hex");
        match f[0] {
            "ref" => {
                refs.replace.insert(n, hex_str(f.get(2).copied().unwrap_or("")));
            }
            _ => {
                refs.drop.insert(n);
            }
        }
    }
    refs
});

/// `html.unescape` of one `&…;` reference.
pub(super) fn html_unescape(s: &str) -> String {
    let body = &s[1..];
    if let Some(num) = body.strip_prefix('#') {
        let (hex, digits) = match num.strip_prefix(['x', 'X']) {
            Some(d) => (true, d),
            None => (false, num),
        };
        let digits = digits.strip_suffix(';').unwrap_or(digits);
        let valid = if hex {
            digits.chars().all(|c| c.is_ascii_hexdigit())
        } else {
            digits.chars().all(|c| c.is_ascii_digit())
        };
        if digits.is_empty() || !valid {
            return s.to_string(); // html's reference pattern takes ASCII digits only
        }
        let n = u64::from_str_radix(digits, if hex { 16 } else { 10 }).unwrap_or(u64::MAX);
        if let Ok(n32) = u32::try_from(n)
            && let Some(r) = CHARREFS.replace.get(&n32)
        {
            return r.clone();
        }
        if (0xD800..=0xDFFF).contains(&n) || n > 0x10FFFF {
            return "\u{FFFD}".into();
        }
        if CHARREFS.drop.contains(&(n as u32)) {
            return String::new();
        }
        return char::from_u32(n as u32).map_or_else(|| "\u{FFFD}".into(), |c| c.to_string());
    }
    if let Some(v) = HTML5.get(body) {
        return v.clone();
    }
    for x in (2..body.len()).rev() {
        if let Some(v) = HTML5.get(&body[..x]) {
            return format!("{v}{}", &body[x..]);
        }
    }
    s.to_string()
}

struct Emoji {
    name: String,
    component: bool,
}

static EMOJI: LazyLock<HashMap<String, Emoji>> = LazyLock::new(|| {
    include_str!("../../data/prepass/emoji.tsv")
        .lines()
        .map(|l| {
            let f: Vec<&str> = l.split('\t').collect();
            (hex_str(f[0]), Emoji { name: f[1].to_string(), component: f[2] == "1" })
        })
        .collect()
});

static ALIAS: LazyLock<HashMap<&'static str, String>> = LazyLock::new(|| {
    include_str!("../../data/prepass/emoji_alias.tsv")
        .lines()
        .filter_map(|l| l.split_once('\t'))
        .map(|(k, v)| (k, hex_str(v)))
        .collect()
});

/// `emoji.emojize(shortcode, language="alias")` when it names an emoji.
pub(super) fn emoji_alias(shortcode: &str) -> Option<String> {
    ALIAS.get(shortcode).cloned()
}

fn textlike(s: &str) -> bool {
    let mut it = s.chars();
    let (Some(c), None) = (it.next(), it.next()) else { return false };
    "©®™‼⁉ℹⓂ〰〽㊗㊙➡".contains(c)
        || ('\u{2194}'..'\u{21AB}').contains(&c)
        || ('\u{2934}'..'\u{2936}').contains(&c)
        || ('\u{25AA}'..'\u{25FF}').contains(&c)
        || ('\u{2B05}'..'\u{2B08}').contains(&c)
}

/// The spoken name of an emoji: its CLDR short name and “emoji” (“Japan flag emoji”), its digit for a keycap, or
/// `None` for a text-style symbol (© ™ ↔ ▪ without U+FE0F) or anything that is not an emoji.
pub(super) fn emoji_name(e: &str) -> Option<String> {
    let base: String = e.chars().filter(|&c| c != '\u{FE0F}' && c != '\u{FE0E}').collect();
    if !base.is_empty() && textlike(&base) && !e.contains('\u{FE0F}') {
        return None;
    }
    let d = EMOJI.get(e).or_else(|| EMOJI.get(&base)).or_else(|| EMOJI.get(&format!("{base}\u{FE0F}")))?;
    if "©®™".contains(base.as_str()) {
        return None;
    }
    if e.contains('\u{20E3}') {
        return Some(base.replace('\u{20E3}', ""));
    }
    let skin = super::rx(r"_(?:light|medium-light|medium|medium-dark|dark)_skin_tone");
    let n = skin.replace_all(d.name.trim_matches(':'), "").replace('_', " ").replace(['“', '”'], "");
    let n = super::py_strip(&n).to_string();
    let flag = base.chars().all(|c| ('\u{1F1E6}'..='\u{1F1FF}').contains(&c))
        || base.chars().any(|c| ('\u{E0060}'..='\u{E007F}').contains(&c));
    let flag_word = if flag && !n.contains("flag") { " flag" } else { "" };
    Some(format!("{n}{flag_word} emoji"))
}

#[derive(Default)]
struct Node {
    next: HashMap<char, usize>,
    data: bool,
}

/// The emoji package's search tree: every emoji's code points, with `data` where one ends.
static TREE: LazyLock<Vec<Node>> = LazyLock::new(|| {
    let mut nodes = vec![Node::default()];
    for e in EMOJI.keys() {
        let mut at = 0;
        for c in e.chars() {
            at = match nodes[at].next.get(&c) {
                Some(&n) => n,
                None => {
                    nodes.push(Node::default());
                    let n = nodes.len() - 1;
                    nodes[at].next.insert(c, n);
                    n
                }
            };
        }
        nodes[at].data = true;
    }
    nodes
});

struct Token {
    chars: String,
    start: usize,
    end: usize,
    emoji: bool,
}

const ZWJ: char = '\u{200D}';

/// `emoji.emoji_list(text)`: each emoji as (byte start, byte end, its code points), from a port of the package's
/// `tokenize(text, keep_zwj=False)`, including its handling of ZWJ sequences that are not in the data.
pub(super) fn emoji_list(text: &str) -> Vec<(usize, usize, String)> {
    let tree = &*TREE;
    let s: Vec<char> = text.chars().collect();
    let mut byte = Vec::with_capacity(s.len() + 1);
    let mut b = 0;
    for c in &s {
        byte.push(b);
        b += c.len_utf8();
    }
    byte.push(b);
    let n = s.len();
    let mut out: Vec<Token> = Vec::new();
    let mut result: Vec<Token> = Vec::new();
    let mut ignore: HashSet<usize> = HashSet::new();
    let mut i = 0usize;
    while i < n {
        let mut consumed = false;
        let ch = s[i];
        if ignore.contains(&i) {
            i += 1;
            continue;
        } else if let Some(&first) = tree[0].next.get(&ch) {
            let mut j = i + 1;
            let mut node = first;
            while j < n {
                let Some(&nx) = tree[node].next.get(&s[j]) else { break };
                if ignore.contains(&j) {
                    break;
                }
                node = nx;
                j += 1;
            }
            if tree[node].data {
                result.push(Token { chars: s[i..j].iter().collect(), start: i, end: j, emoji: true });
                i = j - 1;
                consumed = true;
            }
        } else if ch == ZWJ
            && result.last().is_some_and(|t| EMOJI.contains_key(&t.chars))
            && i > 0
            && tree[0].next.contains_key(&s[i - 1])
        {
            ignore.insert(i);
            let last = result.last().expect("checked");
            if EMOJI[&last.chars].component {
                let k = result.len().saturating_sub(2);
                let back: usize = result[k..].iter().map(|t| t.chars.chars().count()).sum();
                i = i.saturating_sub(back);
                if s[i] == ZWJ {
                    i += 1;
                    result.pop();
                } else {
                    result.truncate(k);
                }
            } else {
                i = i.saturating_sub(last.chars.chars().count());
                result.pop();
            }
            continue;
        } else if !result.is_empty() {
            out.append(&mut result);
        }
        if !consumed && ch != '\u{FE0E}' && ch != '\u{FE0F}' {
            result.push(Token { chars: ch.to_string(), start: i, end: i + 1, emoji: false });
        }
        i += 1;
    }
    out.append(&mut result);
    out.into_iter().filter(|t| t.emoji).map(|t| (byte[t.start], byte[t.end], t.chars)).collect()
}
