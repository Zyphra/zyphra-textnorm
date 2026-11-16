//! Shared rules: the port of the workbench's `langrules/shared.py` (ids `all.*`): S05 leading zeros, S06 phone
//! numbers, S18 operator words, S23 email addresses and URLs, S32 Unicode fractions. The words these rules write
//! themselves (an address, a phone number, a code) are wrapped in U+E000 … U+E001 so the grammar passes them through.

use super::super::{Ctx, chars_before, g, is_alnum, matches_at_start, rx, search};
use super::{LangRule, digit_words, words};

/// Run right after `en.url`.
pub(in crate::prepass) const EARLY: &[LangRule] = &[
    ("all.email-url", all_email_url),
    ("all.operators", all_operators),
    ("all.phone", all_phone),
    ("all.plus-sign", all_plus_sign),
    ("all.fraction-char", all_fraction_char),
];
/// Run after the language's own rules.
pub(in crate::prepass) const LATE: &[LangRule] = &[("all.leading-zero", all_leading_zero)];

fn verbatim(s: &str) -> String {
    format!("\u{e000}{s}\u{e001}")
}

fn lookup<'a>(map: &[(&str, &'a str)], k: &str) -> Option<&'a str> {
    map.iter().find(|(a, _)| *a == k).map(|(_, v)| *v)
}

// ------------------------------------------------------------------------------------------------- digits of a code

const CODE_DIGIT: &[(&str, &str, &str)] = &[
    ("es", "1", "uno"),
    ("da", "1", "en"),
    ("ja", "0", "ゼロ"),
    ("ko", "0", "공"),
    ("tl", "0", "zero"),
    ("tl", "1", "one"),
    ("tl", "2", "two"),
    ("tl", "3", "three"),
    ("tl", "4", "four"),
    ("tl", "5", "five"),
    ("tl", "6", "six"),
    ("tl", "7", "seven"),
    ("tl", "8", "eight"),
    ("tl", "9", "nine"),
];
const GLUED: [&str; 4] = ["ja", "zh", "ko", "th"];

/// Each digit of `s` as a code is read: prototype `code_digits`.
fn code_digits(s: &str, lang: &str) -> String {
    let sep = if GLUED.contains(&lang) { "" } else { " " };
    s.chars()
        .map(|d| {
            let d = d.to_string();
            CODE_DIGIT
                .iter()
                .find(|(l, k, _)| *l == lang && *k == d)
                .map_or_else(|| words(&d, lang), |x| x.2.to_string())
        })
        .collect::<Vec<_>>()
        .join(sep)
}

/// The letters and digits of `s`.
fn alnum(s: &str) -> String {
    s.chars().filter(|&c| is_alnum(c)).collect()
}

/// The characters that may not touch a number or an address (only ASCII ones in ja, zh, ko, th).
fn edge(lang: &str) -> &'static str {
    if GLUED.contains(&lang) { "A-Za-z0-9_" } else { r"\w" }
}

// ------------------------------------------------------------------------------------------------- S23 addresses

const E_WORDS: &[(&str, [&str; 7])] = &[
    ("en", ["at", "dot", "slash", "dash", "underscore", "colon", "plus"]),
    ("de", ["at", "punkt", "slash", "bindestrich", "unterstrich", "doppelpunkt", "plus"]),
    ("es", ["arroba", "punto", "barra", "guion", "guion bajo", "dos puntos", "más"]),
    ("fr", ["arobase", "point", "slash", "tiret", "tiret bas", "deux-points", "plus"]),
    ("it", ["chiocciola", "punto", "slash", "trattino", "trattino basso", "due punti", "più"]),
    ("pt", ["arroba", "ponto", "barra", "traço", "underscore", "dois pontos", "mais"]),
    ("ja", ["アットマーク", "ドット", "スラッシュ", "ハイフン", "アンダースコア", "コロン", "プラス"]),
    ("zh", ["艾特", "点", "斜杠", "横杠", "下划线", "冒号", "加"]),
    ("ko", ["골뱅이", "닷", "슬래시", "하이픈", "언더바", "콜론", "플러스"]),
    ("nl", ["apenstaartje", "punt", "slash", "streepje", "laag streepje", "dubbele punt", "plus"]),
    ("pl", ["małpa", "kropka", "ukośnik", "myślnik", "podkreślenie", "dwukropek", "plus"]),
    ("tr", ["et", "nokta", "bölü", "tire", "alt çizgi", "iki nokta üst üste", "artı"]),
    ("uk", ["равлик", "крапка", "слеш", "дефіс", "підкреслення", "двокрапка", "плюс"]),
    ("cs", ["zavináč", "tečka", "lomítko", "pomlčka", "podtržítko", "dvojtečka", "plus"]),
    ("da", ["snabel-a", "punktum", "skråstreg", "bindestreg", "understreg", "kolon", "plus"]),
    ("fi", ["ät", "piste", "kauttaviiva", "viiva", "alaviiva", "kaksoispiste", "plus"]),
    ("el", ["παπάκι", "τελεία", "κάθετος", "παύλα", "κάτω παύλα", "άνω και κάτω τελεία", "συν"]),
    ("nb", ["krøllalfa", "punktum", "skråstrek", "bindestrek", "understrek", "kolon", "pluss"]),
    ("ro", ["arond", "punct", "slash", "liniuță", "liniuță jos", "două puncte", "plus"]),
    ("sk", ["zavináč", "bodka", "lomka", "pomlčka", "podčiarkovník", "dvojbodka", "plus"]),
    ("bg", ["кльомба", "точка", "наклонена черта", "тире", "долна черта", "двоеточие", "плюс"]),
    ("he", ["שטרודל", "נקודה", "סלאש", "מקף", "קו תחתון", "נקודתיים", "פלוס"]),
    ("th", ["แอท", "ดอท", "สแลช", "ขีด", "อันเดอร์สกอร์", "โคลอน", "บวก"]),
    ("tl", ["at", "dot", "slash", "dash", "underscore", "colon", "plus"]),
    ("ms", ["at", "dot", "slash", "dash", "underscore", "colon", "plus"]),
    ("ka", ["ეთ", "წერტილი", "დახრილი ხაზი", "დეფისი", "ქვედა ტირე", "ორწერტილი", "პლუს"]),
    ("ta", ["அட்", "டாட்", "ஸ்லாஷ்", "ஹைபன்", "அண்டர்ஸ்கோர்", "கோலன்", "பிளஸ்"]),
    ("gu", ["એટ", "ડૉટ", "સ્લેશ", "હાઇફન", "અંડરસ્કોર", "કોલન", "પ્લસ"]),
    ("kn", ["ಅಟ್", "ಡಾಟ್", "ಸ್ಲ್ಯಾಶ್", "ಹೈಫನ್", "ಅಂಡರ್\u{200c}ಸ್ಕೋರ್", "ಕೋಲನ್", "ಪ್ಲಸ್"]),
    ("ml", ["അറ്റ്", "ഡോട്ട്", "സ്ലാഷ്", "ഹൈഫൻ", "അണ്ടർസ്കോർ", "കോളൻ", "പ്ലസ്"]),
    ("pa", ["ਐਟ", "ਡਾਟ", "ਸਲੈਸ਼", "ਹਾਈਫ਼ਨ", "ਅੰਡਰਸਕੋਰ", "ਕਾਲਨ", "ਪਲੱਸ"]),
    ("or", ["ଆଟ୍", "ଡଟ୍", "ସ୍ଲାସ୍", "ଡ୍ୟାସ୍", "ଅଣ୍ଡରସ୍କୋର", "କୋଲନ୍", "ପ୍ଲସ୍"]),
    ("ru", ["собака", "точка", "слэш", "дефис", "нижнее подчеркивание", "двоеточие", "плюс"]),
    ("sv", ["snabel-a", "punkt", "snedstreck", "bindestreck", "understreck", "kolon", "plus"]),
    ("hu", ["kukac", "pont", "perjel", "kötőjel", "aláhúzásjel", "kettőspont", "plusz"]),
    ("ar", ["آت", "نقطة", "شرطة مائلة", "شرطة", "شرطة سفلية", "نقطتان", "زائد"]),
    ("vi", ["a còng", "chấm", "gạch chéo", "gạch ngang", "gạch dưới", "hai chấm", "cộng"]),
    ("id", ["et", "titik", "garis miring", "strip", "garis bawah", "titik dua", "plus"]),
    ("hi", ["एट", "डॉट", "फॉरवर्ड स्लैश", "हाइफ़न", "अंडर स्कोर", "कोलन", "प्लस"]),
    ("bn", ["অ্যাট", "ডট", "স্ল্যাশ", "হাইফেন", "আন্ডারস্কোর", "কোলন", "প্লাস"]),
    ("te", ["ఎట్", "డాట్", "స్లాష్", "హైఫన్", "అండర్\u{200c}స్కోర్", "కోలన్", "ప్లస్"]),
    ("mr", ["ॲट", "डॉट", "स्लॅश", "हायफन", "अंडरस्कोर", "कोलन", "प्लस"]),
    ("ur", ["ایٹ", "ڈاٹ", "سلیش", "ہائفن", "انڈر اسکور", "کولن", "پلس"]),
];
const E_SYMBOLS: &str = "@./-_:+";

fn e_words(lang: &str) -> &'static [&'static str; 7] {
    &E_WORDS.iter().find(|(l, _)| *l == lang).unwrap_or(&E_WORDS[0]).1
}

const WWW: &[(&str, &str)] = &[
    ("ro", "dublu ve dublu ve dublu ve"),
    ("fi", "vee vee vee"),
    ("tr", "ve ve ve"),
    ("ja", "ダブリューダブリューダブリュー"),
    ("ko", "더블유 더블유 더블유"),
    ("uk", "дабл ю дабл ю дабл ю"),
    ("bg", "в в в"),
    ("he", "דאבליו דאבליו דאבליו"),
    ("th", "ดับเบิลยู ดับเบิลยู ดับเบิลยู"),
    ("ka", "დაბლიუ დაბლიუ დაბლიუ"),
    ("ta", "டபிள்யூ டபிள்யூ டபிள்யூ"),
    ("gu", "ડબલ્યુ ડબલ્યુ ડબલ્યુ"),
    ("kn", "ಡಬ್ಲ್ಯೂ ಡಬ್ಲ್ಯೂ ಡಬ್ಲ್ಯೂ"),
    ("ml", "ഡബ്ല്യു ഡബ്ല്യു ഡബ്ല്യു"),
    ("pa", "ਡਬਲਯੂ ਡਬਲਯੂ ਡਬਲਯੂ"),
    ("or", "ଡବ୍ଲ୍ୟୁ ଡବ୍ଲ୍ୟୁ ଡବ୍ଲ୍ୟୁ"),
    ("ar", "دبليو دبليو دبليو"),
    ("vi", "vê kép vê kép vê kép"),
    ("hi", "डब्ल्यू डब्ल्यू डब्ल्यू"),
    ("bn", "ডব্লিউ ডব্লিউ ডব্লিউ"),
    ("te", "డబ్ల్యూ డబ్ల్యూ డబ్ల్యూ"),
    ("mr", "डब्ल्यू डब्ल्यू डब्ल्यू"),
    ("ur", "ڈبلیو ڈبلیو ڈبلیو"),
];
const SPELLED: [&str; 4] = ["asdf", "qwerty", "api", "edu"];
const SPELL_SHORT: [&str; 3] = ["es", "it", "fr"];
const LETTER_NAMES: &[(&str, [&str; 26])] = &[
    (
        "he",
        [
            "איי",
            "בי",
            "סי",
            "די",
            "אי",
            "אף",
            "ג'י",
            "אייץ'",
            "איי",
            "ג'יי",
            "קיי",
            "אל",
            "אם",
            "אן",
            "או",
            "פי",
            "קיו",
            "אר",
            "אס",
            "טי",
            "יו",
            "וי",
            "דבליו",
            "אקס",
            "וואי",
            "זד",
        ],
    ),
    (
        "uk",
        [
            "ей",
            "бі",
            "сі",
            "ді",
            "і",
            "еф",
            "джі",
            "ейч",
            "ай",
            "джей",
            "кей",
            "ель",
            "ем",
            "ен",
            "оу",
            "пі",
            "кю",
            "ар",
            "ес",
            "ті",
            "ю",
            "ві",
            "дабл-ю",
            "ікс",
            "вай",
            "зед",
        ],
    ),
];
const LABEL: &str = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?";
const URL_PATH: &str = r"(?:/[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)*/?";

fn address_rx(lang: &str) -> String {
    let e = edge(lang);
    format!(
        r"(?<![{e}@./:%+&])(?:(?:mailto:)?[A-Za-z0-9](?:[A-Za-z0-9._+-]*[A-Za-z0-9])?@{LABEL}(?:\.{LABEL})*\.[A-Za-z]{{2,}}|(?:https?://)(?:{LABEL}(?:\.{LABEL})+|localhost)(?::[0-9]{{2,5}})?{URL_PATH}|www\.{LABEL}(?:\.{LABEL})+{URL_PATH}|{LABEL}(?:\.{LABEL})*\.(?:com|org|net|edu|gov|info|io|co\.[a-z]{{2}})(?:\.[a-z]{{2}})?{URL_PATH})(?![{e}@/#=&%~+|^*$\\-]|[.?!:]\w)"
    )
}

/// Letters said one by one: prototype `spell`.
fn spell(s: &str, lang: &str) -> String {
    let names = LETTER_NAMES.iter().find(|(l, _)| *l == lang).map(|x| &x.1);
    s.chars()
        .map(|ch| {
            if lang == "ru" {
                words(&ch.to_string(), "ru")
            } else if let Some(n) = names {
                n[(ch.to_ascii_lowercase() as u8 - b'a') as usize].to_string()
            } else {
                ch.to_string()
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// abc, def, xyz: letters in alphabetical order.
fn alphabetical(s: &str) -> bool {
    let b: Vec<u8> = s.to_ascii_lowercase().into_bytes();
    b.len() >= 3 && b.windows(2).all(|w| w[1] as i32 - w[0] as i32 == 1)
}

fn address_words(addr: &str, lang: &str) -> String {
    let sym = e_words(lang);
    let mut out: Vec<String> = Vec::new();
    let mut local = addr.contains('@'); // the user part of an email address, before the @
    for tok in rx(r"[A-Za-z]+|[0-9]+|.").find_iter(addr).flatten().map(|m| m.as_str()) {
        if tok.bytes().all(|b| b.is_ascii_digit()) {
            out.push(if lang == "ko" { digit_words(tok, "ko", "") } else { code_digits(tok, lang) });
        } else if tok.eq_ignore_ascii_case("www") {
            out.push(lookup(WWW, lang).map_or_else(|| spell(tok, lang), str::to_string));
        } else if tok.bytes().all(|b| b.is_ascii_alphabetic()) {
            let low = tok.to_ascii_lowercase();
            if low.len() <= 2 {
                out.push(if SPELL_SHORT.contains(&lang) || local { spell(tok, lang) } else { tok.to_string() });
                continue;
            }
            let word =
                low.contains(['a', 'e', 'i', 'o', 'u']) && !SPELLED.contains(&low.as_str()) && !alphabetical(&low);
            out.push(if word { tok.to_string() } else { spell(tok, lang) });
        } else {
            local = local && tok != "@";
            let i = E_SYMBOLS.find(tok).expect("address symbol");
            out.push(sym[i].to_string());
        }
    }
    out.join(" ")
}

fn all_email_url(t: String, c: &mut Ctx) -> String {
    let lang = c.lang().to_string();
    if lang == "en" {
        return t;
    }
    c.sub(&rx(&address_rx(&lang)), &t, |m| {
        let end = m.get(0).expect("group 0").end();
        if lang == "ko" && !t[end..].chars().next().is_some_and(|ch| ('가'..='힣').contains(&ch)) {
            return None; // Korean: only an address with a particle glued on, which its grammar misses
        }
        let mut addr = &m[0];
        for p in ["mailto:", "https://", "http://"] {
            if let Some(rest) = addr.strip_prefix(p) {
                addr = rest;
                break;
            }
        }
        Some(verbatim(&address_words(addr, &lang)))
    })
}

// ------------------------------------------------------------------------------------------------- S06 phone numbers

const PHONE_STYLE: &[(&str, &str)] = &[
    ("bg", "groups"),
    ("cs", "groups"),
    ("sk", "groups"),
    ("pl", "groups"),
    ("uk", "groups"),
    ("ru", "groups"),
    ("hu", "groups"),
    ("tr", "groups"),
    ("fr", "pairs"),
];
const GROUP_SEP: &[(&str, &str)] = &[
    ("ja", "の"),
    ("he", ", "),
    ("ka", ", "),
    ("vi", ", "),
    ("bg", ", "),
    ("cs", ", "),
    ("sk", ", "),
    ("pl", ", "),
    ("uk", ", "),
    ("ru", ", "),
    ("hu", ", "),
    ("fr", ", "),
];
const PHONE_PLUS: &[(&str, &str)] = &[("ko", "국가번호")];
const EXTENSION: &[(&str, &str)] = &[
    ("en", "extension"),
    ("de", "Durchwahl"),
    ("es", "extensión"),
    ("fr", "poste"),
    ("it", "interno"),
    ("pt", "extensão"),
    ("ja", "内線"),
    ("zh", "分机"),
    ("ko", "내선"),
    ("nl", "toestel"),
    ("pl", "wewnętrzny"),
    ("tr", "dahili"),
    ("uk", "додатковий"),
    ("cs", "linka"),
    ("da", "lokal"),
    ("fi", "alanumero"),
    ("el", "εσωτερικό"),
    ("nb", "internnummer"),
    ("ro", "interior"),
    ("sk", "linka"),
    ("bg", "вътрешен"),
    ("he", "שלוחה"),
    ("th", "ต่อ"),
    ("tl", "extension"),
    ("ms", "sambungan"),
    ("ka", "შიდა"),
    ("ta", "எக்ஸ்டென்ஷன்"),
    ("gu", "એક્સટેન્શન"),
    ("kn", "ಎಕ್ಸ್\u{200c}ಟೆನ್ಶನ್"),
    ("ml", "എക്സ്റ്റൻഷൻ"),
    ("pa", "ਐਕਸਟੈਂਸ਼ਨ"),
    ("or", "ଏକ୍ସଟେନସନ"),
    ("ru", "добавочный"),
    ("sv", "anknytning"),
    ("hu", "mellék"),
    ("ar", "تحويلة"),
    ("vi", "máy lẻ"),
    ("id", "ekstensi"),
    ("hi", "एक्सटेंशन"),
    ("bn", "এক্সটেনশন"),
    ("te", "ఎక్స్\u{200c}టెన్షన్"),
    ("mr", "एक्स्टेंशन"),
    ("ur", "ایکسٹینشن"),
];
const PHONE_CUE: &[(&str, &str)] = &[
    ("en", r"call\w*|phone\w*|tel|mobile|cell|fax|ring|dial\w*|whatsapp|hotline"),
    ("de", r"anruf\w*|ruf|rufen|telefon\w*|tel|handy|mobil\w*|fax|nummer|rufnummer|hotline|whatsapp|erreichbar"),
    ("es", r"ll[aá]m\w*|tel[eé]fono\w*|tel|tlf|m[oó]vil|celular|whatsapp|n[uú]mero|contacto|fax"),
    ("fr", r"appel\w*|t[eé]l[eé]phone\w*|t[eé]l|portable|mobile|num[eé]ro|joindre|fax|whatsapp"),
    ("it", r"chiam\w*|telefon\w*|tel|cellulare|cell|numero|whatsapp|fax|contatt\w*"),
    ("pt", r"lig[au]\w*|telefone\w*|tel|celular|telem[oó]vel|n[uú]mero|whatsapp|contato|contacto|fax"),
    ("nl", r"bel|bellen|belt|telefoon\w*|tel|mobiel|nummer|fax|whatsapp"),
    ("pl", r"dzwo\w*|zadzwo\w*|telefon\w*|tel|kom[oó]rk\w*|numer\w*|fax"),
    ("cs", r"volej\w*|zavolej\w*|volat|telefon\w*|tel|mobil\w*|[čc][ií]sl\w*|fax"),
    ("sk", r"volaj\w*|zavolaj\w*|telef[oó]n\w*|tel|mobil\w*|[čc][ií]sl\w*|fax"),
    ("ru", r"звон\w*|позвон\w*|телефон\w*|тел|моб\w*|номер\w*|факс"),
    ("uk", r"дзвон\w*|зателефон\w*|телефон\w*|тел|моб\w*|номер\w*|факс"),
    ("bg", r"обад\w*|звън\w*|телефон\w*|тел|моб\w*|номер\w*|факс"),
    ("sv", r"ring\w*|telefon\w*|tel|mobil\w*|nummer|fax"),
    ("da", r"ring\w*|telefon\w*|tlf|tel|mobil\w*|nummer|fax"),
    ("nb", r"ring\w*|telefon\w*|tlf|tel|mobil\w*|nummer|fax"),
    ("fi", r"soit\w*|puhelin\w*|puh|numero\w*|gsm|faksi"),
    ("hu", r"h[ií]v\w*|telefon\w*|tel|mobil\w*|sz[aá]m\w*|fax"),
    ("ro", r"sun[aă]\w*|telefon\w*|tel|mobil|num[aă]r\w*|fax"),
    ("el", r"καλ[εέ]στε|τηλ[εέ]φων\w*|τηλ|κινητ\w*|αριθμ\w*|φαξ"),
];
const EXT_ABBR: &[(&str, &str)] = &[
    ("de", "Durchw|Durchwahl|Dw"),
    ("fr", "poste"),
    ("it", "int|interno"),
    ("pt", "ramal"),
    ("es", "extensión|extension"),
    ("nl", "toestel|tst"),
    ("sv", "ankn"),
    ("da", "lokal"),
    ("nb", "linje"),
    ("pl", "wewn"),
    ("cs", "linka|kl"),
    ("sk", "kl"),
    ("ru", "доб"),
    ("uk", "дод"),
    ("hu", "mellék|m"),
    ("ro", "int|interior"),
    ("tr", "dahili"),
    ("fi", "alanro"),
];

fn phone_rx(lang: &str) -> String {
    let e = edge(lang);
    let ext = match lookup(EXT_ABBR, lang) {
        Some(a) => format!("ext|Ext|EXT|extn|Extn|{a}"),
        None => "ext|Ext|EXT|extn|Extn".to_string(),
    };
    format!(
        r"(?:(?<![{e}+(.,/:@-])|(?<=\()(?=\+))(\+ ?)?(\([0-9]{{1,5}}\)|[0-9]{{1,15}})( ?\(0\))?((?:(?:(?<=\)) ?|[ ./-])[0-9]{{1,12}}|[ ./-]?\([0-9]{{1,5}}\)){{0,7}})(,? ?(?:{ext})\.? ?([0-9]{{1,6}}))?(?![{e}@)]|[.,/:-][0-9])"
    )
}

/// A group cut into the parts said as numbers: prototype `chunks`.
fn chunks(g: &str, style: &str) -> Vec<String> {
    let n = g.len();
    if n <= 3 {
        return vec![g.to_string()];
    }
    if style == "pairs" {
        let mut out = Vec::new();
        let start = if n % 2 == 1 {
            out.push(g[..3].to_string());
            3
        } else {
            0
        };
        out.extend((start..n).step_by(2).map(|i| g[i..(i + 2).min(n)].to_string()));
        return out;
    }
    let cut: &[usize] = match n {
        4 => &[2],
        5 | 6 => &[3],
        7 => &[3, 5],
        8 | 9 => &[3, 6],
        _ => return g.chars().map(|c| c.to_string()).collect(),
    };
    let mut bounds = vec![0];
    bounds.extend_from_slice(cut);
    bounds.push(n);
    bounds.windows(2).map(|w| g[w[0]..w[1]].to_string()).collect()
}

fn group_words(g: &str, lang: &str, style: &str) -> String {
    if style == "digits" || g.starts_with('0') {
        return code_digits(g, lang);
    }
    chunks(g, style)
        .iter()
        .map(|p| if p.starts_with('0') || p.len() == 1 { code_digits(p, lang) } else { words(p, lang) })
        .collect::<Vec<_>>()
        .join(" ")
}

fn digit_groups(first: &str, rest: &str) -> Vec<String> {
    let mut groups = vec![first.trim_matches(|c| c == '(' || c == ')').to_string()];
    groups.extend(rx(r"[0-9]+").find_iter(rest).flatten().map(|m| m.as_str().to_string()));
    groups
}

/// Whether the digits are a phone number: prototype `phone_shape`.
fn phone_shape(plus: bool, first: &str, rest: &str, before: &str, lang: &str) -> bool {
    let groups = digit_groups(first, rest);
    let seps: Vec<char> = rest.chars().filter(|c| " ./-".contains(*c)).collect();
    let n: usize = groups.iter().map(String::len).sum();
    if plus {
        return (8..=15).contains(&n) && (groups.len() > 1 || first.len() >= 8) && !seps.contains(&'/');
    }
    if first.starts_with('(') {
        return (8..=12).contains(&n) && !seps.contains(&'/') && !seps.contains(&'.');
    }
    if groups.len() < 2 || first.len() > 5 {
        return false;
    }
    if first.starts_with('0') && first.len() >= 2 {
        if !(9..=12).contains(&n) {
            return false;
        }
        if seps.contains(&'/') {
            return groups.len() == 2 && groups[1].len() >= 5;
        }
        if seps.contains(&'.') {
            return groups.len() >= 3 && !(groups.len() == 4 && groups.iter().all(|g| g.len() <= 3));
        }
        return true;
    }
    if seps.contains(&'/') || seps.contains(&'.') || !(9..=12).contains(&n) || groups.iter().any(|g| g.len() < 2) {
        return false;
    }
    let lens: Vec<usize> = groups.iter().map(String::len).collect();
    if !seps.is_empty() && seps.iter().all(|&s| s == '-') {
        return groups.len() >= 3
            && lens[lens.len() - 1] == 4
            && lens[1..lens.len() - 1].iter().all(|x| (3..=4).contains(x))
            && ((2..=4).contains(&lens[0]) || (lens[0] == 1 && groups.len() == 4));
    }
    if groups.len() > 4 || lens[lens.len() - 1] < 3 || lens.iter().all(|&x| x == 4) {
        return false;
    }
    if lens[0] <= 3 && lens[1..].iter().all(|&x| x == 3) {
        return lookup(PHONE_CUE, lang).is_some_and(|cue| search(&format!(r"(?i)(?<!\w)(?:{cue})(?!\w)"), before));
    }
    true
}

fn all_phone(t: String, c: &mut Ctx) -> String {
    let lang = c.lang().to_string();
    let style = lookup(PHONE_STYLE, &lang).unwrap_or("digits");
    let sep = lookup(GROUP_SEP, &lang).unwrap_or(" ");
    c.sub(&rx(&phone_rx(&lang)), &t, |m| {
        let (plus, first, rest) = (!g(m, 1).is_empty(), g(m, 2), g(m, 4));
        let whole = m.get(0).expect("group 0");
        let mut ext = g(m, 6).to_string();
        if !phone_shape(plus, first, rest, chars_before(&t, whole.start(), 40), &lang) {
            return None;
        }
        if lang == "en" {
            // English: the grammar's telephone reading and your verdicts (+59 837 762 8639) stand; only ext. is read
            let e = m.get(5)?;
            return Some(format!(
                "{}, {}",
                &whole.as_str()[..e.start() - whole.start()],
                verbatim(&format!("extension {}", code_digits(&ext, "en")))
            ));
        }
        let mut groups = digit_groups(first, rest);
        let k = groups.len();
        if ext.is_empty()
            && k >= 4
            && groups[k - 4..k - 1].iter().map(String::len).eq([3, 3, 4])
            && groups[k - 1].len() <= 4
            && (plus || first.starts_with('('))
        {
            ext = groups.pop().expect("group"); // +58 (123) 123-5678-12: the last group is the extension
        }
        let mut parts = Vec::new();
        if plus {
            let cc = if groups.len() > 1 { groups.remove(0) } else { String::new() };
            let cc_style = if style != "digits" || (lang == "es" && cc.len() <= 2) { "groups" } else { "digits" };
            let word = lookup(PHONE_PLUS, &lang).unwrap_or(e_words(&lang)[6]);
            parts.push(if cc.is_empty() {
                word.to_string()
            } else {
                format!("{word} {}", group_words(&cc, &lang, cc_style))
            });
        }
        if lang == "pt"
            && first.starts_with('(')
            && first.len() == 4
            && groups.first().is_some_and(|g| g == &first[1..3])
        {
            // Brazil: the parenthesized DDD area code is said as a number, (11) 98765-4321 → onze, nove oito …
            parts.push(words(&groups.remove(0), "pt"));
        }
        parts.extend(groups.iter().map(|g| group_words(g, &lang, style)));
        let mut said = parts.join(sep);
        if !ext.is_empty() {
            said = format!("{said}{sep}{} {}", lookup(EXTENSION, &lang).unwrap_or(""), code_digits(&ext, &lang));
        }
        Some(verbatim(&said))
    })
}

const SIGN_PLUS: &[(&str, &str)] = &[("zh", "正")];

fn all_plus_sign(t: String, c: &mut Ctx) -> String {
    let lang = c.lang().to_string();
    if ["en", "it", "ja", "vi"].contains(&lang.as_str()) {
        return t;
    }
    let word = lookup(SIGN_PLUS, &lang).unwrap_or(e_words(&lang)[6]);
    c.sub(&rx(r"(?<![\w)+.,])(?<![0-9] )\+[0-9]\S*"), &t, |m| {
        let w = m.get(0).expect("group 0");
        if search(
            r"(?i)\b(?:utc|gmt|cet|cest|eet|eest|msk|ist|jst|kst|est|edt|pst|pdt|cst|cdt|mst|mdt)[ \t]*$",
            &t[..w.start()],
        ) {
            return None; // 3:00 UTC +1 is a time zone, the grammar's
        }
        let said = words(w.as_str(), &lang);
        if !said.contains('+') && alnum(&said) != alnum(&words(&w.as_str()[1..], &lang)) {
            return None; // the grammar reads this + itself (hu +36-80/555-111, ko +1109/11/1)
        }
        Some(format!("{word} {}", &w.as_str()[1..]))
    })
}

// ------------------------------------------------------------------------------------------------- S32 fractions

const FRACTIONS: &[(&str, &str)] = &[
    ("½", "1/2"),
    ("⅓", "1/3"),
    ("⅔", "2/3"),
    ("¼", "1/4"),
    ("¾", "3/4"),
    ("⅕", "1/5"),
    ("⅖", "2/5"),
    ("⅗", "3/5"),
    ("⅘", "4/5"),
    ("⅙", "1/6"),
    ("⅚", "5/6"),
    ("⅐", "1/7"),
    ("⅛", "1/8"),
    ("⅜", "3/8"),
    ("⅝", "5/8"),
    ("⅞", "7/8"),
    ("⅑", "1/9"),
    ("⅒", "1/10"),
];
const IT_FRACTIONS: &[(&str, &str)] = &[
    ("½", "mezzo"),
    ("⅓", "un terzo"),
    ("⅔", "due terzi"),
    ("¼", "un quarto"),
    ("¾", "tre quarti"),
    ("⅕", "un quinto"),
    ("⅖", "due quinti"),
    ("⅗", "tre quinti"),
    ("⅘", "quattro quinti"),
    ("⅙", "un sesto"),
    ("⅚", "cinque sesti"),
    ("⅐", "un settimo"),
    ("⅛", "un ottavo"),
    ("⅜", "tre ottavi"),
    ("⅝", "cinque ottavi"),
    ("⅞", "sette ottavi"),
    ("⅑", "un nono"),
    ("⅒", "un decimo"),
];

/// Whether a Korean syllable ends in a consonant (삼 yes, 사 no).
fn hangul_final(s: &str) -> bool {
    s.chars().next_back().is_some_and(|c| ('가'..='힣').contains(&c) && !(c as u32 - 0xAC00).is_multiple_of(28))
}

/// What joins a whole number and its fraction: prototype `mixed_join`.
fn mixed_join(whole: &str, lang: &str) -> &'static str {
    match lang {
        "ja" => "と",
        "zh" => "又",
        "ko" if hangul_final(&words(whole, "ko")) => "과 ",
        "ko" => "와 ",
        "it" => " e ",
        _ => " ",
    }
}

fn all_fraction_char(t: String, c: &mut Ctx) -> String {
    let lang = c.lang().to_string();
    c.sub(&rx(r"(?<![0-9])(?:([0-9]+)[ \x{A0}]?)?([½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅐⅛⅜⅝⅞⅑⅒])"), &t, |m| {
        let (whole, frac) = (g(m, 1), g(m, 2));
        if !words(&format!("{whole}{frac}"), &lang).contains(frac) {
            return None; // the grammar reads it
        }
        let new = lookup(if lang == "it" { IT_FRACTIONS } else { FRACTIONS }, frac)?;
        Some(if whole.is_empty() { new.to_string() } else { format!("{whole}{}{new}", mixed_join(whole, &lang)) })
    })
}

// ------------------------------------------------------------------------------------------------- S05 leading zeros

const ORDINAL_DOT: [&str; 9] = ["de", "da", "nb", "cs", "sk", "pl", "fi", "hu", "tr"];
const CJK_TIME: &str = "時时分秒月日号號点點";
const KO_COUNTER: &str = r"(?:시|분|초|년|월|일|층|개|명|살|도|원|회|주|박|대|장|권|잔|병)";

fn all_leading_zero(t: String, c: &mut Ctx) -> String {
    let lang = c.lang().to_string();
    if lang == "fr" {
        return t; // French reads the zeros, then the rest as a number (zéro zéro quarante-deux)
    }
    let nxt = r"((?:[.,]?[ \t\x{A0}]?(?:[^\W\d_]+|[^\w\s]))?)";
    let pat = format!(
        r"(?<![{}.,:/'’$€£¥₹#№+-])(?<![0-9][ ,.\x{{A0}}\x{{202F}}])(0[0-9]+)(?![0-9]|[.,:/-]?[ \t\x{{A0}}\x{{202F}}]?[0-9]){nxt}",
        edge(&lang)
    );
    c.sub(&rx(&pat), &t, |m| {
        let (num, nxt) = (g(m, 1), g(m, 2));
        let cjk = lang == "ja" || lang == "zh";
        if cjk && nxt.chars().next().is_some_and(|ch| CJK_TIME.contains(ch)) {
            if num.len() != 2 {
                return None;
            }
            let n = num.trim_start_matches('0');
            return Some(format!("{}{nxt}", if n.is_empty() { "0" } else { n })); // 09時 → 9時 (九時, was 零九時)
        }
        if cjk && matches_at_start(r"[\x{4e00}-\x{9fff}]", nxt) {
            return None; // a counter or a noun after it
        }
        if lang == "ko" && matches_at_start(KO_COUNTER, nxt) {
            return None;
        }
        let said = code_digits(num, &lang);
        let alone = words(num, &lang);
        if alnum(&alone) == alnum(&said) {
            return None; // the grammar reads it digit by digit already
        }
        if !nxt.is_empty() && alnum(&words(&format!("{num}{nxt}"), &lang)) != alnum(&(alone + &words(nxt, &lang))) {
            return None; // read together with what follows: a date, a time, a unit, an ordinal
        }
        if ORDINAL_DOT.contains(&lang.as_str()) && matches_at_start(r"\.[ \t]*[^\W\d_]", nxt) {
            return None;
        }
        Some(verbatim(&said) + nxt)
    })
}

// ------------------------------------------------------------------------------------------------- S18 operators

const OPS: &[(&str, &[(&str, &str)])] = &[
    (
        "de",
        &[
            ("+", "plus"),
            ("-", "minus"),
            ("×", "mal"),
            ("÷", "geteilt durch"),
            ("=", "ist gleich"),
            ("±", "plus minus"),
            ("&", "und"),
        ],
    ),
    (
        "fr",
        &[
            ("+", "plus"),
            ("-", "moins"),
            ("×", "fois"),
            ("÷", "divisé par"),
            ("=", "égale"),
            ("±", "plus ou moins"),
            ("&", "et"),
        ],
    ),
    (
        "it",
        &[("+", "più"), ("-", "meno"), ("×", "per"), ("÷", "diviso"), ("=", "uguale"), ("±", "più o meno"), ("&", "e")],
    ),
    (
        "pt",
        &[
            ("+", "mais"),
            ("-", "menos"),
            ("×", "vezes"),
            ("÷", "dividido por"),
            ("=", "igual"),
            ("±", "mais ou menos"),
            ("&", "e"),
        ],
    ),
    (
        "es",
        &[
            ("+", "más"),
            ("-", "menos"),
            ("×", "por"),
            ("÷", "entre"),
            ("=", "es igual a"),
            ("±", "más menos"),
            ("&", "y"),
        ],
    ),
    (
        "ja",
        &[
            ("+", "プラス"),
            ("-", "引く"),
            ("×", "掛ける"),
            ("÷", "割る"),
            ("=", "は"),
            ("±", "プラスマイナス"),
            ("&", "アンド"),
        ],
    ),
    ("zh", &[("+", "加"), ("-", "减"), ("×", "乘"), ("÷", "除以"), ("=", "等于"), ("±", "正负"), ("&", "和")]),
    (
        "ko",
        &[
            ("+", "더하기"),
            ("-", "빼기"),
            ("×", "곱하기"),
            ("÷", "나누기"),
            ("=", ""),
            ("±", "플러스마이너스"),
            ("&", "앤드"),
        ],
    ),
    ("nl", &[("+", "plus"), ("-", "minus"), ("×", "keer"), ("÷", "gedeeld door"), ("=", "is gelijk aan")]),
    ("pl", &[("+", "plus"), ("-", "minus"), ("×", "razy"), ("÷", "podzielone przez"), ("=", "równa się")]),
    ("tr", &[("+", "artı"), ("-", "eksi"), ("×", "çarpı"), ("÷", "bölü"), ("=", "eşittir")]),
    ("uk", &[("+", "плюс"), ("-", "мінус"), ("×", "помножити на"), ("÷", "поділити на"), ("=", "дорівнює")]),
    ("cs", &[("+", "plus"), ("-", "minus"), ("×", "krát"), ("÷", "děleno"), ("=", "rovná se")]),
    ("da", &[("+", "plus"), ("-", "minus"), ("×", "gange"), ("÷", "divideret med"), ("=", "er lig med")]),
    ("fi", &[("+", "plus"), ("-", "miinus"), ("×", "kertaa"), ("÷", "jaettuna"), ("=", "on yhtä kuin")]),
    ("el", &[("+", "συν"), ("-", "μείον"), ("×", "επί"), ("÷", "διά"), ("=", "ίσον")]),
    ("nb", &[("+", "pluss"), ("-", "minus"), ("×", "ganger"), ("÷", "delt på"), ("=", "er lik")]),
    ("ro", &[("+", "plus"), ("-", "minus"), ("×", "ori"), ("÷", "împărțit la"), ("=", "egal cu")]),
    ("sk", &[("+", "plus"), ("-", "mínus"), ("×", "krát"), ("÷", "delené"), ("=", "rovná sa")]),
    ("bg", &[("+", "плюс"), ("-", "минус"), ("×", "по"), ("÷", "делено на"), ("=", "е равно на")]),
    ("he", &[("+", "ועוד"), ("-", "פחות"), ("×", "כפול"), ("÷", "חלקי"), ("=", "שווה")]),
    ("th", &[("+", "บวก"), ("-", "ลบ"), ("×", "คูณ"), ("÷", "หาร"), ("=", "เท่ากับ")]),
    ("tl", &[("+", "dagdag"), ("-", "bawas"), ("×", "beses"), ("÷", "hinati sa"), ("=", "ay katumbas ng")]),
    ("ms", &[("+", "tambah"), ("-", "tolak"), ("×", "darab"), ("÷", "bahagi"), ("=", "sama dengan")]),
    ("ka", &[("+", "პლუს"), ("-", "მინუს"), ("×", "გამრავლებული"), ("÷", "გაყოფილი"), ("=", "უდრის")]),
    ("ta", &[("+", "கூட்டல்"), ("-", "கழித்தல்"), ("×", "பெருக்கல்"), ("÷", "வகுத்தல்"), ("=", "சமம்")]),
    ("gu", &[("+", "વત્તા"), ("-", "બાદ"), ("×", "ગુણ્યા"), ("÷", "ભાગ્યા"), ("=", "બરાબર")]),
    ("kn", &[("+", "ಕೂಡು"), ("-", "ಕಳೆ"), ("×", "ಗುಣಿಸು"), ("÷", "ಭಾಗಿಸು"), ("=", "ಸಮ")]),
    ("ml", &[("+", "കൂട്ടുക"), ("-", "കുറയ്ക്കുക"), ("×", "ഗുണം"), ("÷", "ഹരിക്കുക"), ("=", "സമം")]),
    ("pa", &[("+", "ਜੋੜ"), ("-", "ਘਟਾਓ"), ("×", "ਗੁਣਾ"), ("÷", "ਭਾਗ"), ("=", "ਬਰਾਬਰ")]),
    ("or", &[("+", "ଯୋଗ"), ("-", "ବିଯୋଗ"), ("×", "ଗୁଣନ"), ("÷", "ଭାଗ"), ("=", "ସମାନ")]),
    ("ru", &[("+", "плюс"), ("-", "минус"), ("×", "умножить на"), ("÷", "разделить на"), ("=", "равно")]),
    ("sv", &[("+", "plus"), ("-", "minus"), ("×", "gånger"), ("÷", "delat med"), ("=", "är lika med")]),
    ("hu", &[("+", "plusz"), ("-", "mínusz"), ("×", "szorozva"), ("÷", "osztva"), ("=", "egyenlő")]),
    ("ar", &[("+", "زائد"), ("-", "ناقص"), ("×", "ضرب"), ("÷", "على"), ("=", "يساوي")]),
    ("vi", &[("+", "cộng"), ("-", "trừ"), ("×", "nhân"), ("÷", "chia"), ("=", "bằng")]),
    ("id", &[("+", "tambah"), ("-", "kurang"), ("×", "kali"), ("÷", "bagi"), ("=", "sama dengan")]),
    ("hi", &[("+", "धन"), ("-", "घटा"), ("×", "गुणा"), ("÷", "भाग"), ("=", "बराबर")]),
    ("bn", &[("+", "যোগ"), ("-", "বিয়োগ"), ("×", "গুণ"), ("÷", "ভাগ"), ("=", "সমান")]),
    ("te", &[("+", "కూడిక"), ("-", "తీసివేత"), ("×", "గుణకారం"), ("÷", "భాగహారం"), ("=", "సమానం")]),
    ("mr", &[("+", "अधिक"), ("-", "वजा"), ("×", "गुणिले"), ("÷", "भागिले"), ("=", "बरोबर")]),
    ("ur", &[("+", "جمع"), ("-", "منفی"), ("×", "ضرب"), ("÷", "تقسیم"), ("=", "برابر")]),
];

const GLUED_OPS: &[&str] = &["ja", "zh", "th"]; // operator words are written without spaces
// = in a sum of numbers only, where the idiom is shorter than OPS's reading of = (sv “två plus två är fyra”; with a
// variable it stays “x är lika med fem”)
const SUM_EQUALS: &[(&str, &str)] = &[("sv", "är")];

/// Whether `w` is the first word of one of the language's operator words (the agreement rules must not take “plus” or
/// “равно” after a number for a noun: cs “jedna plus”, not “jeden plus”). Prototype `is_op_word`.
pub(super) fn is_op_word(lang: &str, w: &str) -> bool {
    OPS.iter().find(|(l, _)| *l == lang).is_some_and(|(_, ops)| {
        ops.iter().any(|(k, v)| "+-×÷=".contains(*k) && !v.is_empty() && v.split(' ').next() == Some(w))
    })
}
const NUMBER: &str = r"[0-9]+(?:[.,][0-9]+)*";

fn all_operators(t: String, c: &mut Ctx) -> String {
    let lang = c.lang().to_string();
    let Some(ops) = OPS.iter().find(|(l, _)| *l == lang).map(|x| x.1) else { return t };
    let glued = GLUED_OPS.contains(&lang.as_str());
    let letter = r"[A-Za-z](?![^\W\d_])";
    let term = rx(&format!(r"[ \t]*([-−+×÷=±])[ \t]*(-?{NUMBER}|{letter})"));
    let pat = format!(
        r"((?<![A-Za-z0-9_.,:+±−-])(?<![0-9][/*^])(?<![0-9][/*^][ \t])(?<![0-9][ \t][/*^][ \t]){NUMBER}|(?<![^\s(\[]){letter})((?:[ \t]*[-−+×÷=±][ \t]*(?:-?{NUMBER}|{letter}))+)(?![A-Za-z0-9_:^]|/\d|[.,][0-9])"
    );
    let is_alpha = |v: &str| !v.is_empty() && v.chars().all(char::is_alphabetic);
    let mut t = c.sub(&rx(&pat), &t, |m| {
        let terms: Vec<(String, String)> = term
            .captures_iter(g(m, 2))
            .flatten()
            .map(|x| (if g(&x, 1) == "−" { "-" } else { g(&x, 1) }.to_string(), g(&x, 2).to_string()))
            .collect();
        if terms.iter().all(|(op, _)| op == "-") || !terms.iter().any(|(op, _)| lookup(ops, op).is_some()) {
            return None; // a range, a date, a score: no sum
        }
        let letters = usize::from(is_alpha(g(m, 1))) + terms.iter().filter(|(_, v)| is_alpha(v)).count();
        if letters > 0 && (!terms.iter().any(|(op, _)| op == "=") || letters == terms.len() + 1) {
            return None; // a letter is a variable only in an equation that has a number
        }
        if lang == "ko" {
            let mut out = words(g(m, 1), "ko");
            for (op, num) in &terms {
                let said = words(num, "ko");
                if op == "=" {
                    let topic = if hangul_final(&out) { "은" } else { "는" };
                    out = format!("{out}{topic} {said}");
                } else {
                    let w = lookup(ops, op).filter(|w| !w.is_empty()).unwrap_or(op);
                    out = format!("{out} {w} {said}");
                }
            }
            return Some(verbatim(&out));
        }
        let mut out = g(m, 1).to_string();
        let last = terms.len() - 1;
        for (i, (op, num)) in terms.iter().enumerate() {
            if lang == "ka" && op == "=" && i == last && !num.is_empty() && num.chars().all(|ch| ch.is_ascii_digit()) {
                out = format!("{out} = {num}"); // ka.equals reads it, with the dative
                continue;
            }
            let sum_eq = if op == "=" && letters == 0 { lookup(SUM_EQUALS, &lang) } else { None };
            let w = sum_eq.or_else(|| lookup(ops, op)).unwrap_or(op);
            out = if glued { format!("{out}{w}{num}") } else { format!("{out} {w} {num}") };
        }
        Some(out)
    });
    if let Some(pm) = lookup(ops, "±") {
        let repl = format!("{pm}{}", if glued { "" } else { " " });
        t = c.sub_tpl(&rx(r"(?<![A-Za-z0-9_)])±[ \t]?(?=[0-9])"), &t, &repl);
    }
    if let Some(and) = lookup(ops, "&") {
        t = c.sub_tpl(&rx(r"(?<=[^\W\d_]) & (?=[^\W\d_])"), &t, &format!(" {and} "));
    }
    t
}
