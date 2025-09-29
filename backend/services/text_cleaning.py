import re
from typing import Iterable

_BOILERPLATE_PATTERNS: Iterable[re.Pattern] = [
    re.compile(r"^дисклеймер", re.IGNORECASE),
    re.compile(r"^конфиденциально", re.IGNORECASE),
    re.compile(r"^пожалуйста не отвечайте", re.IGNORECASE),
]


def clean_chunk(text: str) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines()]
    cleaned_lines = []
    for line in lines:
        if not line:
            continue
        if any(pattern.search(line) for pattern in _BOILERPLATE_PATTERNS):
            continue
        cleaned_lines.append(line)
    cleaned = " \n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
