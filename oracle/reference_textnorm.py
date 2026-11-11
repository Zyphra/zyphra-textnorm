"""Frozen copy of ZONOS3's text-normalization wrapper (model/src/zonos3/tokenizer/textnorm.py of Zyphra/ZONOS3) as of
the Rust port: the differential-test oracle.

Runs only inside the oracle container (oracle/Dockerfile), where the NeMo r1.2.0 grammars and pynini are installed.
The zonos3 imports are inlined; nothing else changed. Its language codes are ZONOS3's (`SERVER_TO_NEMO_LANG`); the
goldens are keyed by the NeMo code.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from collections import OrderedDict
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Server language codes -> NeMo text_normalization language packages (model/src/zonos3/registries/languages.json).
SERVER_TO_NEMO_LANG: Dict[str, str] = {
    "en_us": "en",
    "en_gb": "en",
    "fr_fr": "fr",
    "de": "de",
    "es": "es",
    "it": "it",
    "pt_br": "pt",
    "ja": "ja",
    "cmn": "zh",
    "ko": "ko",
}

# zonos3.tts.markup, inlined.
_NONVERBAL_MARKUP = re.compile(r"</?(?:laugh|breath|sigh|cough|panting|shouting|crying)\s*/?>")
_NONVERBAL_MARKUP_SPLIT = re.compile(f"({_NONVERBAL_MARKUP.pattern})")


def has_nonverbal_markup(text: str) -> bool:
    return _NONVERBAL_MARKUP.search(text) is not None


def split_nonverbal_markup(text: str) -> list[str]:
    return _NONVERBAL_MARKUP_SPLIT.split(text)


# Upstream's own tests run Korean grammars with lower_cased input; everything
# else uses cased.
LOWER_CASED_LANGS = {"ko"}

# zh/ja verbalizers read a cached .far but never write one (upstream quirk);
# we post-write it after first compile so later loads are fast. Note ja reads
# a "jp_" prefixed name.
_VERBALIZER_FAR_PREFIX = {"zh": "zh", "ja": "jp"}

# A digit directly followed by sentence punctuation confuses several upstream
# r1.2.0 grammars: pt's tagger raises FstOpError outright and de reads dates
# digit-by-digit (reproduced with upstream code and its pinned pynini
# 2.1.6.post1 — upstream bugs, not vendoring artifacts). Space the punctuation
# off before normalization; it is re-attached afterwards.
_DIGIT_PUNCT_RE = re.compile(r"(\d)([.!?,;:])(?=\s|$)")
_SPACE_PUNCT_RE = re.compile(r" +([.!?,;:])(?=\s|$)")

# Moses-based punct_post_process re-attaches punctuation well for these
# languages. For the European languages it also glues currency symbols to the
# following word ("5,32 € am" -> "€am"), so there we skip moses and only
# collapse the spacing we introduced ourselves.
_MOSES_POSTPROCESS_LANGS = {"en", "zh", "ja", "ko"}

_LINE_BREAK_RE = re.compile(r"\s*[^\S ]\s*")

# Normalized texts kept per TTSTextNormalizer (LRU over (text, language)).
NORMALIZED_MEMO_SIZE = 1024


def collapse_line_breaks(text: str) -> str:
    """One plain space for every whitespace run that contains a line break, tab or non-breaking space."""
    return _LINE_BREAK_RE.sub(" ", text) if text else text


# Pronunciation groups of phoneme-token checkpoints (zonos3.tts.superbpe): never normalized.
_PHONEME_OPEN = "\ue000"
_PHONEME_GROUP_RE = re.compile("(\ue000[^\ue000\ue001]*\ue001)")


# Written with escapes: U+F900 is a CJK compatibility ideograph that NFC-normalizing editors rewrite to U+8C48.
_CJK = "\u3000-\u303f\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef"
_CJK_SPACE_RE = re.compile(rf"(?<=[{_CJK}])\s+(?=[{_CJK}])")
_CJK_LANGS = {"ja", "zh"}

_DE_OTHER_PUNCT_RE = re.compile(r"(\d)([!?,;:])(?=\s|$)")
_DE_FINAL_PERIOD_RE = re.compile(r"(\d)(\.)(?=[\"'»“”)\]]*\s*$)")
_DE_LONG_PERIOD_RE = re.compile(r"(\d{3,})(\.)(?=\s|$)")

_PT_TRAIL_PUNCT_RE = re.compile(r"(\S*[\d%ºª]\S*?)([.!?,;:)\]]+)(?=\s|$)")
_PT_LEAD_BRACKET_RE = re.compile(r"(^|\s)([(\[])(?=\S*\d)")
_PT_SPACE_TRAIL_RE = re.compile(r" +([.!?,;:)\]]+)(?=\s|$)")
_PT_SPACE_LEAD_RE = re.compile(r"([(\[]) +")

_EN_SLASH_PAIRS = {("24", "7"), ("9", "11"), ("7", "11")}
_EN_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")
_EN_MONEY_K_RE = re.compile(r"([$£€])(\d+(?:\.\d+)?)[kK]\b")

# Sentence boundaries for the per-sentence retry after a grammar failure.
_SENTENCE_RE = re.compile(r"(?<=[.!?;:])\s+|(?<=[。！？])")


def _en_slash(m: "re.Match[str]") -> str:
    a, b = m.group(1), m.group(2)
    if (a, b) in _EN_SLASH_PAIRS or (len(a) == 2 and len(b) == 2 and int(a) + int(b) == 100):
        return f"{a} {b}"
    return m.group(0)


def _en_money_k(m: "re.Match[str]") -> str:
    return f"{m.group(1)}{int(round(float(m.group(2)) * 1000)):,}"


def pre_normalize(text: str, lang: str) -> str:
    """The language-specific rewrite applied right before the NeMo grammar (see the notes above)."""
    if lang in _CJK_LANGS:
        return _CJK_SPACE_RE.sub("", text)
    if lang == "de":
        text = _DE_OTHER_PUNCT_RE.sub(r"\1 \2", text)
        text = _DE_FINAL_PERIOD_RE.sub(r"\1 \2", text)
        return _DE_LONG_PERIOD_RE.sub(r"\1 \2", text)
    if lang == "pt":
        text = _PT_TRAIL_PUNCT_RE.sub(r"\1 \2", text)
        return _PT_LEAD_BRACKET_RE.sub(r"\1\2 ", text)
    text = _DIGIT_PUNCT_RE.sub(r"\1 \2", text)
    if lang == "en":
        text = _EN_SLASH_RE.sub(_en_slash, text)
        text = _EN_MONEY_K_RE.sub(_en_money_k, text)
    return text


def post_normalize(result: str, lang: str) -> str:
    """Re-attach the punctuation pre_normalize() spaced off."""
    if lang == "pt":
        result = _PT_SPACE_TRAIL_RE.sub(r"\1", result)
        return _PT_SPACE_LEAD_RE.sub(r"\1", result)
    return _SPACE_PUNCT_RE.sub(r"\1", result)


def default_cache_root() -> str:
    return os.environ.get(
        "ZONOS3_TTS_NORM_CACHE_DIR",
        os.path.expanduser("~/.cache/zonos3-tts-norm"),
    )


def normalization_enabled() -> bool:
    return os.environ.get("ZONOS3_TTS_NORM", "1") != "0"


class TTSTextNormalizer:
    """Lazy per-language NeMo normalizers with .far caching (see the module docstring of the original)."""

    def __init__(self, cache_root: str | None = None):
        self.cache_root = cache_root or default_cache_root()
        self._normalizers: Dict[str, object] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._memo: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._memo_lock = threading.Lock()

    @staticmethod
    def nemo_lang(language: str) -> Optional[str]:
        return SERVER_TO_NEMO_LANG.get(language)

    def supported(self, language: str) -> bool:
        return language in SERVER_TO_NEMO_LANG

    def _lang_lock(self, lang: str) -> threading.Lock:
        with self._global_lock:
            if lang not in self._locks:
                self._locks[lang] = threading.Lock()
            return self._locks[lang]

    def _build(self, lang: str):
        from nemo_text_processing.text_normalization import Normalizer

        input_case = "lower_cased" if lang in LOWER_CASED_LANGS else "cased"
        cache_dir = os.path.join(self.cache_root, f"{lang}_{input_case}")
        os.makedirs(cache_dir, exist_ok=True)

        logger.info("Loading TTS text normalizer for '%s' (%s)...", lang, input_case)
        normalizer = Normalizer(
            input_case=input_case,
            lang=lang,
            cache_dir=cache_dir,
            overwrite_cache=False,
        )

        prefix = _VERBALIZER_FAR_PREFIX.get(lang)
        if prefix is not None:
            far_path = os.path.join(cache_dir, f"{prefix}_tn_True_deterministic_verbalizer.far")
            if not os.path.exists(far_path):
                from nemo_text_processing.text_normalization.en.graph_utils import generator_main

                generator_main(far_path, {"verbalize": normalizer.verbalizer.fst})
        return normalizer

    def get(self, lang: str):
        with self._lang_lock(lang):
            if lang not in self._normalizers:
                self._normalizers[lang] = self._build(lang)
            return self._normalizers[lang]

    def warmup(self, languages: list[str] | None = None) -> None:
        langs = languages or sorted(set(SERVER_TO_NEMO_LANG.values()))
        for lang in langs:
            lang = SERVER_TO_NEMO_LANG.get(lang, lang)
            try:
                self.get(lang)
            except Exception:  # noqa: BLE001
                logger.exception("TTS text normalizer warmup failed for '%s'", lang)

    def _normalize_once(self, text: str, lang: str) -> str:
        normalizer = self.get(lang)
        text_in = pre_normalize(text, lang)
        with self._lang_lock(lang):
            result = normalizer.normalize(text_in, punct_post_process=lang in _MOSES_POSTPROCESS_LANGS)
        if not isinstance(result, str) or not result.strip():
            raise ValueError("empty normalizer output")
        return post_normalize(result, lang)

    def normalize(self, text: str, language: str) -> str:
        key = (text, language)
        with self._memo_lock:
            result = self._memo.get(key)
            if result is not None:
                self._memo.move_to_end(key)
                return result
        result = self._normalize_uncached(text, language)
        with self._memo_lock:
            self._memo[key] = result
            while len(self._memo) > NORMALIZED_MEMO_SIZE:
                self._memo.popitem(last=False)
        return result

    def _normalize_uncached(self, text: str, language: str) -> str:
        text = collapse_line_breaks(text)  # every return path hands back single-line text
        if SERVER_TO_NEMO_LANG.get(language) is None or not has_nonverbal_markup(text):
            return self._normalize_groups(text, language)
        out = []
        for index, piece in enumerate(split_nonverbal_markup(text)):
            core = piece.strip()
            if index % 2 or not core:
                out.append(piece if index % 2 else (" " if piece else ""))
                continue
            lead = " " if piece[0].isspace() else ""
            trail = " " if piece[-1].isspace() else ""
            out.append(lead + self._normalize_groups(core, language) + trail)
        result = "".join(out).strip()
        return result

    def _normalize_groups(self, text: str, language: str) -> str:
        if _PHONEME_OPEN in text:
            pieces = _PHONEME_GROUP_RE.split(text)
            for i in range(0, len(pieces), 2):
                stretch = pieces[i]
                if stretch.strip():
                    lead, trail = stretch[: len(stretch) - len(stretch.lstrip())], stretch[len(stretch.rstrip()) :]
                    pieces[i] = lead + self._normalize_text(stretch.strip(), language) + trail
            return "".join(pieces)
        return self._normalize_text(text, language)

    def _normalize_text(self, text: str, language: str) -> str:
        lang = SERVER_TO_NEMO_LANG.get(language)
        text = collapse_line_breaks(text)  # every return path below hands back single-line text
        if lang is None or not text.strip():
            return text
        try:
            result = self._normalize_once(text, lang)
        except Exception:  # noqa: BLE001
            logger.exception("TTS text normalization failed for lang=%s; retrying sentence by sentence", language)
            pieces = []
            for piece in _SENTENCE_RE.split(text):
                if not piece or not piece.strip():
                    continue
                try:
                    pieces.append(self._normalize_once(piece, lang))
                except Exception:  # noqa: BLE001
                    logger.warning("TTS text normalization failed for lang=%s on %r; kept as typed", language, piece)
                    pieces.append(piece)
            result = ("" if lang in _CJK_LANGS else " ").join(pieces)
        return result
