//! 'fr' rules: the port of the workbench's `langrules/fr.py` (ids `fr.*`).
//!
//! NeMo r1.2.0's French grammar reads cardinals, decimals, ordinals (1er, 2e), numeric dates and fractions, but has
//! no money, time, measure or Roman reading (S30). These rules write those spoken forms themselves, on top of the
//! grammar's own cardinals (`words`), and leave everything else to the grammar.

use std::collections::HashSet;
use std::sync::LazyLock;

use fancy_regex::Captures;

use super::super::{Ctx, chars_before, full, g, matches_at_start, py_int, rx, search};
use super::{LangRule, words};

pub(super) const RULES: &[LangRule] = &[
    ("fr.abbrev", fr_abbrev),
    ("fr.dot-groups", fr_dot_groups),
    ("fr.roman", fr_roman),
    ("fr.ordinal", fr_ordinal),
    ("fr.range", fr_range),
    ("fr.time", fr_time),
    ("fr.money-range", fr_money_range),
    ("fr.per-unit", fr_per_unit),
    ("fr.money", fr_money),
    ("fr.measure", fr_measure),
    ("fr.scale-de", fr_scale_de),
    ("fr.big", fr_big),
    ("fr.fraction", fr_fraction),
    ("fr.gender", fr_gender),
    ("fr.decade", fr_decade),
];

const LETTER: &str = r"[^\W\d_]";
/// Space, no-break space, narrow no-break space (French puts them in numbers and before units).
const SP: &str = " \u{a0}\u{202f}";
const S: &str = "[ \u{a0}\u{202f}]";

fn cat(parts: &[&str]) -> String {
    parts.concat()
}

/// 1 234 567 or 1234567.
static INT: LazyLock<String> = LazyLock::new(|| cat(&[r"\d{1,3}(?:", S, r"\d{3})+|\d+"]));

/// Python's `re.escape` (3.7+): only the regex metacharacters and whitespace get a backslash.
fn esc(s: &str) -> String {
    let mut out = String::new();
    for ch in s.chars() {
        if "()[]{}?*+-|^$\\.&~# \t\n\r\x0b\x0c".contains(ch) {
            out.push('\\');
        }
        out.push(ch);
    }
    out
}

/// `"|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))`.
fn alt(keys: &[&str]) -> String {
    let mut k: Vec<&str> = keys.to_vec();
    k.sort_by_key(|s| std::cmp::Reverse(s.chars().count()));
    k.iter().map(|s| esc(s)).collect::<Vec<_>>().join("|")
}

fn tail(t: &str, i: usize) -> &str {
    chars_before(t, i, 40)
}

fn start(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.start())
}

fn end(m: &Captures<'_, str>) -> usize {
    m.get(0).map_or(0, |x| x.end())
}

fn digits(s: &str) -> String {
    s.chars().filter(|ch| !SP.contains(*ch) && *ch != '.').collect()
}

/// The grammar's reading of '1 234' or '1 234,5' (group spaces and dots dropped); 'cinq cents mille' (a grammar slip)
/// is written 'cinq cent mille'. From 10^12 up the number is composed with billion and billiard (prototype `num`).
fn num(s: &str) -> String {
    let d = digits(s);
    let (i, dec) = d.split_once(',').map_or((d.as_str(), None), |(a, b)| (a, Some(b)));
    let w = if full(r"[1-9][0-9]{12,17}", i) {
        let mut w = big(i);
        if let Some(dec) = dec {
            let frac = words(&format!("0,{dec}"), "fr");
            match frac.strip_prefix("zéro ") {
                Some(rest) => w = format!("{w} {rest}"),
                None => return words(&d, "fr"),
            }
        }
        w
    } else {
        words(&d, "fr")
    };
    w.replace("cents mille", "cent mille").replace("vingts mille", "vingt mille")
}

/// A whole number of 13 to 18 digits: “deux billions”, “un billiard trois cents billions”, then the grammar's words
/// for the rest below 10^12 (prototype `big`).
fn big(i: &str) -> String {
    let mut n = py_int(i);
    let mut parts: Vec<String> = Vec::new();
    for (value, name) in [(10u128.pow(15), "billiard"), (10u128.pow(12), "billion")] {
        let q = n / value;
        n %= value;
        if q != 0 {
            parts.push(format!("{} {name}{}", words(&q.to_string(), "fr"), if q > 1 { "s" } else { "" }));
        }
    }
    if n != 0 {
        parts.push(words(&n.to_string(), "fr"));
    }
    parts.join(" ")
}

/// A reading that takes de/d' before what it counts.
const SCALE_END: &str = r"(?:million|milliard|billion|billiard)s?$";

/// 'vingt et un' -> 'vingt et une': the number before a feminine noun.
fn fem(w: &str) -> String {
    if w == "un" || w.ends_with(" un") || w.ends_with("-un") { format!("{w}e") } else { w.to_string() }
}

fn int_part(s: &str) -> u128 {
    py_int(&digits(s))
}

/// Python's `s[:-1]` for a non-empty string.
fn chop(s: &str) -> &str {
    s.char_indices().next_back().map_or(s, |(i, _)| &s[..i])
}

// ------------------------------------------------------------------------------------------------- feminine nouns

const FEM_WORDS: &str = "page personne heure minute seconde semaine fois place pièce chambre étoile femme fille ville langue lettre
ligne photo étape voiture maison tasse tranche gousse pomme tomate cuillère cuiller bouteille boîte part partie porte
fenêtre table chaise classe école salle rue route nuit voix victoire défaite équipe famille sœur mère tante cousine amie
victime vie fleur feuille branche pierre île montagne plage côte mer terre planète image vidéo chanson chaîne série carte
clé clef note histoire chose manière façon sorte espèce catégorie couleur odeur valeur erreur faute peine douleur maladie
dose pilule gélule goutte tonne calorie kilocalorie centaine dizaine douzaine vingtaine trentaine quarantaine
cinquantaine soixantaine offre demande commande facture dépense taxe somme banque prime amende marche course manche balle
médaille coupe finale épreuve décennie reprise tentative chance vague couche portion ration assiette tablette barre
brique canette caisse palette caméra radio moto auto roue piste colonne case rubrique règle loi norme phrase syllabe
voyelle consonne touche application appli puce pile batterie ampoule lampe prise question réponse œuvre guerre bataille
fête vache poule chèvre souris mouche abeille dent main jambe tête épaule oreille bouche langue joue lèvre vertèbre
côte pomme poire banane orange fraise cerise noix noisette olive carotte salade soupe tarte crêpe gaufre pizza pâte
baguette tartine sauce crème glace bière boisson tasse cuillerée pincée poignée feuille gorgée tranche boule pastille
dose unité livraison commune paroisse province nation région république entreprise société usine boutique pharmacie
agence association université bibliothèque piscine église mosquée synagogue école classe chambre cuisine maison villa
tente cabane";
const FEM_END: &[&str] = &[
    "tion", "sion", "xion", "ité", "ure", "ette", "ence", "ance", "esse", "aison", "ière", "elle", "erie", "ée", "ude",
    "ade", "ine", "ise", "ie",
];
const NOT_FEM_WORDS: &str =
    "comité été côté député traité pâté invité karaté comté velouté doigté aparté mercure murmure parjure
augure cyanure chlorure sulfure fluorure carbure bromure iodure nitrure squelette silence cimetière violoncelle
vermicelle musée lycée trophée mausolée apogée scarabée pygmée prélude stade grade jade bastion magazine platine
domaine capitaine moine génie incendie parapluie sosie messie foie paradis prix pays mois avis repas bras dos tas
bois corps temps poids cas pare-brise";
static FEM: LazyLock<HashSet<&str>> = LazyLock::new(|| FEM_WORDS.split_whitespace().collect());
static NOT_FEM: LazyLock<HashSet<&str>> = LazyLock::new(|| NOT_FEM_WORDS.split_whitespace().collect());

/// A feminine noun (singular or plural): the table, or a feminine ending (-tion, -ité, -ure, -ette…) that is not a
/// listed masculine exception.
fn is_fem(w: &str) -> bool {
    let w = w.to_lowercase();
    let plural = w.chars().count() > 3 && (w.ends_with('s') || w.ends_with('x')) && !FEM.contains(w.as_str());
    let s = if plural { chop(&w) } else { w.as_str() };
    if NOT_FEM.contains(w.as_str()) || NOT_FEM.contains(s) {
        return false;
    }
    FEM.contains(w.as_str()) || FEM.contains(s) || FEM_END.iter().any(|e| s.ends_with(e))
}

// ------------------------------------------------------------------------------------------------- abbreviations

const TITLES: &[(&str, &str)] = &[
    ("Mmes", "Mesdames"),
    ("Mme", "Madame"),
    ("Mlles", "Mesdemoiselles"),
    ("Mlle", "Mademoiselle"),
    ("Mgr", "Monseigneur"),
];
const TITLES_NAME: &[(&str, &str)] = &[
    ("MM.", "Messieurs"),
    ("M.", "Monsieur"),
    ("Dre", "docteure"),
    ("Dr", "docteur"),
    ("Pr", "professeur"),
    ("Ste", "Sainte"),
    ("St", "Saint"),
];
const BEFORE_NUM: &[(&str, &str)] = &[
    ("pp", "pages"),
    ("p", "page"),
    ("chap", "chapitre"),
    ("Chap", "Chapitre"),
    ("art", "article"),
    ("Art", "Article"),
    ("vol", "volume"),
    ("Vol", "Volume"),
    ("env", "environ"),
];

fn sentence_end(rest: &str) -> bool {
    matches_at_start(r"[ \t]*(?:$|\n|[A-ZÀ-Ý])", rest)
}

fn fr_abbrev(t: String, c: &mut Ctx) -> String {
    let mut t = t;
    for (a, w) in TITLES {
        t = c.sub_tpl(&rx(&cat(&[r"(?<![\w.])", &esc(a), r"(?:\.(?=", S, r"+[A-ZÀ-Ý]))?(?![\w-])"])), &t, w);
    }
    for (a, w) in TITLES_NAME {
        let dot = if a.ends_with('.') { "" } else { r"\.?" };
        t = c.sub_tpl(
            &rx(&cat(&[r"(?<![\w.])(?<![A-Z]\. )", &esc(a), dot, r"(?=(?:", S, r"+|-)(?:[A-ZÀ-Ý]|et", S, r"+Mme))"])),
            &t,
            w,
        );
    }
    let t = c.sub(&rx(&cat(&[r"(?<!\w)([nN])[°º](s?)(?=", S, r"*\d)"])), &t, |m| {
        Some(format!("{}uméro{} ", if g(m, 1) == "N" { "N" } else { "n" }, g(m, 2)))
    });
    let t = c.sub_tpl(&rx(&cat(&[r"(?<![\w.])p\.", S, r"?ex(?:\.|(?!\w))"])), &t, "par exemple");
    let t = c.sub_tpl(&rx(r"(?<![\w.])c(?:\.-|\.|-)?à(?:-|\.)?d\.?(?!\w)"), &t, "c'est-à-dire");
    let t = c.sub(&rx(r"(?<![\w.])([cC])f\.(?!\w)"), &t, |m| {
        Some(format!("{}onfer", if g(m, 1) == "C" { "C" } else { "c" }))
    });
    let t = c.sub(&rx(r"(?<![\w.])([tT])él\.(?!\w)"), &t, |m| Some(format!("{}éléphone", g(m, 1))));
    let mut t = c.sub(&rx(r"(?<![\w.])etc\.?(?!\w)"), &t, |m| {
        let keep = g(m, 0).ends_with('.') && sentence_end(&t[end(m)..]);
        Some(if keep { "et cetera." } else { "et cetera" }.to_string())
    });
    for (a, w) in BEFORE_NUM {
        t = c.sub_tpl(&rx(&cat(&[r"(?<![\w.])", a, r"\.(?=", S, r"*(?:\d|[IVXLC]+\b))"])), &t, w);
    }
    let t = c.sub(&rx(&cat(&[r"(?<![\w.])(?i:(av|apr)\.", S, r"?j\.-?c\.)"])), &t, |m| {
        if g(m, 0) == "av. J.-C." || g(m, 0) == "apr. J.-C." {
            return None;
        }
        Some(format!("{} Jésus-Christ", if g(m, 1).to_lowercase() == "av" { "avant" } else { "après" }))
    });
    let t = c.sub_tpl(&rx(&cat(&[r"(?<![\w.])av\.(?=", S, r"+(?![jJ]\.)[\w])"])), &t, "avenue");
    c.sub_tpl(
        &rx(&cat(&[r"(?<=\d", S, r")bd\.?(?=", S, r"+\w)|(?<=\d,", S, r")bd\.?(?=", S, r"+\w)"])),
        &t,
        "boulevard",
    )
}

// ------------------------------------------------------------------------------------------------- ordinal suffixes

/// The ordinal of n: premier/première, then the cardinal + ième (vingt-cinquième, vingt-neuvième, quatre-vingtième).
fn ordinal(n: u128, fem_: bool, plural: bool) -> String {
    let mut w = if n == 1 {
        (if fem_ { "première" } else { "premier" }).to_string()
    } else {
        let mut w = num(&n.to_string());
        if w.ends_with("vingts") || w.ends_with("cents") {
            w = chop(&w).to_string();
        }
        if w.ends_with("cinq") {
            w.push('u');
        } else if w.ends_with("neuf") {
            w = format!("{}v", chop(&w));
        } else if w.ends_with('e') {
            w = chop(&w).to_string();
        }
        w + "ième"
    };
    if plural {
        w.push('s');
    }
    w
}

static FEM_DET: LazyLock<String> =
    LazyLock::new(|| cat(&[r"(?i)(?:^|[^\w])(?:la|une|cette|sa|ma|ta|leur|notre|votre|les|des|ces)", S, r"+$"]));

fn fr_ordinal(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(concat!(
            r"(?<![\w.,])(\d+)(ᵉʳˢ|ʳᵉˢ|ᵉʳ|ʳᵉ|ᵉˢ|ᵉ|ères|eres|ere|res|re|ers|èmes|emes|eme|ème|ès|è|es|e|ndes|nds|nde|nd|",
            r"des|ds|de|d)(?![\w])"
        )),
        &t,
        |m| {
            let (n, suf) = (g(m, 1), g(m, 2));
            let v = py_int(n);
            let one = v == 1 && n.chars().count() == 1;
            let pl = suf.ends_with('s') || suf.ends_with('ˢ');
            let base = if pl { chop(suf) } else { suf };
            if ["re", "ère", "ʳᵉ", "ere"].contains(&base) {
                return one.then(|| (if pl { "premières" } else { "1ère" }).to_string());
            }
            if ["er", "ᵉʳ"].contains(&base) {
                return one.then(|| (if pl { "premiers" } else { "1er" }).to_string());
            }
            if ["nd", "nde", "d", "de"].contains(&base) {
                if n != "2" {
                    return None;
                }
                return Some(format!(
                    "second{}{}",
                    if base.ends_with('e') { "e" } else { "" },
                    if pl { "s" } else { "" }
                ));
            }
            if one {
                return Some(ordinal(1, search(&FEM_DET, tail(&t, start(m))), pl));
            }
            let w = num(n);
            if w.ends_with("vingts")
                || w.ends_with("-quatre")
                || w.ends_with("-cinq")
                || (w.ends_with("-neuf") && !w.ends_with("dix-neuf"))
            {
                return Some(ordinal(v, false, pl));
            }
            if ["e", "es", "ème"].contains(&suf) {
                return None;
            }
            Some(format!("{n}e{}", if pl { "s" } else { "" }))
        },
    )
}

// ------------------------------------------------------------------------------------------------- Roman numerals

const ROMAN: &[(&str, u128)] = &[
    ("M", 1000),
    ("CM", 900),
    ("D", 500),
    ("CD", 400),
    ("C", 100),
    ("XC", 90),
    ("L", 50),
    ("XL", 40),
    ("X", 10),
    ("IX", 9),
    ("V", 5),
    ("IV", 4),
    ("I", 1),
];

/// The value of a well-formed Roman numeral (XIV → 14), or 0.
fn roman(s: &str) -> u128 {
    let (mut n, mut i) = (0u128, 0usize);
    for (sym, v) in ROMAN {
        while s[i..].starts_with(sym) {
            n += v;
            i += sym.len();
        }
    }
    if i != s.len() || n == 0 {
        return 0;
    }
    let (mut back, mut k) = (String::new(), n);
    for (sym, v) in ROMAN {
        while k >= *v {
            back.push_str(sym);
            k -= v;
        }
    }
    if back == s { n } else { 0 }
}

const REGNAL_WORDS: &str =
    "Louis Henri Charles François Philippe Jean Jean-Paul Benoît Pie Léon Grégoire Napoléon Élisabeth Elizabeth
Elisabeth Guillaume Édouard Edouard Richard George Georges Frédéric Alexandre Nicolas Pierre Catherine Paul Innocent
Clément Boniface Urbain Alphonse Ferdinand Isabelle Marie Carlos Felipe Juan Othon Rodolphe Ramsès Ptolémée Antiochus
Hugues Robert Lothaire Childéric Clotaire Dagobert Pépin Sixte Jules Martin Adrien Eugène Honorius Célestin Sylvestre
Étienne Léopold Albert Baudouin Christian Haakon Olaf Gustave Mohammed Hassan Abdallah Constantin Justinien Théodose
Basile Michel Manuel Ivan Vassili Mehmed Mehmet Soliman Sélim Mourad Rainier Jacques Harald Frederik Margrethe Willem
Victor-Emmanuel Humbert Amédée Côme Laurent Charles-Quint Wenceslas Casimir Sigismond Ladislas Béla Venceslas Thoutmôsis
Aménophis Séleucos Anne Jeanne Marguerite Victoria Christine Isabel Juliana Wilhelmine Elizabeth Mathilde Béatrice
Alexis Boris Siméon Michel Constantin Ferdinand Carol Pedro João Manuel Sancho Alfonso Fernando Enrique Afonso";
const FEM_NAME_WORDS: &str = "Élisabeth Elizabeth Elisabeth Catherine Isabelle Marie Anne Jeanne Marguerite Victoria Christine Isabel \
Juliana Wilhelmine Margrethe Mathilde Béatrice";
const NOT_NAME_WORDS: &str = "Le La Les L Un Une Des Du De D Au Aux En Et Ou Où À A Par Pour Sur Dans Avec Sans Sous Entre Vers Chez Ce
Cet Cette Ces Son Sa Ses Mon Ma Mes Ton Ta Tes Notre Votre Nos Vos Leur Leurs Il Elle On Nous Vous Ils Elles Je Tu Qui Que
Quoi Dont Si Mais Car Donc Or Ni Puis Comme Depuis Pendant Avant Après Dès Selon Malgré Voici Voilà Est Sont Était Fut";
static REGNAL: LazyLock<HashSet<&str>> = LazyLock::new(|| REGNAL_WORDS.split_whitespace().collect());
static FEM_NAMES: LazyLock<HashSet<&str>> = LazyLock::new(|| FEM_NAME_WORDS.split_whitespace().collect());
static NOT_NAME: LazyLock<HashSet<&str>> = LazyLock::new(|| NOT_NAME_WORDS.split_whitespace().collect());
const NAME: &str = r"([A-ZÀ-Ý][a-zà-ÿ]+(?:-[A-ZÀ-Ý][a-zà-ÿ]+)*)";

fn fr_roman(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&cat(&[r"(?<![\w-])([IVXLC]+)(ᵉʳ|ʳᵉ|ème|eme|ère|er|re|ᵉ|è|e)(s|ˢ)?(?![\w])(", S, r"s\.(?!\w))?"])),
        &t,
        |m| {
            let (r, suf, pl, sie) = (g(m, 1), g(m, 2), !g(m, 3).is_empty(), !g(m, 4).is_empty());
            let v = roman(r);
            if v == 0 {
                return None;
            }
            let mut out = if ["er", "ᵉʳ", "re", "ʳᵉ", "ère"].contains(&suf) {
                if v != 1 {
                    return None;
                }
                if ["er", "ᵉʳ"].contains(&suf) {
                    (if pl { "premiers" } else { "1er" }).to_string()
                } else {
                    (if pl { "premières" } else { "1ère" }).to_string()
                }
            } else {
                if v == 1 || (r.chars().count() == 1 && !"VX".contains(r)) {
                    return None;
                }
                format!("{v}e{}", if pl { "s" } else { "" })
            };
            if sie {
                out.push_str(if sentence_end(&t[end(m)..]) { " siècle." } else { " siècle" });
            }
            Some(out)
        },
    );
    let t = c.sub(&rx(&cat(&[r"(?<![\w-])([IVXLC]+)(?=", S, r"+siècles?\b)"])), &t, |m| {
        let v = roman(g(m, 1));
        (v != 0).then(|| if v > 1 { format!("{v}e") } else { "1er".to_string() })
    });
    c.sub(&rx(&cat(&[r"(?<![\w-])", NAME, S, r"+([IVXLC]+)(?![\w'’-])"])), &t, |m| {
        let (name, r) = (g(m, 1), g(m, 2));
        let v = roman(r);
        if v == 0 || NOT_NAME.contains(name) {
            return None;
        }
        if !REGNAL.contains(name) && (r.chars().count() < 2 || !full(r"[IVX]+", r)) {
            return None;
        }
        if v == 1 {
            return Some(format!("{name}{}", if FEM_NAMES.contains(name) { " première" } else { " premier" }));
        }
        Some(format!("{name} {}", num(&v.to_string())))
    })
}

// ------------------------------------------------------------------------------------------------- ranges

const SCORE_CUE: &str = concat!(
    r"(?i)\b(?:victoire|défaite|match|nul|gagn\w*|perd\w*|battu\w*|bat|battent|impos\w*|emport\w*|score|",
    r"men\w*|mi-temps|vainqueur|vaincu\w*|finale|set|sets|résultat)\b"
);

fn fr_range(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[r"(?<![\w.,/:-])(\d{1,4})(?:-|", S, r"?–", S, r"?)(\d{1,4})(?![\w/:-]|[.,]\d|", S, r"*[=+×*/])"])),
        &t,
        |m| {
            let (a, b) = (g(m, 1), g(m, 2));
            let (la, lb) = (a.chars().count(), b.chars().count());
            if (la > 1 && a.starts_with('0')) || (lb > 1 && b.starts_with('0')) || (la == 3 && lb == 4) {
                return None;
            }
            let before = tail(&t, start(m));
            if before.ends_with(") ") {
                return None;
            }
            let (ia, ib) = (py_int(a), py_int(b));
            if ia >= ib && !(la <= 2 && lb <= 2 && search(SCORE_CUE, before)) {
                return None;
            }
            if search(&cat(&[r"(?i)\b(?:le|du|au|ce)", S, r"$"]), before) && ia <= 31 && (1..=12).contains(&ib) {
                return None;
            }
            if search(&cat(&[r"(?i)\bentre", S, r"$"]), before) {
                return Some(format!("{a} et {b}"));
            }
            Some(format!("{a} à {b}"))
        },
    )
}

// ------------------------------------------------------------------------------------------------- clock times

fn hours(h: u128) -> String {
    format!(
        "{}{}",
        if h == 0 { "zéro".to_string() } else { fem(&num(&h.to_string())) },
        if h <= 1 { " heure" } else { " heures" }
    )
}

fn minutes(mm: &str, unit: bool) -> String {
    let v = py_int(mm);
    if v == 0 {
        return String::new();
    }
    let u = if unit { if v == 1 { " minute" } else { " minutes" } } else { "" };
    format!(" {}{u}", fem(&num(&v.to_string())))
}

static HM: LazyLock<String> =
    LazyLock::new(|| cat(&[r"(\d{1,2})", S, r"?[hH](?:", S, r"?([0-5]\d)(?!\d))?(", S, r"?(?:min|mn)(?!\w))?"]));

/// `m.group(i) or default`.
fn or<'a>(s: &'a str, default: &'a str) -> &'a str {
    if s.is_empty() { default } else { s }
}

fn fr_time(t: String, c: &mut Ctx) -> String {
    let t =
        c.sub(&rx(&cat(&[r"(?<![\w.,/])(\d{1,2})", S, r"?([hHj])", S, r"?/", S, r"?(\d{1,2})(?![\w/])"])), &t, |m| {
            let (n, u, d) = (g(m, 1), g(m, 2), g(m, 3));
            if "hH".contains(u) {
                return Some(format!("{} sur {}", hours(py_int(n)), num(d)));
            }
            Some(format!("{}{} sur {}", num(n), if py_int(n) <= 1 { " jour" } else { " jours" }, num(d)))
        });
    let t =
        c.sub(&rx(&cat(&[r"(?<![\w.,:/-])", &HM, r"(?:", S, r"?[-–à]", S, r"?", &HM, r")?(?![\w/])"])), &t, |m| {
            let mut out = hours(py_int(g(m, 1))) + &minutes(or(g(m, 2), "0"), !g(m, 3).is_empty());
            if !g(m, 4).is_empty() {
                out += &format!(" à {}{}", hours(py_int(g(m, 4))), minutes(or(g(m, 5), "0"), !g(m, 6).is_empty()));
            }
            Some(out)
        });
    c.sub(
        &rx(&cat(&[
            r"(?<![\w.,:/-])(\d{1,2}):([0-5]\d)(?:",
            S,
            r"?[-–]",
            S,
            r"?(\d{1,2}):([0-5]\d))?(?![\w:]|[.,]\d)",
        ])),
        &t,
        |m| {
            let h = py_int(g(m, 1));
            if h > 23
                || (g(m, 1).chars().count() == 1 && search(&cat(&[r"[A-ZÀ-Ý][\w-]*", S, r"$"]), tail(&t, start(m))))
            {
                return None;
            }
            let mut out = hours(h) + &minutes(g(m, 2), false);
            if !g(m, 3).is_empty() {
                if py_int(g(m, 3)) > 23 {
                    return None;
                }
                out += &format!(" à {}{}", hours(py_int(g(m, 3))), minutes(g(m, 4), false));
            }
            Some(out)
        },
    )
}

// ------------------------------------------------------------------------------------------------- money

/// (written forms, singular, plural, feminine, minor singular, minor plural).
type Currency = (&'static [&'static str], &'static str, &'static str, bool, &'static str, &'static str);
const CURRENCIES: &[Currency] = &[
    (&["€", "EUR", "euros", "euro"], "euro", "euros", false, "centime", "centimes"),
    (&["US$", "$", "USD", "dollars", "dollar"], "dollar", "dollars", false, "cent", "cents"),
    (&["£", "GBP"], "livre sterling", "livres sterling", true, "penny", "pence"),
    (&["CHF"], "franc suisse", "francs suisses", false, "centime", "centimes"),
    (&["¥", "JPY"], "yen", "yens", false, "", ""),
    (&["FCFA", "XOF", "XAF"], "franc CFA", "francs CFA", false, "", ""),
    (&["CAD"], "dollar canadien", "dollars canadiens", false, "cent", "cents"),
    (&["MAD", "DH"], "dirham", "dirhams", false, "centime", "centimes"),
    (&["DZD"], "dinar algérien", "dinars algériens", false, "centime", "centimes"),
    (&["TND"], "dinar tunisien", "dinars tunisiens", false, "", ""),
];
static CUR_FORMS: LazyLock<Vec<&str>> = LazyLock::new(|| CURRENCIES.iter().flat_map(|c| c.0.iter().copied()).collect());
/// The signs and codes that may also stand before the amount (`not f.islower()`).
static CUR_SIGNS: LazyLock<Vec<&str>> =
    LazyLock::new(|| CUR_FORMS.iter().copied().filter(|f| !f.chars().any(char::is_lowercase)).collect());

fn cur_of(f: &str) -> &'static Currency {
    CURRENCIES.iter().find(|c| c.0.contains(&f)).expect("currency form")
}

static CUR_ALT: LazyLock<String> = LazyLock::new(|| alt(&CUR_FORMS));
static CUR_SIGN: LazyLock<String> = LazyLock::new(|| alt(&CUR_SIGNS));
const SCALES: &[(&str, &str)] = &[
    ("Mds", "milliard"),
    ("Mrds", "milliard"),
    ("Mrd", "milliard"),
    ("Md", "milliard"),
    ("M", "million"),
    ("milliards", "milliard"),
    ("milliard", "milliard"),
    ("millions", "million"),
    ("million", "million"),
    ("billions", "billion"),
    ("billion", "billion"),
    ("billiards", "billiard"),
    ("billiard", "billiard"),
    ("trillions", "trillion"),
    ("trillion", "trillion"),
    ("k", "mille"),
    ("K", "mille"),
];
static SCALE_ALT: LazyLock<String> = LazyLock::new(|| alt(&SCALES.iter().map(|s| s.0).collect::<Vec<_>>()));
static AMT: LazyLock<String> =
    LazyLock::new(|| cat(&[r"(-?)(\d{1,3}(?:[", SP, r".]\d{3})+|\d+)(?:,(\d{1,2})(?!\d)|\.(\d{2})(?!\d))?"]));

/// AMT without its groups.
static AMOUNT: LazyLock<String> = LazyLock::new(|| cat(&[r"(?:\d{1,3}(?:[", SP, r".]\d{3})+|\d+)(?:,\d{1,2})?"]));

/// An amount as written (“1 200”, “2,5”, “7,50”) in cents, to compare the two ends of a range.
fn cents_of(a: &str) -> u128 {
    let (i, d) = a.split_once(',').unwrap_or((a, ""));
    let dv = if d.is_empty() { 0 } else { py_int(&format!("{d}0")[..2]) };
    py_int(&digits(i)).saturating_mul(100).saturating_add(dv)
}

fn joined(p: &str, first: &str, last: &str) -> String {
    if p.is_empty() { format!("{first} à {last}") } else { format!("{p} {first} et {last}") }
}

fn fr_money_range(t: String, c: &mut Ctx) -> String {
    let t = c.sub_tpl(&rx(&cat(&[r"(?<![\w.,])[-−](", &CUR_SIGN, r")(", S, r"?)(?=\d)"])), &t, r"\1\2-");
    let prep = cat(&[r"(?:([Ee]ntre)", S, r"+)?"]);
    let t = c.sub(
        &rx(&cat(&[
            r"(?<![\w.,$€£¥])",
            &prep,
            r"(",
            &CUR_SIGN,
            r")",
            S,
            r"?(",
            &AMOUNT,
            r")",
            S,
            r"?[-–~]",
            S,
            r"?(?:(",
            &CUR_SIGN,
            r")",
            S,
            r"?)?(",
            &AMOUNT,
            r")(?![\w]|[.,]\d)",
        ])),
        &t,
        |m| {
            let (p, s, a, s2, b) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5));
            if (!s2.is_empty() && s2 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            let first = if a.contains(',') { format!("{a} {s}") } else { a.to_string() };
            Some(joined(p, &first, &format!("{b} {s}")))
        },
    );
    c.sub(
        &rx(&cat(&[
            r"(?<![\w.,])",
            &prep,
            r"(",
            &AMOUNT,
            r")(?:",
            S,
            r"?(",
            &CUR_ALT,
            r"))?",
            S,
            r"?[-–~]",
            S,
            r"?(",
            &AMOUNT,
            r")(",
            S,
            r"?)(",
            &CUR_ALT,
            r")(?![\w$€£¥])",
        ])),
        &t,
        |m| {
            let (p, a, s1, b, sp, s) = (g(m, 1), g(m, 2), g(m, 3), g(m, 4), g(m, 5), g(m, 6));
            if (!s1.is_empty() && s1 != s) || cents_of(a) >= cents_of(b) {
                return None;
            }
            let first = if a.contains(',') { format!("{a}{sp}{s}") } else { a.to_string() };
            Some(joined(p, &first, &format!("{b}{sp}{s}")))
        },
    )
}

fn fr_per_unit(t: String, c: &mut Ctx) -> String {
    let amount = cat(&[r"(?:(?:", &CUR_SIGN, r")", S, r"?", &AMOUNT, r"|", &AMOUNT, S, r"?(?:", &CUR_ALT, r"))"]);
    c.sub(&rx(&cat(&[r"(?<![\w.,$€£¥])(", &amount, r")/([^\W\d_]+[²³]?)(?![\w/²³])"])), &t, |m| {
        let tok = g(m, 2);
        if let Some(u) = UNITS.iter().find(|x| x.0 == tok) {
            return Some(format!("{} par {}", g(m, 1), u.1));
        }
        full(r"[a-zà-ÿœæ]+", tok).then(|| format!("{} par {tok}", g(m, 1)))
    })
}

/// Nouns with an aspirated h: no elision before them (de hertz, de héros).
const H_ASPIRE: &str =
    "hertz héros haricots hamburgers handicapés hiboux homards hérissons hangars harengs hameaux hauts
hasards haches harpes halls hockeyeurs hublots huttes hamacs hamsters harkis";
static H_ASPIRE_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| H_ASPIRE.split_whitespace().collect());

/// “de” or “d'” before a counted noun: d'euros, d'habitants, de personnes, de hertz.
fn de(plural: &str) -> String {
    let first = plural.split(' ').next().unwrap_or("");
    let c0 = plural.chars().next().unwrap_or(' ');
    let elide = "aeiouéèêëàâîïôûœæh".contains(c0) && !H_ASPIRE_SET.contains(first);
    format!("{}{plural}", if elide { "d'" } else { "de " })
}

fn money(sign: &str, i: &str, cents: &str, scale: &str, cur: &Currency) -> Option<String> {
    let (_, sg, pl, f, msg, mpl) = *cur;
    let lead = if sign.is_empty() { "" } else { "moins " };
    if !scale.is_empty() {
        let sc = SCALES.iter().find(|(k, _)| *k == scale).map(|(_, w)| *w).expect("scale");
        if sc == "mille" {
            let d = digits(i);
            if d.chars().count() > 15 {
                return None;
            }
            let extra = if cents.is_empty() { 0 } else { py_int(&format!("{cents:0<3}")) };
            let v = num(&(py_int(&d) * 1000 + extra).to_string());
            let v = if f { fem(&v) } else { v };
            return Some(format!("{lead}{v} {}", if py_int(&d) != 0 || !cents.is_empty() { pl } else { sg }));
        }
        let n = num(&if cents.is_empty() { i.to_string() } else { format!("{i},{cents}") });
        return Some(format!("{lead}{n} {sc}{} {}", if int_part(i) >= 2 { "s" } else { "" }, de(pl)));
    }
    let n = int_part(i);
    let w = num(i);
    let w = if f { fem(&w) } else { w };
    let cv = if cents.is_empty() { 0 } else { py_int(&format!("{cents:0<2}")) };
    if n == 0 && cv != 0 && !msg.is_empty() {
        let cw = num(&cv.to_string());
        return Some(format!("{lead}{cw} {}", if cv == 1 { msg } else { mpl }));
    }
    let major = if search(SCALE_END, &w) { de(pl) } else { (if n <= 1 { sg } else { pl }).to_string() };
    let mut out = format!("{lead}{w} {major}");
    if cv != 0 {
        out += &format!(" {}", num(&cv.to_string()));
    }
    Some(out)
}

fn fr_money(t: String, c: &mut Ctx) -> String {
    let t = c.sub(
        &rx(&cat(&[
            r"(?<![\w.,])",
            &AMT,
            r"(?:",
            S,
            r"?(",
            &SCALE_ALT,
            r"))?",
            S,
            r"?(",
            &CUR_ALT,
            r")(?:(?<=[€$£¥])(\d{2})(?!\d))?(?![\w$€£¥])",
        ])),
        &t,
        |m| {
            // the words euros/dollars are already read by the grammar; only cents or a scale need us
            if !CUR_SIGNS.contains(&g(m, 6)) && g(m, 3).is_empty() && g(m, 4).is_empty() && g(m, 5).is_empty() {
                return None;
            }
            let cents = or(g(m, 3), or(g(m, 4), g(m, 7)));
            money(g(m, 1), g(m, 2), cents, g(m, 5), cur_of(g(m, 6)))
        },
    );
    c.sub(
        &rx(&cat(&[
            r"(?<![\w.,$€£¥])(",
            &CUR_SIGN,
            r")",
            S,
            r"?",
            &AMT,
            r"(?:",
            S,
            r"?(",
            &SCALE_ALT,
            r"))?(?![\w,.]\d|\d|",
            S,
            r"?(?:",
            &CUR_ALT,
            r")(?!\w))",
        ])),
        &t,
        |m| money(g(m, 2), g(m, 3), or(g(m, 4), g(m, 5)), g(m, 6), cur_of(g(m, 1))),
    )
}

// ------------------------------------------------------------------------------------------------- measures

/// (abbreviation, singular, plural, feminine); data/fr/measures/measurements.tsv plus the common ones.
const UNITS: &[(&str, &str, &str, bool)] = &[
    ("km/h", "kilomètre heure", "kilomètres heure", false),
    ("m/s", "mètre par seconde", "mètres par seconde", false),
    ("Mbit/s", "mégabit par seconde", "mégabits par seconde", false),
    ("Mb/s", "mégabit par seconde", "mégabits par seconde", false),
    ("Gbit/s", "gigabit par seconde", "gigabits par seconde", false),
    ("km²", "kilomètre carré", "kilomètres carrés", false),
    ("km2", "kilomètre carré", "kilomètres carrés", false),
    ("cm²", "centimètre carré", "centimètres carrés", false),
    ("m²", "mètre carré", "mètres carrés", false),
    ("m2", "mètre carré", "mètres carrés", false),
    ("cm³", "centimètre cube", "centimètres cubes", false),
    ("m³", "mètre cube", "mètres cubes", false),
    ("m3", "mètre cube", "mètres cubes", false),
    ("° C", "degré Celsius", "degrés Celsius", false),
    ("°C", "degré Celsius", "degrés Celsius", false),
    ("° F", "degré Fahrenheit", "degrés Fahrenheit", false),
    ("°F", "degré Fahrenheit", "degrés Fahrenheit", false),
    (" °", "degré", "degrés", false),
    ("km", "kilomètre", "kilomètres", false),
    ("cm", "centimètre", "centimètres", false),
    ("mm", "millimètre", "millimètres", false),
    ("m", "mètre", "mètres", false),
    ("kg", "kilo", "kilos", false),
    ("mg", "milligramme", "milligrammes", false),
    ("µg", "microgramme", "microgrammes", false),
    ("μg", "microgramme", "microgrammes", false),
    ("g", "gramme", "grammes", false),
    ("ml", "millilitre", "millilitres", false),
    ("mL", "millilitre", "millilitres", false),
    ("cl", "centilitre", "centilitres", false),
    ("cL", "centilitre", "centilitres", false),
    ("dl", "décilitre", "décilitres", false),
    ("dL", "décilitre", "décilitres", false),
    ("l", "litre", "litres", false),
    ("L", "litre", "litres", false),
    ("ha", "hectare", "hectares", false),
    ("kWh", "kilowattheure", "kilowattheures", false),
    ("kW", "kilowatt", "kilowatts", false),
    ("MW", "mégawatt", "mégawatts", false),
    ("W", "watt", "watts", false),
    ("kHz", "kilohertz", "kilohertz", false),
    ("MHz", "mégahertz", "mégahertz", false),
    ("GHz", "gigahertz", "gigahertz", false),
    ("Hz", "hertz", "hertz", false),
    ("To", "téraoctet", "téraoctets", false),
    ("Go", "gigaoctet", "gigaoctets", false),
    ("Mo", "mégaoctet", "mégaoctets", false),
    ("Ko", "kilooctet", "kilooctets", false),
    ("ko", "kilooctet", "kilooctets", false),
    ("dB", "décibel", "décibels", false),
    ("t", "tonne", "tonnes", true),
    ("kcal", "kilocalorie", "kilocalories", true),
    ("min", "minute", "minutes", true),
    ("mn", "minute", "minutes", true),
    ("ms", "milliseconde", "millisecondes", true),
    ("s", "seconde", "secondes", true),
    ("h", "heure", "heures", true),
    ("‰", "pour mille", "pour mille", false),
];
static UNIT_ALT: LazyLock<String> = LazyLock::new(|| alt(&UNITS.iter().map(|u| u.0).collect::<Vec<_>>()));

fn fr_measure(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[r"(?<![\w.,/-])(-?)(", &INT, r")(?:,(\d+))?", S, r"?(", &UNIT_ALT, r")(?![\w/²³'’]|\.\w)"])),
        &t,
        |m| {
            let (sign, i, dec) = (g(m, 1), g(m, 2), g(m, 3));
            let u = UNITS.iter().find(|x| x.0 == g(m, 4)).expect("unit");
            let before_last = g(m, 0).chars().rev().nth(1).unwrap_or(' ');
            if u.0 == "s" && dec.is_empty() && full(r"[1-9]0|1[0-9]{2}0|20[0-9]0", i) && before_last.is_ascii_digit() {
                return None; // 80s, 1960s: a decade (the grammar reads les 80s as the eighties)
            }
            let n = num(&if dec.is_empty() { i.to_string() } else { format!("{i},{dec}") });
            let n = if u.3 && dec.is_empty() { fem(&n) } else { n };
            let mut unit = (if int_part(i) >= 2 { u.2 } else { u.1 }).to_string();
            if search(SCALE_END, &n) {
                unit = de(u.2); // deux millions de kilomètres
            }
            Some(format!("{}{n} {unit}", if sign.is_empty() { "" } else { "moins " }))
        },
    )
}

// ------------------------------------------------------------------------------------------------- round millions

/// A whole number of millions as written (2 000 000, 3 500 000 000, 2000000; no leading zero); its reading decides.
static ROUND: LazyLock<String> = LazyLock::new(|| {
    cat(&[
        r"(?:[1-9]\d{0,2}(?:",
        S,
        r"\d{3})*",
        S,
        r"000",
        S,
        r"000|[1-9]\d{0,8}000000)(?![\w%°'’]|[.,:/-]\d|",
        S,
        r"\d)",
    ])
});
/// Lower-case plural words after a round million that are not what it counts.
const SCALE_NOT_COUNTED: &str = "
plus moins près après très dès lors alors puis depuis sous dans sans vers chez toujours jamais désormais ailleurs
parfois tous toutes les des ces mes tes ses nos vos leurs aux nous vous ils elles eux ceux celles quelques plusieurs
certains certaines autres mêmes deux trois six dix sommes êtes avons avez étions étiez pas mais hors
supplémentaires annuels annuelles mensuels mensuelles hebdomadaires quotidiens journaliers restants restantes nets
bruts totaux initiaux additionnels environs exactement perdus vendus reçus prévus obtenus rendus tenus dus attendus
voulus investis promis acquis remis transmis compris mis pris appris requis inclus exclus réunis garantis fournis
perçus définis choisis réussis finis établis répartis convertis premiers premières derniers dernières
";
/// -és words that are counted nouns (“2 000 000 salariés”).
const PARTICIPLE_NOUNS: &str = "
salariés employés blessés réfugiés déplacés députés invités abonnés retraités associés alliés condamnés délégués
initiés mariés licenciés exilés immigrés émigrés affiliés sinistrés vaccinés contaminés infectés hospitalisés décédés
tués comités côtés étés degrés clés cités comtés traités communautés libertés difficultés facultés beautés
";
static SCALE_NOT_COUNTED_SET: LazyLock<HashSet<&str>> =
    LazyLock::new(|| SCALE_NOT_COUNTED.split_whitespace().collect());
static PARTICIPLE_NOUNS_SET: LazyLock<HashSet<&str>> = LazyLock::new(|| PARTICIPLE_NOUNS.split_whitespace().collect());

/// A plural noun after a round million (prototype `counted_noun`).
fn counted_noun(w: &str) -> bool {
    if w.chars().count() < 3
        || !w.chars().next().is_some_and(char::is_lowercase)
        || !w.chars().next_back().is_some_and(|c| c == 's' || c == 'x')
        || !full(&cat(&[LETTER, "+"]), w)
    {
        return false;
    }
    if SCALE_NOT_COUNTED_SET.contains(w) {
        return false;
    }
    !w.ends_with("és") || w.ends_with("ités") || w.ends_with("iétés") || PARTICIPLE_NOUNS_SET.contains(w)
}

fn fr_scale_de(t: String, c: &mut Ctx) -> String {
    let re = rx(&cat(&[
        r"(?<![\w.,])",
        &AMT,
        r"(?:",
        S,
        r"?(",
        &SCALE_ALT,
        r"))?",
        S,
        r"+de",
        S,
        r"+(",
        &CUR_SIGN,
        r")(?![\w$€£¥/]|",
        S,
        r"*\d)",
    ]));
    let t = c.sub(&re, &t, |m| {
        let sc = g(m, 5);
        if sc.is_empty() && !search(SCALE_END, &num(g(m, 2))) {
            return None;
        }
        money(g(m, 1), g(m, 2), or(g(m, 3), g(m, 4)), sc, cur_of(g(m, 6)))
    });
    let re = rx(&cat(&[r"(?<![\w.,/:-])(?<!\d", S, r")(", &ROUND, r")(", S, r"+)([^\W\d_]+)(?![\w'’-])"]));
    c.sub(&re, &t, |m| {
        let (n, sp, w) = (g(m, 1), g(m, 2), g(m, 3));
        if !search(SCALE_END, &num(n)) || !counted_noun(w) {
            return None;
        }
        Some(format!("{n}{sp}{}", de(w)))
    })
}

// ------------------------------------------------------------------------------------------------- 10^12 and up

fn fr_big(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[r"(?<![\w.,/:])(?<!\d", S, r")(-?)([1-9]\d{0,2}(?:", S, r"\d{3}){4,5})(?![\w]|[.,]\d|", S, r"\d)"])),
        &t,
        |m| Some(format!("{}{}", if g(m, 1).is_empty() { "" } else { "moins " }, num(g(m, 2)))),
    )
}

// ------------------------------------------------------------------------------------------------- dot groups

fn fr_dot_groups(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(r"(?<![\w.,/:-])([1-9]\d{0,2}(?:\.\d{3})+)(?!\d|\.\d)"), &t, |m| Some(g(m, 1).replace('.', " ")))
}

// ------------------------------------------------------------------------------------------------- fractions, gender

fn fr_fraction(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&cat(&[r"(?<![\w.,/])1/2", S, r"+(", LETTER, r"+)(?![\w/-])"])), &t, |m| {
        let w = g(m, 1);
        if w == "h" {
            return Some("une demi-heure".to_string());
        }
        is_fem(w).then(|| format!("une demi-{w}"))
    })
}

static LABELS: LazyLock<String> = LazyLock::new(|| {
    cat(&[
        r"(?i)(?:^|[^\w])(?:page|pages|p|chapitre|chap|article|art|numéro|numéros|n°|no|tome|vol|volume|acte|scène|",
        r"saison|épisode|étape|niveau|version|classe|catégorie|porte|salle|chambre|bus|ligne|route|zone|phase|partie|",
        r"section|figure|fig|tableau|annexe|question|exercice|leçon|point|rang|groupe|lot|case|bâtiment|bloc|quai|voie|",
        r"terminal|appartement|étage|numéro|top|n)\.?",
        S,
        r"*$",
    ])
});

const STREET_WORDS: &str = "rue avenue place route allée impasse chaussée voie promenade esplanade cité résidence ruelle venelle \
traverse rocade corniche";
static STREETS: LazyLock<HashSet<&str>> = LazyLock::new(|| STREET_WORDS.split_whitespace().collect());
static STREET_NAME: LazyLock<String> = LazyLock::new(|| cat(&[S, r"+(?:[A-ZÀ-Ý]|d[eu]\b|des\b|d['’]|l['’]|la\b)"]));

fn fr_gender(t: String, c: &mut Ctx) -> String {
    c.sub(
        &rx(&cat(&[r"(?<![\w.,/:-])(\d{1,3}(?:", S, r"\d{3})*)(", S, r"+)([a-zà-ÿœæ]", LETTER, r"*)(?![\w'’-])"])),
        &t,
        |m| {
            let (n, sp, w) = (g(m, 1), g(m, 2), g(m, 3));
            if !is_fem(w) || search(&LABELS, tail(&t, start(m))) {
                return None;
            }
            if STREETS.contains(w.to_lowercase().as_str()) && matches_at_start(&STREET_NAME, &t[end(m)..]) {
                return None;
            }
            let r = num(n);
            let gw = fem(&r);
            (gw != r).then(|| format!("{gw}{sp}{w}"))
        },
    )
}

fn fr_decade(t: String, c: &mut Ctx) -> String {
    c.sub(&rx(&cat(&[r"(?<=années", S, r")(\d{2,4})(?![\w,.]\d|\d)"])), &t, |m| {
        let w = num(g(m, 1));
        (w.ends_with("vingts") || w.ends_with("cents")).then(|| chop(&w).to_string())
    })
}
