"""Autocomplete for the editor.

Provides two styles of completion:
  * Keyword completion -- pre-defined per-language keywords.
  * Word completion   -- words already present in the current document.

The popup is a Tkinter listbox shown near the cursor. The editor widget
drives it via the completion engine returned here.
"""

import re

from .syntax import _LANGUAGES


# Language keyword sets, extracted from the syntax definitions above.
# We reuse the same source of truth for keyword/function/builtin words so
# the completion list is consistent with highlighting where practical.
def _extract_words(name):
    """Return a set of identifier-ish words for a language's keyword patterns."""
    words = set()
    for regex, category in _LANGUAGES.get(name, []):
        if category not in ("keyword", "builtin", "class"):
            continue
        # Handle the \b(?:a|b|c...)\b alternation-group form used for keywords.
        for m in re.finditer(r'\\b\(\?:([^)]+)\)\\b', regex):
            for word in m.group(1).split("|"):
                word = word.strip()
                if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', word):
                    words.add(word)
        # Also catch standalone \bword\b occurrences (e.g. builtins).
        for m in re.finditer(r'\\b([A-Za-z_][A-Za-z0-9_]*)\\b', regex):
            words.add(m.group(1))
    return words


# Cache per language to avoid re-parsing regexes constantly.
_KEYWORD_CACHE = {}


def keywords_for(language):
    if language not in _KEYWORD_CACHE:
        _KEYWORD_CACHE[language] = sorted(_extract_words(language))
    return _KEYWORD_CACHE[language]


class Completer:
    """Holds the completion state for one text widget."""

    def __init__(self, text_widget):
        self.text = text_widget
        self.listbox = None
        self.matches = []
        self.current_idx = 0
        self.active = False

    def word_matches(self, prefix, language):
        """Return candidate words matching prefix from keywords + document."""
        kw = keywords_for(language)

        # Gather document words
        doc_words = set()
        content = self.text.get("1.0", "end")
        for m in re.finditer(r'\b[A-Za-z_][A-Za-z0-9_]*\b', content):
            doc_words.add(m.group(0))

        candidates = set(kw) | doc_words
        prefix_l = prefix.lower()
        ranked = [w for w in sorted(candidates) if w.lower().startswith(prefix_l)]
        return ranked[:200]
