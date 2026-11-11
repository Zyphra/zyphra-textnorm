"""Differential-test corpus: per NeMo language, 400 lines per generator kind, each kind built from that language's
own grammar tables so every TSV row is exercised. Deterministic (random.Random(0)).

    python3 oracle/gen_corpus.py   ->   tests/corpus/<lang>.jsonl

Also folds oracle/handcrafted.jsonl (handcrafted inputs + the upstream NeMo test cases) into each language.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "tests" / "corpus"
PER_KIND = 400
LANGS = ["en", "de", "es", "fr", "it", "pt", "ja", "zh", "ko"]

ASCII_PUNCT = list("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
UNICODE_PUNCT = list("«»“”‘’…—–")
WS_RUNS = ["  ", "\t", "\n", "\r\n", "\u00a0", " \n ", "\n\n"]

FILLERS = {
    "en": "the a of and to in is was for on with he she it they we you at by from this that but not are have".split(),
    "de": "der die das und ist war für auf mit er sie es wir ihr bei von zu dieser aber nicht sind haben ein".split(),
    "es": "el la de y a en es era para con él ella ellos nosotros por desde este pero no son tienen un una".split(),
    "fr": "le la de et à en est était pour sur avec il elle ils nous vous par depuis ce mais pas sont ont un".split(),
    "it": "il la di e a in è era per su con lui lei loro noi voi da questo ma non sono hanno un una".split(),
    "pt": "o a de e para em é era com ele ela eles nós vocês por desde este mas não são têm um uma".split(),
    "ja": "私 は が を に で と も から まで の です ます した ある ない 今日 明日 昨日 彼 彼女 東京 日本 時間".split(),
    "zh": "我 你 他 她 我们 的 是 在 有 和 不 了 这 那 一个 今天 明天 北京 中国 时间 很 都 也 还".split(),
    "ko": "나는 너는 그는 그녀는 우리는 의 이 가 을 를 에 에서 와 과 오늘 내일 어제 서울 한국 시간 매우 모두 또 아직".split(),
}
SENTENCE_END = {"ja": "。", "zh": "。"}

# Locale numeric formatting: thousands separator alternatives and the decimal separator.
GROUPS = {
    "en": [",", ""],
    "de": [".", ""],
    "es": [".", " ", ""],
    "fr": [" ", "", "\u00a0"],
    "it": [".", ""],
    "pt": [".", ""],
    "ja": [",", ""],
    "zh": [",", ""],
    "ko": [",", ""],
}
DECIMAL = {"en": ".", "de": ",", "es": ",", "fr": ",", "it": ",", "pt": ",", "ja": ".", "zh": ".", "ko": "."}

# Tables per kind (relative to data/<lang>/); missing files are skipped.
TABLES = {
    "en": {
        "money": ["money/currency_major.tsv"],
        "money_minor": ["money/currency_minor_plural.tsv", "money/currency_minor_singular.tsv"],
        "measure": [
            "measure/unit.tsv",
            "measure/unit_alternatives.tsv",
            "measure/math_operation.tsv",
            "address/address_word.tsv",
            "address/state.tsv",
        ],
        "month": ["date/month_name.tsv", "date/month_abbr.tsv"],
        "year_suffix": ["date/year_suffix.tsv"],
        "time_suffix": ["time/suffix.tsv"],
        "time_zone": ["time/zone.tsv"],
        "telephone": ["telephone/telephone_prompt.tsv", "telephone/ip_prompt.tsv", "telephone/ssn_prompt.tsv"],
        "domain": ["electronic/domain.tsv"],
        "esymbol": ["electronic/symbol.tsv"],
        "whitelist": ["whitelist/tts.tsv", "whitelist/symbol.tsv", "whitelist/alternatives.tsv"],
        "quantity": ["number/quantity_abbr.tsv", "number/thousand.tsv"],
        "ordinal_suffix": ["ordinal/digit.tsv", "ordinal/teen.tsv"],
        "roman": ["roman/key_word.tsv", "roman/male.tsv", "roman/female.tsv"],
        "fraction_sym": ["number/fraction.tsv"],
    },
    "de": {
        "money": ["money/currency.tsv"],
        "money_minor": ["money/currency_minor_plural.tsv", "money/currency_minor_singular.tsv"],
        "measure": ["measure/measurements.tsv", "measure/suppletive.tsv"],
        "month": ["months/abbr_to_name.tsv"],
        "time_zone": ["time/time_zone.tsv"],
        "domain": ["electronic/domain.tsv", "electronic/server_name.tsv"],
        "esymbol": ["electronic/symbols.tsv"],
        "whitelist": ["whitelist.tsv"],
        "quantity": ["numbers/quantities.tsv"],
        "fraction_sym": ["fractions.tsv"],
    },
    "es": {
        "money": ["money/currency_major.tsv", "money/currency_major_ext.tsv"],
        "money_minor": ["money/currency_minor.tsv", "money/currency_minor_ext.tsv"],
        "measure": ["measures/measurements.tsv", "measures/measurements_complex.tsv", "measures/math_symbols.tsv"],
        "month": ["dates/months.tsv", "dates/months_abbr.tsv", "dates/days_abbr.tsv"],
        "year_suffix": ["dates/year_suffix.tsv"],
        "time_suffix": ["time/time_suffix.tsv"],
        "time_zone": ["time/time_zone.tsv", "time/time_zone_ext.tsv"],
        "telephone": ["telephone/telephone_prompt.tsv", "telephone/ip_prompt.tsv"],
        "domain": ["electronic/domain.tsv", "electronic/server_name.tsv"],
        "esymbol": ["electronic/symbols.tsv"],
        "whitelist": ["whitelist.tsv"],
        "quantity": ["numbers/quantities.tsv"],
        "fraction_sym": ["fractions/fraction_symbols.tsv"],
        "roman": ["roman/digit.tsv", "roman/ties.tsv", "roman/hundreds.tsv", "roman/thousands.tsv"],
    },
    "fr": {
        "measure": ["measures/measurements.tsv"],
        "month": ["dates/months.tsv"],
        "whitelist": ["whitelist.tsv"],
        "quantity": ["numbers/quantities.tsv"],
        "ordinal_suffix": ["ordinals/suffixes.tsv"],
        "eras": ["dates/eras.tsv"],
    },
    "it": {
        "money": ["money/currency_major.tsv"],
        "money_minor": ["money/currency_minor.tsv"],
        "measure": ["measure/measurements.tsv", "measure/suppletive.tsv"],
        "domain": ["electronic/domain.tsv", "electronic/server_name.tsv"],
        "esymbol": ["electronic/symbols.tsv"],
        "whitelist": ["whitelist/whitelist.tsv"],
        "quantity": ["numbers/quantities.tsv"],
    },
    "pt": {
        "money": ["money/currency_major.tsv", "money/currency_major_plural.tsv"],
        "money_minor": ["money/currency_minor.tsv", "money/currency_minor_plural.tsv"],
        "measure": ["measure/measurements_singular.tsv", "measure/measurements_plural.tsv"],
        "month": ["date/months.tsv"],
        "telephone": ["telephone/telephone_prompt.tsv", "telephone/ip_prompt.tsv"],
        "domain": ["electronic/domain.tsv", "electronic/server_name.tsv"],
        "esymbol": ["electronic/symbols.tsv"],
        "whitelist": ["whitelist/tts.tsv", "whitelist/symbol.tsv"],
        "quantity": ["numbers/scales.tsv", "numbers/quantity_words.tsv"],
        "time_suffix": ["time/day_period_suffix.tsv"],
    },
    "ja": {
        "month": ["date/month.tsv"],
        "era": ["date/era.tsv", "date/era_abbrev.tsv"],
        "week": ["date/week.tsv"],
        "time_suffix": ["time/division.tsv"],
        "whitelist": ["whitelist.tsv"],
        "symbol": ["symbol.tsv"],
    },
    "zh": {
        "money": ["money/currency_major.tsv", "money/currency_mandarin.tsv"],
        "measure": ["measure/units_en.tsv"],
        "month": ["date/months.tsv"],
        "year_suffix": ["date/suffix.tsv", "date/suffixes.tsv"],
        "time_suffix": ["time/AM.tsv", "time/PM.tsv"],
        "whitelist": ["whitelist.tsv", "erhua/whitelist.tsv"],
        "quantity": ["number/suffix.tsv"],
        "math": ["math/symbol.tsv", "math/score.tsv"],
    },
    "ko": {
        "money": ["money/currency_major.tsv"],
        "measure": ["measure/unit.tsv"],
        "week": ["date/week.tsv"],
        "time_suffix": ["time/division.tsv"],
        "telephone": ["electronic/cc_cues.tsv"],
        "domain": ["electronic/domain.tsv", "electronic/extensions.tsv"],
        "esymbol": ["electronic/symbol.tsv"],
        "whitelist": ["whitelist.tsv"],
        "counter": ["number/counter_suffix.tsv"],
        "ordinal_suffix": ["ordinal/exceptions.tsv"],
    },
}

# Ordinal written forms per language: callable(n) -> list of strings.
ORDINAL_SUFFIX = {
    "en": lambda n: [f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"],
    "de": lambda n: [f"{n}."],
    "es": lambda n: [f"{n}º", f"{n}ª", f"{n}.º", f"{n}°", f"{n}er"],
    "fr": lambda n: [f"{n}e", f"{n}ème", f"{n}er" if n == 1 else f"{n}e", f"{n}°"],
    "it": lambda n: [f"{n}°", f"{n}º"],
    "pt": lambda n: [f"{n}º", f"{n}ª", f"{n}.º", f"{n}o", f"{n}a"],
    "ja": lambda n: [f"第{n}", f"{n}番目", f"{n}位"],
    "zh": lambda n: [f"第{n}", f"第{n}个", f"{n}号"],
    "ko": lambda n: [f"{n}번째", f"제{n}", f"{n}째"],
}
TIME_FORMATS = {
    "en": ["{h}:{m:02d}", "{h}:{m:02d}:{s:02d}", "{h}.{m:02d}", "{h}:{m:02d} {suf}", "{h} {suf}", "{h}:{m:02d} {zone}"],
    "de": [
        "{h}:{m:02d}",
        "{h}:{m:02d}:{s:02d}",
        "{h}.{m:02d}",
        "{h} Uhr",
        "{h}:{m:02d} Uhr",
        "{h}:{m:02d} {zone}",
        "{h}.{m:02d} Uhr",
    ],
    "es": [
        "{h}:{m:02d}",
        "{h}:{m:02d}:{s:02d}",
        "{h}.{m:02d}",
        "{h}:{m:02d} {suf}",
        "{h}h",
        "{h}h{m:02d}",
        "{h}:{m:02d} {zone}",
    ],
    "fr": ["{h}h{m:02d}", "{h}h", "{h}:{m:02d}", "{h} h {m:02d}"],
    "it": ["{h}:{m:02d}", "{h}.{m:02d}", "{h}:{m:02d}:{s:02d}", "ore {h}:{m:02d}"],
    "pt": ["{h}:{m:02d}", "{h}h{m:02d}", "{h}h", "{h}:{m:02d}:{s:02d}", "{h}h {suf}", "{h}:{m:02d} {suf}"],
    "ja": ["{h}時{m}分", "{h}:{m:02d}", "{h}時", "{h}:{m:02d}:{s:02d}", "{suf}{h}時{m}分", "{h}時半"],
    "zh": ["{h}:{m:02d}", "{h}点{m}分", "{h}点", "{h}:{m:02d}:{s:02d}", "{suf}{h}点{m}分", "{h}点半"],
    "ko": ["{h}:{m:02d}", "{h}시 {m}분", "{h}시", "{h}:{m:02d}:{s:02d}", "{suf} {h}시 {m}분", "{h}시 반"],
}
DATE_FORMATS = {
    "en": [
        "{m}/{d}/{y}",
        "{d}/{m}/{y}",
        "{y}-{m:02d}-{d:02d}",
        "{mon} {d}, {y}",
        "{d} {mon} {y}",
        "{mon} {d}",
        "{mon}. {d}",
        "{mon} {y}",
        "the {d}th of {mon}",
        "{y}s",
        "'{y2}s",
        "{mon} {d}th",
        "{d}.{m}.{y}",
        "{m}/{d}",
        "{y}",
    ],
    "de": [
        "{d}.{m}.{y}",
        "{d}.{m}.",
        "{d}. {mon} {y}",
        "{d}. {mon}",
        "{mon} {y}",
        "{d}.{m:02d}.{y}",
        "{y}",
        "{d}/{m}/{y}",
        "{mon}. {y}",
    ],
    "es": [
        "{d}/{m}/{y}",
        "{d}-{m}-{y}",
        "{d}.{m}.{y}",
        "{d} de {mon} de {y}",
        "{d} de {mon}",
        "{mon} de {y}",
        "{d}/{m}",
        "{y}",
        "{d} {mon} {y}",
    ],
    "fr": [
        "{d}/{m}/{y}",
        "{d} {mon} {y}",
        "{d} {mon}",
        "{mon} {y}",
        "{d}.{m}.{y}",
        "le {d} {mon}",
        "{d}-{m}-{y}",
        "{y}",
    ],
    "it": ["{d}/{m}/{y}", "{d}.{m}.{y}", "{d} {mon} {y}", "{d}-{m}-{y}"],
    "pt": [
        "{d}/{m}/{y}",
        "{d}-{m}-{y}",
        "{d}.{m}.{y}",
        "{d} de {mon} de {y}",
        "{d} de {mon}",
        "{mon} de {y}",
        "{d}/{m}",
        "{y}",
        "{d}/{m:02d}/{y}",
    ],
    "ja": [
        "{y}年{m}月{d}日",
        "{m}月{d}日",
        "{y}年{m}月",
        "{y}/{m}/{d}",
        "{y}年",
        "{m}月{d}日({wk})",
        "{y}-{m:02d}-{d:02d}",
        "{era}{y2}年",
        "{y}.{m}.{d}",
    ],
    "zh": [
        "{y}年{m}月{d}日",
        "{m}月{d}日",
        "{y}年{m}月",
        "{y}/{m}/{d}",
        "{y}年",
        "{y}-{m:02d}-{d:02d}",
        "{y}.{m}.{d}",
        "{m}月",
        "{d}日",
        "{y}年{m}月{d}号",
    ],
    "ko": [
        "{y}년 {m}월 {d}일",
        "{m}월 {d}일",
        "{y}년 {m}월",
        "{y}/{m}/{d}",
        "{y}년",
        "{y}-{m:02d}-{d:02d}",
        "{y}.{m}.{d}.",
        "{m}월 {d}일 {wk}",
        "{y}. {m}. {d}.",
    ],
}


def load(lang: str, kind: str) -> list[str]:
    keys = []
    for rel in TABLES.get(lang, {}).get(kind, []):
        path = DATA / lang / rel
        if not path.exists():
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.reader(f, delimiter="\t"):
                if row and row[0]:
                    keys.append(row[0])
    return keys


def fmt_int(n: int, group: str) -> str:
    s = str(abs(n))
    if group:
        parts = []
        while len(s) > 3:
            parts.insert(0, s[-3:])
            s = s[:-3]
        parts.insert(0, s)
        s = group.join(parts)
    return ("-" if n < 0 else "") + s


class Gen:
    def __init__(self, lang: str):
        self.lang = lang
        self.rng = random.Random(0)
        self.t = {k: load(lang, k) for k in TABLES.get(lang, {})}
        self.fillers = FILLERS[lang]
        self.sep = " " if lang not in ("ja", "zh") else ""

    def pick(self, kind: str, default: list[str]) -> str:
        keys = self.t.get(kind) or default
        return self.rng.choice(keys) if keys else ""

    def number(self, lo=0, hi=10**15) -> int:
        magnitude = self.rng.choice([1, 2, 3, 4, 5, 6, 7, 9, 12, 15])
        return self.rng.randint(lo, min(hi, 10**magnitude))

    def cardinal(self) -> str:
        n = self.number()
        if self.rng.random() < 0.15:
            n = -n
        return fmt_int(n, self.rng.choice(GROUPS[self.lang]))

    def ordinal(self) -> str:
        n = self.rng.randint(1, self.rng.choice([10, 31, 100, 1000]))
        return self.rng.choice(ORDINAL_SUFFIX[self.lang](n))

    def decimal(self) -> str:
        whole = fmt_int(self.number(hi=10**7), self.rng.choice(GROUPS[self.lang]))
        frac = "".join(self.rng.choice("0123456789") for _ in range(self.rng.randint(1, 6)))
        s = f"{whole}{DECIMAL[self.lang]}{frac}"
        if self.rng.random() < 0.2:
            s = f"-{s}"
        if self.rng.random() < 0.3 and self.t.get("quantity"):
            s = f"{s} {self.pick('quantity', [])}".rstrip()
        return s

    def fraction(self) -> str:
        if self.rng.random() < 0.2:
            return self.rng.choice("½⅓¼¾⅔⅛") if not self.t.get("fraction_sym") else self.pick("fraction_sym", [])
        a, b = self.rng.randint(1, 99), self.rng.randint(2, 100)
        s = f"{a}/{b}"
        if self.rng.random() < 0.3:
            s = f"{self.rng.randint(1, 20)} {s}"
        if self.rng.random() < 0.2:
            s = f"-{s}"
        return s

    def money(self) -> str:
        cur = self.pick("money", ["$", "€"])
        n = fmt_int(self.number(hi=10**7), self.rng.choice(GROUPS[self.lang]))
        r = self.rng.random()
        if r < 0.4:
            n = f"{n}{DECIMAL[self.lang]}{self.rng.randint(0, 99):02d}"
        elif r < 0.5 and self.t.get("quantity"):
            n = f"{n} {self.pick('quantity', [])}"
        if self.rng.random() < 0.5 or self.lang in ("ja", "zh", "ko"):
            s = f"{cur}{n}" if self.rng.random() < 0.7 else f"{cur} {n}"
        else:
            s = f"{n}{cur}" if self.rng.random() < 0.3 else f"{n} {cur}"
        if self.t.get("money_minor") and self.rng.random() < 0.15:
            s = f"{self.rng.randint(1, 99)} {self.pick('money_minor', [])}"
        return s

    def measure(self) -> str:
        unit = self.pick("measure", ["kg", "km", "%"])
        n = (
            fmt_int(self.number(hi=10**6), self.rng.choice(GROUPS[self.lang]))
            if self.rng.random() < 0.7
            else self.decimal()
        )
        if self.rng.random() < 0.1:
            n = "1"
        if self.rng.random() < 0.1:
            n = f"-{n}"
        sep = "" if self.rng.random() < 0.5 else " "
        s = f"{n}{sep}{unit}"
        if self.rng.random() < 0.15 and self.t.get("measure"):
            s = f"{s}/{self.pick('measure', [])}"
        if self.rng.random() < 0.1:
            s = f"{self.rng.randint(1, 99)}x{self.rng.randint(1, 99)}"
        return s

    def date(self) -> str:
        y = self.rng.randint(1000, 2099)
        m, d = self.rng.randint(1, 12), self.rng.randint(1, 31)
        mon = self.pick("month", ["January", "Feb"])
        if self.lang in ("es", "fr", "pt", "ja", "zh") and mon.isdigit():
            mon = self.rng.choice(["enero", "mai", "janeiro", "一月", "三月"])
        if self.rng.random() < 0.3 and self.lang in ("en", "de"):
            mon = mon.capitalize()
        fmt = self.rng.choice(DATE_FORMATS[self.lang])
        s = fmt.format(
            y=y,
            m=m,
            d=d,
            mon=mon,
            y2=y % 100,
            wk=self.pick("week", ["月"]),
            era=self.pick("era", ["令和"]),
        )
        if self.rng.random() < 0.15 and self.t.get("year_suffix"):
            s = f"{y} {self.pick('year_suffix', [])}"
        if self.rng.random() < 0.1 and self.t.get("eras"):
            s = self.pick("eras", [])
        return s

    def time(self) -> str:
        h, m, s = self.rng.randint(0, 23), self.rng.randint(0, 59), self.rng.randint(0, 59)
        if self.rng.random() < 0.6:
            h = self.rng.randint(1, 12)
        fmt = self.rng.choice(TIME_FORMATS[self.lang])
        return fmt.format(
            h=h, m=m, s=s, suf=self.pick("time_suffix", ["pm", "a.m."]), zone=self.pick("time_zone", ["est"])
        )

    def telephone(self) -> str:
        prompt = self.pick("telephone", [])
        digits = lambda n: "".join(self.rng.choice("0123456789") for _ in range(n))
        forms = [
            f"{digits(3)}-{digits(3)}-{digits(4)}",
            f"({digits(3)}) {digits(3)}-{digits(4)}",
            f"+{digits(2)} {digits(3)} {digits(3)} {digits(4)}",
            f"{digits(3)}.{digits(3)}.{digits(4)}",
            f"{digits(1)}.{digits(3)}.{digits(3)}.{digits(3)}",
            f"{digits(3)}-{digits(2)}-{digits(4)}",
            f"{digits(10)}",
            f"{digits(4)} {digits(4)} {digits(4)} {digits(4)}",
        ]
        s = self.rng.choice(forms)
        if prompt and self.rng.random() < 0.7:
            s = f"{prompt} {s}"
        return s

    def electronic(self) -> str:
        words = self.rng.sample(self.fillers, 2)
        dom = self.pick("domain", [".com"])
        sym = self.pick("esymbol", ["."])
        forms = [
            f"{words[0]}@{words[1]}{dom}",
            f"{words[0]}{sym}{words[1]}@{words[1]}{dom}",
            f"www.{words[0]}{dom}",
            f"https://{words[0]}{dom}/{words[1]}",
            f"http://www.{words[0]}{dom}",
            f"{words[0]}{dom}",
            f"@{words[0]}",
            f"{words[0]}{self.rng.randint(1, 99)}@{words[1]}{dom}",
        ]
        return self.rng.choice(forms)

    def whitelist(self) -> str:
        key = self.pick("whitelist", [])
        return key if self.rng.random() < 0.6 else key.lower()

    def misc(self) -> str:
        pool = [
            self.cardinal,
            self.ordinal,
            self.decimal,
            self.fraction,
            self.money,
            self.measure,
            self.date,
            self.time,
        ]
        if self.t.get("telephone") or self.lang in ("en", "ko"):
            pool.append(self.telephone)
        if self.t.get("domain"):
            pool.append(self.electronic)
        if self.t.get("whitelist"):
            pool.append(self.whitelist)
        if self.t.get("roman"):
            pool.append(lambda: self.rng.choice(["II", "IV", "VII", "XIV", "XX"]) + " " + self.pick("roman", []))
        if self.t.get("counter"):
            pool.append(lambda: f"{self.rng.randint(1, 99)}{self.pick('counter', [])}")
        if self.t.get("math"):
            pool.append(lambda: f"{self.rng.randint(1, 99)}{self.pick('math', [])}{self.rng.randint(1, 99)}")
        return self.rng.choice(pool)()

    def punct_stress(self) -> str:
        item = self.misc()
        mark = self.rng.choice(ASCII_PUNCT + UNICODE_PUNCT)
        r = self.rng.random()
        word = self.rng.choice(self.fillers)
        if r < 0.25:
            return f"{word} {item}{mark}"
        if r < 0.5:
            return f"{mark}{item} {word}"
        if r < 0.65:
            return f"{word} {item}{mark}{mark}"
        if r < 0.8:
            q = self.rng.choice(['"', "'", "(", "[", "«", "“"])
            close = {"(": ")", "[": "]", "«": "»", "“": "”"}.get(q, q)
            return f"{word} {q}{item}{close} {word}"
        return f"{word}{mark} {item} {mark}{word}"

    def whitespace(self) -> str:
        words = [self.rng.choice(self.fillers), self.misc(), self.rng.choice(self.fillers)]
        ws = self.rng.choice(WS_RUNS)
        s = ws.join(words)
        if self.rng.random() < 0.3:
            s = self.rng.choice(WS_RUNS) + s
        if self.rng.random() < 0.3:
            s = s + self.rng.choice(WS_RUNS)
        return s

    def escapes(self) -> str:
        item = self.misc()
        e = self.rng.choice(["[", "]", "\\"])
        r = self.rng.random()
        if r < 0.3:
            return f"{e}{item}{e}"
        if r < 0.6:
            return f"[{item}] {self.rng.choice(self.fillers)}"
        return f"{self.rng.choice(self.fillers)} {e} {item} \\{item}"

    def mixed(self) -> str:
        n = self.rng.randint(2, 5)
        parts = []
        for _ in range(n):
            parts.extend(self.rng.sample(self.fillers, self.rng.randint(1, 3)))
            parts.append(self.misc())
        parts.extend(self.rng.sample(self.fillers, self.rng.randint(0, 2)))
        s = self.sep.join(parts)
        end = SENTENCE_END.get(self.lang, self.rng.choice([".", "!", "?", ""]))
        s = s + end
        if self.rng.random() < 0.3:
            s = s[0].upper() + s[1:]
        return s

    def markup(self) -> str:
        s = self.mixed()
        r = self.rng.random()
        words = s.split(" ") if self.sep else list(s)
        i = self.rng.randint(0, len(words))
        if r < 0.3:
            words.insert(i, "<laugh/>")
        elif r < 0.5:
            words.insert(i, "<shouting>")
            words.insert(self.rng.randint(i + 1, len(words)), "</shouting>")
        elif r < 0.75:
            words.insert(i, "\ue000kæt\ue001")
        else:
            words.insert(i, "\n")
        return self.sep.join(words) if self.sep else "".join(words)

    def kinds(self):
        yield "cardinal", self.cardinal
        yield "ordinal", self.ordinal
        yield "decimal", self.decimal
        yield "fraction", self.fraction
        yield "money", self.money
        yield "measure", self.measure
        yield "date", self.date
        yield "time", self.time
        yield "telephone", self.telephone
        yield "electronic", self.electronic
        yield "whitelist", self.whitelist
        yield "punct", self.punct_stress
        yield "whitespace", self.whitespace
        yield "escapes", self.escapes
        yield "mixed", self.mixed
        yield "markup", self.markup

    def table_rows(self):
        """Every key of every table once, standalone and in a short sentence."""
        for kind, keys in self.t.items():
            for key in keys:
                yield key
                if kind in ("money",):
                    yield f"{key}{self.rng.randint(1, 999)}"
                    yield f"{self.rng.randint(1, 999)} {key}"
                elif kind in ("measure", "counter"):
                    yield f"{self.rng.randint(1, 999)} {key}"
                    yield f"{self.rng.randint(1, 999)}{key}"
                elif kind in ("whitelist",):
                    yield f"{self.rng.choice(self.fillers)} {key} {self.rng.choice(self.fillers)}"
                    yield key.lower()
                elif kind in ("month",):
                    yield f"{self.rng.randint(1, 28)} {key} {self.rng.randint(1900, 2030)}"
                    yield f"{key} {self.rng.randint(1, 28)}"
                elif kind in ("time_suffix", "time_zone"):
                    yield f"{self.rng.randint(1, 12)}:{self.rng.randint(0, 59):02d} {key}"
                elif kind in ("domain",):
                    yield f"abc{key}"
                    yield f"a@b{key}"
                elif kind in ("telephone",):
                    yield f"{key} 555-123-4567"
                elif kind in ("quantity",):
                    yield f"{self.rng.randint(1, 99)} {key}"
                    yield f"{self.rng.randint(1, 99)}{DECIMAL[self.lang]}5 {key}"
                else:
                    yield f"{self.rng.choice(self.fillers)} {key} {self.rng.choice(self.fillers)}"

    def generate(self):
        seen = set()
        for _, fn in self.kinds():
            produced = 0
            tries = 0
            while produced < PER_KIND and tries < PER_KIND * 20:
                tries += 1
                s = fn()
                if s and "\x00" not in s and s not in seen:
                    seen.add(s)
                    produced += 1
                    yield s
        for s in self.table_rows():
            if s and s not in seen:
                seen.add(s)
                yield s


def handcrafted() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {l: [] for l in LANGS}
    path = ROOT / "oracle" / "handcrafted.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out.setdefault(row["lang"], []).append(row["text"])
    for lang in LANGS:
        d = ROOT / "oracle" / "upstream_cases" / lang
        for f in sorted(d.glob("test_cases_*.txt")) if d.exists() else []:
            for line in f.read_text(encoding="utf-8").splitlines():
                if "~" in line:
                    out[lang].append(line.split("~", 1)[0])
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    extra = handcrafted()
    for lang in LANGS:
        gen = Gen(lang)
        seen = set()
        rows = []
        for text in list(extra.get(lang, [])) + list(gen.generate()):
            if text and "\x00" not in text and text not in seen:
                seen.add(text)
                rows.append(text)
        with open(OUT / f"{lang}.jsonl", "w", encoding="utf-8") as f:
            for text in rows:
                f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
        print(f"{lang}: {len(rows)} lines")


if __name__ == "__main__":
    main()
