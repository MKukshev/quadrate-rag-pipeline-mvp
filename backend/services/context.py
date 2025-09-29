import re
from typing import Iterable

from . import config

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_WORD_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def _extract_keywords(query: str, min_len: int = 3) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(query or "")
        if len(token) >= min_len
    }


def compress_text(text: str, query: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not sentences:
        return text[: config.CONTEXT_SNIPPET_MAX_CHARS]

    keywords = _extract_keywords(query)
    if keywords:
        selected: list[str] = []
        for sentence in sentences:
            lowered = sentence.lower()
            if any(kw in lowered for kw in keywords):
                selected.append(sentence)
        if not selected:
            selected = sentences[:2]
    else:
        selected = sentences[:2]

    snippet = " ".join(selected)
    if len(snippet) >= config.CONTEXT_SNIPPET_MAX_CHARS:
        return snippet[: config.CONTEXT_SNIPPET_MAX_CHARS].rsplit(" ", 1)[0] + "…"

    remaining_chars = config.CONTEXT_SNIPPET_MAX_CHARS - len(snippet)
    for sentence in sentences:
        if sentence in selected:
            continue
        if len(sentence) + 1 > remaining_chars:
            break
        snippet += " " + sentence
        remaining_chars = config.CONTEXT_SNIPPET_MAX_CHARS - len(snippet)
        if remaining_chars <= 0:
            break
    return snippet
