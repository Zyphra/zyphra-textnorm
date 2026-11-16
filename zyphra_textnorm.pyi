"""Text normalization for TTS: written text to its spoken form ("$5.32" -> "five dollars thirty two cents")."""

from collections.abc import Iterable

LANGUAGES: list[str]
"""The grammar languages (ISO 639-1; ``zh`` is Mandarin)."""

__version__: str

class Normalizer:
    """A text normalizer: the markup it keeps as typed and its memo of the last 1024 results. Thread-safe."""

    def __init__(self, markup_tags: Iterable[str] = (), prepass: bool = True) -> None:
        """``markup_tags``: tag names whose markup stays as typed: point tags (``<laugh/>``, ``<laugh>``) and span tags
        (``<shouting>...</shouting>``). ``prepass``: run the pre-pass first (markdown, HTML, emoji, look-alike characters,
        and each language's readings of numbers, dates, money, phone numbers, addresses and equations rewritten before
        the grammars; see ``prepass``). ``prepass=False``: every output is the NeMo-parity output."""

    @property
    def markup_tags(self) -> list[str]: ...
    @property
    def prepass(self) -> bool: ...
    def normalize(self, text: str, language: str) -> str:
        """The spoken form of ``text`` in ``language`` (one of ``LANGUAGES``), memoized. Never raises: a language
        without a grammar comes back with its line breaks collapsed, and a sentence the grammar fails on is kept as
        typed. Markup and verbatim spans (U+E000 ... U+E001) stay as typed. Releases the GIL."""

    def clear_memo(self) -> None: ...

def normalize(text: str, language: str) -> str:
    """``Normalizer().normalize(text, language)`` on a shared normalizer without markup tags."""

PREPASS_RULES: list[str]
"""The pre-pass rules in the order they run."""

def prepass(text: str, language: str, markup_tags: Iterable[str] = ()) -> tuple[str, list[tuple[str, str, str]]]:
    """The pre-pass alone: the rewritten text and each rewrite as ``(rule, before, after)``. The normalizer runs it
    itself unless ``Normalizer(prepass=False)``; this is for inspecting what the rules do."""

def collapse_line_breaks(text: str) -> str:
    """One plain space for every whitespace run that contains a line break, tab or other non-space whitespace."""

def supported(language: str) -> bool:
    """Whether this build has a grammar for ``language``."""
