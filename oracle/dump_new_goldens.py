"""Generate compressed new-locale goldens, one grammar process at a time.

Run from repository root: /tmp/tn-env/bin/python oracle/dump_new_goldens.py
Pass locale codes as arguments to restrict the run. Requires zstd on PATH.
Each child exits before the next starts, releasing its FSTs and bounding memory.
"""
import os
import subprocess
import sys

from gen_new_corpus import LANGS, ROOT


def main():
    langs = sys.argv[1:] or LANGS
    if any(lang not in LANGS for lang in langs):
        raise SystemExit('unknown locale: ' + ', '.join(x for x in langs if x not in LANGS))
    cache = os.environ.get('ZONOS3_TTS_NORM_CACHE_DIR', '/tmp/zonos3-tts-norm')
    for lang in langs:
        plain = ROOT / 'tests/golden' / f'{lang}.jsonl'
        subprocess.run([sys.executable, str(ROOT / 'oracle/dump_golden.py'), '--lang', lang,
                        '--corpus', str(ROOT / 'tests/corpus' / f'{lang}.jsonl'),
                        '--out', str(plain), '--cache', cache], cwd=ROOT, check=True)
        subprocess.run(['zstd', '-19', '-f', str(plain), '-o', str(plain) + '.zst'], check=True)
        plain.unlink()


if __name__ == '__main__':
    main()
