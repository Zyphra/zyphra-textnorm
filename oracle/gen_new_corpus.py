"""Generate new-locale corpora from source input columns and productive rule boundaries.

Run: /tmp/tn-env/bin/python oracle/gen_new_corpus.py
The source fixture inputs are frozen in oracle/upstream_cases/<lang>/inputs.txt;
lexical inputs come from the vendored NeMo data tables. No expected outputs are used.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = 'nl pl tr uk cs da fi el nb ro sk bg he th tl ms ka ta gu kn ml pa or ru sv hu ar vi id hi bn te mr ur'.split()


def cases(lang):
    yield from (ROOT / 'oracle/upstream_cases' / lang / 'inputs.txt').read_text(encoding='utf-8').splitlines()
    rng = random.Random('zyphra-locale-corpus-' + lang)
    # Numeric boundaries and held-out compositions exercise cardinal, decimal,
    # date, time, fraction, sign, range, ordinal and punctuation branches.
    numbers = [0, 1, 2, 9, 10, 11, 19, 20, 21, 99, 100, 101, 999, 1000,
               1001, 9999, 10000, 99999, 100000, 999999, 1000000, 1000001]
    numbers += [rng.randrange(1, 9999999) for _ in range(100)]
    for n in numbers:
        s = str(n)
        yield s
        yield '-' + s
        yield '−' + s
        yield s + '.'
        yield s + '%'
        yield f'{n},25'
        yield f'{n}.75'
        yield f'{n}/7'
    for _ in range(80):
        a, b = rng.randrange(1, 100), rng.randrange(1, 100)
        day, month, year = rng.randrange(1, 29), rng.randrange(1, 13), rng.randrange(1900, 2100)
        h, minute = rng.randrange(24), rng.randrange(60)
        yield f'{a}+{b}={a+b}'
        yield f'{a}-{b}'
        yield f'{day:02d}.{month:02d}.{year}'
        yield f'{day:02d}/{month:02d}/{year}'
        yield f'{year}-{month:02d}-{day:02d}'
        yield f'{h:02d}:{minute:02d}'
    data = ROOT / 'oracle/nemo_text_processing/text_normalization' / lang / 'data'
    for table in sorted(data.rglob('*.tsv')):
        # The first column is a written form; combining it with held-out
        # quantities probes productive unit and currency rules as well as words.
        for line in table.read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):
                continue
            key = line.split('\t', 1)[0].strip()
            if not key or len(key) > 40 or '"' in key or '\\' in key:
                continue
            yield key
            if any(part in str(table).lower() for part in ('measure', 'unit', 'currency', 'money')):
                yield '37 ' + key
                yield key + ' 123'
    # ISO years beyond colloquial 19xx/20xx readers must retain the actual year.
    yield '2017-12-14'
    yield '2189-12-06'
    # Numeric recognizers must not silently widen their source digit alphabet.
    yield '١٢٣'
    yield '١٢:٣٠'
    native_zero = {'th': 0x0E50, 'ta': 0x0BE6, 'gu': 0x0AE6, 'kn': 0x0CE6,
                   'ml': 0x0D66, 'pa': 0x0A66, 'or': 0x0B66, 'hi': 0x0966,
                   'bn': 0x09E6, 'te': 0x0C66, 'mr': 0x0966}.get(lang)
    if native_zero is not None:
        yield ''.join(chr(native_zero + n) for n in (1, 2, 3))
    if lang == 'pl':
        yield '1' * 129
    if lang == 'gu':
        # Serial prefix gates must retain one-dot v-versions, unprefixed
        # two-dot versions and powers, without misreading a word's final dot.
        yield from ('v1.2', '1.2.3', '2²', 'રૂપિયા.')
    if lang in {'ar', 'ur'}:
        yield from ('۱۲۳', '١٬٢٣٤٫٥٠', '۱۲٬۳۴۵٫۶۷')
    if lang == 'hu':
        yield from ('2.', 'Ő lett a 2.', 'április 1.', '2010. 04. 1.',
                    '2010. IV. 1.', '2^3', '2^5', '2^1', '2^1000')
    if lang == 'sv':
        yield from ('2.', '3. plats', '1+5=6', 'α+1=3', '1=1', '2^3')
    if lang in {'hi', 'bn', 'te', 'mr', 'ur'}:
        yield from ('2^2', '2^3', '2^4', '2 ^ 3', '2^3+1')


def main():
    out = ROOT / 'tests/corpus'
    out.mkdir(parents=True, exist_ok=True)
    for lang in LANGS:
        seen = set()
        with (out / f'{lang}.jsonl').open('w', encoding='utf-8') as f:
            for text in cases(lang):
                if text and text not in seen:
                    seen.add(text)
                    f.write(json.dumps({'text': text}, ensure_ascii=False) + '\n')
        print(f'{lang}: {len(seen)}')


if __name__ == '__main__':
    main()
