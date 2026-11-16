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
    ("pt.money-code", pt_money_code),
    ("pt.money-cents", pt_money_cents),
    ("pt.money-scale", pt_money_scale),
    ("pt.units", pt_units),
    ("pt.range", pt_range),
    ("pt.score", pt_score),
    ("pt.half", pt_half),
    ("pt.hour-article", pt_hour_article),
    ("pt.gender", pt_gender),
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

fn pt_money_code(t: String, c: &mut Ctx) -> String {
    let codes = CODES.iter().map(|(k, _)| *k).collect::<Vec<_>>().join("|");
    let t = c.sub(&rx(&format!(r"(?<![\w.,])(\d+(?:[.,]\d+)*){SP}?({codes})(?!\w)")), &t, |m| {
        Some(format!("{} {}", code_key(g(m, 2)), g(m, 1)))
    });
    let t = c.sub(&rx(&format!(r"(?<!\w)({codes}){SP}?(?=\d)")), &t, |m| Some(format!("{} ", code_key(g(m, 1)))));
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

fn amount(n: &str, cents: &str) -> Option<String> {
    let n2 = n.replace('.', "");
    if cents == "00" {
        return Some(n2);
    }
    (n2 != n).then(|| format!("{n2},{cents}"))
}

fn pt_money_cents(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w$])({SYMBOLS})({SP}?)({INTEGER}),(\d{{2}})(?!\w|[.,]\d)")), &t, |m| {
        amount(g(m, 3), g(m, 4)).map(|a| format!("{}{}{a}", g(m, 1), g(m, 2)))
    });
    c.sub(&rx(&format!(r"(?<![\w.,])({INTEGER}),(\d{{2}})({SP}?€)(?!\w)")), &t, |m| {
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

fn pt_units(t: String, c: &mut Ctx) -> String {
    let t = c.sub(&rx(&format!(r"(?<![\w.,])(\d+(?:[.,]\d+)*){SP}?km/h(?!\w)")), &t, |m| {
        let n = g(m, 1);
        Some(format!("{n}{}", if n == "1" { " quilômetro por hora" } else { " quilômetros por hora" }))
    });
    let mut units: Vec<&str> = FEM_UNITS.to_vec();
    units.sort_by(|a, b| b.chars().count().cmp(&a.chars().count()).then(a.cmp(b)));
    let alt = units.join("|");
    c.sub(&rx(&format!(r"{NUM_BEFORE}({NUM})({SP}?)({alt})(?![\w/])")), &t, |m| {
        let (num, unit) = (g(m, 1), g(m, 3));
        let base = words(num, "pt");
        let whole = words(&format!("{num} {unit}"), "pt");
        let fem = feminine(&base);
        if fem == base || !whole.starts_with(&format!("{base} ")) {
            return None;
        }
        Some(format!("{fem}{}", &whole[base.len()..]))
    })
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
                feminine(&w)
            };
            Some(if new != w { new } else { x[0].to_string() })
        });
        (new_chain != chain).then(|| format!("{new_chain}{}", &m0.as_str()[chain.len()..]))
    })
}
