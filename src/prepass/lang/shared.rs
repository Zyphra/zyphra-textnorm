//! Shared rules: the port of the workbench's `langrules/shared.py` (ids `all.*`): S05 leading zeros, S06 phone
//! numbers, S18 operator words, S23 email addresses and URLs, S32 Unicode fractions, dollar signs with a country
//! prefix (US$, HK$, A$, C$, NZ$, S$, NT$, R$). The words these rules write
//! themselves (an address, a phone number, a code) are wrapped in U+E000 … U+E001 so the grammar passes them through.

use super::super::{Ctx, chars_before, g, is_alnum, matches_at_start, rx, search};
use super::{LangRule, digit_words, words};

/// Run right after `en.url`.
pub(in crate::prepass) const EARLY: &[LangRule] = &[
    ("all.email-url", all_email_url),
    ("all.dollar-prefix", all_dollar_prefix),
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

// ------------------------------------------------------------------------------------------------- dollar prefixes

const DP_PREFIX: &[(&str, &str)] = &[
    ("US", "US"),
    ("HK", "HK"),
    ("AU", "AU"),
    ("CA", "CA"),
    ("NZ", "NZ"),
    ("SG", "SG"),
    ("NT", "TW"),
    ("A", "AU"),
    ("C", "CA"),
    ("S", "SG"),
    ("R", "BR"),
];
const DP_COMMA: &[&str] = &[
    "de", "es", "fr", "it", "pt", "nl", "pl", "tr", "uk", "cs", "da", "fi", "el", "nb", "ro", "sk", "bg", "ru", "sv",
    "hu", "vi", "id", "ka",
];
const DP_SCALE: &[(&str, &str)] = &[
    ("en", r"[ \x{A0}]?(?:million|billion|trillion|bn|mn|tn|m|b|k)"),
    ("de", r"[ \x{A0}](?:Mio\.|Mrd\.|Millionen|Million|Milliarden|Milliarde|Billionen|Billion)"),
    ("es", r"[ \x{A0}](?:mil millones|millones|millón|billones|billón|mil)"),
    ("fr", r"[ \x{A0}](?:millions|million|milliards|milliard|billions|billion)"),
    ("it", r"[ \x{A0}](?:milioni|milione|miliardi|miliardo|bilioni|bilione|mln|mld|mila)"),
    ("pt", r"[ \x{A0}](?:milhões|milhão|bilhões|bilhão|trilhões|trilhão|mil|mi|bi|tri)"),
    ("nl", r"[ \x{A0}](?:miljoen|miljard|biljoen|mln\.?|mld\.?)"),
    ("pl", r"[ \x{A0}](?:mln|mld|bln|milionów|miliony|milion|miliardów|miliardy|miliard|bilionów|biliony|bilion)"),
    ("tr", r"[ \x{A0}](?:milyon|milyar|trilyon|bin)"),
    (
        "uk",
        r"[ \x{A0}](?:млн|млрд|трлн|мільйонів|мільйони|мільйон|мільярдів|мільярди|мільярд|трильйонів|трильйони|трильйон)",
    ),
    ("cs", r"[ \x{A0}](?:mil\.|mld\.|bil\.|milionů|miliony|milion|miliardy|miliard|bilionů|biliony|bilion)"),
    ("sk", r"[ \x{A0}](?:mil\.|mld\.|bil\.|miliónov|milióny|milión|miliárd|miliardy|miliarda|biliónov|bilióny|bilión)"),
    ("bg", r"[ \x{A0}](?:млн\.?|млрд\.?|трлн\.?|милиона|милион|милиарда|милиард|трилиона|трилион)"),
    ("da", r"[ \x{A0}](?:mio\.|mia\.|mio|mia|millioner|million|milliarder|milliard|billioner|billion)"),
    ("nb", r"[ \x{A0}](?:mill\.|mrd\.|mill|mrd|millioner|million|milliarder|milliard|billioner|billion)"),
    ("fi", r"[ \x{A0}](?:milj\.|mrd\.|miljoonaa|miljoona|miljardia|miljardi|biljoonaa|biljoona)"),
    (
        "el",
        r"[ \x{A0}](?:εκατ\.|δισ\.|τρισ\.|εκατομμύρια|εκατομμύριο|δισεκατομμύρια|δισεκατομμύριο|τρισεκατομμύρια|τρισεκατομμύριο)",
    ),
    ("ro", r"[ \x{A0}](?:milioane|milion|miliarde|miliard|trilioane|trilion|mil\.|mld\.)"),
    ("he", r"[ \x{A0}](?:מיליון|מיליארד|טריליון)"),
    ("th", r"[ \x{A0}]?(?:พันล้าน|ล้าน)"),
    ("ka", r"[ \x{A0}](?:მილიონი|მილიარდი|ტრილიონი|მლნ|მლრდ)"),
    ("ru", r"[ \x{A0}](?:млн|млрд|трлн)"),
    ("hu", r"[ \x{A0}](?:millió|milliárd|billió)"),
    ("ar", r"[ \x{A0}](?:مليون|مليار|تريليون)"),
    ("ja", r"(?:万|億|兆)"),
    ("zh", r"(?:万|亿|億|兆)"),
    ("ko", r"(?:만|억|조)"),
    ("ml", r"[ \x{A0}](?:ദശലക്ഷം|കോടി|ലക്ഷം)"),
    ("pa", r"[ \x{A0}](?:ਮਿਲੀਅਨ|ਕਰੋੜ|ਲੱਖ|ਅਰਬ)"),
    ("or", r"[ \x{A0}](?:ମିଲିୟନ|କୋଟି|ଲକ୍ଷ)"),
    ("bn", r"[ \x{A0}](?:মিলিয়ন|কোটি|লাখ)"),
    ("ta", r"[ \x{A0}](?:மில்லியன்|கோடி|லட்சம்)"),
    ("kn", r"[ \x{A0}](?:ಮಿಲಿಯನ್|ಕೋಟಿ|ಲಕ್ಷ)"),
    ("te", r"[ \x{A0}](?:మిలియన్|కోట్ల|కోటి|లక్షల|లక్ష)"),
    ("ur", r"[ \x{A0}](?:ملین|کروڑ|لاکھ|ارب)"),
    ("hi", r"[ \x{A0}](?:मिलियन|करोड़|लाख|अरब)"),
    ("gu", r"[ \x{A0}](?:મિલિયન|કરોડ|લાખ|અબજ)"),
    ("mr", r"[ \x{A0}](?:दशलक्ष|मिलियन|कोटी|लाख|अब्ज)"),
    ("tl", r"[ \x{A0}](?:milyon|bilyon|trilyon)"),
    ("ms", r"[ \x{A0}](?:juta|bilion|trilion|ribu)"),
    ("id", r"[ \x{A0}](?:juta|miliar|triliun|ribu)"),
    ("vi", r"[ \x{A0}](?:triệu|tỷ|nghìn|ngàn)"),
    ("sv", r"[ \x{A0}](?:miljoner|miljon|miljarder|miljard|biljoner|biljon|mn|mdr)"),
];
const DP_FORM: &[(&str, &[(&str, How)])] = &[
    (
        "en",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "de",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "it",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "nl",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "pl",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "tr",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "uk",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "cs",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "sk",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "bg",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "da",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "nb",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "fi",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "el",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "ro",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "he",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "th",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "ka",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "ml",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "pa",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "or",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "hu",
        &[
            ("US", How::W),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    (
        "es",
        &[
            ("US", How::T("US${n}")),
            ("HK", How::W),
            ("AU", How::W),
            ("CA", How::W),
            ("NZ", How::W),
            ("SG", How::W),
            ("TW", How::W),
            ("BR", How::W),
        ],
    ),
    ("pt", &[("HK", How::W), ("AU", How::W), ("CA", How::W), ("NZ", How::W), ("SG", How::W), ("TW", How::W)]),
    (
        "fr",
        &[
            ("US", How::T("{n} $")),
            ("HK", How::T("{n} $ de Hong Kong")),
            ("AU", How::Pair("{n} $ australien", "{n} $ australiens")),
            ("CA", How::Pair("{n} $ canadien", "{n} $ canadiens")),
            ("NZ", How::T("{n} $ néo-zélandais")),
            ("SG", How::T("{n} $ de Singapour")),
            ("TW", How::T("{n} $ taïwanais")),
            ("BR", How::Pair("{n} réal brésilien", "{n} reais brésiliens")),
        ],
    ),
    (
        "ja",
        &[
            ("US", How::T("{n} USD")),
            ("HK", How::T("{n} HKD")),
            ("AU", How::T("{n} AUD")),
            ("CA", How::T("{n} CAD")),
            ("NZ", How::T("{n} NZD")),
            ("SG", How::T("{n} SGD")),
            ("TW", How::T("{n} TWD")),
            ("BR", How::T("{n}ブラジルレアル")),
        ],
    ),
    (
        "zh",
        &[
            ("US", How::T("{n} USD")),
            ("HK", How::T("{n} HKD")),
            ("AU", How::T("{n} AUD")),
            ("CA", How::T("{n} CAD")),
            ("NZ", How::T("{n} NZD")),
            ("SG", How::T("{n} SGD")),
            ("TW", How::T("{n} TWD")),
            ("BR", How::T("R${n}")),
        ],
    ),
    (
        "ko",
        &[
            ("US", How::T("{n} USD")),
            ("HK", How::T("{n} HKD")),
            ("AU", How::T("{n} AUD")),
            ("CA", How::T("{n} CAD")),
            ("NZ", How::T("{n} NZD")),
            ("SG", How::T("{n} SGD")),
            ("TW", How::T("{n} TWD")),
            ("BR", How::T("{n} 브라질 헤알")),
        ],
    ),
    (
        "ar",
        &[
            ("US", How::Pair("{P}${n}", "{n} USD")),
            ("AU", How::Pair("{P}${n}", "{n} AUD")),
            ("CA", How::Pair("{P}${n}", "{n} CAD")),
            ("NZ", How::Pair("{P}${n}", "{n} NZD")),
            ("SG", How::Pair("{P}${n}", "{n} SGD")),
            ("BR", How::Pair("{P}${n}", "{n} BRL")),
        ],
    ),
    ("ru", &[("CA", How::T("CA${n}")), ("SG", How::T("S${n}"))]),
    ("bn", &[("HK", How::W), ("AU", How::T("A${n}")), ("NZ", How::W), ("SG", How::W), ("TW", How::W)]),
    ("ta", &[("AU", How::T("A${n}")), ("SG", How::T("S${n}")), ("TW", How::W)]),
    ("kn", &[("AU", How::T("A${n}")), ("SG", How::T("S${n}")), ("TW", How::W)]),
    ("te", &[("AU", How::T("A${n}")), ("SG", How::T("S${n}")), ("TW", How::W)]),
    ("ur", &[("SG", How::T("S${n}")), ("TW", How::W)]),
    ("gu", &[("AU", How::T("A${n}")), ("SG", How::T("S${n}"))]),
    ("mr", &[("AU", How::T("A${n}")), ("SG", How::T("S${n}"))]),
    ("hi", &[("SG", How::T("S${n}"))]),
    ("tl", &[("SG", How::T("S${n}"))]),
    ("ms", &[("SG", How::T("S${n}"))]),
    ("id", &[("SG", How::T("S${n}"))]),
];
const DP_WORDS: &[DpWords] = &[
    (
        "en",
        &["dollars", "dollar"],
        "",
        0,
        &[
            ("US", &["US dollars", "US dollar"]),
            ("HK", &["Hong Kong dollars", "Hong Kong dollar"]),
            ("AU", &["Australian dollars", "Australian dollar"]),
            ("CA", &["Canadian dollars", "Canadian dollar"]),
            ("NZ", &["New Zealand dollars", "New Zealand dollar"]),
            ("SG", &["Singapore dollars", "Singapore dollar"]),
            ("TW", &["New Taiwan dollars", "New Taiwan dollar"]),
            ("BR", &["Brazilian reais", "Brazilian real"]),
        ],
    ),
    (
        "de",
        &["1:dollar", "dollar"],
        "",
        1,
        &[
            ("US", &["US-Dollar", "US-Dollar"]),
            ("HK", &["Hongkong-Dollar", "Hongkong-Dollar"]),
            ("AU", &["australischer Dollar", "australische Dollar"]),
            ("CA", &["kanadischer Dollar", "kanadische Dollar"]),
            ("NZ", &["Neuseeland-Dollar", "Neuseeland-Dollar"]),
            ("SG", &["Singapur-Dollar", "Singapur-Dollar"]),
            ("TW", &["Taiwan-Dollar", "Taiwan-Dollar"]),
            ("BR", &["brasilianischer Real", "brasilianische Real"]),
        ],
    ),
    (
        "es",
        &["dólares", "dólar"],
        "de ",
        0,
        &[
            ("US", &["dólares estadounidenses", "dólar estadounidense"]),
            ("HK", &["dólares de Hong Kong", "dólar de Hong Kong"]),
            ("AU", &["dólares australianos", "dólar australiano"]),
            ("CA", &["dólares canadienses", "dólar canadiense"]),
            ("NZ", &["dólares neozelandeses", "dólar neozelandés"]),
            ("SG", &["dólares de Singapur", "dólar de Singapur"]),
            ("TW", &["dólares taiwaneses", "dólar taiwanés"]),
            ("BR", &["reales brasileños", "real brasileño"]),
        ],
    ),
    (
        "it",
        &["dollari", "dollaro"],
        "di ",
        0,
        &[
            ("US", &["dollari statunitensi", "dollaro statunitense"]),
            ("HK", &["dollari di Hong Kong", "dollaro di Hong Kong"]),
            ("AU", &["dollari australiani", "dollaro australiano"]),
            ("CA", &["dollari canadesi", "dollaro canadese"]),
            ("NZ", &["dollari neozelandesi", "dollaro neozelandese"]),
            ("SG", &["dollari di Singapore", "dollaro di Singapore"]),
            ("TW", &["dollari taiwanesi", "dollaro taiwanese"]),
            ("BR", &["real brasiliani", "real brasiliano"]),
        ],
    ),
    ("fr", &["dollars", "dollar"], "de ", 0, &[("BR", &["reais brésiliens", "réal brésilien"])]),
    (
        "pt",
        &["dólares", "dólar"],
        "de ",
        0,
        &[
            ("HK", &["dólares de Hong Kong", "dólar de Hong Kong"]),
            ("AU", &["dólares australianos", "dólar australiano"]),
            ("CA", &["dólares canadenses", "dólar canadense"]),
            ("NZ", &["dólares neozelandeses", "dólar neozelandês"]),
            ("SG", &["dólares de Singapura", "dólar de Singapura"]),
            ("TW", &["dólares taiwaneses", "dólar taiwanês"]),
        ],
    ),
    (
        "nl",
        &["dollar"],
        "",
        0,
        &[
            ("US", &["Amerikaanse dollar"]),
            ("HK", &["Hongkongse dollar"]),
            ("AU", &["Australische dollar"]),
            ("CA", &["Canadese dollar"]),
            ("NZ", &["Nieuw-Zeelandse dollar"]),
            ("SG", &["Singaporese dollar"]),
            ("TW", &["Taiwanese dollar"]),
            ("BR", &["Braziliaanse real"]),
        ],
    ),
    (
        "pl",
        &["dolarów", "dolary", "dolara", "dolar"],
        "",
        0,
        &[
            ("US", &["dolarów", "dolary", "dolara", "dolar"]),
            ("HK", &["dolarów hongkońskich", "dolary hongkońskie", "dolara hongkońskiego", "dolar hongkoński"]),
            ("AU", &["dolarów australijskich", "dolary australijskie", "dolara australijskiego", "dolar australijski"]),
            ("CA", &["dolarów kanadyjskich", "dolary kanadyjskie", "dolara kanadyjskiego", "dolar kanadyjski"]),
            (
                "NZ",
                &["dolarów nowozelandzkich", "dolary nowozelandzkie", "dolara nowozelandzkiego", "dolar nowozelandzki"],
            ),
            ("SG", &["dolarów singapurskich", "dolary singapurskie", "dolara singapurskiego", "dolar singapurski"]),
            ("TW", &["dolarów tajwańskich", "dolary tajwańskie", "dolara tajwańskiego", "dolar tajwański"]),
            ("BR", &["reali brazylijskich", "reale brazylijskie", "reala brazylijskiego", "real brazylijski"]),
        ],
    ),
    (
        "tr",
        &["dolar"],
        "",
        0,
        &[
            ("US", &["amerikan doları"]),
            ("HK", &["Hong Kong doları"]),
            ("AU", &["avustralya doları"]),
            ("CA", &["kanada doları"]),
            ("NZ", &["Yeni Zelanda doları"]),
            ("SG", &["Singapur doları"]),
            ("TW", &["Yeni Tayvan doları"]),
            ("BR", &["brezilya reali"]),
        ],
    ),
    (
        "uk",
        &["доларів", "долари", "долара", "долар"],
        "",
        0,
        &[
            ("US", &["доларів", "долари", "долара", "долар"]),
            ("HK", &["гонконгських доларів", "гонконгські долари", "гонконгського долара", "гонконгський долар"]),
            (
                "AU",
                &["австралійських доларів", "австралійські долари", "австралійського долара", "австралійський долар"],
            ),
            ("CA", &["канадських доларів", "канадські долари", "канадського долара", "канадський долар"]),
            (
                "NZ",
                &[
                    "новозеландських доларів",
                    "новозеландські долари",
                    "новозеландського долара",
                    "новозеландський долар",
                ],
            ),
            ("SG", &["сінгапурських доларів", "сінгапурські долари", "сінгапурського долара", "сінгапурський долар"]),
            ("TW", &["тайванських доларів", "тайванські долари", "тайванського долара", "тайванський долар"]),
            ("BR", &["бразильських реалів", "бразильські реали", "бразильського реала", "бразильський реал"]),
        ],
    ),
    (
        "cs",
        &["dolarů", "dolary", "dolaru", "dolar"],
        "",
        0,
        &[
            ("US", &["dolarů", "dolary", "dolaru", "dolar"]),
            ("HK", &["hongkongských dolarů", "hongkongské dolary", "hongkongského dolaru", "hongkongský dolar"]),
            ("AU", &["australských dolarů", "australské dolary", "australského dolaru", "australský dolar"]),
            ("CA", &["kanadských dolarů", "kanadské dolary", "kanadského dolaru", "kanadský dolar"]),
            (
                "NZ",
                &["novozélandských dolarů", "novozélandské dolary", "novozélandského dolaru", "novozélandský dolar"],
            ),
            ("SG", &["singapurských dolarů", "singapurské dolary", "singapurského dolaru", "singapurský dolar"]),
            ("TW", &["tchajwanských dolarů", "tchajwanské dolary", "tchajwanského dolaru", "tchajwanský dolar"]),
            ("BR", &["brazilských realů", "brazilské realy", "brazilského realu", "brazilský real"]),
        ],
    ),
    (
        "sk",
        &["dolárov", "doláre", "dolára", "dolár"],
        "",
        0,
        &[
            ("US", &["dolárov", "doláre", "dolára", "dolár"]),
            ("HK", &["hongkonských dolárov", "hongkonské doláre", "hongkonského dolára", "hongkonský dolár"]),
            ("AU", &["austrálskych dolárov", "austrálske doláre", "austrálskeho dolára", "austrálsky dolár"]),
            ("CA", &["kanadských dolárov", "kanadské doláre", "kanadského dolára", "kanadský dolár"]),
            (
                "NZ",
                &["novozélandských dolárov", "novozélandské doláre", "novozélandského dolára", "novozélandský dolár"],
            ),
            ("SG", &["singapurských dolárov", "singapurské doláre", "singapurského dolára", "singapurský dolár"]),
            ("TW", &["taiwanských dolárov", "taiwanské doláre", "taiwanského dolára", "taiwanský dolár"]),
            ("BR", &["brazílskych realov", "brazílske realy", "brazílskeho realu", "brazílsky real"]),
        ],
    ),
    (
        "bg",
        &["долара", "долар"],
        "",
        0,
        &[
            ("US", &["долара", "долар"]),
            ("HK", &["хонконгски долара", "хонконгски долар"]),
            ("AU", &["австралийски долара", "австралийски долар"]),
            ("CA", &["канадски долара", "канадски долар"]),
            ("NZ", &["новозеландски долара", "новозеландски долар"]),
            ("SG", &["сингапурски долара", "сингапурски долар"]),
            ("TW", &["тайвански долара", "тайвански долар"]),
            ("BR", &["бразилски реала", "бразилски реал"]),
        ],
    ),
    (
        "da",
        &["1:dollar", "dollar"],
        "",
        1,
        &[
            ("US", &["amerikansk dollar", "amerikanske dollar"]),
            ("HK", &["hongkongsk dollar", "hongkongske dollar"]),
            ("AU", &["australsk dollar", "australske dollar"]),
            ("CA", &["canadisk dollar", "canadiske dollar"]),
            ("NZ", &["newzealandsk dollar", "newzealandske dollar"]),
            ("SG", &["singaporeansk dollar", "singaporeanske dollar"]),
            ("TW", &["taiwansk dollar", "taiwanske dollar"]),
            ("BR", &["brasiliansk real", "brasilianske real"]),
        ],
    ),
    (
        "nb",
        &["1:dollar", "dollar"],
        "",
        1,
        &[
            ("US", &["dollar", "dollar"]),
            ("HK", &["hongkongsk dollar", "hongkongske dollar"]),
            ("AU", &["australsk dollar", "australske dollar"]),
            ("CA", &["kanadisk dollar", "kanadiske dollar"]),
            ("NZ", &["newzealandsk dollar", "newzealandske dollar"]),
            ("SG", &["singaporsk dollar", "singaporske dollar"]),
            ("TW", &["taiwansk dollar", "taiwanske dollar"]),
            ("BR", &["brasiliansk real", "brasilianske real"]),
        ],
    ),
    (
        "fi",
        &["dollaria", "dollari"],
        "",
        0,
        &[
            ("US", &["Yhdysvaltain dollaria", "Yhdysvaltain dollari"]),
            ("HK", &["Hongkongin dollaria", "Hongkongin dollari"]),
            ("AU", &["Australian dollaria", "Australian dollari"]),
            ("CA", &["Kanadan dollaria", "Kanadan dollari"]),
            ("NZ", &["Uuden-Seelannin dollaria", "Uuden-Seelannin dollari"]),
            ("SG", &["Singaporen dollaria", "Singaporen dollari"]),
            ("TW", &["Taiwanin dollaria", "Taiwanin dollari"]),
            ("BR", &["Brasilian realia", "Brasilian real"]),
        ],
    ),
    (
        "el",
        &["δολάρια", "δολάριο"],
        "",
        0,
        &[
            ("US", &["δολάρια", "δολάριο"]),
            ("HK", &["δολάρια Χονγκ Κονγκ", "δολάριο Χονγκ Κονγκ"]),
            ("AU", &["δολάρια Αυστραλίας", "δολάριο Αυστραλίας"]),
            ("CA", &["δολάρια Καναδά", "δολάριο Καναδά"]),
            ("NZ", &["δολάρια Νέας Ζηλανδίας", "δολάριο Νέας Ζηλανδίας"]),
            ("SG", &["δολάρια Σιγκαπούρης", "δολάριο Σιγκαπούρης"]),
            ("TW", &["δολάρια Ταϊβάν", "δολάριο Ταϊβάν"]),
            ("BR", &["ρεάλ Βραζιλίας", "ρεάλ Βραζιλίας"]),
        ],
    ),
    (
        "ro",
        &["dolari", "dolar"],
        "de ",
        0,
        &[
            ("US", &["dolari", "dolar"]),
            ("HK", &["dolari din Hong Kong", "dolar din Hong Kong"]),
            ("AU", &["dolari australieni", "dolar australian"]),
            ("CA", &["dolari canadieni", "dolar canadian"]),
            ("NZ", &["dolari neozeelandezi", "dolar neozeelandez"]),
            ("SG", &["dolari singaporezi", "dolar singaporez"]),
            ("TW", &["dolari taiwanezi", "dolar taiwanez"]),
            ("BR", &["reali brazilieni", "real brazilian"]),
        ],
    ),
    (
        "he",
        &["דולרים", "דולר"],
        "",
        1,
        &[
            ("US", &["דולרים", "דולר"]),
            ("HK", &["דולרים הונג קונגיים", "דולר הונג קונגי"]),
            ("AU", &["דולרים אוסטרליים", "דולר אוסטרלי"]),
            ("CA", &["דולרים קנדיים", "דולר קנדי"]),
            ("NZ", &["דולרים ניו זילנדיים", "דולר ניו זילנדי"]),
            ("SG", &["דולרים סינגפוריים", "דולר סינגפורי"]),
            ("TW", &["דולרים טאיוואניים", "דולר טאיוואני"]),
            ("BR", &["ריאלים ברזילאיים", "ריאל ברזילאי"]),
        ],
    ),
    (
        "th",
        &["ดอลลาร์"],
        "",
        0,
        &[
            ("US", &["ดอลลาร์สหรัฐ"]),
            ("HK", &["ดอลลาร์ฮ่องกง"]),
            ("AU", &["ดอลลาร์ออสเตรเลีย"]),
            ("CA", &["ดอลลาร์แคนาดา"]),
            ("NZ", &["ดอลลาร์นิวซีแลนด์"]),
            ("SG", &["ดอลลาร์สิงคโปร์"]),
            ("TW", &["ดอลลาร์ไต้หวัน"]),
            ("BR", &["เรียลบราซิล"]),
        ],
    ),
    (
        "ka",
        &["დოლარი"],
        "",
        0,
        &[
            ("US", &["დოლარი"]),
            ("HK", &["ჰონკონგური დოლარი"]),
            ("AU", &["ავსტრალიური დოლარი"]),
            ("CA", &["კანადური დოლარი"]),
            ("NZ", &["ახალზელანდიური დოლარი"]),
            ("SG", &["სინგაპურული დოლარი"]),
            ("TW", &["ტაივანური დოლარი"]),
            ("BR", &["ბრაზილიური რეალი"]),
        ],
    ),
    (
        "ml",
        &["ഡോളർ"],
        "",
        0,
        &[
            ("US", &["ഡോളർ"]),
            ("HK", &["ഹോങ്കോങ് ഡോളർ"]),
            ("AU", &["ഓസ്ട്രേലിയൻ ഡോളർ"]),
            ("CA", &["കനേഡിയൻ ഡോളർ"]),
            ("NZ", &["ന്യൂസിലൻഡ് ഡോളർ"]),
            ("SG", &["സിംഗപ്പൂർ ഡോളർ"]),
            ("TW", &["തായ്\u{200c}വാൻ ഡോളർ"]),
            ("BR", &["ബ്രസീലിയൻ റിയാൽ"]),
        ],
    ),
    (
        "pa",
        &["ਡਾਲਰ"],
        "",
        0,
        &[
            ("US", &["ਡਾਲਰ"]),
            ("HK", &["ਹਾਂਗ ਕਾਂਗ ਡਾਲਰ"]),
            ("AU", &["ਆਸਟ੍ਰੇਲੀਆਈ ਡਾਲਰ"]),
            ("CA", &["ਕੇਨੇਡਿਆਈ ਡਾਲਰ"]),
            ("NZ", &["ਨਿਊਜ਼ੀਲੈਂਡ ਡਾਲਰ"]),
            ("SG", &["ਸਿੰਗਾਪੁਰ ਡਾਲਰ"]),
            ("TW", &["ਤਾਈਵਾਨ ਡਾਲਰ"]),
            ("BR", &["ਬ੍ਰਾਜ਼ੀਲੀਆਈ ਰੀਅਲ"]),
        ],
    ),
    (
        "or",
        &["ଡଲାର୍"],
        "",
        0,
        &[
            ("US", &["ଡଲାର୍"]),
            ("HK", &["ହଂକଂ ଡଲାର୍"]),
            ("AU", &["ଅଷ୍ଟ୍ରେଲିୟ ଡଲାର୍"]),
            ("CA", &["କାନେଡିୟ ଡଲାର୍"]),
            ("NZ", &["ନ୍ୟୁଜିଲାଣ୍ଡ ଡଲାର୍"]),
            ("SG", &["ସିଙ୍ଗାପୁର ଡଲାର୍"]),
            ("TW", &["ତାଇୱାନ ଡଲାର୍"]),
            ("BR", &["ବ୍ରାଜିଲିୟ ରିଆଲ୍"]),
        ],
    ),
    (
        "bn",
        &["ডলার"],
        "",
        0,
        &[
            ("US", &["মার্কিন ডলার"]),
            ("HK", &["হংকং ডলার"]),
            ("AU", &["অস্ট্রেলীয় ডলার"]),
            ("CA", &["কানাডিয়ান ডলার"]),
            ("NZ", &["নিউজিল্যান্ড ডলার"]),
            ("SG", &["সিঙ্গাপুর ডলার"]),
            ("TW", &["তাইওয়ান ডলার"]),
            ("BR", &["ব্রাজিলিয়ান রিয়েল"]),
        ],
    ),
    (
        "ta",
        &["டாலர்கள்", "டாலர்"],
        "",
        0,
        &[
            ("US", &["டாலர்கள்", "டாலர்"]),
            ("HK", &["ஹாங்காங் டாலர்கள்", "ஹாங்காங் டாலர்"]),
            ("AU", &["ஆஸ்திரேலிய டாலர்கள்", "ஆஸ்திரேலிய டாலர்"]),
            ("CA", &["கனடியன் டாலர்கள்", "கனடியன் டாலர்"]),
            ("NZ", &["நியூசிலாந்து டாலர்கள்", "நியூசிலாந்து டாலர்"]),
            ("SG", &["சிங்கப்பூர் டாலர்கள்", "சிங்கப்பூர் டாலர்"]),
            ("TW", &["தைவான் டாலர்கள்", "தைவான் டாலர்"]),
            ("BR", &["பிரேசிலியன் ரியால்", "பிரேசிலியன் ரியால்"]),
        ],
    ),
    (
        "kn",
        &["ಡಾಲರ್"],
        "",
        0,
        &[
            ("US", &["ಯುಎಸ್ ಡಾಲರ್"]),
            ("HK", &["ಹಾಂಗ್ ಕಾಂಗ್ ಡಾಲರ್"]),
            ("AU", &["ಆಸ್ಟ್ರೇಲಿಯನ್ ಡಾಲರ್"]),
            ("CA", &["ಕೆನಡಿಯನ್ ಡಾಲರ್"]),
            ("NZ", &["ನ್ಯೂಜಿಲೆಂಡ್ ಡಾಲರ್"]),
            ("SG", &["ಸಿಂಗಾಪುರ್ ಡಾಲರ್"]),
            ("TW", &["ತೈವಾನ್ ಡಾಲರ್"]),
            ("BR", &["ಬ್ರೆಜಿಲಿಯನ್ ರಿಯಲ್"]),
        ],
    ),
    (
        "te",
        &["డాలర్లు", "డాలర్"],
        "",
        0,
        &[
            ("US", &["అమెరికన్ డాలర్లు", "అమెరికన్ డాలర్"]),
            ("HK", &["హాంకాంగ్ డాలర్లు", "హాంకాంగ్ డాలర్"]),
            ("AU", &["ఆస్ట్రేలియన్ డాలర్లు", "ఆస్ట్రేలియన్ డాలర్"]),
            ("CA", &["కెనడియన్ డాలర్లు", "కెనడియన్ డాలర్"]),
            ("NZ", &["న్యూజిలాండ్ డాలర్లు", "న్యూజిలాండ్ డాలర్"]),
            ("SG", &["సింగపూర్ డాలర్లు", "సింగపూర్ డాలర్"]),
            ("TW", &["తైవాన్ డాలర్లు", "తైవాన్ డాలర్"]),
            ("BR", &["బ్రెజిలియన్ రియల్\u{200c}లు", "బ్రెజిలియన్ రియల్"]),
        ],
    ),
    (
        "hu",
        &["dollár"],
        "",
        0,
        &[
            ("US", &["amerikai dollár"]),
            ("HK", &["hongkongi dollár"]),
            ("AU", &["ausztrál dollár"]),
            ("CA", &["kanadai dollár"]),
            ("NZ", &["új-zélandi dollár"]),
            ("SG", &["szingapúri dollár"]),
            ("TW", &["tajvani dollár"]),
            ("BR", &["brazil real"]),
        ],
    ),
    (
        "hi",
        &["डॉलर"],
        "",
        0,
        &[
            ("US", &["अमेरिकी डॉलर"]),
            ("HK", &["हांगकांग डॉलर"]),
            ("AU", &["ऑस्ट्रेलियाई डॉलर"]),
            ("CA", &["कनाडाई डॉलर"]),
            ("NZ", &["न्यूज़ीलैंड डॉलर"]),
            ("SG", &["सिंगापुर डॉलर"]),
            ("TW", &["नया ताइवान डॉलर"]),
            ("BR", &["ब्राज़ीलियाई रियाल"]),
        ],
    ),
    (
        "gu",
        &["ડૉલર"],
        "",
        0,
        &[
            ("US", &["યુએસ ડૉલર"]),
            ("HK", &["હોંગકોંગ ડૉલર"]),
            ("AU", &["ઑસ્ટ્રેલિયન ડૉલર"]),
            ("CA", &["કેનેડિયન ડૉલર"]),
            ("NZ", &["ન્યૂઝીલેન્ડ ડૉલર"]),
            ("SG", &["સિંગાપોર ડૉલર"]),
            ("TW", &["નવીન તાઇવાન ડૉલર"]),
            ("BR", &["બ્રાઝિલિયન રિયાલ"]),
        ],
    ),
    (
        "mr",
        &["डॉलर"],
        "",
        0,
        &[
            ("US", &["यूएस डॉलर"]),
            ("HK", &["हाँगकाँग डॉलर"]),
            ("AU", &["ऑस्ट्रेलियन डॉलर"]),
            ("CA", &["कॅनडियन डॉलर"]),
            ("NZ", &["न्यूझीलंड डॉलर"]),
            ("SG", &["सिंगापूर डॉलर"]),
            ("TW", &["नवीन तैवान डॉलर"]),
            ("BR", &["ब्राझिलियन रियाल"]),
        ],
    ),
    (
        "tl",
        &["dolyar"],
        "",
        0,
        &[
            ("US", &["dolyar ng US"]),
            ("HK", &["dolyar ng Hong Kong"]),
            ("AU", &["dolyar ng Australia"]),
            ("CA", &["dolyar ng Canada"]),
            ("NZ", &["dolyar ng New Zealand"]),
            ("SG", &["dolyar ng Singapore"]),
            ("TW", &["bagong dolyar ng Taiwan"]),
            ("BR", &["real ng Brazil"]),
        ],
    ),
    (
        "ar",
        &["دولار"],
        "",
        0,
        &[
            ("US", &["دولار أمريكي"]),
            ("HK", &["دولار هونج كونج"]),
            ("AU", &["دولار أسترالي"]),
            ("CA", &["دولار كندي"]),
            ("NZ", &["دولار نيوزيلندي"]),
            ("SG", &["دولار سنغافوري"]),
            ("TW", &["دولار تايواني"]),
            ("BR", &["ريال برازيلي"]),
        ],
    ),
    (
        "ur",
        &["ڈالر"],
        "",
        0,
        &[
            ("US", &["امریکی ڈالر"]),
            ("HK", &["ہانگ کانگ ڈالر"]),
            ("AU", &["آسٹریلوی ڈالر"]),
            ("CA", &["کینیڈین ڈالر"]),
            ("NZ", &["نیوزی لینڈ ڈالر"]),
            ("SG", &["سنگاپور ڈالر"]),
            ("TW", &["تائیوان ڈالر"]),
            ("BR", &["برازیلی ریئل"]),
        ],
    ),
    (
        "ms",
        &["dolar"],
        "",
        0,
        &[
            ("US", &["dolar Amerika"]),
            ("HK", &["dolar Hong Kong"]),
            ("AU", &["dolar Australia"]),
            ("CA", &["dolar Kanada"]),
            ("NZ", &["dolar New Zealand"]),
            ("SG", &["dolar Singapura"]),
            ("TW", &["dolar Baru Taiwan"]),
            ("BR", &["real Brazil"]),
        ],
    ),
    (
        "id",
        &["dolar"],
        "",
        0,
        &[
            ("US", &["dolar Amerika"]),
            ("HK", &["dolar Hong Kong"]),
            ("AU", &["dolar Australia"]),
            ("CA", &["dolar Kanada"]),
            ("NZ", &["dolar Selandia Baru"]),
            ("SG", &["dolar Singapura"]),
            ("TW", &["dolar Baru Taiwan"]),
            ("BR", &["real Brasil"]),
        ],
    ),
    (
        "vi",
        &["đô la"],
        "",
        0,
        &[
            ("US", &["đô la mỹ"]),
            ("HK", &["đô la hồng kông"]),
            ("AU", &["đô la úc"]),
            ("CA", &["đô la canada"]),
            ("NZ", &["đô la new zealand"]),
            ("SG", &["đô la singapore"]),
            ("TW", &["đô la đài loan"]),
            ("BR", &["real brazil"]),
        ],
    ),
    (
        "sv",
        &["dollar"],
        "",
        0,
        &[
            ("US", &["amerikanska dollar"]),
            ("HK", &["hongkongdollar"]),
            ("AU", &["australiska dollar"]),
            ("CA", &["kanadensiska dollar"]),
            ("NZ", &["nyzeeländska dollar"]),
            ("SG", &["singaporianska dollar"]),
            ("TW", &["taiwanesiska dollar"]),
            ("BR", &["realer"]),
        ],
    ),
];
const DP_OF: &[(&str, &[&str])] = &[
    ("es", &["mil millones", "millones", "millón", "billones", "billón"]),
    ("it", &["milioni", "milione", "miliardi", "miliardo", "bilioni", "bilione", "mln", "mld"]),
    ("pt", &["milhões", "milhão", "bilhões", "bilhão", "trilhões", "trilhão", "mi", "bi", "tri"]),
    ("ro", &["milioane", "milion", "miliarde", "miliard", "trilioane", "trilion", "mil.", "mld."]),
    ("fr", &["millions", "million", "milliards", "milliard", "billions", "billion"]),
];
const DP_SCALE_SAID: &[&str] = &["en"];
const DP_JOIN: &[(&str, &[&str])] =
    &[("de", &["million", "millionen", "milliarde", "milliarden", "billion", "billionen", "cent"])];
const DP_FIX: &[(&str, &[(&str, &str)])] = &[("hu", &[("kettő", "két")])];
const DP_CENTS: &[DpCents] = &[
    ("en", &["cents", "cent"], &[("dollars", "cents"), ("dollar", "cent"), ("reais", "centavos"), ("real", "centavo")]),
    ("de", &["", "Cent"], &[("Dollar", "Cent"), ("Real", "Centavos")]),
    (
        "es",
        &["centavos", "centavo"],
        &[("dólares", "centavos"), ("dólar", "centavo"), ("reales", "centavos"), ("real", "centavo")],
    ),
    (
        "it",
        &["centesimi", "centesimo"],
        &[
            ("dollari", "centesimi"),
            ("dollaro", "centesimo"),
            ("real brasiliani", "centavos brasiliani"),
            ("real brasiliano", "centavo brasiliano"),
        ],
    ),
    ("pt", &["centavos", "centavo"], &[("dólares", "centavos"), ("dólar", "centavo")]),
    ("nl", &["cent"], &[("dollar", "cent"), ("real", "centavo")]),
    (
        "pl",
        &["centów", "centy", "centa", "cent"],
        &[("dolarów", "centów"), ("dolary", "centy"), ("dolara", "centa"), ("dolar", "cent")],
    ),
    ("tr", &["sent"], &[("doları", "senti"), ("dolar", "sent")]),
    (
        "cs",
        &["centů", "centy", "centu", "cent"],
        &[("dolarů", "centů"), ("dolary", "centy"), ("dolaru", "centu"), ("dolar", "cent")],
    ),
    (
        "sk",
        &["centov", "centy", "centa", "cent"],
        &[("dolárov", "centov"), ("doláre", "centy"), ("dolára", "centa"), ("dolár", "cent")],
    ),
    ("bg", &["цента", "цент"], &[("долара", "цента"), ("долар", "цент"), ("реала", "сентаво"), ("реал", "сентаво")]),
    ("da", &["", "cent"], &[("dollar", "cent")]),
    ("nb", &["", "cent"], &[("dollar", "cent"), ("real", "centavos")]),
    ("fi", &["senttiä", "sentti"], &[("dollaria", "senttiä"), ("dollari", "sentti")]),
    ("el", &["σεντ", "σεντ"], &[("δολάρια", "σεντ"), ("δολάριο", "σεντ"), ("ρεάλ", "σεντάβος")]),
    ("ro", &["cenți", "cent"], &[("dolari", "cenți"), ("dolar", "cent"), ("reali", "centavos"), ("real", "centavo")]),
    ("he", &["סנטים", "סנט"], &[("דולרים", "סנטים"), ("דולר", "סנט"), ("ריאלים", "סנטאבו"), ("ריאל", "סנטאבו")]),
    ("ka", &["ცენტი"], &[("დოლარი", "ცენტი")]),
    ("ml", &["സെന്റ്"], &[("ഡോളർ", "സെന്റ്"), ("റിയാൽ", "സെന്റാവോ")]),
    ("pa", &["ਸੈਂਟ"], &[("ਡਾਲਰ", "ਸੈਂਟ"), ("ਰੀਅਲ", "ਸੈਂਟਾਵੋ")]),
    ("or", &["ସେଣ୍ଟ"], &[("ଡଲାର୍", "ସେଣ୍ଟ")]),
    ("bn", &["সেন্ট"], &[("ডলার", "সেন্ট")]),
    ("ta", &["சென்ட்கள்", "சென்ட்"], &[("டாலர்கள்", "சென்ட்கள்"), ("டாலர்", "சென்ட்")]),
    ("kn", &["ಸೆಂಟ್"], &[("ಡಾಲರ್", "ಸೆಂಟ್")]),
    ("te", &["సెంట్లు", "సెంట్"], &[("డాలర్లు", "సెంట్లు"), ("డాలర్", "సెంట్")]),
    ("hu", &["cent"], &[("dollár", "cent")]),
    ("hi", &["सेंट"], &[("डॉलर", "सेंट")]),
    ("gu", &["સેન્ટ"], &[("ડૉલર", "સેન્ટ")]),
    ("mr", &["सेंट"], &[("डॉलर", "सेंट")]),
    ("tl", &["sentimo"], &[("dolyar", "sentimo")]),
    ("ar", &["سنت"], &[("دولار", "سنت")]),
    ("ur", &["سینٹ"], &[("ڈالر", "سینٹ")]),
    ("ms", &["sen"], &[("dolar", "sen")]),
    ("id", &["sen"], &[("dolar", "sen")]),
    ("vi", &["xu"], &[("đô la", "xu")]),
    ("sv", &["cent"], &[("dollar", "cent")]),
];
const DP_MINUS: &[(&str, &str)] = &[
    ("en", "minus"),
    ("de", "minus"),
    ("es", "menos"),
    ("fr", "moins"),
    ("it", "meno"),
    ("pt", "menos"),
    ("ja", "マイナス"),
    ("zh", "负"),
    ("ko", "마이너스"),
    ("nl", "min"),
    ("pl", "minus"),
    ("tr", "eksi"),
    ("uk", "мінус"),
    ("cs", "minus"),
    ("da", "minus"),
    ("fi", "miinus"),
    ("el", "μείον"),
    ("nb", "minus"),
    ("ro", "minus"),
    ("sk", "mínus"),
    ("bg", "минус"),
    ("he", "מינוס"),
    ("th", "ลบ"),
    ("tl", "minus"),
    ("ms", "negatif"),
    ("ka", "მინუს"),
    ("ta", "மைனஸ்"),
    ("gu", "માઇનસ"),
    ("kn", "ಮೈನಸ್"),
    ("ml", "മൈനസ്"),
    ("pa", "ਮਾਈਨਸ"),
    ("or", "ମାଇନସ"),
    ("ru", "минус"),
    ("sv", "minus"),
    ("hu", "mínusz"),
    ("ar", "سالب"),
    ("vi", "âm"),
    ("id", "negatif"),
    ("hi", "माइनस"),
    ("bn", "মাইনাস"),
    ("te", "మైనస్"),
    ("mr", "उणे"),
    ("ur", "منفی"),
];
const DP_BUILD: &[DpBuild] = &[(
    "fr",
    &[
        ("HK", ["dollar de Hong Kong", "dollars de Hong Kong", "cents de Hong Kong"]),
        ("AU", ["dollar australien", "dollars australiens", "cents australiens"]),
        ("CA", ["dollar canadien", "dollars canadiens", "cents canadiens"]),
        ("NZ", ["dollar néo-zélandais", "dollars néo-zélandais", "cents néo-zélandais"]),
        ("SG", ["dollar de Singapour", "dollars de Singapour", "cents de Singapour"]),
        ("TW", ["dollar taïwanais", "dollars taïwanais", "cents taïwanais"]),
        ("BR", ["réal brésilien", "reais brésiliens", "centavos"]),
    ],
)];
const DP_RANGE_B: &[&str] = &["cs", "sk"];
const DP_RANGE_SAY: &[(&str, &str, &str, bool)] = &[("bg", "от ", " до ", true), ("ta", "", " முதல் ", false)];
const DP_MINUS_KEPT: &[&str] = &["hi", "gu", "bn"];
const DP_RANGE_GRAMMAR: &[&str] = &["ka", "he"];
const DP_RANGE_SIGN: &[&str] = &["es", "it", "pt", "ro", "el", "ml"];
const DP_RANGE_FORM: &[(&str, &[(&str, &str)])] = &[
    ("zh", &[("BR", "{a}-{b}巴西雷亚尔")]),
    ("ko", &[("BR", "{a}~{b} 브라질 헤알")]),
    ("it", &[("BR", "da {a} a {b} real brasiliani")]),
];
const DP_STOP: &[&str] = &[
    "the",
    "in",
    "of",
    "to",
    "from",
    "across",
    "throughout",
    "within",
    "for",
    "at",
    "by",
    "into",
    "outside",
    "inside",
    "around",
    "over",
    "all",
];

/// A dollar-prefix amount's spoken form: the words (DP_WORDS), a written form ({n}: the amount without its thousands
/// separators, with its scale word; {P}: the prefix as typed), or a pair (the form for one, the form for other amounts).
#[derive(Clone, Copy)]
enum How {
    W,
    T(&'static str),
    Pair(&'static str, &'static str),
}

/// (language, the grammar's dollar words, the word before the currency after a scale noun, the form after a scale
/// word, per currency the replacement of each dollar word)
type DpWords =
    (&'static str, &'static [&'static str], &'static str, usize, &'static [(&'static str, &'static [&'static str])]);

/// (language, the grammar's cents word for each dollar word, the dollar words turned into cents words)
type DpCents = (&'static str, &'static [&'static str], &'static [(&'static str, &'static str)]);
/// (language, per currency the words for one, for more and for its cents)
type DpBuild = (&'static str, &'static [(&'static str, [&'static str; 3])]);

fn dp_table<T: Copy>(table: &[(&str, T)], lang: &str) -> Option<T> {
    table.iter().find(|(l, _)| *l == lang).map(|x| x.1)
}

fn dp_words_of(lang: &str) -> Option<&'static DpWords> {
    DP_WORDS.iter().find(|w| w.0 == lang)
}

/// No digit and no dollar sign: the grammar read the amount.
fn dp_read(s: &str) -> bool {
    !s.chars().any(|ch| ch.is_ascii_digit() || ch == '$')
}

/// The integer digits and the decimals of an amount as the language writes it: prototype `dp_amount`.
fn dp_amount(s: &str, lang: &str) -> Option<(String, String)> {
    let (dec, grp) = if DP_COMMA.contains(&lang) { (',', '.') } else { ('.', ',') };
    let mut nums: Vec<String> = vec![String::new()];
    let mut seps: Vec<char> = Vec::new();
    for ch in s.chars() {
        if matches!(ch, '.' | ',' | '\u{a0}' | '\u{202f}' | ' ') {
            seps.push(ch);
            nums.push(String::new());
        } else {
            nums.last_mut().expect("a group").push(ch);
        }
    }
    let mut frac = String::new();
    if let Some(&last) = seps.last()
        && (last == dec
            || (last == grp
                && nums.last().expect("a group").len() <= 2
                && seps.iter().filter(|&&x| x == grp).count() == 1))
    {
        frac = nums.pop().expect("a group");
        seps.pop();
    }
    if !seps.is_empty()
        && (seps.iter().any(|&x| x != seps[0])
            || seps[0] == dec
            || nums[0].len() > 3
            || nums[1..].iter().any(|x| x.len() != 3))
    {
        return None;
    }
    Some((nums.concat(), frac))
}

/// Python's `str.capitalize` for a lower-case word.
fn dp_capitalize(s: &str) -> String {
    let mut c = s.chars();
    c.next().map_or_else(String::new, |f| f.to_uppercase().chain(c.flat_map(char::to_lowercase)).collect())
}

/// The DP_FIX replacements of the language.
fn dp_fix(lang: &str, mut said: String) -> String {
    for (a, b) in dp_table(DP_FIX, lang).unwrap_or(&[]) {
        said = said.replace(a, b);
    }
    said
}

/// The spoken words of a prefixed amount, or the written form for the language's rules: prototype `dp_words`.
fn dp_words(lang: &str, cur: &str, whole: &str, frac: &str, scale: &str, written: &str, unit: &str) -> Option<String> {
    let &(_, forms, of, of_form, table) = dp_words_of(lang)?;
    let repl = dp_table(table, cur)?;
    let glued = GLUED.contains(&lang);
    let sp = if glued { "" } else { " " };
    if !scale.is_empty() && !DP_SCALE_SAID.contains(&lang) {
        let word = scale.trim_matches(|c| c == ' ' || c == '\u{a0}');
        let of = if dp_table(DP_OF, lang).is_some_and(|w| w.contains(&word)) { of } else { "" };
        return Some(format!("{written}{scale}{sp}{of}{}{unit}", repl[of_form]));
    }
    let mut frac = frac.to_string();
    if scale.is_empty() && frac.len() == 1 {
        frac.push('0'); // $2,5 is two dollars fifty
    }
    if scale.is_empty() && frac.trim_matches('0').is_empty() {
        frac.clear(); // 5,00 is five
    }
    let num = if frac.is_empty() {
        whole.to_string()
    } else {
        format!("{whole}{}{frac}", if DP_COMMA.contains(&lang) { "," } else { "." })
    };
    let mut base = words(&format!("${num}{scale}"), lang);
    if !dp_read(&base) {
        return None;
    }
    let mut unit = unit;
    if !unit.is_empty() {
        let per = words(&format!("${num}{unit}"), lang);
        if per.starts_with(&format!("{base} ")) && dp_read(&per) && !per.contains('/') {
            base = per; // the grammar reads the unit after a plain dollar amount
            unit = "";
        }
    }
    let mut toks: Vec<String> = if glued { Vec::new() } else { base.split(' ').map(str::to_string).collect() };
    if let Some(nouns) = dp_table(DP_JOIN, lang) {
        let mut out: Vec<String> = Vec::new();
        let mut joining = false;
        for tok in toks {
            if nouns.contains(&tok.as_str()) || forms.contains(&tok.as_str()) {
                out.push(if nouns.contains(&tok.as_str()) { dp_capitalize(&tok) } else { tok });
                joining = false;
            } else if joining {
                out.last_mut().expect("a token").push_str(&tok);
            } else {
                out.push(tok);
                joining = true;
            }
        }
        toks = out;
    }
    let one = whole == "1" && scale.is_empty();
    let active: Vec<(usize, &str)> = forms
        .iter()
        .enumerate()
        .filter_map(|(i, f)| match f.strip_prefix("1:") {
            Some(rest) => one.then_some((i, rest)),
            None => Some((i, *f)),
        })
        .collect();
    let mut hit: Option<(usize, usize, &str)> = None;
    if glued {
        for &(i, f) in &active {
            let k = if scale.is_empty() { base.find(f) } else { base.rfind(f) };
            if let Some(k) = k {
                hit = Some((k, i, f));
                break;
            }
        }
    } else {
        let order: Vec<usize> =
            if scale.is_empty() { (0..toks.len()).collect() } else { (0..toks.len()).rev().collect() };
        for k in order {
            hit = active.iter().find(|(_, f)| toks[k] == *f).map(|&(i, f)| (k, i, f));
            if hit.is_some() {
                break;
            }
        }
    }
    if hit.is_none()
        && scale.is_empty()
        && !glued
        && let Some(&(_, cents, pairs)) = DP_CENTS.iter().find(|x| x.0 == lang)
    {
        // cents only (HK$0.50 → fifty Hong Kong cents): the cents word becomes the currency's cents
        let (k, ci) = toks
            .iter()
            .enumerate()
            .find_map(|(k, tok)| cents.iter().position(|c| !tok.is_empty() && c == tok).map(|ci| (k, ci)))?;
        let own = repl[ci];
        let (a, b) = pairs.iter().find(|(a, _)| own.contains(a))?;
        toks[k] = own.replacen(a, b, 1);
        return Some(dp_fix(lang, toks.join(" ")) + unit);
    }
    let rest = |&(k, _, f): &(usize, usize, &str)| if glued { k + f.len() < base.len() } else { k + 1 < toks.len() };
    let Some((k, i, f)) = hit.filter(|h| scale.is_empty() || !rest(h)) else {
        return (!scale.is_empty()).then(|| format!("{written}{scale}{sp}{of}{}{unit}", repl[of_form]));
    };
    if glued {
        return Some(format!("{}{}{}{unit}", &base[..k], repl[i], &base[k + f.len()..]));
    }
    if !of.is_empty() && k > 0 && dp_table(DP_OF, lang).is_some_and(|w| w.contains(&toks[k - 1].as_str())) {
        let prev = format!("{} {}", toks[k - 1], of.trim()); // es “dos millones de dólares”
        toks[k - 1] = prev;
    }
    toks[k] = repl[i].to_string();
    Some(dp_fix(lang, toks.join(" ")) + unit)
}

/// The amount as the rule writes it for the grammar: prototype `dp_flat`.
fn dp_flat(n: &str, whole: &str, frac: &str, scale: &str) -> String {
    if frac.trim_matches('0').is_empty() {
        return whole.to_string();
    }
    let at = n.len() - frac.len();
    let pad = if frac.len() == 1 && scale.is_empty() { "0" } else { "" };
    format!("{whole}{}{frac}{pad}", &n[at - 1..at])
}

/// Whether amount a (integer digits, decimals) is smaller than amount b: prototype `dp_less`.
fn dp_less(a: &(String, String), b: &(String, String)) -> bool {
    let key = |x: &(String, String)| {
        let whole = x.0.trim_start_matches('0').to_string();
        let mut frac = x.1.clone();
        while frac.chars().count() < 9 {
            frac.push('0');
        }
        (whole.chars().count(), whole, frac)
    };
    key(a) < key(b)
}

fn dp_has_words(lang: &str, cur: &str) -> bool {
    dp_words_of(lang).is_some_and(|w| dp_table(w.4, cur).is_some())
}

/// An amount with cents in the fr money style (DP_BUILD): prototype `dp_build`.
fn dp_build(lang: &str, cur: &str, whole: &str, frac: &str) -> Option<String> {
    let [one, many, cents] = dp_table(dp_table(DP_BUILD, lang)?, cur)?;
    let two: String = format!("{frac}0").chars().take(2).collect();
    let c = two.trim_start_matches('0');
    let said = words(if c.is_empty() { "0" } else { c }, lang);
    let w = whole.trim_start_matches('0');
    if w.is_empty() {
        return Some(format!("{said} {cents}"));
    }
    Some(format!("{} {} {said}", words(whole, lang), if w == "1" { one } else { many }))
}

/// A range of a prefixed currency for the language's range rule: prototype `dp_range_words`.
fn dp_range_words(lang: &str, cur: &str, fa: &str, fb: &str, pb: &(String, String), scale: &str) -> Option<String> {
    let &(_, forms, of, of_form, table) = dp_words_of(lang)?;
    let repl = dp_table(table, cur)?;
    let word = scale.trim_matches(|c| c == ' ' || c == '\u{a0}');
    let of = if dp_table(DP_OF, lang).is_some_and(|w| w.contains(&word)) { of } else { "" };
    if scale.is_empty()
        && let Some(&(_, fro, to, money)) = DP_RANGE_SAY.iter().find(|x| x.0 == lang)
    {
        let first = if money { words(&format!("${fa}"), lang) } else { words(fa, lang) };
        if let Some(said) = dp_words(lang, cur, &pb.0, &pb.1, "", fb, "")
            && !said.is_empty()
            && dp_read(&first)
        {
            let nums = first.split(' ').filter(|x| !forms.contains(x)).collect::<Vec<_>>().join(" ");
            return Some(format!("{fro}{nums}{to}{said}"));
        }
    }
    if scale.is_empty() && DP_RANGE_GRAMMAR.contains(&lang) {
        let base = words(&format!("${fa}-{fb}"), lang);
        let toks: Vec<&str> = base.split(' ').collect();
        if let Some(i) = forms.iter().position(|f| toks.last() == Some(f))
            && dp_read(&base)
        {
            let mut out = toks[..toks.len() - 1].to_vec();
            out.push(repl[i]);
            return Some(out.join(" "));
        }
    }
    let mut k = of_form;
    if scale.is_empty() && DP_RANGE_B.contains(&lang) {
        let said = words(&format!("${}", pb.0), lang);
        let toks: Vec<&str> = said.split(' ').collect();
        k = forms.iter().position(|f| toks.contains(f)).unwrap_or(of_form);
    }
    if scale.is_empty() && DP_RANGE_SIGN.contains(&lang) {
        if repl[of_form] == forms[of_form] {
            return Some(format!("{fa}-{fb} $"));
        }
        if let Some(q) = repl[of_form].strip_prefix(&format!("{} ", forms[of_form])) {
            return Some(format!("{fa}-{fb} $ {q}"));
        }
    }
    Some(format!("{fa}-{fb}{scale} {of}{}", repl[k]))
}

/// Cents only: no whole part, some cents.
fn dp_cents_only(whole: &str, frac: &str) -> bool {
    whole.trim_matches('0').is_empty() && !frac.trim_matches('0').is_empty()
}

/// The grammar reads the prefix as typed: prototype `all_dollar_prefix.kept`.
fn dp_kept(lang: &str, forms: &[(&str, How)], cur: &str, whole: &str, frac: &str, sc: &str) -> bool {
    let build = dp_table(DP_BUILD, lang).is_some_and(|b| dp_table(b, cur).is_some())
        && !frac.trim_matches('0').is_empty()
        && sc.is_empty();
    dp_table(forms, cur).is_none()
        && !(dp_has_words(lang, cur) && (!sc.is_empty() || dp_cents_only(whole, frac)))
        && !build
}

/// The rewrite of one prefixed amount: prototype `all_dollar_prefix.positive`.
fn dp_positive(lang: &str, forms: &[(&str, How)], p: &str, n: &str, sc: &str, u: &str) -> Option<String> {
    let cur = dp_table(DP_PREFIX, p)?;
    let how = dp_table(forms, cur);
    let (whole, frac) = dp_amount(n, lang)?;
    let hw = dp_has_words(lang, cur);
    if matches!(how, Some(How::W))
        || (how.is_none() && hw && (!sc.is_empty() || dp_cents_only(&whole, &frac)))
        || (!sc.is_empty() && hw)
    {
        let said = dp_words(lang, cur, &whole, &frac, sc, n, u);
        if said.is_none() && cur == "US" {
            return Some(format!("${n}{sc}{u}")); // the grammar's dollar is the US dollar
        }
        return said;
    }
    if !frac.trim_matches('0').is_empty()
        && sc.is_empty()
        && let Some(b) = dp_build(lang, cur, &whole, &frac)
    {
        return Some(b + u);
    }
    let flat = dp_flat(n, &whole, &frac, sc);
    let template = match how {
        None => return Some(format!("{p}${flat}{sc}{u}")),
        Some(How::T(s)) => s,
        Some(How::Pair(one, many)) => {
            if whole == "1" && sc.is_empty() {
                one
            } else {
                many
            }
        }
        Some(How::W) => unreachable!("handled above"),
    };
    Some(template.replace("{P}", p).replace("{n}", &format!("{flat}{sc}")) + u)
}

/// One prefixed amount in the text: prototype `all_dollar_prefix.f`.
#[allow(clippy::too_many_arguments)]
fn dp_rewrite(
    lang: &str,
    forms: &[(&str, How)],
    whole_match: &str,
    p: &str,
    n: &str,
    sc: &str,
    u: &str,
    first: bool,
) -> Option<String> {
    let cur = dp_table(DP_PREFIX, p)?;
    let (whole, frac) = dp_amount(n, lang)?;
    if dp_kept(lang, forms, cur, &whole, &frac, sc) {
        let flat = dp_flat(n, &whole, &frac, sc);
        return (flat != n).then(|| whole_match.replacen(n, &flat, 1)); // HK$1 500 → HK$1500, in place
    }
    let new = dp_positive(lang, forms, p, n, sc, u)?;
    if first && new == format!("{p}${n}{sc}{u}") && !GLUED.contains(&lang) {
        return None; // as typed, give or take the space after the sign (US$ 5)
    }
    Some(new)
}

/// A negative amount: prototype `all_dollar_prefix.neg`.
fn dp_negative(lang: &str, forms: &[(&str, How)], p: &str, n: &str, sc: &str, u: &str, plain: bool) -> Option<String> {
    let cur = dp_table(DP_PREFIX, p)?;
    let (whole, frac) = dp_amount(n, lang)?;
    if dp_kept(lang, forms, cur, &whole, &frac, sc) {
        let flat = dp_flat(n, &whole, &frac, sc);
        if DP_MINUS_KEPT.contains(&lang) {
            return Some(format!("{} {p}${flat}{sc}{u}", dp_table(DP_MINUS, lang).unwrap_or("-")));
        }
        return if plain && flat == n { None } else { Some(format!("-{p}${flat}{sc}{u}")) };
    }
    let new = dp_positive(lang, forms, p, n, sc, u)?;
    if new.starts_with(|ch: char| ch.is_ascii_digit()) {
        return Some(format!("-{new}")); // 5 HKD → -5 HKD, which the language's rules read
    }
    let sp = if GLUED.contains(&lang) { "" } else { " " };
    Some(format!("{}{sp}{new}", dp_table(DP_MINUS, lang).unwrap_or("-")))
}

/// A range: prototype `all_dollar_prefix.rng` (a hyphen with spaces around it only when the second amount is the
/// larger: HK$10 - HK$3 is a subtraction).
fn dp_range(lang: &str, forms: &[(&str, How)], p: &str, a: &str, s: &str, b: &str, sc: &str) -> Option<String> {
    let cur = dp_table(DP_PREFIX, p)?;
    let how = dp_table(forms, cur);
    let pa = dp_amount(a, lang)?;
    let pb = dp_amount(b, lang)?;
    if s.contains('-') && s != "-" && !dp_less(&pa, &pb) {
        return None;
    }
    let (fa, fb) = (dp_flat(a, &pa.0, &pa.1, sc), dp_flat(b, &pb.0, &pb.1, sc));
    if let Some(own) = dp_table(DP_RANGE_FORM, lang).and_then(|t| dp_table(t, cur)) {
        return Some(own.replace("{a}", &fa).replace("{b}", &format!("{fb}{sc}")));
    }
    let tmpl = match how {
        Some(How::T(s)) => Some(s),
        Some(How::Pair(_, many)) => Some(many),
        _ => None,
    };
    // a form that is the prefix and the amount (CA${n}, {P}${n})
    let pfx = tmpl
        .and_then(|s| s.strip_suffix("${n}"))
        .filter(|x| *x == "{P}" || ((1..=2).contains(&x.len()) && x.bytes().all(|b| b.is_ascii_uppercase())));
    if (how.is_none() || matches!(how, Some(How::W)) || pfx.is_some()) && dp_has_words(lang, cur) {
        return dp_range_words(lang, cur, &fa, &fb, &pb, sc);
    }
    if how.is_none() || pfx.is_some() {
        let q = match pfx {
            Some(x) if x != "{P}" => x,
            _ => p,
        };
        return Some(format!("{fa}-{fb}{sc} {q}$"));
    }
    Some(tmpl?.replace("{P}", p).replace("{n}", &format!("{fa}-{fb}{sc}")))
}

fn all_dollar_prefix(t: String, c: &mut Ctx) -> String {
    if !t.contains('$') {
        return t;
    }
    let lang = c.lang().to_string();
    let forms: &[(&str, How)] = dp_table(DP_FORM, &lang).unwrap_or(&[]);
    let e = edge(&lang);
    let pre = DP_PREFIX.iter().map(|(p, _)| *p).collect::<Vec<_>>().join("|");
    let amount = r"[0-9]+(?:[.,][0-9]+|[ \x{A0}\x{202F}][0-9]{3}(?![0-9]))*";
    let glued = GLUED.contains(&lang.as_str());
    let scale = match dp_table(DP_SCALE, &lang) {
        Some(s) => format!("({s}{})?", if glued { r"(?![A-Za-z])" } else { r"(?![^\W\d_])" }),
        None => "()".to_string(),
    };
    let unit = r"(/[^\W\d_]{1,12})?";
    let sep = r"([ \x{A0}]?[-–~〜][ \x{A0}]?)";
    // (a range the range pass left, HK$5-HK$10 with another prefix, stays as typed; a spaced hyphen is a subtraction
    // there, HK$10 - HK$3, and each amount is read)
    let tail = format!(r"(?![{e}$]|[.,][0-9]|:[A-Za-z]|(?:-|[ \x{{A0}}]?[–~〜][ \x{{A0}}]?)(?:[A-Z]{{1,2}}\$)?[0-9])");
    let lb = format!(r"(?<![{e}$/@.,:=+\-–~])");
    // US $5 → US$5 (the letters apart from the sign)
    let t = c.sub(&rx(&format!(r"{lb}(US|HK|AU|CA|NZ|SG|NT) \$(?=[0-9])")), &t, |m| {
        let start = m.get(0).expect("group 0").start();
        let before = rx(r"(\w+)[ \t]*$").captures(&t[..start]).ok().flatten();
        if before.is_some_and(|b| DP_STOP.contains(&g(&b, 1).to_lowercase().as_str())) {
            return None;
        }
        Some(format!("{}$", g(m, 1)))
    });
    // ranges: HK$5-10, HK$5–HK$10, US$5~10 and 5-10 US$
    let t = c.sub(
        &rx(&format!(r"{lb}({pre})\$[ \x{{A0}}]?({amount}){sep}(?:\1\$[ \x{{A0}}]?)?({amount}){scale}{tail}")),
        &t,
        |m| dp_range(&lang, forms, g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5)),
    );
    let t = c.sub(&rx(&format!(r"{lb}({amount}){sep}({amount}){scale}[ \x{{A0}}]?({pre})\$(?![{e}$])")), &t, |m| {
        dp_range(&lang, forms, g(m, 5), g(m, 1), g(m, 2), g(m, 3), g(m, 4))
    });
    // negatives: -HK$5, −US$5, HK$-5, -5 HK$
    let t = c.sub(&rx(&format!(r"{lb}[-−]({pre})\$[ \x{{A0}}]?({amount}){scale}{unit}{tail}")), &t, |m| {
        dp_negative(&lang, forms, g(m, 1), g(m, 2), g(m, 3), g(m, 4), m[0].starts_with('-'))
    });
    let t = c.sub(&rx(&format!(r"{lb}({pre})\$[ \x{{A0}}]?[-−]({amount}){scale}{unit}{tail}")), &t, |m| {
        dp_negative(&lang, forms, g(m, 1), g(m, 2), g(m, 3), g(m, 4), false)
    });
    let t = c.sub(&rx(&format!(r"{lb}[-−]({amount}){scale}[ \x{{A0}}]?({pre})\$(?![{e}$])")), &t, |m| {
        dp_negative(&lang, forms, g(m, 3), g(m, 1), g(m, 2), "", false)
    });
    // amounts: HK$5, US$ 5, 5 US$
    let t = c.sub(&rx(&format!(r"{lb}({pre})\$[ \x{{A0}}]?({amount}){scale}{unit}{tail}")), &t, |m| {
        dp_rewrite(&lang, forms, &m[0], g(m, 1), g(m, 2), g(m, 3), g(m, 4), true)
    });
    c.sub(&rx(&format!(r"{lb}({amount}){scale}[ \x{{A0}}]?({pre})\$(?![{e}$])")), &t, |m| {
        dp_rewrite(&lang, forms, &m[0], g(m, 3), g(m, 1), g(m, 2), "", false)
    })
}
