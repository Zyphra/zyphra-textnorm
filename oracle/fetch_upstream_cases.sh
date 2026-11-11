#!/usr/bin/env bash
# Downloads the NeMo-text-processing r1.2.0 text-normalization test cases (format: written~spoken per line) into
# oracle/upstream_cases/<lang>/. Only the written column feeds the differential corpus.
set -euo pipefail
cd "$(dirname "$0")"
base="https://raw.githubusercontent.com/NVIDIA/NeMo-text-processing/r1.2.0/tests/nemo_text_processing"

kinds() {
  case "$1" in
    en) echo "address cardinal date decimal electronic fraction math measure money normalize_with_audio ordinal punctuation punctuation_match_input range roman serial special_text telephone time whitelist word" ;;
    de|es) echo "cardinal date decimal electronic fraction measure money normalize_with_audio ordinal telephone time whitelist word" ;;
    fr) echo "cardinal date decimal fraction ordinal whitelist word" ;;
    it) echo "cardinal decimal electronic measure money time whitelist" ;;
    pt) echo "cardinal date decimal electronic fraction measure money ordinal telephone time" ;;
    ja) echo "cardinal date decimal fraction ordinal time" ;;
    zh) echo "cardinal date decimal fraction measure money ordinal time whitelist word" ;;
    ko) echo "cardinal date decimal electronic fraction measure money ordinal telephone time" ;;
  esac
}

for lang in en de es fr it pt ja zh ko; do
  mkdir -p "upstream_cases/$lang"
  for kind in $(kinds "$lang"); do
    out="upstream_cases/$lang/test_cases_$kind.txt"
    curl -sSfL "$base/$lang/data_text_normalization/test_cases_$kind.txt" -o "$out"
    echo "$out: $(wc -l < "$out") lines"
  done
done
