"""Text normalization for TTS: written text to its spoken form ("$5.32" -> "five dollars thirty two cents")."""

from collections.abc import Iterable

LANGUAGES: list[str]
"""The grammar languages (ISO 639-1; ``zh`` is Mandarin)."""

__version__: str

class Normalizer:
    """A text normalizer: the markup it keeps as typed and its memo of the last 1024 results. Thread-safe."""

    def __init__(self, markup_tags: Iterable[str] = ()) -> None:
        """``markup_tags``: tag names whose markup stays as typed: point tags (``<laugh/>``, ``<laugh>``) and span tags
        (``<shouting>...</shouting>``)."""

    @property
    def markup_tags(self) -> list[str]: ...
    def normalize(self, text: str, language: str) -> str:
        """The spoken form of ``text`` in ``language`` (one of ``LANGUAGES``), memoized. Never raises: a language
        without a grammar comes back with its line breaks collapsed, and a sentence the grammar fails on is kept as
        typed. Markup and verbatim spans (U+E000 ... U+E001) stay as typed. Releases the GIL."""

    def clear_memo(self) -> None: ...

def normalize(text: str, language: str) -> str:
    """``Normalizer().normalize(text, language)`` on a shared normalizer without markup tags."""

def collapse_line_breaks(text: str) -> str:
    """One plain space for every whitespace run that contains a line break, tab or other non-space whitespace."""

def supported(language: str) -> bool:
    """Whether this build has a grammar for ``language``."""
