"""Locale-gated rules from ZONOS3; symbol names derived from Unicode CLDR 49 annotations.

Unicode CLDR data is © 2001–2026 Unicode, Inc.; see unicode-cldr-LICENSE.txt.
NeMo grammar sources are © NVIDIA Corporation and affiliates, Apache-2.0;
see ../licenses/nemo-Apache-2.0.txt and source file headers.
"""
import re
from typing import Dict

# hu / sv and the added dot-ordinal locales: "3." is an ordinal ("harmadik", "tredje") and the periods of a numeric date belong to it ("2010. április 1.",
# "2010. 04. 1.", "23. jan. 2022"); the grammars read both from the glued period, which the generic digit rule spaced
# off (every one a cardinal: "kettőezer-tíz. április elseje."). The period stays glued when the number is the whole text
# ("2."), or when a lower-case word, a number or a Roman numeral follows ("a 2. helyen", "2010. április", "2010. IV.
# 1."); at the end of the text also, in hu, after the article a / az ("Ő lett a 2.") or a date's month ("április 1.",
# "04. 1."). Otherwise a capital letter follows or the text ends, and it is the sentence's period ("1990. Utána",
# "Van 3."). Known residue: an ordinal before a capitalized name ("a 2. Világháború").
_ORDINAL_PERIOD_LANGS = {"hu", "sv", "pl", "tr", "cs", "da", "fi", "nb", "sk"}
_ORDINAL_PERIOD_RE = re.compile(r"(?<!\d)(?<!\d )(\d{1,3}(?: \d{3})+|\d+)\.(?=\s|[\"'»”)\]]*$)")
_HU_DAY_AFTER_RE = re.compile(
    r"(?:^|\s)(?:\d{1,4}\.|[IVX]{1,4}\.|(?i:január|február|március|április|május|június|július|augusztus|szeptember"
    r"|október|november|december|jan\.|febr?\.|márc\.|ápr\.|máj\.|jún\.|júl\.|aug\.|szept?\.|okt\.|nov\.|dec\.))\s+$"
)
_HU_ARTICLE_RE = re.compile(r"(?:^|\s)(?i:az?)\s+$")
_ORDINAL_PERIOD_MASK = "\ue013"  # private use: the kept period while the generic rule runs


def _keep_ordinal_periods(text: str, lang: str) -> str:
    def sub(m: "re.Match[str]") -> str:
        before, rest = text[: m.start()], text[m.end() :].lstrip()
        if rest and rest[0] not in "\"'»”)]":
            keep = rest[0].islower() or rest[0].isdigit() or re.match(r"[IVX]{1,4}\.", rest) is not None
        else:
            num = m.group(1)
            is_year = len(num) == 4 and num.isdigit() and 1000 <= int(num) <= 2999
            keep = (not before.strip() and not is_year) or (
                lang == "hu" and (_HU_ARTICLE_RE.search(before) or _HU_DAY_AFTER_RE.search(before)) is not None
            )
        return m.group(1) + _ORDINAL_PERIOD_MASK if keep else m.group(0)

    return _ORDINAL_PERIOD_RE.sub(sub, text)

_SYMBOL_WORDS: Dict[str, tuple] = {
    "en": ("minus", "plus", "equals", "times", "divided by", "to the power of", "number"),
    "de": ("minus", "plus", "gleich", "mal", "geteilt durch", "hoch", "Nummer"),
    "fr": ("moins", "plus", "égal", "fois", "divisé par", "puissance", "numéro"),
    "es": ("menos", "más", "igual a", "por", "entre", "elevado a", "número"),
    "it": ("meno", "più", "uguale a", "per", "diviso", "elevato alla", "numero"),
    "pt": ("menos", "mais", "igual a", "vezes", "dividido por", "elevado a", "número"),
    "ja": ("マイナス", "プラス", "イコール", "かける", "わる", "の", "番号"),
    "zh": ("减", "加", "等于", "乘", "除以", "的", "第"),
    "ko": ("빼기", "더하기", "는", "곱하기", "나누기", "의", "번"),
    "hi": ("घटा", "धन", "बराबर", "गुणा", "भाग", "की घात", "नंबर"),
    "ar": ("ناقص", "زائد", "يساوي", "ضرب", "على", "أس", "رقم"),
    "bn": ("বিয়োগ", "যোগ", "সমান", "গুণ", "ভাগ", "এর ঘাত", "নম্বর"),
    "id": ("kurang", "tambah", "sama dengan", "kali", "bagi", "pangkat", "nomor"),
    "ur": ("منفی", "جمع", "برابر", "ضرب", "تقسیم", "کی طاقت", "نمبر"),
    "ru": ("минус", "плюс", "равно", "умножить на", "разделить на", "в степени", "номер"),
    "mr": ("वजा", "अधिक", "बरोबर", "गुणिले", "भागिले", "चा घात", "क्रमांक"),
    "vi": ("trừ", "cộng", "bằng", "nhân", "chia", "mũ", "số"),
    "te": ("తీసివేత", "కూడిక", "సమానం", "గుణకారం", "భాగహారం", "ఘాతం", "సంఖ్య"),
    "sw": ("toa", "jumlisha", "ni sawa na", "mara", "gawanya kwa", "kipeo", "namba"),
    "ha": ("ɗebe", "da", "daidai da", "sau", "raba da", "ƙarfin", "lamba"),
    "sv": ("minus", "plus", "är lika med", "gånger", "delat med", "upphöjt till", "nummer"),
    "hu": ("mínusz", "plusz", "egyenlő", "szorozva", "osztva", "hatványon", "szám"),
    "hy": ("մինուս", "պլյուս", "հավասար է", "բազմապատկած", "բաժանած", "աստիճան", "համար"),
    "rw": ("gukuramo", "guteranya", "bingana na", "gukuba", "kugabanya", "ubwikube bwa", "nimero"),
    "nl": ("min", "plus", "is gelijk aan", "maal", "gedeeld door", "tot de macht", "nummer"),
    "pl": ("minus", "plus", "równa się", "razy", "podzielone przez", "do potęgi", "numer"),
    "tr": ("eksi", "artı", "eşittir", "çarpı", "bölü", "üzeri", "numara"),
    "uk": ("мінус", "плюс", "дорівнює", "помножити на", "поділити на", "у степені", "номер"),
    "cs": ("mínus", "plus", "rovná se", "krát", "děleno", "na", "číslo"),
    "da": ("minus", "plus", "er lig med", "gange", "divideret med", "i", "nummer"),
    "fi": ("miinus", "plus", "on yhtä kuin", "kertaa", "jaettuna", "potenssiin", "numero"),
    "el": ("μείον", "συν", "ίσον", "επί", "διά", "στη δύναμη", "αριθμός"),
    "nb": ("minus", "pluss", "er lik", "ganger", "delt på", "opphøyd i", "nummer"),
    "ro": ("minus", "plus", "egal cu", "ori", "împărțit la", "la puterea", "numărul"),
    "sk": ("mínus", "plus", "rovná sa", "krát", "delené", "na", "číslo"),
    "bg": ("минус", "плюс", "е равно на", "по", "делено на", "на степен", "номер"),
    "he": ("מינוס", "פלוס", "שווה", "כפול", "חלקי", "בחזקת", "מספר"),
    "th": ("ลบ", "บวก", "เท่ากับ", "คูณ", "หาร", "ยกกำลัง", "หมายเลข"),
    "tl": ("bawas", "dagdag", "ay katumbas ng", "beses", "hinati sa", "na may eksponenteng", "bilang"),
    "ms": ("negatif", "tambah", "sama dengan", "darab", "bahagi", "kuasa", "nombor"),
    "ka": ("მინუს", "პლუს", "უდრის", "გამრავლებული", "გაყოფილი", "ხარისხში", "ნომერი"),
    "ta": ("கழித்தல்", "கூட்டல்", "சமம்", "பெருக்கல்", "வகுத்தல்", "அடுக்கு", "எண்"),
    "gu": ("બાદ", "વત્તા", "બરાબર", "ગુણ્યા", "ભાગ્યા", "ની ઘાત", "નંબર"),
    "kn": ("ಕಳೆ", "ಕೂಡು", "ಸಮ", "ಗುಣಿಸು", "ಭಾಗಿಸು", "ಘಾತ", "ಸಂಖ್ಯೆ"),
    "ml": ("കുറയ്ക്കുക", "കൂട്ടുക", "സമം", "ഗുണം", "ഹരിക്കുക", "ഘാതം", "നമ്പർ"),
    "pa": ("ਘਟਾਓ", "ਜੋੜ", "ਬਰਾਬਰ", "ਗੁਣਾ", "ਭਾਗ", "ਦੀ ਘਾਤ", "ਨੰਬਰ"),
    "or": ("ବିଯୋଗ", "ଯୋଗ", "ସମାନ", "ଗୁଣନ", "ଭାଗ", "ଘାତ", "ସଂଖ୍ୟା"),
}
_OP_INDEX = {"-": 0, "−": 0, "+": 1, "=": 2, "×": 3, "*": 3, "÷": 4, "^": 5}
_UNICODE_MINUS_RE = re.compile(r"(?<![\w.,])−(?=(?:[A-Z]{1,3}\$|Rs\.?\s*\d|[\d$£€¥₹₨₦৳֏₽₩₫₱฿₺₪₴₵¢¼½¾⅐-⅞]))")
_NUM = r"\d+(?:[.,]\d+)*"  # digits with optional grouping / decimal separators
_OP = r"(?: [-−+=×*÷^] |[+=×*÷^])"
_EXPR_RE = re.compile(rf"(?<![\w.,/:\-&#])({_NUM}(?:{_OP}{_NUM})+)(?![\w/:])")
_EXPR_PART_RE = re.compile(rf"({_NUM})|({_OP})")
_HASH_NUMBER_RE = re.compile(r"(?<![\w&])#(?=\d)")
_UNSPACED_SYMBOL_LANGS = {"ja", "zh"}
# grammars that read a lone "a^b" themselves (en "two cubed"; the hi-derived serial grammars "दो क्यूब", "দুই কিউব")
_POWER_GRAMMAR_LANGS = {"en", "hi", "bn", "mr", "ur", "te"}
# hu / hy say a power with the exponent as an ordinal, which their grammars read from its written form: "2^3" ->
# "2 a 3. hatványon" ("kettő a harmadik hatványon", "az" before a vowel: egy-, öt-, ezer-) / "2-ի 3-րդ աստիճան"
# ("երկուսի երրորդ աստիճան": the base in the genitive). (base, exponent) -> the rewrite.
_ORDINAL_POWER = {
    "hu": lambda b, n: f"{b} {'az' if n[0] == '5' or (n[0] == '1' and len(n) in (1, 4)) else 'a'} {n}. hatványon",
    "hy": lambda b, n: f"{b}{'-ի' if b.isdigit() else ''} {n}-{'ին' if n == '1' else 'րդ'} աստիճան",
}


def _speak_expression(lang: str, m: "re.Match[str]", text: str) -> str:
    parts = [p.group(0) for p in _EXPR_PART_RE.finditer(m.group(1))]
    ops = [p.strip() for p in parts[1::2]]
    if all(op in "-−" for op in ops):  # only dashes: a range or a hyphenated number, the grammars' to read
        return m.group(0)
    # en's, es's and sv's measure grammars read "<number> <op> <number> = <number>" equations themselves (en also
    # "1- 2 = 5" and "2+3 m2" with its unit; es "dos más dos menos uno es igual a tres"; sv "ett plus fem är sex", one
    # operator only): leave those to them. A lone "=" between numbers is "equals" / "igual a" / "är lika med" (the
    # grammars say "equal sign" / leave "=").
    if lang == "en" and all(op in "+-−=" for op in ops):
        before = text[max(0, m.start() - 2) : m.start()]
        if any(op in "+-−" for op in ops) or "-" in before:
            return m.group(0)
    if lang == "es" and "=" in ops and len(ops) > 1 and all(op in "+-−×*÷=" for op in ops):
        return m.group(0)
    if lang == "sv" and len(ops) == 2 and ops[1] == "=" and ops[0] in "+-−×*÷":
        return m.group(0)
    if lang == "sv" and ops == ["="] and text[max(0, m.start() - 1) : m.start()] in ("+", "-", "−", "×", "*", "÷"):
        return m.group(0)  # "α+1=3": the expression starts with a letter, which sv's grammar reads too
    if parts[1:2] == ["^"] and len(parts) == 3 and lang in _POWER_GRAMMAR_LANGS:  # a lone unspaced power
        if lang != "en" or parts[2] in ("2", "3"):  # en reads only "squared" / "cubed"
            return m.group(0)
    sep = "" if lang in _UNSPACED_SYMBOL_LANGS else " "
    words = _SYMBOL_WORDS[lang]
    out = [parts[0]]
    for op, num in zip(parts[1::2], parts[2::2]):
        op = op.strip()
        if op == "^" and lang in _ORDINAL_POWER and num.isdigit():
            out.append(_ORDINAL_POWER[lang](out.pop(), num))
        else:
            out += [words[_OP_INDEX[op]], num]
    return sep.join(out)


def _speak_symbols(text: str, lang: str) -> str:
    """Unicode minus to "-", arithmetic to words and "#<number>" to the number word (see _SYMBOL_WORDS)."""
    text = _UNICODE_MINUS_RE.sub("-", text)
    if lang not in _SYMBOL_WORDS:
        return text
    text = _EXPR_RE.sub(lambda m: _speak_expression(lang, m, text), text)
    sep = "" if lang in _UNSPACED_SYMBOL_LANGS else " "
    return _HASH_NUMBER_RE.sub(_SYMBOL_WORDS[lang][6] + sep, text)

_SPACING_MARKS = '()[]{}"«»“”„'


def match_bracket_spacing(original: str, result: str) -> str:
    """``result`` with the space before and after each bracket / double quote as in ``original`` (see above)."""
    drop: set[int] = set()  # spaces of result to delete
    add: set[int] = set()  # gaps of result (before index g) that get a space
    for mark in _SPACING_MARKS:
        typed = [i for i, c in enumerate(original) if c == mark]
        out = [j for j, c in enumerate(result) if c == mark]
        if not typed or len(typed) != len(out):
            continue
        for i, j in zip(typed, out):
            for side in (-1, 1):
                ti, tj = i + side, j + side
                if not (0 <= ti < len(original) and 0 <= tj < len(result)):
                    continue
                spaced = original[ti] == " "
                if result[tj] == " " and not spaced:
                    drop.add(tj)
                elif result[tj] != " " and spaced:
                    add.add(j if side < 0 else j + 1)
    if not drop and not add:
        return result
    return "".join((" " if j in add else "") + ("" if j in drop else c) for j, c in enumerate(result))

_DIGIT_PUNCT_RE = re.compile(r"(\d)([.!?,;:।۔،؛؟։॥])(?=[\"'»”’)\]]*(\s|$))")
_SPACE_PUNCT_RE = re.compile(r" +([.!?,;:।۔،؛؟։॥])(?=[\"'»”’)\]]*(\s|$))")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.", "٬")

def pre_normalize(text, lang):
    if lang in {"ar", "ur"}:
        text = text.translate(_ARABIC_DIGITS)
    text = _speak_symbols(text, lang)
    if lang in _ORDINAL_PERIOD_LANGS:
        text = _keep_ordinal_periods(text, lang)
    return _DIGIT_PUNCT_RE.sub(r"\1 \2", text).replace(_ORDINAL_PERIOD_MASK, ".")

def post_normalize(text):
    return _SPACE_PUNCT_RE.sub(r"\1", text.replace("\u00a0", " "))
