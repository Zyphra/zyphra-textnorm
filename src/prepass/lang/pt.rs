//! 'pt' rules: the port of the workbench's `langrules/pt.py` (ids `pt.*`).
//!
//! The Portuguese grammar reads every number in the masculine (“22 pessoas” → “vinte e dois pessoas”, “200 cadeiras”
//! → “duzentos cadeiras”), has no list of abbreviations at all (its whitelist is empty upstream) and no Roman
//! numerals.

use std::collections::HashSet;
use std::sync::LazyLock;

#[allow(unused_imports)]
use super::super::{Ctx, chars_before, full, g, matches_at_start, py_int, rx, search, sub_plain, tpl};
#[allow(unused_imports)]
use super::{LangRule, digit_words, words};
use crate::text::py_strip;

pub(super) const RULES: &[LangRule] = &[
    ("pt.abbrev", pt_abbrev),
    ("pt.seculo", pt_seculo),
    ("pt.regnal", pt_regnal),
    ("pt.space-groups", pt_space_groups),
    ("pt.money-code", pt_money_code),
    ("pt.money-range", pt_money_range),
    ("pt.per-unit", pt_per_unit),
    ("pt.money-cents", pt_money_cents),
    ("pt.money-scale", pt_money_scale),
    ("pt.units", pt_units),
    ("pt.scale-de", pt_scale_de),
    ("pt.range", pt_range),
    ("pt.score", pt_score),
    ("pt.half", pt_half),
    ("pt.hour-article", pt_hour_article),
    ("pt.gender", pt_gender),
    ("pt.scale-e", pt_scale_e),
    ("pt.sign-punct", pt_sign_punct),
];

const LETTER: &str = r"[^\W\d_]";
const SP: &str = r"[ \t\x{A0}]";
const NUM: &str = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?![\w%°ºª'’]|[.,:/\-–]\w|[ \x{A0}]\d)";
const NUM_BEFORE: &str = r"(?<![\w.,/:\-−–+$€£¥₩₹₽#\\])(?<!\d[ \x{A0}])";
const ROMAN: &str = r"(?=[IVXLC])C{0,3}(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})";
const UPPER: &str = "A-ZÁÂÃÀÉÊÍÓÔÕÚÇ";
const LOWER: &str = "a-záâãàéêíóôõúç";

fn roman_value(s: &str) -> u32 {
    let v = |c: char| match c {
        'I' => 1i64,
        'V' => 5,
        'X' => 10,
        'L' => 50,
        'C' => 100,
        _ => 0,
    };
    let cs: Vec<char> = s.chars().collect();
    let mut n: i64 = 0;
    for (i, &ch) in cs.iter().enumerate() {
        let x = v(ch);
        n += if i + 1 < cs.len() && v(cs[i + 1]) > x { -x } else { x };
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
    ("um", "uma"),
    ("dois", "duas"),
    ("duzentos", "duzentas"),
    ("trezentos", "trezentas"),
    ("quatrocentos", "quatrocentas"),
    ("quinhentos", "quinhentas"),
    ("seiscentos", "seiscentas"),
    ("setecentos", "setecentas"),
    ("oitocentos", "oitocentas"),
    ("novecentos", "novecentas"),
];
const BIG: &[&str] = &["milhão", "milhões", "bilhão", "bilhões", "trilhão", "trilhões", "quatrilhão", "quatrilhões"];

/// The feminine reading of a cardinal's words (prototype `feminine`).
fn feminine(w: &str) -> String {
    let toks: Vec<&str> = w.split(' ').collect();
    let mut start = 0;
    for (i, x) in toks.iter().enumerate() {
        if BIG.contains(x) {
            start = i + 1;
        }
    }
    toks.iter()
        .enumerate()
        .map(|(i, x)| if i < start { *x } else { FEM.iter().find(|(a, _)| a == x).map_or(*x, |(_, b)| *b) })
        .collect::<Vec<_>>()
        .join(" ")
}

/// A whole number of a million or more, dot-grouped or plain (7 to 15 digits, no leading zero).
const BIG_NUM: &str = r"[1-9][0-9]{0,2}(?:\.[0-9]{3}){2,4}|[1-9][0-9]{6,14}";

/// `w`, a reading that starts with the grammar's words for the whole number `num`, with “e” before the last group of
/// a number from a million up when that group is below 100 or a round hundred (prototype `with_e`).
fn with_e(num: &str, w: &str) -> String {
    let d = num.replace('.', "");
    if d.len() < 7 || d.len() > 15 || d.starts_with('0') || !d.chars().all(|ch| ch.is_ascii_digit()) {
        return w.to_string();
    }
    let mut n: u64 = d.parse().unwrap_or(0);
    let mut k = 0;
    while n > 0 && n % 1000 == 0 {
        n /= 1000;
        k += 1;
    }
    let v = n % 1000;
    if v == n || !(v < 100 || v % 100 == 0) {
        return w.to_string();
    }
    let head = words(num, "pt");
    let tail = words(&format!("{v}{}", "000".repeat(k)), "pt");
    if !w.starts_with(&head) || !head.ends_with(&format!(" {tail}")) || head.ends_with(&format!(" e {tail}")) {
        return w.to_string();
    }
    format!("{}e {tail}{}", &head[..head.len() - tail.len()], &w[head.len()..])
}

// ------------------------------------------------------------------------------------------------ noun genders

fn plural(w: &str) -> String {
    if w.ends_with("ão") && w != "mão" {
        return format!("{}ões", &w[..w.len() - "ão".len()]);
    }
    if w.ends_with("ãe") || w.ends_with('ã') {
        return format!("{w}s");
    }
    if let Some(h) = w.strip_suffix('m') {
        return format!("{h}ns");
    }
    if let Some(h) = w.strip_suffix('l') {
        return format!("{h}is");
    }
    if w.chars().next_back().is_some_and(|c| "rzs".contains(c)) {
        return format!("{w}es");
    }
    format!("{w}s")
}

const FEM_NOUNS: &str = "
hora meia semana quinzena década noite tarde manhã madrugada jornada temporada vez etapa fase época edição volta rodada
sessão aula lição data geração consulta visita ligação chamada reunião conferência palestra festa refeição bebida
comida janta ceia tonelada libra onça polegada milha jarda caloria quilocaloria arroba légua colher colherada xícara
xicrinha pitada cabeça fatia rodela porção gota lata garrafa taça jarra caneca concha sacola caixa dúzia dezena
centena unidade peça parte cápsula pílula dose folha página linha palavra letra frase oração canção música série cena
foto fotografia imagem mão carta cama casa praça rua avenida cidade província região comunidade ilha montanha praia
igreja escola universidade loja empresa companhia firma fábrica sede filial mesa cadeira poltrona porta janela parede
chave conta entrada saída opção pergunta resposta ideia razão causa coisa forma maneira pessoa mulher menina garota
moça filha irmã mãe avó tia prima amiga esposa senhora família vítima morte vida espécie raça vaca ovelha galinha cabra
égua abelha formiga mosca baleia tartaruga serpente cobra aranha planta flor rosa semente maçã laranja pera banana
batata cebola cenoura alface berinjela abóbora azeitona amêndoa noz bolacha torta pizza cerveja receita gema clara
pastilha pilha bateria lâmpada máquina tela câmera impressora aplicação ferramenta rede versão função variável tabela
coluna fila célula base camada tarefa prova amostra pesquisa estrela medalha vitória derrota meta corrida rota via
estação parada roda moto bicicleta caminhonete nave lancha barca pistola bala bomba arma guerra batalha revolução lei
norma regra multa pena queixa notícia história novela obra revista sala cozinha varanda piscina fazenda granja moradia
vaga oferta fatura propriedade vacina cirurgia operação mascote nota matéria disciplina bolsa língua sílaba vogal
consoante cifra estrofe tecla corda pista criança moeda peseta lira coroa rupia ação cota parcela prestação
mensalidade diária unidade vela vez porção fileira cartela embalagem garrafinha latinha xícara colherinha
partida rodada viagem mensagem passagem garagem paisagem bagagem homenagem margem origem idade cidade
equipe seleção jogadora aluna professora doutora enfermeira trabalhadora dama rainha princesa
";
const FEM_IRREGULAR: &[&str] = &["mães", "avós", "irmãs", "manhãs", "maçãs"];
const MASC_AS: &str = "
dias mapas planetas cometas guardas colegas guias atletas poetas profetas pilotas patriotas idiotas jesuítas gorilas
coalas pandas pumas sofás atlas gás
";
const DETERMINERS: &str = "
muitas poucas todas outras várias algumas certas tantas quantas essas estas aquelas ambas nenhumas umas as minhas
tuas suas nossas vossas duas mais apenas
";
const INVARIANT_ADJ: &str = "grandes melhores piores diferentes importantes enormes jovens principais possíveis";
const PLURAL_SUFFIXES: &[&str] = &["ções", "sões", "dades", "agens"];
const SINGULAR_SUFFIXES: &[&str] = &["ção", "são", "dade", "agem"];
const NOT_FEM_SUFFIXES: &[&str] =
    &["mas", "istas", "icidas", "cratas", "nautas", "iatras", "personagens", "personagem", "selvagens", "selvagem"];
const MONTHS: &[&str] = &[
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
];

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

/// 'f' for a feminine noun, "" otherwise (masculine or unknown: today's reading stays).
fn noun_gender(word: &str) -> &'static str {
    let w = lower(word);
    if FEM_FORMS.contains(&w) {
        return "f";
    }
    if MASC_AS_SET.contains(w.as_str())
        || DETERMINERS_SET.contains(w.as_str())
        || NOT_FEM_SUFFIXES.iter().any(|x| w.ends_with(x))
    {
        return "";
    }
    let n = w.chars().count();
    if PLURAL_SUFFIXES.iter().chain(SINGULAR_SUFFIXES).any(|x| w.ends_with(x) && n > x.chars().count() + 1) {
        return "f"; // visão, versões (not são, agem)
    }
    if n > 3 && w.ends_with("as") {
        return "f";
    }
    ""
}

// ------------------------------------------------------------------------------------------------ abbreviations

static ABBREV: LazyLock<Vec<(&'static str, String, &'static [&'static str])>> = LazyLock::new(|| {
    let name = format!(r"(?={SP}+[{UPPER}][{LOWER}])");
    let number = format!(r"(?={SP}*\d)");
    vec![
        (r"Srtas?\.", name.clone(), &["senhorita", "senhoritas"][..]),
        (r"Sras?\.", name.clone(), &["senhora", "senhoras"][..]),
        (r"Sr\.", name.clone(), &["senhor"][..]),
        (r"Srs\.", name.clone(), &["senhores"][..]),
        (r"Sres\.", name.clone(), &["senhores"][..]),
        (r"Dras?\.", name.clone(), &["doutora", "doutoras"][..]),
        (r"Drs?\.", name.clone(), &["doutor", "doutores"][..]),
        (r"Prof(?:a|ª)\.?", name.clone(), &["professora"][..]),
        (r"Prof\.", name.clone(), &["professor"][..]),
        (r"Eng(?:a|ª)\.?", name.clone(), &["engenheira"][..]),
        (r"Eng\.", name.clone(), &["engenheiro"][..]),
        (r"D\.ª", name.clone(), &["dona"][..]),
        (r"Sto\.", name.clone(), &["santo"][..]),
        (r"Sta\.", name.clone(), &["santa"][..]),
        (r"[Aa]v\.", name.clone(), &["avenida"][..]),
        (r"R\.", format!(r"(?={SP}+(?:d[aeo]s?{SP}+)?[{UPPER}][{LOWER}]{{2,}})"), &["rua"][..]),
        (r"[Nn]\.?[º°]s", number.clone(), &["números"][..]),
        (r"[Nn]\.?[º°]", number.clone(), &["número"][..]),
        (r"[Pp]ágs\.", number.clone(), &["páginas"][..]),
        (r"[Pp]ág\.", number.clone(), &["página"][..]),
        (r"[Cc]ap\.", number.clone(), &["capítulo"][..]),
        (r"[Aa]rt\.", number.clone(), &["artigo"][..]),
        (r"[Vv]ol\.", number.clone(), &["volume"][..]),
        (r"[Tt]el\.", format!(r"(?={SP}*[\d(:+])"), &["telefone"][..]),
        (r"[Aa]prox\.", number.clone(), &["aproximadamente"][..]),
        (r"[Pp]\.[ \t\x{A0}]?ex\.", String::new(), &["por exemplo"][..]),
        (r"V\.[ \t\x{A0}]?Exa?\.", String::new(), &["Vossa Excelência"][..]),
        (r"Ltda\.", String::new(), &["limitada"][..]),
    ]
});

fn pt_abbrev(t: String, c: &mut Ctx) -> String {
    let mut t = t;
    for (pat, ctx, forms) in ABBREV.iter() {
        let re = rx(&format!(r"(?<![\w.]){pat}{ctx}"));
        t = c.sub(&re, &t, |m| {
            let m0 = m.get(0).expect("group 0");
            let s = m0.as_str();
            if *pat == r"R\." && search(&format!(r"[{UPPER}][{LOWER}]+{SP}+$"), chars_before(&t, m0.start(), 24)) {
                return None; // a middle initial: “José R. Silva”
            }
            let plural_form = forms.len() > 1 && search(r"s\.?$", &s.replace('ª', ""));
            Some(cap_like(s, if plural_form { forms[1] } else { forms[0] }))
        });
    }
    let t = c.sub_tpl(&rx(&format!(r"(?<!\w)etc\.(?={SP}*[,;:)\]]|{SP}+[{LOWER}])")), &t, "etcétera");
    c.sub_tpl(&rx(r"(?<!\w)etc\."), &t, "etcétera.")
}

// ------------------------------------------------------------------------------------------------ Roman numerals

/// A Roman numeral after a name or século: an ordinal up to ten, a cardinal above (prototype `roman_reading`).
fn roman_reading(n: u32, fem: bool) -> String {
    if n <= 10 {
        return words(&format!("{n}{}", if fem { "ª" } else { "º" }), "pt");
    }
    words(&n.to_string(), "pt")
}

fn pt_seculo(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"(?<!\w)(séculos?|Séculos?|SÉCULOS?|[Ss]écs?\.){SP}*({ROMAN})(?!\w|\.\w)(?:({SP}*(?:e|a|ao|-|–){SP}*)({ROMAN})(?!\w))?"
    ));
    c.sub(&re, &t, |m| {
        let (head, r1, sep, r2) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4));
        let lh = lower(head);
        let many = lh.starts_with("séculos") || lh.starts_with("sécs") || !r2.is_empty();
        let word = if many { "séculos" } else { "século" };
        let lead = if lh.starts_with("século") { cap_like(head, word) } else { word.to_string() };
        let mut out = format!("{lead} {}", roman_reading(roman_value(r1), false));
        if !r2.is_empty() {
            let s = py_strip(sep);
            out.push_str(&if s == "-" || s == "–" { " a ".to_string() } else { format!(" {s} ") });
            out.push_str(&roman_reading(roman_value(r2), false));
        }
        Some(out)
    })
}

const REGNAL_MASC: &str = "
Pedro João José Manuel Afonso Sancho Dinis Fernando Duarte Sebastião Henrique Filipe Carlos Luís Luiz Miguel Bento Pio
Paulo Gregório Leão Inocêncio Clemente Urbano Bonifácio Alexandre Júlio Sisto Nicolau Adriano Eduardo Jorge Guilherme
Ricardo Napoleão Frederico Francisco Vítor Humberto Constantino Justiniano Ramsés Gustavo Olavo Haroldo Canuto
Cristiano Ivan Juan Felipe Alfonso Estêvão Ladislau Casimiro Sigismundo Venceslau Otão Rodolfo Maximiliano Leopoldo
Carlos Basílio Teodósio Calisto Eugênio Marcelo Martinho Simão Tutemés Ptolomeu
";
const REGNAL_FEM: &str = "Maria Isabel Elizabeth Catarina Ana Vitória Joana Leonor Mafalda Teresa Beatriz Margarida Cristina \
                          Carlota Amélia Luísa Juliana Mariana Antónia Leopoldina";
const TITLES: &str = "D|Dom|Dona|[Rr]ei|[Rr]ainha|[Pp]apa|[Ii]mperador|[Ii]mperatriz|[Pp]ríncipe|[Pp]rincesa|[Cc]zar|[Ss]ultão|[Ff]araó|[Ii]nfante|[Ii]nfanta";
const FEM_TITLES: &[&str] =
    &["Dona", "rainha", "Rainha", "imperatriz", "Imperatriz", "princesa", "Princesa", "infanta", "Infanta"];
static REGNAL_MASC_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(REGNAL_MASC));
static REGNAL_FEM_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(REGNAL_FEM));

fn pt_regnal(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"(?<![\w.])(?:({TITLES})(\.?){SP}+)?((?:[{UPPER}][{LOWER}]+{SP}+)?)([{UPPER}][{LOWER}]+){SP}+({ROMAN})(?!\w|\.\w)"
    ));
    c.sub(&re, &t, |m| {
        let (title, dot, first, name, r) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
        if title == "D" && dot.is_empty() {
            return None;
        }
        if title.is_empty() && !REGNAL_MASC_SET.contains(name) && !REGNAL_FEM_SET.contains(name) {
            return None;
        }
        let first_name = if first.is_empty() { name } else { first.split_whitespace().next().unwrap_or("") };
        let fem = REGNAL_FEM_SET.contains(first_name) || FEM_TITLES.contains(&title);
        let lead = if title.is_empty() {
            String::new()
        } else if title == "D" {
            format!("{} ", if fem { "Dona" } else { "Dom" })
        } else {
            format!("{title}{dot} ")
        };
        Some(format!("{lead}{first}{name} {}", roman_reading(roman_value(r), fem)))
    })
}

// ------------------------------------------------------------------------------------------------ money

const CODES: &[(&str, &str)] = &[("USD", "US$"), ("EUR", "€"), ("GBP", "£"), ("BRL", "R$")];
/// Scale words after an amount, with their singular and plural (mi, bi, tri are the newspaper abbreviations).
const SCALES: &[(&str, &str, &str)] = &[
    ("mil", "mil", "mil"),
    ("milhão", "milhão", "milhões"),
    ("milhões", "milhão", "milhões"),
    ("mi", "milhão", "milhões"),
    ("bilhão", "bilhão", "bilhões"),
    ("bilhões", "bilhão", "bilhões"),
    ("bi", "bilhão", "bilhões"),
    ("trilhão", "trilhão", "trilhões"),
    ("trilhões", "trilhão", "trilhões"),
    ("tri", "trilhão", "trilhões"),
    ("quatrilhão", "quatrilhão", "quatrilhões"),
    ("quatrilhões", "quatrilhão", "quatrilhões"),
];
const SYMBOLS: &str = r"R\$|US\$|€|£|\$";
const INTEGER: &str = r"\d{1,3}(?:\.\d{3})+|\d+";
const CURRENCY_NAMES: &[(&str, &str, &str)] = &[
    ("R$", "real", "reais"),
    ("US$", "dólar", "dólares"),
    ("€", "euro", "euros"),
    ("£", "libra esterlina", "libras esterlinas"),
    ("$", "dólar", "dólares"),
];

fn code_key(k: &str) -> &'static str {
    CODES.iter().find(|(a, _)| *a == k).map_or("", |(_, v)| *v)
}

/// The currencies of the other Portuguese-speaking countries and of Brazil's neighbours, and a few common ones the
/// grammar does not know: code, singular, plural, cent singular, cent plural (no cents: "").
const LOCAL_CODES: &[(&str, &str, &str, &str, &str)] = &[
    ("AOA", "kwanza", "kwanzas", "cêntimo", "cêntimos"),
    ("Kz", "kwanza", "kwanzas", "cêntimo", "cêntimos"),
    ("MZN", "metical", "meticais", "centavo", "centavos"),
    ("CVE", "escudo cabo-verdiano", "escudos cabo-verdianos", "centavo", "centavos"),
    ("ARS", "peso argentino", "pesos argentinos", "centavo", "centavos"),
    ("UYU", "peso uruguaio", "pesos uruguaios", "centésimo", "centésimos"),
    ("CLP", "peso chileno", "pesos chilenos", "", ""),
    ("PYG", "guarani", "guaranis", "", ""),
    ("BOB", "boliviano", "bolivianos", "centavo", "centavos"),
    ("MXN", "peso mexicano", "pesos mexicanos", "centavo", "centavos"),
    ("CHF", "franco suíço", "francos suíços", "cêntimo", "cêntimos"),
    ("JPY", "iene", "ienes", "", ""),
];

/// “2.000.000 AOA” → “dois milhões de kwanzas”, “2,50 MZN” → “dois meticais e cinquenta centavos” (prototype
/// `local_amount`).
fn local_amount(minus: &str, num: &str, cents: &str, code: &str) -> Option<String> {
    let &(_, one, many, minor1, minor_n) = LOCAL_CODES.iter().find(|x| x.0 == code)?;
    let cv = if cents.is_empty() { 0 } else { py_int(&format!("{cents}0")[..2]) };
    if cv != 0 && minor1.is_empty() {
        return None;
    }
    let n = py_int(&num.replace('.', ""));
    let minor = if cv == 1 { minor1 } else { minor_n };
    let out = if n == 0 && cv != 0 {
        format!("{} {minor}", words(&cv.to_string(), "pt"))
    } else {
        let w = with_e(num, &words(num, "pt"));
        let name = if n == 1 {
            one.to_string()
        } else if BIG.contains(&w.split(' ').next_back().unwrap_or("")) {
            format!("de {many}")
        } else {
            many.to_string()
        };
        let mut out = format!("{w} {name}");
        if cv != 0 {
            out = format!("{out} e {} {minor}", words(&cv.to_string(), "pt"));
        }
        out
    };
    Some(format!("{}{out}", if minus.is_empty() { "" } else { "menos " }))
}

fn pt_money_code(t: String, c: &mut Ctx) -> String {
    let codes = CODES.iter().map(|(k, _)| *k).collect::<Vec<_>>().join("|");
    let t = c.sub(&rx(&format!(r"(?<![\w.,])(\d+(?:[.,]\d+)*){SP}?({codes})(?!\w)")), &t, |m| {
        Some(format!("{} {}", code_key(g(m, 2)), g(m, 1)))
    });
    let t = c.sub(&rx(&format!(r"(?<!\w)({codes}){SP}?(?=\d)")), &t, |m| Some(format!("{} ", code_key(g(m, 1)))));
    let alt = LOCAL_CODES.iter().map(|x| x.0).collect::<Vec<_>>().join("|");
    let t =
        c.sub(&rx(&format!(r"(?<![\w.,\-–~])([-−]?)({INTEGER})(?:,(\d{{1,2}}))?{SP}?({alt})(?!\w)")), &t, |m| {
            local_amount(g(m, 1), g(m, 2), g(m, 3), g(m, 4))
        });
    let t = c.sub(
        &rx(&format!(r"(?<!\w)({alt}){SP}?([-−]?)({INTEGER})(?:,(\d{{1,2}}))?(?!\w|[.,]\d|{SP}?[-–~])")),
        &t,
        |m| local_amount(g(m, 2), g(m, 3), g(m, 4), g(m, 1)),
    );
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w$])¥{SP}?({INTEGER})(?!\w|[.,]\d)")), &t, r"\1 ¥");
    // £ 2 → 2 libras esterlinas, so the number agrees (the grammar read “dois libras esterlinas”)
    let scale = format!(r"(?!{SP}*(?:{})(?!\w))", SCALES.iter().map(|s| s.0).collect::<Vec<_>>().join("|"));
    let re = rx(&format!(r"(?<![\w$])£{SP}?({INTEGER})(?!\w|[.,]\d){scale}|(?<![\w.,])({INTEGER}){SP}?£(?!\w)"));
    c.sub(&re, &t, |m| {
        let n = if m.get(1).is_some() { g(m, 1) } else { g(m, 2) };
        let w = words(n, "pt");
        if feminine(&w) == w {
            return None;
        }
        Some(if n == "1" { format!("{n} libra esterlina") } else { format!("{n} libras esterlinas") })
    })
}

const SIGN: &str = r"R\$|US\$|€|£|\$|¥";
const AMT: &str = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?";

/// An amount as written (“1.200”, “2,5”, “7,50”) in cents, to compare the two ends of a range.
fn cents_of(a: &str) -> u128 {
    let (i, d) = a.split_once(',').unwrap_or((a, ""));
    let dv = if d.is_empty() { 0 } else { py_int(&format!("{d}0")[..2]) };
    py_int(&i.replace('.', "")).saturating_mul(100).saturating_add(dv)
}

fn pt_money_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&format!(r"(?<![\w$])({SIGN})({SP}?)({AMT}){SP}?[-–~]{SP}?(?:({SIGN}){SP}?)?({AMT})(?!\w|[.,]\d)")),
        &t,
        |m| {
            let (s, sp, a, s2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            if (!s2.is_empty() && s2 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            Some(if a.contains(',') { format!("{s}{sp}{a} a {s}{sp}{b}") } else { format!("{a} a {b} {s}") })
        },
    );
    let t = c.sub(
        &rx(&format!(r"(?<![\w.,])({AMT})(?:{SP}?({SIGN}))?{SP}?[-–~]{SP}?({AMT})({SP}?)({SIGN})(?![\w$])")),
        &t,
        |m| {
            let (a, s1, b, sp, s) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            if (!s1.is_empty() && s1 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            Some(if a.contains(',') { format!("{a}{sp}{s} a {b}{sp}{s}") } else { format!("{a} a {b}{sp}{s}") })
        },
    );
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,$€£¥])[-−]({SIGN})({SP}?)({AMT})(?!\w|[.,]\d)")), &t, r"menos \1\2\3");
    let t = c.sub_tpl(&rx(&format!(r"(?<![\w.,$€£¥])[-−]({AMT})({SP}?)({SIGN})(?![\w$])")), &t, r"menos \1\2\3");
    c.sub_tpl(&rx(&format!(r"(?<![\w$])({SIGN})({SP}?)[-−]({AMT})(?!\w|[.,]\d)")), &t, r"menos \1\2\3")
}

// ------------------------------------------------------------------------------------------------ per-unit prices

fn pt_per_unit(t: String, c: &mut Ctx) -> String {
    let scale = format!(r"(?:{SP}+(?:mil|milhão|milhões|mi|bilhão|bilhões|bi))?");
    let amount = format!(r"(?:(?:{SIGN}){SP}?{AMT}{scale}|{AMT}{scale}{SP}?(?:{SIGN}))");
    c.sub(&rx(&format!(r"(?<![\w.,$])({amount})/([^\W\d_]+[²³]?)(?![\w/²³])")), &t, |m| {
        let one = words(&format!("1 {}", g(m, 2)), "pt");
        let rest = one.strip_prefix("um ").or_else(|| one.strip_prefix("uma "))?;
        full(&format!("{LETTER}+(?: {LETTER}+)*"), rest).then(|| format!("{} por {rest}", g(m, 1)))
    })
}

fn amount(n: &str, cents: &str) -> Option<String> {
    let n2 = n.replace('.', "");
    if cents == "00" {
        return Some(n2);
    }
    (n2 != n).then(|| format!("{n2},{cents}"))
}

fn pt_money_cents(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w$])({SYMBOLS})({SP}?)({INTEGER}),(\d{{1,2}})(?!\w|[.,]\d)")), &t, |m| {
        amount(g(m, 3), g(m, 4)).map(|a| format!("{}{}{a}", g(m, 1), g(m, 2)))
    });
    c.sub(&rx(&format!(r"(?<![\w.,])({INTEGER}),(\d{{1,2}})({SP}?(?:{SYMBOLS}))(?![\w$])")), &t, |m| {
        amount(g(m, 1), g(m, 2)).map(|a| format!("{a}{}", g(m, 3)))
    })
}

fn pt_money_scale(t: String, c: &mut Ctx) -> String {
    let mut keys: Vec<&str> = SCALES.iter().map(|s| s.0).collect();
    keys.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    let alt = keys.join("|");
    let re = rx(&format!(r"(?<![\w$])({SYMBOLS}){SP}?(\d+(?:,\d+)?){SP}+({alt})(?!\w)"));
    c.sub(&re, &t, |m| {
        let (sym, num, scale) = (g(m, 1), g(m, 2), g(m, 3));
        let (_, one, many) = SCALES.iter().find(|s| s.0 == scale)?;
        // mi, bi, tri: by the number
        let word = if scale.chars().count() > 3 {
            scale
        } else if num == "1" {
            one
        } else {
            many
        };
        let cur = CURRENCY_NAMES.iter().find(|x| x.0 == sym)?.2;
        Some(if word == "mil" { format!("{num} {word} {cur}") } else { format!("{num} {word} de {cur}") })
    })
}

// ------------------------------------------------------------------------------------------------ units

const FEM_UNITS: &[&str] = &["t", "cal", "kcal", "rpm", "mph"];
/// Unit symbols the grammar leaves as written: symbol, singular, plural, feminine.
const MORE_UNITS: &[(&str, &str, &str, bool)] = &[
    ("GB", "gigabyte", "gigabytes", false),
    ("MB", "megabyte", "megabytes", false),
    ("TB", "terabyte", "terabytes", false),
    ("KB", "quilobyte", "quilobytes", false),
    ("kB", "quilobyte", "quilobytes", false),
    ("Mbps", "megabit por segundo", "megabits por segundo", false),
    ("Gbps", "gigabit por segundo", "gigabits por segundo", false),
    ("lb", "libra", "libras", true),
    ("lbs", "libra", "libras", true),
    ("oz", "onça", "onças", true),
    ("dB", "decibel", "decibéis", false),
    ("µg", "micrograma", "microgramas", false),
    ("μg", "micrograma", "microgramas", false),
    ("mcg", "micrograma", "microgramas", false),
];

fn pt_units(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w.,])(\d+(?:[.,]\d+)*){SP}?km/h(?!\w)")), &t, |m| {
        let n = g(m, 1);
        Some(format!("{n}{}", if n == "1" { " quilômetro por hora" } else { " quilômetros por hora" }))
    });
    let mut units: Vec<&str> = FEM_UNITS.to_vec();
    units.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    let alt = units.join("|");
    let t = c.sub(&rx(&format!(r"{NUM_BEFORE}({NUM})({SP}?)({alt})(?![\w/])")), &t, |m| {
        let (num, unit) = (g(m, 1), g(m, 3));
        let base = words(num, "pt");
        let whole = words(&format!("{num} {unit}"), "pt");
        let fem = feminine(&base);
        if fem == base || !whole.starts_with(&format!("{base} ")) {
            return None;
        }
        Some(format!("{}{}", feminine(&with_e(num, &base)), &whole[base.len()..]))
    });
    let mut more: Vec<&str> = MORE_UNITS.iter().map(|u| u.0).collect();
    more.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    let alt = more.join("|");
    c.sub(&rx(&format!(r"(?<![\w.,\-–~])([-−]?)({INTEGER})(?:,(\d+))?{SP}?({alt})(?![\w/²³])")), &t, |m| {
        let (minus, num, dec) = (g(m, 1), g(m, 2), g(m, 3));
        let &(_, one, many, fem) = MORE_UNITS.iter().find(|u| u.0 == g(m, 4))?;
        let w = if m.get(3).is_some() {
            words(&format!("{num},{dec}"), "pt")
        } else {
            let w = with_e(num, &words(num, "pt"));
            if fem { feminine(&w) } else { w }
        };
        let unit = if num == "1" && m.get(3).is_none() {
            one.to_string()
        } else if BIG.contains(&w.split(' ').next_back().unwrap_or("")) {
            format!("de {many}")
        } else {
            many.to_string()
        };
        Some(format!("{}{w} {unit}", if minus.is_empty() { "" } else { "menos " }))
    })
}

// ------------------------------------------------------------------------------------------------ round millions

/// A whole number of millions as written (2.000.000, 3.500.000.000, 2000000; no leading zero); its reading decides.
const ROUND: &str = r"(?:[1-9]\d{0,2}(?:\.\d{3})*\.000\.000|[1-9]\d{0,8}000000)(?![\w%°ºª'’]|[.,:/\-–]\d)";
const SCALE_WORDS: &str = "milhão|milhões|bilhão|bilhões|trilhão|trilhões|quatrilhão|quatrilhões";
/// Lower-case plural words after a round million that are not what it counts.
const SCALE_NOT_COUNTED: &str = "
mais menos depois antes através atrás apenas pois então após jamais demais os as dos das nos nas pelos pelas aos às
uns umas outros outras todos todas ambos ambas estes estas esses essas aqueles aquelas muitos muitas poucos poucas
vários várias alguns algumas nenhuns nenhumas certos certas tantos tantas quantos quantas nós vós eles elas vocês
seus suas meus minhas teus tuas nossos nossas vossos vossas dois duas três seis dezesseis dezasseis somos estamos
temos vamos podemos fomos éramos és estás tens podes fazes vais dás sabes queres deves dizes anuais mensais semanais
diários diárias trimestrais adicionais restantes líquidos brutos totais iniciais extras exatos grátis
previstos previstas dispostos propostos primeiros primeiras últimos últimas
";
/// -ados/-idos words that are counted nouns (“2.000.000 desabrigados”).
const PARTICIPLE_NOUNS: &str = "
soldados estados empregados deputados aliados afiliados advogados aposentados desalojados desabrigados refugiados
deslocados infectados contaminados vacinados afetados feridos detidos desaparecidos partidos vestidos apelidos pedidos
sentidos ruídos maridos cunhados mercados resultados dados lados pecados prados telhados condados punhados cuidados
legados delegados graduados convidados assalariados entrevistados associados assinados
";
static SCALE_NOT_COUNTED_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(SCALE_NOT_COUNTED));
static PARTICIPLE_NOUNS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(PARTICIPLE_NOUNS));

/// The grammar's words for a round million (“dois milhões”), or None when they do not end in milhão, milhões,
/// bilhão, bilhões… (prototype `scale_head`).
fn scale_head(num: &str) -> Option<String> {
    let w = words(num, "pt");
    BIG.contains(&w.split(' ').next_back().unwrap_or("")).then_some(w)
}

/// What the grammar read after the number's words in `spoken` (“dois milhões quilômetros” → “quilômetros”); a “de”
/// the grammar wrote itself is dropped (prototype `counted`).
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
    if SCALE_NOT_COUNTED_SET.contains(w) || DETERMINERS_SET.contains(w) {
        return false;
    }
    PARTICIPLE_NOUNS_SET.contains(w) || !(w.ends_with("ados") || w.ends_with("idos"))
}

/// The first word of `rest` ends in -s (the counted thing is plural).
fn plural_first(rest: &str) -> bool {
    rest.split(' ').next().unwrap_or("").ends_with('s')
}

fn pt_scale_de(t: String, c: &mut Ctx) -> String {
    // 2.000.000 de €
    let re = rx(&format!(r"{NUM_BEFORE}({ROUND}){SP}+de{SP}+(R\$|US\$|€|£|\$)(?![\w$€£/]|{SP}*\d)"));
    let t = c.sub(&re, &t, |m| {
        let rest = counted(&scale_head(g(m, 1))?, &words(&format!("{} {}", g(m, 1), g(m, 2)), "pt"))?;
        (!rest.is_empty() && plural_first(&rest)).then(|| format!("{} de {rest}", g(m, 1)))
    });
    // 2 milhões de €, 2 milhões €
    let re = rx(&format!(r"(?<!\w)({SCALE_WORDS}){SP}+(?:de{SP}+)?(R\$|US\$|€|£|\$)(?![\w$€£/]|{SP}*\d)"));
    let t = c.sub(&re, &t, |m| {
        let cur = CURRENCY_NAMES.iter().find(|x| x.0 == g(m, 2))?.2;
        Some(format!("{} de {cur}", g(m, 1)))
    });
    // 2.000.000 pessoas, 2.000.000 km
    c.sub(
        &rx(&format!(r"{NUM_BEFORE}({ROUND})({SP}+)([^\W\d_]+(?:[²³]|/[^\W\d_]+)?)(?![\w/²³'’\-]|{SP}*\d)")),
        &t,
        |m| {
            let (num, tok) = (g(m, 1), g(m, 3));
            let rest = counted(&scale_head(num)?, &words(&format!("{num} {tok}"), "pt"))?;
            if rest == tok {
                return counted_noun(tok).then(|| format!("{num} de {tok}"));
            }
            plural_first(&rest).then(|| format!("{num} de {rest}"))
        },
    )
}

// ------------------------------------------------------------------------------------------------ ranges, scores

fn pt_range(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"(?<![\w.,/:\-–])(?:([Ee]ntre){SP}+)?(\d{{1,3}}){SP}?[-–]{SP}?(\d{{1,3}})(?={SP}+(?!de\b|do\b|da\b){LETTER})"
    ));
    c.sub(&re, &t, |m| {
        let (prep, a, b) = (m.get(1).map(|x| x.as_str()), g(m, 2), g(m, 3));
        if py_int(a) >= py_int(b) {
            return None;
        }
        Some(match prep {
            Some(p) => format!("{p} {a} e {b}"),
            None => format!("{a} a {b}"),
        })
    })
}

fn pt_score(t: String, c: &mut Ctx) -> String {
    let cue = r"(?i:venceu|vence|venceram|vencendo|ganhou|ganha|ganharam|ganhando|perdeu|perde|perderam|perdendo|empatou|empatam|empataram|empate|derrotou|derrotaram|bateu|bateram|goleou|goleada|placar|vitória|derrota|jogo|partida|final|terminou|acabou)";
    let re = rx(&format!(
        r"(?<!\w)({cue}(?:{SP}+{LETTER}+){{0,3}}{SP}+)(\d{{1,2}}){SP}?[xX×]{SP}?(\d{{1,2}})(?![\w.,]\w|\w)"
    ));
    c.sub(&re, &t, |m| Some(format!("{}{} a {}", g(m, 1), g(m, 2), g(m, 3))))
}

// ------------------------------------------------------------------------------------------------ halves

const HALF_UNITS: &[&str] = &["kg", "g", "l", "h", "km", "m", "ml", "t", "cm"];
const HALF_FUNCTION: &[&str] = &["de", "do", "da", "dos", "das", "e", "ou", "a", "em", "por", "para", "com"];
/// Masculine measures a fraction is taken of (feminine ones come from the noun table).
const MEASURE_WORDS: &str =
    "copo copos quilo quilos litro litros pacote pacotes tablete tabletes pedaço pedaços prato pratos
dente dentes punhado punhados metro metros grama gramas mililitro mililitros";
static MEASURE_WORDS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| set(MEASURE_WORDS));

fn pt_half(t: String, c: &mut Ctx) -> String {
    let mut units: Vec<&str> = HALF_UNITS.to_vec();
    units.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    let units = units.join("|");
    let t = c.sub(&rx(&format!(r"(?<![\w.,/:\-])(?:(\d+){SP}+)?1/2(?![\d/]){SP}?({units})(?![\w/])")), &t, |m| {
        let (whole, unit) = (g(m, 1), g(m, 2));
        let one = words(&format!("1 {unit}"), "pt");
        let (art, rest) = one.split_once(' ')?;
        if art != "um" && art != "uma" {
            return None;
        }
        let fem = art == "uma" || noun_gender(rest.split(' ').next().unwrap_or("")) == "f";
        if whole.is_empty() {
            return Some(format!("{}{rest}", if fem { "meia " } else { "meio " }));
        }
        let (base, whole_w) = (words(whole, "pt"), words(&format!("{whole} {unit}"), "pt"));
        for prefix in [base.clone(), feminine(&base)] {
            if whole_w.starts_with(&format!("{prefix} ")) {
                let number = if fem { feminine(&base) } else { base.clone() };
                return Some(format!(
                    "{number}{}{}",
                    &whole_w[prefix.len()..],
                    if fem { " e meia" } else { " e meio" }
                ));
            }
        }
        None
    });
    let t = c.sub(&rx(&format!(r"(?<![\w.,/:\-])(?:(\d+){SP}+)?1/2(?![\d/])({SP}+)({LETTER}+)")), &t, |m| {
        let (whole, sp, word) = (g(m, 1), g(m, 2), g(m, 3));
        if HALF_FUNCTION.contains(&lower(word).as_str()) || HALF_UNITS.contains(&word) {
            return None;
        }
        let gender = noun_gender(word);
        if gender != "f" && !MEASURE_WORDS_SET.contains(lower(word).as_str()) {
            return None; // only before a noun the tables know
        }
        let half = if gender == "f" { "meia" } else { "meio" };
        if whole.is_empty() {
            return Some(format!("{half}{sp}{word}"));
        }
        if whole == "1" {
            if !search(r"[aeiouáéó]s$", word) {
                return None;
            }
            let mut cs: Vec<char> = word.chars().collect();
            cs.pop();
            return Some(format!("1 {} e {half}", cs.into_iter().collect::<String>()));
        }
        Some(format!("{whole} {word} e {half}"))
    });
    c.sub(&rx(&format!(r"(?<![\w.,/:\-])(\d+)/(\d+)(?![\d/])({SP}+)({LETTER}+)")), &t, |m| {
        let (a, b, word) = (py_int(g(m, 1)), py_int(g(m, 2)), g(m, 4));
        if !(0 < a && a < b && b <= 16) || (a, b) == (1, 2) {
            return None;
        }
        if noun_gender(word) != "f" && !MEASURE_WORDS_SET.contains(lower(word).as_str()) {
            return None;
        }
        Some(format!("{}/{} de {word}", g(m, 1), g(m, 2)))
    })
}

// ------------------------------------------------------------------------------------------------ gender

fn pt_hour_article(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r#"(?<!\w)((?:[Àà]s?|[Dd]as|[Pp]elas?|[Aa]té{SP}+(?:às|as)|[Aa]pós{SP}+(?:às|as)|[Ee]ntre{SP}+as){SP}+)(\d{{1,2}})(?![\w%°ºª'’]|[.,:/\-–]\w)(?={SP}*(?:[.,;:!?)\]»”"…\n]|$)|{SP}+(?:e|da|de|do|em|até|ou|às|as|a)(?!\w))"#
    ));
    c.sub(&re, &t, |m| {
        if py_int(g(m, 2)) > 24 {
            return None;
        }
        let w = words(g(m, 2), "pt");
        let fem = feminine(&w);
        (fem != w).then(|| format!("{}{fem}", g(m, 1)))
    })
}

static YEAR_CUE: LazyLock<String> =
    LazyLock::new(|| format!(r"(?<!\w)(?i:(?:em|de|do|desde|até|ano|para|antes|depois|durante|o){SP}+)$"));
static DATE_BEFORE: LazyLock<String> = LazyLock::new(|| format!(r"(?<!\w)(?i:{})(?:{SP}+de)?{SP}*$", MONTHS.join("|")));
static CURRENCY_BEFORE: LazyLock<String> = LazyLock::new(|| format!(r"(?:R\$|US\$|€|£|\$|¥){SP}?$"));

fn pt_gender(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r"{NUM_BEFORE}({NUM}(?:{SP}+(?:e|ou|a){SP}+{NUM})*)({SP}+)({LETTER}+)(?!\w|\.{SP}?{LETTER}\.)(?:({SP}+)({LETTER}+)(?!\w))?"
    ));
    c.sub(&re, &t, |m| {
        let m0 = m.get(0).expect("group 0");
        let (chain, w1) = (g(m, 1), g(m, 3));
        let w2 = m.get(5).map(|x| x.as_str());
        let l1 = lower(w1);
        let mut gender = noun_gender(w1);
        if (INVARIANT_ADJ_SET.contains(l1.as_str()) || w1 == "mil") && w2.is_some() {
            gender = noun_gender(w2.unwrap_or(""));
        } else if (l1 == "de" || l1 == "das")
            && w2.is_some_and(|w| ["elas", "estas", "essas", "aquelas"].contains(&lower(w).as_str()))
        {
            gender = "f";
        }
        if gender != "f" {
            return None;
        }
        let before = chars_before(&t, m0.start(), 24); // the words just before the number
        if search(&CURRENCY_BEFORE, before) || search(&DATE_BEFORE, before) {
            return None;
        }
        let num_re = rx(r"\d{1,3}(?:\.\d{3})+|\d+");
        let nums: Vec<&str> = num_re.find_iter(chain).flatten().map(|x| x.as_str()).collect();
        if nums.iter().any(|x| x.starts_with('0') && *x != "0") {
            return None;
        }
        if full(r"1\d{3}|20\d{2}", chain) && search(&YEAR_CUE, before) {
            return None;
        }
        let new_chain = sub_plain(&num_re, chain, |x| {
            let w = words(&x[0], "pt");
            let new = if w1 == "mil" {
                let f = feminine(&format!("{w} mil"));
                f[..f.len() - 4].to_string() // 2 mil pessoas: duas mil
            } else {
                feminine(&with_e(&x[0], &w))
            };
            Some(if new != w { new } else { x[0].to_string() })
        });
        (new_chain != chain).then(|| format!("{new_chain}{}", &m0.as_str()[chain.len()..]))
    })
}

// ------------------------------------------------------------------------------------------------ "e" between groups

static TOKEN: LazyLock<String> = LazyLock::new(|| format!(r"(?:{SIGN}|[^\W\d_]+(?:[²³]|/[^\W\d_]+)?|[°º]C|%)"));

fn pt_scale_e(t: String, c: &mut Ctx) -> String {
    let token = &*TOKEN;
    let re = rx(&format!(
        r"(?<![\w$])({SIGN}){SP}?({BIG_NUM})(?:,\d{{1,2}})?(?!\w|[.,]\d)|{NUM_BEFORE}({BIG_NUM})(?:,\d{{1,2}}(?={SP}?(?:{SIGN})))?(?!\d|[.,]\d)(?:{SP}?{token})?(?![\w/²³'’$€£¥])"
    ));
    c.sub(&re, &t, |m| {
        let m0 = m.get(0).expect("group 0");
        let num = if m.get(2).is_some() { g(m, 2) } else { g(m, 3) };
        if search(&format!(r"(?i)(?<!\w)ip{SP}+$"), chars_before(&t, m0.start(), 4)) {
            return None; // “ip 1.197.000.069” is read digit by digit
        }
        let spoken = words(m0.as_str(), "pt");
        let out = with_e(num, &spoken);
        (out != spoken && full(&format!("{LETTER}+(?: {LETTER}+)*"), &out)).then_some(out)
    })
}

fn pt_sign_punct(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(r"{NUM_BEFORE}({AMT}){SP}({SIGN}|[^\W\d_]{{2,4}}[²³]?|[a-zµμ][²³]?|[°º]C)(?=[^\w\s/])"));
    c.sub(&re, &t, |m| {
        let (num, tok) = (g(m, 1), g(m, 2));
        let spoken = words(&format!("{num} {tok}"), "pt");
        if spoken == format!("{} {tok}", words(num, "pt")) || !full(&format!("{LETTER}+(?: {LETTER}+)*"), &spoken) {
            return None;
        }
        (!(num.contains('.') && spoken.contains(" ponto "))).then_some(spoken) // a dot read as a decimal point
    })
}

// ------------------------------------------------------------------------------------------------ space-grouped numbers

const SPACE_NUM: &str = r"[1-9]\d{0,2}(?:[ \x{A0}\x{202F}]\d{3})+";

fn pt_space_groups(t: String, c: &mut Ctx) -> String {
    let re = rx(&format!(
        r#"(?<![^\s(«“"'‘])((?:R\$|US\$|€|£|\$|¥)[ \t\x{{A0}}]?)?(?<![\w.,])(?<!\d[ \x{{A0}}\x{{202F}}])({SPACE_NUM})(?![ \x{{A0}}\x{{202F}}]?\d|[.,]\d{{3}}|,(?:\d\d|\d(?!\d))[^\s€$£¥])"#
    ));
    c.sub(&re, &t, |m| {
        let m0 = m.get(0).expect("group 0");
        let rest = &t[m0.end()..];
        let ok = m.get(1).is_some()
            || matches_at_start(r"(?:,\d{1,2})?[ \t\x{A0}\x{202F}]?(?:R\$|US\$|€|£|\$|¥)(?!\w)", rest)
            || matches_at_start(r"[ \t\x{A0}\x{202F}]+(?!(?:mil|milhão|milhões|bilhão|bilhões|trilhão|trilhões|mi|bi|tri)(?!\w))[^\W\d_]+(?![\w])", rest)
            || (g(m, 2).ends_with("000") && matches_at_start(r#"(?:\s|$|[.,;:!?)\]»”"…])"#, rest));
        ok.then(|| {
            let dotted: String = g(m, 2).chars().map(|ch| if " \u{a0}\u{202f}".contains(ch) { '.' } else { ch }).collect();
            format!("{}{dotted}", g(m, 1))
        })
    })
}
