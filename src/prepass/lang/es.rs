//! 'es' rules: the port of the workbench's `langrules/es.py` (ids `es.*`).
//!
//! The Spanish grammar reads every number in one form: 1 is always the apocopated “un” (“el 31.” → “treinta y un”,
//! “1 cebolla” → “un cebolla”) and hundreds are always masculine (“200 entradas” → “doscientos entradas”). The gender
//! rules read the word after the number (a noun table, a few safe suffixes) and write the number's words in the
//! right form; where the word is not known, today's reading stays.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, full, g, matches_at_start, py_int, re_escape, rx, search, sub_plain, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::py_strip;

pub(super) const RULES: &[LangRule] = &[
    ("es.abbrev", es_abbrev),
    ("es.siglo", es_siglo),
    ("es.regnal", es_regnal),
    ("es.space-groups", es_space_groups),
    ("es.money-range", es_money_range),
    ("es.per-unit", es_per_unit),
    ("es.money-code", es_money_code),
    ("es.money-scale", es_money_scale),
    ("es.money-cents", es_money_cents),
    ("es.units", es_units),
    ("es.scale-de", es_scale_de),
    ("es.range", es_range),
    ("es.half", es_half),
    ("es.hour-article", es_hour_article),
    ("es.gender", es_gender),
];

const LETTER: &str = r"[^\W\d_]";
const SP: &str = r"[ \t\x{A0}]";
/// An integer as written in Spanish: 1.234.567 or 1234 (not part of a decimal, a time, a fraction, a date or a code).
const NUM: &str = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?![\w%°ºª'’]|[.,:/\-–]\w|[ \x{A0}]\d)";
const NUM_BEFORE: &str = r"(?<![\w.,/:\-−–+$€£¥₩₡₲₧฿₹₽#\\])(?<!\d[ \x{A0}])";
const ROMAN: &str = r"(?=[IVXLC])C{0,3}(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})";

fn roman_value(s: &str) -> u32 {
    let v = |c: char| match c {
        'I' => 1,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        'C' => 100,
        _ => 0,
    };
    let cs: Vec<char> = s.chars().collect();
    let mut n: i64 = 0;
    for (i, &ch) in cs.iter().enumerate() {
        let x = v(ch) as i64;
        if i + 1 < cs.len() && v(cs[i + 1]) as i64 > x {
            n -= x;
        } else {
            n += x;
        }
    }
    n as u32
}

/// `word` with the first letter upper-cased when `src` starts with an upper-case letter.
fn cap_like(src: &str, word: &str) -> String {
    if src.chars().next().is_some_and(char::is_uppercase) {
        let mut cs = word.chars();
        match cs.next() {
            Some(f) => f.to_uppercase().chain(cs).collect(),
            None => String::new(),
        }
    } else {
        word.to_string()
    }
}

fn lower(s: &str) -> String {
    s.to_lowercase()
}

// ------------------------------------------------------------------------------------------------ number forms

const FEM: &[(&str, &str)] = &[
    ("un", "una"),
    ("uno", "una"),
    ("veintiún", "veintiuna"),
    ("veintiuno", "veintiuna"),
    ("doscientos", "doscientas"),
    ("trescientos", "trescientas"),
    ("cuatrocientos", "cuatrocientas"),
    ("quinientos", "quinientas"),
    ("seiscientos", "seiscientas"),
    ("setecientos", "setecientas"),
    ("ochocientos", "ochocientas"),
    ("novecientos", "novecientas"),
];
const BIG: &[&str] = &["millón", "millones", "billón", "billones", "trillón", "trillones"];

/// The feminine reading of a cardinal's words: “doscientos un” → “doscientas una” (prototype `feminine`).
fn feminine(w: &str) -> String {
    let toks: Vec<&str> = w.split(' ').collect();
    let mut start = 0;
    for (i, x) in toks.iter().enumerate() {
        if BIG.contains(x) {
            start = i + 1;
        }
    }
    let mut out: Vec<&str> = Vec::new();
    for (i, x) in toks.iter().enumerate() {
        let keep = (*x == "un" || *x == "veintiún") && i + 1 < toks.len() && toks[i + 1] == "mil";
        if i < start || keep {
            out.push(x);
        } else {
            out.push(FEM.iter().find(|(a, _)| a == x).map_or(*x, |(_, b)| *b));
        }
    }
    out.join(" ")
}

/// The noun-less reading of a cardinal's words: a final “un” is “uno” (prototype `citation`).
fn citation(w: &str) -> String {
    if let Some(head) = w.strip_suffix("veintiún") {
        return format!("{head}veintiuno");
    }
    if w == "un" || w.ends_with(" un") {
        return format!("{}uno", &w[..w.len() - 2]);
    }
    w.to_string()
}

// ------------------------------------------------------------------------------------------------ noun genders

fn plural(w: &str) -> String {
    if w.ends_with("is") {
        return w.to_string();
    }
    if let Some(h) = w.strip_suffix('z') {
        return format!("{h}ces");
    }
    if let Some(h) = w.strip_suffix("ón") {
        return format!("{h}ones"); // canciones, razones
    }
    if let Some(h) = w.strip_suffix("én") {
        return format!("{h}enes");
    }
    if w.chars().next_back().is_some_and(|c| "aeiouáéó".contains(c)) {
        return format!("{w}s");
    }
    format!("{w}es")
}

const FEM_NOUNS: &str = "
hora media semana quincena década noche tarde madrugada jornada temporada vez etapa fase época edición vuelta ronda
sesión clase lección fecha generación cita visita llamada reunión conferencia charla fiesta boda cena comida bebida
tonelada libra onza pulgada milla yarda hectárea caloría kilocaloría arroba legua cucharada cucharadita taza pizca
cabeza rodaja loncha rebanada porción ración gota lata botella copa jarra bolsa caja docena decena centena veintena
unidad pieza parte cápsula pastilla tableta dosis hoja página línea palabra letra frase oración canción película
serie escena foto fotografía imagen mano carta cama habitación casa plaza calle ciudad provincia región comunidad isla
montaña playa iglesia escuela universidad tienda empresa compañía oficina planta fábrica sede sucursal mesa silla
puerta ventana pared llave cuenta tarjeta entrada salida opción pregunta respuesta idea razón causa cosa forma manera
persona mujer niña chica hija hermana madre abuela tía prima amiga esposa señora familia víctima muerte vida especie
raza vaca oveja gallina cabra yegua abeja hormiga mosca rana ballena tortuga serpiente araña flor rosa semilla
manzana naranja pera fresa uva cereza banana patata cebolla zanahoria lechuga berenjena calabaza aceituna almendra
nuez galleta tortilla pizza hamburguesa empanada arepa cerveza receta clara yema ramita rama barra pila batería
bombilla máquina computadora pantalla cámara impresora aplicación herramienta red versión función variable tabla
columna fila celda base capa tarea prueba muestra encuesta estrella medalla victoria derrota meta carrera ruta vía
estación parada rueda moto bicicleta bici furgoneta camioneta nave lancha barca avioneta pistola bala bomba guerra
batalla revolución ley norma regla multa pena condena denuncia queja solicitud firma noticia historia novela obra
revista sala cocina terraza piscina finca granja vivienda parcela cuadra cuchara sartén olla moneda peseta lira corona
rupia acción cuota vacante oferta factura propiedad vacuna camilla operación cirugía consulta mascota nota asignatura
materia beca lengua sílaba vocal consonante cifra estrofa tecla cuerda pista localidad nación provincia pirámide
generación persona dama niña joven adolescente alumna profesora doctora enfermera trabajadora jugadora
cucharilla cazuela bandeja fuente hogaza baguette loncha tira tajada lámina hebra cabeza diente
peseta rupia corona lira libra esterlina
";
const FEM_IRREGULAR: &[&str] = &["imágenes", "órdenes", "vírgenes", "jóvenes"];
const MASC_AS: &str = "
días mapas planetas cometas tranvías guardias policías colegas guías espías atletas poetas profetas ascetas piratas
acróbatas idiotas patriotas compatriotas jesuitas gorilas koalas pandas pumas yogas vodkas tequilas atlas gas
sofás papás karatekas cólera
";
const DETERMINERS: &str = "
muchas pocas todas otras varias algunas ciertas demasiadas tantas cuantas cuántas esas estas aquellas ambas
ningunas unas las nosotras vosotras ellas mías tuyas suyas nuestras vuestras cuyas apenas mientras tras quizas
jamas demas mas
";
const INVARIANT_ADJ: &str = "grandes mejores peores diferentes importantes enormes jóvenes principales posibles";
const NOUNLESS: &str = "
y e o u ni que de del a al en con por para sin sobre entre hasta desde hacia contra según tras como cuando donde
si pero porque aunque mientras es son era eran fue fueron será serán sería está están estaba estuvo ha han había
hay hubo se no sí más menos ya también tampoco solo sólo nunca siempre ves ve veo vemos vi tiene tienen tenía puede
pueden va van iba sale salen salió llega llegó gana ganó pierde perdió queda quedan quedó sobran dice dijo cuesta
costó sigue siguen entró empieza terminó significa equivale indica
";
const MONTHS: &[&str] = &[
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "setiembre",
    "octubre",
    "noviembre",
    "diciembre",
];
const DAYS: &[&str] = &["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const DATE_ABBR: &str = "ene. en. ENE febr. FEB feb. mzo. mzo MAR mar. abr. ABR abr my. MAY may. may jun. JUN jun jul. JUL jul AGO ag.
agt. ago. set. sept. setbre. sept setbre SEP oct. OCT oct nov. novbre. NOV nov novbre dic. dicbre. DIC LU lun. LUN ma. MA
mi. mié. miér. MIÉ mié miér ju. JU jue JUE vie. vier. vie sá. sáb sáb. SÁB do. dom. DOM";
const PLURAL_SUFFIXES: &[&str] = &["ciones", "siones", "xiones", "dades", "tades", "tudes", "umbres"];
const SINGULAR_SUFFIXES: &[&str] = &["ción", "sión", "xión", "dad", "tad", "tud", "umbre", "itis"];
const NOT_FEM_SUFFIXES: &[&str] = &["mas", "istas", "icidas", "cratas", "nautas", "iatras"];

fn set(s: &'static str) -> HashSet<&'static str> {
    s.split_whitespace().collect()
}

static FEM_FORMS: LazyLock<HashSet<String>> = LazyLock::new(|| {
    let mut out: HashSet<String> = HashSet::new();
    for w in FEM_NOUNS.split_whitespace() {
        out.insert(w.to_string());
        out.insert(plural(w));
    }
    out.extend(FEM_IRREGULAR.iter().map(|s| s.to_string()));
    out
});
static MASC_AS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(MASC_AS));
static DETERMINERS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(DETERMINERS));
static INVARIANT_ADJ_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(INVARIANT_ADJ));
static NOUNLESS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(NOUNLESS));
/// A word after “de” that makes “N de …” a date.
static DATE_WORDS: LazyLock<HashSet<String>> = LazyLock::new(|| {
    let mut out: HashSet<String> = MONTHS.iter().map(|s| s.to_string()).collect();
    out.extend(DATE_ABBR.split_whitespace().map(|a| a.trim_end_matches('.').to_string()));
    out
});

/// 'f' for a feminine noun, 'n' for a word that cannot be counted (a function word or verb), "" if unknown.
fn noun_gender(word: &str) -> &'static str {
    let w = lower(word);
    if NOUNLESS_SET.contains(w.as_str()) {
        return "n";
    }
    if FEM_FORMS.contains(&w) {
        return "f";
    }
    if MASC_AS_SET.contains(w.as_str()) || DETERMINERS_SET.contains(w.as_str()) {
        return "";
    }
    if PLURAL_SUFFIXES.iter().chain(SINGULAR_SUFFIXES).any(|x| w.ends_with(x)) {
        return "f";
    }
    if w.chars().count() > 3 && w.ends_with("as") && !NOT_FEM_SUFFIXES.iter().any(|x| w.ends_with(x)) {
        return "f";
    }
    ""
}

// ------------------------------------------------------------------------------------------------ abbreviations

static ABBREV: LazyLock<Vec<(String, Option<&'static str>)>> = LazyLock::new(|| {
    vec![
        (format!(r"(?<!\w)[Nn]úms?\.(?={SP}*\d)"), None),
        (format!(r"(?<!\w)[Nn]\.?[º°]s?(?={SP}*\d)"), None),
        (format!(r"(?<!\w)D(?:ña|ª|\.ª)\.?(?={SP}+[A-ZÁÉÍÓÚÑ])"), Some("doña")),
        (format!(r"(?<!\w)Sres\.(?={SP}+[A-ZÁÉÍÓÚÑ])"), Some("señores")),
        (format!(r"(?<!\w)Sras\.(?={SP}+[A-ZÁÉÍÓÚÑ])"), Some("señoras")),
        (format!(r"(?<!\w)Lic\.(?={SP}+[A-ZÁÉÍÓÚÑ])"), Some("licenciado")),
        (format!(r"(?<!\w)Lcda\.(?={SP}+[A-ZÁÉÍÓÚÑ])"), Some("licenciada")),
        (format!(r"(?<!\w)Ing\.(?={SP}+[A-ZÁÉÍÓÚÑ])"), Some("ingeniero")),
        (format!(r"(?<!\w)[Aa]prox\.(?={SP}*\d)"), Some("aproximadamente")),
        (format!(r"(?<!\w)[Pp]ágs\.(?={SP}*\d)"), Some("páginas")),
    ]
});

fn es_abbrev(t: String, c: &mut Ctx) -> String {
    let mut t = t;
    for (pat, word) in ABBREV.iter() {
        t = c.sub(&rx(pat), &t, |m| {
            let s = &m[0];
            match word {
                None => {
                    let plural_form = lower(s).starts_with("núms") || s.ends_with('s');
                    Some(cap_like(s, if plural_form { "números" } else { "número" }))
                }
                Some(w) => Some(cap_like(s, w)),
            }
        });
    }
    let t = c.sub_tpl(&rx(&format!(r"(?<!\w)etc\.(?={SP}*[,;:)\]]|{SP}+[a-záéíóúñ])")), &t, "etcétera");
    c.sub_tpl(&rx(r"(?<!\w)etc\."), &t, "etcétera.")
}

// ------------------------------------------------------------------------------------------------ centuries

fn es_siglo(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"(?<!\w)(siglos?|Siglos?|SIGLOS?|[Ss]ig\.|s\.|S\.){SP}*({ROMAN})(?!\w|\.\w)(?:({SP}*(?:y|e|o|al|a|-|–){SP}*)({ROMAN})(?!\w))?"
    ));
    c.sub(&re, &t, |m| {
        let (head, r1, sep, r2) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        if head == "S." && r1.chars().count() < 2 {
            return None;
        }
        let word = if lower(head).starts_with("siglos") || !r2.is_empty() { "siglos" } else { "siglo" };
        let lead = if lower(head).starts_with("siglo") { cap_like(head, word) } else { word.to_string() };
        let mut out = format!("{lead} {}", citation(&words(&roman_value(r1).to_string(), "es")));
        if !r2.is_empty() {
            let s = py_strip(sep);
            let joiner = if s == "-" || s == "–" { " a ".to_string() } else { format!(" {s} ") };
            out.push_str(&joiner);
            out.push_str(&citation(&words(&roman_value(r2).to_string(), "es")));
        }
        Some(out)
    })
}

// ------------------------------------------------------------------------------------------------ rulers and popes

const FEM_REGNAL: &str = "Isabel Juana María Catalina Victoria Cristina Margarita Ana Leonor Urraca Berenguela Blanca \
                          Beatriz Teresa Carlota Mariana Luisa Sancha Constanza Elena Sofía";
const REGNAL_NAMES: &str = "
Alfonso Fernando Felipe Carlos Juan Enrique Pedro Jaime Sancho Ramiro García Ordoño Bermudo Luis Pío Benedicto
Gregorio León Clemente Inocencio Urbano Bonifacio Alejandro Julio Sixto Nicolás Adriano Pablo Juan Esteban Martín
Calixto Eugenio Paulo Eduardo Jorge Guillermo Ricardo Napoleón Federico Francisco Víctor Humberto Constantino
Ramsés Amenofis Tutmosis Gustavo Olaf Haroldo Canuto Cristián Iván Basilio Miguel Manuel Andrés Otón Rodolfo
Maximiliano Leopoldo Fernando Wenceslao Casimiro Segismundo Ladislao Juan Pablo Simón Teodoro Justiniano Ptolomeo
Antíoco Seleuco Mitrídates Jerjes Darío Artajerjes Ciro Psamético Sesostris Luis Inocencio Clemente
";
static FEM_REGNAL_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(FEM_REGNAL));
static REGNAL_NAMES_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(REGNAL_NAMES));

fn es_regnal(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(r"(?<![\w.])([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){SP}+({ROMAN})(?!\w|\.\w)"));
    c.sub(&re, &t, |m| {
        let (name, r) = (g(m, 1), g(m, 2));
        let n = roman_value(r);
        let fem = FEM_REGNAL_SET.contains(name);
        if fem && n <= 10 {
            let ordinal = words(&format!("{n}.ª"), "es");
            return full(&format!("{LETTER}+"), &ordinal).then(|| format!("{name} {ordinal}"));
        }
        if n > 10 && (fem || REGNAL_NAMES_SET.contains(name)) {
            return Some(format!("{name} {}", citation(&words(&n.to_string(), "es"))));
        }
        None
    })
}

// ------------------------------------------------------------------------------------------------ money

const CODES: &[(&str, &str)] = &[
    ("USD", "$"),
    ("GBP", "£"),
    ("EUR", "€"),
    ("MXN", "mxn"),
    ("ARS", "ars"),
    ("COP", "cop"),
    ("CLP", "clp"),
    ("PEN", "pen"),
    ("UYU", "uyu"),
    ("BOB", "bob"),
    ("PYG", "pyg"),
    ("CRC", "crc"),
    ("DOP", "dop"),
    ("GTQ", "gtq"),
    ("HNL", "hnl"),
    ("NIO", "nio"),
    ("PAB", "pab"),
    ("CUP", "cup"),
    ("BRL", "brl"),
    ("CAD", "cad"),
    ("CHF", "chf"),
    ("JPY", "jpy"),
    ("CNY", "cny"),
    ("INR", "inr"),
    ("KRW", "krw"),
    ("SVC", "svc"),
];
const DOLLAR_PREFIX: &[(&str, &str)] = &[
    ("MEX$", "mxn"),
    ("MX$", "mxn"),
    ("COL$", "cop"),
    ("CLP$", "clp"),
    ("AR$", "ars"),
    ("RD$", "dop"),
    ("US$", "us$"),
    ("U$S", "us$"),
    ("S/.", "s/"),
    ("S/", "s/"),
];
const AMOUNT: &str = r"\d+(?:[.,]\d+)*";

fn key<'a>(table: &[(&str, &'a str)], k: &str) -> &'a str {
    table.iter().find(|(a, _)| *a == k).map_or("", |(_, v)| *v)
}

fn es_money_code(t: String, c: &mut Ctx) -> String {
    let codes = CODES.iter().map(|(k, _)| re_escape(k)).collect::<Vec<_>>().join("|");
    let prefixes = DOLLAR_PREFIX.iter().map(|(k, _)| re_escape(k)).collect::<Vec<_>>().join("|");
    let t = c.sub(&rx(&format!(r"(?<![\w$])\${SP}?({AMOUNT}){SP}?({codes})(?!\w)")), &t, |m| {
        Some(format!("{} {}", g(m, 1), key(CODES, g(m, 2))))
    });
    let t = c.sub(&rx(&format!(r"(?<![\w.,])({AMOUNT}){SP}?\${SP}?({codes})(?!\w)")), &t, |m| {
        Some(format!("{} {}", g(m, 1), key(CODES, g(m, 2))))
    });
    let t = c.sub(&rx(&format!(r"(?<!\w)({codes}){SP}?\${SP}?({AMOUNT})")), &t, |m| {
        Some(format!("{} {}", key(CODES, g(m, 1)), g(m, 2)))
    });
    let t = c.sub(&rx(&format!(r"(?<![\w$/])({prefixes}){SP}?(?=\d)")), &t, |m| {
        Some(format!("{} ", key(DOLLAR_PREFIX, g(m, 1))))
    });
    // $100 pesos: the $ is the peso sign
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w$])\${SP}?({AMOUNT})({SP}+)(pesos?)(?!\w)")), &t, r"\1\2\3");
    let t = c.sub(&rx(&format!(r"(?<![\w.,])({AMOUNT}){SP}?({codes})(?!\w)")), &t, |m| {
        Some(format!("{} {}", g(m, 1), key(CODES, g(m, 2))))
    });
    c.sub(&rx(&format!(r"(?<!\w)({codes}){SP}?(?=\d)")), &t, |m| Some(format!("{} ", key(CODES, g(m, 1)))))
}

const CURRENCY_WORDS: &[(&str, &str, &str)] =
    &[("€", "euro", "euros"), ("$", "dólar", "dólares"), ("£", "libra", "libras")];
const SIGN: &str = r"€|\$|£|¥";
const AMT: &str = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?";

/// An amount as written (“1.200”, “2,5”, “7,50”) in cents, to compare the two ends of a range.
fn cents_of(a: &str) -> u128 {
    let (i, d) = a.split_once(',').unwrap_or((a, ""));
    let dv = if d.is_empty() { 0 } else { py_int(&format!("{d}0")[..2]) };
    py_int(&i.replace('.', "")).saturating_mul(100).saturating_add(dv)
}

fn joined(prep: &str, first: &str, last: &str) -> String {
    let p = prep.to_lowercase();
    let word = if p == "entre" {
        "y"
    } else if p == "desde" {
        "hasta"
    } else {
        "a"
    };
    format!("{} {first} {word} {last}", if prep.is_empty() { "de" } else { prep })
}

fn es_money_range(t: String, c: &mut Ctx) -> String {
    let prep = format!(r"(?:([Dd]e|[Ee]ntre|[Dd]esde){SP}+)?");
    let t = c.sub(
        &rx(&format!(r"(?<![\w$]){prep}({SIGN})({SP}?)({AMT}){SP}?[-–~]{SP}?(?:({SIGN}){SP}?)?({AMT})(?!\w|[.,]\d)")),
        &t,
        |m| {
            let (p, s, sp, a, s2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
            if (!s2.is_empty() && s2 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            Some(if a.contains(',') {
                joined(p, &format!("{s}{sp}{a}"), &format!("{s}{sp}{b}"))
            } else {
                joined(p, a, &format!("{b} {s}"))
            })
        },
    );
    let t = c.sub(
        &rx(&format!(r"(?<![\w.,]){prep}({AMT})(?:{SP}?({SIGN}))?{SP}?[-–~]{SP}?({AMT})({SP}?)({SIGN})(?![\w$])")),
        &t,
        |m| {
            let (p, a, s1, b, sp, s) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
            if (!s1.is_empty() && s1 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            let first = if a.contains(',') { format!("{a}{sp}{s}") } else { a.to_string() };
            Some(joined(p, &first, &format!("{b}{sp}{s}")))
        },
    );
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,$€£¥])[-−]({SIGN})({SP}?)({AMT})(?!\w|[.,]\d)")), &t, r"menos \1\2\3");
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,$€£¥])[-−]({AMT})({SP}?)({SIGN})(?![\w$])")), &t, r"menos \1\2\3");
    c.sub_tpl(&rx(&format!(r"(?<![\w$])({SIGN})({SP}?)[-−]({AMT})(?!\w|[.,]\d)")), &t, r"menos \1\2\3")
}

const PER: &[(&str, &str)] = &[("mes", "al mes"), ("año", "al año"), ("día", "al día"), ("semana", "a la semana")];

fn es_per_unit(t: String, c: &mut Ctx) -> String {
    let codes = CODES.iter().map(|(k, _)| re_escape(k)).collect::<Vec<_>>().join("|");
    let cur = format!(r"(?:{SIGN}|{codes})");
    let amount = format!(r"(?:{cur}{SP}?{AMT}|{AMT}{SP}?{cur})");
    c.sub(&rx(&format!(r"(?<![\w.,$])({amount})/([^\W\d_]+[²³]?)(?![\w/²³])")), &t, |m| {
        let tok = g(m, 2);
        if let Some((_, per)) = PER.iter().find(|(k, _)| *k == tok.to_lowercase()) {
            return Some(format!("{} {per}", g(m, 1)));
        }
        let one = words(&format!("1 {tok}"), "es");
        let rest = one.strip_prefix("un ").or_else(|| one.strip_prefix("una ")).or_else(|| one.strip_prefix("uno "))?;
        full(&format!("{LETTER}+(?: {LETTER}+)*"), rest).then(|| format!("{} por {rest}", g(m, 1)))
    })
}

fn many(sym: &str) -> &'static str {
    CURRENCY_WORDS.iter().find(|(s, _, _)| *s == sym).map_or("", |(_, _, m)| *m)
}

fn es_money_scale(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w.,])({AMOUNT}){SP}?M([€$£])(?!\w)")), &t, |m| {
        let num = g(m, 1);
        let scale = if num == "1" { "millón" } else { "millones" };
        Some(format!("{num} {scale} de {}", many(g(m, 2))))
    });
    c.sub(&rx(&format!(r"(?<!\w)(millón|millones|billón|billones){SP}+(?:de{SP}+)?([€$£])(?![\w\d])")), &t, |m| {
        Some(format!("{} de {}", g(m, 1), many(g(m, 2))))
    })
}

fn es_money_cents(t: String, c: &mut Ctx) -> String {
    let codes = format!(
        r"€|\$|£|{}|us\$|ar\$|rd\$|mex\$|s/",
        CODES
            .iter()
            .filter(|(_, v)| !["$", "£", "€"].contains(v))
            .map(|(_, v)| re_escape(v))
            .collect::<Vec<_>>()
            .join("|")
    );
    let integer = r"\d{1,3}(?:\.\d{3})+|\d+";
    let scale = format!(r"(?!{SP}*(?:mil|millón|millones|billón|billones)(?!\w))");
    let read = |intpart: &str, cents: &str| -> Option<String> {
        let n = intpart.replace('.', "");
        let cc: String = format!("{cents}0").chars().take(2).collect();
        if py_int(&cc) == 0 {
            return Some(n);
        }
        (n != intpart).then(|| format!("{n},{cents}"))
    };
    let t = c.sub(&rx(&format!(r"(?<![\w.,])({integer}),(\d{{1,2}})({SP}?(?:{codes}))(?![\w$]){scale}")), &t, |m| {
        read(g(m, 1), g(m, 2)).map(|x| x + g(m, 3))
    });
    let t = c.sub(&rx(&format!(r"(?<![\w$])((?:{codes}){SP}?)({integer}),(\d{{1,2}})(?!\w|[.,]\d){scale}")), &t, |m| {
        read(g(m, 2), g(m, 3)).map(|x| format!("{}{x}", g(m, 1)))
    });
    // 2000000,50 € → dos millones de euros cincuenta céntimos (the grammar dropped the “de” it says without cents)
    let big = r"[1-9]\d{6,14}";
    c.sub(
        &rx(&format!(
            r"(?<![\w.,])({big}),\d{{1,2}}{SP}?(?:{codes})(?![\w$])|(?<![\w$])(?:{codes}){SP}?({big}),\d{{1,2}}(?!\w|[.,]\d)"
        )),
        &t,
        |m| {
            let n = if m.get(1).is_some() { g(m, 1) } else { g(m, 2) };
            let head = words(n, "es");
            let spoken = words(&m[0], "es");
            if !BIG.contains(&head.split(' ').next_back().unwrap_or(""))
                || !spoken.starts_with(&format!("{head} "))
                || spoken.starts_with(&format!("{head} de "))
            {
                return None;
            }
            Some(format!("{head} de {}", &spoken[head.len() + 1..]))
        },
    )
}

// ------------------------------------------------------------------------------------------------ units

const UNITS: &[(&str, &str, &str)] = &[
    ("°C", "grado Celsius", "grados Celsius"),
    ("ºC", "grado Celsius", "grados Celsius"),
    ("℃", "grado Celsius", "grados Celsius"),
    ("°F", "grado Fahrenheit", "grados Fahrenheit"),
    ("ºF", "grado Fahrenheit", "grados Fahrenheit"),
    ("℉", "grado Fahrenheit", "grados Fahrenheit"),
    ("kcal", "kilocaloría", "kilocalorías"),
    ("t", "tonelada", "toneladas"),
    ("lb", "libra", "libras"),
    ("lbs", "libra", "libras"),
    ("oz", "onza", "onzas"),
    ("ha", "hectárea", "hectáreas"),
];

fn es_units(t: String, c: &mut Ctx) -> String {
    let mut units: Vec<&(&str, &str, &str)> = UNITS.iter().collect();
    units.sort_by_key(|u| std::cmp::Reverse(u.0.chars().count()));
    let alt = units.iter().map(|u| re_escape(u.0)).collect::<Vec<_>>().join("|");
    let re = rx(&format!(r"(?<![\w.,])([-−]?\d+(?:[.,]\d+)*){SP}?({alt})(?![\w°º/])"));
    c.sub(&re, &t, |m| {
        let (num, unit) = (g(m, 1), g(m, 2));
        let end = m.get(0).expect("group 0").end();
        if unit == "ha" && matches_at_start(&format!(r"{SP}+\w+(?:ado|ido|to|cho|so)\b"), &t[end..]) {
            return None;
        }
        let (_, one, many) = UNITS.iter().find(|u| u.0 == unit)?;
        Some(format!("{num} {}", if ["1", "-1", "−1"].contains(&num) { one } else { many }))
    })
}

// ------------------------------------------------------------------------------------------------ round millions

/// A whole number of millions as written (2.000.000, 3.500.000.000, 2000000; no leading zero); its reading decides.
const ROUND: &str = r"(?:[1-9]\d{0,2}(?:\.\d{3})*\.000\.000|[1-9]\d{0,8}000000)(?![\w%°ºª'’]|[.,:/\-–]\d)";
/// The currency signs and the grammar's currency keys that stand before an amount (es.money-code writes the keys).
const SIGN_KEYS: &[&str] = &[
    "mex$", "us$", "ar$", "rd$", "mxn", "ars", "cop", "clp", "pen", "uyu", "bob", "pyg", "crc", "dop", "gtq", "hnl",
    "nio", "pab", "cup", "brl", "cad", "chf", "jpy", "cny", "inr", "krw", "svc", "s/", "€", "$", "£", "¥", "₩", "₡",
    "₲", "₧",
];
/// Lower-case plural words after a round million that are not what it counts.
const SCALE_NOT_COUNTED: &str = "
más mas menos además después antes atrás detrás apenas mientras pues entonces jamás quizás demás tras según mediante
durante excepto salvo incluso vs los las les unos unas otros otras todos todas ambos ambas estos estas esos esas
aquellos aquellas muchos muchas pocos pocas varios varias algunos algunas ningunos ningunas ciertos ciertas tantos
tantas cuantos cuántos demasiados demasiadas nosotros vosotros ellos ellas ustedes sus mis tus nuestros nuestras
vuestros vuestras suyos suyas cuyos cuyas dos tres seis dieciséis veintidós veintitrés veintiséis somos estamos tenemos
hemos vamos podemos fuimos éramos eres estás has tienes puedes haces vas das sabes quieres debes dices anuales
mensuales semanales diarios diarias trimestrales adicionales restantes netos brutos totales iniciales extras exactos
gratis previstos previstas dispuestos propuestos primeros primeras últimos últimas
";
/// -ados/-idos words that are counted nouns (“2.000.000 desplazados”).
const PARTICIPLE_NOUNS: &str = "
soldados estados empleados diputados aliados afiliados abogados jubilados desplazados refugiados damnificados
infectados contagiados vacunados afectados heridos detenidos desaparecidos partidos sonidos vestidos apellidos
contenidos pedidos sentidos latidos ruidos nidos maridos cuñados grados mercados resultados dados lados pecados
bocados helados tejados condados puñados cuidados legados delegados licenciados graduados invitados asalariados
encuestados abonados asociados
";
static SCALE_NOT_COUNTED_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(SCALE_NOT_COUNTED));
static PARTICIPLE_NOUNS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(PARTICIPLE_NOUNS));

/// The grammar's words for a round million (“dos millones”), or None when they do not end in millón, millones,
/// billón or billones (prototype `scale_head`).
fn scale_head(num: &str) -> Option<String> {
    let w = words(num, "es");
    BIG.contains(&w.split(' ').next_back().unwrap_or("")).then_some(w)
}

/// What the grammar read after the number's words in `spoken` (“dos millones euros” → “euros”); a “de” the grammar
/// wrote itself is dropped (prototype `counted`).
fn counted(head: &str, spoken: &str) -> Option<String> {
    let h: Vec<&str> = head.split(' ').collect();
    let s: Vec<&str> = spoken.split(' ').collect();
    if s.len() <= h.len() || s[h.len() - 1] != h[h.len() - 1] {
        return None;
    }
    let mut rest = &s[h.len()..];
    if rest[0] == "de" && rest.len() > 1 {
        rest = &rest[1..];
    }
    if !rest.iter().all(|x| full(&format!("{LETTER}+"), x)) {
        return None;
    }
    Some(rest.join(" "))
}

/// A plural noun after a round million (prototype `counted_noun`).
fn counted_noun(w: &str) -> bool {
    if w.chars().count() < 3
        || !w.chars().next().is_some_and(char::is_lowercase)
        || !w.ends_with('s')
        || !full(&format!("{LETTER}+"), w)
    {
        return false;
    }
    if SCALE_NOT_COUNTED_SET.contains(w) || NOUNLESS_SET.contains(w) || DETERMINERS_SET.contains(w) {
        return false;
    }
    PARTICIPLE_NOUNS_SET.contains(w) || !(w.ends_with("ados") || w.ends_with("idos"))
}

/// The first word of `rest` ends in -s (the counted thing is plural).
fn plural_first(rest: &str) -> bool {
    rest.split(' ').next().unwrap_or("").ends_with('s')
}

fn es_scale_de(t: String, c: &mut Ctx) -> String {
    let tail = |num: &str, spoken: &str| -> Option<String> {
        let rest = counted(&scale_head(num)?, spoken)?;
        (!rest.is_empty() && plural_first(&rest)).then(|| format!("{num} de {rest}"))
    };
    // 2.000.000 €, 2.000.000 de €
    let t = c.sub(
        &rx(&format!(r"{NUM_BEFORE}({ROUND})({SP}?|{SP}+de{SP}+)([€$£¥₩₡₲₧])(?![\w$€£¥/])")),
        &t,
        |m| tail(g(m, 1), &words(&format!("{} {}", g(m, 1), g(m, 3)), "es")),
    );
    // €2.000.000, us$ 2.000.000, mxn 2.000.000
    let keys = SIGN_KEYS.iter().map(|k| re_escape(k)).collect::<Vec<_>>().join("|");
    let t = c.sub(
        &rx(&format!(r"(?<![\w$])({keys})({SP}?)({ROUND})(?!{SP}*(?:mil|millón|millones|billón|billones)(?!\w)|/)")),
        &t,
        |m| tail(g(m, 3), &words(&format!("{}{}{}", g(m, 1), g(m, 2), g(m, 3)), "es")),
    );
    // 2.000.000 personas, 2.000.000 km
    c.sub(
        &rx(&format!(r"{NUM_BEFORE}({ROUND})({SP}+)([^\W\d_]+(?:[²³]|/[^\W\d_]+)?)(?![\w/²³'’\-]|{SP}*\d)")),
        &t,
        |m| {
            let (num, tok) = (g(m, 1), g(m, 3));
            let rest = counted(&scale_head(num)?, &words(&format!("{num} {tok}"), "es"))?;
            if rest == tok {
                return counted_noun(tok).then(|| format!("{num} de {tok}"));
            }
            plural_first(&rest).then(|| format!("{num} de {rest}"))
        },
    )
}

// ------------------------------------------------------------------------------------------------ ranges

const SCORE_CUE: &str = r"(?i:ganó|gana|ganaron|perdió|pierde|perdieron|empató|empataron|venció|vencieron|derrotó|cayó|goleó|marcador|resultado|victoria|derrota|empate|partido|final)";

fn es_range(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"(?<![\w.,/:\-–])(?:([Dd]e|[Ee]ntre|[Dd]esde){SP}+)?(\d{{1,3}}){SP}?[-–]{SP}?(\d{{1,3}})(?={SP}+(?!de\b|del\b)({LETTER}+))"
    ));
    let cue = format!(r"(?<!\w){SCORE_CUE}(?:{SP}+{LETTER}+){{0,3}}{SP}+$");
    c.sub(&re, &t, |m| {
        let (prep, a, b, nxt) = (m.get(1).map(|x| x.as_str()), g(m, 2), g(m, 3), g(m, 4));
        if py_int(a) >= py_int(b) {
            return None;
        }
        let start = m.get(0).expect("group 0").start();
        if prep.is_none() && search(&cue, chars_before(&t, start, 40)) {
            return Some(format!("{a} a {b}"));
        }
        if NOUNLESS_SET.contains(lower(nxt).as_str()) {
            return None;
        }
        match prep {
            Some(p) if lower(p) == "entre" => Some(format!("{p} {a} y {b}")),
            Some(p) if lower(p) == "desde" => Some(format!("{p} {a} hasta {b}")),
            _ => Some(format!("{} {a} a {b}", prep.unwrap_or("de"))),
        }
    })
}

// ------------------------------------------------------------------------------------------------ halves

fn es_half(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(r"(?<![\w.,/:\-])(?:(\d+){SP}+)?1/2(?![\d/])({SP}+)({LETTER}+)"));
    c.sub(&re, &t, |m| {
        let (whole, sp, word) = (g(m, 1), g(m, 2), g(m, 3));
        let gender = noun_gender(word);
        if gender == "n" {
            return None;
        }
        let half = if gender == "f" { "media" } else { "medio" };
        if whole.is_empty() {
            return (gender == "f").then(|| format!("{half}{sp}{word}"));
        }
        if whole == "1" {
            if !search(r"[aeiouáéó]s$", word) {
                return None;
            }
            let stem: String = {
                let mut cs: Vec<char> = word.chars().collect();
                cs.pop();
                cs.into_iter().collect()
            };
            return Some(format!("1 {stem} y {half}"));
        }
        Some(format!("{whole} {word} y {half}"))
    })
}

// ------------------------------------------------------------------------------------------------ gender

fn es_hour_article(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r#"(?<!\w)((?:[Aa]|[Hh]asta|[Dd]esde|[Ss]obre|[Pp]ara|[Dd]e|[Ee]ntre|[Hh]acia|[Tt]ras|[Ss]on|[Ee]s|[Ee]ra|[Ee]ran){SP}+las?{SP}+)(\d{{1,2}})(?![\w%°ºª'’]|[.,:/\-–]\w)(?={SP}*(?:[.,;:!?)\]»”"…\n]|$)|{SP}+(?:y|e|o|de|del|en|a|al|con|por|para|hasta|menos|más)(?!\w))"#
    ));
    c.sub(&re, &t, |m| {
        if py_int(g(m, 2)) > 24 {
            return None;
        }
        let base = words(g(m, 2), "es");
        let w = feminine(&base);
        (w != base).then(|| format!("{}{w}", g(m, 1)))
    })
}

static YEAR_CUE: LazyLock<String> =
    LazyLock::new(|| format!(r"(?<!\w)(?i:(?:en|de|del|desde|hasta|año|hacia|para|antes|después|durante|el){SP}+)$"));
/// A number right after a month or weekday (“mayo 2021”, “agt. 1”, “SÁB de 1221”) belongs to the date reading.
static DATE_BEFORE: LazyLock<String> = LazyLock::new(|| {
    let mut abbr: Vec<&str> = DATE_ABBR.split_whitespace().collect();
    abbr.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    let names: Vec<&str> = MONTHS.iter().chain(DAYS).copied().collect();
    format!(
        r"(?<!\w)(?:(?i:{})|{})(?:{SP}+del?)?{SP}*$",
        names.join("|"),
        abbr.iter().map(|a| re_escape(a)).collect::<Vec<_>>().join("|")
    )
});
const CURRENCY_KEYS: &str =
    "ars ar$ awg bob brl cad chf clp cny cop crc ₡ cup dop rd$ eur gtq gyd hkd hnl htg inr jpy kr kr. krw mxn
nio pab pen s/ pyg ₲ rs rs. svc ttd usd uyu uyw arp bop cle ecs mxp peh veb vef € $ £ ₩ fr mk ¥ r$ ₧ ptas us$ mex$
q";
static CURRENCY_KEYS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(CURRENCY_KEYS));
static CURRENCY_BEFORE: LazyLock<String> = LazyLock::new(|| {
    let mut keys: Vec<&str> = CURRENCY_KEYS.split_whitespace().collect();
    keys.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    format!(r"(?:^|[^\w$])(?:{}){SP}?$", keys.iter().map(|k| re_escape(k)).collect::<Vec<_>>().join("|"))
});

fn es_gender(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"{NUM_BEFORE}({NUM}(?:{SP}+(?:y|o|u|ó|e|a){SP}+{NUM})*)(?:({SP}+)({LETTER}+)(?![\w\x{{200B}}]|\.{SP}?{LETTER}\.)(?:({SP}+)({LETTER}+)(?![\w\x{{200B}}]))?)?"
    ));
    c.sub(&re, &t, |m: &Captures<'_, str>| {
        let m0 = m.get(0).expect("group 0");
        let chain = g(m, 1);
        let (w1, w2) = (m.get(3).map(|x| x.as_str()), m.get(5).map(|x| x.as_str()));
        let mut gender = "";
        match w1 {
            None => {
                // nothing after it but the end of the phrase (not a bracket: “(591)” is an area code)
                if matches_at_start(&format!(r#"{SP}*(?:[.,;:!?»”"…\n]|$)"#), &t[m0.end()..]) {
                    gender = "n";
                }
            }
            Some(w1) => {
                gender = noun_gender(w1);
                let l1 = lower(w1);
                if (INVARIANT_ADJ_SET.contains(l1.as_str()) || w1 == "mil") && w2.is_some() {
                    gender = noun_gender(w2.unwrap_or(""));
                    if gender == "n" {
                        gender = "";
                    }
                } else if (l1 == "de" || l1 == "del")
                    && let Some(w2) = w2
                {
                    let l2 = lower(w2);
                    if DATE_WORDS.contains(w2) || DATE_WORDS.contains(&l2) {
                        gender = "";
                    } else if ["las", "ellas", "estas", "esas", "aquellas", "nosotras", "vosotras"]
                        .contains(&l2.as_str())
                    {
                        gender = "f";
                    }
                }
            }
        }
        if gender.is_empty() {
            return None;
        }
        let before = chars_before(&t, m0.start(), 24); // the words just before the number
        if w1.is_some_and(|w| CURRENCY_KEYS_SET.contains(lower(w).as_str()))
            || search(&CURRENCY_BEFORE, before)
            || search(&DATE_BEFORE, before)
        {
            return None;
        }
        let num_re = rx(r"\d{1,3}(?:\.\d{3})+|\d+");
        let nums: Vec<&str> = num_re.find_iter(chain).flatten().map(|x| x.as_str()).collect();
        if nums.iter().any(|x| x.starts_with('0') && *x != "0") {
            return None; // a code with a leading zero is read digit by digit
        }
        if gender == "n" && nums.iter().any(|x| x.replace('.', "").chars().count() > 6) {
            return None; // a long number at the end of a phrase is often a phone number or an id
        }
        if gender == "f" && full(r"1\d{3}|20\d{2}", chain) && search(&YEAR_CUE, before) {
            return None;
        }
        let new_chain = sub_plain(&num_re, chain, |x| {
            let w = words(&x[0], "es");
            let new = if gender == "f" {
                if w1 == Some("mil") {
                    let f = feminine(&format!("{w} mil"));
                    f[..f.len() - 4].to_string() // 200 mil personas: doscientas mil
                } else {
                    feminine(&w)
                }
            } else {
                citation(&w)
            };
            Some(if new != w { new } else { x[0].to_string() })
        });
        if new_chain == chain {
            return None;
        }
        Some(format!("{new_chain}{}", &m0.as_str()[chain.len()..]))
    })
}

// ------------------------------------------------------------------------------------------------ space-grouped numbers

const SPACE_NUM: &str = r"[1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+";

fn es_space_groups(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r#"(?<![^\s(«“"'‘])((?:€|\$|£|¥)[ \t\x{{A0}}]?)?(?<![\w.,])(?<!\d[ \x{{A0}}\x{{202F}}])({SPACE_NUM})(?![ \x{{A0}}\x{{202F}}]?\d|[.,]\d{{3}}|,(?:\d\d|\d(?!\d))[^\s€$£¥])"#
    ));
    c.sub(&re, &t, |m| {
        let m0 = m.get(0).expect("group 0");
        let rest = &t[m0.end()..];
        let ok = m.get(1).is_some()
            || matches_at_start(r"(?:,\d{1,2})?[ \t\x{A0}\x{202F}]?(?:€|\$|£|¥)(?!\w)", rest)
            || matches_at_start(r"[ \t\x{A0}\x{202F}]+(?!(?:mil|millón|millones|billón|billones|trillón|trillones|millardos?)(?!\w))[^\W\d_]+(?![\w])", rest)
            || (g(m, 2).ends_with("000") && matches_at_start(r#"(?:\s|$|[.,;:!?)\]»”"…])"#, rest));
        ok.then(|| {
            let dotted: String = g(m, 2).chars().map(|ch| if " \u{a0}\u{202f}".contains(ch) { '.' } else { ch }).collect();
            format!("{}{dotted}", g(m, 1))
        })
    })
}
